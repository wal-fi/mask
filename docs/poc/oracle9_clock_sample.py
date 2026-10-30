"""Read-only Windows boot/tick/UTC sampler; no Desktop/Docker action on import.

Uses the same pinned bounded-process primitive as previous lab procedures.
Both future PowerShell controls and runner B invoke THIS sampler, not a second
P/Invoke implementation. No secrets, service control, registry or fallback.
"""

import asyncio
import ctypes
import hashlib
import json
from pathlib import Path
import stat
import sys

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "docs/poc/run_linux_as_probe.py"
HELPER_SHA = "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627"
CORE = REPO / "docs/poc/oracle9_cycle_freshness.py"
CORE_SHA = "d2b485c29d2cef36599af51fc342ac39a991f9564bb919baa18d3cb1ff7e5b66"
POWERSHELL = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
POWERSHELL_SHA = "60c9b29843624dd8af6b6a7b26147753be6aeef65098b9a503cc50850afe410f"
BOOT_COMMAND = (
    "$ErrorActionPreference='Stop';$WarningPreference='SilentlyContinue';"
    "$InformationPreference='SilentlyContinue';$ProgressPreference='SilentlyContinue';"
    "$b=(Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime;"
    "if(@($b).Count -ne 1 -or $b -isnot [DateTime]){exit 2};"
    "[Console]::Out.Write($b.ToUniversalTime().ToFileTimeUtc().ToString("
    "[Globalization.CultureInfo]::InvariantCulture))"
)


def need(value):
    if not value:
        raise ValueError("CLOCK_REFUSED")


def pinned(path, expected, maximum):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400)
    need(info.st_size <= maximum)
    raw = path.read_bytes()
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected)
    return raw


def frozen(path, expected, name):
    raw = pinned(path, expected, 65536)
    ns = {"__name__": name, "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), ns)
    return ns


def environment():
    return {
        "SystemRoot": "C:\\Windows",
        "WINDIR": "C:\\Windows",
        "SystemDrive": "C:",
        "COMSPEC": "C:\\Windows\\System32\\cmd.exe",
        "PATH": "C:\\Windows\\System32;C:\\Windows",
    }


def _bindings():
    need(sys.platform == "win32")
    dll = ctypes.WinDLL("kernel32.dll", use_last_error=True)

    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    tick = dll.GetTickCount64
    tick.argtypes, tick.restype = [], ctypes.c_uint64
    utc = dll.GetSystemTimeAsFileTime
    utc.argtypes, utc.restype = [ctypes.POINTER(FileTime)], None
    value = FileTime()
    tick_ms = tick()
    utc(ctypes.byref(value))
    return tick_ms, (int(value.high) << 32) | int(value.low)


async def sample():
    need(sys.platform == "win32")
    core = frozen(CORE, CORE_SHA, "_clock_core")
    helper = frozen(HELPER, HELPER_SHA, "_clock_bounded")
    helper["environment"] = environment  # public fixed env only, no mutation of host env
    pinned(POWERSHELL, POWERSHELL_SHA, 2 * 1024 * 1024)
    code, raw = await helper["bounded"](
        [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", BOOT_COMMAND],
        timeout=8,
        limit=256,
    )
    need(code == 0 and type(raw) is bytes and 0 < len(raw) <= 20)
    boot = raw.decode("ascii")
    need(core["number"](boot, core["MAX_FILETIME"]) > 0)
    ticks, utc = _bindings()  # boot first, then native tick and UTC
    result = core["Sample"](boot, str(ticks), str(utc))
    pinned(POWERSHELL, POWERSHELL_SHA, 2 * 1024 * 1024)
    pinned(CORE, CORE_SHA, 65536)
    pinned(HELPER, HELPER_SHA, 65536)
    return {
        "kind": "maskgw-windows-cycle-clock-v1",
        "boot": result.boot,
        "tick_ms": result.tick_ms,
        "utc_100ns": result.utc_100ns,
    }


def main():
    if (
        sys.platform != "win32"
        or sys.flags.optimize
        or sys.flags.isolated != 1
        or sys.flags.dont_write_bytecode != 1
        or len(sys.argv) != 1
    ):
        return 2
    value = None
    try:
        value = asyncio.run(sample())
    except BaseException:
        pass
    if value is None:
        print('{"kind":"maskgw-windows-cycle-clock-v1","outcome":"REFUSED"}')
        return 1
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
