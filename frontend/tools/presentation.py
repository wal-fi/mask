"""Autoria estatica privada: modelos, catalogo, telas e editores sem runtime."""

from __future__ import annotations
import json
from pathlib import Path
from maskgw.admin.http.app import READ_PATHS, WRITE_ROUTES, VALIDATE_PATH
from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.responses import CLOSED_REASONS
from maskgw.masking.transformers.registry import build_default_registry
from maskgw.admin.ui.protocol import validate_presentation

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "frontend/private"
wire = json.loads((PRIVATE / "wire-schemas.json").read_text(encoding="utf-8"))
models = []
names = {}


def put(name, shape):
    key = "m" + str(len(models))
    names[name] = key
    models.append({"id": key, "shape": shape})
    return key


def model(name, node=None):
    if name in names:
        return names[name]
    if node is None:
        node = wire[name]
    if "$ref" in node:
        return model(node["$ref"].rsplit("/", 1)[1])
    if "const" in node:
        return put(name, {"type": "enum", "choices": [node["const"]]})
    if "enum" in node:
        return put(name, {"type": "enum", "choices": node["enum"]})
    if "anyOf" in node:
        choices = [n for n in node["anyOf"] if n.get("type") != "null"]
        if len(choices) != 1:
            raise ValueError("Non-declarative union")
        return put(name, {"type": "nullable", "item": model(name + "Value", choices[0])})
    kind = node.get("type")
    if kind == "object":
        if "properties" not in node:
            return model("Parameters")
        fields = []
        for key, child in node["properties"].items():
            if name == "SqlWriteRequest" and key == "allowed_pg_functions":
                continue
            fields.append(
                {
                    "name": key,
                    "ref": model(name + key, child),
                    "required": key in node.get("required", []),
                    "default": child.get("default")
                    if isinstance(child.get("default"), (str, int, bool))
                    else None,
                }
            )
        return put(name, {"type": "object", "fields": fields})
    if kind == "array":
        return put(name, {"type": "list", "item": model(name + "Item", node["items"])})
    if kind == "string":
        shape = {
            "type": "string",
            "min": node.get("minLength", 0),
            "max": node.get("maxLength", 9007199254740991),
        }
        if "pattern" in node:
            shape.update(
                prefix="rul_" if "rul_" in node["pattern"] else "exc_",
                min=36,
                max=36,
                alphabet="0123456789abcdef",
            )
        return put(name, shape)
    if kind == "integer":
        return put(
            name,
            {
                "type": "integer",
                "min": node.get("minimum", 0),
                "max": node.get("maximum", 9007199254740991),
            },
        )
    if kind == "boolean":
        return put(name, {"type": "boolean"})
    raise ValueError("Unsupported model")


# Shared leaves keep the fixed protocol below 128 definitions without changing types.
_original_put = put
signatures = {}


def put(name, shape):
    signature = json.dumps(shape, sort_keys=True)
    if signature in signatures:
        names[name] = signatures[signature]
        return names[name]
    key = _original_put(name, shape)
    signatures[signature] = key
    return key


wire["Parameters"] = {
    "type": "object",
    "properties": {
        "value": {"type": "string"},
        "length": {"type": "integer", "minimum": 0},
        "pattern": {"type": "string"},
        "replacement": {"type": "string"},
        "strategy": {"type": "string", "enum": ["digits", "alphanumeric"]},
        "preserve_length": {"type": "boolean"},
    },
}
outputs = [
    "AdminStatusResponse",
    "AdminConfigResponse",
    "AdminRulesResponse",
    "AdminRuleResponse",
    "AdminExceptionsResponse",
    "AdminExceptionResponse",
    "AdminTransformersResponse",
    "AdminProtectedResponse",
]
# Error envelopes are closed and discriminated; no executable messages.
variants = []
for index, category in enumerate(AdminErrorCategory):
    props = {
        "error": {"const": category.value},
        "detail": {"type": "string"},
        "current_revision": {"type": "integer", "minimum": 0},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "reason": {"type": "string", "enum": sorted(CLOSED_REASONS)},
                },
                "required": ["path", "reason"],
            },
        },
    }
    required = ["error", "detail"]
    if category is AdminErrorCategory.CONFIG_DURABILITY_ERROR:
        props["applied"] = {"const": True}
        required.append("applied")
    variants.append(
        {
            "value": category.value,
            "ref": model(
                "Error" + str(index), {"type": "object", "properties": props, "required": required}
            ),
        }
    )
error_model = put("ErrorEnvelope", {"type": "union", "tag": "error", "variants": variants})
calls = []


def call(path, method, request, output, operation):
    key = "c" + str(len(calls))
    identity = path.split("{")[1].split("}")[0] if "{" in path else None
    calls.append(
        {
            "id": key,
            "method": method,
            "path": path,
            "input": model(request) if request else None,
            "output": model(output),
            "operation": operation,
            "identity": identity,
            "error": error_model,
        }
    )
    return key


for path, output in zip(READ_PATHS, outputs, strict=True):
    call(path, "GET", None, output, "read")
call(VALIDATE_PATH, "POST", "ConfigValidateRequest", "ConfigValidateResponse", "check")
requests = [
    "AdoptRequest",
    "ConfigReplaceRequest",
    "RuleReorderRequest",
    "RuleCreateRequest",
    "RuleReplaceRequest",
    "DeleteRequest",
    "ExceptionCreateRequest",
    "ExceptionReplaceRequest",
    "DeleteRequest",
    "DatabaseWriteRequest",
    "SqlWriteRequest",
]
operations = [
    "confirm",
    "replace",
    "move",
    "create",
    "replace",
    "delete",
    "create",
    "replace",
    "delete",
    "replace",
    "append",
]
for (path, method), request, operation in zip(WRITE_ROUTES, requests, operations, strict=True):
    if (path, method) == ("/admin/v1/config", "PUT"):
        continue
    call(path, method, request, "WriteResponse", operation)
controls = []


def control(kind, owner, path, label, default=None, condition=None):
    value = {
        "id": "k" + str(len(controls)),
        "type": kind,
        "path": path,
        "model": owner,
        "label": label,
        "default": default,
        "condition": condition,
    }
    controls.append(value)
    return value


views = []
labels = ["Visão geral", "Configuração", "Regras", "Exceptions", "Database", "SQL policy"]
view_calls = [0, 1, 2, 4, 1, 7]
view_actions = [[], [8, 9], [10, 11, 12, 13], [14, 15, 16], [17], [18]]
for i, (label, index, actions) in enumerate(zip(labels, view_calls, view_actions, strict=True)):
    owner = calls[index]["output"]
    shape = next(m["shape"] for m in models if m["id"] == owner)
    fields = [control("read", owner, [f["name"]], f["name"]) for f in shape["fields"]]
    views.append(
        {
            "id": "v" + str(i),
            "label": label,
            "call": calls[index]["id"],
            "controls": fields,
            "actions": [calls[a]["id"] for a in actions],
        }
    )
editors = []
for i, spec in enumerate(build_default_registry().specs()):
    properties = {
        key: wire["Parameters"]["properties"][key]
        for key in (*spec.required_parameters, *spec.optional_parameters)
    }
    owner = model(
        "Editor" + str(i),
        {"type": "object", "properties": properties, "required": list(spec.required_parameters)},
    )
    items = []
    for key, node in properties.items():
        kind = (
            "checkbox"
            if node["type"] == "boolean"
            else "integer"
            if node["type"] == "integer"
            else "select"
            if "enum" in node
            else "text"
        )
        default = True if key == "preserve_length" else None
        condition = (
            {"type": "boolean", "path": ["preserve_length"], "value": False}
            if spec.name == "random" and key == "length"
            else None
        )
        items.append(control(kind, owner, [key], key, default, condition))
    help_text = (
        "Sem parâmetros; a chave é ambiental."
        if spec.name == "hmac_sha256"
        else "Hashes sem chave em domínios pequenos permitem enumeração."
        if spec.name in {"md5", "sha256", "sha512"}
        else "Prefixos preservados podem identificar pessoas."
        if spec.name == "truncate"
        else "Não preserva correlação entre valores."
        if spec.name == "random"
        else "Sem prévia; validação ocorre no servidor."
    )
    editors.append(
        {
            "id": "e" + str(i),
            "name": spec.name,
            "model": owner,
            "controls": items,
            "help": help_text,
        }
    )
bindings = []
for definition in models:
    if definition["shape"]["type"] != "object":
        continue
    for field in definition["shape"]["fields"]:
        role = {
            "revision": "version",
            "expected_revision": "version",
            "id": "identity",
            "position": "order",
            "adopted": "consent",
            "applied": "result",
        }.get(field["name"])
        if role:
            bindings.append(
                {
                    "id": "b" + str(len(bindings)),
                    "role": role,
                    "model": definition["id"],
                    "path": [field["name"]],
                }
            )
message_overrides = {
    "CONFIG_OUT_OF_SYNC": (
        "incompatible",
        "Arquivo e runtime divergiram. Escritas bloqueadas; recuperação operacional fora da interface.",
    ),
    "CONFIG_NOT_ADOPTED": (
        "incompatible",
        "Configuração legada: edição bloqueada até adoção com confirmação explícita.",
    ),
    "CONFIG_ALREADY_ADOPTED": (
        "conflict",
        "A configuração já foi adotada. Releia o estado; não repita a adoção.",
    ),
    "NOT_FOUND": ("conflict", "Item não encontrado. Releia a lista e revise o rascunho."),
    "CONFIG_WRITE_ERROR": (
        "incompatible",
        "A persistência falhou. Preserve o rascunho; não reenviar automaticamente.",
    ),
    "CONFIG_RELOAD_ERROR": (
        "incompatible",
        "Não foi possível compilar ou verificar o candidato. Não é um diagnóstico automático de PostgreSQL.",
    ),
    "PAYLOAD_TOO_LARGE": ("incompatible", "O corpo excedeu 1 MiB. Não dividir a operação atômica."),
    "HOST_NOT_ALLOWED": (
        "incompatible",
        "Destino local recusado. Confira o endereço sem desabilitar a proteção.",
    ),
    "CROSS_ORIGIN_REJECTED": (
        "incompatible",
        "Origem recusada. Abra a origem administrativa exata; não desabilite a proteção.",
    ),
    "IMMUTABLE_FIELD": (
        "incompatible",
        "O cliente tentou alterar um campo protegido. Nenhuma correção silenciosa é permitida.",
    ),
    "UNSUPPORTED_MEDIA_TYPE": (
        "incompatible",
        "Formato incompatível enviado pelo cliente. Não corrigir e reenviar automaticamente.",
    ),
}
messages = []
for name in sorted({*(item.value for item in AdminErrorCategory), *CLOSED_REASONS}):
    state = (
        "conflict"
        if name
        in {
            "REVISION_CONFLICT",
            "CONFIG_OUT_OF_SYNC",
            "CONFIG_NOT_ADOPTED",
            "CONFIG_ALREADY_ADOPTED",
        }
        else "busy"
        if name == "RELOAD_BUSY"
        else "uncertain"
        if name == "CONFIG_DURABILITY_ERROR"
        else "authentication"
        if name == "UNAUTHORIZED"
        else "unknown"
        if name == "INTERNAL_ERROR"
        else "incompatible"
    )
    text = (
        "A gravação foi aplicada; a durabilidade não foi confirmada. Não reenviar automaticamente."
        if state == "uncertain"
        else "Resultado desconhecido. Releia o estado antes de decidir."
        if state == "unknown"
        else "A configuração mudou. Releia e revise o rascunho."
        if state == "conflict"
        else "Há um runtime aposentado em uso. Aguarde e releia."
        if state == "busy"
        else "Autenticação necessária."
        if state == "authentication"
        else "Operação recusada. Confira os campos e valide novamente."
    )
    state, text = message_overrides.get(name, (state, text))
    messages.append({"id": "t" + str(len(messages)), "name": name, "text": text, "state": state})
data = {
    "format": 1,
    "models": models,
    "calls": calls,
    "views": views,
    "editors": editors,
    "bindings": bindings,
    "messages": messages,
}
encoded = (
    json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
).encode("utf-8")
validate_presentation(encoded)
(PRIVATE / "presentation.json").write_bytes(encoded)
(PRIVATE / "model-names.json").write_text(
    json.dumps(names, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(
    "Presentation:",
    len(models),
    "models;",
    len(calls),
    "calls;",
    len(controls),
    "controls;",
    len(encoded),
    "bytes",
)
