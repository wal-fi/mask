"""Public native-Linux dependency resolution; no calls on import, no application."""

import base64
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import urllib.parse
import zlib

MAX_RAW = 16 * 1024 * 1024
MAX_ENVELOPE = 2 * 1024 * 1024
CERT = "/etc/pki/tls/certs/ca-bundle.crt"
CONFIGS = ("/etc/pip.conf", "/etc/xdg/pip/pip.conf", "/opt/maskgw/venv/pip.conf")
INDEX = "https://pypi.org/simple"


def require(value):
    if not value:
        raise RuntimeError("DEPENDENCY_RESOLUTION_REFUSED")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def name_key(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value))
    return re.sub(r"[-_.]+", "-", value).lower()


def validate_inputs(value):
    require(
        type(value) is dict
        and set(value) == {"requirements", "constraints", "project_sha256", "seed_sha256"}
    )
    require(type(value["constraints"]) is str and len(value["constraints"].encode()) <= 8192)
    require(sha(value["constraints"].encode()) == value["seed_sha256"])
    require(re.fullmatch("[0-9a-f]{64}", value["project_sha256"]) is not None)
    pins = {}
    for line in value["constraints"].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.!+_]+)", line)
        require(m is not None)
        key = name_key(m[1])
        require(key not in pins)
        pins[key] = m[2]
    require(1 <= len(pins) <= 32)
    roots = []
    reqs = value["requirements"]
    require(type(reqs) is list and 1 <= len(reqs) <= 32)
    for req in reqs:
        require(type(req) is str and len(req) <= 256 and req.isascii())
        require(not any(c in req for c in ("\r", "\n", "\x00", "@", ":", "/", "\\")))
        m = re.match(r"([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[A-Za-z0-9_,.-]+\])?(?=[<>=!~;]|$)", req)
        require(m is not None)
        key = name_key(m[1])
        require(key in pins and key not in roots)
        roots.append(key)
    return pins, roots


def wheel_filename(filename, package, version, glibc):
    require(type(filename) is str and len(filename) <= 256)
    require(re.fullmatch(r"[A-Za-z0-9_.+!-]+\.whl", filename) is not None)
    parts = filename[:-4].split("-")
    require(len(parts) in (5, 6))
    require(name_key(parts[0]) == package and parts[1] == version)
    if len(parts) == 6:
        require(re.fullmatch(r"[0-9][A-Za-z0-9_.]*", parts[2]) is not None)
    py, abi, platform = parts[-3:]
    if platform == "any":
        require(py in ("py3", "py2.py3") and abi == "none")
        return
    require(
        py == "cp311"
        and abi == "cp311"
        or abi == "abi3"
        and re.fullmatch(r"cp3(?:[2-9]|10|11)", py)
    )
    aliases = {
        "manylinux1_x86_64": (2, 5),
        "manylinux2010_x86_64": (2, 12),
        "manylinux2014_x86_64": (2, 17),
    }
    for tag in platform.split("."):
        minimum = aliases.get(tag)
        if minimum is None:
            m = re.fullmatch(r"manylinux_(2)_([0-9]{1,2})_x86_64", tag)
            require(m is not None)
            minimum = (int(m[1]), int(m[2]))
        require(minimum <= glibc)


def project_report(report, inputs, glibc):
    pins, roots = validate_inputs(inputs)
    require(
        type(report) is dict and set(report) == {"version", "pip_version", "install", "environment"}
    )
    require(report["version"] == "0" and report["pip_version"] == "22.3.1")
    require(
        type(glibc) is tuple and len(glibc) == 2 and all(type(v) is int and v >= 0 for v in glibc)
    )
    environment = report["environment"]
    expected = {
        "sys_platform": "linux",
        "platform_machine": "x86_64",
        "python_full_version": "3.11.13",
        "implementation_name": "cpython",
        "platform_system": "Linux",
    }
    require(type(environment) is dict and all(environment.get(k) == v for k, v in expected.items()))
    require(
        all(type(k) is str and type(v) is str and len(v) <= 512 for k, v in environment.items())
    )
    rows = report["install"]
    require(type(rows) is list and 1 <= len(rows) <= 64)
    files, seen, seen_files = [], set(), set()
    for item in rows:
        require(
            type(item) is dict
            and set(item)
            in (
                {"is_direct", "requested", "download_info", "metadata"},
                {"is_direct", "requested", "download_info", "metadata", "requested_extras"},
            )
        )
        require(item["is_direct"] is False and type(item["requested"]) is bool)
        metadata = item["metadata"]
        key, version = name_key(metadata["name"]), metadata["version"]
        require(type(version) is str and re.fullmatch(r"[A-Za-z0-9.!+_]+", version) is not None)
        require(key not in seen and key not in {"pywin32", "pypiwin32", "pywin32-ctypes"})
        require(key not in pins or pins[key] == version)
        seen.add(key)
        require(item["requested"] == (key in roots))
        extras = item.get("requested_extras", [])
        require(type(extras) is list and len(extras) <= 8 and all(name_key(v) == v for v in extras))
        require(extras == sorted(set(extras)))
        download = item["download_info"]
        require(type(download) is dict and set(download) == {"url", "archive_info"})
        url = download["url"]
        require(type(url) is str and url.isascii() and len(url) <= 2048)
        parsed = urllib.parse.urlsplit(url)
        require(parsed.scheme == "https" and parsed.netloc == "files.pythonhosted.org")
        require(url == urllib.parse.urlunsplit(parsed))
        require(not parsed.query and not parsed.fragment and parsed.path.startswith("/packages/"))
        require(re.fullmatch(r"/packages/[A-Za-z0-9/._+!-]+", parsed.path) is not None)
        require(all(part not in ("", ".", "..") for part in parsed.path.split("/")[1:]))
        filename = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1], errors="strict")
        wheel_filename(filename, key, version, glibc)
        require(filename not in seen_files)
        seen_files.add(filename)
        archive = download["archive_info"]
        require(type(archive) is dict and set(archive) == {"hash"})
        require(
            type(archive["hash"]) is str and re.fullmatch("sha256=[0-9a-f]{64}", archive["hash"])
        )
        requires_python = metadata.get("requires_python")
        require(
            requires_python is None or type(requires_python) is str and len(requires_python) <= 256
        )
        requires_dist = metadata.get("requires_dist", [])
        require(type(requires_dist) is list and len(requires_dist) <= 128)
        require(
            all(
                type(v) is str and len(v) <= 1024 and "\x00" not in v and "\n" not in v
                for v in requires_dist
            )
        )
        files.append(
            {
                "name": key,
                "version": version,
                "url": url,
                "filename": filename,
                "sha256": archive["hash"][7:],
                "requires_python": requires_python,
                "requires_dist": requires_dist,
                "requested": item["requested"],
                "requested_extras": extras,
            }
        )
    require(set(pins) <= seen and set(roots) <= seen)
    return {
        "schema": "oracle9-pip22-projection-v1",
        "pip_version": "22.3.1",
        "report_version": "0",
        "environment": environment,
        "glibc": list(glibc),
        "index_url": INDEX,
        "files": sorted(files, key=lambda v: v["name"]),
    }


def pack_report(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RAW)
    packed = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    require(len(packed) <= MAX_ENVELOPE)
    return {"encoding": "zlib-base64-v1", "raw_bytes": len(raw), "sha256": sha(raw), "data": packed}


def unpack_report(value):
    require(type(value) is dict and set(value) == {"encoding", "raw_bytes", "sha256", "data"})
    require(
        value["encoding"] == "zlib-base64-v1"
        and type(value["raw_bytes"]) is int
        and 0 < value["raw_bytes"] <= MAX_RAW
    )
    require(type(value["data"]) is str and len(value["data"]) <= MAX_ENVELOPE)
    packed = base64.b64decode(value["data"], validate=True)
    stream = zlib.decompressobj()
    raw = stream.decompress(packed, MAX_RAW + 1)
    require(stream.eof and not stream.unused_data and not stream.unconsumed_tail)
    require(len(raw) == value["raw_bytes"] and sha(raw) == value["sha256"])
    return raw


def child_environment():
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/var/empty",
        "LANG": "C.UTF-8",
        "TMPDIR": "/tmp/maskgw-resolve",
    }


def validate_packet(value, inputs):
    require(
        type(value) is dict
        and set(value)
        == {
            "kind",
            "projection",
            "raw",
            "diagnostic",
            "config_absent",
            "child_environment",
            "cert",
            "inputs",
        }
    )
    require(value["kind"] == "oracle9-pip-resolution-v1" and value["inputs"] == inputs)
    require(
        value["config_absent"] == list(CONFIGS)
        and value["child_environment"] == child_environment()
    )
    require(value["projection"]["glibc"] == [2, 34])
    raw = unpack_report(value["raw"])
    require(value["projection"] == project_report(json.loads(raw), inputs, (2, 34)))
    cert = value["cert"]
    require(set(cert) == {"path", "resolved_path", "uid", "gid", "mode", "bytes", "sha256"})
    require(cert["path"] == CERT and cert["resolved_path"].startswith("/etc/pki/"))
    require(".." not in cert["resolved_path"].split("/") and "\x00" not in cert["resolved_path"])
    require(
        type(cert["uid"]) is int and type(cert["gid"]) is int and cert["uid"] == cert["gid"] == 0
    )
    require(type(cert["mode"]) is int and 0 <= cert["mode"] <= 0o7777 and not cert["mode"] & 0o6022)
    require(type(cert["bytes"]) is int and 0 < cert["bytes"] <= 4 * 1024 * 1024)
    require(re.fullmatch("[0-9a-f]{64}", cert["sha256"]) is not None)
    diagnostic = value["diagnostic"]
    require(
        set(diagnostic)
        == {
            "exit",
            "stdout_bytes",
            "stdout_sha256",
            "stdout_utf8",
            "stderr_bytes",
            "stderr_sha256",
            "stderr_utf8",
        }
    )
    require(type(diagnostic["exit"]) is int and diagnostic["exit"] == 0)
    for label, limit in (("stdout", 65536), ("stderr", 16384)):
        data = diagnostic[label + "_utf8"].encode("utf8")
        require(type(diagnostic[label + "_bytes"]) is int and len(data) <= limit)
        require(
            len(data) == diagnostic[label + "_bytes"] and sha(data) == diagnostic[label + "_sha256"]
        )
    return raw


def pip_args(requirements):
    return [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "pip",
        "--isolated",
        "--no-input",
        "--no-cache-dir",
        "--disable-pip-version-check",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--quiet",
        "--report",
        "/tmp/maskgw-resolve/report.json",
        "--only-binary=:all:",
        "--index-url",
        INDEX,
        "--cert",
        CERT,
        "--retries",
        "0",
        "--timeout",
        "15",
        "--constraint",
        "/tmp/maskgw-resolve/constraints.txt",
        *requirements,
    ]


def failure_log(path, limit):
    count, digest, prefix = 0, hashlib.sha256(), bytearray()
    with path.open("rb") as f:
        while block := f.read(8192):
            count += len(block)
            digest.update(block)
            if len(prefix) < limit:
                prefix.extend(block[: limit - len(prefix)])
    require(count == path.stat().st_size)
    return {
        "bytes": count,
        "sha256": digest.hexdigest(),
        "prefix_bytes": len(prefix),
        "prefix_utf8": prefix.decode("utf8", errors="replace"),
    }


def native(inputs):
    validate_inputs(inputs)
    require(os.getuid() == os.getgid() == 10001 and sys.version_info[:3] == (3, 11, 13))
    require(
        sys.prefix == "/opt/maskgw/venv" and sys.flags.isolated and sys.flags.dont_write_bytecode
    )
    os.environ.clear()
    os.environ.update(child_environment())
    require(all(not pathlib.Path(v).exists() and not pathlib.Path(v).is_symlink() for v in CONFIGS))
    m = re.fullmatch(r"glibc ([0-9]+)\.([0-9]+)", os.confstr("CS_GNU_LIBC_VERSION"))
    require(m is not None)
    glibc = (int(m[1]), int(m[2]))
    require(glibc == (2, 34))
    cert = pathlib.Path(CERT).resolve(strict=True)
    s = cert.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == s.st_gid == 0 and not s.st_mode & 0o6022)
    require(0 < s.st_size <= 4 * 1024 * 1024)
    cert_proof = {
        "path": CERT,
        "resolved_path": str(cert),
        "uid": s.st_uid,
        "gid": s.st_gid,
        "mode": stat.S_IMODE(s.st_mode),
        "bytes": s.st_size,
        "sha256": sha(cert.read_bytes()),
    }
    tmp = pathlib.Path("/tmp/maskgw-resolve")
    tmp.mkdir(mode=0o700)
    (tmp / "constraints.txt").write_text(inputs["constraints"], encoding="utf8")
    with (tmp / "stdout").open("xb") as out, (tmp / "stderr").open("xb") as err:
        p = subprocess.run(
            pip_args(inputs["requirements"]),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            timeout=150,
            check=False,
            env=child_environment(),
        )
    if p.returncode != 0:
        print(
            json.dumps(
                {
                    "kind": "oracle9-pip-refused-v1",
                    "exit": p.returncode,
                    "stdout": failure_log(tmp / "stdout", 16384),
                    "stderr": failure_log(tmp / "stderr", 16384),
                }
            )
        )
        raise SystemExit(2)
    require((tmp / "stdout").stat().st_size <= 65536 and (tmp / "stderr").stat().st_size <= 16384)
    stdout, stderr = (tmp / "stdout").read_bytes(), (tmp / "stderr").read_bytes()
    diagnostic = {
        "exit": p.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256": sha(stdout),
        "stdout_utf8": stdout.decode("utf8", errors="strict"),
        "stderr_bytes": len(stderr),
        "stderr_sha256": sha(stderr),
        "stderr_utf8": stderr.decode("utf8", errors="strict"),
    }
    require((tmp / "report.json").stat().st_size <= MAX_RAW)
    raw = (tmp / "report.json").read_bytes()
    report = json.loads(raw)
    result = {
        "kind": "oracle9-pip-resolution-v1",
        "projection": project_report(report, inputs, glibc),
        "raw": pack_report(raw),
        "diagnostic": diagnostic,
        "config_absent": list(CONFIGS),
        "child_environment": child_environment(),
        "cert": cert_proof,
        "inputs": inputs,
    }
    validate_packet(result, inputs)
    encoded = json.dumps(result, sort_keys=True).encode()
    require(len(encoded) + 1 <= MAX_ENVELOPE)
    sys.stdout.buffer.write(encoded + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    require(len(sys.argv) == 2 and len(sys.argv[1]) <= 16384)
    native(json.loads(base64.b64decode(sys.argv[1], validate=True)))
