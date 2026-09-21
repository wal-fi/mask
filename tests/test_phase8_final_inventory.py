"""Exact approved Stage 8 inventory, including every nested control and message."""

import hashlib
import json
from pathlib import Path

import pytest

from maskgw.admin.ui.resources import load_resources

APPROVED = {
    "bindings": "c08a773fe9de394429933bee3f137102bcec60922862114d68ff2ca7c1e9ba59",
    "calls": "5c67bafcbcefd0ccd6f2d9bdbe645fa56bed81563589b367c500ed19b6720aba",
    "editors": "4fbef20c88adcd761262f770b4663f2fecc5547a92f45a55033ab2d45308b650",
    "format": "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
    "messages": "31fa9cd475478ca543430495da55a15fdd1484804a9920e7185eaabea7c25327",
    "models": "19a8807f047580d787109e36b717a8cb1eb3829ecc63792987e7979d633bfed1",
    "views": "3e236ca17a0ea5f9d7f487f396d3ec7f11923635e999792654d560e8db5b687a",
}


def sealed(document: dict[str, object]) -> dict[str, str]:
    return {
        key: hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        for key, value in document.items()
    }


def test_all_inventory_sections_equal_approved_stage8():
    public = load_resources()["presentation.json"]
    private = Path("frontend/private/presentation.json").read_bytes()
    assert public == private
    document = json.loads(public)
    assert sealed(document) == APPROVED
    assert {k: len(v) for k, v in document.items() if isinstance(v, list)} == {
        "bindings": 56,
        "calls": 19,
        "editors": 8,
        "messages": 25,
        "models": 110,
        "views": 6,
    }
    controls = [c for group in document["views"] + document["editors"] for c in group["controls"]]
    assert len(controls) == len({c["id"] for c in controls}) == 48
    writes = {
        (c["method"], c["path"])
        for c in document["calls"]
        if c["operation"] not in {"read", "check"}
    }
    assert writes == {
        ("POST", "/admin/v1/config:adopt"),
        ("POST", "/admin/v1/rules:reorder"),
        ("POST", "/admin/v1/rules"),
        ("PUT", "/admin/v1/rules/{rule_id}"),
        ("DELETE", "/admin/v1/rules/{rule_id}"),
        ("POST", "/admin/v1/exceptions"),
        ("PUT", "/admin/v1/exceptions/{exception_id}"),
        ("DELETE", "/admin/v1/exceptions/{exception_id}"),
        ("PUT", "/admin/v1/database"),
        ("PUT", "/admin/v1/sql"),
    }


@pytest.mark.parametrize("section", APPROVED)
@pytest.mark.parametrize("change", ["absent", "unknown", "modified"])
def test_inventory_seal_detects_every_section_counterexample(section, change):
    document = json.loads(load_resources()["presentation.json"])
    if change == "absent":
        del document[section]
    elif change == "unknown":
        document["unexpected"] = document[section]
    elif section == "format":
        document[section] += 1
    else:
        document[section][0]["unexpected"] = True
    assert sealed(document) != APPROVED
