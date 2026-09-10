"""Etapa 2: artefatos independentes, gramática hostil e invariantes sem HTTP novo."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.http.app import READ_PATHS, VALIDATE_PATH, WRITE_ROUTES
from maskgw.admin.http.schemas import AdoptRequest, DatabaseWriteRequest, RuleCreateRequest
from maskgw.admin.ui import resources
from maskgw.admin.ui.protocol import InvalidPresentationError, parse_json, validate_presentation
from maskgw.admin.ui.resources import load_resources, validate_catalog
from maskgw.masking.transformers.registry import build_default_registry

ROOT = Path(__file__).resolve().parents[1]


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def document() -> dict[str, Any]:
    value: object = json.loads((ROOT / "frontend/private/presentation.json").read_bytes())
    assert isinstance(value, dict)
    return value


def test_package_catalog_is_exact_and_independent():
    data = load_resources()
    assert set(data) == {"index.html", "ui.js", "ui.css", "presentation.json"}
    result = validate_presentation(data["presentation.json"])
    validate_catalog(result)
    actual = {(c.path, c.method) for c in result.calls}
    expected = {(p, "GET") for p in READ_PATHS} | {(VALIDATE_PATH, "POST")}
    expected |= set(WRITE_ROUTES) - {("/admin/v1/config", "PUT")}
    assert actual == expected
    assert len(result.calls) == 19
    assert {e.name for e in result.editors} == set(build_default_registry().available())
    assert getattr(data, "__setitem__", None) is None


def test_catalog_refuses_valid_but_unauthorized_call():
    raw = document()
    raw["calls"][0]["path"] = "/admin/v1/unapproved"
    result = validate_presentation(encoded(raw))
    with pytest.raises(InvalidPresentationError):
        validate_catalog(result)


def test_catalog_refuses_rewired_schema():
    raw = document()
    raw["calls"][0]["output"] = raw["calls"][1]["output"]
    with pytest.raises(InvalidPresentationError):
        validate_catalog(validate_presentation(encoded(raw)))


@pytest.mark.parametrize(
    "data",
    [
        b"\xff",
        b"\xef\xbb\xbf{}",
        b'{"format":1,"format":1}',
        b'{"a":{"x":1,"x":2}}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1e309}',
        b'{"__proto__":{}}',
        b'{"a":{"constructor":{}}}',
    ],
)
def test_json_rejects_invalid_utf8_duplicate_keys_and_poison(data):
    with pytest.raises(InvalidPresentationError) as caught:
        parse_json(data)
    assert str(caught.value) == "Invalid presentation."
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("key", ["__proto__", "constructor", "prototype"])
def test_poison_structural_fields_and_segments(key):
    raw = document()
    raw["views"][0]["controls"][0]["path"] = [key]
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))
    raw = document()
    obj = next(n for n in raw["models"] if n["shape"]["type"] == "object")
    obj["shape"]["fields"][0]["name"] = key
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_poison_text_is_not_reinterpreted():
    raw = document()
    raw["messages"][0]["text"] = "__proto__ constructor prototype <img src=x onerror=alert(1)>"
    validate_presentation(encoded(raw))


@pytest.mark.parametrize("value", [True, 1.0, "1", 2, None])
def test_format_is_exact_integer(value):
    raw = document()
    raw["format"] = value
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.invalid/admin/v1/status",
        "//evil.invalid/admin/v1/status",
        "/admin/v1/../status",
        "/admin/v1/%73tatus",
        "/admin/v1/status?x=1",
        "/admin/v1/status#x",
        "/admin/v1/\\status",
        "/admin/v1//status",
        "/admin/v1/{rule_id}/{rule_id}",
    ],
)
def test_destination_restrictions(path):
    raw = document()
    raw["calls"][0]["path"] = path
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


@pytest.mark.parametrize(
    "shape",
    [
        {"type": "nullable", "item": "m0"},
        {"type": "nullable", "item": "m999"},
        {"type": "integer", "min": 9, "max": 8},
        {"type": "integer", "max": 9007199254740992},
        {"type": "enum", "choices": ["a", "a"]},
        {"type": "javascript", "source": "x"},
    ],
)
def test_cycles_references_and_shapes(shape):
    raw = document()
    raw["models"][0]["shape"] = shape
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_definition_limit_is_inclusive():
    raw = document()
    while len(raw["models"]) < 128:
        raw["models"].append({"id": f"m{len(raw['models'])}", "shape": {"type": "boolean"}})
    validate_presentation(encoded(raw))
    raw["models"].append({"id": "m128", "shape": {"type": "boolean"}})
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_depth_limit_is_inclusive_and_dag_is_bounded():
    raw = document()
    for i in range(16):
        shape = {"type": "boolean"} if i == 15 else {"type": "nullable", "item": f"m{201 + i}"}
        raw["models"].append({"id": f"m{200 + i}", "shape": shape})
    validate_presentation(encoded(raw))
    raw["models"].append({"id": "m199", "shape": {"type": "nullable", "item": "m200"}})
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_controls_limit_is_inclusive():
    raw = document()
    total = sum(len(v["controls"]) for v in raw["views"] + raw["editors"])
    sample = raw["views"][0]["controls"][0]
    for i in range(512 - total):
        raw["views"][0]["controls"].append({**sample, "id": f"k{1000 + i}"})
    validate_presentation(encoded(raw))
    raw["views"][0]["controls"].append({**sample, "id": "k9999"})
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


@pytest.fixture
def resource_copy(tmp_path, monkeypatch):
    source = files("maskgw.admin.ui").joinpath("assets")
    for item in source.iterdir():
        if item.is_file():
            (tmp_path / item.name).write_bytes(item.read_bytes())
    monkeypatch.setattr(resources, "files", lambda _name: tmp_path.parent)

    # Public loader appends assets; map only that exact traversal in the fixture.
    class Local:
        def joinpath(self, name):
            assert name == "assets"
            return tmp_path

    monkeypatch.setattr(resources, "files", lambda _name: Local())
    return tmp_path


@pytest.mark.parametrize(
    "name", ["index.html", "ui.js", "ui.css", "presentation.json", "manifest.json"]
)
def test_each_resource_corruption_fails_closed(resource_copy, name):
    (resource_copy / name).write_bytes(b"SENSITIVE_MARKER")
    with pytest.raises(InvalidPresentationError) as caught:
        load_resources()
    assert str(caught.value) == "Invalid presentation."
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    "name", ["index.html", "ui.js", "ui.css", "presentation.json", "manifest.json"]
)
def test_each_resource_missing_fails_closed(resource_copy, name):
    (resource_copy / name).unlink()
    with pytest.raises(InvalidPresentationError):
        load_resources()


def test_loaded_bytes_are_immutable_and_do_not_follow_disk(resource_copy):
    loaded = load_resources()
    before = loaded["ui.js"]
    (resource_copy / "ui.js").write_bytes(b"changed")
    assert loaded["ui.js"] == before
    with pytest.raises(InvalidPresentationError):
        load_resources()


@pytest.mark.parametrize(
    "mutation", ["extra", "missing", "duplicate", "path", "mime", "size", "format"]
)
def test_manifest_semantics_beyond_hash(resource_copy, monkeypatch, mutation):
    path = resource_copy / "manifest.json"
    raw = json.loads(path.read_bytes())
    if mutation == "extra":
        raw["extra"] = 1
    elif mutation == "missing":
        raw["entries"].pop()
    elif mutation == "duplicate":
        raw["entries"][1] = copy.deepcopy(raw["entries"][0])
    elif mutation == "path":
        raw["entries"][0]["path"] = "../outside.html"
    elif mutation == "mime":
        raw["entries"][0]["mime"] = "application/octet-stream"
    elif mutation == "size":
        raw["entries"][0]["size"] = True
    else:
        raw["format"] = True
    data = encoded(raw)
    path.write_bytes(data)
    monkeypatch.setattr(resources, "MANIFEST_SHA256", hashlib.sha256(data).hexdigest())
    with pytest.raises(InvalidPresentationError):
        load_resources()


@pytest.mark.parametrize(
    "name,limit",
    [
        ("index.html", 16384),
        ("ui.js", 524288),
        ("ui.css", 65536),
        ("presentation.json", 262144),
        ("manifest.json", 16384),
    ],
)
def test_reads_are_bounded_and_inclusive(tmp_path, name, limit):
    path = tmp_path / name
    path.write_bytes(b" " * limit)
    assert len(resources._read(tmp_path, name, limit)) == limit
    path.write_bytes(b" " * (limit + 1))
    with pytest.raises(InvalidPresentationError):
        resources._read(tmp_path, name, limit)


def test_existing_contracts_keep_their_validation():
    assert AdoptRequest(expected_revision=0, confirm_comment_loss=True).expected_revision == 0
    assert (
        RuleCreateRequest.model_validate(
            {"expected_revision": 0, "rule": {"match": "x", "transformer": "md5"}}
        ).rule.case_sensitive
        is False
    )
    assert (
        DatabaseWriteRequest.model_validate(
            {"expected_revision": 0, "statement_timeout_ms": 100, "max_rows": 1}
        ).max_rows
        == 1
    )


def test_public_vocabulary_is_derived_and_not_in_shipped_bytes():
    words = json.loads((ROOT / "frontend/private/vocabulary.json").read_bytes())
    assert {
        "revision",
        "expected_revision",
        "CONFIG_DURABILITY_ERROR",
        "rule_create",
        "rul_",
    } <= set(words)
    for name in ("index.html", "ui.js", "ui.css"):
        text = load_resources()[name].decode()
        assert not any(word in text for word in words)


def test_ui_loader_has_no_runtime_or_http_dependency():
    # Etapa 3 autoriza somente o composition root a carregar os recursos.
    for path in (ROOT / "src/maskgw/admin/http").rglob("*.py"):
        assert "maskgw.admin.ui" not in path.read_text(encoding="utf-8")
    for path in (ROOT / "src/maskgw/admin/ui").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("maskgw.admin.http", "maskgw.runtime", "maskgw.mcp", "logging")
                )


@pytest.mark.parametrize("source", ["token", "Authorization", "environment"])
def test_projection_has_no_secret_source(source):
    raw = document()
    raw["views"][0]["controls"][0]["projections"] = [
        {"type": "copy", "source": source, "paths": [], "target": []}
    ]
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_closed_union_requires_matching_discriminator():
    raw = document()
    union = next(m for m in raw["models"] if m["shape"]["type"] == "union")
    union["shape"]["variants"][0]["value"] = "UNAPPROVED"
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_default_must_match_its_referenced_type():
    raw = document()
    integer = next(m["id"] for m in raw["models"] if m["shape"]["type"] == "integer")
    parent = next(
        m
        for m in raw["models"]
        if m["shape"]["type"] == "object" and any(f["ref"] == integer for f in m["shape"]["fields"])
    )
    field = next(f for f in parent["shape"]["fields"] if f["ref"] == integer)
    field["default"] = "not an integer"
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))


def test_model_catalog_detects_changed_constraints():
    raw = document()
    integer = next(m for m in raw["models"] if m["shape"]["type"] == "integer")
    integer["shape"]["max"] -= 1
    with pytest.raises(InvalidPresentationError):
        validate_catalog(validate_presentation(encoded(raw)))


@pytest.mark.parametrize("identity", ["__proto__", "constructor", "prototype"])
def test_template_identity_is_structural_not_display_text(identity):
    raw = document()
    raw["calls"][3]["path"] = "/admin/v1/rules/{" + identity + "}"
    raw["calls"][3]["identity"] = identity
    with pytest.raises(InvalidPresentationError):
        validate_presentation(encoded(raw))
