"""Offline structural inspection of a pinned wheelhouse; never extract or import it."""

import base64
import configparser
import csv
from email.parser import HeaderParser
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[2]
DOWNLOAD = REPO / "docs/poc/oracle9_wheels_download.py"
DOWNLOAD_SHA = "e3c243cc714123e15589e70442d439ed37d68c0c58618e5e93bfbae0bead50b1"
MANIFEST_SHA = "1d16b3e1115bc3bd955a95640ca90101c72adca2c518b1deb9af6a474787fd02"
LOCK_SHA = "e24ec23e810e8cf7203ae4599d0a3e1ea6b9a98b795df72153f12ba08d31fce0"
MAX_ENTRIES = 10000
MAX_MEMBER = 64 * 1024 * 1024
MAX_WHEEL = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_REPORT = 16 * 1024 * 1024
MAX_ENVELOPE = 2 * 1024 * 1024
SPECIAL_LIMITS = {"METADATA": 1024 * 1024, "WHEEL": 65536, "RECORD": 2 * 1024 * 1024}


class Refused(RuntimeError):
    """Closed diagnostic category, with public archive/member identity separately."""


def need(value, category):
    if not value:
        raise Refused(category)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(65536):
            h.update(block)
    return h.hexdigest()


def regular(path):
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "FILE")


def directory(path):
    s = path.lstat()
    need(stat.S_ISDIR(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "DIRECTORY")


def canonical(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def safe_name(name):
    need(isinstance(name, str) and 0 < len(name.encode("utf-8")) <= 512, "PATH")
    need(not any(ord(c) < 32 or ord(c) == 127 for c in name), "PATH")
    need(not any(c in name for c in ("\\", ":")) and not name.startswith("/"), "PATH")
    parts = name.rstrip("/").split("/")
    need(all(p not in ("", ".", "..") for p in parts), "PATH")
    return parts


def extra_fields(raw):
    offset = 0
    fields = []
    need(len(raw) <= 4096, "EXTRA")
    while offset < len(raw):
        need(offset + 4 <= len(raw), "EXTRA")
        kind, length = struct.unpack_from("<HH", raw, offset)
        offset += 4
        need(kind != 1 and offset + length <= len(raw), "ZIP64_OR_EXTRA")
        fields.append({"kind": kind, "bytes": length, "sha256": sha(raw[offset : offset + length])})
        offset += length
    return fields


def central_preflight(f):
    size = f.seek(0, 2)
    need(22 <= size <= 32 * 1024 * 1024, "ZIP_SIZE")
    f.seek(max(0, size - 65557))
    tail = f.read(65557)
    at = tail.rfind(b"PK\x05\x06")
    need(at >= 0 and at + 22 <= len(tail), "EOCD")
    signature, disk, cd_disk, on_disk, total, length, start, comment = struct.unpack_from(
        "<4s4H2LH", tail, at
    )
    need(signature == b"PK\x05\x06" and disk == cd_disk == 0, "MULTIDISK")
    need(0 < total == on_disk <= MAX_ENTRIES and total != 65535, "ENTRY_COUNT")
    need(comment <= 4096 and at + 22 + comment == len(tail), "TRAILING_OR_COMMENT")
    need(0 < length <= 2 * 1024 * 1024 and start + length == size - len(tail) + at, "CD_RANGE")
    f.seek(0)
    need(f.read(4) == b"PK\x03\x04", "PREFIX")
    return start, total


def local_range(f, info, cd_start):
    f.seek(info.header_offset)
    raw = f.read(30)
    need(len(raw) == 30, "LOCAL_HEADER")
    sig, version, flags, method, _, _, crc, compressed, expanded, names, extras = struct.unpack(
        "<4s5H3L2H", raw
    )
    need(sig == b"PK\x03\x04" and version <= 45, "LOCAL_VERSION")
    need(flags == info.flag_bits and method == info.compress_type, "LOCAL_MISMATCH")
    need(names <= 512 and extras <= 4096, "LOCAL_SIZE")
    name = f.read(names)
    need(name.decode("utf-8" if flags & 0x800 else "cp437") == info.orig_filename, "LOCAL_NAME")
    local_extras = extra_fields(f.read(extras))
    begin = f.tell()
    end = begin + info.compress_size
    need(end <= cd_start, "MEMBER_RANGE")
    if flags & 8:
        need(crc in (0, info.CRC) and compressed in (0, info.compress_size), "DESCRIPTOR_HEADER")
        need(expanded in (0, info.file_size), "DESCRIPTOR_HEADER")
        f.seek(end)
        descriptor = f.read(16)
        signed = descriptor[:4] == b"PK\x07\x08"
        width = 16 if signed else 12
        need(len(descriptor) >= width and end + width <= cd_start, "DESCRIPTOR")
        values = struct.unpack("<3L", descriptor[4:16] if signed else descriptor[:12])
        need(values == (info.CRC, info.compress_size, info.file_size), "DESCRIPTOR")
        end += width
    else:
        need(
            (crc, compressed, expanded) == (info.CRC, info.compress_size, info.file_size),
            "LOCAL_SIZE",
        )
    return info.header_offset, begin, end, {"needed_version": version, "extras": local_extras}


def stream_member(f, info, begin, deadline):
    f.seek(begin)
    left, size, crc = info.compress_size, 0, 0
    decoder = zlib.decompressobj(-15) if info.compress_type == 8 else None
    while left:
        need(time.monotonic() < deadline, "DEADLINE")
        raw = f.read(min(left, 65536))
        need(raw, "TRUNCATED")
        left -= len(raw)
        pending = raw
        while pending:
            block = decoder.decompress(pending, 65536) if decoder else pending
            pending = decoder.unconsumed_tail if decoder else b""
            size += len(block)
            need(size <= info.file_size and size <= MAX_MEMBER, "EXPANSION")
            crc = zlib.crc32(block, crc)
            if block:
                yield block
            if decoder:
                need(
                    not decoder.unused_data and not (decoder.eof and (pending or left)),
                    "DEFLATE_TAIL",
                )
    # Input may be exhausted while zlib still holds match output internally.
    # Drain with a bounded max_length; unbounded flush() would allocate first.
    while decoder is not None and not decoder.eof:
        need(time.monotonic() < deadline, "DEADLINE")
        block = decoder.decompress(b"", 65536)
        need(not decoder.unused_data, "DEFLATE_TAIL")
        if not block:
            break
        size += len(block)
        need(size <= info.file_size and size <= MAX_MEMBER, "EXPANSION")
        crc = zlib.crc32(block, crc)
        yield block
    need(decoder is None or decoder.eof, "DEFLATE_TRUNCATED")
    need(size == info.file_size and crc == info.CRC, "CRC_OR_SIZE")


def headers(raw):
    text = raw.decode("utf-8")
    need("\x00" not in text, "METADATA_ENCODING")
    msg = HeaderParser().parsestr(text)
    need(not msg.defects, "METADATA_PARSE")
    return msg


def field(msg, key, required=True):
    values = msg.get_all(key, [])
    need(len(values) == 1 if required else len(values) <= 1, "METADATA_DUPLICATE_OR_MISSING")
    return unfold(values[0]) if values else None


def unfold(value):
    # PEP566 headers, with conservative RFC folding only. Not a PEP508 resolver.
    text = re.sub(r"\r?\n[ \t]+", " ", value).strip()
    need("\n" not in text and "\r" not in text, "METADATA_FOLD")
    return text


def inspect_metadata(blobs, entry, dist, filename_tags):
    meta, wheel = headers(blobs[dist + "/METADATA"]), headers(blobs[dist + "/WHEEL"])
    need(canonical(field(meta, "Name")) == entry["name"], "METADATA_NAME")
    need(field(meta, "Version") == entry["version"], "METADATA_VERSION")
    requires = [unfold(v) for v in meta.get_all("Requires-Dist", [])]
    need(set(requires) == {unfold(v) for v in entry["requires_dist"]}, "REQUIRES_DIST")
    python = field(meta, "Requires-Python", False)
    expected = entry["requires_python"]
    need(python == (unfold(expected) if expected is not None else None), "REQUIRES_PYTHON")
    need(re.fullmatch(r"1\.[0-9]+", field(wheel, "Wheel-Version")), "WHEEL_VERSION")
    pure = field(wheel, "Root-Is-Purelib")
    need(pure in ("true", "false"), "PURELIB")
    tags = [unfold(v) for v in wheel.get_all("Tag", [])]
    need(len(tags) == len(set(tags)) and set(tags) == filename_tags, "TAGS")
    need((pure == "true") == all(v.endswith("-none-any") for v in tags), "PURELIB_TAGS")
    return {
        "requires_dist": requires,
        "requires_python": python,
        "tags": tags,
        "root_is_purelib": pure == "true",
        "metadata_version": field(meta, "Metadata-Version"),
        "license_expression": field(meta, "License-Expression", False),
        "license": field(meta, "License", False),
    }


def inspect_record(raw, inventory, dist):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True))
    need(len(rows) <= MAX_ENTRIES, "RECORD_COUNT")
    actual = {v["path"]: v for v in inventory if not v["directory"]}
    record = dist + "/RECORD"
    signatures = {dist + "/RECORD.jws", dist + "/RECORD.p7s"} & set(actual)
    seen = set()
    for row in rows:
        need(len(row) == 3, "RECORD_COLUMNS")
        name, encoded, size = row
        safe_name(name)
        need(name in actual and name not in seen and name not in signatures, "RECORD_MEMBER")
        seen.add(name)
        if name == record:
            need(encoded == size == "", "RECORD_SELF")
            continue
        need(re.fullmatch(r"0|[1-9][0-9]{0,9}", size), "RECORD_SIZE")
        need(int(size) == actual[name]["bytes"], "RECORD_SIZE")
        algorithm, sep, digest = encoded.partition("=")
        need(sep and algorithm in ("sha256", "sha384", "sha512"), "RECORD_ALGORITHM")
        need(re.fullmatch(r"[A-Za-z0-9_-]+", digest), "RECORD_DIGEST")
        expected = actual[name]["hashes"][algorithm]
        need(digest == expected, "RECORD_HASH")
    need(seen == set(actual) - signatures, "RECORD_COVERAGE")
    return sorted(signatures)


def inspect_wheel(path, entry, deadline):
    regular(path)
    need(file_sha(path) == entry["sha256"], "ARCHIVE_HASH")
    parts = entry["filename"][:-4].split("-")
    need(len(parts) in (5, 6) and canonical(parts[0]) == entry["name"], "FILENAME")
    need(parts[1] == entry["version"], "FILENAME")
    tags = {"-".join(v) for v in itertools.product(*(v.split(".") for v in parts[-3:]))}
    prefix = parts[0] + "-" + parts[1]
    dist = prefix + ".dist-info"
    data = prefix + ".data"
    inventory, blobs, seen, total = [], {}, set(), 0
    with path.open("rb") as f:
        cd_start, count = central_preflight(f)
        with zipfile.ZipFile(f) as archive:
            infos = archive.infolist()
            need(len(infos) == count, "CD_COUNT")
            ranges = {}
            for info in infos:
                name = info.filename
                members = safe_name(name)
                need(name == info.orig_filename and name not in seen, "DUPLICATE_OR_NUL")
                seen.add(name)
                need(
                    info.compress_type in (0, 8) and not info.flag_bits & ~0x80E, "METHOD_OR_FLAGS"
                )
                need(info.compress_type == 8 or not info.flag_bits & 6, "FLAGS")
                need(len(info.comment) <= 1024, "MEMBER_COMMENT")
                extra_fields(info.extra)
                need(info.volume == 0, "MULTIDISK_MEMBER")
                mode = info.external_attr >> 16
                need(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), "SPECIAL_FILE")
                need(not mode & 0o6000, "PRIVILEGE_BITS")
                need(stat.S_IFMT(mode) != stat.S_IFDIR or info.is_dir(), "DIRECTORY_MODE")
                need(not info.is_dir() or info.file_size == 0, "DIRECTORY_SIZE")
                need(info.file_size <= MAX_MEMBER, "MEMBER_SIZE")
                total += info.file_size
                need(total <= MAX_WHEEL, "WHEEL_EXPANSION")
                ranges[name] = local_range(f, info, cd_start)
            roots = {v.split("/", 1)[0] for v in seen}
            dist_roots = {v for v in roots if v.endswith(".dist-info")}
            data_roots = {v for v in roots if v.endswith(".data")}
            need(len(dist_roots) == 1 and len(data_roots) <= 1, "DIST_INFO_OR_DATA_COUNT")
            for names, suffix in ((dist_roots, ".dist-info"), (data_roots, ".data")):
                for name in names:
                    identity = name[: -len(suffix)].rsplit("-", 1)
                    need(
                        len(identity) == 2
                        and canonical(identity[0]) == entry["name"]
                        and identity[1] == entry["version"],
                        "DIST_INFO_OR_DATA_IDENTITY",
                    )
            dist = next(iter(dist_roots))
            data = next(iter(data_roots)) if data_roots else data
            for name in seen:
                members = name.rstrip("/").split("/")
                if members[0] == data and len(members) > 1:
                    need(
                        members[1] in ("purelib", "platlib", "headers", "scripts", "data"),
                        "DATA_SCHEME",
                    )
            ordered = sorted(ranges.values(), key=lambda v: v[0])
            end = 0
            for begin, _, finish, _facts in ordered:
                need(begin == end and finish >= begin, "OVERLAP_PREFIX_OR_GAP")
                end = finish
            need(end == cd_start, "DATA_GAP")
            paths = {v.rstrip("/") for v in seen}
            need(len(paths) == len(seen), "FILE_DIRECTORY_CONFLICT")
            for info in infos:
                ancestors = info.filename.rstrip("/").split("/")[:-1]
                for index in range(1, len(ancestors) + 1):
                    need("/".join(ancestors[:index]) not in seen, "FILE_DIRECTORY_CONFLICT")
                name = info.filename
                basename = name.rsplit("/", 1)[-1]
                capture = name in {dist + "/" + v for v in SPECIAL_LIMITS}
                limit = SPECIAL_LIMITS.get(basename, MAX_MEMBER) if capture else MAX_MEMBER
                if name.lower().endswith(".pth") or name == dist + "/entry_points.txt":
                    capture, limit = True, 65536
                need(info.file_size <= limit, "METADATA_SIZE")
                hashes = {v: hashlib.new(v) for v in ("sha256", "sha384", "sha512")}
                buffer, head = bytearray(), bytearray()
                for block in stream_member(f, info, ranges[name][1], deadline):
                    for h in hashes.values():
                        h.update(block)
                    if len(head) < 4:
                        head.extend(block[: 4 - len(head)])
                    if capture:
                        buffer.extend(block)
                        need(len(buffer) <= limit, "METADATA_SIZE")
                row = {
                    "path": name,
                    "bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "method": info.compress_type,
                    "flags": info.flag_bits,
                    "central_extras": extra_fields(info.extra),
                    "local_header": ranges[name][3],
                    "mode": info.external_attr >> 16,
                    "directory": info.is_dir(),
                    "sha256": hashes["sha256"].hexdigest(),
                    "elf": head == b"\x7fELF",
                    "native_path": bool(re.search(r"\.(?:so(?:\.|$)|dll$|dylib$|pyd$)", name)),
                    "hashes": {
                        k: base64.urlsafe_b64encode(h.digest()).rstrip(b"=").decode()
                        for k, h in hashes.items()
                    },
                }
                inventory.append(row)
                if capture:
                    blobs[name] = bytes(buffer)
            need(all(dist + "/" + v in blobs for v in SPECIAL_LIMITS), "DIST_INFO_MISSING")
            metadata = inspect_metadata(blobs, entry, dist, tags)
            signatures = inspect_record(blobs[dist + "/RECORD"], inventory, dist)
    need(file_sha(path) == entry["sha256"], "ARCHIVE_CHANGED")
    pth = [
        {"path": k, "bytes": len(v), "sha256": sha(v), "utf8": v.decode("utf-8")}
        for k, v in blobs.items()
        if k.lower().endswith(".pth")
    ]
    eps = {}
    if dist + "/entry_points.txt" in blobs:
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(blobs[dist + "/entry_points.txt"].decode("utf-8"))
        need(not parser.defaults(), "ENTRYPOINT_DEFAULTS")
        eps = {group: dict(parser.items(group, raw=True)) for group in parser.sections()}
    return {
        "name": entry["name"],
        "version": entry["version"],
        "filename": entry["filename"],
        "archive_sha256": entry["sha256"],
        "expanded_bytes": total,
        "metadata": metadata,
        "signatures_unverified": signatures,
        "pth_unapproved": pth,
        "entry_points": eps,
        "scripts": [
            v["path"]
            for v in inventory
            if v["path"].startswith(data + "/scripts/") and not v["directory"]
        ],
        "members": inventory,
    }


def admission(root):
    directory(root)
    regular(DOWNLOAD)
    need(DOWNLOAD.stat().st_size <= 65536, "DOWNLOAD_PROGRAM_SIZE")
    source = DOWNLOAD.read_bytes()
    need(sha(source) == DOWNLOAD_SHA, "DOWNLOAD_PROGRAM")
    ns = {"__name__": "_frozen_download_admission", "__file__": str(DOWNLOAD)}
    # Trusted, captured, hash-pinned repository code, not wheel/package code.
    exec(compile(source, str(DOWNLOAD), "exec"), ns)
    for filename, expected in (
        ("manifest.json", MANIFEST_SHA),
        ("requirements.dependencies.lock", LOCK_SHA),
    ):
        regular(root / filename)
        need(file_sha(root / filename) == expected, "INPUT_MANIFEST")
    regular(root / "attempt.json")
    regular(root / "download-result.json")
    need(
        (root / "attempt.json").stat().st_size <= 65536
        and (root / "download-result.json").stat().st_size <= 1024 * 1024,
        "STATE_SIZE",
    )
    state = json.loads((root / "attempt.json").read_bytes())
    result = json.loads((root / "download-result.json").read_bytes())
    need(
        state["task"] == "0db814cd7c2844bca53f54a1bcca0726"
        and state["invoked"] is True
        and state["wheelhouse_ready"] is True,
        "DOWNLOAD_NOT_READY",
    )
    need(result["outcome"] == "WHEELS_DOWNLOADED_VERIFIED", "DOWNLOAD_NOT_READY")
    files = ns["selected_files"]()
    manifest = json.loads((root / "manifest.json").read_bytes())
    # All 36 regular files/hash/lock checked BEFORE opening any archive.
    ns["check_wheelhouse"](root, files, manifest)
    return files, manifest, ns


def write_new(path, raw):
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def main(root, output):
    need(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize, "RUNTIME")
    directory(output)
    need(
        output.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve(),
        "OUTPUT_ROOT",
    )
    need(output.name.startswith("maskgw-oracle9-inspect-"), "OUTPUT_ROOT")
    regular(output / "state.json")
    state = json.loads((output / "state.json").read_bytes())
    need(state["kind"] == "oracle9-wheel-inspection-v1" and state["invoked"] is False, "CONSUMED")
    need(
        state["program_sha256"] == file_sha(Path(__file__)) and state["wheelhouse"] == str(root),
        "PROGRAM",
    )
    write_new(output / "invoked.json", b'{"invoked":true}\n')
    files, manifest, ns = admission(root)
    results, total, current = [], 0, None
    outcome, category = "WHEELS_INSPECTION_REFUSED", None
    started = time.monotonic()
    try:
        for entry in files:
            current = entry["filename"]
            row = inspect_wheel(root / "wheels" / current, entry, started + 120)
            total += row["expanded_bytes"]
            need(total <= MAX_TOTAL, "TOTAL_EXPANSION")
            results.append(row)
            need(len(json.dumps(results).encode()) <= MAX_REPORT - 65536, "REPORT_SIZE")
        ns["check_wheelhouse"](root, files, manifest)
        outcome = "WHEELS_INSPECTED_STRUCTURALLY"
    except Refused as exc:
        category = str(exc)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        csv.Error,
        zipfile.BadZipFile,
        zlib.error,
        configparser.Error,
    ):
        category = "FORMAT_OR_IO"
    except Exception:
        # Preserve partial evidence on unexpected parser failures, never success.
        category = "UNEXPECTED"
    report = {
        "kind": "oracle9-wheel-inspection-result-v1",
        "outcome": outcome,
        "category": category,
        "current_file": current,
        "task": state["task"],
        "program_sha256": state["program_sha256"],
        "manifest_sha256": MANIFEST_SHA,
        "lock_sha256": LOCK_SHA,
        "expanded_bytes": total,
        "elapsed_seconds": time.monotonic() - started,
        "inspection_only_no_install": True,
        "wheels": results,
    }
    raw = (json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n").encode()
    need(len(raw) <= MAX_REPORT, "REPORT_SIZE")
    envelope = {
        "kind": "oracle9-wheel-inspection-envelope-v1",
        "raw_bytes": len(raw),
        "raw_sha256": sha(raw),
        "zlib_base64": base64.b64encode(zlib.compress(raw, 9)).decode(),
    }
    packet = (json.dumps(envelope, sort_keys=True) + "\n").encode()
    need(len(packet) <= MAX_ENVELOPE, "ENVELOPE_SIZE")
    write_new(output / "inspection.json.zlib-base64", packet)
    write_new(
        output / "summary.json",
        (
            json.dumps({k: v for k, v in report.items() if k != "wheels"}, sort_keys=True) + "\n"
        ).encode(),
    )
    print(
        json.dumps(
            {
                "outcome": outcome,
                "category": category,
                "count": len(results),
                "expanded_bytes": total,
                "envelope_sha256": sha(packet),
            }
        )
    )
    return 0 if outcome == "WHEELS_INSPECTED_STRUCTURALLY" else 1


if __name__ == "__main__":
    try:
        status = main(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, KeyError, RuntimeError):
        print("WHEELS_INSPECTION_ADMISSION_REFUSED")
        status = 1
    raise SystemExit(status)
