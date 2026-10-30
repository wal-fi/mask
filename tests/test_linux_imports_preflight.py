"""Preflight flow with fake CLI, clock and cases; never starts Docker."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_linux_imports_probe import HOST, normal

VERSION = json.dumps({"Server": {"Version": "29.7.2", "Os": "linux", "Arch": "amd64"}}).encode()


@pytest.fixture
def simulation(tmp_path, monkeypatch):
    observer = HOST.Observer.__new__(HOST.Observer)
    observer.root, observer.image = tmp_path, HOST.BASE
    observer.total_written, observer.originals = 0, {}
    observer.installed, observer.inventory = tmp_path / "unused", {}
    observer.prepared = {"launchers_allowlist": []}
    observer.preflight_passed = False
    observer.probe = tmp_path / "probe"
    observer.probe.mkdir()
    (observer.probe / "runtime.json").write_bytes(b"{}")
    observer.runtime_hash = hashlib.sha256(b"{}").hexdigest()
    data = SimpleNamespace(
        observer=observer,
        now=0.0,
        calls=[],
        cases=[],
        polls=[(0, VERSION)],
        elapsed=[],
        ps=(0, b""),
        image={"Os": "linux", "Architecture": "amd64", "Config": {"Env": []}},
        fired=False,
        watchdog_started=False,
        watchdog_closed=False,
    )

    def start():
        data.watchdog_started = True

    def close():
        data.watchdog_closed = True

    observer.watchdog = SimpleNamespace(
        start=start, close=close, fired=SimpleNamespace(is_set=lambda: data.fired)
    )
    monkeypatch.setattr(HOST, "time", SimpleNamespace(monotonic=lambda: data.now))

    async def sleep(seconds):
        data.now += seconds

    monkeypatch.setattr(HOST, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(HOST.PREP, "verify_tree", lambda *_args: {})

    async def cli(*args, **kwargs):
        data.calls.append((args, kwargs))
        if args[0] == "version":
            data.now += data.elapsed.pop(0) if data.elapsed else 0
            value = data.polls.pop(0)
        elif args[0] == "ps":
            value = data.ps
        else:
            raise AssertionError("unexpected CLI call")
        if isinstance(value, Exception):
            raise value
        return value

    async def inspect(_target):
        data.calls.append((("inspect",), {}))
        if isinstance(data.image, Exception):
            raise data.image
        return data.image

    async def case(name):
        assert observer.preflight_passed is True
        data.cases.append(name)
        result = {
            "case": name,
            "outcome": "normal",
            "cleanup_confirmed": True,
            "diagnostic": normal(),
        }
        observer.save(name + ".json", result)
        return result

    monkeypatch.setattr(observer, "cli", cli)
    monkeypatch.setattr(observer, "inspect", inspect)
    monkeypatch.setattr(observer, "case", case)
    return data


def run(data: Any) -> dict[str, Any]:
    return asyncio.run(data.observer.run(diagnostic_only=True))


def assert_abort(data: Any, result: dict[str, Any], marker: str) -> None:
    assert result["host_failure"] == marker
    assert result["cases"] == [] and not data.cases and not data.observer.preflight_passed
    assert not result["preflight"]["passed"]
    assert data.watchdog_closed and result["watchdog_closed"]
    assert (data.observer.root / "summary.json").exists()
    assert not (data.observer.root / "pending.json").exists()
    assert not any(call[0][0] == "create" for call in data.calls)
    assert "SECRET" not in json.dumps(result)


def test_ready_first_poll_then_single_ps_image_and_case(simulation):
    result = run(simulation)
    assert result["preflight"]["passed"] and simulation.cases == ["control"]
    assert [args[0] for args, _kwargs in simulation.calls] == ["version", "ps", "inspect", "ps"]
    args, kwargs = simulation.calls[0]
    assert args == ("version", "--format", "{{json .}}")
    assert kwargs == {"limit": 16384, "timeout": 5}
    assert result["preflight"]["engine"] == {"Version": "29.7.2", "Os": "linux", "Arch": "amd64"}
    assert not simulation.observer.preflight_passed  # closed run cannot admit a later case


@pytest.mark.parametrize("prefix", [[TimeoutError("SECRET")], [(1, b"SECRET"), (1, b"SECRET")]])
def test_readiness_retries_only_bounded_transients(simulation, prefix):
    simulation.polls = [*prefix, (0, VERSION)]
    simulation.elapsed = [5] * len(prefix) + [0]
    result = run(simulation)
    attempts = result["preflight"]["attempts"]
    assert len(attempts) == len(prefix) + 1 and attempts[-1]["outcome"] == "READY"
    assert simulation.cases == ["control"] and "SECRET" not in json.dumps(result)


def test_three_failed_polls_are_not_a_measurement(simulation):
    simulation.polls = [(1, b"SECRET")] * 3
    simulation.elapsed = [5, 5, 5]
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_NOT_READY")
    assert len(result["preflight"]["attempts"]) == 3


def test_readiness_includes_cleanup_and_interval_without_shortening_timeout(simulation):
    simulation.polls = [TimeoutError("SECRET"), (1, b"SECRET"), (0, VERSION)]
    simulation.elapsed = [10, 5, 0]
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_NOT_READY")
    assert len(result["preflight"]["attempts"]) == 2
    assert all(kwargs["timeout"] == 5 for args, kwargs in simulation.calls if args[0] == "version")


def test_late_ready_cannot_admit_case(simulation):
    simulation.elapsed = [21]
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_NOT_READY")
    assert result["preflight"]["attempts"][-1]["outcome"] == "LATE"


@pytest.mark.parametrize(
    "failure",
    [
        HOST.OLD.HostFault("CLI_CLEANUP"),
        HOST.OLD.HostFault("OUTPUT_LIMIT"),
        OSError("SECRET"),
        (0, b"SECRET"),
        (0, b'{"Server":null}'),
        (0, b"{}"),
        (0, b'{"Server":{},"Server":{}}'),
        (
            0,
            json.dumps(
                {"Server": {"Version": "29.7.2", "Os": "windows", "Arch": "amd64"}}
            ).encode(),
        ),
        (0, json.dumps({"Server": {"Version": "29.7.2", "Os": "linux", "Arch": "arm64"}}).encode()),
        (
            0,
            json.dumps(
                {"Server": {"Version": "SECRET/path", "Os": "linux", "Arch": "amd64"}}
            ).encode(),
        ),
    ],
)
def test_invalid_readiness_aborts_without_further_poll(simulation, failure):
    simulation.polls = [failure, (0, VERSION)]
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_INVALID")
    assert len(simulation.calls) == 1
    assert result["preflight"]["attempt_count"] == 1
    if isinstance(failure, HOST.OLD.HostFault) and failure.category == "CLI_CLEANUP":
        assert not result["preflight"]["cli_cleanup_confirmed"]


@pytest.mark.parametrize("failure", [(0, b"container"), (1, b"SECRET"), TimeoutError("SECRET")])
def test_ps_failure_single_attempt_no_case(simulation, failure):
    simulation.ps = failure
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_INVALID")
    assert [args[0] for args, _kwargs in simulation.calls] == ["version", "ps"]


def test_wrong_image_profile_cannot_set_flag(simulation):
    simulation.image["Architecture"] = "arm64"
    result = run(simulation)
    assert_abort(simulation, result, "PREFLIGHT_INVALID")
    assert [args[0] for args, _kwargs in simulation.calls] == ["version", "ps", "inspect"]


def test_old_true_flag_is_reset_before_failed_preflight(simulation):
    simulation.observer.preflight_passed = True
    simulation.polls = [(0, b"SECRET")]
    assert_abort(simulation, run(simulation), "PREFLIGHT_INVALID")


def test_fired_watchdog_never_admits_case(simulation):
    simulation.fired = True
    result = run(simulation)
    assert not simulation.cases and result["cases"] == []
    assert simulation.watchdog_closed and not simulation.observer.preflight_passed
    assert not result["preflight"]["passed"]


def test_direct_case_requires_flag_before_timer_or_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = HOST.Observer.__new__(HOST.Observer)
    observer.root, observer.docker = tmp_path, "not-called"

    def no_timer(*_args):
        raise AssertionError("timer must not start")

    monkeypatch.setattr(HOST.OLD, "Watchdog", no_timer)
    with pytest.raises(HOST.OLD.HostFault, match="PREFLIGHT_REQUIRED"):
        asyncio.run(observer.case("control"))
    assert not (tmp_path / "pending.json").exists()


@pytest.mark.parametrize("version", [None, 29, "", "x" * 65, "29.\u00e9", "29.7\n"])
def test_invalid_version_value_never_reflected(simulation, version):
    simulation.polls = [
        (0, json.dumps({"Server": {"Version": version, "Os": "linux", "Arch": "amd64"}}).encode())
    ]
    assert_abort(simulation, run(simulation), "PREFLIGHT_INVALID")


def test_version_records_only_closed_server_fields(simulation):
    simulation.polls = [
        (
            0,
            json.dumps(
                {
                    "Server": {
                        "Version": "29.7.2",
                        "Os": "linux",
                        "Arch": "amd64",
                        "extra": "SECRET",
                    },
                    "Client": {"extra": "SECRET"},
                }
            ).encode(),
        )
    ]
    result = run(simulation)
    assert result["preflight"]["passed"] and "SECRET" not in json.dumps(result)
