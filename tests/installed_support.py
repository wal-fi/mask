"""Private package gate: refuse checkout imports and build-tool PATH fallback."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import maskgw


def verify_environment() -> None:
    """Called before and after every browser child in an isolated installation."""
    site = Path(os.environ["MASKGW_INSTALLED_SITE"]).resolve()
    checkout = Path(os.environ["MASKGW_CHECKOUT"]).resolve()
    assert sys.flags.isolated and not site.is_relative_to(checkout)
    assert not Path(sys.prefix).resolve().is_relative_to(checkout)
    assert all(not Path(p).resolve().is_relative_to(checkout) for p in sys.path)
    assert shutil.which("node") is None and shutil.which("npm") is None
    assert maskgw.__file__ is not None
    for name, module in tuple(sys.modules.items()):
        if name == "maskgw" or name.startswith("maskgw."):
            source = getattr(module, "__file__", None)
            assert source is not None and Path(source).resolve().is_relative_to(site / "maskgw")
