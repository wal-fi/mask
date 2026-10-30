"""Pure freshness admission; no host clock, Desktop, CLI or process effects."""

import ast
import runpy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/oracle9_cycle_freshness.py"
m = runpy.run_path(str(SOURCE))
Sample, Cycle, Phase = m["Sample"], m["Cycle"], m["Phase"]
Decision, Reason = m["Decision"], m["Reason"]
start, advance, encode, decode, abort = (
    m[k] for k in ("start", "advance", "encode", "decode", "abort")
)
BOOT = "134370000000000000"
BASE = 9007199254740993
UTC = 134375000000000000


def sample(ms: int = 0, *, utc_delta: int = 0, boot: str = BOOT) -> Any:
    return Sample(boot, str(BASE + ms), str(UTC + ms * 10000 + utc_delta))


def observed(gap: int = 10000) -> Any:
    state = start(sample())
    for index in range(1, 10):
        result = advance(state, sample(index * gap), "OBSERVE")
        assert result.decision is Decision.ACCEPT
        state = result.state
    return state


def test_full_cycle_exact_serialization_and_one_b_only():
    state = observed()
    ready = advance(state, sample(90000), "READY")
    admitted = advance(ready.state, sample(90000), "B")
    assert admitted.decision is Decision.ACCEPT and admitted.state.phase is Phase.B_CONSUMED
    assert decode(encode(admitted.state)) == admitted.state
    assert str(BASE).encode() in encode(admitted.state)
    denied = advance(admitted.state, sample(90000), "B")
    assert denied.decision is Decision.REFUSE and denied.state is admitted.state


@pytest.mark.parametrize(
    "gap,expected", [(9999, Reason.TOO_EARLY), (10000, None), (30000, None), (30001, Reason.GAP)]
)
def test_observation_bounds_inclusive(gap, expected):
    result = advance(start(sample()), sample(gap), "OBSERVE")
    assert result.reason is expected


@pytest.mark.parametrize("action", ["READY", "B", "OBSERVE"])
def test_wrong_order_or_too_many_observations_is_terminal(action):
    state = observed() if action == "OBSERVE" else start(sample())
    result = advance(state, state.last, action)
    assert result.reason is Reason.ORDER and result.state.phase is Phase.FAILED
    assert advance(result.state, state.last, "B").reason is Reason.TERMINAL


@pytest.mark.parametrize("action", ["READY", "B"])
@pytest.mark.parametrize("gap", [0, 30000, 30001])
def test_ready_and_b_gap_boundaries(action, gap):
    state = observed()
    if action == "B":
        state = advance(state, sample(90000), "READY").state
    result = advance(state, sample(90000 + gap), action)
    assert result.reason is (Reason.GAP if gap > 30000 else None)


@pytest.mark.parametrize("ms", [300000, 300001])
def test_total_ceiling_dominates_individually_valid_gaps(ms):
    state = observed(30000)  # O9 at270s, READY at290s, B at300s or300s+1ms
    state = advance(state, sample(290000), "READY").state
    result = advance(state, sample(ms), "B")
    assert result.reason is (Reason.TOTAL_AGE if ms > 300000 else None)


@pytest.mark.parametrize("where", ["OBSERVE", "READY", "B"])
def test_two_hour_pause_or_suspend_never_enters_b(where):
    state = start(sample()) if where == "OBSERVE" else observed()
    if where == "B":
        state = advance(state, sample(90000), "READY").state
    result = advance(state, sample(7200000), where)
    assert result.decision is Decision.REFUSE and result.reason is Reason.TOTAL_AGE
    assert advance(result.state, sample(7200000), "B").reason is Reason.TERMINAL
    assert abort(result.state) is result.state


@pytest.mark.parametrize("delta", [-1, 1, 20000000, -20000000, 20100000, -20100000])
def test_tick_utc_secondary_check_integer_precision(delta):
    result = advance(start(sample()), sample(10000, utc_delta=delta), "OBSERVE")
    assert result.reason is None  # tolerance20,000,000 +100,000 (0.1% of10s)


@pytest.mark.parametrize("delta", [20100001, -20100001, 72000000000])
def test_tick_utc_disagreement_aborts_without_using_utc_as_fallback(delta):
    result = advance(start(sample()), sample(10000, utc_delta=delta), "OBSERVE")
    assert result.reason is Reason.DISAGREEMENT


def test_cumulative_disagreement_cannot_be_hidden_by_small_per_step_drift():
    state = start(sample())
    first = advance(state, sample(10000, utc_delta=11000000), "OBSERVE")
    assert first.decision is Decision.ACCEPT
    result = advance(first.state, sample(20000, utc_delta=22000000), "OBSERVE")
    assert result.reason is Reason.DISAGREEMENT


@pytest.mark.parametrize("boot", [str(int(BOOT) + 1), str(int(BOOT) + 20000000)])
def test_any_boot_reference_change_refuses_no_automatic_tolerance(boot):
    result = advance(start(sample()), sample(10000, boot=boot), "OBSERVE")
    assert result.reason is Reason.BOOT


def test_counter_or_utc_rollback_is_fatal():
    state = observed()
    assert advance(state, sample(89999), "READY").reason is Reason.ROLLBACK
    result = advance(state, sample(90000, utc_delta=-1), "READY")
    assert result.reason is Reason.ROLLBACK


def test_abort_requires_no_fresh_sample_and_never_grants_restore_authority():
    state = abort(observed())
    assert state.phase is Phase.ABORTED
    assert advance(state, sample(7200000), "B").reason is Reason.TERMINAL
    assert "restore" not in encode(state).decode()


@pytest.mark.parametrize(
    "value", [True, 1, 1.0, "", "01", "-1", "1.0", "1e2", "\uff11\uff12", "1" * 21, str(1 << 64)]
)
def test_closed_decimal_strings_only(value):
    with pytest.raises((ValueError, TypeError)):
        Sample(BOOT, value, str(UTC))


@pytest.mark.parametrize("change", [b" ", b"\n", b"x"])
def test_noncanonical_or_trailing_bytes_refused(change):
    with pytest.raises((ValueError, TypeError)):
        decode(encode(observed()) + change)


@pytest.mark.parametrize(
    "mode", ["extra", "duplicate", "version", "count", "phase", "clock_number", "truncated", "huge"]
)
def test_state_schema_mutation_refused(mode):
    raw = encode(observed())
    if mode == "extra":
        raw = raw.replace(b"{", b'{"extra":1,', 1)
    elif mode == "duplicate":
        raw = raw.replace(b'"version":1', b'"version":1,"version":1')
    elif mode == "version":
        raw = raw.replace(b'"version":1', b'"version":true')
    elif mode == "count":
        raw = raw.replace(b'"observations":9', b'"observations":true')
    elif mode == "phase":
        raw = raw.replace(b'"OBSERVING"', b'"UNKNOWN"')
    elif mode == "clock_number":
        raw = raw.replace(b'"' + str(BASE).encode() + b'"', str(BASE).encode())
    elif mode == "truncated":
        raw = raw[:-3]
    else:
        raw = b"x" * 2049
    with pytest.raises((ValueError, TypeError)):
        decode(raw)


def test_freeze_bypass_revalidated_before_transition_or_encoding():
    state = replace(observed())
    object.__setattr__(state, "observations", True)
    with pytest.raises(ValueError):
        encode(state)
    with pytest.raises(ValueError):
        advance(state, sample(90000), "READY")


@pytest.mark.parametrize("mode", ["too_fast", "too_slow", "expired", "utc"])
def test_deserialized_state_requires_consistent_count_and_elapsed(mode):
    state = observed()
    changed = sample({"too_fast": 1, "too_slow": 270001, "expired": 300001, "utc": 90000}[mode])
    if mode == "utc":
        changed = sample(90000, utc_delta=30000000)
    with pytest.raises(ValueError):
        replace(state, last=changed)


def test_module_remains_pure_without_cli_clock_or_io():
    tree = ast.parse(SOURCE.read_text("utf8"))
    modules: set[str | None] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "print", "exec", "eval", "__import__"}
    assert modules == {"dataclasses", "enum", "json"}
