"""Limited C1 installed-module probe; dependencies use the existing interpreter.

Not a full application, dependency-isolated or OS-containment certification.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


def run(target: Path, checkout: Path) -> dict[str, Any]:
    if (
        not checkout.is_absolute()
        or target.is_relative_to(checkout)
        or Path.cwd().is_relative_to(checkout)
    ):
        raise ValueError("probe must run outside checkout")
    if not target.is_absolute() or not (target / "maskgw/runtime/domain.py").is_file():
        raise ValueError("missing installed C1")
    sys.path.insert(0, str(target))
    domain = importlib.import_module("maskgw.runtime.domain")
    budget = importlib.import_module("maskgw.runtime.budget")
    origins = {}
    matched = 0
    for name, module in tuple(sys.modules.items()):
        if name == "maskgw" or name.startswith("maskgw."):
            source = getattr(module, "__file__", None)
            if type(source) is not str or not Path(source).resolve().is_relative_to(target):
                raise ValueError("wrong module origin")
            installed = Path(source).resolve()
            reviewed = checkout / "src" / installed.relative_to(target)
            if installed.read_bytes() != reviewed.read_bytes():
                raise ValueError("installed module differs from reviewed source")
            matched += 1
    for name, module in (("domain", domain), ("budget", budget)):
        filename = module.__file__
        if type(filename) is not str:
            raise ValueError("missing module origin")
        origins[name] = hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    q = domain.Quantity.VIRTUAL_ADDRESS_SPACE
    costs = tuple(
        domain.Cost(index, owner, domain.CostLocation.IN_DOMAIN, q, size, count)
        for index, owner, size, count in (
            (1, domain.CostOwner.BASE, 200, 1),
            (2, domain.CostOwner.HEADROOM, 100, 1),
            (3, domain.CostOwner.WORKER, 256, 2),
            (4, domain.CostOwner.PARENT, 256, 2),
            (5, domain.CostOwner.CANDIDATE, 50, 1),
            (6, domain.CostOwner.GENERATION, 50, 2),
            (7, domain.CostOwner.AUXILIARY, 64, 1),
        )
    )
    plan = domain.CostPlan(q, costs, 1, 2, 1, 1, 0, 1, None, 80, 40)
    limits = budget.BudgetLimits(10000, 200, 100, 8, 2, 2, 1, 2, 1)
    results = {}
    for profile in (domain.LINUX_HELD_AS128, domain.WINDOWS_JOB_PRIVATE32):
        result = domain.reconcile(profile, plan, limits)
        if result.ready or domain.DomainReason.AGGREGATE_UNPROVEN not in result.reasons:
            raise ValueError("unsafe profile verdict")
        results[profile.name] = tuple(reason.value for reason in result.reasons)
    return {
        "python": sys.version.split()[0],
        "known_profiles_not_ready": results,
        "module_hashes": origins,
        "source_match": True,
        "matched_module_count": matched,
        "maskgw_outside_checkout": True,
        "dependencies": "existing interpreter, not isolated",
    }


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()), sort_keys=True))
