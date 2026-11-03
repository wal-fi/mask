"""Fake-only tests for the private api_factory of the pinned composition.

The keyword-only `api_factory` of `_collect_pinned` does not exist yet: until
it does, calls passing it fail with TypeError and the record has no factory
fields (feature-absent baseline, not a product regression). The 63 tests of
the existing composition stay unchanged in their own file; this file reuses
their preloaded helpers. Every factory here is a Python fake returning the
fake NT api; nothing loads a DLL or converts a native call, and the factory
seam is private, not an authentication boundary.
"""

import builtins
import ctypes
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
PINNED = REPO / "docs/poc/pg16_shell_native_control_collect_pinned.py"
PINNED_TESTS = REPO / "tests/test_pg16_shell_native_control_collect_pinned.py"
COLLECTOR = REPO / "docs/poc/pg16_shell_native_control_collect.py"
WIN32 = REPO / "docs/poc/pg16_shell_native_control_collect_win32.py"
WIN32_TESTS = REPO / "tests/test_pg16_shell_native_control_collect_win32.py"
VERIFY_SOURCE = REPO / "docs/poc/pg16_shell_native_control_verify.py"
VERIFY_TESTS = REPO / "tests/test_pg16_shell_native_control_verify.py"
NONCE = "0123456789abcdef0123456789abcdef"
ARGV0 = "C:\\fictitious\\lab\\venv\\Scripts\\python.exe"
ARGUMENT = ("INVALID", "COLLECT_ARGUMENT", None, None)
UNAVAILABLE = ("INVALID", "COLLECT_UNAVAILABLE", None, None)
INTERNAL = ("INVALID", "COLLECT_INTERNAL", None, None)
POISONED = ("INVALID", "COLLECT_POISONED", None, None)
SOURCE = ("INVALID", "COLLECT_SOURCE", None, None)
SAME: Any = object()


class Signal(BaseException):
    """A fictitious control interruption."""


@pytest.fixture
def pin(monkeypatch: Any) -> SimpleNamespace:
    module = runpy.run_path(str(PINNED))
    shared = runpy.run_path(str(PINNED_TESTS))
    helpers = runpy.run_path(str(WIN32_TESTS))
    builder = runpy.run_path(str(VERIFY_TESTS))
    original = runpy.run_path(str(COLLECTOR))
    win32 = runpy.run_path(str(WIN32))
    function = module["_collect_pinned"]
    return SimpleNamespace(
        run=function,
        glob=function.__globals__,
        shared=shared,
        helpers=helpers,
        builder=builder,
        collector_src=COLLECTOR.read_bytes(),
        backend_src=WIN32.read_bytes(),
        verifier=VERIFY_SOURCE.read_bytes(),
        original=original["collect"].__globals__,
        win32=win32["backend"].__globals__,
        monkeypatch=monkeypatch,
    )


# -- shared helpers of the 63 pinned tests (same fixture attribute names) --


def sealed(pin: SimpleNamespace) -> Any:
    return pin.shared["sealed"](pin)


def no_exec(patch: Any) -> None:
    """Inside `sealed`: neither source may be compiled or executed."""
    patch.setattr(builtins, "exec", forbidden)
    patch.setattr(builtins, "compile", forbidden)


def forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("exec, factory or native effect where none is allowed")


def world(pin: SimpleNamespace, scenario: str = "approved") -> SimpleNamespace:
    result: SimpleNamespace = pin.shared["world"](pin, scenario)
    return result


def attempts(pin: SimpleNamespace) -> list[Any]:
    result: list[Any] = pin.shared["attempts"](pin)
    return result


def assert_consumed(pin: SimpleNamespace, fake: Any, record: Any) -> None:
    pin.shared["assert_consumed"](pin, fake, record)


def assert_originals_untouched(pin: SimpleNamespace) -> None:
    pin.shared["assert_originals_untouched"](pin)


def run(
    pin: SimpleNamespace, factory: Any, api: Any = None, collector: Any = SAME, backend: Any = SAME
) -> Any:
    first = pin.collector_src if collector is SAME else collector
    second = pin.backend_src if backend is SAME else backend
    return pin.run(first, second, api, NONCE, ARGV0, api_factory=factory)


class Factory:
    """A fake factory: records each namespace and the record state it sees,
    then returns its result or raises its error."""

    def __init__(self, pin: SimpleNamespace, result: Any = None, error: Any = None) -> None:
        self.pin, self.result, self.error = pin, result, error
        self.calls: list[Any] = []
        self.observed: list[tuple[Any, Any, Any]] = []
        self.declared: dict[str, Any] = {}

    def __call__(self, namespace: Any) -> Any:
        self.calls.append(namespace)
        record = attempts(self.pin)[0]
        self.observed.append((record.factory_started, record.api, record.backend))
        for name in ("_Win32Backend", "OBJECT_ATTRIBUTES", "IO_STATUS_BLOCK", "PROTOTYPES"):
            self.declared[name] = namespace.get(name)
        if self.error is not None:
            raise self.error
        return self.result


def typed_api(pin: SimpleNamespace, fake_api: Any, seen: list[Any]) -> SimpleNamespace:
    """The fake api, with `create` recording the declared ctypes types it gets."""
    operations = {name: getattr(fake_api, name) for name in pin.helpers["API_OPERATIONS"]}
    inner = operations["create"]

    def create(*args: Any) -> Any:
        seen.append((type(args[0]), type(args[2]), type(args[3])))
        return inner(*args)

    operations["create"] = create
    return SimpleNamespace(**operations)


# -- argument contract: nothing runs on refusal --


@pytest.mark.parametrize("kind", ["short", "flipped", "bytearray", "swapped"])
@pytest.mark.parametrize("which", ["collector", "backend"])
def test_tampered_sources_never_reach_the_factory(
    pin: SimpleNamespace, which: str, kind: str
) -> None:
    w = world(pin)
    factory = Factory(pin, result=w.api)
    tampered = pin.shared["tampered"]
    if which == "collector":
        arguments = {"collector": tampered(pin.collector_src, pin.backend_src, kind)}
    else:
        arguments = {"backend": tampered(pin.backend_src, pin.collector_src, kind)}
    with sealed(pin) as patch:
        no_exec(patch)
        assert run(pin, factory, **arguments) == SOURCE
    assert factory.calls == [] and attempts(pin) == [] and w.nt.calls == []


@pytest.mark.parametrize("value", [7, "factory", object(), b"factory"])
def test_a_non_callable_factory_is_an_argument_refusal(pin: SimpleNamespace, value: Any) -> None:
    w = world(pin)
    with sealed(pin) as patch:
        no_exec(patch)
        assert run(pin, value) == ARGUMENT
    assert attempts(pin) == [] and w.nt.calls == []


def test_an_explicit_api_together_with_a_factory_is_refused(pin: SimpleNamespace) -> None:
    w = world(pin)
    factory = Factory(pin, result=w.api)
    with sealed(pin) as patch:
        no_exec(patch)
        assert run(pin, factory, api=w.api) == ARGUMENT
    assert factory.calls == [] and attempts(pin) == [] and w.nt.calls == []


def test_no_api_and_no_factory_is_unavailable_without_consumption(pin: SimpleNamespace) -> None:
    w = world(pin)
    with sealed(pin) as patch:
        no_exec(patch)
        assert run(pin, None) == UNAVAILABLE
    assert attempts(pin) == []
    with sealed(pin):
        assert run(pin, Factory(pin, result=w.api))[:2] == ("VERIFIED_APPROVED", "OK")


def test_legacy_api_path_is_unchanged_with_the_default_factory(pin: SimpleNamespace) -> None:
    w = world(pin)
    with sealed(pin):
        result = run(pin, None, api=w.api)
    assert result[:2] == ("VERIFIED_APPROVED", "OK")
    (record,) = attempts(pin)
    assert record.api is w.api and record.factory is None
    assert record.factory_started is False
    assert record.backend._ops["create"] is w.api.create


def test_a_consumed_attempt_never_calls_a_factory(pin: SimpleNamespace) -> None:
    w = world(pin)
    with sealed(pin):
        assert pin.run(pin.collector_src, pin.backend_src, w.api, NONCE, ARGV0)[1] == "OK"
    (record,) = attempts(pin)
    factory = Factory(pin, result=w.api)
    before = list(w.nt.calls)
    with sealed(pin) as patch:
        no_exec(patch)
        assert run(pin, factory) == POISONED
    assert factory.calls == [] and w.nt.calls == before
    assert attempts(pin) == [record] and attempts(pin)[0] is record


# -- the factory path --


@pytest.mark.parametrize(
    ("scenario", "label"),
    [("approved", "VERIFIED_APPROVED"), ("rejected_at_1", "VERIFIED_REJECTED")],
)
def test_the_factory_gets_the_same_pinned_namespace_once(
    pin: SimpleNamespace, scenario: str, label: str
) -> None:
    w = world(pin, scenario)
    seen: list[Any] = []
    api = typed_api(pin, w.api, seen)
    factory = Factory(pin, result=api)
    with sealed(pin):
        result = run(pin, factory)
    sha = pin.shared["sha"]
    assert result == (label, "OK", sha(w.bundle.summary_raw), sha(w.bundle.transport_raw))
    (record,) = attempts(pin)
    assert len(factory.calls) == 1 and factory.calls[0] is record.native
    assert factory.observed == [(True, None, None)]  # latched before; api/backend after
    assert record.factory is factory and record.factory_started is True
    assert record.api is api
    backend = record.backend
    assert type(backend) is factory.declared["_Win32Backend"]
    assert backend._ops["create"] is api.create  # the constructor saw the returned api
    assert backend._handle is record.collector["Handle"]
    assert record.collector["_backend"]() is backend
    attributes, iosb = factory.declared["OBJECT_ATTRIBUTES"], factory.declared["IO_STATUS_BLOCK"]
    assert record.native["OBJECT_ATTRIBUTES"] is attributes
    create_types = factory.declared["PROTOTYPES"]["NtCreateFile"][1]
    assert create_types[2] is ctypes.POINTER(attributes)
    assert create_types[3] is ctypes.POINTER(iosb)
    assert seen and all(types[1:] == (attributes, iosb) for types in seen)
    assert all(types[0] is ctypes.c_void_p for types in seen)
    assert record.collector["_POISON"] == [] and record.collector["_ACTIVE"] == []
    assert backend._retained == [] and backend._open == {}
    assert_originals_untouched(pin)
    assert_consumed(pin, w.nt, record)


def test_a_factory_returning_none_is_unavailable_and_consumes(pin: SimpleNamespace) -> None:
    w = world(pin)
    factory = Factory(pin, result=None)
    with sealed(pin):
        assert run(pin, factory) == UNAVAILABLE
    (record,) = attempts(pin)
    assert len(factory.calls) == 1 and record.factory_started is True
    assert record.api is None and record.backend is None
    assert record.collector["_backend"]() is None
    assert record.collector["_POISON"] == [] and record.collector["_ACTIVE"] == []
    assert w.nt.calls == []
    assert_consumed(pin, w.nt, record)


@pytest.mark.parametrize("shape", ["empty", "incomplete", "not-callable"])
def test_a_malformed_returned_api_is_internal_and_retained(
    pin: SimpleNamespace, shape: str
) -> None:
    w = world(pin)
    if shape == "empty":
        returned: Any = SimpleNamespace()
    elif shape == "incomplete":
        returned = SimpleNamespace(create=w.api.create)
    else:
        operations = {name: getattr(w.api, name) for name in pin.helpers["API_OPERATIONS"]}
        operations["close"] = "not-callable"
        returned = SimpleNamespace(**operations)
    factory = Factory(pin, result=returned)
    with sealed(pin):
        assert run(pin, factory) == INTERNAL
    (record,) = attempts(pin)
    assert record.factory is factory and record.api is returned and record.backend is None
    assert factory.calls[0] is record.native
    assert w.nt.calls == []
    assert_consumed(pin, w.nt, record)


def test_an_ordinary_factory_failure_is_closed_and_retained(
    pin: SimpleNamespace, capsys: Any
) -> None:
    w = world(pin)
    sentinel = pin.shared["SENTINEL"]
    factory = Factory(pin, error=OSError(sentinel))
    with sealed(pin):
        result = run(pin, factory)
    assert result == INTERNAL
    (record,) = attempts(pin)
    assert record.factory is factory and record.factory_started is True
    assert record.api is None and record.backend is None
    captured = capsys.readouterr()
    for text in (repr(result), repr(record), captured.out, captured.err):
        assert sentinel not in text
    assert_consumed(pin, w.nt, record)


def test_control_during_the_factory_propagates_and_keeps_the_record(pin: SimpleNamespace) -> None:
    w = world(pin)
    signal = Signal()
    factory = Factory(pin, error=signal)
    with sealed(pin), pytest.raises(Signal) as caught:
        run(pin, factory)
    assert caught.value is signal
    signal.__traceback__ = None
    del caught
    (record,) = attempts(pin)
    assert record.factory is factory and record.factory_started is True
    assert factory.calls == [record.native]
    assert record.api is None and record.backend is None
    assert w.nt.calls == []
    assert_consumed(pin, w.nt, record)


def test_control_before_the_factory_keeps_it_unstarted(pin: SimpleNamespace) -> None:
    w = world(pin)
    signal = Signal()
    factory = Factory(pin, result=w.api)
    real_compile = builtins.compile
    count = [0]

    def interrupted(source: Any, *args: Any, **kwargs: Any) -> Any:
        count[0] += 1
        if count[0] == 2:  # the backend source: after the record, before the factory
            raise signal
        return real_compile(source, *args, **kwargs)

    with sealed(pin) as patch:
        patch.setattr(builtins, "compile", interrupted)
        with pytest.raises(Signal) as caught:
            run(pin, factory)
    assert caught.value is signal
    signal.__traceback__ = None
    del caught
    (record,) = attempts(pin)
    assert record.factory is factory and record.factory_started is False
    assert factory.calls == [] and record.api is None and record.backend is None
    assert_consumed(pin, w.nt, record)


def test_interruption_before_any_exec_already_holds_the_factory(pin: SimpleNamespace) -> None:
    w = world(pin)
    signal = Signal()
    factory = Factory(pin, result=w.api)
    received: list[Any] = []

    def interrupted(_code: Any, namespace: Any = None, *_rest: Any) -> Any:
        received.append(namespace)
        raise signal

    with sealed(pin) as patch:
        patch.setattr(builtins, "exec", interrupted)
        with pytest.raises(Signal) as caught:
            run(pin, factory)
    assert caught.value is signal
    signal.__traceback__ = None
    del caught
    (record,) = attempts(pin)
    assert received == [record.collector]
    assert record.factory is factory and record.factory_started is False
    assert set(record.native) <= {"__name__"} and factory.calls == []
    assert_consumed(pin, w.nt, record)


class ControlApi:
    """A returned api whose every operation lookup is interrupted."""

    def __init__(self, signal: BaseException) -> None:
        self.signal = signal

    def __getattr__(self, _name: str) -> Any:
        raise self.signal


def test_control_after_the_factory_keeps_the_returned_api(pin: SimpleNamespace) -> None:
    w = world(pin)
    signal = Signal()
    returned = ControlApi(signal)
    factory = Factory(pin, result=returned)
    with sealed(pin), pytest.raises(Signal) as caught:
        run(pin, factory)
    assert caught.value is signal
    signal.__traceback__ = None
    del caught
    (record,) = attempts(pin)
    assert record.factory_started is True and record.api is returned
    assert record.backend is None and record.collector["_backend"]() is None
    assert_consumed(pin, w.nt, record)


def test_a_reentrant_call_from_the_factory_is_refused(pin: SimpleNamespace) -> None:
    w = world(pin)
    inner: list[Any] = []

    def reentrant(_namespace: Any) -> Any:
        inner.append(run(pin, Factory(pin, result=w.api)))
        inner.append(pin.run(pin.collector_src, pin.backend_src, w.api, NONCE, ARGV0))
        return w.api

    with sealed(pin):
        result = run(pin, reentrant)
    assert inner == [POISONED, POISONED]
    assert result[:2] == ("VERIFIED_APPROVED", "OK")
    (record,) = attempts(pin)
    assert record.factory is reentrant
    assert_consumed(pin, w.nt, record)


def test_uncertain_close_after_a_factory_is_retained(pin: SimpleNamespace) -> None:
    w = world(pin)
    w.nt.hooks[("close", "poc")] = pin.helpers["returns"](pin.helpers["INVALID_HANDLE"])
    with sealed(pin):
        assert run(pin, Factory(pin, result=w.api)) == ("INVALID", "COLLECT_CLEANUP", None, None)
    (record,) = attempts(pin)
    assert pin.shared["poisoned_by"](record)
    assert w.nt.calls.count(("close", "poc")) == 1
    assert_consumed(pin, w.nt, record)
