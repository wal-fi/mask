"""Synthetic wheel structures only: never opens the downloaded wheelhouse."""

import base64
import hashlib
import importlib.util
import io
import json
import struct
import time
import types
import zipfile
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def inspector() -> Any:
    path = Path(__file__).resolve().parents[1] / "docs/poc/oracle9_wheels_inspect.py"
    spec = importlib.util.spec_from_file_location("_inspection_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wheel(  # noqa: PLR0913 -- independent corruption controls in a test fixture.
    tmp_path: Path,
    *,
    extra: dict[str, bytes] | None = None,
    metadata: bytes | None = None,
    wheel_metadata: bytes | None = None,
    record_edit: str | None = None,
    method: int = zipfile.ZIP_DEFLATED,
    mode: int = 0o100644,
) -> tuple[Path, dict[str, Any]]:
    dist = "sample-1.0.dist-info/"
    files = {
        "sample/__init__.py": b"raise AssertionError('wheel code must not run')\n",
        dist + "METADATA": metadata
        or (
            b"Metadata-Version: 2.3\nName: Sample\nVersion: 1.0\nRequires-Python: >=3.11\n"
            b"Requires-Dist: other>=1; python_version > '3'\n\nPublic description.\n"
        ),
        dist + "WHEEL": wheel_metadata
        or b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
    }
    files.update(extra or {})
    rows = []
    for name, raw in files.items():
        if name.endswith(("/RECORD.jws", "/RECORD.p7s")):
            continue
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(raw)}\n")
    rows.append(dist + "RECORD,,\n")
    record = "".join(rows)
    if record_edit == "weak":
        record = record.replace("sha256=", "md5=", 1)
    elif record_edit == "hash":
        record = record.replace("sha256=", "sha256=X", 1)
    elif record_edit == "size":
        record = record.replace(f",{len(files['sample/__init__.py'])}\n", ",1\n", 1)
    elif record_edit == "missing":
        record = "\n".join(record.splitlines()[1:]) + "\n"
    elif record_edit == "duplicate":
        record += rows[0]
    elif record_edit == "self":
        record = record.replace("RECORD,,", "RECORD,sha256=X,0")
    elif record_edit == "columns":
        record += "extra,field,1,2\n"
    elif record_edit == "signature":
        record += dist + "RECORD.jws,,\n"
    files[dist + "RECORD"] = record.encode()
    path = tmp_path / "sample-1.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", compression=method) as archive:
        for name, raw in files.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = method
            info.external_attr = mode << 16
            archive.writestr(info, raw)
    entry = {
        "name": "sample",
        "version": "1.0",
        "filename": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "requires_python": ">=3.11",
        "requires_dist": ["other>=1; python_version > '3'"],
    }
    return path, entry


def inspect(inspector: Any, path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    result = inspector.inspect_wheel(path, entry, time.monotonic() + 10)
    assert isinstance(result, dict)
    return result


def rehash(path: Path, entry: dict[str, Any]) -> None:
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_full_inventory_record_and_metadata_without_execution(tmp_path, inspector, method):
    path, entry = wheel(tmp_path, method=method)
    result = inspect(inspector, path, entry)
    assert result["name"] == "sample" and len(result["members"]) == 4
    assert result["metadata"]["requires_dist"] == entry["requires_dist"]
    assert result["metadata"]["tags"] == ["py3-none-any"]
    assert sum(v["bytes"] for v in result["members"]) == result["expanded_bytes"]


def test_pth_plugins_scripts_and_native_are_inventoried_never_loaded(tmp_path, inspector):
    path, entry = wheel(
        tmp_path,
        extra={
            "canary.pth": b"import sys; raise AssertionError('never execute pth')\n",
            "sample-1.0.dist-info/entry_points.txt": (
                b"[console_scripts]\nhello = sample:main\n[plugin.group]\nPlugIn = sample:plugin\n"
            ),
            "sample-1.0.data/scripts/hello": b"#!/bin/sh\nexit 9\n",
            "sample/libfake.so.1": b"\x7fELFnot-an-executable",
            "sample-1.0.dist-info/RECORD.jws": b"signature-not-verified",
        },
    )
    result = inspect(inspector, path, entry)
    assert "never execute pth" in result["pth_unapproved"][0]["utf8"]
    assert result["entry_points"] == {
        "console_scripts": {"hello": "sample:main"},
        "plugin.group": {"PlugIn": "sample:plugin"},
    }
    assert result["scripts"] == ["sample-1.0.data/scripts/hello"]
    assert result["signatures_unverified"] == ["sample-1.0.dist-info/RECORD.jws"]
    native = next(v for v in result["members"] if v["elf"])
    assert native["path"] == "sample/libfake.so.1" and native["native_path"]
    assert not (tmp_path / "sample").exists()


@pytest.mark.parametrize(
    "bad", ["weak", "hash", "size", "missing", "duplicate", "self", "columns", "signature"]
)
def test_record_never_accepts_unverified_member(tmp_path, inspector, bad):
    path, entry = wheel(tmp_path, record_edit=bad)
    with pytest.raises(inspector.Refused):
        inspect(inspector, path, entry)


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/abs",
        "C:/drive",
        "back\\slash",
        "a//b",
        "a/./b",
        "a\x01b",
        "other-1.0.dist-info/x",
        "other-1.0.data/x",
        "sample/file/x",
    ],
)
def test_unsafe_or_conflicting_paths_refuse(tmp_path, inspector, name):
    path, entry = wheel(tmp_path, extra={"sample/file": b"file", name: b"bad"})
    with pytest.raises(inspector.Refused):
        inspect(inspector, path, entry)


@pytest.mark.parametrize("mode", [0o120777, 0o020600, 0o106644, 0o104644, 0o102644])
def test_symlink_special_and_privilege_modes_refuse(tmp_path, inspector, mode):
    path, entry = wheel(tmp_path, mode=mode)
    with pytest.raises(inspector.Refused):
        inspect(inspector, path, entry)


@pytest.mark.parametrize(
    "what", ["name", "version", "python", "requires", "duplicate", "tag", "major", "pure"]
)
def test_metadata_and_wheel_must_match_native_projection(tmp_path, inspector, what):
    path, entry = wheel(tmp_path)
    if what in ("name", "version", "python", "requires"):
        entry[{"python": "requires_python", "requires": "requires_dist"}.get(what, what)] = (
            ["different"] if what == "requires" else "different"
        )
    else:
        metadata = None
        wm = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"
        if what == "duplicate":
            metadata = b"Metadata-Version: 2.3\nName: Sample\nName: Other\nVersion: 1.0\n\n"
        elif what == "tag":
            wm = wm.replace(b"py3-none-any", b"py2-none-any")
        elif what == "major":
            wm = wm.replace(b"1.0", b"2.0")
        else:
            wm = wm.replace(b"true", b"false")
        path, entry = wheel(tmp_path, metadata=metadata, wheel_metadata=wm)
    with pytest.raises(inspector.Refused):
        inspect(inspector, path, entry)


def test_only_header_folding_is_normalized(inspector):
    assert inspector.unfold(" a>=1;\r\n python_version > '3' ") == "a>=1; python_version > '3'"
    assert inspector.unfold("x; marker == 'a  b'") == "x; marker == 'a  b'"
    with pytest.raises(inspector.Refused):
        inspector.unfold("x\ny")


@pytest.mark.parametrize(
    "what", ["prefix", "trailing", "local-name", "overlap", "crc", "zip64", "count", "method"]
)
def test_archive_structural_attacks_refuse(tmp_path, inspector, what):
    path, entry = wheel(tmp_path)
    raw = bytearray(path.read_bytes())
    eocd = raw.rfind(b"PK\x05\x06")
    cd = raw.find(b"PK\x01\x02")
    if what == "prefix":
        raw = bytearray(b"arbitrary-prefix") + raw
    elif what == "trailing":
        raw.extend(b"tail")
    elif what == "local-name":
        raw[30] ^= 1
    elif what == "overlap":
        second = raw.find(b"PK\x01\x02", cd + 4)
        struct.pack_into("<L", raw, second + 42, 0)
    elif what == "crc":
        struct.pack_into("<L", raw, 14, 1)
    elif what == "zip64":
        struct.pack_into("<H", raw, eocd + 10, 65535)
    elif what == "count":
        struct.pack_into("<H", raw, eocd + 10, 10001)
    else:
        struct.pack_into("<H", raw, cd + 10, 12)
    path.write_bytes(raw)
    rehash(path, entry)
    with pytest.raises((inspector.Refused, zipfile.BadZipFile)):
        inspect(inspector, path, entry)


def test_archive_hash_verified_before_zip(monkeypatch, tmp_path, inspector):
    path, entry = wheel(tmp_path)
    entry["sha256"] = "0" * 64
    monkeypatch.setattr(inspector.zipfile, "ZipFile", lambda *_a: pytest.fail("must not open ZIP"))
    with pytest.raises(inspector.Refused, match="ARCHIVE_HASH"):
        inspect(inspector, path, entry)


def test_member_budget_checked_before_decompression(monkeypatch, tmp_path, inspector):
    path, entry = wheel(tmp_path, extra={"large": b"x" * 10000})
    monkeypatch.setattr(inspector, "MAX_MEMBER", 1000)
    with pytest.raises(inspector.Refused, match="MEMBER_SIZE"):
        inspect(inspector, path, entry)


def test_stream_actual_expansion_cannot_exceed_declared_size(inspector):
    compressed = inspector.zlib.compress(b"x" * 100000)[2:-4]
    info = zipfile.ZipInfo("fake")
    info.compress_type = 8
    info.compress_size = len(compressed)
    info.file_size = 10
    with pytest.raises(inspector.Refused, match="EXPANSION"):
        list(inspector.stream_member(io.BytesIO(compressed), info, 0, time.monotonic() + 10))


def test_compressed_garbage_and_timeout_are_refused(tmp_path, inspector):
    path, entry = wheel(tmp_path)
    with pytest.raises(inspector.Refused, match="DEADLINE"):
        inspector.inspect_wheel(path, entry, time.monotonic() - 1)
    raw = inspector.zlib.compress(b"valid")[2:-4] + b"garbage"
    info = zipfile.ZipInfo("fake")
    info.compress_type, info.compress_size, info.file_size = 8, len(raw), 5
    with pytest.raises(inspector.Refused, match="DEFLATE_TAIL"):
        list(inspector.stream_member(io.BytesIO(raw), info, 0, time.monotonic() + 10))


def test_directory_entries_are_not_record_files(tmp_path, inspector):
    path, entry = wheel(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("empty/", b"")
    rehash(path, entry)
    assert any(v["directory"] for v in inspect(inspector, path, entry)["members"])


def test_data_descriptor_zip_is_measured(tmp_path, inspector):
    class NonSeek(io.BytesIO):
        def seek(self, *_args):
            raise io.UnsupportedOperation()

    path, entry = wheel(tmp_path)
    out = NonSeek()
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(out, "w", compression=8) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
    path.write_bytes(out.getvalue())
    rehash(path, entry)
    assert len(inspect(inspector, path, entry)["members"]) == 4


def test_empty_entrypoint_defaults_are_not_inherited(tmp_path, inspector):
    path, entry = wheel(
        tmp_path,
        extra={
            "sample-1.0.dist-info/entry_points.txt": (
                b"[DEFAULT]\nsecret = value\n[group]\nname = sample:entry\n"
            )
        },
    )
    with pytest.raises(inspector.Refused, match="ENTRYPOINT_DEFAULTS"):
        inspect(inspector, path, entry)


def test_report_is_json_data_only(tmp_path, inspector):
    path, entry = wheel(tmp_path)
    result = inspect(inspector, path, entry)
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize("output_limit", range(1, 8))
def test_pending_deflate_output_is_drained_with_bounded_blocks(
    monkeypatch, inspector, output_limit
):
    factory = inspector.zlib.decompressobj

    class SmallOutput:
        def __init__(self) -> None:
            self.decoder = factory(-15)

        def decompress(self, raw, limit):
            return self.decoder.decompress(raw, min(limit, output_limit))

        def __getattr__(self, key):
            return getattr(self.decoder, key)

    monkeypatch.setattr(inspector.zlib, "decompressobj", lambda *_a: SmallOutput())
    for payload in (b"x" * 4096, bytes(range(256)) * 40):
        compressed = inspector.zlib.compress(payload)[2:-4]
        info = zipfile.ZipInfo("fake")
        info.compress_type, info.compress_size, info.file_size = 8, len(compressed), len(payload)
        info.CRC = inspector.zlib.crc32(payload)
        blocks = list(
            inspector.stream_member(io.BytesIO(compressed), info, 0, time.monotonic() + 10)
        )
        assert b"".join(blocks) == payload
        assert max(map(len, blocks)) <= output_limit


def test_normalized_dist_info_and_inner_data_suffix_are_valid(tmp_path, inspector):
    path, entry = wheel(
        tmp_path, extra={"sample/cache.data": b"ordinary", "sample/name.dist-info": b"ordinary"}
    )
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(path, "w", compression=8) as archive:
        for name, raw in contents.items():
            content = (
                raw.replace(b"sample-1.0.dist-info/", b"Sample-1.0.dist-info/")
                if name.endswith("/RECORD")
                else raw
            )
            archive.writestr(
                name.replace("sample-1.0.dist-info/", "Sample-1.0.dist-info/"), content
            )
    rehash(path, entry)
    assert inspect(inspector, path, entry)["metadata"]["tags"] == ["py3-none-any"]


@pytest.mark.parametrize("disk", [0, 1])
def test_needed_version_45_without_zip64_and_member_disk(tmp_path, inspector, disk):
    path, entry = wheel(tmp_path)
    raw = bytearray(path.read_bytes())
    central = raw.find(b"PK\x01\x02")
    struct.pack_into("<H", raw, 4, 45)
    struct.pack_into("<H", raw, central + 6, 45)
    struct.pack_into("<H", raw, central + 34, disk)
    path.write_bytes(raw)
    rehash(path, entry)
    if disk:
        with pytest.raises(inspector.Refused, match="MULTIDISK_MEMBER"):
            inspect(inspector, path, entry)
    else:
        result = inspect(inspector, path, entry)
        assert result["members"][0]["local_header"]["needed_version"] == 45


def test_unexpected_parser_failure_preserves_refused_evidence(monkeypatch, tmp_path, inspector):
    parent = tmp_path / "Temp"
    parent.mkdir()
    output = parent / "maskgw-oracle9-inspect-fake"
    output.mkdir()
    root = tmp_path / "fake-wheelhouse"
    state = {
        "kind": "oracle9-wheel-inspection-v1",
        "invoked": False,
        "task": "test",
        "program_sha256": inspector.file_sha(Path(inspector.__file__)),
        "wheelhouse": str(root),
    }
    (output / "state.json").write_text(json.dumps(state), encoding="utf-8")
    inspector_os = types.SimpleNamespace(
        name="nt", environ={"LOCALAPPDATA": str(tmp_path)}, fsync=inspector.os.fsync
    )
    monkeypatch.setattr(inspector, "os", inspector_os)
    monkeypatch.setattr(
        inspector,
        "sys",
        types.SimpleNamespace(flags=types.SimpleNamespace(isolated=True, optimize=False)),
    )
    monkeypatch.setattr(inspector, "admission", lambda _root: ([{"filename": "fake.whl"}], {}, {}))

    def broken_parser(*_args):
        raise IndexError("public parser detail must not escape")

    monkeypatch.setattr(inspector, "inspect_wheel", broken_parser)
    assert inspector.main(root, output) == 1
    result = json.loads((output / "summary.json").read_bytes())
    assert result["category"] == "UNEXPECTED" and result["outcome"] == "WHEELS_INSPECTION_REFUSED"
    assert (output / "invoked.json").is_file()
    with pytest.raises(FileExistsError):
        inspector.main(root, output)


def test_each_member_records_its_own_permission_mode(tmp_path, inspector):
    path, entry = wheel(tmp_path)
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    expected = {}
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in contents.items():
            info = zipfile.ZipInfo(name)
            mode = 0o100755 if name == "sample/__init__.py" else 0o100644
            expected[name] = mode
            info.external_attr = mode << 16
            info.compress_type = 8
            archive.writestr(info, raw)
    rehash(path, entry)
    actual = {v["path"]: v["mode"] for v in inspect(inspector, path, entry)["members"]}
    assert actual == expected
