"""Specific T4 process identity and fixed PS template; no native calls on import."""

import base64
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
import sys

SHELL = "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


class IdentityError(Exception):
    def __init__(self):
        super().__init__("IDENTITY_UNKNOWN")


def need(ok):
    if not ok:
        raise IdentityError() from None


@dataclass(frozen=True)
class Birth:
    pid: int
    filetime: int

    def __post_init__(self):
        need(type(self.pid) is int and 0 < self.pid < 2**32)
        need(type(self.filetime) is int and 0 < self.filetime < 2**63)


def raw_filetime(handle):
    """Borrow the ORIGINAL Popen handle; never open by PID or close the handle."""
    need(sys.platform == "win32" and sys.version_info[:3] == (3, 11, 3))
    need(isinstance(handle, int) and type(handle) is not bool and handle > 0)
    failed = False
    value = None
    try:
        function = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessTimes
        function.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        function.restype = wintypes.BOOL
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        success = function(
            wintypes.HANDLE(handle),
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not success:
            failed = True
        else:
            value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    except Exception:
        failed = True
    if failed:
        raise IdentityError() from None
    need(type(value) is int and 0 < value < 2**63)
    return value


def capture(process):
    """Call synchronously immediately after start returns OR raises with an adopted process."""
    result = None
    try:
        if process is not None:
            result = Birth(process.pid, raw_filetime(process._transport._proc._handle))
    except Exception:
        pass
    return result  # absence retains uncertainty; never guess a PID


def kill_script(birth):
    need(type(birth) is Birth)
    # Numeric validated literals only. One Process, forced retained handle, no PID reopen for kill.
    return (
        "$ErrorActionPreference='Stop'\n"
        "$p=$null;$status='ERROR';$observed=$null;$missing=$false\n"
        "try {\n"
        " try { $p=[System.Diagnostics.Process]::GetProcessById(" + str(birth.pid) + ") }\n"
        " catch [System.ArgumentException] { $missing=$true }\n"
        " if($missing){$status='ABSENT'}else{\n"
        "  [void]$p.Handle\n"
        "  $observed=[int64]$p.StartTime.ToUniversalTime().ToFileTimeUtc()\n"
        "  if($observed -ne [int64]" + str(birth.filetime) + "){$status='IDENTITY_MISMATCH'}\n"
        "  elseif($p.HasExited){$status='ABSENT'}else{\n"
        "   $p.Kill();if($p.WaitForExit(3000)){$status='KILLED'}\n"
        "  }\n"
        " }\n"
        "}catch{$status='ERROR'}finally{if($null -ne $p){$p.Dispose()}}\n"
        "[pscustomobject]@{status=$status;pid="
        + str(birth.pid)
        + ";observed_filetime=if($null -eq $observed){$null}else{"
        "$observed.ToString([Globalization.CultureInfo]::InvariantCulture)}}"
        "|ConvertTo-Json -Compress\n"
    )


def kill_args(birth):
    script = kill_script(birth)
    return [
        SHELL,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
        base64.b64encode(script.encode("utf-16-le")).decode("ascii"),
    ]


def parse_report(raw, birth):
    need(type(birth) is Birth and type(raw) is bytes and 0 < len(raw) <= 512)
    failed = False
    value = None
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        failed = True
    if failed:
        raise IdentityError() from None
    need(type(value) is dict and set(value) == {"status", "pid", "observed_filetime"})
    need(type(value["pid"]) is int and value["pid"] == birth.pid)
    need(value["status"] in ("KILLED", "ABSENT", "IDENTITY_MISMATCH", "ERROR"))
    observed = value["observed_filetime"]
    need(
        observed is None
        or (
            type(observed) is str
            and observed.isascii()
            and observed.isdecimal()
            and 0 < int(observed) < 2**63
            and str(int(observed)) == observed
        )
    )
    if value["status"] == "KILLED":
        need(observed == str(birth.filetime))
    if value["status"] == "IDENTITY_MISMATCH":
        need(observed is not None and observed != str(birth.filetime))
    return value
