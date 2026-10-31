"""Call counts only for budgeting. Fake latency is never native timing evidence."""

import inspect
import json
from collections import Counter
from typing import Any

import pytest

from tests.test_pg16_shell_host import bound as host_fixture
from tests.test_pg16_shell_host import run
from tests.test_pg16_shell_run import context as context_fixture
from tests.test_pg16_shell_run import entry as entry_fixture

bound, entry, context = host_fixture, entry_fixture, context_fixture


@pytest.mark.parametrize("path", ["preserved", "own-stop", "retry-own-stop"])
def test_pin_counts_separate_phase_case_collect_retry_and_restore(  # noqa: PLR0915 - serial lifecycle count oracle
    entry: Any, context: Any, monkeypatch: Any, path: str
) -> None:
    value, host, engine, module = context
    # Observed counts use the real invoke and explicit pins in reviewed source.
    # Replaced PS/clock/final-pin paths are separately declared, never labelled
    # as observed native calls or timings.
    observed: Counter[Any] = Counter()
    declared: Counter[Any] = Counter()
    visits: Counter[str] = Counter()
    stack: list[Any] = [("setup", "")]
    originals = {
        name: getattr(host, name)
        for name in (
            "start_cycle",
            "perform_b",
            "_case",
            "_collect",
            "cleanup_owned",
            "restore_desktop",
            "sample",
            "processes",
            "_bounded",
        )
    }
    loop_code = originals["perform_b"].__func__.__code__
    case_code = originals["_case"].__func__.__code__
    invoke_code = module["Host"].invoke.__code__
    stopped = [False]
    own = {"pid": 123, "name": "Docker Desktop", "created": "134372987595123457"}

    def pin(*, cleanup: bool = False) -> None:
        phase, case = stack[-1]
        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        assert caller is not None
        origin = "other"
        if caller.f_code is loop_code:
            case, origin = caller.f_locals["case"], "case-loop"
        elif caller.f_code is case_code:
            case, origin = caller.f_locals["case"], "owner-start"
        elif caller.f_code is invoke_code:
            origin = "invoke"
        observed[phase, case, origin, cleanup] += 1
        del caller, frame

    def scope(name: str, phase: str) -> None:
        original = originals[name]

        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            case = args[0] if name == "_case" else args[0]["case"] if name == "_collect" else ""
            selected = phase
            if name == "_collect":
                selected = "B-collect" if stack[-1][0] == "B" else stack[-1][0] + "-collect"
            stack.append((selected, case))
            visits[selected] += 1
            try:
                return await original(*args, **kwargs)
            finally:
                stack.pop()

        monkeypatch.setattr(host, name, wrapped)

    for name, phase in (
        ("start_cycle", "A"),
        ("perform_b", "B"),
        ("_case", "B"),
        ("_collect", "collect"),
    ):
        scope(name, phase)

    async def sample() -> Any:
        phase, _ = stack[-1]
        declared[phase, "sample-host-pin-cleanup"] += 1
        declared[phase, "clock-subset-upper-cleanup"] += 1
        return await originals["sample"]()

    async def processes(*args: Any, **kwargs: Any) -> Any:
        phase, _ = stack[-1]
        declared[
            phase, "ps-invoke-cleanup" if kwargs.get("cleanup", False) else "ps-invoke-normal"
        ] += 1
        if phase == "restore" and path != "preserved":
            return [] if stopped[0] else [own]
        return await originals["processes"](*args, **kwargs)

    async def backend(label: str, args: Any, *more: Any, **kwargs: Any) -> Any:
        if tuple(args[3:]) == ("desktop", "stop", "--timeout", "20"):
            stopped[0] = True
            return 0, b""
        return await originals["_bounded"](label, args, *more, **kwargs)

    async def restore() -> None:
        stack.append(("restore", ""))
        try:
            if path != "preserved":
                # The actual restore branch is exercised. A was preserved in
                # this model, so its unexecuted start-PS is declared separately.
                host.initial_active, host.started = False, own
                declared["A", "own-start-ps-unexecuted-normal"] += 1
            await originals["restore_desktop"]()
        finally:
            stack.pop()

    async def cleanup() -> None:
        phase = "cleanup" if visits["cleanup"] == 0 else "retry"
        visits[phase] += 1
        stack.append((phase, ""))
        try:
            if path == "retry-own-stop" and phase == "cleanup":
                assert host._cleanup_lock.acquire(blocking=False)
                monitor = host._monitors["one"]
                close = monitor.close

                def joined_emergency() -> bool:
                    host._cleanup_lock.release()  # fake emergency completes
                    return bool(close())

                monkeypatch.setattr(monitor, "close", joined_emergency)
                await originals["cleanup_owned"]()
                assert not host.result["owned_cleanup"]
                monitor.fired.set()
            else:
                await originals["cleanup_owned"]()
        finally:
            stack.pop()

    monkeypatch.setattr(host, "pins", pin)
    monkeypatch.setattr(host, "sample", sample)
    monkeypatch.setattr(host, "processes", processes)
    monkeypatch.setattr(host, "_bounded", backend)
    monkeypatch.setattr(host, "restore_desktop", restore)
    monkeypatch.setattr(host, "cleanup_owned", cleanup)
    monkeypatch.setitem(
        entry["run"].__globals__,
        "final_pins",
        lambda _value: declared.update({("terminal", "FINAL23"): 1}),
    )
    if path == "retry-own-stop":
        engine.fail_start = True
    status = run(entry["run"](value))
    assert status == (1 if path == "retry-own-stop" else 0)
    assert value.released and not engine.rows
    assert declared["A", "sample-host-pin-cleanup"] == 12
    assert declared["A", "clock-subset-upper-cleanup"] == 12
    assert declared["A", "ps-invoke-normal"] == 12
    assert declared["terminal", "FINAL23"] == 1
    assert observed["A", "", "other", False] == 1
    assert observed["A", "", "invoke", False] == 6
    if path != "retry-own-stop":
        for case in module["CASES"]:
            assert observed["B", case, "case-loop", False] == 1
            assert observed["B", case, "owner-start", False] == 1
            assert observed["B", case, "invoke", False] == 4
            assert observed["B-collect", case, "invoke", True] == 4
        assert observed["cleanup", "", "invoke", True] == 2
        grouped: Counter[str] = Counter()
        for row in host._cases:
            grouped[row["report_category"] or "POSITIVE"] += 1
        assert grouped["POSITIVE"] == 4 and grouped["HEADER"] == 9 and grouped["DEADLINE"] == 3
    else:
        assert visits["cleanup"] == visits["retry"] == 1
        assert observed["cleanup-collect", "one", "invoke", True] == 0
        assert observed["retry-collect", "one", "invoke", True] == 6
        assert observed["retry", "", "invoke", True] == 2
        assert not host._cases
    assert observed["restore", "", "invoke", True] == (1 if path == "preserved" else 3)
    assert declared["restore", "ps-invoke-cleanup"] == (1 if path == "preserved" else 2)
    assert declared["restore", "sample-host-pin-cleanup"] == (0 if path == "preserved" else 1)
    assert host.result["desktop_state"] == (
        "PRESERVED_ACTIVE" if path == "preserved" else "OFF_CONFIRMED"
    )
    # Counts remain serializable public scalars, not fake wall-clock samples.
    assert "seconds" not in json.dumps({"calls": sum(observed.values())})
