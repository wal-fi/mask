"""S1 export integration using fake-controller artifacts only. No native effects."""

import asyncio
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

from tests.test_w1_bootstrap_t4_v2_host import bound as runner_bound
from tests.test_w1_bootstrap_t4_v2_host import module as runner_module
from tests.test_w1_bootstrap_t4_v2_run import context as runner_context
from tests.test_w1_bootstrap_t4_v2_run import entry  # noqa: F401 - pytest fixture

REPO = Path(__file__).resolve().parents[1]
module = runner_module
bound = runner_bound
context = runner_context


@pytest.fixture
def exporter() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_v2_export.py"))


@pytest.fixture
def source(  # noqa: PLR0913, PLR0917 - explicit fixture dependencies
    exporter: Any,
    module: Any,
    context: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: Any,
) -> Any:
    value, engine, _, _ = context
    private = getattr(request, "param", False)
    if private:
        original = engine.row

        def row(case, cid):
            info = original(case, cid)
            info["Config"]["Env"].append("HTTPS_PROXY=http://u:fake-private-canary@example.invalid")
            return info

        engine.row = row
    code = asyncio.run(module["run"](value))
    assert value.released and not engine.rows
    source_files = tuple(value.root.iterdir())
    home = tmp_path / "source"
    home.mkdir()
    root = home / ("maskgw-oracle9-t4-v2-20261029-" + "b" * 32)
    root.mkdir()
    for item in source_files:
        (root / item.name).write_bytes(item.read_bytes())
    if not private:
        retained = (root / "retain-cli-reaped-cid-alive.json").read_bytes()
        result_path = root / "result.json"
        result = json.loads(result_path.read_bytes())
        result["commands"].append(
            {
                "label": "inspect-cleanup-retain",
                "exit": 0,
                "bytes": len(retained),
                "sha256": hashlib.sha256(retained).hexdigest(),
            }
        )
        result_path.write_text(json.dumps(result), encoding="utf-8")
    prep = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_v2_prepare.py"))
    state = prep["state_for"](value.state["task"])
    state.update(
        kind="maskgw-oracle9-t4-v2",
        phase=value.state["phase"],
        invoked=True,
        entry_sha256=exporter["RUN_SHA"],
        transport_pins=module["TRANSPORT_PINS"],
    )
    (root / "attempt.json").write_bytes(module["R"]["json_bytes"](state))
    image = json.loads((REPO / exporter["IMAGE_RECORD"]).read_bytes())[0]
    (root / "candidate-image.json").write_bytes(module["R"]["json_bytes"](image))
    output = tmp_path / "evidence"
    output.mkdir()
    monkeypatch.setitem(exporter["export"].__globals__, "TEMP_ROOT", home)
    monkeypatch.setitem(exporter["export"].__globals__, "OUTPUT_PARENT", output)
    destination = output / ("oracle9-t4-v2-run-20261029-" + state["task"][:12])
    return root, destination, code


def test_complete_public_snapshot_copies_every_registered_alias_and_live_retain(exporter, source):
    root, destination, code = source
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 0
    raw_names = [item.name for item in root.iterdir() if exporter["raw_role"](item.name)]
    assert len(raw_names) == 20
    for name in raw_names:
        assert (destination / name).read_bytes() == (root / name).read_bytes()
    manifest = (destination / "transport.json").read_bytes()
    assert hashlib.sha256(manifest).hexdigest() == result["transport_sha256"]
    assert json.loads(manifest)["source_unchanged"] is True


@pytest.mark.parametrize("source", [True], indirect=True)
def test_proxy_raw_and_inherited_copy_stay_local_without_value_in_any_export(exporter, source):
    root, destination, code = source
    assert code == 1
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 1
    assert not (destination / "normal-transport-inspect-00.json").exists()
    assert not (destination / "normal-inspect-before.json").exists()
    assert b"fake-private-canary" in (root / "normal-transport-inspect-00.json").read_bytes()
    assert all(b"fake-private-canary" not in item.read_bytes() for item in destination.iterdir())


@pytest.mark.parametrize("source", [True], indirect=True)
def test_export_recomputes_guard_instead_of_trusting_recorded_allowed(exporter, source):
    root, destination, code = source
    path = root / "transport-captures.json"
    captures = json.loads(path.read_bytes())
    for item in captures:
        item["publication"]["allowed"] = True
    path.write_text(json.dumps(captures), encoding="utf-8")
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 1
    assert not (destination / "normal-inspect-before.json").exists()


def test_unregistered_matching_raw_name_is_default_denied(exporter, source):
    root, destination, code = source
    name = "normal-transport-inspect-99.json"
    (root / name).write_bytes(b"fake-private-canary")
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 1 and not (destination / name).exists()
    manifest = json.loads((destination / "transport.json").read_bytes())
    record = next(item for item in manifest["files"] if item["name"] == name)
    assert record["publication"]["categories"] == ["UNREGISTERED_RAW"]


@pytest.mark.parametrize(
    "fault", ["capture-hash", "inherited-alias", "image", "result", "state", "extra-file"]
)
def test_integrity_or_shape_failure_happens_before_destination_creation(exporter, source, fault):
    root, destination, code = source
    if fault == "capture-hash":
        path = root / "transport-captures.json"
        value = json.loads(path.read_bytes())
        value[0]["sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
    elif fault == "inherited-alias":
        (root / "normal-inspect-before.json").write_bytes(b"changed")
    elif fault == "image":
        (root / "candidate-image.json").write_bytes(b"{}")
    elif fault == "result":
        path = root / "result.json"
        value = json.loads(path.read_bytes())
        value["owned_cleanup"] = False
        path.write_text(json.dumps(value), encoding="utf-8")
    elif fault == "state":
        path = root / "attempt.json"
        value = json.loads(path.read_bytes())
        value["kind"] = "maskgw-oracle9-admission-v1"
        path.write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())
    else:
        (root / "unexpected.json").write_bytes(b"fake-private-canary")
    with pytest.raises(RuntimeError):
        exporter["export"](root, destination, code)
    assert not destination.exists()


def test_reported_exit_must_match_terminal_state(exporter, source):
    root, destination, _ = source
    with pytest.raises(RuntimeError, match="EXIT"):
        exporter["export"](root, destination, 1)
    assert not destination.exists()


def test_existing_destination_is_never_overwritten(exporter, source):
    root, destination, code = source
    destination.mkdir()
    preserve = destination / "preserve"
    preserve.write_bytes(b"leave")
    with pytest.raises(FileExistsError):
        exporter["export"](root, destination, code)
    assert {item.name for item in destination.iterdir()} == {"preserve"}
    assert preserve.read_bytes() == b"leave"


def test_cleanup_raw_alias_gets_the_same_publication_guard(exporter, source):
    root, destination, code = source
    original = json.loads((root / "normal-transport-inspect-00.json").read_bytes())
    original[0]["State"]["UnexpectedAuth"] = "fake-private-canary"
    raw = json.dumps(original).encode()
    name = "normal-transport-inspect-98.json"
    (root / name).write_bytes(raw)
    path = root / "transport-captures.json"
    captures = json.loads(path.read_bytes())
    captures.append(
        {
            "role": "normal",
            "phase": "cleanup",
            "raw_name": name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "publication": {"allowed": True},
        }
    )
    path.write_text(json.dumps(captures), encoding="utf-8")
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 1 and not (destination / name).exists()
    assert all(b"fake-private-canary" not in item.read_bytes() for item in destination.iterdir())


def test_source_change_during_write_leaves_no_complete_transport(exporter, source, monkeypatch):
    root, destination, code = source
    original = exporter["os"].fsync
    changed: list[bool] = []

    def sync(fd):
        original(fd)
        if not changed:
            changed.append(True)
            with (root / "cycle.json").open("ab") as stream:
                stream.write(b" ")

    monkeypatch.setattr(exporter["os"], "fsync", sync)
    with pytest.raises(RuntimeError, match="SOURCE_CHANGED"):
        exporter["export"](root, destination, code)
    assert destination.exists() and not (destination / "transport.json").exists()


@pytest.mark.parametrize("name", ["version.json", "cases.json"])
def test_metadata_with_private_keys_is_withheld_too(exporter, source, name):
    root, destination, code = source
    path = root / name
    value = json.loads(path.read_bytes()) if path.exists() else {}
    if isinstance(value, list):
        value[0]["UnexpectedAuth"] = "fake-private-canary"
    else:
        value["HTTPProxy"] = "fake-private-canary"
    path.write_text(json.dumps(value), encoding="utf-8")
    result = exporter["export"](root, destination, code)
    assert result["withheld_count"] == 1
    assert not (destination / name).exists()
    assert all(b"fake-private-canary" not in item.read_bytes() for item in destination.iterdir())


@pytest.mark.parametrize("fault", ["no-command", "wrong-hash", "wrong-cid", "private-key"])
def test_live_retain_needs_its_own_command_binding_and_s1(exporter, source, fault):
    root, destination, code = source
    path = root / "retain-cli-reaped-cid-alive.json"
    original = path.read_bytes()
    assert original != (root / "retain-inspect-before.json").read_bytes()
    result_path = root / "result.json"
    result = json.loads(result_path.read_bytes())
    row = result["commands"][0]
    if fault == "no-command":
        result["commands"] = []
    elif fault == "wrong-hash":
        row["sha256"] = "0" * 64
    else:
        value = json.loads(original)
        if fault == "wrong-cid":
            value[0]["Id"] = "d" * 64
        else:
            value[0]["State"]["ProxyAuth"] = "fake-private-canary"
        raw = json.dumps(value).encode()
        path.write_bytes(raw)
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    result_path.write_text(json.dumps(result), encoding="utf-8")
    exported = exporter["export"](root, destination, code)
    assert exported["withheld_count"] == 1 and not (destination / path.name).exists()
    assert all(b"fake-private-canary" not in item.read_bytes() for item in destination.iterdir())
