"""Public cleanup adapter interoperability, no Docker/image/CLI or mutation."""

import hashlib
import runpy
from pathlib import Path
from typing import Any

import pytest

from tests.test_pg16_public_profile import CID, TASK, encoded, image_info

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_cleanup_policy.py"))


@pytest.fixture
def example(module: Any) -> Any:
    p = module["P"]
    intent = p["Intent"](TASK, p["admit_image"](encoded(image_info(p))))
    info = {
        "Id": CID,
        "Name": "/" + intent.name,
        "Image": p["IMAGE"],
        "Config": {
            "Image": p["IMAGE"],
            "Cmd": list(intent.command),
            "Entrypoint": list(p["ENTRY"]),
            "Labels": dict(intent.labels),
        },
    }
    return intent, info


def test_same_authoritative_identity_without_requiring_image_env_or_acceptance(module, example):
    intent, info = example
    assert module["P"]["identity"](info, intent, CID) == CID
    assert module["identity"](info, task=TASK, command=intent.command, cid=CID) == CID
    info["Config"]["Env"] = ["PGPASSWORD=fake-private-canary"]
    info["HostConfig"] = {"NetworkMode": "unexpected"}
    assert module["identity"](info, task=TASK, command=intent.command, cid=CID) == CID


@pytest.mark.parametrize(
    "field",
    ["cid", "name", "image", "command", "entry", "task-label", "source-label", "manifest-label"],
)
def test_alien_inspect_or_identity_never_passes_cleanup(module, example, field):
    intent, info = example
    if field == "cid":
        info["Id"] = "d" * 64
    elif field == "name":
        info["Name"] = "/unrelated"
    elif field == "image":
        info["Image"] = "sha256:" + "0" * 64
    elif field == "command":
        info["Config"]["Cmd"] = ["-ec", "different"]
    elif field == "entry":
        info["Config"]["Entrypoint"] = ["different"]
    else:
        key = {
            "task-label": "maskgw.task",
            "source-label": "maskgw.source-sha256",
            "manifest-label": "maskgw.manifest-sha256",
        }[field]
        info["Config"]["Labels"][key] = "wrong"
    with pytest.raises(RuntimeError, match=r"^PG16_PUBLIC_OWNERSHIP$") as caught:
        module["identity"](info, task=TASK, command=intent.command, cid=CID)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("bad", [None, "x" * 32, "a" * 31, False])
def test_bad_task_never_builds_a_cleanup_capture(module, example, bad):
    intent, info = example
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        module["identity"](info, task=bad, command=intent.command, cid=CID)


@pytest.mark.parametrize("bad", [None, [], ("-ec", "different"), ("-c", "different")])
def test_cleanup_command_cannot_be_an_arbitrary_shell_backend(module, example, bad):
    _, info = example
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        module["identity"](info, task=TASK, command=bad, cid=CID)


def test_live_source_unreadable_does_not_change_captured_cleanup_identity(
    module, example, monkeypatch
):
    intent, info = example

    def unreadable(_path):
        raise OSError("fake-private-canary")

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    assert module["identity"](info, task=TASK, command=intent.command, cid=CID) == CID


def test_corrupted_captured_source_is_refused_even_during_cleanup(module, example, monkeypatch):
    intent, info = example
    monkeypatch.setitem(module["identity"].__globals__, "PROFILE_RAW", b"changed")
    with pytest.raises(RuntimeError, match="SOURCE"):
        module["identity"](info, task=TASK, command=intent.command, cid=CID)


def test_extra_labels_do_not_block_owned_resource_cleanup(module, example):
    intent, info = example
    info["Config"]["Labels"]["unexpected"] = "public-only"
    assert module["identity"](info, task=TASK, command=intent.command, cid=CID) == CID
    assert hashlib.sha256(module["PROFILE_RAW"]).hexdigest() == module["PROFILE_SHA"]


@pytest.mark.parametrize("cid", [None, True, "c" * 63, "unrelated"])
def test_unknown_create_cid_never_falls_back_to_the_inspect_cid(module, example, cid):
    intent, info = example
    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        module["identity"](info, task=TASK, command=intent.command, cid=cid)


def test_command_elements_are_exact_strings_not_overloaded_subclasses(module, example):
    intent, info = example

    class Text(str):
        pass

    with pytest.raises(RuntimeError, match="OWNERSHIP"):
        module["identity"](info, task=TASK, command=("-ec", Text(intent.command[1])), cid=CID)
