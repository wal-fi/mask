"""Exact approved inventory: Stage 8 (Phase 8) intact inside the Phase 9 format 2.

The Stage 8 seals are UNCHANGED. Since Phase 9, Stage 5 (D-097), the document
has format 2 and a read-only `console`; the v1 sections must still be
byte-for-byte the approved ones: views, editors, bindings and messages whole,
and the first 110 models and 19 calls as prefixes. What Stage 5 added is sealed
separately, so neither side can drift silently.
"""

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
STAGE8_MODELS = 110
STAGE8_CALLS = 19

#: Phase 9, Stage 5 additions, sealed separately.
STAGE5 = {
    "format": "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
    "console": "884b5047f0afcab8f3708b70e166f9eb66e599f808ff2bf40b2ad14c649d32f7",
    "models": "61e93e5c9089ede0149ae805e1d6eac5fde64974143b72d07d9bd82ada38623a",
    "calls": "edb0149496b9bf504c656d63667c84f70c1d719ca01f347902727330035b4d07",
}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def sealed(document: dict[str, object]) -> dict[str, str]:
    return {key: digest(value) for key, value in document.items()}


def stage8_view(document: dict[str, object]) -> dict[str, object]:
    """The Stage 8 sections as they exist inside format 2."""
    models = document["models"]
    calls = document["calls"]
    assert isinstance(models, list)
    assert isinstance(calls, list)
    return {
        "bindings": document["bindings"],
        "calls": calls[:STAGE8_CALLS],
        "editors": document["editors"],
        "format": 1,
        "messages": document["messages"],
        "models": models[:STAGE8_MODELS],
        "views": document["views"],
    }


def test_all_inventory_sections_equal_approved_stage8():
    public = load_resources()["presentation.json"]
    private = Path("frontend/private/presentation.json").read_bytes()
    assert public == private
    document = json.loads(public)
    assert set(document) == {*APPROVED, "console"}
    assert document["format"] == 2
    assert sealed(stage8_view(document)) == APPROVED
    assert {k: len(v) for k, v in document.items() if isinstance(v, list)} == {
        "bindings": 56,
        "calls": 23,
        "editors": 8,
        "messages": 25,
        "models": 147,
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


def test_stage5_additions_are_sealed_and_read_only():
    document = json.loads(load_resources()["presentation.json"])
    assert {
        "format": digest(document["format"]),
        "console": digest(document["console"]),
        "models": digest(document["models"][STAGE8_MODELS:]),
        "calls": digest(document["calls"][STAGE8_CALLS:]),
    } == STAGE5
    added = document["calls"][STAGE8_CALLS:]
    assert {(c["method"], c["path"], c["operation"], c["input"]) for c in added} == {
        ("GET", "/admin/v2/status", "read", None),
        ("GET", "/admin/v2/datasources", "read", None),
        ("GET", "/admin/v2/datasources/{datasource_id}", "read", None),
        ("GET", "/admin/v2/datasources/{datasource_id}/policy", "read", None),
    }
    # No role binding points into a second-prefix model (one version per v1 read).
    added_models = {m["id"] for m in document["models"][STAGE8_MODELS:]}
    assert not any(b["model"] in added_models for b in document["bindings"])


@pytest.mark.parametrize("section", APPROVED)
@pytest.mark.parametrize("change", ["absent", "unknown", "modified"])
def test_inventory_seal_detects_every_section_counterexample(section, change):
    document = stage8_view(json.loads(load_resources()["presentation.json"]))
    if change == "absent":
        del document[section]
    elif change == "unknown":
        document["unexpected"] = document[section]
    elif section == "format":
        document[section] = 2
    else:
        items = document[section]
        assert isinstance(items, list)
        items[0]["unexpected"] = True
    assert sealed(document) != APPROVED
