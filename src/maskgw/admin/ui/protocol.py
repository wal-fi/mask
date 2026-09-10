"""Protocolo declarativo fechado, sem HTTP, runtime ou efeitos de startup."""

from __future__ import annotations

import json
import re
from contextlib import suppress
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_DEPTH = 16
MAX_MODELS = 128
MAX_CONTROLS = 512
MAX_PRESENTATION_BYTES = 262144
SAFE_INTEGER = 9007199254740991
FORBIDDEN = frozenset({"__proto__", "constructor", "prototype"})
Scalar = str | bool | int | None
Segment = str | int


class InvalidPresentationError(ValueError):
    """Erro publico fixo; nao contem entrada rejeitada."""


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Text(Closed):
    type: Literal["string"]
    min: int = Field(default=0, ge=0, le=SAFE_INTEGER)
    max: int = Field(default=SAFE_INTEGER, ge=0, le=SAFE_INTEGER)
    prefix: str = ""
    alphabet: str = ""


class Integer(Closed):
    type: Literal["integer"]
    min: int = Field(default=0, ge=0, le=SAFE_INTEGER)
    max: int = Field(default=SAFE_INTEGER, ge=0, le=SAFE_INTEGER)


class Boolean(Closed):
    type: Literal["boolean"]


class Choice(Closed):
    type: Literal["enum"]
    choices: list[str | int | bool] = Field(min_length=1)


class FieldLink(Closed):
    name: str
    ref: str
    required: bool
    default: Scalar = None


class Object(Closed):
    type: Literal["object"]
    fields: list[FieldLink]


class Sequence(Closed):
    type: Literal["list", "nullable"]
    item: str


class Variant(Closed):
    value: str | bool | int
    ref: str


class Union(Closed):
    type: Literal["union"]
    tag: str
    variants: list[Variant] = Field(min_length=1)


Shape = Annotated[
    Text | Integer | Boolean | Choice | Object | Sequence | Union, Field(discriminator="type")
]


class Definition(Closed):
    id: str
    shape: Shape


class Call(Closed):
    id: str
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str
    input: str | None
    output: str
    error: str
    operation: Literal["read", "create", "replace", "delete", "move", "check", "confirm", "append"]
    identity: str | None


class Condition(Closed):
    type: Literal["present", "equal", "choice", "boolean"]
    path: list[Segment]
    value: Scalar = None


class Projection(Closed):
    type: Literal["copy", "object", "list", "omit", "insert", "replace", "remove", "permute"]
    source: Literal["base", "draft"]
    paths: list[list[Segment]] = Field(max_length=MAX_CONTROLS)
    target: list[Segment]


class Control(Closed):
    id: str
    type: Literal["text", "integer", "checkbox", "select", "table", "list", "read", "confirm"]
    path: list[Segment]
    model: str
    label: str
    default: Scalar = None
    condition: Condition | None = None
    projections: list[Projection] = Field(default_factory=list, max_length=MAX_CONTROLS)


class View(Closed):
    id: str
    label: str
    call: str
    controls: list[Control]
    actions: list[str]


class Editor(Closed):
    id: str
    name: str
    model: str
    controls: list[Control]
    help: str


class Binding(Closed):
    id: str
    role: Literal["version", "identity", "order", "consent", "result"]
    model: str
    path: list[Segment]


class Message(Closed):
    id: str
    name: str
    text: str
    state: Literal[
        "loading",
        "authentication",
        "draft",
        "pending",
        "success",
        "conflict",
        "busy",
        "incompatible",
        "unknown",
        "uncertain",
    ]


class Presentation(Closed):
    format: Literal[1]
    models: list[Definition] = Field(min_length=1, max_length=MAX_MODELS)
    calls: list[Call] = Field(min_length=19, max_length=19)
    views: list[View] = Field(min_length=6, max_length=6)
    editors: list[Editor] = Field(min_length=8, max_length=8)
    bindings: list[Binding]
    messages: list[Message]


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result or key in FORBIDDEN:
            raise ValueError
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise ValueError


def parse_json(data: bytes) -> object:
    """UTF-8 estrito, sem BOM, duplicatas, NaN ou Infinity."""
    result: object = None
    valid = False
    try:
        text = data.decode("utf-8")
        result = json.loads(
            text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_constant
        )
        valid = True
    except (ValueError, RecursionError):
        pass
    if not valid:
        raise InvalidPresentationError("Invalid presentation.")
    return result


def _need(condition: bool) -> None:
    if not condition:
        raise InvalidPresentationError("Invalid presentation.")


def _segments(path: list[Segment]) -> None:
    _need(len(path) <= MAX_DEPTH)
    for part in path:
        _need(
            (isinstance(part, str) and bool(part) and part not in FORBIDDEN)
            or (type(part) is int and 0 <= part <= SAFE_INTEGER)
        )


def _refs(shape: Shape) -> list[str]:
    if isinstance(shape, Object):
        names = [field.name for field in shape.fields]
        _need(len(names) == len(set(names)))
        _need(all(name and name not in FORBIDDEN for name in names))
        return [field.ref for field in shape.fields]
    if isinstance(shape, Sequence):
        return [shape.item]
    if isinstance(shape, Union):
        _need(shape.tag not in FORBIDDEN and bool(shape.tag))
        values = [json.dumps(item.value) for item in shape.variants]
        _need(len(values) == len(set(values)))
        return [item.ref for item in shape.variants]
    if isinstance(shape, Text | Integer):
        _need(shape.min <= shape.max)
    if isinstance(shape, Choice):
        values = [json.dumps(item) for item in shape.choices]
        _need(len(values) == len(set(values)))
    return []


def _graph(models: dict[str, Definition]) -> None:
    edges = {key: _refs(value.shape) for key, value in models.items()}
    heights: dict[str, int] = {}

    def visit(key: str, ancestors: frozenset[str]) -> int:
        _need(key in models and key not in ancestors and len(ancestors) < MAX_DEPTH)
        if key in heights:
            return heights[key]
        height = 1 + max((visit(ref, ancestors | {key}) for ref in edges[key]), default=0)
        _need(height <= MAX_DEPTH)
        heights[key] = height
        return height

    for key in models:
        visit(key, frozenset())
    for definition in models.values():
        shape = definition.shape
        if isinstance(shape, Object):
            for field in shape.fields:
                _default(field.default, models[field.ref].shape, models)
        if isinstance(shape, Union):
            for variant in shape.variants:
                target = models[variant.ref].shape
                _need(isinstance(target, Object))
                if isinstance(target, Object):
                    tags = [f for f in target.fields if f.name == shape.tag and f.required]
                    _need(len(tags) == 1)
                    node = models[tags[0].ref].shape
                    _need(isinstance(node, Choice) and node.choices == [variant.value])


def _default(value: Scalar, shape: Shape, models: dict[str, Definition]) -> None:
    if value is None:
        return
    while isinstance(shape, Sequence) and shape.type == "nullable":
        shape = models[shape.item].shape
    if isinstance(shape, Boolean):
        _need(type(value) is bool)
    elif isinstance(shape, Integer):
        _need(type(value) is int and shape.min <= value <= shape.max)
    elif isinstance(shape, Text):
        _need(isinstance(value, str))
        if isinstance(value, str):
            _need(shape.min <= len(value) <= shape.max and value.startswith(shape.prefix))
            _need(
                not shape.alphabet or all(c in shape.alphabet for c in value[len(shape.prefix) :])
            )
    elif isinstance(shape, Choice):
        _need(any(type(v) is type(value) and v == value for v in shape.choices))
    else:
        _need(False)


def _path(model: str, path: list[Segment], models: dict[str, Definition]) -> Shape:
    _segments(path)
    _need(model in models)
    for part in path:
        shape = models[model].shape
        while isinstance(shape, Sequence) and shape.type == "nullable":
            shape = models[shape.item].shape
        if isinstance(shape, Object) and isinstance(part, str):
            fields = [f for f in shape.fields if f.name == part]
            _need(len(fields) == 1)
            model = fields[0].ref
        elif isinstance(shape, Sequence) and shape.type == "list" and type(part) is int:
            model = shape.item
        else:
            _need(False)
    return models[model].shape


def _destination(call: Call) -> None:
    _need(call.path.startswith("/admin/v1/"))
    _need(not any(char in call.path for char in ("?", "#", "%", "\\", "//")))
    segments = call.path.split("/")[3:]
    _need(all(part and part not in {".", ".."} for part in segments))
    slots = [part for part in segments if "{" in part or "}" in part]
    _need(len(slots) <= 1)
    if slots:
        _need(call.identity not in FORBIDDEN)
        _need(call.identity is not None and slots == ["{" + str(call.identity) + "}"])
        _need(bool(re.fullmatch(r"[a-z_]+", str(call.identity))))
    else:
        _need(call.identity is None)


def _tree(value: object, depth: int) -> None:
    _need(depth <= MAX_DEPTH)
    if type(value) is int:
        _need(-SAFE_INTEGER <= value <= SAFE_INTEGER)
    if isinstance(value, dict):
        _need(not FORBIDDEN.intersection(value))
        for child in value.values():
            _tree(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _tree(child, depth + 1)


def validate_presentation(data: bytes) -> Presentation:
    """Valida formato e referencias, sem importar schemas/HTTP ou ler runtime."""
    _need(len(data) <= MAX_PRESENTATION_BYTES)
    raw = parse_json(data)
    _tree(raw, 0)
    _need(isinstance(raw, dict) and type(raw.get("format")) is int)
    result: Presentation | None = None
    with suppress(ValidationError):
        result = Presentation.model_validate(raw)
    if result is None:
        raise InvalidPresentationError("Invalid presentation.")
    _need(type(result.format) is int)
    identities: list[str] = []
    collections = (
        result.models,
        result.calls,
        result.views,
        result.editors,
        result.bindings,
        result.messages,
    )
    for collection in collections:
        identities.extend(item.id for item in collection)
    controls = [c for view in result.views for c in view.controls]
    controls.extend(c for editor in result.editors for c in editor.controls)
    identities.extend(control.id for control in controls)
    _need(len(controls) <= MAX_CONTROLS)
    _need(len(identities) == len(set(identities)))
    _need(all(re.fullmatch(r"[a-z][0-9]+", key) for key in identities))
    models = {item.id: item for item in result.models}
    _graph(models)
    calls = {item.id: item for item in result.calls}
    for call in result.calls:
        _destination(call)
        _need(
            call.output in models
            and call.error in models
            and (call.input is None or call.input in models)
        )
        _need((call.method == "GET") == (call.input is None))
    for view in result.views:
        _need(view.call in calls and calls[view.call].method == "GET")
        _need(all(action in calls for action in view.actions))
    for control in controls:
        leaf = _path(control.model, control.path, models)
        _default(control.default, leaf, models)
        if control.condition is not None:
            _path(control.model, control.condition.path, models)
        for projection in control.projections:
            for path in projection.paths:
                _path(control.model, path, models)
            _segments(projection.target)
    for editor in result.editors:
        _need(editor.model in models)
    for binding in result.bindings:
        _path(binding.model, binding.path, models)
    return result
