"""Import producer/collector with synthetic modules/events; no native product imports."""

from __future__ import annotations

import copy
from pathlib import PurePosixPath
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import PROBE, load

C = load("loaded_memory_collect")
P = load("loaded_memory_protocol")
VM = {"size": 100 << 20, "peak": 108 << 20, "rss": 20 << 20, "threads": 1}
FDS = {"fds": [0, 1, 2, 9], "proc_children_available": True}
NATIVE = {root: [root + "._native"] for root in PROBE.NATIVE_ROOTS}


@pytest.fixture(autouse=True)
def linux_path_semantics(monkeypatch):
    class VirtualPath(PurePosixPath):
        def resolve(self):
            return self

    monkeypatch.setattr(PROBE, "Path", VirtualPath)


def events() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [
        {"phase": "baseline", "row": ["sys", "stdlib", "builtin-or-frozen"]}
    ]
    for stage in range(3):
        result.append({"phase": "start", "stage": stage})
        if stage == 0:
            for root, names in NATIVE.items():
                result.append(
                    {
                        "phase": "module",
                        "stage": stage,
                        "row": [names[0], root, "installed/" + root + "/native.so"],
                    }
                )
        result.append({"phase": "end", "stage": stage, "vm": dict(VM), "fds": copy.deepcopy(FDS)})
    result.append({"phase": "verified", "native": copy.deepcopy(NATIVE), "psycopg_impl": "binary"})
    return result


def consumed(stream: Any = None) -> Any:
    state = C.ImportCollector(PROBE)
    for event in events() if stream is None else stream:
        state.feed(event)
    return state


def test_complete_collector_snapshot_digest_and_no_commands():
    state = consumed()
    rows = state.snapshot()
    assert len(rows) == 5
    assert len(P.inventory_digest(rows, PROBE.validate_inventory)) == 64
    rows[0][1][0] = "tampered"
    assert state.snapshot()[0][1][0] == "sys"
    assert not hasattr(state, "send")


@pytest.mark.parametrize("count", range(12))
def test_incomplete_stream_never_exposes_snapshot(count):
    stream = events()
    if count >= len(stream):
        return
    state = consumed(stream[:count])
    with pytest.raises(C.CollectFault):
        state.snapshot()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda e: e[1].update(stage=True),
        lambda e: e[2].update(stage=2),
        lambda e: e[0].update(extra=1),
        lambda e: e.insert(1, e[0]),
        lambda e: e[6]["fds"]["fds"].remove(9),
        lambda e: e[6]["vm"].update(threads=2),
        lambda e: e[-1].update(psycopg_impl="python"),
        lambda e: e[-1]["native"].update(yaml=[]),
        lambda e: e[-1]["native"].update(yaml=["not.audited"]),
        lambda e: e[2]["row"].__setitem__(2, "installed/pglast/native.py"),
        lambda e: e.pop(1),
        lambda e: e.append({"phase": "verified"}),
        lambda e: e.insert(2, {"phase": "loaded", "vm": VM, "limits": [-1, -1]}),
    ],
)
def test_forged_sequence_terminal_no_snapshot_or_raw_chain(mutation):
    stream = events()
    mutation(stream)
    state = C.ImportCollector(PROBE)
    with pytest.raises(C.CollectFault) as caught:
        for event in stream:
            state.feed(event)
    assert caught.value.__context__ is None
    with pytest.raises(C.CollectFault):
        state.snapshot()
    with pytest.raises(C.CollectFault):
        state.feed(events()[0])


@pytest.mark.parametrize("category,code", [("MEMORY", 72), ("IMPORT", 73), ("OTHER", 74)])
def test_import_failure_category_code_closed_and_no_admission(category, code):
    state = consumed(events()[:2])
    with pytest.raises(C.CollectFault):
        state.feed({"phase": "error", "stage": 0, "category": category})
    assert state.expected_exit == code
    assert state.failure == category
    assert state.match_exit(code)
    assert not state.match_exit(True)
    assert not state.match_exit(0)
    assert state.match_exit(77) is False  # cleanup override isn't the recorded import result


@pytest.mark.parametrize("phase,code", [("audit_error", 75), ("check_error", 76)])
def test_closed_audit_check_failures_stop(phase, code):
    state = C.ImportCollector(PROBE)
    error = (
        {
            "phase": phase,
            "stage": -1,
            "category": "OTHER",
            "module": "bad",
            "has_file": False,
            "under_installed": False,
        }
        if code == 75
        else {"phase": phase, "stage": -1, "category": "OTHER", "root": None}
    )
    with pytest.raises(C.CollectFault):
        state.feed(error)
    assert state.match_exit(code)
    with pytest.raises(C.CollectFault):
        state.snapshot()


class Emitter:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.failed = False

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def check(self) -> None:
        pass

    def sample(self) -> tuple[dict[str, int], list[int]]:
        return dict(VM), [-1, -1]


@pytest.mark.parametrize("name,filename", list(C.HARNESS.items()))
def test_harness_exact_pair_before_old_rule(name, filename):
    module = ModuleType(name)
    module.__file__ = "/probe/" + filename
    io = Emitter()
    assert C.audit_one(io, PROBE, -1, name, module, {}, {}, resolve=lambda s: str(PurePosixPath(s)))
    assert io.events == [{"phase": "baseline", "row": [name, "harness", "probe/" + filename]}]


@pytest.mark.parametrize(
    "module",
    [
        None,
        SimpleNamespace(__file__="/probe/linux_loaded_probe.py"),
        ModuleType("wrong"),
        "private-data",
    ],
)
def test_reserved_harness_wrong_type_path_never_delegates(module):
    io = Emitter()
    assert not C.audit_one(io, PROBE, -1, "__main__", module, {}, {}, resolve=lambda s: s)
    assert io.events[-1]["category"] == "OUTSIDE_ORIGIN"
    assert "private-data" not in repr(io.events)


def test_reserved_harness_rejects_module_subclass_without_attribute_hook():
    class Hostile(ModuleType):
        def __getattribute__(self, _name):
            raise AssertionError("attribute-hook")

    io = Emitter()
    assert not C.audit_one(io, PROBE, -1, "__main__", Hostile("x"), {}, {})
    assert io.events[-1]["category"] == "OUTSIDE_ORIGIN"


def test_nonharness_delegates_unmodified_old_audit_and_no_batch(monkeypatch):
    called: list[Any] = []

    def audit(*args, **kwargs):
        called.append((args, kwargs))
        return True

    monkeypatch.setattr(PROBE, "audit_module", audit)
    io = Emitter()
    assert C.audit_one(io, PROBE, 0, "other", None, {}, {})
    assert called[0][0][0] is io
    assert called[0][1] == {"batch": None}


def member_imports(error: Any = None, **updates: Any) -> tuple[int, Emitter, list[str]]:
    io, modules, called = Emitter(), {"sys": ModuleType("sys")}, []

    def importer(target):
        called.append(target)
        if error is not None:
            raise error("private-data")
        name = "new" + str(len(called))
        modules[name] = ModuleType(name)
        modules[name].__file__ = "/installed/root/" + name + ".py"

    code = C.collect_imports(
        io,
        PROBE,
        {"root": "owner"},
        {},
        modules=modules,
        importer=importer,
        effects_fn=updates.get("effects_fn", lambda: copy.deepcopy(FDS)),
        native_fn=updates.get("native_fn", lambda: NATIVE),
    )
    return code, io, called


def test_member_collects_three_roots_and_missing_harness_is_permitted():
    code, io, called = member_imports()
    assert code == 0
    assert called == list(PROBE.ROOTS)
    assert io.events[-1]["phase"] == "verified"
    assert not any(row["phase"] in ("ready", "loaded", "held") for row in io.events)


@pytest.mark.parametrize(
    "error,category,code",
    [
        (MemoryError, "MEMORY", 72),
        (ImportError, "IMPORT", 73),
        (OSError, "OTHER", 74),
        (SystemExit, "OTHER", 74),
    ],
)
def test_member_import_failure_stops_no_message_or_next_import(error, category, code):
    result, io, called = member_imports(error)
    assert result == code
    assert len(called) == 1
    assert io.events[-1] == {"phase": "error", "stage": 0, "category": category}
    assert "private-data" not in repr(io.events)


def test_changed_effects_or_native_failure_are_closed_check_error():
    counts = iter([copy.deepcopy(FDS), {"fds": [0, 1, 2], "proc_children_available": True}])
    code, io, called = member_imports(effects_fn=lambda: next(counts))
    assert code == 76 and len(called) == 1
    assert io.events[-1]["category"] == "FD_SET_CHANGED"

    def fail():
        raise OSError("private-data")

    code, io, called = member_imports(native_fn=fail)
    assert code == 76 and len(called) == 3
    assert io.events[-1]["category"] == "OTHER"
    assert "private-data" not in repr(io.events)


LIMITS = (
    b"Limit                     Soft Limit           Hard Limit           Units\n"
    b"Max address space         134217728            134217728            bytes\n"
)


@pytest.mark.parametrize(
    "raw,expected",
    [(LIMITS, [128 << 20] * 2), (LIMITS.replace(b"134217728", b"unlimited"), [-1, -1])],
)
def test_limits_parse_unique_closed_line(raw, expected):
    assert C.parse_limits(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        LIMITS[:-1],
        LIMITS + LIMITS,
        LIMITS.replace(b"bytes", b"kB"),
        LIMITS.replace(b"134217728", b"-1"),
        LIMITS.replace(b"134217728", b"99999999999999999999999"),
        LIMITS.replace(b"Max address space", b"Max other space"),
        LIMITS + b"x" * 65536,
    ],
    ids=["empty", "truncated", "duplicate", "unit", "negative", "overflow", "missing", "large"],
)
def test_limits_invalid_missing_duplicate_truncated_overflow_rejected(raw):
    with pytest.raises(C.CollectFault, match=r"^PROTOCOL$") as caught:
        C.parse_limits(raw)
    assert caught.value.__context__ is None


def test_closed_ready_loaded_envelopes_separate_from_import_stream():
    assert C.envelope({"phase": "loaded", "vm": VM, "limits": [-1, -1]}, "loaded")
    assert C.envelope(
        {"phase": "ready", "vm": VM, "limits": [-1, -1], "pid": 7, "ppid": 1}, "ready"
    )
    for event in (
        {"phase": "loaded", "vm": VM, "limits": [-1, -1], "extra": 1},
        {"phase": "ready", "vm": VM, "limits": [-1, -1], "pid": True, "ppid": 1},
    ):
        with pytest.raises(C.CollectFault):
            C.envelope(event, event["phase"])
