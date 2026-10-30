"""Public, one-shot Linux installer/probe. Not a gateway or product entrypoint."""

import base64
import contextlib
import csv
import ctypes
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import signal
import ssl
import stat
import subprocess
import sys
import time

PREFIX = Path("/opt/maskgw/venv")
SITE = PREFIX / "lib/python3.11/site-packages"
ATTEST = Path("/opt/maskgw/oracle9-installed.json")
TEMP_ROOT = Path("/tmp")
BASE_TOOLS = {"pip": "22.3.1", "setuptools": "65.5.1"}
SCRIPT_NAMES = {"cffi-gen-src", "fastapi", "httpx2", "idna", "jsonschema", "mcp", "pgpp", "uvicorn"}
CRYPTO = "psycopg_binary.libs/libcrypto-e7530dde.so.3"
CRYPTO_SHA = "3761d43a07bc3a119cfce159a0ae50b5fd526bd9db8bf9e87626487d12fc89cd"
PHASE = "admission"


def need(value, category):
    if not value:
        raise RuntimeError(category)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(65536):
            h.update(block)
    return h.hexdigest()


def key(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def read_regular(path, limit):
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and 0 <= s.st_size <= limit, "REGULAR_SIZE")
    raw = path.read_bytes()
    need(len(raw) == s.st_size, "READ_SIZE")
    return raw


def versions():
    rows = {}
    for dist in importlib.metadata.distributions(path=[str(SITE)]):
        name = key(dist.metadata["Name"])
        need(name not in rows, "DUPLICATE_DISTRIBUTION")
        rows[name] = dist.version
    return dict(sorted(rows.items()))


def scan_prefix():
    """No link traversal; baseline symlinks are retained and compared exactly."""
    prefix = PREFIX.lstat()
    need(
        stat.S_ISDIR(prefix.st_mode)
        and prefix.st_uid == prefix.st_gid == 0
        and not prefix.st_mode & 0o6022,
        "PREFIX_ROOT",
    )
    rows, pending, total = {}, [PREFIX], 0
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            s = path.lstat()
            relative = path.relative_to(PREFIX).as_posix()
            need(s.st_uid == s.st_gid == 0, "PREFIX_OWNER")
            row = {"mode": stat.S_IMODE(s.st_mode), "uid": s.st_uid, "gid": s.st_gid}
            if stat.S_ISLNK(s.st_mode):
                target = os.readlink(path)
                need(len(target) <= 512, "PREFIX_LINK")
                row.update(kind="link", target=target)
            else:
                need(not s.st_mode & 0o6022, "PREFIX_MODE")
                if stat.S_ISDIR(s.st_mode):
                    row.update(kind="directory")
                    pending.append(path)
                else:
                    need(
                        stat.S_ISREG(s.st_mode) and s.st_size <= 64 * 1024 * 1024,
                        "PREFIX_SPECIAL_OR_SIZE",
                    )
                    total += s.st_size
                    need(total <= 256 * 1024 * 1024, "PREFIX_TOTAL")
                    row.update(kind="file", bytes=s.st_size, sha256=file_sha(path))
            rows[relative] = row
            need(len(rows) <= 10000, "PREFIX_COUNT")
    return rows


def runtime_profile(probe):
    import resource

    need(
        sys.platform == "linux"
        and sys.version_info[:3] == (3, 11, 13)
        and Path(sys.prefix) == PREFIX
        and sys.flags.isolated
        and sys.flags.dont_write_bytecode,
        "RUNTIME",
    )
    expected_uid = 10001 if probe else 0
    need(
        os.getuid() == os.getgid() == expected_uid and set(os.getgroups()) <= {expected_uid},
        "RUNTIME_USER",
    )
    limits = {
        "core": resource.getrlimit(resource.RLIMIT_CORE),
        "nofile": resource.getrlimit(resource.RLIMIT_NOFILE),
    }
    need(limits == {"core": (0, 0), "nofile": (128, 128)}, "RLIMIT")
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    need(
        int(status["CapEff"].strip(), 16) == 0 and status["NoNewPrivs"].strip() == "1", "PRIVILEGE"
    )
    need(
        all(int(status[v].strip(), 16) == 0 for v in ("CapBnd", "CapPrm", "CapInh", "CapAmb"))
        and status["Seccomp"].strip() == "2",
        "PRIVILEGE_BOUND",
    )
    group = Path("/sys/fs/cgroup")
    memory = {
        name: (group / name).read_text().strip()
        for name in ("memory.max", "memory.swap.max", "pids.max", "cpu.max")
    }
    need(
        memory["memory.max"] == "536870912"
        and memory["memory.swap.max"] == "0"
        and memory["pids.max"] == "32",
        "CGROUP",
    )
    quota, period = memory["cpu.max"].split()
    need(quota != "max" and int(quota) == int(period) > 0, "CPU")
    need({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "NETWORK")
    roots = [line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines()]
    root = [v for v in roots if v[4] == "/"]
    need(len(root) == 1 and (("ro" in root[0][5].split(",")) == probe), "ROOT_MODE")
    temporary = [v for v in roots if v[4] == "/tmp"]
    need(
        len(temporary) == 1 and {"noexec", "nodev", "nosuid"} <= set(temporary[0][5].split(",")),
        "TMP_MODE",
    )
    tmp = Path("/tmp").stat()
    need(
        tmp.st_uid == tmp.st_gid == (10001 if probe else 0) and stat.S_IMODE(tmp.st_mode) == 0o700,
        "TMP_OWNER",
    )
    tmpfs = os.statvfs("/tmp")
    shm = os.statvfs("/dev/shm")
    need(
        tmpfs.f_blocks * tmpfs.f_frsize == (16 if probe else 64) * 1024 * 1024
        and shm.f_blocks * shm.f_frsize == 8 * 1024 * 1024,
        "TMP_SIZE",
    )
    return {
        "uid": os.getuid(),
        "gid": os.getgid(),
        "limits": limits,
        "cgroup": memory,
        "kernel": os.uname().release,
        "root_read_only": probe,
        "network_interfaces": ["lo"],
    }


def load_inputs(root, expected_hash):
    need(
        root.parent == Path("/opt/maskgw")
        and re.fullmatch(r"install-inputs-[0-9a-f]{32}", root.name),
        "INPUT_PREFIX",
    )
    for path in (root, root / "wheels"):
        need(stat.S_ISDIR(path.lstat().st_mode), "INPUT_DIRECTORY")
    raw = read_regular(root / "manifest.json", 2 * 1024 * 1024)
    need(sha(raw) == expected_hash, "MANIFEST_HASH")
    manifest = json.loads(raw)
    need(
        manifest["kind"] == "oracle9-offline-context-v1"
        and len(manifest["wheels"]) == 37
        and manifest["base_tools"] == BASE_TOOLS
        and len(manifest["installed_files"]) == 1382
        and set(manifest["console_scripts"]) == SCRIPT_NAMES,
        "MANIFEST",
    )
    need(
        {p.name for p in root.iterdir()} == {"manifest.json", "requirements.lock", "wheels"},
        "INPUT_EXTRA",
    )
    need(
        {p.name for p in (root / "wheels").iterdir()}
        == {v["filename"] for v in manifest["wheels"]},
        "WHEELS_EXTRA",
    )
    lock = read_regular(root / "requirements.lock", 65536)
    expected = (
        "# Closed candidate Linux CPython3.11 set, no dev extras.\n"
        + "".join(
            v["name"] + "==" + v["version"] + " --hash=sha256:" + v["sha256"] + "\n"
            for v in manifest["wheels"]
        )
    ).encode()
    need(lock == expected and sha(lock) == manifest["lock_sha256"], "LOCK")
    modes, total = {}, 0
    files = [root / "manifest.json", root / "requirements.lock"]
    for wheel in manifest["wheels"]:
        filename = wheel["filename"]
        need(re.fullmatch(r"[A-Za-z0-9_.+!-]+\.whl", filename), "FILENAME")
        path = root / "wheels" / filename
        data = read_regular(path, 32 * 1024 * 1024)
        need(len(data) == wheel["bytes"] and sha(data) == wheel["sha256"], "WHEEL_HASH")
        total += len(data)
        files.append(path)
    need(total == manifest["wheel_bytes"] == 22643029, "WHEEL_TOTAL")
    for path in [root, root / "wheels", *files]:
        s = path.lstat()
        need(s.st_uid == s.st_gid == 0 and not stat.S_ISLNK(s.st_mode), "INPUT_OWNER")
        modes[path.relative_to(root).as_posix()] = stat.S_IMODE(s.st_mode)
        os.chmod(path, 0o755 if stat.S_ISDIR(s.st_mode) else 0o644)
    return manifest, modes


def child_environment():
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(TEMP_ROOT / "maskgw-home"),
        "TMPDIR": str(TEMP_ROOT),
        "LANG": "C.UTF-8",
        "PIP_CONFIG_FILE": "/dev/null",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }


def log_summary(raw):
    prefix = raw[: 256 * 1024]
    return {
        "bytes": len(raw),
        "sha256": sha(raw),
        "prefix_bytes": len(prefix),
        "prefix_base64": base64.b64encode(prefix).decode(),
        "truncated": len(prefix) < len(raw),
    }


def emit(result):
    raw = (json.dumps(result, sort_keys=True) + "\n").encode("ascii")
    need(len(raw) <= 1536 * 1024, "RESULT_OUTPUT_LIMIT")
    sys.stdout.write(raw.decode("ascii"))


def parent_environment():
    home = TEMP_ROOT / "maskgw-home"
    home.mkdir(mode=0o700)
    os.environ.clear()
    os.environ.update({k: v for k, v in child_environment().items() if not k.startswith("PIP_")})


def run_pip(arguments, label):
    need(
        not any(
            Path(v).exists()
            for v in ("/etc/pip.conf", "/etc/xdg/pip/pip.conf", str(PREFIX / "pip.conf"))
        ),
        "PIP_CONFIG",
    )
    log = TEMP_ROOT / (label + ".log")
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        *arguments,
    ]
    with log.open("xb") as output:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=child_environment(),
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 120
            while process.poll() is None:
                need(time.monotonic() < deadline, "PIP_TIMEOUT")
                need(log.stat().st_size <= 1024 * 1024, "PIP_OUTPUT")
                time.sleep(0.025)
            code = process.wait()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    raw = read_regular(log, 1024 * 1024)
    need(code == 0, "PIP_NONZERO")
    return {"exit": code, **log_summary(raw)}


def record_target(value):
    need(
        type(value) is str
        and 0 < len(value.encode()) <= 1024
        and not any(ord(c) < 32 or c in "\\:" for c in value)
        and not value.startswith("/"),
        "RECORD_PATH",
    )
    target = Path(os.path.normpath(str(SITE / value)))
    need(target.is_relative_to(PREFIX), "RECORD_ESCAPE")
    return target.relative_to(PREFIX).as_posix()


def verify_record(path, allowed):
    rows = list(
        csv.reader(
            io.StringIO(read_regular(path, 2 * 1024 * 1024).decode(), newline=""), strict=True
        )
    )
    seen = set()
    own = path.relative_to(PREFIX).as_posix()
    for row in rows:
        need(len(row) == 3, "RECORD_COLUMNS")
        name, encoded, size = row
        relative = record_target(name)
        need(relative in allowed and relative not in seen, "RECORD_MEMBER")
        seen.add(relative)
        target = PREFIX / relative
        if relative == own:
            need(encoded == size == "", "RECORD_SELF")
            continue
        need(re.fullmatch(r"0|[1-9][0-9]{0,9}", size), "RECORD_SIZE")
        need(target.lstat().st_size == int(size), "RECORD_SIZE")
        algorithm, sep, digest = encoded.partition("=")
        need(sep and algorithm in ("sha256", "sha384", "sha512"), "RECORD_ALGORITHM")
        raw = read_regular(target, 64 * 1024 * 1024)
        actual = (
            base64.urlsafe_b64encode(hashlib.new(algorithm, raw).digest()).rstrip(b"=").decode()
        )
        need(actual == digest, "RECORD_HASH")
    need(seen == allowed, "RECORD_COVERAGE")


def verify_install(manifest, before, after):
    expected_versions = {v["name"]: v["version"] for v in manifest["wheels"]} | BASE_TOOLS
    need(
        len(expected_versions) == 39 and versions() == dict(sorted(expected_versions.items())),
        "INSTALLED_SET",
    )
    site_relative = SITE.relative_to(PREFIX)
    per_owner, expected_files = {}, {}
    dist_roots = {}
    for path, item in manifest["installed_files"].items():
        need(
            not path.startswith("/") and all(v not in ("", ".", "..") for v in path.split("/")),
            "SOURCE_PATH",
        )
        relative = (site_relative / path).as_posix()
        need(not path.endswith(".pyc") and relative not in before, "FILE_COLLISION")
        expected_files[relative] = item
        per_owner.setdefault(item["owner"], set()).add(relative)
        if item["rewritten_record"]:
            need(
                path.endswith(".dist-info/RECORD") and item["owner"] not in dist_roots, "DIST_INFO"
            )
            dist_roots[item["owner"]] = path.rsplit("/", 1)[0]
    need(set(dist_roots) == {v["name"] for v in manifest["wheels"]}, "DIST_INFO_SET")
    for owner, folder in dist_roots.items():
        for basename, content in (("INSTALLER", b"pip\n"), ("REQUESTED", b"")):
            relative = (site_relative / folder / basename).as_posix()
            need(relative not in expected_files and relative not in before, "GENERATED_COLLISION")
            need(read_regular(PREFIX / relative, 16) == content, "GENERATED_CONTENT")
            expected_files[relative] = None
            per_owner[owner].add(relative)
    for name, script in manifest["console_scripts"].items():
        need(name in SCRIPT_NAMES, "SCRIPT_NAME")
        relative = "bin/" + name
        need(relative not in before, "BASE_SCRIPT_COLLISION")
        raw = read_regular(PREFIX / relative, 16384)
        need(raw.splitlines()[0] == ("#!" + sys.executable).encode(), "SCRIPT_SHEBANG")
        expected_files[relative] = None
        per_owner[script["owner"]].add(relative)
    for relative, item in expected_files.items():
        row = after[relative]
        need(row["kind"] == "file", "INSTALLED_FILE_TYPE")
        if item is not None and not item["rewritten_record"]:
            need(
                row["bytes"] == item["bytes"] and row["sha256"] == item["sha256"], "INSTALLED_BYTES"
            )
    for relative, row in before.items():
        need(after.get(relative) == row, "BASE_CHANGED")
    allowed = set(before) | set(expected_files)
    for relative in expected_files:
        parent = Path(relative).parent
        while parent != Path("."):
            allowed.add(parent.as_posix())
            parent = parent.parent
    need(set(after) == allowed, "PREFIX_EXTRA_OR_MISSING")
    for owner, folder in dist_roots.items():
        verify_record(SITE / folder / "RECORD", per_owner[owner])
    return expected_versions


def imports_and_native():
    # Python-level connection/bind calls are forbidden during this import probe.
    import socket
    from unittest.mock import patch

    def reject(*_args, **_kwargs):
        raise RuntimeError("IMPORT_NETWORK_REQUEST")

    with contextlib.ExitStack() as stack:
        for name in ("connect", "connect_ex", "bind", "listen"):
            stack.enter_context(patch.object(socket.socket, name, reject))
        stack.enter_context(patch.object(socket, "create_connection", reject))
        modules = [
            "maskgw",
            "maskgw.bootstrap.application",
            "maskgw.mcp.server",
            "maskgw.admin.http.app",
            "maskgw.pgwire.listener",
            "maskgw.masking",
            "maskgw.runtime.worker_job",
        ]
        for name in modules:
            importlib.import_module(name)
        from maskgw.admin.ui.resources import load_resources
        from importlib.resources import files
        from cryptography.hazmat.backends.openssl.backend import backend
        import psycopg

        resources = load_resources()
        need(
            set(resources) == {"index.html", "ui.js", "ui.css", "presentation.json"}, "UI_RESOURCES"
        )
        assets = files("maskgw.admin.ui").joinpath("assets")
        need({v.name for v in assets.iterdir()} == set(resources) | {"manifest.json"}, "UI_ASSETS")
        hashes = {v.name: sha(v.read_bytes()) for v in assets.iterdir()}
        need(psycopg.pq.__impl__ == "binary", "PSYCOPG_IMPL")
        crypto = SITE / CRYPTO
        need(file_sha(crypto) == CRYPTO_SHA, "PSYCOPG_CRYPTO_HASH")
        handle = ctypes.CDLL(str(crypto), mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)
        handle.OpenSSL_version.argtypes = [ctypes.c_int]
        handle.OpenSSL_version.restype = ctypes.c_char_p
        version = handle.OpenSSL_version(0)
        need(version is not None and len(version) <= 256, "PSYCOPG_CRYPTO_VERSION")
        result = {
            "modules": modules,
            "ui_assets_sha256": hashes,
            "system_openssl": ssl.OPENSSL_VERSION,
            "cryptography_openssl": backend.openssl_version_text(),
            "libpq_version": psycopg.pq.version(),
            "psycopg_impl": psycopg.pq.__impl__,
            "psycopg_libcrypto": CRYPTO,
            "psycopg_libcrypto_sha256": CRYPTO_SHA,
            "psycopg_openssl": version.decode("ascii"),
        }
    return result


def base_pth():
    path = SITE / "distutils-precedence.pth"
    raw = read_regular(path, 16384)
    return {
        "bytes": len(raw),
        "sha256": sha(raw),
        "utf8": raw.decode("utf-8"),
        "executes_at_site_startup": True,
    }


def write_new(path, raw):
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def install(root, manifest_sha):
    global PHASE
    profile = runtime_profile(False)
    need(os.getpid() == 1 and not ATTEST.exists(), "INSTALL_PID_OR_EXISTING")
    os.umask(0o022)
    manifest, input_modes = load_inputs(root, manifest_sha)
    parent_environment()
    PHASE = "base"
    need(versions() == BASE_TOOLS, "BASE_TOOLS")
    before, pth = scan_prefix(), base_pth()
    need(
        before.get("lib64", {}).get("kind") == "link" and before["lib64"]["target"] == "lib",
        "BASE_LIB64_LINK",
    )
    need(all("bin/" + name not in before for name in SCRIPT_NAMES), "BASE_SCRIPT_COLLISION")
    PHASE = "pip-install"
    installed = run_pip(
        [
            "install",
            "--no-input",
            "--no-index",
            "--no-deps",
            "--require-hashes",
            "--only-binary=:all:",
            "--no-compile",
            "--no-cache-dir",
            "--find-links",
            str(root / "wheels"),
            "-r",
            str(root / "requirements.lock"),
        ],
        "pip-install",
    )
    PHASE = "pip-check"
    checked = run_pip(["check"], "pip-check")
    PHASE = "verify-install"
    after = scan_prefix()
    installed_versions = verify_install(manifest, before, after)
    need(base_pth() == pth, "BASE_PTH_CHANGED")
    PHASE = "imports"
    native = imports_and_native()
    need(scan_prefix() == after, "IMPORT_PREFIX_WRITE")
    attestation = {
        "kind": "oracle9-installed-v1",
        "manifest_sha256": manifest_sha,
        "manifest": manifest,
        "base_snapshot": before,
        "installed_snapshot": after,
        "base_pth": pth,
        "versions": installed_versions,
        "native": native,
    }
    raw = (json.dumps(attestation, sort_keys=True) + "\n").encode()
    need(len(raw) <= 4 * 1024 * 1024, "ATTEST_SIZE")
    write_new(ATTEST, raw)
    PHASE = "cleanup-inputs"
    # Only this exact public, already hash-checked input set. No recursive removal.
    load_inputs(root, manifest_sha)
    for wheel in manifest["wheels"]:
        (root / "wheels" / wheel["filename"]).unlink()
    (root / "wheels").rmdir()
    (root / "requirements.lock").unlink()
    (root / "manifest.json").unlink()
    root.rmdir()
    return {
        "outcome": "CANDIDATE_INSTALL_VERIFIED",
        "profile": profile,
        "versions": installed_versions,
        "native": native,
        "attestation_sha256": sha(raw),
        "attestation_bytes": len(raw),
        "prefix_paths": len(after),
        "pip_install": installed,
        "pip_check": checked,
        "input_modes_before": input_modes,
        "managed_inputs_removed": not root.exists(),
    }


def probe(expected_sha):
    global PHASE
    profile = runtime_profile(True)
    parent_environment()
    PHASE = "probe-attestation"
    raw = read_regular(ATTEST, 4 * 1024 * 1024)
    need(sha(raw) == expected_sha, "ATTEST_HASH")
    report = json.loads(raw)
    need(report["kind"] == "oracle9-installed-v1", "ATTEST_KIND")
    current = scan_prefix()
    need(current == report["installed_snapshot"], "PROBE_PREFIX_CHANGED")
    installed_versions = verify_install(report["manifest"], report["base_snapshot"], current)
    need(base_pth() == report["base_pth"], "PROBE_PTH_CHANGED")
    checked = run_pip(["check"], "probe-pip-check")
    PHASE = "probe-imports"
    native = imports_and_native()
    need(native == report["native"] and scan_prefix() == current, "PROBE_NATIVE_OR_FILES")
    return {
        "outcome": "CANDIDATE_PROBE_VERIFIED",
        "profile": profile,
        "versions": installed_versions,
        "native": native,
        "attestation_sha256": expected_sha,
        "prefix_paths": len(current),
        "pip_check": checked,
    }


def failure_logs():
    logs = {}
    for label in ("pip-install", "pip-check", "probe-pip-check"):
        path = TEMP_ROOT / (label + ".log")
        try:
            if path.exists():
                raw = read_regular(path, 1024 * 1024)
                logs[label] = log_summary(raw)
        except Exception:
            logs[label] = {"diagnostic": "LOG_UNAVAILABLE_OR_OVER_LIMIT"}
    return logs


if __name__ == "__main__":
    try:
        need(
            os.name == "posix"
            and (
                len(sys.argv) == 4
                and sys.argv[1] == "install"
                or len(sys.argv) == 3
                and sys.argv[1] == "probe"
            ),
            "ARGUMENTS",
        )
        result = (
            install(Path(sys.argv[2]), sys.argv[3])
            if sys.argv[1] == "install" and len(sys.argv) == 4
            else probe(sys.argv[2])
        )
        emit(result)
    except Exception as exc:
        emit(
            {
                "outcome": "CANDIDATE_NATIVE_REFUSED",
                "phase": PHASE,
                "category": type(exc).__name__,
                "logs": failure_logs(),
            }
        )
        raise SystemExit(1) from None
