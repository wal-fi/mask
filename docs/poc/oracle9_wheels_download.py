"""Closed public-wheel downloads only; no ZIP interpretation or installation."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
CURL = Path("C:/Windows/System32/curl.exe")
CURL_SHA = "73d24149ff289afc49ec41f08918ef9faa727d39ad993e929757dc2ddafab805"
POLICY = REPO / "deploy/oracle9_dependencies.py"
POLICY_SHA = "011ba3744ab393b1887fcd3290e66d3a507eb9297f1929e39f2e5a03269f2c3a"
EVIDENCE = REPO / "docs/poc/evidence/oracle9-dependencies-attempt2-20261025.json"
EVIDENCE_SHA = "8b737f8fe07f6ec42d8984fec013bf43bdf483e3629a04cf3390b3b9f4807113"
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


def require(value):
    if not value:
        raise RuntimeError("WHEELHOUSE_DOWNLOAD_REFUSED")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(65536):
            h.update(block)
    return h.hexdigest()


def regular(path):
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400)


def write_new(path, raw):
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def save(path, value):
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    require(len(raw) <= 1024 * 1024)
    candidate = path.with_suffix(path.suffix + ".next")
    write_new(candidate, raw)
    os.replace(candidate, path)


def selected_files():
    regular(POLICY)
    regular(EVIDENCE)
    require(POLICY.stat().st_size <= 65536 and EVIDENCE.stat().st_size <= 1024 * 1024)
    source, evidence = POLICY.read_bytes(), EVIDENCE.read_bytes()
    require(
        hashlib.sha256(source).hexdigest() == POLICY_SHA
        and hashlib.sha256(evidence).hexdigest() == EVIDENCE_SHA
    )
    ns = {"__file__": str(POLICY), "__name__": "_frozen_linux_dependency_policy"}
    exec(compile(source, str(POLICY), "exec"), ns)
    original = json.loads(evidence)
    state = json.loads(original["raw"]["attempt.json"]["utf8"])
    require(
        state["task"] == "d8c06b17ed9e4287aff515719d5bcf1a"
        and state["desktop_restored_off"] is True
    )
    block = original["raw"]["resolution.stdout"]
    raw = block["utf8"].encode()
    require(len(raw) == block["bytes"] and hashlib.sha256(raw).hexdigest() == block["sha256"])
    packet = json.loads(raw)
    ns["validate_packet"](packet, packet["inputs"])
    inputs = packet["inputs"]
    require(digest(REPO / "pyproject.toml") == inputs["project_sha256"])
    require(digest(REPO / "deploy/constraints-tested.txt") == inputs["seed_sha256"])
    result = json.loads(original["raw"]["result.json"]["utf8"])
    require(
        result["outcome"] == "LINUX_DEPENDENCY_REPORT_PASSED"
        and result["owned_cleanup"] is True
        and result["inventory_restored"] is True
    )
    require(
        result["resolution_sha256"] == block["sha256"]
        and result["projection"] == packet["projection"]
    )
    files = packet["projection"]["files"]
    require(len(files) == 36)
    return files


def curl_args(path, entry, files, limit):
    require(0 < limit <= MAX_FILE and entry in files)
    require(entry["url"] in {v["url"] for v in files} and path.name == entry["filename"])
    require(
        re.fullmatch(
            r"https://files\.pythonhosted\.org/packages/[A-Za-z0-9/._+!-]+\.whl", entry["url"]
        )
    )
    require(entry["url"].rsplit("/", 1)[-1] == entry["filename"])
    return [
        str(CURL),
        "-q",
        "--noproxy",
        "*",
        "--proto",
        "=https",
        "--max-redirs",
        "0",
        "--no-ssl-auto-client-cert",
        "--fail",
        "--silent",
        "--connect-timeout",
        "10",
        "--max-time",
        "30",
        "--max-filesize",
        str(limit),
        "--retry",
        "0",
        "--output",
        str(path),
        "--write-out",
        "%{http_code}\n%{url_effective}",
        "--url",
        entry["url"],
    ]


def environment():
    return {
        key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ
    }


def lock_bytes(files):
    return (
        "# Candidate only: Linux x86_64 / CPython 3.11; not an installed application lock.\n"
        + "".join(
            v["name"] + "==" + v["version"] + " --hash=sha256:" + v["sha256"] + "\n" for v in files
        )
    ).encode("ascii")


def check_wheelhouse(root, files, manifest):
    require(
        type(manifest) is dict
        and set(manifest) == {"kind", "source_evidence_sha256", "files", "total_bytes"}
    )
    directory = root / "wheels"
    s = directory.lstat()
    require(stat.S_ISDIR(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400)
    require({v.name for v in directory.iterdir()} == {v["filename"] for v in files})
    require(
        manifest["kind"] == "oracle9-closed-wheels-v1"
        and manifest["source_evidence_sha256"] == EVIDENCE_SHA
    )
    require(len(manifest["files"]) == len(files))
    total = 0
    for source, entry in zip(files, manifest["files"]):
        require(set(entry) == {"name", "version", "filename", "url", "sha256", "bytes"})
        require(
            {key: entry[key] for key in source if key in entry}
            == {key: source[key] for key in entry if key != "bytes"}
        )
        path = directory / entry["filename"]
        regular(path)
        require(
            type(entry["bytes"]) is int
            and 0 < entry["bytes"] <= MAX_FILE
            and path.stat().st_size == entry["bytes"]
        )
        require(digest(path) == entry["sha256"])
        total += entry["bytes"]
    require(total <= MAX_TOTAL and manifest["total_bytes"] == total)
    regular(root / "requirements.dependencies.lock")
    require((root / "requirements.dependencies.lock").read_bytes() == lock_bytes(files))
    return total


def main(root):
    require(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize)
    require(root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve())
    require(root.name.startswith("maskgw-oracle9-wheels-20261025-") and not root.is_symlink())
    require(not root.lstat().st_file_attributes & 0x400)
    state = json.loads((root / "attempt.json").read_bytes())
    require(
        state["kind"] == "maskgw-oracle9-wheels" and re.fullmatch("[0-9a-f]{32}", state["task"])
    )
    require(state["invoked"] is False and not (root / "download-result.json").exists())
    require(digest(Path(__file__)) == state["program_sha256"] and digest(CURL) == CURL_SHA)
    files = selected_files()
    require(state["policy_sha256"] == POLICY_SHA and state["evidence_sha256"] == EVIDENCE_SHA)
    state.update(invoked=True, phase="DOWNLOAD_CONSUMED")
    save(root / "attempt.json", state)
    result = {
        "kind": "oracle9-wheel-download-result-v1",
        "task": state["task"],
        "outcome": "NOT_PASSED",
        "files": [],
    }
    started = time.monotonic()
    total = 0
    entries = []
    try:
        directory = root / "wheels"
        directory.mkdir()
        for entry in files:
            require(digest(CURL) == CURL_SHA)
            remaining = 1500 - (time.monotonic() - started)
            require(remaining > 0 and total < MAX_TOTAL)
            path = directory / entry["filename"]
            write_new(path, b"")
            regular(path)
            limit = min(MAX_FILE, MAX_TOTAL - total)
            p = subprocess.run(
                curl_args(path, entry, files, limit),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=CURL.parent,
                env=environment(),
                timeout=min(35, remaining),
                check=False,
            )
            result["files"].append({"filename": path.name, "exit": p.returncode})
            require(p.returncode == 0 and len(p.stdout) <= 4096)
            require(p.stdout.replace(b"\r\n", b"\n") == ("200\n" + entry["url"]).encode("ascii"))
            regular(path)
            size = path.stat().st_size
            require(0 < size <= limit)
            with path.open("r+b") as f:
                os.fsync(f.fileno())
            require(digest(path) == entry["sha256"])
            total += size
            entries.append(
                {key: entry[key] for key in ("name", "version", "filename", "url", "sha256")}
                | {"bytes": size}
            )
            print(
                json.dumps(
                    {
                        "downloaded": len(entries),
                        "total": len(files),
                        "name": entry["name"],
                        "bytes": size,
                    }
                ),
                flush=True,
            )
        manifest = {
            "kind": "oracle9-closed-wheels-v1",
            "source_evidence_sha256": EVIDENCE_SHA,
            "files": entries,
            "total_bytes": total,
        }
        write_new(root / "requirements.dependencies.lock", lock_bytes(files))
        require(check_wheelhouse(root, files, manifest) == total)
        require(selected_files() == files and digest(Path(__file__)) == state["program_sha256"])
        require(digest(CURL) == CURL_SHA)
        write_new(root / "manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode())
        state["wheelhouse_ready"] = True
        state["manifest_sha256"] = digest(root / "manifest.json")
        save(root / "attempt.json", state)
        result.update(
            outcome="WHEELS_DOWNLOADED_VERIFIED",
            total_bytes=total,
            manifest_sha256=state["manifest_sha256"],
        )
    except BaseException:
        result["failure_after_completed_files"] = len(entries)
    finally:
        result["seconds"] = time.monotonic() - started
        save(root / "download-result.json", result)
        print(json.dumps(result), flush=True)
    return 0 if result["outcome"] == "WHEELS_DOWNLOADED_VERIFIED" else 2


if __name__ == "__main__":
    require(len(sys.argv) == 2)
    raise SystemExit(main(Path(sys.argv[1])))
