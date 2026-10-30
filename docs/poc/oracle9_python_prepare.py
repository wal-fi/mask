"""Owned, one-shot vendor Python image preparation; no calls on import."""

import asyncio
import base64
import hashlib
import json
import os
import pathlib
import re
import runpy
import subprocess
import sys
import threading
import time
import zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CLI = pathlib.Path("C:/Users/w.filho/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe")
HOME = pathlib.Path(os.environ["USERPROFILE"])
HELPER = REPO / "docs/poc/run_linux_as_probe.py"
PAYLOAD = REPO / "deploy/oracle9_python_payload.py"
DOWNLOADER = REPO / "docs/poc/oracle9_rpm_download.py"
PREP_CAPS = frozenset(
    {
        "CAP_CHOWN",
        "CAP_DAC_OVERRIDE",
        "CAP_FOWNER",
        "CAP_SETFCAP",
        "CAP_SETUID",
        "CAP_SETGID",
        "CAP_SYS_CHROOT",
    }
)
META = (
    HOME
    / ".docker/contexts/meta/fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json"
)
IMAGE = "sha256:d8c0a1f95f3394a2b40ece95dbff199cea94d06ac0ed354a7b88e96e2df5bb94"
PATH_ENV = "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE_LAYERS = ["sha256:c8033153c9465fa4e4f02df8b57cda30011514f5b1e7438bf521776e63f0abaf"]
ENTRY = ["/opt/maskgw/venv/bin/python", "-I", "-B"]
ENV = [
    PATH_ENV,
    "HOME=/var/empty",
    "LANG=C.UTF-8",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTHONUNBUFFERED=1",
]
PINS = {
    HELPER: "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627",
    CLI: "60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599",
    HOME
    / ".docker/config.json": "f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a",
    META: "c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25",
}


def require(value):
    if not value:
        raise RuntimeError("PREPARATION_REFUSED")


def validate_prepared_image(value, task, tag):
    image = value["Id"]
    require(re.fullmatch("sha256:[0-9a-f]{64}", image) is not None)
    require(value.get("Os") == "linux" and value.get("Architecture") == "amd64")
    require(value.get("RepoTags") == [tag])
    c = value["Config"]
    require(value["RootFS"]["Layers"][:1] == BASE_LAYERS and len(value["RootFS"]["Layers"]) == 2)
    require(all(re.fullmatch("sha256:[0-9a-f]{64}", v) for v in value["RootFS"]["Layers"]))
    require(c["User"] == "10001:10001" and c["WorkingDir"] == "/var/empty")
    require(c["Entrypoint"] == ENTRY and not c.get("Cmd"))
    require(c["Env"] == ENV and c["Labels"]["maskgw.task"] == task)
    require(not c.get("Volumes") and not c.get("ExposedPorts"))
    require(c.get("Healthcheck") in (None, {"Test": ["NONE"]}))
    return image


def pins():
    require(all(hashlib.sha256(p.read_bytes()).hexdigest() == v for p, v in PINS.items()))
    require(
        json.loads(META.read_bytes())["Endpoints"]["docker"]["Host"]
        in ("npipe:////./pipe/dockerDesktopLinuxEngine", "npipe://./pipe/dockerDesktopLinuxEngine")
    )


def save(path, value):
    data = (json.dumps(value, sort_keys=True) + "\n").encode()
    require(len(data) <= 4 * 1024 * 1024)
    with path.with_suffix(path.suffix + ".next").open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, path)


def shell(payload, task):
    require(re.fullmatch("[0-9a-f]{32}", task) is not None)
    rows = runpy.run_path(str(DOWNLOADER))["manifest_rows"]()
    packages = " ".join("/opt/maskgw/" + v["filename"] for v in rows)
    script = r"""set -euo pipefail
exec 2>&1
printf '@@STAGE@@BASELINE\n'
test -d /opt
test ! -e /opt/maskgw
test ! -L /opt/maskgw
test -d /maskgw-rpm-input-TASK_ID
test ! -L /maskgw-rpm-input-TASK_ID
mv /maskgw-rpm-input-TASK_ID /opt/maskgw
chmod 0755 /opt/maskgw
chmod 0644 /opt/maskgw/*
chown 0:0 /opt/maskgw/*
for input in /opt/maskgw/*; do
    [[ "$(stat -c '%u:%g:%a' "$input")" == '0:0:644' ]]
    stat -c '%n|%u|%g|%a' "$input"
done
cd /opt/maskgw
sha256sum --check inputs.sha256
printf '%s  runtime_probe.py\n' PAYLOAD_SHA | sha256sum --check
mkdir -p /opt/maskgw/keydb
rpm --dbpath /opt/maskgw/keydb --initdb
rpm --dbpath /opt/maskgw/keydb --import /etc/pki/rpm-gpg/RPM-GPG-KEY-oracle
rpm --dbpath /opt/maskgw/keydb -qa --qf '%{NAME}|%{ARCH}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}\n' > /opt/maskgw/allowed-keys.txt
rpm --dbpath /opt/maskgw/keydb -qa --qf '%{VERSION}\n' > /opt/maskgw/allowed-keyids.txt
rpm -qa --qf '%{NAME}|%{ARCH}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}\n' | LC_ALL=C sort > /opt/maskgw/rpm-before.txt
if rpm -Va > /opt/maskgw/verify-before.txt; then :; else test "$?" -eq 1; fi
cp /etc/os-release /opt/maskgw/os-before
cp /etc/passwd /opt/maskgw/passwd-before
cp /etc/group /opt/maskgw/group-before
test -L /lib64
test -d /usr/lib64 && test ! -L /usr/lib64
readlink /lib64 > /opt/maskgw/lib64-before.txt
stat -c '%d|%i|%u|%g|%a' /lib64 >> /opt/maskgw/lib64-before.txt
stat -c '%d|%i|%u|%g|%a' /usr/lib64 >> /opt/maskgw/lib64-before.txt
if [[ ! -e /etc/ld.so.cache && ! -L /etc/ld.so.cache ]]; then
    printf 'absent\n' > /opt/maskgw/linker-cache-before.txt
else
    test -f /etc/ld.so.cache && test ! -L /etc/ld.so.cache
    printf 'present\n' > /opt/maskgw/linker-cache-before.txt
    sha256sum /etc/ld.so.cache | cut -d ' ' -f 1 >> /opt/maskgw/linker-cache-before.txt
fi
if [[ ! -e /var/cache/ldconfig && ! -L /var/cache/ldconfig ]]; then
    printf 'absent\n' > /opt/maskgw/cache-dir-before.txt
else
    printf 'present\n' > /opt/maskgw/cache-dir-before.txt
fi
find /usr /etc /var/log /tmp /var/tmp /root -print > /opt/maskgw/paths-before.txt
find /etc -type f -readable -exec sha256sum {} + > /opt/maskgw/etc-before.txt
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-oracle
packages=(PACKAGES)
printf '@@STAGE@@SIGNATURES\n'
for package in "${packages[@]}"; do
    verified=$(rpm --define '_pkgverify_level all' -K "$package")
    [[ "$verified" == *'signatures OK'* && "$verified" != *NOKEY* && "$verified" != *'NOT OK'* ]]
    printf '%s\n' "$verified"
    signature=$(rpm --define '_pkgverify_level all' -qp --qf '%{RSAHEADER:pgpsig}' "$package")
    keyid="${signature##*Key ID }"
    [[ "$keyid" =~ ^[0-9a-fA-F]{8,16}$ ]]
    short="${keyid: -8}"
    found=false
    while read -r allowed; do
        if [[ "${allowed,,}" == "${short,,}" ]]; then found=true; fi
    done < /opt/maskgw/allowed-keyids.txt
    "$found"
done
rpm --define '_pkgverify_level all' -qp --qf '%{NAME}|%{ARCH}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}\n' "${packages[@]}" | LC_ALL=C sort > /opt/maskgw/actual-rpms.txt
[[ "$(cat /opt/maskgw/expected-rpms.txt)" == "$(cat /opt/maskgw/actual-rpms.txt)" ]]
rpm --define '_pkgverify_level all' -qp --qf '[%{FILENAMES}|%{FILEMODES:octal}\n]' "${packages[@]}" > /opt/maskgw/declared-modes.txt
while IFS='|' read -r filename mode; do
    [[ "$filename" == /* && "$mode" =~ ^[0-7]+$ ]]
    (( (8#$mode & 06000) == 0 ))
done < /opt/maskgw/declared-modes.txt
rpm --define '_pkgverify_level all' -qp --qf '%|FILECAPS?{[%{FILECAPS}\n]}:{(none)\n}|' "${packages[@]}" > /opt/maskgw/declared-caps.txt
while IFS= read -r caps; do
    [[ -z "$caps" || "$caps" == '(none)' ]]
done < /opt/maskgw/declared-caps.txt
printf '@@STAGE@@DEPENDENCIES\n'
rpm --define '_pkgverify_level all' --test -i "${packages[@]}"
printf '@@STAGE@@INSTALL\n'
rpm --define '_pkgverify_level all' -ivh "${packages[@]}"
export PYTHONDONTWRITEBYTECODE=1
printf '@@STAGE@@VENV\n'
python3.11 -B -m venv /opt/maskgw/venv
/opt/maskgw/venv/bin/python -I -B /opt/maskgw/runtime_probe.py finish
"""
    return (
        script.replace("PACKAGES", packages)
        .replace("PAYLOAD_SHA", hashlib.sha256(payload).hexdigest())
        .replace("TASK_ID", task)
    )


def identity(info, name, task, image):
    require(info["Name"] == "/" + name and info["Config"]["Labels"].get("maskgw.task") == task)
    require(info["Image"] == image and re.fullmatch("[0-9a-f]{64}", info["Id"]))
    return info["Id"]


def profile(info, image, command, prep):
    c, h = info["Config"], info["HostConfig"]
    require(c["Image"] == image and c["Env"] == ([PATH_ENV] if prep else ENV))
    require(c["User"] == ("0:0" if prep else "10001:10001"))
    require(c["Entrypoint"] == (["/bin/bash"] if prep else ENTRY) and c["Cmd"] == command)
    require(not info["Mounts"] and c["Healthcheck"]["Test"] == ["NONE"])
    require(h["ReadonlyRootfs"] is (not prep) and h["Privileged"] is False)
    mem, fds, pids = (2 * 1024 * 1024 * 1024, 256, 64) if prep else (128 * 1024 * 1024, 64, 16)
    require(h["Memory"] == h["MemorySwap"] == mem and h["PidsLimit"] == pids)
    require(h["NanoCpus"] == 1000000000 and h["ShmSize"] == 1048576)
    require(h["NetworkMode"] == "none" and h["IpcMode"] == h["CgroupnsMode"] == "private")
    require(not h.get("PidMode") and not h.get("UTSMode") and not h.get("Init"))
    additions = h.get("CapAdd") or []
    require(type(additions) is list and all(type(v) is str for v in additions))
    normalized = {v if v.startswith("CAP_") else "CAP_" + v for v in additions}
    require(
        h["CapDrop"] == ["ALL"]
        and len(normalized) == len(additions)
        and normalized == (PREP_CAPS if prep else frozenset())
    )
    require(h["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges=true"]))
    require(h["RestartPolicy"]["Name"] == "no" and h["LogConfig"]["Type"] == "none")
    require(not any(h.get(k) for k in ("Binds", "Devices", "DeviceRequests", "PortBindings")))
    require(
        len(h["Ulimits"]) == 2
        and {v["Name"]: (v["Soft"], v["Hard"]) for v in h["Ulimits"]}
        == {"nofile": (fds, fds), "core": (0, 0)}
    )


def validate_diff(raw, report):
    rows = raw.decode("utf8", "strict").splitlines()
    require(len(rows) <= 20000)
    directories = set(report["directories"]) | {
        "/opt/maskgw",
        "/var/lib/rpm",
        "/var/lib/dnf",
    }
    for line in rows:
        action, path = line.split(" ", 1)
        require(action in ("A", "C") and path.startswith("/") and "\x00" not in path)
        if path in directories:
            continue
        if path == "/var/cache/ldconfig/aux-cache" and action == "A":
            aux = report.get("aux_cache", {})
            require(
                aux.get("action") == "retained-base-glibc"
                and aux.get("owner") == ["glibc", "x86_64"]
            )
            continue
        if any(
            path.startswith(top + "/")
            for top in (
                "/opt/maskgw",
                "/var/lib/rpm",
                "/var/lib/dnf",
                "/usr/lib/sysimage/rpm",
            )
        ):
            continue
        if path == "/etc/ld.so.cache":
            cache = report.get("linker_cache", {})
            after = cache.get("after", {})
            require(after.get("owner") == ["glibc", "x86_64"] and after.get("kind") == "regular")
            before = cache.get("before", {})
            require(
                (action == "A" and before == {"kind": "absent"})
                or (
                    action == "C"
                    and before.get("kind") == "regular"
                    and re.fullmatch("[0-9a-f]{64}", before.get("sha256", "")) is not None
                )
            )
            continue
        if path in ("/etc/passwd", "/etc/group"):
            require(report["passwd_group_literal_append"])
            continue
        if action == "A" and path.startswith(("/usr/", "/etc/")) and path in report["new_paths"]:
            continue
        if path in ("/tmp", "/var/tmp", "/var/empty") and report["empty_dirs"][path]:
            continue
        raise RuntimeError("DIFF_REFUSED")


def verify_copy_origin(current, original_raw, expected_sha):
    require(hashlib.sha256(original_raw).hexdigest() == expected_sha)
    original = json.loads(original_raw)
    require(original["kind"] == current["kind"] == "oracle9-rpms-v1")
    before = {v["filename"]: v for v in original["files"] if v["filename"] != "runtime_probe.py"}
    after = {v["filename"]: v for v in current["files"] if v["filename"] != "runtime_probe.py"}
    require(len(before) == len(after) == 9 and before == after)


def decode_summary(raw):
    wire = json.loads(raw)
    require(type(wire) is dict and set(wire) == {"encoding", "raw_bytes", "data"})
    require(wire["encoding"] == "zlib-base64-v1" and type(wire["data"]) is str)
    require(type(wire["raw_bytes"]) is int and 0 < wire["raw_bytes"] <= 2 * 1024 * 1024)
    require(len(wire["data"]) <= 1024 * 1024)
    packed = base64.b64decode(wire["data"], validate=True)
    decoder = zlib.decompressobj()
    value = decoder.decompress(packed, 2 * 1024 * 1024 + 1)
    require(
        len(value) == wire["raw_bytes"]
        and decoder.eof
        and not decoder.unconsumed_tail
        and not decoder.unused_data
    )
    report = json.loads(value)
    require(type(report) is dict)
    return report


async def main(root):
    require(
        sys.flags.optimize == 0 and root.parent.resolve() == (HOME / "AppData/Local/Temp").resolve()
    )
    require(root.name.startswith("maskgw-oracle9-python-20261023-"))
    require(root.resolve().parent == root.parent.resolve() and not root.is_symlink())
    require(not getattr(root.stat(), "st_file_attributes", 0) & 0x400)
    state = json.loads((root / "attempt.json").read_bytes())
    require(
        state["kind"] == "maskgw-oracle9-python"
        and state["phase"] == "APP_READY"
        and state["invoked"] is False
    )
    require(re.fullmatch("[0-9a-f]{32}", state["task"]) and not (root / "result.json").exists())
    pins()
    payload = PAYLOAD.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == state["payload_sha256"])
    payload_module = {"__name__": "_maskgw_pinned_runtime_policy", "__file__": str(PAYLOAD)}
    exec(compile(payload, str(PAYLOAD), "exec"), payload_module)
    payload_policy = payload_module["validate_runtime_report"]
    require(hashlib.sha256(PAYLOAD.read_bytes()).hexdigest() == state["payload_sha256"])
    require(
        hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest() == state["program_sha256"]
    )
    downloaded = state.get("bundle_download_invoked") is True and state.get("bundle_origin") in (
        None,
        "download-v1",
    )
    copied = (
        state.get("bundle_download_invoked") is False
        and state.get("bundle_origin") == "verified-local-copy-v1"
    )
    require(state.get("bundle_ready") is True and (downloaded or copied))
    if copied:
        origin = REPO / "docs/poc/evidence/oracle9-rpm-download-result-20261023.json"
        require(
            hashlib.sha256(origin.read_bytes()).hexdigest()
            == state["bundle_origin_evidence_sha256"]
        )
        original = json.loads(origin.read_bytes())
        require(original["task"] == state["bundle_origin_task"])
        require(
            original["raw"]["bundle/bundle.json"]["sha256"]
            == state["bundle_origin_manifest_sha256"]
        )
    require(hashlib.sha256(DOWNLOADER.read_bytes()).hexdigest() == state["download_program_sha256"])
    download_module = runpy.run_path(str(DOWNLOADER))
    bundle_manifest = download_module["check_bundle"](root, state)
    if copied:
        verify_copy_origin(
            bundle_manifest,
            original["raw"]["bundle/bundle.json"]["utf8"].encode("utf8"),
            state["bundle_origin_manifest_sha256"],
        )
    state["invoked"] = True
    state["phase"] = "PREPARATION_CONSUMED"
    save(root / "attempt.json", state)
    mod = runpy.run_path(str(HELPER))
    bounded = mod["bounded"]
    result = {
        "profile": "oracle9-python",
        "task": state["task"],
        "commands": [],
        "outcome": "NOT_PASSED",
        "owned_cleanup": False,
        "inventory_restored": False,
    }
    tag = "maskgw-oracle9-python:" + state["task"]
    records = []
    stop = threading.Event()
    fired = threading.Event()
    active = {"cid": None}

    def watchdog():
        if not stop.wait(1200):
            fired.set()
            if active["cid"] is not None:
                try:
                    pins()
                    subprocess.run(
                        [
                            str(CLI),
                            "--context",
                            "desktop-linux",
                            "kill",
                            "--signal",
                            "KILL",
                            active["cid"],
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=mod["environment"](),
                        timeout=10,
                        check=False,
                    )
                except Exception:
                    pass

    thread = threading.Thread(target=watchdog, name="maskgw-oracle9-python-watchdog", daemon=False)

    async def cli(label, *args, timeout=10, limit=2 * 1024 * 1024):
        pins()
        result["stage"] = label
        t = time.monotonic()
        try:
            rc, raw = await bounded(
                [str(CLI), "--context", "desktop-linux", *args], timeout=timeout, limit=limit
            )
        except BaseException as e:
            category = (
                "CLI_TIMEOUT"
                if type(e) is TimeoutError
                else e.category
                if type(e) is mod["HostFault"]
                else "CLI_OS"
                if isinstance(e, OSError)
                else "CLI_FAULT"
            )
            result["commands"].append(
                {"name": label, "category": category, "exit": None, "seconds": time.monotonic() - t}
            )
            raise
        result["commands"].append(
            {
                "name": label,
                "exit": rc,
                "category": "OK" if rc == 0 else "NONZERO",
                "seconds": time.monotonic() - t,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        return rc, raw

    async def inspect(target):
        rc, raw = await cli("inspect-own", "inspect", "--type", "container", target)
        require(rc == 0)
        rows = json.loads(raw)
        require(type(rows) is list and len(rows) == 1)
        return rows[0]

    async def unused_tag():
        # image ls is successful even when absent; daemon errors never mean absent.
        rc, raw = await cli(
            "tag-collision",
            "image",
            "ls",
            "--no-trunc",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            tag,
        )
        require(rc == 0 and not raw.strip())

    async def create(image, suffix, command, prep):
        name = "maskgw-ol9-python-" + state["task"][:12] + "-" + suffix
        record = {"name": name, "image": image, "cid": None}
        records.append(record)
        mb, fds, pids = ("2g", "256", "64") if prep else ("128m", "64", "16")
        args = [
            "create",
            "--pull",
            "never",
            "--name",
            name,
            "--label",
            "maskgw.task=" + state["task"],
            "--network",
            "none",
            "--ipc",
            "private",
            "--cgroupns",
            "private",
            "--user",
            "0:0" if prep else "10001:10001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--memory",
            mb,
            "--memory-swap",
            mb,
            "--pids-limit",
            pids,
            "--cpus",
            "1",
            "--shm-size",
            "1m",
            "--ulimit",
            "nofile=" + fds + ":" + fds,
            "--ulimit",
            "core=0:0",
            "--restart",
            "no",
            "--log-driver",
            "none",
            "--no-healthcheck",
        ]
        if prep:
            args += ["--entrypoint", "/bin/bash"]
            args += [v for cap in sorted(PREP_CAPS) for v in ("--cap-add", cap)]
        else:
            args += ["--read-only"]
        rc, raw = await cli("create-" + suffix, *args, image, *command, timeout=20)
        require(rc == 0 and re.fullmatch("[0-9a-f]{64}", raw.decode("ascii").strip()))
        record["cid"] = raw.decode("ascii").strip()
        info = await inspect(record["cid"])
        identity(info, name, state["task"], image)
        profile(info, image, command, prep)
        active["cid"] = record["cid"]
        return record

    try:
        rc, raw = await cli("version", "version", "--format", "{{json .Server}}")
        require(rc == 0 and json.loads(raw)["Os"] == "linux" and json.loads(raw)["Arch"] == "amd64")
        rc, raw = await cli("inventory-before", "ps", "-aq", "--no-trunc")
        require(rc == 0 and not raw.strip())
        rc, raw = await cli("daemon-memory", "info", "--format", "{{json .MemTotal}}")
        require(rc == 0)
        total = json.loads(raw)
        require(type(total) is int and total >= 8 * 1024 * 1024 * 1024)
        result["daemon_memory_total"] = total
        await unused_tag()
        rc, raw = await cli("base-image", "image", "inspect", IMAGE)
        require(rc == 0)
        base = json.loads(raw)[0]
        require(
            base["Id"] == IMAGE
            and base["Config"]["Env"] == [PATH_ENV]
            and base["RootFS"]["Layers"] == BASE_LAYERS
        )
        require(not any(base["Config"].get(k) for k in ("Volumes", "ExposedPorts", "Healthcheck")))
        require(base["Config"]["Cmd"] == ["/bin/bash"])
        script = shell(payload, state["task"])
        require(len(script) < 25000)
        thread.start()
        prep = await create(IMAGE, "prep", ["-c", script], True)
        download_module["check_bundle"](root, state)
        rc, _ = await cli(
            "copy-bundle",
            "cp",
            str(root / "bundle"),
            prep["cid"] + ":/maskgw-rpm-input-" + state["task"],
            timeout=30,
        )
        require(rc == 0)
        info = await inspect(prep["cid"])
        identity(info, prep["name"], state["task"], IMAGE)
        profile(info, IMAGE, ["-c", script], True)
        require(info["State"]["Running"] is False)
        rc, raw = await cli("install-runtime", "start", "--attach", prep["cid"], timeout=300)
        with (root / "install.stdout").open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        require(rc == 0 and raw.count(b"@@RUNTIME@@") == 1)
        report = decode_summary(raw.split(b"@@RUNTIME@@")[1])
        require(
            report["python"] == [3, 11, 13]
            and report["base_verify_accepted"] is True
            and report["os_unchanged"] is True
        )
        result["runtime"] = report
        payload_policy(report)
        require(
            report["no_new_privilege_bits_or_caps"] is True
            and type(report["privilege_checked_nodes"]) is int
            and report["privilege_checked_nodes"] > 0
        )
        info = await inspect(prep["cid"])
        identity(info, prep["name"], state["task"], IMAGE)
        require(
            not info["State"]["Running"]
            and info["State"]["ExitCode"] == 0
            and not info["State"]["OOMKilled"]
        )
        rc, raw = await cli("diff", "diff", prep["cid"])
        require(rc == 0)
        with (root / "diff.txt").open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        validate_diff(raw, report)
        await unused_tag()
        changes = [
            "USER 10001:10001",
            "WORKDIR /var/empty",
            "ENTRYPOINT " + json.dumps(ENTRY),
            "CMD []",
            "ENV " + " ".join(ENV[1:]),
        ]
        args = [value for change in changes for value in ("--change", change)]
        rc, raw = await cli(
            "commit-image", "commit", "--pause=false", *args, prep["cid"], tag, timeout=60
        )
        with (root / "commit.stdout").open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        require(rc == 0)
        # Human-facing commit stdout is evidence only, never the image selector.
        # This unique own tag was absent just before commit. Metadata is authoritative.
        rc, raw = await cli("prepared-inspect", "image", "inspect", tag)
        require(rc == 0)
        values = json.loads(raw)
        require(type(values) is list and len(values) == 1)
        image = validate_prepared_image(values[0], state["task"], tag)
        result["prepared_image"] = image
        result["prepared_tag"] = tag
        probe = await create(image, "probe", ["/opt/maskgw/runtime_probe.py", "probe"], False)
        rc, raw = await cli("probe", "start", "--attach", probe["cid"], timeout=20, limit=16384)
        require(rc == 0)
        result["probe"] = json.loads(raw)
        require(result["probe"]["runtime_sha256"] == report["runtime_sha256"])
        require(
            result["probe"]["kind"] == "oracle9-python-probe" and result["probe"]["uid"] == 10001
        )
        info = await inspect(probe["cid"])
        identity(info, probe["name"], state["task"], image)
        require(
            not info["State"]["Running"]
            and info["State"]["ExitCode"] == 0
            and not info["State"]["OOMKilled"]
        )
        result["outcome"] = "PYTHON_RUNTIME_PASSED"
    except BaseException:
        result["failure_stage"] = result.get("stage", "PRECHECK")
    finally:
        clean = True
        for record in reversed(records):
            try:
                info = await inspect(record["cid"] or record["name"])
                cid = identity(info, record["name"], state["task"], record["image"])
                record["cid"] = cid
                record["state_before_cleanup"] = {
                    key: info["State"][key] for key in ("Running", "ExitCode", "OOMKilled")
                }
                if info["State"]["Running"]:
                    rc, _ = await cli("stop-own", "stop", "--time", "5", cid, timeout=15)
                    require(rc == 0)
                    info = await inspect(cid)
                    identity(info, record["name"], state["task"], record["image"])
                    require(not info["State"]["Running"])
                rc, _ = await cli("remove-own", "rm", cid, timeout=20)
                require(rc == 0)
                if active["cid"] == cid:
                    active["cid"] = None
            except BaseException:
                clean = False
        stop.set()
        if thread.ident is not None:
            thread.join(timeout=12)
        result["owned_cleanup"] = clean and not thread.is_alive() and not fired.is_set()
        result["containers"] = records
        try:
            rc, raw = await cli("inventory-after", "ps", "-aq", "--no-trunc")
            result["inventory_restored"] = rc == 0 and not raw.strip()
        except BaseException:
            pass
        if not result["owned_cleanup"] or not result["inventory_restored"]:
            result["outcome"] = "NOT_PASSED"
        save(root / "result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "runtime"}, sort_keys=True))
    return 0 if result["outcome"] == "PYTHON_RUNTIME_PASSED" else 2


if __name__ == "__main__":
    require(len(sys.argv) == 2)
    raise SystemExit(asyncio.run(main(pathlib.Path(sys.argv[1]))))
