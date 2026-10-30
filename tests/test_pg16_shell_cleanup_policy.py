"""Ownership adapter fakes only; no native CLI, cleanup, admission or release."""

import hashlib
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.test_pg16_public_profile import CID, TASK, encoded, image_info

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_cleanup_policy.py"))


@pytest.fixture
def example(module: Any) -> Any:
    profile = module["P"]
    image = profile["admit_image"](encoded(image_info(profile["P"])))
    intent = profile["Intent"](TASK, image, profile["R"]["Case"].BINARY)
    info = {
        "Id": CID,
        "Name": "/" + intent.name,
        "Image": profile["IMAGE"],
        "Config": {
            "Image": profile["IMAGE"],
            "Cmd": list(intent.command),
            "Entrypoint": list(profile["ENTRY"]),
            "Labels": dict(intent.labels),
        },
    }
    return intent, info


def check(module: Any, intent: Any, info: Any, **changes: Any) -> Any:
    args = {"task": TASK, "case": "binary", "command": intent.command, "cid": CID}
    args.update(changes)
    return module["identity"](info, **args)


def test_all23_case_bindings_use_captured_profile_without_environment_or_admission(module):
    profile = module["P"]
    assert len(profile["R"]["Case"]) == 23
    image = profile["admit_image"](encoded(image_info(profile["P"])))
    for case in profile["R"]["Case"]:
        intent = profile["Intent"](TASK, image, case)
        info = {
            "Id": CID,
            "Name": "/" + intent.name,
            "Image": profile["IMAGE"],
            "Config": {
                "Image": profile["IMAGE"],
                "Cmd": list(intent.command),
                "Entrypoint": list(profile["ENTRY"]),
                "Labels": dict(intent.labels),
            },
        }
        assert check(module, intent, info, case=case.value) == CID
        with pytest.raises(profile["ProbeError"]):
            profile["validate_container"](info, intent, CID)


def test_refused_profile_secret_env_and_extra_labels_keep_owned_identity(module, example):
    intent, info = example
    info["Config"]["Env"] = ["PGPASSWORD=public-canary-not-a-real-secret"]
    info["Config"]["StdinOnce"] = False
    info["HostConfig"] = {"NetworkMode": "unexpected"}
    info["Config"]["Labels"]["unknown"] = "public-canary"
    assert check(module, intent, info) == CID


@pytest.mark.parametrize(
    "field",
    [
        "cid",
        "name",
        "image",
        "config-image",
        "command",
        "entry",
        "task-label",
        "source-label",
        "manifest-label",
    ],
)
def test_alien_fields_fail_closed_without_error_chain(module, example, field):
    intent, info = example
    if field == "cid":
        info["Id"] = "d" * 64
    elif field == "name":
        info["Name"] = "/maskgw-ol9-pg16-admit-" + TASK[:12]
    elif field == "image":
        info["Image"] = "sha256:" + "0" * 64
    elif field == "config-image":
        info["Config"]["Image"] = "sha256:" + "0" * 64
    elif field == "command":
        info["Config"]["Cmd"] = ["-ec", "unknown"]
    elif field == "entry":
        info["Config"]["Entrypoint"] = ["unknown"]
    else:
        key = {
            "task-label": "maskgw.task",
            "source-label": "maskgw.source-sha256",
            "manifest-label": "maskgw.manifest-sha256",
        }[field]
        info["Config"]["Labels"][key] = "wrong"
    with pytest.raises(RuntimeError, match=r"^PG16_READER_OWNERSHIP$") as caught:
        check(module, intent, info)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize(
    "changes",
    [
        {"task": None},
        {"task": "A" * 32},
        {"task": "b" * 32},
        {"case": "one"},
        {"case": "unknown-public-marker"},
        {"case": False},
        {"command": ["-ec", "unknown"]},
        {"command": ("-ec", "unknown")},
        {"cid": None},
        {"cid": True},
        {"cid": "c" * 63},
    ],
)
def test_untrusted_caller_never_selects_arbitrary_case_backend_or_cid(module, example, changes):
    intent, info = example
    with pytest.raises(RuntimeError, match=r"^PG16_READER_OWNERSHIP$") as caught:
        check(module, intent, info, **changes)
    assert caught.value.__context__ is None and "public-marker" not in str(caught.value)


def test_case_enum_and_string_subclass_are_refused_not_coerced(module, example):
    intent, info = example

    class Text(str):
        pass

    for case in (module["P"]["R"]["Case"].BINARY, Text("binary")):
        with pytest.raises(RuntimeError, match="OWNERSHIP"):
            check(module, intent, info, case=case)
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        check(module, intent, info, command=("-ec", Text(intent.command[1])))


@pytest.mark.parametrize("field", ["id", "command", "label"])
@pytest.mark.parametrize("mode", ["true", "raise"])
def test_overloaded_equality_never_runs_or_forces_false_ownership(module, example, field, mode):
    intent, info = example
    calls = []

    class Text(str):
        __hash__ = str.__hash__

        def __eq__(self, _other: Any) -> bool:
            calls.append(True)
            if mode == "raise":
                raise OSError("public-canary-private-detail")
            return True

    class Sequence(list[Any]):
        __hash__ = None

        def __eq__(self, _other: Any) -> bool:
            calls.append(True)
            return True

    if field == "id":
        info["Id"] = Text("wrong")
    elif field == "command":
        info["Config"]["Cmd"] = Sequence(["wrong"])
    else:
        info["Config"]["Labels"]["maskgw.task"] = Text("wrong")
    with pytest.raises(RuntimeError, match="OWNERSHIP") as caught:
        check(module, intent, info)
    assert not calls and caught.value.__context__ is None


def test_live_source_is_never_reread_during_cleanup(module, example, monkeypatch):
    intent, info = example

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("do-not-read-live-source")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert check(module, intent, info) == CID


@pytest.mark.parametrize("raw", [b"changed", None, "not-bytes"])
def test_captured_source_corruption_is_closed_source_category(module, example, monkeypatch, raw):
    intent, info = example
    monkeypatch.setitem(module["identity"].__globals__, "PROFILE_RAW", raw)
    with pytest.raises(RuntimeError, match=r"^PG16_READER_SOURCE$"):
        check(module, intent, info)


def test_nested_capture_exec_error_is_mapped_without_raw_context(module, monkeypatch):
    def rejected(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("raw-nested-source-detail")

    monkeypatch.setitem(module["capture"].__globals__, "exec", rejected)
    with pytest.raises(RuntimeError, match=r"^PG16_READER_SOURCE$") as caught:
        module["capture"]()
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_local_intent_uses_reconstructed_command_and_is_never_returned(
    module, example, monkeypatch
):
    intent, info = example
    original = module["P"]["identity"]
    captured = []

    def observe(value: Any, binding: Any, cid: str) -> Any:
        captured.append(binding)
        assert binding.image is None and binding.case.value == "binary"
        assert binding.core_sha256 == module["P"]["R"]["CORE_SHA"]
        assert binding.command == intent.command and binding.command is not intent.command
        return original(value, binding, cid)

    monkeypatch.setitem(module["P"], "identity", observe)
    assert check(module, intent, info) == CID and len(captured) == 1


def test_interrupt_is_never_absorbed_as_identity_success(module, example, monkeypatch):
    intent, info = example

    def interrupt(*_args: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setitem(module["P"], "identity", interrupt)
    with pytest.raises(KeyboardInterrupt):
        check(module, intent, info)


def test_import_build_and_identity_never_spawn_or_write(module, example, monkeypatch):
    assert hashlib.sha256(module["PROFILE_RAW"]).hexdigest() == module["PROFILE_SHA"]

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("adapter attempted native effect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    loaded = runpy.run_path(str(REPO / "docs/poc/pg16_shell_cleanup_policy.py"))
    # Different captured namespaces are intentional: only primitive expected args cross.
    intent, info = example
    assert check(loaded, intent, info) == CID
