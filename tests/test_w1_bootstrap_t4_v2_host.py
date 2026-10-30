"""Measured transport host fakes. No native process/thread/Docker."""

import ast
import asyncio
import hashlib
import json
import runpy
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_w1_bootstrap_t4_host import Engine as OriginalEngine
from tests.test_w1_bootstrap_t4_host import Owner

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_v2_run.py"))


class Engine(OriginalEngine):
    def row(self, case: Any, cid: str) -> Any:
        value = super().row(case, cid)
        value["Config"]["StdinOnce"] = True
        return value


@pytest.fixture
def bound(module: Any, tmp_path: Path) -> Any:
    state = {
        "task": TASK,
        "pins": dict(module["R"]["LIBRARIES"].values()),
        "host_sha256": module["HOST_SHA"],
        "entry_sha256": hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
        "transport_pins": module["TRANSPORT_PINS"],
    }
    host = module["TransportHost"](tmp_path, state)
    state["create_measurements"] = {
        key: host.t4["policy"]["create_args"](str(module["R"]["CLI"]), intent)[1]
        for key, intent in host._intents.items()
    }
    engine = Engine(host)
    host.cli = engine.cli
    host.pins = lambda **_kw: None
    host._store = host.t4["watch"]["Store"](0.0)
    host._cleanup_lock = threading.Lock()
    host.t4["identity"]["capture"] = lambda process: (
        None if process is None else host.t4["identity"]["Birth"](123, 134375857978266391)
    )
    host.t4["channel"]["ManagedBootstrap"] = lambda target: Owner(host, engine, target)
    return host, engine


def test_exact_four_overrides_and_all_other_methods_are_original_objects(module):
    cls, base = module["TransportHost"], module["H"]["Host"]
    assert {key for key in cls.__dict__ if callable(getattr(base, key, None))} == {
        "__init__",
        "pins",
        "inspect_own",
        "_owned_inspect",
    }
    for name in dir(base):
        if (
            callable(getattr(base, name))
            and name not in cls.__dict__
            and name not in ("__init_subclass__", "__subclasshook__")
        ):
            assert getattr(cls, name) is getattr(base, name)
    assert (
        hashlib.sha256((REPO / module["HOST_RELATIVE"]).read_bytes()).hexdigest()
        == module["HOST_SHA"]
    )


def test_driver_join_retention_and_restore_are_ast_identical(module):
    before = ast.parse((REPO / "docs/poc/w1_bootstrap_t4_run.py").read_bytes())
    after = ast.parse(Path(module["__file__"]).read_bytes())
    for name in ("binding", "join_ready", "visible", "retain", "restore_budget", "drive"):
        original = next(n for n in before.body if getattr(n, "name", None) == name)
        current = next(n for n in after.body if getattr(n, "name", None) == name)
        assert ast.dump(current) == ast.dump(original)


def test_seven_case_matrix_still_proves_collection_and_live_retain(bound):
    host, engine = bound

    async def run() -> None:
        host.cycle = SimpleNamespace(phase=host.libs["core"]["Phase"].B_CONSUMED)
        await host.perform_b()
        await host.cleanup_owned()
        host._monitor_joined = True
        host.assert_released()

    asyncio.run(run())
    assert host.result["t4_verified"] is True and not engine.rows
    assert len(host._cases) == 7 and all(record["removed"] for record in host.records)
    captures = json.loads((host.root / "transport-captures.json").read_bytes())
    assert {row["role"] for row in captures} == {case.value for case in host.t4["policy"]["Case"]}
    assert all(row["publication"]["allowed"] and row["validator_completed"] for row in captures)
    assert (host.root / "retain-cli-reaped-cid-alive.json").is_file()
    assert host.result["cleanup_initial_raw_captured"] is False


@pytest.mark.parametrize("fault", ["stdin", "publication", "malformed", "ownership"])
def test_raw_and_category_survive_admission_failure_before_any_start(bound, fault):
    host, engine = bound
    original = engine.row

    def row(case, cid):
        value = original(case, cid)
        if fault == "stdin":
            value["Config"]["StdinOnce"] = False
        if fault == "publication":
            value["State"]["nested"] = {"ProxyAuth": "fake-private"}
        if fault == "ownership":
            value["Config"]["Labels"] = {}
        return value

    engine.row = row
    original_cli = engine.cli

    async def cli(label, *args, **kw):
        if fault == "malformed" and args[0] == "inspect":
            return 0, b"not-json"
        return await original_cli(label, *args, **kw)

    host.cli = cli
    with pytest.raises((RuntimeError, ValueError)):
        asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    captures = json.loads((host.root / "transport-captures.json").read_bytes())
    capture = captures[0]
    raw = (host.root / capture["raw_name"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == capture["sha256"] and len(raw) == capture["bytes"]
    assert capture["validator_completed"] is True
    assert (
        capture["validator_category"]
        == {
            "stdin": "CONFIG",
            "publication": None,
            "malformed": "INTERNAL",
            "ownership": "OWNERSHIP",
        }[fault]
    )
    assert not host._owners and not any(event[0] == "start" for event in engine.events)
    if fault in ("stdin", "publication"):
        asyncio.run(host.cleanup_owned())
        assert not engine.rows and host.result["owned_cleanup"] is True


def test_factory_is_exact_captured_namespace_without_mutation(bound):
    host, _ = bound
    policy = host.t4["policy"]
    before = dict(policy)
    actual = host._transport["validate_container"]
    seen = []

    def validator(info, intent, factory):
        assert factory is policy
        seen.append(factory)
        return actual(info, intent, factory)

    host._transport["validate_container"] = validator
    asyncio.run(host.create_own(policy["Case"].NORMAL))
    assert seen == [policy] and policy.keys() == before.keys()
    assert all(policy[key] is value for key, value in before.items())


def test_cleanup_ignores_changed_profile_but_acceptance_refuses_it(bound):
    host, engine = bound
    record = asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))

    def refuse(*_args):
        raise RuntimeError("SOURCE_PIN")

    host._transport["validate_container"] = refuse
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        asyncio.run(host.inspect_own(record))
    asyncio.run(host.cleanup_owned())
    assert not engine.rows and host.result["owned_cleanup"] is True


def test_new_pins_extend_parent_first_and_cleanup_uses_captured_bytes(module, bound, monkeypatch):
    host, _ = bound
    calls = []

    def parent(_self, cleanup=False):
        calls.append(("parent", cleanup))

    def pinned(path, _digest, *_args):
        calls.append((str(path), False))
        if Path(path) == REPO / module["PROFILE_RELATIVE"]:
            raise RuntimeError("SOURCE_PIN")
        return b"public"

    monkeypatch.setattr(module["H"]["Host"], "pins", parent)
    monkeypatch.setitem(module["R"], "pinned", pinned)
    monkeypatch.setitem(module["R"], "regular", lambda *_args: b"{}")
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        module["TransportHost"].pins(host)
    assert calls[0] == ("parent", False)
    calls.clear()
    module["TransportHost"].pins(host, cleanup=True)
    assert calls == [("parent", True)]
    host._transport_raw = b"changed"
    with pytest.raises(RuntimeError, match="CAPTURE"):
        module["TransportHost"].pins(host, cleanup=True)


def test_proxy_configuration_stops_before_any_case(module, bound, monkeypatch):
    host, _ = bound
    monkeypatch.setattr(module["H"]["Host"], "pins", lambda _self, **_kw: None)
    monkeypatch.setitem(module["R"], "pinned", lambda *_args: b"public")
    monkeypatch.setitem(
        module["R"], "regular", lambda *_args: b'{"proxies":{"default":"fake-private"}}'
    )
    with pytest.raises(RuntimeError, match="CONFIG"):
        module["TransportHost"].pins(host)
    assert not host.records and not host._owners
