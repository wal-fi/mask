"""Leitura limitada de recursos embarcados; chamada somente explicita nesta etapa."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextlib import suppress
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType

from maskgw.admin.ui._anchor import MANIFEST_SHA256
from maskgw.admin.ui._catalog import CALLS, MODEL_SHA256
from maskgw.admin.ui.protocol import (
    InvalidPresentationError,
    Presentation,
    parse_json,
    validate_presentation,
)

RESOURCES = (
    ("h", "index.html", "text/html; charset=utf-8", 16384),
    ("j", "ui.js", "text/javascript; charset=utf-8", 524288),
    ("s", "ui.css", "text/css; charset=utf-8", 65536),
    ("p", "presentation.json", "application/json", 262144),
)


def _need(condition: bool) -> None:
    if not condition:
        raise InvalidPresentationError("Invalid presentation.")


def validate_catalog(presentation: Presentation) -> None:
    """Igualdade exata, nunca uma checagem de subconjunto."""
    actual = tuple(
        (c.method, c.path, c.input, c.output, c.operation, c.identity, c.error)
        for c in presentation.calls
    )
    _need(actual == CALLS)
    models = json.dumps(
        [m.model_dump() for m in presentation.models], sort_keys=True, separators=(",", ":")
    )
    _need(hashlib.sha256(models.encode()).hexdigest() == MODEL_SHA256)


def _read(root: Traversable, name: str, maximum: int) -> bytes:
    with root.joinpath(name).open("rb") as stream:
        data = stream.read(maximum + 1)
    _need(len(data) <= maximum)
    data.decode("utf-8")
    return data


def _load(root: Traversable) -> Mapping[str, bytes]:
    manifest = _read(root, "manifest.json", 16384)
    _need(hashlib.sha256(manifest).hexdigest() == MANIFEST_SHA256)
    raw = parse_json(manifest)
    _need(isinstance(raw, dict))
    if not isinstance(raw, dict):
        raise InvalidPresentationError("Invalid presentation.")
    _need(set(raw) == {"format", "entries"} and type(raw["format"]) is int and raw["format"] == 1)
    entries = raw["entries"]
    _need(isinstance(entries, list) and len(entries) == len(RESOURCES))
    if not isinstance(entries, list):
        raise InvalidPresentationError("Invalid presentation.")
    result: dict[str, bytes] = {}
    for entry, (key, name, mime, maximum) in zip(entries, RESOURCES, strict=True):
        _need(isinstance(entry, dict))
        if not isinstance(entry, dict):
            raise InvalidPresentationError("Invalid presentation.")
        _need(set(entry) == {"id", "path", "mime", "size", "sha256"})
        _need(entry["id"] == key and entry["path"] == name and entry["mime"] == mime)
        _need(type(entry["size"]) is int and 0 <= entry["size"] <= maximum)
        data = _read(root, name, maximum)
        _need(len(data) == entry["size"] and hashlib.sha256(data).hexdigest() == entry["sha256"])
        result[name] = data
    presentation = validate_presentation(result["presentation.json"])
    validate_catalog(presentation)
    digest = hashlib.sha256(result["presentation.json"]).hexdigest().encode()
    _need(b'export const digest="' + digest + b'";' in result["ui.js"])
    return MappingProxyType(result)


def load_resources() -> Mapping[str, bytes]:
    """Somente o pacote, nunca cwd/env. Bytes imutaveis, sem logs ou efeitos externos."""
    result: Mapping[str, bytes] | None = None
    with suppress(OSError, ValueError, RecursionError):
        result = _load(files("maskgw.admin.ui").joinpath("assets"))
    if result is None:
        raise InvalidPresentationError("Invalid presentation.")
    return result
