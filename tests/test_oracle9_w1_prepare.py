"""Pure W1 host builders and validators; no Desktop, Docker or processes."""

import json
import runpy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "docs/poc/oracle9_w1_prepare.py"
CLI = r"C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
TASK = "0" * 32
OLD_SOURCE = "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af"
OLD_MANIFEST = "359a055ccbd7689dce453f7979f5d0ac137cd5963f599d462400abe7f1d87c22"


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(SOURCE))


@pytest.fixture
def policies(module: Any) -> Any:
    return module["policy_pair"]()


def foundation() -> dict[str, Any]:
    return {
        "ENTRY": ["/opt/maskgw/venv/bin/python", "-I", "-B"],
        "ENV": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME=/var/empty",
            "LANG=C.UTF-8",
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONUNBUFFERED=1",
        ],
    }


def base(module: Any) -> dict[str, Any]:
    return {
        "Id": module["IMAGE"],
        "Os": "linux",
        "Architecture": "amd64",
        "RepoTags": [module["OLD_TAG"]],
        "RootFS": {"Layers": list(module["LAYERS"])},
        "Config": {
            "Entrypoint": foundation()["ENTRY"],
            "Env": foundation()["ENV"],
            "Healthcheck": {"Test": ["NONE"]},
            "User": "10001:10001",
            "WorkingDir": "/var/empty",
            "Labels": {
                "desktop.docker.io/ports.scheme": "v2",
                "maskgw.task": module["OLD_TASK"],
                "maskgw.source-sha256": OLD_SOURCE,
                "maskgw.manifest-sha256": OLD_MANIFEST,
            },
        },
    }


def test_policy_exports_only_five_functions_and_rebinds_two_metadata(module, policies):
    old, new, changed = policies
    assert set(old) == set(new) == module["EXPORTS"]
    assert changed == ["MANIFEST_SHA", "PAYLOAD_SHA"]
    assert (
        old["create_args"].__globals__["PAYLOAD_SHA"]
        == "ee2becec0e6683807827e3682a410497f94a24d7509d6670cd88b50654d4c5af"
    )
    assert new["create_args"].__globals__["PAYLOAD_SHA"] == module["PAYLOAD_SHA"]
    for name in ("main", "native_command", "validate_diff", "context_inputs"):
        with pytest.raises(KeyError):
            _ = new[name]
    with pytest.raises(TypeError):
        new["main"] = lambda: None


def test_original_image_binds_exact_id_layers_and_old_metadata(module, policies):
    old, _, _ = policies
    assert module["validate_base"](base(module), old, foundation()) == module["IMAGE"]
    bad = base(module)
    bad["RootFS"]["Layers"][-1] = "sha256:" + "0" * 64
    with pytest.raises(RuntimeError, match="ORIGIN_IMAGE"):
        module["validate_base"](bad, old, foundation())


@pytest.mark.parametrize(
    "fault", ["none", "extra_label", "extra_config", "empty_cmd", "volume", "env"]
)
def test_new_image_config_is_exact_except_three_label_values(module, policies, fault):
    _, new, _ = policies
    original = base(module)
    info = base(module)
    info.update(Id="sha256:" + "f" * 64, RepoTags=["maskgw-oracle9-w1-candidate:" + TASK])
    info["RootFS"]["Layers"].append("sha256:" + "e" * 64)
    info["Config"]["Labels"] = module["expected_labels"](original, TASK)
    if fault == "extra_label":
        info["Config"]["Labels"]["unexpected"] = "public"
    elif fault == "extra_config":
        info["Config"]["StopSignal"] = "SIGTERM"
    elif fault == "empty_cmd":
        info["Config"]["Cmd"] = []
    elif fault == "volume":
        info["Config"]["Volumes"] = {}
    elif fault == "env":
        info["Config"]["Env"].append("UNEXPECTED=public")
    if fault != "none":
        with pytest.raises(RuntimeError):
            module["validate_new_image"](
                info, original, new, foundation(), TASK, info["RepoTags"][0]
            )
    else:
        assert (
            module["validate_new_image"](
                info, original, new, foundation(), TASK, info["RepoTags"][0]
            )
            == info["Id"]
        )


@pytest.mark.parametrize("mode", ["install", "probe"])
def test_entire_create_command_measured_before_any_effect(module, policies, mode):
    _, new, _ = policies
    payload = (REPO / "deploy/oracle9_w1_update.py").read_bytes()
    command = module["native_command"](payload, mode, TASK, "0" * 64 if mode == "probe" else None)
    args, size = module["measured_create"](
        CLI,
        new,
        image=module["IMAGE"],
        name="maskgw-ol9-w1-" + TASK[:12] + "-" + mode,
        task=TASK,
        command=command,
        probe=mode == "probe",
    )
    assert 23000 < size["createprocess_chars"] < 26000 and size["margin_chars"] > 1500
    assert command == args[-len(command) :] and "--pull=never" in args
    assert "w1-inputs-" in command[-2] if mode == "install" else command[-1] == "0" * 64
    with pytest.raises(RuntimeError, match="CREATE_ARGV_LIMIT"):
        module["measured_create"](
            "C:\\" + "x" * 27000,
            new,
            image=module["IMAGE"],
            name="maskgw-ol9-w1-" + TASK[:12] + "-" + mode,
            task=TASK,
            command=command,
            probe=mode == "probe",
        )


def test_bootstrap_checks_decompressed_bytes_before_compiling(module):
    payload = (REPO / "deploy/oracle9_w1_update.py").read_bytes()
    command = module["native_command"](payload, "install", TASK)
    namespace: dict[str, Any] = {"__name__": "_public_payload_model"}
    exec(command[1], namespace)  # noqa: S102 - hash-qualified payload, explicitly non-main namespace
    assert "install" in namespace and namespace["_ORIGIN"] is None
    invalid = command[1].replace(repr(module["PAYLOAD_SHA"]), repr("0" * 64))
    with pytest.raises(RuntimeError, match="PAYLOAD_PIN"):
        exec(invalid, {"__name__": "_must_not_compile"})  # noqa: S102 - wrong-digest refusal before compile


@pytest.mark.parametrize("fault", ["payload", "task", "role", "attest"])
def test_command_builder_refuses_invalid_identity(module, fault):
    payload = (REPO / "deploy/oracle9_w1_update.py").read_bytes()
    with pytest.raises(RuntimeError):
        module["native_command"](
            payload + b"x" if fault == "payload" else payload,
            "unknown" if fault == "role" else "install",
            "bad" if fault == "task" else TASK,
            "bad" if fault == "attest" else None,
        )


def diff_model(module: Any) -> Any:
    before = json.loads(
        (REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json").read_bytes()
    )["installed_snapshot"]
    after = dict(before)
    lines = ["C " + p for p in sorted(module["ANCESTORS"])] + ["A " + module["ATTEST"]]
    for relative in sorted(module["ADDED"]):
        path = module["SITE"] + "/" + relative
        after[path.removeprefix(module["PREFIX"] + "/")] = {"kind": "file", "MODEL": True}
        lines.append("A " + path)
    lines.append("C " + module["DIST"] + "/RECORD")
    return before, after, lines


@pytest.mark.parametrize("opaque", [False, True])
def test_diff_two_declared_forms_with_or_without_opaque_directory(module, opaque):
    before, after, lines = diff_model(module)
    if opaque:
        lines.append("D " + module["APP"] + "/runtime")
    raw = ("\n".join(lines) + "\n").encode()
    assert module["validate_diff"](raw, before, after) == len(lines)


@pytest.mark.parametrize(
    "fault",
    [
        "stash",
        "input",
        "tmp",
        "opaque_file",
        "outside_delete",
        "traversal",
        "duplicate",
        "missing_guard",
        "missing_record",
        "missing_attest",
    ],
)
def test_diff_refuses_unplanned_changes_or_incomplete_evidence(module, fault):
    before, after, lines = diff_model(module)
    extra = {
        "stash": "A " + module["SITE"] + "/~askgw",
        "input": "A /opt/maskgw/w1-inputs-" + TASK,
        "tmp": "C /tmp",
        "opaque_file": "D " + module["APP"] + "/__init__.py",
        "outside_delete": "D /opt",
        "traversal": "A /opt/../escape",
    }
    if fault in extra:
        lines.append(extra[fault])
    elif fault == "duplicate":
        lines.append(lines[-1])
    elif fault == "missing_guard":
        lines = [s for s in lines if not s.endswith("/runtime/linux_guard.py")]
    elif fault == "missing_record":
        lines = [s for s in lines if not s.endswith("/RECORD")]
    else:
        lines = [s for s in lines if s != "A " + module["ATTEST"]]
    with pytest.raises(RuntimeError):
        module["validate_diff"](("\n".join(lines) + "\n").encode(), before, after)


def test_diff_rejects_same_path_twice_even_with_different_action(module):
    before, after, lines = diff_model(module)
    lines.append("A " + module["DIST"] + "/RECORD")
    with pytest.raises(RuntimeError, match="DIFF_FORMAT"):
        module["validate_diff"](("\n".join(lines) + "\n").encode(), before, after)
