"""One-shot vendor-runtime attestation; no gateway, database or client inputs."""

import base64
from collections import Counter
import errno
import hashlib
import json
import os
import pathlib
import ssl
import stat
import subprocess
import sys
import zlib

ROOT = pathlib.Path("/opt/maskgw")
QF = "%{NAME}|%{ARCH}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}\n"
EXPECTED = {
    ("expat", "x86_64"): ("0", "2.5.0", "6.el9_8.7"),
    ("libnsl2", "x86_64"): ("0", "2.0.0", "1.el9"),
    ("libtirpc", "x86_64"): ("0", "1.3.3", "9.el9"),
    ("mpdecimal", "x86_64"): ("0", "2.5.1", "3.el9"),
    ("python3.11", "x86_64"): ("0", "3.11.13", "10.0.1.el9_8"),
    ("python3.11-libs", "x86_64"): ("0", "3.11.13", "10.0.1.el9_8"),
    ("python3.11-pip", "noarch"): ("0", "22.3.1", "6.el9"),
    ("python3.11-pip-wheel", "noarch"): ("0", "22.3.1", "6.el9"),
    ("python3.11-setuptools-wheel", "noarch"): ("0", "65.5.1", "5.el9"),
}
APPENDS = {
    "passwd": b"maskgw:x:10001:10001:Mask Gateway:/var/empty:/sbin/nologin\n",
    "group": b"maskgw:x:10001:\n",
}
RESTORED_DIRS = ("/usr/share/man", "/usr/share/man/man1", "/var/cache/ldconfig")
VERIFY_POLICY = "oracle9-python-restored-directories-v1"
AUX_PATH = "/var/cache/ldconfig/aux-cache"
AUX_CACHE = pathlib.Path(AUX_PATH)
TIRPC_DIGEST = "a49b5fc0698b359730de2566c15fee3186a1f9b801c58abae9ee25a672c9447c"
TIRPC_LINK = "libtirpc.so.3.0.0"
TIRPC_NAMES = ("libtirpc.so.3", TIRPC_LINK)
RUNTIME_POLICY = "oracle9-python-lib64-cache-v1"


def is_hash(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_stat(value, kind):
    require(set(value) == {"kind", "dev", "ino", "uid", "gid", "mode"})
    require(value["kind"] == kind)
    for field in ("dev", "ino", "uid", "gid", "mode"):
        require(type(value[field]) is int and value[field] >= 0)
    require(value["ino"] > 0 and value["uid"] == value["gid"] == 0)
    if kind == "symlink":
        require(value["mode"] == 0o777)
    else:
        validate_directory_fact({**value, "symlink": False})


def stat_fact(path):
    s = pathlib.Path(path).lstat()
    return {
        "kind": "symlink"
        if stat.S_ISLNK(s.st_mode)
        else "directory"
        if stat.S_ISDIR(s.st_mode)
        else "other",
        "dev": s.st_dev,
        "ino": s.st_ino,
        "uid": s.st_uid,
        "gid": s.st_gid,
        "mode": stat.S_IMODE(s.st_mode),
    }


def validate_alias(value):
    require(set(value) == {"link", "alias", "target"})
    require(value["link"] in ("usr/lib64", "/usr/lib64"))
    validate_stat(value["alias"], "symlink")
    validate_stat(value["target"], "directory")


def read_alias_before():
    rows = (ROOT / "lib64-before.txt").read_text().splitlines()
    require(len(rows) == 3)
    result = {"link": rows[0]}
    for label, kind, line in zip(("alias", "target"), ("symlink", "directory"), rows[1:]):
        dev, ino, uid, gid, mode = line.split("|")
        result[label] = {
            "kind": kind,
            "dev": int(dev),
            "ino": int(ino),
            "uid": int(uid),
            "gid": int(gid),
            "mode": int(mode, 8),
        }
    validate_alias(result)
    return result


def attest_lib64(owned_paths):
    before = read_alias_before()
    after = {
        "link": os.readlink("/lib64"),
        "alias": stat_fact("/lib64"),
        "target": stat_fact("/usr/lib64"),
    }
    validate_alias(after)
    require(before == after)
    require(rpm("-q", "libtirpc", "--qf", "%{FILEDIGESTALGO}\n") == "8\n")
    declared = {}
    for line in rpm(
        "-q",
        "libtirpc",
        "--qf",
        "[%{FILENAMES}|%{FILEMODES:octal}|%{FILEDIGESTS}|%{FILELINKTOS}\n]",
    ).splitlines():
        name, mode, digest, link = line.split("|")
        if name in ("/lib64/" + n for n in TIRPC_NAMES):
            require(name not in declared)
            declared[name] = (int(mode, 8), digest, link)
    require(
        declared
        == {
            "/lib64/libtirpc.so.3": (0o120777, "", TIRPC_LINK),
            "/lib64/" + TIRPC_LINK: (0o100755, TIRPC_DIGEST, ""),
        }
    )
    nodes = {}
    for name in TIRPC_NAMES:
        original, physical = "/lib64/" + name, "/usr/lib64/" + name
        require(owned_paths.get(original) == ("libtirpc", "x86_64") and physical not in owned_paths)
        a, b = pathlib.Path(original).lstat(), pathlib.Path(physical).lstat()
        require((a.st_dev, a.st_ino) == (b.st_dev, b.st_ino))
        mode, digest, link = declared[original]
        require(
            a.st_mode == b.st_mode == mode and a.st_uid == a.st_gid == b.st_uid == b.st_gid == 0
        )
        actual_link = os.readlink(physical) if stat.S_ISLNK(mode) else ""
        require(actual_link == link)
        data = actual_link.encode() if link else pathlib.Path(physical).read_bytes()
        actual_digest = hashlib.sha256(data).hexdigest()
        require(link or actual_digest == digest)
        nodes[physical] = {
            "rpm_path": original,
            "owner": ["libtirpc", "x86_64"],
            "alias_dev": a.st_dev,
            "alias_ino": a.st_ino,
            "physical_dev": b.st_dev,
            "physical_ino": b.st_ino,
            "kind": "symlink" if link else "regular",
            "linkto": actual_link,
            "sha256": actual_digest,
            "declared_digest": digest,
        }
        owned_paths[physical] = ("libtirpc", "x86_64")
    return {"before": before, "after": after, "nodes": nodes}


def attest_linker_cache():
    rows = (ROOT / "linker-cache-before.txt").read_text().splitlines()
    require(rows == ["absent"] or len(rows) == 2 and rows[0] == "present" and is_hash(rows[1]))
    before = {"kind": "absent"} if rows == ["absent"] else {"kind": "regular", "sha256": rows[1]}
    p = pathlib.Path("/etc/ld.so.cache")
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == s.st_gid == 0 and not s.st_mode & 0o6022)
    require(0 < s.st_size <= 16 * 1024 * 1024)
    require(rpm("-qf", "--qf", "%{NAME}|%{ARCH}\n", str(p)) == "glibc|x86_64\n")
    return {
        "before": before,
        "after": {
            "path": "/etc/ld.so.cache",
            "kind": "regular",
            "uid": s.st_uid,
            "gid": s.st_gid,
            "mode": stat.S_IMODE(s.st_mode),
            "bytes": s.st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "owner": ["glibc", "x86_64"],
        },
    }


def validate_runtime_report(value):
    validate_verification_report(value)
    require(value.get("runtime_attestation_policy") == RUNTIME_POLICY)
    lib = value.get("lib64")
    require(type(lib) is dict and set(lib) == {"before", "after", "nodes"})
    validate_alias(lib["before"])
    validate_alias(lib["after"])
    require(lib["before"] == lib["after"])
    require(set(lib["nodes"]) == {"/usr/lib64/" + n for n in TIRPC_NAMES})
    for physical, node in lib["nodes"].items():
        require(
            set(node)
            == {
                "rpm_path",
                "owner",
                "alias_dev",
                "alias_ino",
                "physical_dev",
                "physical_ino",
                "kind",
                "linkto",
                "sha256",
                "declared_digest",
            }
        )
        name = physical.rsplit("/", 1)[1]
        require(node["rpm_path"] == "/lib64/" + name and node["owner"] == ["libtirpc", "x86_64"])
        for key in ("alias_dev", "alias_ino", "physical_dev", "physical_ino"):
            require(type(node[key]) is int and node[key] >= (1 if key.endswith("ino") else 0))
        require(
            node["alias_dev"] == node["physical_dev"] and node["alias_ino"] == node["physical_ino"]
        )
        if name == "libtirpc.so.3":
            require(node["kind"] == "symlink" and node["linkto"] == TIRPC_LINK)
            require(
                node["declared_digest"] == ""
                and node["sha256"] == hashlib.sha256(TIRPC_LINK.encode()).hexdigest()
            )
        else:
            require(node["kind"] == "regular" and node["linkto"] == "")
            require(node["declared_digest"] == node["sha256"] == TIRPC_DIGEST)
        if "new_nodes" in value:
            require(
                value["new_nodes"][physical] == {k: node[k] for k in ("owner", "sha256", "kind")}
            )
        else:
            require(physical in value["new_paths"])
    cache = value.get("linker_cache")
    require(type(cache) is dict and set(cache) == {"before", "after"})
    before, after = cache["before"], cache["after"]
    require(
        before == {"kind": "absent"}
        or set(before) == {"kind", "sha256"}
        and before["kind"] == "regular"
        and is_hash(before["sha256"])
    )
    require(set(after) == {"path", "kind", "uid", "gid", "mode", "bytes", "sha256", "owner"})
    require(after["path"] == "/etc/ld.so.cache" and after["kind"] == "regular")
    require(after["owner"] == ["glibc", "x86_64"] and is_hash(after["sha256"]))
    require(
        type(after["uid"]) is int
        and type(after["gid"]) is int
        and after["uid"] == after["gid"] == 0
    )
    require(
        type(after["mode"]) is int and 0 <= after["mode"] <= 0o7777 and not after["mode"] & 0o6022
    )
    require(type(after["bytes"]) is int and 0 < after["bytes"] <= 16 * 1024 * 1024)


def validate_directory_facts(facts):
    require(type(facts) is dict and set(facts) == set(RESTORED_DIRS))
    for v in facts.values():
        validate_directory_fact(v)


def validate_directory_fact(v):
    require(v.get("kind") == "directory" and v.get("symlink") is False)
    require(type(v.get("uid")) is int and type(v.get("gid")) is int and v["uid"] == v["gid"] == 0)
    require(type(v.get("mode")) is int and 0 <= v["mode"] <= 0o7777)
    require(not v["mode"] & 0o7022 and v["mode"] & 0o500 == 0o500)


def directory_facts():
    facts = {}
    for name in RESTORED_DIRS:
        p = pathlib.Path(name)
        try:
            s = p.lstat()
        except FileNotFoundError:
            facts[name] = {"kind": "absent"}
            continue
        facts[name] = {
            "kind": "directory" if stat.S_ISDIR(s.st_mode) else "other",
            "symlink": stat.S_ISLNK(s.st_mode),
            "uid": s.st_uid,
            "gid": s.st_gid,
            "mode": stat.S_IMODE(s.st_mode),
        }
    return facts


def validate_verification_report(value):
    require(
        value.get("verification_policy") == VERIFY_POLICY
        and value.get("base_verify_accepted") is True
    )
    unchanged = value.get("base_verify_unchanged")
    require(type(unchanged) is bool)
    if unchanged:
        require(
            value.get("restored_directories") == [] and value.get("restored_directory_facts") == {}
        )
    else:
        require(value.get("restored_directories") == list(RESTORED_DIRS))
        validate_directory_facts(value.get("restored_directory_facts"))
    aux = value.get("aux_cache")
    require(type(aux) is dict)
    if aux.get("action") == "absent":
        require(set(aux) == {"action"})
    else:
        require(aux.get("action") in ("retained-base-glibc", "removed-unowned"))
        expected = {"action", "path", "bytes", "sha256", "uid", "gid", "mode"}
        if aux["action"] == "retained-base-glibc":
            expected.add("owner")
            require(aux.get("owner") == ["glibc", "x86_64"])
        require(set(aux) == expected and aux["path"] == AUX_PATH)
        require(
            type(aux["uid"]) is int and type(aux["gid"]) is int and aux["uid"] == aux["gid"] == 0
        )
        require(
            type(aux["mode"]) is int and 0 <= aux["mode"] <= 0o7777 and not aux["mode"] & 0o6022
        )
        require(type(aux["bytes"]) is int and 0 < aux["bytes"] <= 16 * 1024 * 1024)
        require(
            type(aux["sha256"]) is str
            and len(aux["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in aux["sha256"])
        )


def handle_aux_cache(before, facts):
    fact = facts["/var/cache/ldconfig"]
    if fact.get("kind") == "absent":
        return {"action": "absent"}
    validate_directory_fact(fact)
    p = AUX_CACHE
    names = {v.name for v in p.parent.iterdir()}
    require(names <= {"aux-cache"})
    if not names:
        return {"action": "absent"}
    require((ROOT / "cache-dir-before.txt").read_bytes() == b"absent\n")
    require(verify_lines(before).count("missing     /var/cache/ldconfig") == 1)
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == s.st_gid == 0)
    require(not s.st_mode & 0o6022 and 0 < s.st_size <= 16 * 1024 * 1024)
    data_hash = hashlib.sha256(p.read_bytes()).hexdigest()
    q = subprocess.run(
        ["rpm", "-qf", "--qf", "%{NAME}|%{ARCH}\n", str(p)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        check=False,
        env={"PATH": os.environ["PATH"], "LC_ALL": "C"},
    )
    print(
        "@@AUX_CACHE_OWNER@@"
        + json.dumps(
            {
                "exit": q.returncode,
                "stdout": q.stdout[:4096].decode("utf8", errors="replace"),
                "stderr_bytes": len(q.stderr),
                "stderr_sha256": hashlib.sha256(q.stderr).hexdigest(),
            }
        )
    )
    require(not q.stderr and len(q.stdout) <= 4096)
    info = {
        "path": AUX_PATH,
        "bytes": s.st_size,
        "sha256": data_hash,
        "uid": s.st_uid,
        "gid": s.st_gid,
        "mode": stat.S_IMODE(s.st_mode),
    }
    if q.returncode == 0:
        require(q.stdout == b"glibc|x86_64\n")
        info["action"] = "retained-base-glibc"
        info["owner"] = ["glibc", "x86_64"]
    else:
        require(
            q.returncode == 1 and q.stdout == f"file {p} is not owned by any package\n".encode()
        )
        p.unlink()
        info["action"] = "removed-unowned"
    return info


def require(value):
    if not value:
        raise RuntimeError("RUNTIME_ATTESTATION_REFUSED")


def rpm(*args, allow_verify=False):
    p = subprocess.run(
        ["rpm", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        check=False,
        env={"PATH": os.environ["PATH"], "LC_ALL": "C"},
    )
    if p.stderr or p.returncode not in ((0, 1) if allow_verify else (0,)):
        print(
            "@@RPM_DIAGNOSTIC@@"
            + json.dumps(
                {
                    "operation": args[0] if args else "NONE",
                    "exit": p.returncode,
                    "stderr_bytes": len(p.stderr),
                    "stderr_sha256": hashlib.sha256(p.stderr).hexdigest(),
                    "public_stderr_prefix": p.stderr[:4096].decode("utf8", errors="replace"),
                },
                sort_keys=True,
            )
        )
    require(not p.stderr and p.returncode in ((0, 1) if allow_verify else (0,)))
    require(len(p.stdout) <= 2 * 1024 * 1024)
    return p.stdout.decode("utf8", "strict")


def inventory(text):
    rows = {}
    keys = {}
    for line in text.splitlines():
        name, arch, epoch, version, release = line.split("|")
        if name == "gpg-pubkey":
            require((version, release) not in keys)
            keys[version, release] = (arch, epoch)
            continue
        require((name, arch) not in rows)
        rows[name, arch] = (epoch, version, release)
    return rows, keys


def verify_lines(raw):
    # Declared, separately byte-checked changes only. All other old RPM
    # deviations must equal the recorded base, never silently become accepted.
    return sorted(
        line
        for line in raw.splitlines()
        if line.rsplit(" ", 1)[-1] not in ("/etc/passwd", "/etc/group", "/etc/ld.so.cache")
    )


def compare_verification(before, after, facts=None):
    a, b = verify_lines(before), verify_lines(after)
    result = {
        "verification_policy": VERIFY_POLICY,
        "base_verify_accepted": True,
        "base_verify_unchanged": a == b,
        "restored_directories": [],
        "restored_directory_facts": {},
    }
    if a == b:
        return result
    if a != b:
        removed = list((Counter(a) - Counter(b)).elements())
        added = list((Counter(b) - Counter(a)).elements())
        expected = ["missing     " + p for p in RESTORED_DIRS]
        if not added and Counter(removed) == Counter(expected):
            validate_directory_facts(facts)
            result["restored_directories"] = list(RESTORED_DIRS)
            result["restored_directory_facts"] = facts
            return result
        print(
            "@@RPM_VERIFY_DIFF@@"
            + json.dumps(
                {
                    "before_count": len(a),
                    "after_count": len(b),
                    "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                    "after_sha256": hashlib.sha256(after.encode()).hexdigest(),
                    "removed_count": len(removed),
                    "added_count": len(added),
                    "removed": [v[:512] for v in removed[:40]],
                    "added": [v[:512] for v in added[:40]],
                },
                sort_keys=True,
            )
        )
    require(a == b)
    return result


def require_owned_new_paths(unowned):
    if unowned:
        ordered = sorted(unowned)
        print(
            "@@RPM_UNOWNED_NEW@@"
            + json.dumps(
                {
                    "count": len(ordered),
                    "paths_sha256": hashlib.sha256("\n".join(ordered).encode()).hexdigest(),
                    "paths": [v[:512] for v in ordered[:40]],
                },
                sort_keys=True,
            )
        )
    require(not unowned)


def finish():
    require(sys.version_info[:3] == (3, 11, 13))
    before, before_keys = inventory((ROOT / "rpm-before.txt").read_text())
    after_text = rpm("-qa", "--qf", QF)
    after, after_keys = inventory(after_text)
    allowed_packages, allowed_keys = inventory((ROOT / "allowed-keys.txt").read_text())
    require(not allowed_packages and allowed_keys)
    require(all(after_keys.get(k) == v for k, v in before_keys.items()))
    require(all(k in before_keys or allowed_keys.get(k) == v for k, v in after_keys.items()))
    require(all(after.get(key) == value for key, value in before.items()))
    require(all(after.get(key) == value for key, value in EXPECTED.items()))
    require(pathlib.Path("/etc/os-release").read_bytes() == (ROOT / "os-before").read_bytes())
    os_release = pathlib.Path("/etc/os-release").read_text()
    require('\nID="ol"\n' in "\n" + os_release or "\nID=ol\n" in "\n" + os_release)
    require('\nVERSION_ID="9.8"\n' in "\n" + os_release)

    before_verification = (ROOT / "verify-before.txt").read_text()
    facts = directory_facts()
    aux_cache = handle_aux_cache(before_verification, facts)
    require(aux_cache["action"] != "retained-base-glibc" or ("glibc", "x86_64") in before)
    verification = rpm("-Va", allow_verify=True)
    (ROOT / "verify-after.txt").write_text(verification)
    verification_result = compare_verification(before_verification, verification, facts)
    print("@@RPM_VERIFY_ACCEPTED@@" + json.dumps(verification_result, sort_keys=True))
    require(("glibc", "x86_64") in before)
    linker_cache = attest_linker_cache()
    added = {key for key in after if key not in before}
    require(added == set(EXPECTED))
    require(not rpm("-V", *sorted({name for name, arch in added}), allow_verify=True).strip())

    for name, extra in APPENDS.items():
        p = pathlib.Path("/etc") / name
        original = (ROOT / (name + "-before")).read_bytes()
        require(p.read_bytes() == original and b"maskgw:" not in original)
        require(not any(line.split(b":")[2] == b"10001" for line in original.splitlines()))
        require(original.endswith(b"\n"))
        p.write_bytes(original + extra)
    pathlib.Path("/var/empty").mkdir(exist_ok=True)

    # Every old /etc regular file is hashed by the shell before installation.
    for line in (ROOT / "etc-before.txt").read_text().splitlines():
        digest, filename = line.split("  ", 1)
        if filename in ("/etc/passwd", "/etc/group", "/etc/ld.so.cache"):
            continue
        require(hashlib.sha256(pathlib.Path(filename).read_bytes()).hexdigest() == digest)

    previous = set((ROOT / "paths-before.txt").read_text().splitlines())
    # Public RPMs are inputs, not runtime contents. Remove only the nine
    # exact, already checked regular files; keep the manifest/headers/hashes.
    manifest = json.loads((ROOT / "bundle.json").read_bytes())
    for entry in manifest["files"]:
        if entry["filename"] == "runtime_probe.py":
            continue
        p = ROOT / entry["filename"]
        require(p.is_file() and not p.is_symlink())
        require(hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"])
        p.unlink()
    for name in ("dnf.log", "dnf.rpm.log", "dnf.librepo.log", "hawkey.log"):
        p = pathlib.Path("/var/log") / name
        if str(p) not in previous and p.exists():
            require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 8 * 1024 * 1024)
            p.unlink()
    owned_paths = {}
    owner = None
    ownership = rpm(
        "-q",
        *sorted({name for name, arch in added}),
        "--qf",
        "@@PKG@@%{NAME}|%{ARCH}\n[%{FILENAMES}\n]",
    )
    for line in ownership.splitlines():
        if line.startswith("@@PKG@@"):
            owner = tuple(line[len("@@PKG@@") :].split("|"))
            require(owner in added)
        else:
            require(owner is not None and line.startswith("/"))
            if line in {
                prefix + name for prefix in ("/lib64/", "/usr/lib64/") for name in TIRPC_NAMES
            }:
                require(line not in owned_paths)
            owned_paths[line] = owner
    lib64 = attest_lib64(owned_paths)
    new_nodes = {}
    checked_privileges = 0
    for top in ("/usr", "/etc", "/opt/maskgw", "/var/cache/ldconfig"):
        for p in pathlib.Path(top).rglob("*"):
            if str(p) in previous and str(p) not in (
                "/etc/passwd",
                "/etc/group",
                "/etc/ld.so.cache",
            ):
                continue
            mode = p.lstat().st_mode
            require(not mode & 0o6000)
            if stat.S_ISREG(mode):
                try:
                    os.getxattr(p, "security.capability", follow_symlinks=False)
                except OSError as error:
                    require(error.errno == errno.ENODATA)
                else:
                    require(False)
            checked_privileges += 1
    directories = [
        *RESTORED_DIRS,
        "/usr",
        "/etc",
        "/opt",
        "/var",
        "/var/lib",
        "/var/cache",
        "/var/log",
        "/tmp",
        "/var/tmp",
    ]
    unowned = []
    for top in ("/usr", "/etc"):
        for p in pathlib.Path(top).rglob("*"):
            text = str(p)
            if p.is_dir() and not p.is_symlink():
                directories.append(text)
                continue
            if text in previous or text.startswith("/usr/lib/sysimage/rpm/"):
                continue
            if text == "/etc/ld.so.cache":
                continue
            owner = owned_paths.get(text)
            if owner is None:
                unowned.append(text)
                continue
            data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
            new_nodes[text] = {
                "owner": list(owner),
                "sha256": hashlib.sha256(data).hexdigest(),
                "kind": "symlink" if p.is_symlink() else "regular",
            }
    require_owned_new_paths(unowned)

    result = {
        "python": list(sys.version_info[:3]),
        "executable": sys.executable,
        "openssl": ssl.OPENSSL_VERSION,
        "rpm_before": (ROOT / "rpm-before.txt").read_text(),
        "rpm_after": after_text,
        "added": [list(v) for v in sorted(added)],
        "gpg_keys_before": [list(k) for k in sorted(before_keys)],
        "gpg_keys_after": [list(k) for k in sorted(after_keys)],
        "signatures": rpm("-qa", "--qf", "%{NAME}|%{ARCH}|%{RSAHEADER:pgpsig}\n"),
        **verification_result,
        "aux_cache": aux_cache,
        "runtime_attestation_policy": RUNTIME_POLICY,
        "lib64": lib64,
        "linker_cache": linker_cache,
        "os_unchanged": True,
        "new_nodes": new_nodes,
        "passwd_group_literal_append": True,
        "no_new_privilege_bits_or_caps": True,
        "privilege_checked_nodes": checked_privileges,
        "directories": directories,
        "empty_dirs": {
            p: not any(pathlib.Path(p).iterdir())
            for p in ("/tmp", "/var/tmp", "/var/log", "/var/empty")
        },
    }
    data = (json.dumps(result, sort_keys=True) + "\n").encode()
    require(len(data) <= 8 * 1024 * 1024)
    (ROOT / "runtime.json").write_bytes(data)
    validate_runtime_report(result)
    summary = {k: v for k, v in result.items() if k not in ("new_nodes", "signatures")}
    summary["new_paths"] = sorted(new_nodes)
    summary["runtime_sha256"] = hashlib.sha256(data).hexdigest()
    summary["runtime_bytes"] = len(data)
    raw_summary = json.dumps(summary, sort_keys=True).encode()
    require(len(raw_summary) <= 2 * 1024 * 1024)
    packed = base64.b64encode(zlib.compress(raw_summary, 9)).decode("ascii")
    require(len(packed) <= 1024 * 1024)
    print(
        "@@RUNTIME@@"
        + json.dumps({"encoding": "zlib-base64-v1", "raw_bytes": len(raw_summary), "data": packed})
    )


def probe():
    import ctypes
    import grp
    import pwd
    import sqlite3
    import zlib

    require(os.getuid() == os.getgid() == 10001)
    require(pwd.getpwuid(10001).pw_name == grp.getgrgid(10001).gr_name == "maskgw")
    require(sys.version_info[:3] == (3, 11, 13) and sys.prefix == "/opt/maskgw/venv")
    require(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1)
    v = json.loads((ROOT / "runtime.json").read_bytes())
    require(v["python"] == [3, 11, 13] and v["os_unchanged"] is True)
    validate_runtime_report(v)
    require(ctypes.CDLL(None) is not None and zlib.decompress(zlib.compress(b"ok")) == b"ok")
    print(
        json.dumps(
            {
                "kind": "oracle9-python-probe",
                "python": v["python"],
                "uid": os.getuid(),
                "ssl": ssl.OPENSSL_VERSION,
                "sqlite": sqlite3.sqlite_version,
                "runtime_sha256": hashlib.sha256((ROOT / "runtime.json").read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    require(len(sys.argv) == 2 and sys.argv[1] in ("finish", "probe"))
    (finish if sys.argv[1] == "finish" else probe)()
