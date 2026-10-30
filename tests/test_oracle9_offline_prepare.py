"""Docker command/ownership orchestration with fake daemon, never Docker CLI."""

import asyncio
import base64
import hashlib
import importlib.util
import json
import types
import zlib
from pathlib import Path
from typing import Any

import pytest

GOOD_DIFF = (
    b"C /opt\nC /opt/maskgw\nA /opt/maskgw/oracle9-installed.json\n"
    b"A /opt/maskgw/venv/lib/python3.11/site-packages/maskgw/__init__.py\n"
)


@pytest.fixture
def host() -> Any:
    path = Path(__file__).resolve().parents[1] / "docs/poc/oracle9_offline_prepare.py"
    spec = importlib.util.spec_from_file_location("_offline_host_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def origin_for(host: Any) -> dict[str, Any]:
    origin = host.frozen(host.FOUNDATION, host.FOUNDATION_SHA, "_frozen_test_foundation")
    assert isinstance(origin, dict)
    origin["pins"] = lambda: None
    origin["save"] = lambda path, value: path.write_text(json.dumps(value), encoding="utf-8")
    return origin


def container(  # noqa: PLR0913, PLR0917 -- independent daemon profile fields in a fixture.
    host: Any,
    origin: Any,
    name: str,
    task: str,
    image: str,
    command: list[str],
    probe: bool = False,
) -> dict[str, Any]:
    uid = "10001" if probe else "0"
    size = "16777216" if probe else "67108864"
    return {
        "Name": "/" + name,
        "Id": ("d" if probe else "c") * 64,
        "Image": image,
        "Config": {
            "Image": image,
            "User": uid + ":" + uid,
            "WorkingDir": "/var/empty",
            "Entrypoint": origin["ENTRY"],
            "Cmd": command,
            "Env": origin["ENV"],
            "Labels": {
                "maskgw.task": task,
                "maskgw.source-sha256": host.PAYLOAD_SHA,
                "maskgw.manifest-sha256": host.MANIFEST_SHA,
            },
            "Tty": False,
            "OpenStdin": False,
            "Healthcheck": {"Test": ["NONE"]},
        },
        "HostConfig": {
            "ReadonlyRootfs": probe,
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Memory": 536870912,
            "MemorySwap": 536870912,
            "PidsLimit": 32,
            "NanoCpus": 1000000000,
            "ShmSize": 8388608,
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": 128, "Hard": 128},
            ],
            "Tmpfs": {"/tmp": f"rw,noexec,nosuid,nodev,size={size},uid={uid},gid={uid},mode=0700"},  # noqa: S108 -- Docker mount key, no host file.
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "PidMode": "",
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "LogConfig": {"Type": "none"},
        },
        "State": {"Running": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False, "Dead": False},
    }


def test_command_transports_only_public_pinned_payload(host):
    payload = host.PAYLOAD.read_bytes()
    args = host.native_command(
        payload, "install", "/opt/maskgw/install-inputs-" + "a" * 32, host.MANIFEST_SHA
    )
    assert args[0] == "-c" and args[2] == "install" and sum(map(len, args)) < 26000
    encoded = args[1].split("b64decode(", 1)[1].split(")", 1)[0].strip("'\"")
    assert zlib.decompress(base64.b64decode(encoded)) == payload
    assert host.PAYLOAD_SHA in args[1]


@pytest.mark.parametrize("bad", ["mode", "arity", "prefix", "hash", "source"])
def test_command_wrong_role_or_source_refuses(host, bad):
    payload, mode, args = host.PAYLOAD.read_bytes(), "probe", ["a" * 64]
    if bad == "mode":
        mode = "query"
    elif bad == "arity":
        args.append("extra")
    elif bad == "prefix":
        mode, args = "install", ["/etc", host.MANIFEST_SHA]
    elif bad == "hash":
        args = ["wrong"]
    else:
        payload += b"\n"
    with pytest.raises(RuntimeError):
        host.native_command(payload, mode, *args)


@pytest.mark.parametrize("probe", [False, True])
def test_create_profile_has_no_mount_port_pull_or_restart(host, probe):
    args = host.create_args(host.IMAGE, "own", "a" * 32, ["-c", "public"], probe)
    assert args[0] == "create" and "--pull=never" in args
    assert "--mount" not in args and "--publish" not in args and "--privileged" not in args
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--user") + 1] == ("10001:10001" if probe else "0:0")
    assert ("--read-only" in args) is probe and args[args.index("--restart") + 1] == "no"


@pytest.mark.parametrize(
    "bad",
    [
        "name",
        "image",
        "task",
        "payload",
        "manifest",
        "memory",
        "mount",
        "network",
        "user",
        "rootfs",
        "caps",
        "tmpfs",
    ],
)
def test_container_identity_and_profile_never_accepts_foreign_or_weakened(host, bad):
    origin = origin_for(host)
    info = container(host, origin, "own", "a" * 32, host.IMAGE, ["public"])
    if bad == "name":
        info["Name"] = "/foreign"
    elif bad == "image":
        info["Image"] = "sha256:" + "b" * 64
    elif bad in ("task", "payload", "manifest"):
        field = {
            "task": "maskgw.task",
            "payload": "maskgw.source-sha256",
            "manifest": "maskgw.manifest-sha256",
        }[bad]
        info["Config"]["Labels"][field] = "other"
    elif bad == "memory":
        info["HostConfig"]["Memory"] = 0
    elif bad == "mount":
        info["Mounts"] = [{"Type": "bind", "Source": "host"}]
    elif bad == "network":
        info["HostConfig"]["NetworkMode"] = "host"
    elif bad == "user":
        info["Config"]["User"] = "10001:10001"
    elif bad == "rootfs":
        info["HostConfig"]["ReadonlyRootfs"] = True
    elif bad == "caps":
        info["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
    else:
        info["HostConfig"]["Tmpfs"] = {}
    with pytest.raises(RuntimeError):
        host.validate_container(info, "own", "a" * 32, host.IMAGE, ["public"], False, origin)


def test_profiles_validate_for_both_roles(host):
    origin = origin_for(host)
    for probe in (False, True):
        info = container(host, origin, "own", "a" * 32, host.IMAGE, ["public"], probe)
        host.validate_container(info, "own", "a" * 32, host.IMAGE, ["public"], probe, origin)


def test_diff_only_declared_prefix_and_attestation(host):
    good = GOOD_DIFF
    assert host.validate_diff(good) == 4
    for extra in (
        b"A /root/private\n",
        b"A /opt/maskgw/install-inputs-task/file\n",
        b"A /opt/maskgw/venv/../escape\n",
    ):
        with pytest.raises(RuntimeError):
            host.validate_diff(good + extra)


def test_host_independently_rejects_any_removed_base_path(host):
    with pytest.raises(RuntimeError):
        host.validate_diff(GOOD_DIFF + b"D /opt/maskgw/venv/bin/python\n")


@pytest.mark.parametrize("bad", ["multiple", "outcome", "missing-newline", "oversize"])
def test_report_is_one_bounded_json_object(host, bad):
    raw = json.dumps({"outcome": "expected", "attestation_sha256": "a" * 64}).encode() + b"\n"
    if bad == "multiple":
        raw += raw
    elif bad == "outcome":
        raw = raw.replace(b"expected", b"refused")
    elif bad == "missing-newline":
        raw = raw[:-1]
    else:
        raw = b"x" * (1536 * 1024 + 1)
    with pytest.raises(RuntimeError):
        host.report_line(raw, "expected")


class FakeDocker:
    def __init__(self, host: Any, origin: Any, fault: str, payload: Path):
        self.host, self.origin, self.fault, self.payload = host, origin, fault, payload
        self.rows: dict[str, Any] = {}
        self.calls: list[list[str]] = []
        self.attest = b'{"public_fake_attestation":true}\n'
        self.attest_sha = hashlib.sha256(self.attest).hexdigest()
        self.layers = origin["BASE_LAYERS"] + ["sha256:" + "b" * 64]
        self.candidate = "sha256:" + "e" * 64
        self.tag = ""

    def image_info(self, candidate: bool) -> dict[str, Any]:
        task = "a" * 32 if candidate else self.host.ORIGIN_TASK
        tag = self.tag if candidate else "maskgw-oracle9-python:" + task
        return {
            "Id": self.candidate if candidate else self.host.IMAGE,
            "Os": "linux",
            "Architecture": "amd64",
            "RepoTags": [tag],
            "RootFS": {"Layers": self.layers + (["sha256:" + "f" * 64] if candidate else [])},
            "Config": {
                "User": "10001:10001",
                "WorkingDir": "/var/empty",
                "Env": self.origin["ENV"],
                "Entrypoint": self.origin["ENTRY"],
                "Cmd": [],
                "Labels": {
                    "maskgw.task": task,
                    "maskgw.source-sha256": self.host.PAYLOAD_SHA,
                    "maskgw.manifest-sha256": self.host.MANIFEST_SHA,
                },
            },
        }

    async def bounded(self, argv: list[str], **_kwargs: Any) -> tuple[int, bytes]:  # noqa: PLR0911, PLR0912 -- stateful fake CLI dispatch.
        assert argv[1:3] == ["--context", "desktop-linux"]
        args = argv[3:]
        self.calls.append(args)
        command = args[0]
        if command == "version":
            return 0, b"{}"
        if command == "info":
            return 0, json.dumps(
                {
                    "OSType": "linux",
                    "Architecture": "x86_64",
                    "KernelVersion": "fake",
                    "MemTotal": 4 * 1024**3,
                    "Driver": "overlayfs",
                    "CgroupVersion": "2",
                    "ServerVersion": "29.7.2",
                }
            ).encode()
        if command == "ps":
            if "--filter" in args:
                selected = args[-1].removeprefix("id=")
                return 0, (selected.encode() if selected in self.rows else b"")
            return 0, "\n".join(self.rows).encode()
        if command == "image":
            if args[1] == "ls":
                return 0, b""
            return 0, json.dumps([self.image_info(args[-1] != self.host.IMAGE)]).encode()
        if command == "create":
            name = args[args.index("--name") + 1]
            probe = name.endswith("-probe")
            image = self.candidate if probe else self.host.IMAGE
            index = args.index(image)
            info = container(
                self.host, self.origin, name, "a" * 32, image, args[index + 1 :], probe
            )
            if self.fault == "foreign-owner":
                info["Config"]["Labels"]["maskgw.task"] = "foreign"
            self.rows[info["Id"]] = info
            return 0, info["Id"].encode() + b"\n"
        if command == "inspect":
            target = args[-1]
            matches = [v for k, v in self.rows.items() if k == target or v["Name"] == "/" + target]
            return (0, json.dumps(matches).encode()) if matches else (1, b"")
        if command == "cp":
            if args[1].endswith(":/opt/maskgw/oracle9-installed.json"):
                Path(args[2]).write_bytes(self.attest)
            elif self.fault == "copy-failure":
                return 1, b""
            return 0, b""
        if command == "start":
            info = self.rows[args[-1]]
            probe = info["Name"].endswith("-probe")
            outcome = "CANDIDATE_PROBE_VERIFIED" if probe else "CANDIDATE_INSTALL_VERIFIED"
            if self.fault == "native-refused":
                outcome = "CANDIDATE_NATIVE_REFUSED"
            if self.fault == "source-changed":
                self.payload.write_bytes(self.payload.read_bytes() + b"\n")
            return 0, json.dumps(
                {
                    "outcome": outcome,
                    "attestation_sha256": self.attest_sha,
                    "attestation_bytes": len(self.attest),
                    "managed_inputs_removed": True,
                }
            ).encode() + b"\n"
        if command == "diff":
            return (
                0,
                GOOD_DIFF,
            )
        if command == "commit":
            assert "--pause" not in args and args[-2] in self.rows
            assert "CMD []" in args and "USER 10001:10001" in args
            self.tag = args[-1]
            return 0, b"public warning\n" + self.candidate.encode() + b"\n"
        if command == "rm":
            del self.rows[args[-1]]
            return 0, b"removed\n"
        if command == "kill":
            raise AssertionError("no fake process is running")
        raise AssertionError("unexpected fake command " + str(args))


@pytest.mark.parametrize(
    "fault", ["", "copy-failure", "native-refused", "source-changed", "foreign-owner"]
)
def test_fake_full_orchestration_never_calls_docker_and_owns_cleanup(
    host, tmp_path, monkeypatch, fault
):
    parent = tmp_path / "Temp"
    root = parent / "maskgw-oracle9-offline-fake"
    root.mkdir(parents=True)
    payload = tmp_path / "pinned-native.py"
    payload.write_bytes(host.PAYLOAD.read_bytes())
    monkeypatch.setattr(host, "PAYLOAD", payload)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        host,
        "sys",
        types.SimpleNamespace(flags=types.SimpleNamespace(isolated=True, optimize=False)),
    )
    state = {
        "kind": "maskgw-oracle9-offline",
        "phase": "APP_READY",
        "invoked": False,
        "task": "a" * 32,
        "program_sha256": hashlib.sha256(Path(host.__file__).read_bytes()).hexdigest(),
        "payload_sha256": host.PAYLOAD_SHA,
    }
    (root / "attempt.json").write_text(json.dumps(state), encoding="utf-8")
    origin = origin_for(host)
    fake = FakeDocker(host, origin, fault, payload)
    monkeypatch.setattr(host, "frozen", lambda *_args: origin)
    monkeypatch.setattr(host, "context_inputs", lambda: {})
    monkeypatch.setattr(
        host,
        "runpy",
        types.SimpleNamespace(
            run_path=lambda *_args: {"bounded": fake.bounded, "environment": lambda: {}}
        ),
    )
    code = asyncio.run(host.main(root))
    result = json.loads((root / "result.json").read_bytes())
    if not fault:
        assert code == 0 and result["outcome"] == "ORACLE9_APP_CANDIDATE_VERIFIED"
        assert result["owned_cleanup"] is True and result["inventory_restored"] is True
        assert len(result["containers"]) == 2 and all(v["removed"] for v in result["containers"])
    elif fault == "foreign-owner":
        assert code == 1 and result["owned_cleanup"] is False
        assert not any(v[0] in ("kill", "rm", "start", "commit") for v in fake.calls)
    else:
        assert code == 1 and result["outcome"] == "NOT_PASSED"
        assert result["owned_cleanup"] is True and result["inventory_restored"] is True
        assert not any(v[0] == "commit" for v in fake.calls)
    assert not any(t.name == "maskgw-oracle9-offline-watchdog" for t in host.threading.enumerate())
