"""Pure post-import protocol tests; no allocation pressure, child, Docker or SQL."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.test_linux_imports_probe import PROBE, load

P = load("loaded_memory_protocol")
MIB = 1024 * 1024
DIGEST = "268da600f53252ac4f15d6e565ef6cd5c17da53dee68f26dd605090c980e6587"
ROWS: list[list[Any]] = [
    [-1, ["b", "owner", "installed/b.py"]],
    [0, ["a", "owner", "installed/a.py"]],
]


class Clock:
    now = 100.0

    def __call__(self) -> float:
        return self.now


def vm(size: int = 108, peak: int | None = None) -> dict[str, int]:
    return {"size": size * MIB, "peak": (peak or size) * MIB, "rss": 10 * MIB, "threads": 1}


def limits(case: str = "private") -> list[int]:
    return [-1, -1] if case == "control" else [128 * MIB] * 2


def session(case: str = "private", validator: Any = PROBE.validate_inventory) -> tuple[Any, Clock]:
    clock = Clock()
    state = P.PressureProtocol(
        case,
        "-" if case == "control" else DIGEST,
        deadline=120.0,
        clock=clock,
        validator=validator,
        pid=7,
    )
    return state, clock


def admitted(case: str = "private") -> tuple[Any, Clock]:
    state, clock = session(case)
    assert state.ready(vm(20), limits(case), pid=7, ppid=1) == b"GO_IMPORTS\n"
    assert state.admit_imports(ROWS, vm(), limits(case)) is True
    return state, clock


def sample(case: str = "private", **updates: Any) -> dict[str, Any]:
    control = case == "control"
    accepted = (40 if control else 16) * MIB
    return {
        "phase": "held",
        "kind": "private" if control else case,
        "limits": limits(case),
        "vm": vm(150, 152) if control else vm(124, 126),
        "accepted_bytes": accepted,
        "touched_pages": accepted // 4096,
        "blocks": accepted // (4 * MIB),
        "failure": "NONE" if control else "MEMORY",
        "errno": None,
        **updates,
    }


def line(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("ascii") + b"\n"


def held(case: str = "private") -> tuple[Any, Clock]:
    state, clock = admitted(case)
    assert state.pressure(vm(), limits(case)) == (
        b"PRESSURE_SHARED\n" if case == "shared" else b"PRESSURE_PRIVATE\n"
    )
    assert state.held(line(sample(case))) == ("control_ok" if case == "control" else "imposed")
    return state, clock


def finished(case: str = "private") -> tuple[Any, Clock]:
    state, clock = held(case)
    observed = vm(148, 152) if case == "control" else vm(122, 126)
    assert state.release(observed, limits(case), anon=120 * MIB, inventory=[1, 7])
    assert state.released(vm(108, observed["peak"] // MIB), limits(case), anon=80 * MIB)
    if case == "control":
        assert state.pressure(vm(108, 152), limits(case)) == b"PRESSURE_SHARED\n"
        assert state.held(line(sample(case, kind="shared"))) == "control_ok"
        assert state.release(vm(148, 152), limits(case), anon=120 * MIB, inventory=[1, 7])
        assert state.released(vm(108, 152), limits(case), anon=80 * MIB)
    assert state.finish() == b"FINISH\n"
    return state, clock


def test_digest_known_bytes_and_order_stage_independence():
    assert P.inventory_digest(ROWS, PROBE.validate_inventory) == DIGEST
    assert (
        P.inventory_digest([[2, ROWS[1][1]], [-1, ROWS[0][1]]], PROBE.validate_inventory) == DIGEST
    )
    assert P.MAX_ROWS == PROBE.MAX_ROWS and P.MAX_RAW == PROBE.MAX_RAW


@pytest.mark.parametrize("field", [1, 2])
def test_owner_or_origin_change_changes_digest(field):
    rows: list[list[Any]] = [
        [0, ["a", "owner", "installed/a.py"]],
        [0, ["b", "owner", "installed/b.py"]],
    ]
    rows[0][1][field] += "changed"
    assert P.inventory_digest(rows, PROBE.validate_inventory) != DIGEST


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [*ROWS, ROWS[0]],
        [[True, ["a", "owner", "path"]]],
        [[0, ["a", "b"]]],
        [[0, ["a", "b", "x" * 769]]],
        [[0, [str(n), "b", "c"]] for n in range(1501)],
        [[0, [str(n), "\u2603" * 768, "x"]] for n in range(1000)],
    ],
)
def test_bad_or_oversized_inventory_refused(rows):
    with pytest.raises(P.ProtocolFault):
        P.inventory_digest(rows, PROBE.validate_inventory)


@pytest.mark.parametrize(
    "case,expected", [("control", "-"), ("private", DIGEST), ("shared", DIGEST)]
)
def test_exact_argv(case, expected):
    assert P.parse_case_args(["--case", case, "--expected", expected]) == (case, expected)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--case", "private", "--expected", "-"],
        ["--case", "control", "--expected", DIGEST],
        ["--case", "private", "--expected", DIGEST.upper()],
        ["--case", "private", "--expected", DIGEST, "extra"],
        ["--case", "prefix", "--expected", DIGEST],
    ],
)
def test_argv_cannot_expand(args):
    with pytest.raises(P.ProtocolFault):
        P.parse_case_args(args)


@pytest.mark.parametrize("case", ["private", "shared", "control"])
def test_full_state_path_and_control_peak_over_cap_allowed(case):
    state, _clock = finished(case)
    assert state.outcome == "inconclusive"  # held is never final evidence.
    assert state.completed(
        {"phase": "done"}, eof=True, returncode=0, cleanup=True, inventory=[1]
    ) == ("control_ok" if case == "control" else "imposed")
    if case == "control":
        assert state.control_digest() == DIGEST


def test_control_digest_cannot_escape_before_exit_and_cleanup():
    state, _clock = admitted("control")
    with pytest.raises(P.ProtocolFault):
        state.control_digest()
    assert state.state == "ABORTED"


def test_mismatched_inventory_aborts_before_pressure():
    state, _clock = session()
    state.ready(vm(20), limits(), pid=7, ppid=1)
    with pytest.raises(P.ProtocolFault):
        state.admit_imports([[0, ["different", "owner", "installed/a.py"]]], vm(), limits())
    assert state.state == "ABORTED"
    with pytest.raises(P.ProtocolFault):
        state.pressure(vm(), limits())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(accepted_bytes=True),
        lambda x: x.update(blocks=5),
        lambda x: x.update(touched_pages=0),
        lambda x: x.update(extra="SECRET"),
        lambda x: x.update(errno=12),
        lambda x: x.update(kind="shared"),
        lambda x: x.update(failure="SECRET"),
        lambda x: x.update(vm=vm(127, 126)),
        lambda x: x.update(limits=[True, True]),
        lambda x: x.update(phase="other"),
    ],
)
def test_closed_held_schema(mutate):
    state, _clock = admitted()
    state.pressure(vm(), limits())
    event = sample()
    mutate(event)
    with pytest.raises(P.ProtocolFault) as caught:
        state.held(line(event))
    assert state.state == "ABORTED" and "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"{}\n{}\n",
        b"x" * 1025,
        b'{"phase":"held","phase":"held"}\n',
        b'{"x":NaN}\n',
        b"\xff\n",
    ],
)
def test_framing_is_closed(raw):
    state, _clock = admitted()
    state.pressure(vm(), limits())
    with pytest.raises(P.ProtocolFault):
        state.held(raw)
    assert state.state == "ABORTED"


@pytest.mark.parametrize(
    "changes,outcome",
    [
        ({"accepted_bytes": 0, "blocks": 0, "touched_pages": 0}, "inconclusive"),
        ({"vm": vm(129)}, "fail"),
        (
            {
                "accepted_bytes": 40 * MIB,
                "blocks": 10,
                "touched_pages": 40 * MIB // 4096,
                "failure": "NONE",
            },
            "fail",
        ),
        ({"failure": "OTHER", "errno": 5}, "inconclusive"),
    ],
)
def test_refusal_or_success_does_not_manufacture_imposition(changes, outcome):
    state, _clock = admitted()
    state.pressure(vm(), limits())
    with pytest.raises(P.ProtocolFault):
        state.held(line(sample(**changes)))
    assert state.outcome == outcome


@pytest.mark.parametrize("observed", [vm(122, 125), vm(122, 127)])
def test_independent_peak_mismatch_stops_release(observed):
    state, _clock = held()
    with pytest.raises(P.ProtocolFault):
        state.release(observed, limits(), anon=120 * MIB, inventory=[1, 7])
    assert state.state == "ABORTED"


def test_control_release_needs_both_criteria_and_full_wait_budget():
    state, clock = held("control")
    state.release(vm(148, 152), limits("control"), anon=120 * MIB, inventory=[1, 7])
    assert not state.released(vm(113, 152), limits("control"), anon=80 * MIB)
    assert state.release_wait() == 1.0
    clock.now += 1
    assert not state.release_sample(vm(108, 152), limits("control"), anon=100 * MIB)
    clock.now += 1
    assert state.release_sample(vm(108, 152), limits("control"), anon=80 * MIB)
    assert state.pressure(vm(108, 152), limits("control")) == b"PRESSURE_SHARED\n"


def test_five_failed_release_samples_abort():
    state, clock = held("control")
    state.release(vm(148, 152), limits("control"), anon=120 * MIB, inventory=[1, 7])
    assert not state.released(vm(150, 152), limits("control"), anon=120 * MIB)
    for _ in range(3):
        clock.now += 1
        assert not state.release_sample(vm(150, 152), limits("control"), anon=120 * MIB)
    clock.now += 1
    with pytest.raises(P.ProtocolFault):
        state.release_sample(vm(150, 152), limits("control"), anon=120 * MIB)
    assert state.state == "ABORTED"


@pytest.mark.parametrize("failure", ["eof", "returncode", "cleanup", "inventory", "marker"])
def test_no_final_outcome_without_all_cleanup_facts(failure):
    state, _clock = finished()
    facts = {"eof": True, "returncode": 0, "cleanup": True, "inventory": [1]}
    marker = {"phase": "done"}
    if failure == "marker":
        marker["extra"] = "SECRET"
    else:
        facts[failure] = {"eof": False, "returncode": False, "cleanup": False, "inventory": [1, 7]}[
            failure
        ]
    with pytest.raises(P.ProtocolFault):
        state.completed(marker, **facts)
    assert state.outcome == "inconclusive"


@pytest.mark.parametrize("time_value", [120.0, float("nan"), float("inf"), 99.0, True])
def test_one_deadline_and_valid_clock(time_value):
    state, clock = admitted()
    clock.now = time_value
    with pytest.raises(P.ProtocolFault):
        state.pressure(vm(), limits())
    assert state.state == "ABORTED"


def test_validator_and_clock_failures_are_sanitized_without_exception_chain():
    def bad(*_args):
        raise RuntimeError("SECRET /absolute/path")

    state, _clock = session(validator=bad)
    state.ready(vm(20), limits(), pid=7, ppid=1)
    with pytest.raises(P.ProtocolFault) as caught:
        state.admit_imports(ROWS, vm(), limits())
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value)
    with pytest.raises(P.ProtocolFault) as caught:
        P.PressureProtocol(
            "private", DIGEST, deadline=120, clock=bad, validator=PROBE.validate_inventory, pid=7
        )
    assert caught.value.__context__ is None


def test_after_abort_even_cleanup_commands_are_forbidden():
    state, _clock = admitted()
    with pytest.raises(P.ProtocolFault):
        state.finish()
    with pytest.raises(P.ProtocolFault):
        state.release(vm(), limits(), anon=0, inventory=[1, 7])
    assert state.state == "ABORTED"


def at_state(target: str) -> Any:
    state, _clock = session()
    steps = [
        ("READY", lambda: None),
        ("IMPORTING", lambda: state.ready(vm(20), limits(), pid=7, ppid=1)),
        ("ADMITTED", lambda: state.admit_imports(ROWS, vm(), limits())),
        ("PRESSURING", lambda: state.pressure(vm(), limits())),
        ("HELD", lambda: state.held(line(sample()))),
        (
            "RELEASE_SENT",
            lambda: state.release(vm(122, 126), limits(), anon=120 * MIB, inventory=[1, 7]),
        ),
        ("FINISH_READY", lambda: state.released(vm(108, 126), limits(), anon=80 * MIB)),
        ("EXITING", state.finish),
        (
            "DONE",
            lambda: state.completed(
                {"phase": "done"}, eof=True, returncode=0, cleanup=True, inventory=[1]
            ),
        ),
    ]
    for name, action in steps:
        action()
        if name == target:
            return state
    raise AssertionError("unknown test state")


OPERATIONS = {
    "ready": lambda s: s.ready(vm(20), limits(), pid=7, ppid=1),
    "admit": lambda s: s.admit_imports(ROWS, vm(), limits()),
    "pressure": lambda s: s.pressure(vm(), limits()),
    "held": lambda s: s.held(line(sample())),
    "release": lambda s: s.release(vm(122, 126), limits(), anon=120 * MIB, inventory=[1, 7]),
    "released": lambda s: s.released(vm(108, 126), limits(), anon=80 * MIB),
    "wait": lambda s: s.release_wait(),
    "resample": lambda s: s.release_sample(vm(108, 126), limits(), anon=80 * MIB),
    "finish": lambda s: s.finish(),
    "complete": lambda s: s.completed(
        {"phase": "done"}, eof=True, returncode=0, cleanup=True, inventory=[1]
    ),
    "digest": lambda s: s.control_digest(),
}
ALLOWED = {
    "READY": "ready",
    "IMPORTING": "admit",
    "ADMITTED": "pressure",
    "PRESSURING": "held",
    "HELD": "release",
    "RELEASE_SENT": "released",
    "FINISH_READY": "finish",
    "EXITING": "complete",
    "DONE": None,
}


@pytest.mark.parametrize(
    "state_name,operation",
    [
        (name, operation)
        for name, allowed in ALLOWED.items()
        for operation in OPERATIONS
        if operation != allowed
    ],
)
def test_every_wrong_state_or_duplicate_is_terminal(state_name, operation):
    state = at_state(state_name)
    with pytest.raises(P.ProtocolFault):
        OPERATIONS[operation](state)
    assert state.state == "ABORTED"
    with pytest.raises(P.ProtocolFault):
        state.finish()


def test_validator_time_cannot_renew_the_deadline():
    state, clock = session()

    def slow_validator(rows):
        PROBE.validate_inventory(rows)
        clock.now = 120.0

    state.validator = slow_validator
    state.ready(vm(20), limits(), pid=7, ppid=1)
    with pytest.raises(P.ProtocolFault):
        state.admit_imports(ROWS, vm(), limits())
    assert state.state == "ABORTED"


def test_release_wait_requires_a_whole_second_remaining():
    state, clock = held("control")
    state.release(vm(148, 152), limits("control"), anon=120 * MIB, inventory=[1, 7])
    state.released(vm(150, 152), limits("control"), anon=120 * MIB)
    clock.now = 119.5
    with pytest.raises(P.ProtocolFault):
        state.release_wait()


@pytest.mark.parametrize(
    "observed,pid,ppid",
    [
        (vm(125), 7, 1),
        (vm(20), True, 1),
        (vm(20), 7, True),
        ({**vm(20), "threads": 2}, 7, 1),
        ({**vm(20), "size": True}, 7, 1),
        ({**vm(20), "rss": 30 * MIB}, 7, 1),
    ],
)
def test_ready_refuses_wrong_identity_or_facts(observed, pid, ppid):
    state, _clock = session()
    with pytest.raises(P.ProtocolFault):
        state.ready(observed, limits(), pid=pid, ppid=ppid)
    assert state.state == "ABORTED"


@pytest.mark.parametrize("where", ["marker", "final_inventory", "held_inventory"])
@pytest.mark.parametrize("raising", [False, True])
def test_hostile_equality_never_runs_and_cannot_forge_completion(where, raising):
    calls: list[str] = []

    class Hostile:
        __hash__ = object.__hash__

        def __eq__(self, _other):
            calls.append("equality")
            if raising:
                raise RuntimeError("SECRET equality")
            return True

    candidate = Hostile()
    state, _clock = held() if where == "held_inventory" else finished()

    def action() -> Any:
        if where == "held_inventory":
            return state.release(vm(122, 126), limits(), anon=120 * MIB, inventory=[candidate, 7])
        return state.completed(
            {"phase": candidate} if where == "marker" else {"phase": "done"},
            eof=True,
            returncode=0,
            cleanup=True,
            inventory=[candidate] if where == "final_inventory" else [1],
        )

    with pytest.raises(P.ProtocolFault) as caught:
        action()
    assert state.state == "ABORTED" and calls == []
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value)
    with pytest.raises(P.ProtocolFault):
        state.finish()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_unexpected_exception_in_any_public_operation_is_terminal(operation):
    state, _clock = session()

    def broken(_state):
        raise OSError("SECRET unexpected")

    state._guard = broken
    with pytest.raises(P.ProtocolFault) as caught:
        OPERATIONS[operation](state)
    assert state.state == "ABORTED" and state.outcome == "inconclusive"
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "SECRET" not in str(caught.value)


def test_bad_signature_is_terminal_without_a_retry():
    state, _clock = session()
    with pytest.raises(P.ProtocolFault):
        state.ready()
    assert state.state == "ABORTED"
    with pytest.raises(P.ProtocolFault):
        state.ready(vm(20), limits(), pid=7, ppid=1)


@pytest.mark.parametrize("raising", [False, True])
def test_vm_keys_are_exact_strings_before_hash_or_equality(raising):
    calls: list[str] = []

    class Key:
        def __hash__(self):
            calls.append("hash")
            return hash("size")

        def __eq__(self, _other):
            calls.append("equality")
            if raising:
                raise OSError("SECRET key")
            return True

    observed: dict[Any, int] = vm(20)
    del observed["size"]
    observed[Key()] = 20 * MIB
    calls.clear()
    state, _clock = session()
    with pytest.raises(P.ProtocolFault):
        state.ready(observed, limits(), pid=7, ppid=1)
    assert state.state == "ABORTED" and calls == []
