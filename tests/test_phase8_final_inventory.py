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

from maskgw.admin.http.v2.routes import V2_WRITE_ROUTES
from maskgw.admin.ui.protocol import V2_WRITES
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

#: Phase 9, Stage 5 additions, sealed separately. Console seal includes the
#: requested read-only presentation refinements (Masking and SQL; then grouped
#: detail tabs, declared tones and the detail title path; then `pages`, the
#: Portuguese grouped presentation of the six Política v1 readings). Only
#: `console` changed: format, second-prefix models and calls keep their seals,
#: and the Stage 8 sections above stay equal to `APPROVED`.
STAGE5 = {
    "format": "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
    "models": "61e93e5c9089ede0149ae805e1d6eac5fde64974143b72d07d9bd82ada38623a",
    "calls": "edb0149496b9bf504c656d63667c84f70c1d719ca01f347902727330035b4d07",
}
STAGE5_MODELS = 147
STAGE5_CALLS = 23

#: Phase 9, Stage 6 (D-103-D-106): the nine approved second-prefix writes, their
#: models and the declared forms. Appended after the Stage 5 slices, which keep
#: their seals; `console` now also carries actions, outcomes and reasons.
STAGE6 = {
    "console": "b7f3d675d4c81f13909eed28fdd097ad9f1183c32d0ed37e67e9ca93e97e0206",
    "models": "59646aa05382fafa151bf7d941872ef85a245116c4c53b189600ea77f998dfbd",
    "calls": "20d0adaa1774880d73f9ed30368ff82bb84530088555c5e365c07f6302698c03",
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
        "calls": 32,
        "editors": 8,
        "messages": 25,
        "models": 211,
        "views": 6,
    }
    controls = [c for group in document["views"] + document["editors"] for c in group["controls"]]
    assert len(controls) == len({c["id"] for c in controls}) == 48
    writes = {
        (c["method"], c["path"])
        for c in document["calls"][:STAGE8_CALLS]
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
        "models": digest(document["models"][STAGE8_MODELS:STAGE5_MODELS]),
        "calls": digest(document["calls"][STAGE8_CALLS:STAGE5_CALLS]),
    } == STAGE5
    added = document["calls"][STAGE8_CALLS:STAGE5_CALLS]
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


def test_stage6_writes_are_exactly_the_approved_inventory():
    document = json.loads(load_resources()["presentation.json"])
    assert {
        "console": digest(document["console"]),
        "models": digest(document["models"][STAGE5_MODELS:]),
        "calls": digest(document["calls"][STAGE5_CALLS:]),
    } == STAGE6
    added = document["calls"][STAGE5_CALLS:]
    assert {(c["method"], c["path"], c["operation"]) for c in added} == {
        ("POST", "/admin/v2/datasources", "register"),
        ("POST", "/admin/v2/datasources:test", "probe"),
        ("POST", "/admin/v2/datasources/{datasource_id}:test", "probe"),
        ("POST", "/admin/v2/datasources/{datasource_id}:rotate-credential", "renew"),
        ("POST", "/admin/v2/datasources/{datasource_id}:enable", "resume"),
        ("POST", "/admin/v2/datasources/{datasource_id}:disable", "pause"),
        ("PUT", "/admin/v2/datasources/{datasource_id}", "revise"),
        ("DELETE", "/admin/v2/datasources/{datasource_id}", "retire"),
        ("PUT", "/admin/v2/datasources/{datasource_id}/policy", "amend"),
    }
    assert all(c["input"] is not None for c in added)
    # The v1 views never offer a second-prefix write; no role binding points there.
    written = {c["id"] for c in added}
    assert not any(key in written for view in document["views"] for key in view["actions"])
    added_models = {m["id"] for m in document["models"][STAGE5_MODELS:]}
    assert not any(b["model"] in added_models for b in document["bindings"])


def test_stage6_inventory_mirrors_the_router():
    assert {(method, path) for method, path, _ in V2_WRITES} == {
        (method, path) for path, method in V2_WRITE_ROUTES
    }
