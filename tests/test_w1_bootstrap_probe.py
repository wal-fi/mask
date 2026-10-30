"""Public T4 preparation only. Never runs a canary, Docker or subprocess."""

import ast
import builtins
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32
CLI = "C:/Users/w.filho/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_probe.py"))


def inventory(module: Any, case: Any) -> tuple[Any, Any]:
    intent = module["Intent"](TASK, case)
    old = REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/probe-inspect-before.json"
    value = json.loads(old.read_bytes())
    # Historical inspect was saved as its single object, not a new OS observation.
    info = value[0] if isinstance(value, list) else value
    info = deepcopy(info)
    info.update(Id="c" * 64, Name="/" + module["name_for"](TASK, case), Image=module["IMAGE"])
    config, host = info["Config"], info["HostConfig"]
    config.update(
        Image=module["IMAGE"],
        Labels=module["labels_for"](TASK),
        Cmd=list(intent.command),
        OpenStdin=True,
        StdinOnce=False,
        User="70:70" if case is module["Case"].RETAIN else "10001:10001",
    )
    host.update(Memory=134217728, MemorySwap=134217728, PidsLimit=8, Tmpfs={})
    return info, intent


@pytest.mark.parametrize("selected", range(7))
def test_each_exact_case_builds_one_bounded_public_command(module, selected):
    case = list(module["Case"])[selected]
    info, intent = inventory(module, case)
    args, measurement = module["create_args"](CLI, intent)
    assert args[0] == "create" and args[1] == "--pull=never"
    assert "--interactive" in args and "--read-only" in args
    assert args[-3] == module["IMAGE"] and args[-2] == "-c"
    assert measurement["createprocess_chars"] <= 26000 and measurement["margin_chars"] > 0
    assert "W1_PUBLIC_CANARY" not in args[-1]  # code compressed; not a private seed argument
    assert "-v" not in args and "--publish" not in args and "--tmpfs" not in args
    assert module["identity"](info, intent) == "c" * 64
    assert module["validate_container"](info, intent) == "c" * 64


def test_source_and_helper_are_pinned_before_compile(module):
    raw = module["channel_bytes"]()
    assert hashlib.sha256(raw).hexdigest() == module["CHANNEL_SHA"]
    assert hashlib.sha256(module["SOURCE"].encode("ascii")).hexdigest() == module["SOURCE_SHA"]
    command = module["command"](TASK, module["Case"].NORMAL)
    tree = ast.parse(command[1])
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "unpack"
            for node in ast.walk(tree)
        )
        == 2
    )
    # Test the exact bounded decoder without running either decoded program.
    decoder = ast.Module(body=tree.body[:2], type_ignores=[])
    namespace: dict[str, Any] = {}
    exec(compile(decoder, "<loader-decoder-only>", "exec"), namespace)  # noqa: S102
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "unpack"
    ]
    for assignment, expected in zip(
        assignments, (raw, module["SOURCE"].encode("ascii")), strict=True
    ):
        call = assignment.value
        assert isinstance(call, ast.Call)
        blob, digest = (ast.literal_eval(value) for value in call.args)
        assert namespace["unpack"](blob, digest) == expected
        with pytest.raises(SystemExit) as caught:
            namespace["unpack"](blob, "0" * 64)
        assert caught.value.code == 3


def test_own_labels_override_all_historical_image_identity_labels(module):
    image = REPO / "docs/poc/evidence/oracle9-w1-v2-run-20261027/candidate-image.json"
    value = json.loads(image.read_bytes())
    info = value[0] if isinstance(value, list) else value
    existing = set(info["Config"]["Labels"]) - {"desktop.docker.io/ports.scheme"}
    assert set(module["labels_for"](TASK)) == existing


def test_extra_presentation_label_does_not_block_cleanup_ownership(module):
    case = module["Case"].NORMAL
    info, intent = inventory(module, case)
    info["Config"]["Labels"]["desktop.docker.io/ports.scheme"] = "v2"
    assert module["identity"](info, intent) == "c" * 64
    with pytest.raises(RuntimeError):
        module["validate_container"](info, intent)


def test_cleanup_uses_captured_intent_when_source_is_unreadable(module, monkeypatch):
    case = module["Case"].NORMAL
    info, intent = inventory(module, case)

    def unreadable():
        raise RuntimeError("CHANNEL_PIN")

    monkeypatch.setitem(module["command"].__globals__, "channel_bytes", unreadable)
    assert module["identity"](info, intent) == "c" * 64
    with pytest.raises(RuntimeError, match="CHANNEL_PIN"):
        module["validate_container"](info, intent)


def test_linux_helper_import_does_not_use_windows_or_spawn(module):
    real_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name == "sys":
            return SimpleNamespace(platform="linux")
        assert name != "asyncio.windows_utils"
        return real_import(name, *args, **kwargs)

    namespace: dict[str, Any] = {
        "__name__": "_t4_linux_import",
        "__file__": "<public-channel>",
        "__builtins__": {**vars(builtins), "__import__": checked_import},
    }
    exec(compile(module["channel_bytes"](), "<public-channel>", "exec"), namespace)  # noqa: S102
    assert namespace["PIPE_TYPE"] is None and callable(namespace["read_seed_fd"])
    # Import canary definitions without its __main__ guard or any native call.
    canary: dict[str, Any] = {"__name__": "_definitions_only"}
    exec(compile(module["SOURCE"], "<public-canary>", "exec"), canary)  # noqa: S102
    assert canary["body"]() == module["public_body"]()
    assert len(module["public_body"]()) == 16384
    assert b"SEEDEND\n" in module["public_body"]()


@pytest.mark.parametrize(
    "field,value",
    [
        ("OpenStdin", False),
        ("StdinOnce", True),
        ("Tty", True),
        ("User", "0:0"),
        ("Env", ["MASKGW_TEST_DSN=public-canary"]),
        ("ExposedPorts", {"5432/tcp": {}}),
    ],
)
def test_profile_drift_refused_without_losing_ownership(module, field, value):
    case = module["Case"].NORMAL
    info, intent = inventory(module, case)
    info["Config"][field] = value
    assert module["identity"](info, intent) == "c" * 64
    with pytest.raises(RuntimeError, match="CONFIG"):
        module["validate_container"](info, intent)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ReadonlyRootfs", False),
        ("NetworkMode", "bridge"),
        ("CapAdd", ["SYS_ADMIN"]),
        ("SecurityOpt", ["seccomp=unconfined"]),
        ("MemorySwap", 268435456),
        ("PidsLimit", 32),
        ("Privileged", True),
        ("AutoRemove", True),
        ("Binds", ["/etc:/host"]),
        ("PortBindings", {"5432/tcp": [{"HostPort": "5432"}]}),
    ],
)
def test_host_profile_drift_refused_but_identity_remains(module, field, value):
    case = module["Case"].NORMAL
    info, intent = inventory(module, case)
    info["HostConfig"][field] = value
    assert module["identity"](info, intent) == "c" * 64
    with pytest.raises(RuntimeError):
        module["validate_container"](info, intent)


@pytest.mark.parametrize("defect", ["task", "image", "command", "name", "own-label"])
def test_cleanup_identity_refuses_unrelated_objects(module, defect):
    case = module["Case"].NORMAL
    info, intent = inventory(module, case)
    if defect == "task":
        info["Config"]["Labels"]["maskgw.task"] = "b" * 32
    elif defect == "image":
        info["Image"] = "sha256:" + "f" * 64
    elif defect == "command":
        info["Config"]["Cmd"] = ["-c", "unrelated"]
    elif defect == "name":
        info["Name"] += "-other"
    else:
        info["Config"]["Labels"]["maskgw.manifest-sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        module["identity"](info, intent)


@pytest.mark.parametrize("negative", [False, True])
@pytest.mark.parametrize("eof", [False, True])
def test_report_oracles_do_not_assume_eof_or_log_body_hash(module, negative, eof):
    case = module["Case"].READER_NEGATIVE if negative else module["Case"].NORMAL
    value = {
        "kind": "MASKGW_T4_CANARY_V1",
        "case": case.value,
        "bytes": 16384,
        "equality": True,
        "eof_observed": eof,
        "observation_ms": 1500,
        "uid": 10001,
        "pid": 1,
    }
    if negative:
        value["categories"] = ["FRAME"] * 4
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    assert module["report"](raw, case) == value
    value["seed_hash"] = "0" * 64
    with pytest.raises(RuntimeError, match="REPORT_SCHEMA"):
        module["report"](json.dumps(value).encode() + b"\n", case)


@pytest.mark.parametrize("defect", ["extra", "twice", "bad-bytes", "not-equal", "bad-eof"])
def test_report_rejects_success_prefix_and_malformed_facts(module, defect):
    value = {
        "kind": "MASKGW_T4_CANARY_V1",
        "case": "normal",
        "bytes": 16384,
        "equality": True,
        "eof_observed": False,
        "observation_ms": 1500,
        "uid": 10001,
        "pid": 1,
    }
    if defect == "bad-bytes":
        value["bytes"] = True
    elif defect == "not-equal":
        value["equality"] = False
    elif defect == "bad-eof":
        value["eof_observed"] = 0
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    if defect == "extra":
        raw += b"x"
    elif defect == "twice":
        raw += raw
    with pytest.raises((RuntimeError, ValueError)):
        module["report"](raw, module["Case"].NORMAL)


@pytest.mark.parametrize("case", ["immediate", "delayed", "absent", "extra"])
def test_eof_observation_has_a_fixed_bound_without_assuming_arrival(module, case):
    namespace: dict[str, Any] = {"__name__": "_definitions_only"}
    exec(compile(module["SOURCE"], "<public-canary>", "exec"), namespace)  # noqa: S102
    clock = [0.0]

    def select(_read, _write, _errors, timeout):
        assert 0.0 < timeout <= 0.05
        clock[0] += timeout
        visible = case in ("immediate", "extra") or (case == "delayed" and clock[0] >= 0.5)
        return ([0] if visible else []), [], []

    namespace["time"] = SimpleNamespace(monotonic=lambda: clock[0])
    namespace["select"] = SimpleNamespace(select=select)
    namespace["os"] = SimpleNamespace(read=lambda _fd, _size: b"x" if case == "extra" else b"")
    if case == "extra":
        with pytest.raises(RuntimeError, match="T4_REFUSED"):
            namespace["observe_eof"]()
    else:
        eof, elapsed = namespace["observe_eof"]()
        assert eof is (case != "absent")
        assert 0 <= elapsed <= 1500
        if case == "absent":
            assert elapsed == 1500


def test_intent_is_immutable_and_create_does_not_reread_source(module, monkeypatch):
    intent = module["Intent"](TASK, module["Case"].NORMAL)
    original = intent.command

    def unreadable():
        raise RuntimeError("CHANNEL_PIN")

    monkeypatch.setitem(module["command"].__globals__, "channel_bytes", unreadable)
    args, _ = module["create_args"](CLI, intent)
    assert tuple(args[-2:]) == original
    with pytest.raises(AttributeError):
        intent.command = ("-c", "unrelated")
