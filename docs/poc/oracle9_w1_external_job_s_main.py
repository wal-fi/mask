"""Specific Windows S main and retaining park for the external job entry (SM3, SM-R1..R4).

Import only defines. ``main`` (reached only through the final ``__name__`` guard) creates
ONE empty ``SHolder``, captures the borrowed binary stdin/stdout ONCE and runs:

* phase A (``_run_s``): ``_inputs`` (pure; exit 2), ``_load_entry`` (the pinned sibling
  entry, same checked bytes, closed ``SMainLoadError``) and ``_prepare`` (Request from the
  SAME ``AdoptionLoad``, the fixed NATURAL profile, a fresh ``EntryCustody``). An ordinary
  failure keeps the FIRST error and exits 3; a control keeps the FIRST control and parks.
* phase C (``_enter``): one protected region with the re-entry guard, the four public
  custody guards, ``entered = True`` and the ONLY ``run_entry`` call, then the fixed exit
  table. Any escaping failure, RETAIN or a result outside the table parks.

Nothing here writes to stdout or stderr: the entry's single ack is the only stdout writer.
The park retains the holder (ports, entry, adoption, Request, custody with its Owner and
the first objects) for the life of S and swallows later controls without replacing the
first. Controls landing between bytecodes outside the protected regions, and the
interpreter's own shutdown, are residuals of the language: no containment, cleanup or
physical-lifetime claim is made. Not a native or product admission.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium.
"""

from __future__ import annotations

import hashlib
import re
import stat
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn

# Pinned sibling entry (b4826e0b), loaded by its checked bytes only.
_ENTRY_NAME: Final = "oracle9_w1_external_job_entry.py"
_ENTRY_SHA: Final = "b4826e0b649e37b485b4ca065e225e1103cbd41e19836c2ac95ca78172a62e18"
_ENTRY_LIMIT: Final = 65536
_MODULE_NAME: Final = "_w1_s_main_entry"
_REPARSE_POINT: Final = 0x400

# Fixed NATURAL profile and path domain: statically equal to the pinned reviewed sources.
_ENV: Final = (("W1_NATIVE_PROBE", "1"),)
_NATURAL_CODE: Final = "print('MASKGW-W1-SUPERVISOR-NATURAL')"
_PATH_LIMIT: Final = 1024
_COMMAND_LIMIT: Final = 2048
_LOCAL_PATTERN: Final = r"[A-Za-z]:[\\/][^\x00\"\r\n]*"
_PARK_SLICE_S: Final = 60.0

_EXITS: Final = {
    "DONE": 0,
    "DONE_NONZERO": 10,
    "REFUSED": 11,
    "SETUP_REFUSED": 12,
    "ACK_FAILED": 13,
    "REJECTED": 14,
}


class SMainLoadError(Exception):
    """Closed ordinary refusal of ``_load_entry``: fixed text, never a path or a cause."""

    def __init__(self) -> None:
        super().__init__("S_MAIN_LOAD")


@dataclass(slots=True, repr=False)
class SHolder:
    """The ONE caller-owned holder of S: references only, retained until S ends."""

    reader: Any = None
    writer: Any = None
    entry: types.ModuleType | None = None
    adoption: Any = None
    request: Any = None
    custody: Any = None
    entered: bool = False
    result: object = None
    first_error: Exception | None = None
    first_control: BaseException | None = None

    def __repr__(self) -> str:
        return "SHolder(<redacted>)"


# ---------------------------------------------------------------- phase A pieces


def _natural_command(application: str) -> str:
    return '"' + application + '" -I -B -S -c "' + _NATURAL_CODE + '"'


def _inputs(argv: object) -> tuple[str, str] | None:
    """Pure: exactly two exact local absolute paths; no filesystem or environment."""
    if type(argv) is not list or len(argv) != 2:
        return None
    application, directory = argv
    for value in (application, directory):
        if type(value) is not str or not 0 < len(value) <= _PATH_LIMIT:
            return None
        if re.fullmatch(_LOCAL_PATTERN, value) is None:
            return None
    if len(_natural_command(application)) > _COMMAND_LIMIT:
        return None
    return application, directory


def _entry_bytes(path: Path) -> bytes | None:
    """One bounded read of a regular non-reparse file with the pinned SHA; None otherwise.

    Ordinary failures become None; controls propagate unchanged.
    """
    raw: bytes | None = None
    try:
        info = path.lstat()
        regular = stat.S_ISREG(info.st_mode) and info.st_size <= _ENTRY_LIMIT
        reparse = getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        if regular and not reparse:
            with path.open("rb") as stream:
                raw = stream.read(_ENTRY_LIMIT + 1)
            if len(raw) != info.st_size:
                raw = None
    except Exception:
        raw = None
    if raw is None or hashlib.sha256(raw).hexdigest() != _ENTRY_SHA:
        return None
    return raw  # the checked bytes are the only bytes ever executed


def _load_entry(holder: SHolder) -> None:
    """Executes the SAME checked entry bytes, then its own ``load_adoption`` once.

    The module name is registered only while those bytes execute (the entry's dataclasses
    resolve annotations through it) and removed only if it is still this module; an
    existing binding is refused and left untouched. Ordinary failures raise the closed
    ``SMainLoadError`` outside any handler; controls propagate by identity, unrecorded.
    """
    path: Path | None = None
    try:
        path = Path(__file__).resolve().parent / _ENTRY_NAME
    except Exception:
        path = None  # ordinary failure preparing the path: closed refusal below
    if path is None:
        raise SMainLoadError()
    raw = _entry_bytes(path)
    if raw is None:
        raise SMainLoadError()
    modules = sys.modules
    if _MODULE_NAME in modules:
        raise SMainLoadError()
    module = types.ModuleType(_MODULE_NAME)
    module.__dict__["__file__"] = str(path)
    failed = False
    try:
        modules[_MODULE_NAME] = module
        exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    except Exception:
        failed = True
    finally:
        if modules.get(_MODULE_NAME) is module:
            del modules[_MODULE_NAME]
    if failed:
        raise SMainLoadError()
    adoption: object = None
    try:
        adoption = module.load_adoption()
    except Exception:
        failed = True
    if failed or adoption is None:
        raise SMainLoadError()
    holder.entry = module
    holder.adoption = adoption


def _prepare(holder: SHolder, application: str, directory: str) -> None:
    """Pure: the Request of the SAME AdoptionLoad and a fresh custody; no SDK."""
    entry, adoption = holder.entry, holder.adoption
    if entry is None or adoption is None:
        raise SMainLoadError()
    holder.request = adoption.Request(
        application=application,
        command_line=_natural_command(application),
        environment=_ENV,
        directory=directory,
    )
    holder.custody = entry.EntryCustody()


# ---------------------------------------------------------------- phase C


def _enter(holder: SHolder) -> int | None:
    """ONE protected region: guards, ``entered``, the only ``run_entry`` call, mapping."""
    try:
        if holder.entered is not False:
            return None
        entry: Any = holder.entry
        custody = holder.custody
        if type(custody) is not entry.EntryCustody:
            return None
        if custody.claimed is not False:
            return None
        if custody.owner is not None:
            return None
        if custody.first_control is not None:
            return None
        holder.entered = True
        holder.result = entry.run_entry(
            holder.adoption,
            holder.request,
            holder.reader,
            holder.writer,
            entry.MAX_TURNS,
            custody,
        )
        result = holder.result
        if type(result) is not str:
            return None
        return _EXITS.get(result)
    except Exception as error:
        if holder.first_error is None:
            holder.first_error = error
        return None
    except BaseException as control:
        if holder.first_control is None and (
            holder.custody is None or holder.custody.first_control is None
        ):
            holder.first_control = control
        return None


def _run_s(argv: object, holder: SHolder) -> int | None:
    """Phase A (exit 2/3 or park), then phase C OUTSIDE region A; None means park."""
    try:
        values = _inputs(argv)
        if values is None:
            return 2
        _load_entry(holder)
        _prepare(holder, values[0], values[1])
    except Exception as error:
        if holder.first_error is None:
            holder.first_error = error
        return 3
    except BaseException as control:
        if holder.first_control is None and (
            holder.custody is None or holder.custody.first_control is None
        ):
            holder.first_control = control
        return None
    return _enter(holder)


# ---------------------------------------------------------------- park and main


def _park_s(holder: SHolder) -> NoReturn:
    """Retains the holder for the life of S; swallows later controls; never releases."""
    retained = holder
    while True:
        try:
            while retained is not None:
                time.sleep(_PARK_SLICE_S)
        except BaseException:
            continue


def main(argv: list[str]) -> int:
    holder = SHolder()
    code: int | None = None
    try:
        holder.reader, holder.writer = sys.stdin.buffer, sys.stdout.buffer
        code = _run_s(argv, holder)
    except Exception as error:
        if holder.first_error is None:
            holder.first_error = error
        code = 3 if holder.entered is False else None
    except BaseException as control:
        if holder.first_control is None and (
            holder.custody is None or holder.custody.first_control is None
        ):
            holder.first_control = control
        code = None
    if code is None:
        _park_s(holder)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
