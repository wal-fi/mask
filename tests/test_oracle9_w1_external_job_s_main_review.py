"""Review regressions for the S main loader (source review R1 under SM-R4).

``_load_entry`` resolves its own file path before reading the pinned entry. A scoped
stdlib ``Path.resolve`` port (only for the main's own source path) shows that:

* an ORDINARY failure there must surface as the exact closed ``SMainLoadError`` with the
  fixed ``S_MAIN_LOAD`` args, no cause/context and no trace of the original error;
* a CONTROL there must propagate as the SAME object, never inspected or wrapped.

The REAL loaded source and a fresh own holder are used, with the accepted native traps;
no fake entry/Owner, product patch, main, park or native effect. Helpers of the frozen
tests are reused unchanged.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests import test_oracle9_w1_external_job_adoption as xj
from tests import test_oracle9_w1_external_job_entry as et
from tests import test_oracle9_w1_external_job_s_main as sm
from tests import test_oracle9_w1_supervisor_qualification as qbase

SOURCE_KEY = os.path.normcase(str(sm.SOURCE))


def _resolve_port(patch: pytest.MonkeyPatch, failure: BaseException) -> list[str]:
    """Scoped stdlib port: ``resolve`` of the main's own path raises ``failure``."""
    real = Path.resolve
    hits: list[str] = []

    def resolve(self: Path, *args: Any, **kwargs: Any) -> Path:
        if et._same_path(self, SOURCE_KEY):
            hits.append("resolve")
            raise failure
        return real(self, *args, **kwargs)

    patch.setattr(Path, "resolve", resolve)
    return hits


def test_review_resolve_os_error_is_the_closed_load_error(monkeypatch: Any) -> None:
    namespace = sm.main_namespace()
    xj.native_traps(monkeypatch)
    holder = namespace["SHolder"]()
    original = OSError(sm.CANARY)
    with monkeypatch.context() as patch:
        hits = _resolve_port(patch, original)
        error = xj.error_of(lambda: namespace["_load_entry"](holder))
    assert hits == ["resolve"]  # the ordinary failure really happened at this port
    sm.loader_refusal(namespace, holder, error)  # exact type, S_MAIN_LOAD, no chain
    assert error is not original and sm.CANARY not in repr(error)
    assert holder.entry is None and holder.adoption is None


CONTROLS: dict[str, Callable[[list[str]], BaseException]] = {
    "kernel": lambda _probes: xj.KernelCtl(),
    "false": qbase.FalseCtl,
    "boom": qbase.BoomCtl,
}


@pytest.mark.parametrize("kind", sorted(CONTROLS))
def test_review_resolve_control_propagates_by_identity(monkeypatch: Any, kind: str) -> None:
    namespace = sm.main_namespace()
    xj.native_traps(monkeypatch)
    holder = namespace["SHolder"]()
    probes: list[str] = []
    control = CONTROLS[kind](probes)
    with monkeypatch.context() as patch:
        hits = _resolve_port(patch, control)
        outcome = xj.error_of(lambda: namespace["_load_entry"](holder))
    assert hits == ["resolve"] and outcome is control and probes == []
    assert control.__cause__ is None and control.__context__ is None
    for name in sm.HOLDER_FIELDS:
        assert getattr(holder, name) is (False if name == "entered" else None), name
