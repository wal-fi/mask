"""Create/inspect diagnostic fakes. No native thread/process, Docker or secret."""

import ast
import asyncio
import hashlib
import json
import runpy
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_w1_bootstrap_t4_host import Engine

REPO = Path(__file__).resolve().parents[1]
TASK = "a" * 32


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_admission_run.py"))


@pytest.fixture
def bound(module: Any, tmp_path: Path) -> Any:
    state = {
        "task": TASK,
        "pins": dict(module["R"]["LIBRARIES"].values()),
        "host_sha256": module["HOST_SHA"],
        "entry_sha256": hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
        "diagnostic_pins": {module["CORE_RELATIVE"]: module["CORE_SHA"]},
    }
    host = module["DiagnosticHost"](tmp_path, state)
    state["create_measurements"] = {
        key: host.t4["policy"]["create_args"](str(module["R"]["CLI"]), intent)[1]
        for key, intent in host._intents.items()
    }
    engine = Engine(host)
    host.cli = engine.cli
    host.pins = lambda **_kw: None
    host._store = host.t4["watch"]["Store"](0.0)
    host._cleanup_lock = threading.Lock()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("diagnostic constructed transport")

    host.t4["channel"]["ManagedBootstrap"] = forbidden
    return host, engine


@pytest.fixture
def context(module: Any, bound: Any) -> Any:
    host, engine = bound
    events: list[str] = []
    stopped = asyncio.Event()
    tick = [0]

    async def heartbeat() -> None:
        while not host._heartbeat_stop and not stopped.is_set():
            await asyncio.sleep(0.01)

    def close() -> bool:
        assert module["join_ready"](host)
        events.append("join")
        stopped.set()
        return True

    async def supervise() -> None:
        events.append("supervision")
        host._monitor = SimpleNamespace(
            close=close,
            metadata=lambda: {"thread_joined": True, "fired": False},
            ack=threading.Event(),
        )
        host._heartbeat = host._task(heartbeat(), "fake-heartbeat")

    async def sample() -> Any:
        tick[0] += 10000
        return host.libs["core"]["Sample"](
            "134372287595000000", str(tick[0]), str(134373000000000000 + tick[0] * 10000)
        )

    async def app(action, **_kw):
        events.append(action)

    async def preflight():
        events.append("preflight")

    async def wait():
        return None

    async def processes(*_args, **_kw):
        return [{"pid": 123, "created": "134372987595123457", "name": "Docker Desktop"}]

    async def restore():
        assert host._monitor_joined
        events.append("restore")
        host.result["desktop_restored"] = True

    host.start_supervision, host.sample, host.check_app = supervise, sample, app
    host.preflight, host.wait_observation, host.processes = preflight, wait, processes
    host.restore_desktop = restore
    return module["Context"](host.root, host.state, host), engine, events, stopped


def test_five_overrides_and_closed_entry_differences(module):
    cls, base = module["DiagnosticHost"], module["H"]["Host"]
    assert {name for name in cls.__dict__ if callable(getattr(base, name, None))} == {
        "__init__",
        "pins",
        "inspect_own",
        "perform_b",
        "_case",
    }
    for name in (
        "create_own",
        "_collect",
        "cleanup_owned",
        "start_cycle",
        "save",
        "restore_desktop",
        "stop_supervision",
    ):
        assert getattr(cls, name) is getattr(base, name)
    old = ast.parse((REPO / "docs/poc/w1_bootstrap_t4_run.py").read_bytes())
    new = ast.parse(Path(module["__file__"]).read_bytes())
    old_nodes = {
        node.name: node
        for node in old.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    new_nodes = {
        node.name: deepcopy(node)
        for node in new.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert set(new_nodes) - set(old_nodes) == {"capture_core", "DiagnosticHost"}
    for name in (
        "need",
        "binding",
        "Context",
        "join_ready",
        "visible",
        "retain",
        "restore_budget",
        "drive",
    ):
        assert ast.dump(new_nodes[name]) == ast.dump(old_nodes[name])

    class Normalize(ast.NodeTransformer):
        def visit_Constant(self, node):
            values = {
                "maskgw-oracle9-admission-v1": "maskgw-oracle9-t4-v1",
                r"maskgw-oracle9-admission-20261028-[0-9a-f]{32}": (
                    r"maskgw-oracle9-t4-20261028-[0-9a-f]{32}"
                ),
                "MASKGW_ADMISSION_INVOKED_V1": "MASKGW_T4_INVOKED_V1",
                "admission_capture_complete": "t4_verified",
                "ORACLE9_ADMISSION_CAPTURED": "ORACLE9_T4_VERIFIED",
            }
            if isinstance(node.value, str) and node.value in values:
                return ast.Constant(values[node.value])
            return node

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == "DiagnosticHost":
                node.func = ast.Subscript(
                    ast.Name("H", ast.Load()), ast.Constant("Host"), ast.Load()
                )
            return self.generic_visit(node)

        def visit_Attribute(self, node):
            if node.attr == "_admission_reports":
                node.attr = "_cases"
            return self.generic_visit(node)

        def visit_Compare(self, node):
            if ast.unparse(node.left) == "len(host._admission_reports)":
                assert ast.unparse(node) == "len(host._admission_reports) == 2"
                node.comparators = [ast.Constant(7)]
            return self.generic_visit(node)

    admit = new_nodes["admit"]
    sets = [
        node
        for node in ast.walk(admit)
        if isinstance(node, ast.Set)
        and any(
            isinstance(item, ast.Constant) and item.value == "diagnostic_pins" for item in node.elts
        )
    ]
    assert len(sets) == 1
    sets[0].elts = [
        node
        for node in sets[0].elts
        if not (isinstance(node, ast.Constant) and node.value == "diagnostic_pins")
    ]
    pin_checks = [
        node
        for node in ast.walk(admit)
        if isinstance(node, ast.BoolOp)
        and any(
            isinstance(item, ast.Compare) and ast.unparse(item.left) == "state['diagnostic_pins']"
            for item in node.values
        )
    ]
    assert len(pin_checks) == 1
    values = pin_checks[0].values
    check = next(
        item
        for item in values
        if isinstance(item, ast.Compare) and ast.unparse(item.left) == "state['diagnostic_pins']"
    )
    assert ast.unparse(check) == "state['diagnostic_pins'] == {CORE_RELATIVE: CORE_SHA}"
    values.remove(check)
    category = new_nodes["category"]
    assert isinstance(category, ast.FunctionDef)
    assert ast.unparse(category.body[-1]) == "return CORE['closed_category'](error)"
    category.body[-1] = ast.Return(ast.Constant("FAILED"))
    for name in ("admit", "prepare", "category", "run"):
        assert ast.dump(Normalize().visit(new_nodes[name])) == ast.dump(old_nodes[name])


@pytest.mark.parametrize("stdin_once", [False, True])
def test_two_complete_capture_profiles_do_not_mean_transport_approved(module, context, stdin_once):
    value, engine, events, _ = context
    original = engine.row

    def row(case, cid):
        info = original(case, cid)
        info["Config"].update(StdinOnce=stdin_once, AttachStdin=True)
        return info

    engine.row = row
    assert asyncio.run(module["run"](value)) == 0
    host = value.host
    assert value.released and not host._owners and not engine.rows
    assert events.index("join") < events.index("restore")
    assert host.result["outcome"] == "ORACLE9_ADMISSION_CAPTURED"
    assert "t4_verified" not in host.result
    assert len(host._admission_reports) == len(host._admission_captures) == 2
    assert all(item["profile_accepted"] is (not stdin_once) for item in host._admission_reports)
    assert all(
        item["validator_category"] == ("CONFIG" if stdin_once else None)
        for item in host._admission_reports
    )
    assert host.result["cleanup_initial_raw_captured"] is False
    assert len(list(host.root.glob("checkpoint-*.json"))) == 12
    for role, index in (("normal", 0), ("retain", 1)):
        assert (
            host.root / (role + "-admission-inspect-0" + str(index) + ".json")
        ).read_bytes() == (host.root / (role + "-inspect-before.json")).read_bytes()
    assert all(
        event[1][0] not in ("start", "exec", "run") for event in engine.events if len(event) == 3
    )


def test_raw_is_local_before_publication_or_identity_and_no_overwrite(bound):
    host, _ = bound
    original = host._admission_fields["publication"]
    observed = []

    def publication(raw, *args, **kwargs):
        path = host.root / "normal-admission-inspect-00.json"
        assert path.read_bytes() == raw
        observed.append(True)
        return original(raw, *args, **kwargs)

    host._admission_fields["publication"] = publication
    asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    assert observed == [True]
    assert (host.root / "normal-inspect-before.json").read_bytes() == (
        host.root / "normal-admission-inspect-00.json"
    ).read_bytes()


def test_running_state_aborts_and_cleanup_observation_is_distinct(module, context):
    value, engine, _, _ = context
    original = engine.row

    def running(case, cid):
        info = original(case, cid)
        info["State"].update(Running=True, Pid=456)
        return info

    engine.row = running
    assert asyncio.run(module["run"](value)) == 1
    assert value.released and not engine.rows
    assert value.host.result["failure_category"] == "CREATE_RUNNING"
    assert len(value.host._admission_reports) == 1
    assert [item["phase"] for item in value.host._admission_captures] == ["admission", "cleanup"]


def test_private_env_stops_before_second_profile_and_never_appears_in_report(module, context):
    value, engine, _, _ = context
    original = engine.row
    canary = "fake-private-canary"

    def injected(case, cid):
        info = original(case, cid)
        info["Config"]["Env"].append("HTTPS_PROXY=http://u:" + canary + "@example.invalid")
        return info

    engine.row = injected
    assert asyncio.run(module["run"](value)) == 1
    host = value.host
    assert host.result["privacy_review_required"] is True and value.released
    assert len(host.records) == 1 and not engine.rows
    assert canary not in (host.root / "normal-admission-report.json").read_text()
    assert host._admission_captures[0]["publication"]["allowed"] is False
    # Local raw intentionally contains the fake; export is a separate pending gate.
    assert canary in (host.root / "normal-admission-inspect-00.json").read_text()


def test_collision_preserves_existing_raw_and_still_removes_owned_cid(module, context):
    value, engine, _, _ = context
    path = value.host.root / "normal-admission-inspect-00.json"
    path.write_bytes(b"preserve")
    assert asyncio.run(module["run"](value)) == 1
    assert value.released and not engine.rows and path.read_bytes() == b"preserve"
    assert value.host.result["failure_category"] == "INTERNAL"


def test_case_method_cannot_reach_transport(bound):
    host, _ = bound
    with pytest.raises(RuntimeError, match="DIAGNOSTIC_NO_TRANSPORT"):
        asyncio.run(host._case(host.t4["policy"]["Case"].NORMAL))


def test_malformed_raw_is_saved_before_parse(bound):
    host, engine = bound
    fake = engine.cli

    async def cli(label, *args, **kw):
        if args[0] == "inspect":
            return 0, b"malformed-public-canary"
        return await fake(label, *args, **kw)

    host.cli = cli
    with pytest.raises(ValueError):
        asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    assert (
        host.root / "normal-admission-inspect-00.json"
    ).read_bytes() == b"malformed-public-canary"


def test_create_uncertain_retains_loop_without_restore_or_retry(module, context):
    value, engine, events, stopped = context
    engine.fail_create = True

    async def run() -> None:
        task = asyncio.create_task(module["run"](value))
        try:
            for _ in range(100):
                if value.held:
                    break
                await asyncio.sleep(0.01)
            assert value.held and not value.released and not task.done()
            assert len(value.host.records) == 1
            assert value.host.records[0]["create_uncertain"]
            assert "restore" not in events and "join" not in events
        finally:
            stopped.set()
            for owned in value.host._host_tasks:
                if not owned.done():
                    owned.cancel()
            for _ in range(5):
                if task.done():
                    break
                task.cancel()
                await asyncio.sleep(0.01)
            assert task.done()
            await asyncio.gather(task, *value.host._host_tasks, return_exceptions=True)

    asyncio.run(run())


def test_new_pins_extend_parent_and_live_source_change_does_not_block_cleanup(
    module, bound, monkeypatch
):
    host, _ = bound
    calls = []

    def parent(_self, cleanup=False):
        calls.append(("parent", cleanup))

    def pinned(path, _digest, *_args):
        calls.append((str(path), False))
        if Path(path) == REPO / module["CORE_RELATIVE"]:
            raise RuntimeError("SOURCE_PIN")
        return b"public"

    monkeypatch.setattr(module["H"]["Host"], "pins", parent)
    monkeypatch.setitem(module["R"], "pinned", pinned)
    monkeypatch.setitem(module["R"], "regular", lambda *_args: b"{}")
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        module["DiagnosticHost"].pins(host)
    assert calls[0] == ("parent", False)
    calls.clear()
    module["DiagnosticHost"].pins(host, cleanup=True)
    assert calls == [("parent", True)]
    host._admission_raw = b"changed-memory"
    with pytest.raises(RuntimeError, match="CAPTURE"):
        module["DiagnosticHost"].pins(host, cleanup=True)


def test_proxy_config_refused_without_printing_values(module, bound, monkeypatch):
    host, _ = bound
    monkeypatch.setattr(module["H"]["Host"], "pins", lambda _self, **_kw: None)
    monkeypatch.setitem(module["R"], "pinned", lambda *_args: b"public")
    monkeypatch.setitem(
        module["R"],
        "regular",
        lambda *_args: b'{"proxies":{"default":{"httpsProxy":"fake-private-value"}}}',
    )
    with pytest.raises(RuntimeError, match="CONFIG") as caught:
        module["DiagnosticHost"].pins(host)
    assert "fake-private-value" not in str(caught.value)


@pytest.fixture
def fresh(module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    root = tmp_path / "AppData/Local/Temp" / ("maskgw-oracle9-admission-20261028-" + "b" * 32)
    root.mkdir(parents=True)
    prep = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_prepare.py"))
    state = prep["state_for"](TASK)
    state.update(
        kind="maskgw-oracle9-admission-v1",
        entry_sha256=hashlib.sha256(Path(module["__file__"]).read_bytes()).hexdigest(),
        diagnostic_pins={module["CORE_RELATIVE"]: module["CORE_SHA"]},
    )
    monkeypatch.setitem(module["R"], "HOME", tmp_path)
    monkeypatch.setitem(
        module["admit"].__globals__,
        "sys",
        SimpleNamespace(
            platform="win32",
            version_info=(3, 11, 3),
            flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0),
        ),
    )
    (root / "attempt.json").write_bytes(module["R"]["json_bytes"](state))
    return root, state


def test_own_fresh_kind_accepts_and_t4_cannot_reuse_it(module, fresh, monkeypatch):
    root, state = fresh
    assert module["admit"](root) == state
    prior = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_t4_run.py"))
    monkeypatch.setitem(prior["R"], "HOME", root.parents[3])
    monkeypatch.setitem(prior["admit"].__globals__, "sys", module["admit"].__globals__["sys"])
    with pytest.raises(RuntimeError, match="ROOT"):
        prior["admit"](root)
    state["kind"] = "maskgw-oracle9-t4-v1"
    (root / "attempt.json").write_bytes(module["R"]["json_bytes"](state))
    with pytest.raises(RuntimeError, match="STATE_VALUES"):
        module["admit"](root)


@pytest.mark.parametrize("fault", ["diagnostic_pins", "invoked", "unknown-field"])
def test_closed_state_refuses_reuse_pin_or_added_fields(module, fresh, fault):
    root, state = fresh
    if fault == "diagnostic_pins":
        state["diagnostic_pins"] = {}
    elif fault == "invoked":
        state["invoked"] = True
    else:
        state["unknown-field"] = "public"
    (root / "attempt.json").write_bytes(module["R"]["json_bytes"](state))
    with pytest.raises(RuntimeError, match=r"STATE_SCHEMA|STATE_VALUES"):
        module["admit"](root)


@pytest.mark.parametrize("elapsed", [4.0, -1.0])
def test_capture_work_over_budget_reproves_without_discarding_raw(
    module, bound, monkeypatch, elapsed
):
    host, _ = bound
    now = [0.0]
    monkeypatch.setitem(
        module["DiagnosticHost"].inspect_own.__globals__,
        "time",
        SimpleNamespace(monotonic=lambda: now[0]),
    )
    original = host._admission_fields["fields"]

    def delayed(*args):
        result = original(*args)
        now[0] = elapsed
        return result

    host._admission_fields["fields"] = delayed
    with pytest.raises(RuntimeError, match="REPORT_FACTS"):
        asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    assert (host.root / "normal-admission-inspect-00.json").is_file()
    assert not (host.root / "normal-inspect-before.json").exists()


@pytest.mark.parametrize("failure", ["key-error", "disagreement"])
def test_report_survives_validator_exception_or_predicate_disagreement(bound, failure):
    host, _ = bound
    if failure == "key-error":

        def validator(*_args):
            raise KeyError("fake-private-value")

        host.t4["policy"]["validate_container"] = validator
    else:
        original = host._admission_fields["fields"]

        def inconsistent(*args):
            result = original(*args)
            result["profile_predicates_match"] = False
            return result

        host._admission_fields["fields"] = inconsistent
    with pytest.raises(RuntimeError, match=r"INTERNAL|REPORT_FACTS"):
        asyncio.run(host.create_own(host.t4["policy"]["Case"].NORMAL))
    path = host.root / "normal-admission-report.json"
    assert path.is_file()
    saved = path.read_text()
    assert "fake-private-value" not in saved
    metadata = json.loads(saved)
    assert metadata["validator_completed"] is True
    assert metadata["predicate_agreement"] is False
    assert metadata["profile_accepted"] is False
    assert metadata["validator_category"] == ("INTERNAL" if failure == "key-error" else None)
    assert host._admission_reports == []
