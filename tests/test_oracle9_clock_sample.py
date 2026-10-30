"""Sampler tests are fakes; no Windows API, shell, subprocess or CIM query."""

import asyncio
import ctypes
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/oracle9_clock_sample.py"


def setup(
    monkeypatch: pytest.MonkeyPatch, *, code: int = 0, raw: bytes = b"134370000000000000"
) -> tuple[Any, list[str]]:
    namespace = runpy.run_path(str(SOURCE))
    events: list[str] = []
    core = runpy.run_path(str(namespace["CORE"]))

    async def bounded(argv, **kwargs):
        events.append("boot")
        assert argv[1:5] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
        assert argv[5] == namespace["BOOT_COMMAND"]
        assert kwargs == {"timeout": 8, "limit": 256}
        return code, raw

    def frozen(path, _expected, _name):
        return core if path == namespace["CORE"] else {"bounded": bounded}

    def bindings():
        events.append("tick_utc")
        return 123456789, 134375000000000000

    namespace["sample"].__globals__["sys"] = SimpleNamespace(platform="win32")
    monkeypatch.setitem(namespace["sample"].__globals__, "frozen", frozen)
    monkeypatch.setitem(namespace["sample"].__globals__, "pinned", lambda *_: None)
    monkeypatch.setitem(namespace["sample"].__globals__, "_bindings", bindings)
    return namespace, events


def test_sample_order_and_exact_metadata(monkeypatch):
    ns, events = setup(monkeypatch)
    value = asyncio.run(ns["sample"]())
    assert events == ["boot", "tick_utc"]
    assert value == {
        "kind": "maskgw-windows-cycle-clock-v1",
        "boot": "134370000000000000",
        "tick_ms": "123456789",
        "utc_100ns": "134375000000000000",
    }
    assert set(ns["environment"]()) == {"SystemRoot", "WINDIR", "SystemDrive", "COMSPEC", "PATH"}


@pytest.mark.parametrize(
    "raw",
    [b"", b"1\n", b"01", b"-1", b"NaN", b"1" * 21, b"0", b"\xef\xbb\xbf1", str(1 << 63).encode()],
)
def test_bad_boot_never_calls_native_clock(monkeypatch, raw):
    ns, events = setup(monkeypatch, raw=raw)
    with pytest.raises((ValueError, UnicodeError)):
        asyncio.run(ns["sample"]())
    assert events == ["boot"]


def test_failed_cim_has_no_clock_or_utc_fallback(monkeypatch):
    ns, events = setup(monkeypatch, code=1)
    with pytest.raises(ValueError):
        asyncio.run(ns["sample"]())
    assert events == ["boot"]


def test_native_clock_error_propagates_to_refusing_entry(monkeypatch):
    ns, _ = setup(monkeypatch)

    def failure():
        raise OSError("PUBLIC_CLOCK_ERROR")

    monkeypatch.setitem(ns["sample"].__globals__, "_bindings", failure)
    with pytest.raises(OSError):
        asyncio.run(ns["sample"]())


def test_native_signatures_and_64bit_filetime_with_fake_dll(monkeypatch):
    ns = runpy.run_path(str(SOURCE))
    monkeypatch.setitem(ns["_bindings"].__globals__, "sys", SimpleNamespace(platform="win32"))
    events = []

    class Function:
        def __init__(self, kind: str) -> None:
            self.kind = kind
            self.argtypes: Any = None
            self.restype: Any = None

        def __call__(self, *args):
            events.append(self.kind)
            if self.kind == "tick":
                assert self.argtypes == [] and self.restype is ctypes.c_uint64
                return (1 << 63) + 3
            assert self.restype is None and len(self.argtypes) == 1
            args[0]._obj.low = 0x89ABCDEF
            args[0]._obj.high = 0x01234567
            return None

    dll = SimpleNamespace(GetTickCount64=Function("tick"), GetSystemTimeAsFileTime=Function("utc"))

    def load(name, **kwargs):
        assert name == "kernel32.dll" and kwargs == {"use_last_error": True}
        return dll

    monkeypatch.setattr(ctypes, "WinDLL", load, raising=False)
    assert ns["_bindings"]() == ((1 << 63) + 3, 0x0123456789ABCDEF)
    assert events == ["tick", "utc"]


@pytest.mark.parametrize("bad", ["platform", "optimize", "isolated", "bytecode", "args"])
def test_cli_refuses_before_sampling_with_wrong_flags(monkeypatch, bad):
    ns, events = setup(monkeypatch)
    flags = SimpleNamespace(
        optimize=int(bad == "optimize"),
        isolated=int(bad != "isolated"),
        dont_write_bytecode=int(bad != "bytecode"),
    )
    fake = SimpleNamespace(
        platform="linux" if bad == "platform" else "win32",
        flags=flags,
        argv=["clock"] if bad != "args" else ["clock", "unexpected"],
    )
    monkeypatch.setitem(ns["main"].__globals__, "sys", fake)
    assert ns["main"]() == 2 and not events
