"""Deriva contratos privados e vocabulario das fontes atuais; uso somente no build."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from pydantic import BaseModel
from maskgw.admin.http import schemas, views
from maskgw.sql.policy import DEFAULT_SQL_POLICY
from maskgw.admin.http.app import READ_PATHS, WRITE_ROUTES, VALIDATE_PATH
from maskgw.admin.http.responses import CLOSED_REASONS
from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.ui.protocol import Presentation
from maskgw.config.ids import RULE_ID_PATTERN, EXCEPTION_ID_PATTERN
from maskgw.masking.transformers.registry import build_default_registry
from maskgw.audit.log import AdminOperationName

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "frontend/private"


def write(name, value):
    (PRIVATE / name).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def ts(node):
    if isinstance(node, bool):
        return "unknown"
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[1]
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(v) for v in node["enum"])
    if "anyOf" in node:
        return " | ".join(ts(v) for v in node["anyOf"])
    kind = node.get("type")
    if kind == "object":
        if "properties" not in node:
            return "Readonly<Record<string, " + ts(node.get("additionalProperties", {})) + ">>"
        required = node.get("required", [])
        return (
            "{ "
            + "; ".join(
                "readonly " + json.dumps(k) + ("" if k in required else "?") + ": " + ts(v)
                for k, v in node["properties"].items()
            )
            + " }"
        )
    if kind == "array":
        return "ReadonlyArray<" + ts(node["items"]) + ">"
    return {
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "string": "string",
        "null": "null",
    }.get(kind, "unknown")


def main():
    all_schemas = {}
    words = set()
    for name, model in vars(schemas).items():
        if inspect.isclass(model) and issubclass(model, BaseModel) and model is not BaseModel:
            data = model.model_json_schema()
            all_schemas.update(data.pop("$defs", {}))
            all_schemas[name] = data
            words.add(name)

    def vocabulary(node):
        if isinstance(node, dict):
            words.update(node.get("properties", {}))
            words.update(v for v in node.get("enum", []) if isinstance(v, str))
            if isinstance(node.get("const"), str):
                words.add(node["const"])
            for value in node.values():
                vocabulary(value)
        elif isinstance(node, list):
            for value in node:
                vocabulary(value)

    for data in all_schemas.values():
        vocabulary(data)
    for spec in build_default_registry().specs():
        words.update((spec.name, *spec.required_parameters, *spec.optional_parameters))
    words.update(READ_PATHS)
    words.update(path for path, _ in WRITE_ROUTES)
    words.update((VALIDATE_PATH, RULE_ID_PATTERN, EXCEPTION_ID_PATTERN, "rul_", "exc_"))
    words.update(item.value for item in AdminErrorCategory)
    words.update(CLOSED_REASONS)
    words.update(
        (
            *views.VALIDATOR_RULES,
            *views.PIPELINE,
            views.UNMATCHED_POLICY,
            views.PG_NAMESPACE_DEFAULT,
            views.STATEMENT_TIMEOUT_ENFORCED_BY,
        )
    )
    words.update(
        (
            *DEFAULT_SQL_POLICY.allowed_pg_functions,
            *DEFAULT_SQL_POLICY.denied_functions,
            *DEFAULT_SQL_POLICY.denied_prefixes,
            *DEFAULT_SQL_POLICY.denied_relations,
        )
    )
    words.update(item.value for item in AdminOperationName)
    words.difference_update(
        {"id", "name", "value", "type", "mode", "length", "path", "fields", "error", "detail"}
    )
    all_schemas["WriteResponse"]["required"] = ["revision", "applied"]
    all_schemas["AdoptRequest"]["properties"]["confirm_comment_loss"] = {"const": True}
    write("vocabulary.json", sorted(words))
    write("wire-schemas.json", all_schemas)
    write("protocol-schema.json", Presentation.model_json_schema())
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
    types = ["// Generated from the eleven existing HTTP contracts. Never shipped."]
    for name, data in sorted(all_schemas.items()):
        types.append("export type " + name + " = " + ts(data) + ";")
    types.append(
        "export type WriteContract =\n"
        + " |\n".join(
            "{ readonly method: "
            + json.dumps(method)
            + "; readonly path: "
            + json.dumps(path)
            + "; readonly request: "
            + request
            + "; readonly response: WriteResponse }"
            for (path, method), request in zip(WRITE_ROUTES, requests, strict=True)
        )
        + ";"
    )
    types.extend(
        [
            'export type TransformerInput = { readonly transformer: "md5" | "sha256" | "sha512" | "hmac_sha256"; readonly config?: Readonly<Record<string, never>> } | { readonly transformer: "fixed"; readonly config: { readonly value: string } } | { readonly transformer: "truncate"; readonly config: { readonly length: number } } | { readonly transformer: "regex"; readonly config: { readonly pattern: string; readonly replacement: string } } | { readonly transformer: "random"; readonly config: { readonly strategy: "digits" | "alphanumeric" } & ({ readonly preserve_length?: true; readonly length?: never } | { readonly preserve_length: false; readonly length: number }) };',
            'export type UiRuleContent = Omit<RuleContent, "transformer" | "config"> & TransformerInput;',
            'export type UiRuleCreateRequest = Omit<RuleCreateRequest, "rule"> & { readonly rule: UiRuleContent };',
            'export type UiRuleReplaceRequest = Omit<RuleReplaceRequest, "rule"> & { readonly rule: UiRuleContent };',
        ]
    )
    ui_names = {
        "RuleCreateRequest": "UiRuleCreateRequest",
        "RuleReplaceRequest": "UiRuleReplaceRequest",
        "SqlWriteRequest": "UiSqlRequest",
    }
    types.append(
        "export type UiWriteContract =\n"
        + " |\n".join(
            "{ readonly method: "
            + json.dumps(method)
            + "; readonly path: "
            + json.dumps(path)
            + "; readonly request: "
            + ui_names.get(request, request)
            + "; readonly response: WriteResponse }"
            for (path, method), request in zip(WRITE_ROUTES, requests, strict=True)
            if (path, method) != ("/admin/v1/config", "PUT")
        )
        + ";"
    )
    types.append(
        'export type UiSqlRequest = Omit<SqlWriteRequest, "allowed_pg_functions"> & { readonly allowed_pg_functions?: never };'
    )
    types.append(
        "export type ErrorCategory = "
        + " | ".join(json.dumps(c.value) for c in AdminErrorCategory)
        + ";"
    )
    types.append(
        "export type ReasonCode = "
        + " | ".join(json.dumps(c) for c in sorted(CLOSED_REASONS))
        + ";"
    )
    types.append(
        'export type AdminErrorResponse = { readonly detail: string; readonly current_revision?: number; readonly fields?: ReadonlyArray<{ readonly path: string; readonly reason: ReasonCode }> } & ({ readonly error: "CONFIG_DURABILITY_ERROR"; readonly applied: true } | { readonly error: Exclude<ErrorCategory, "CONFIG_DURABILITY_ERROR">; readonly applied?: never });'
    )
    types.append(
        'export type DurabilityResponse = Extract<AdminErrorResponse, { readonly error: "CONFIG_DURABILITY_ERROR" }>;'
    )
    types.append(
        'export type UiCommand<C = UiWriteContract> = C extends UiWriteContract ? Omit<C, "response"> : never;'
    )
    types.append(
        "export type EditState = { readonly base: AdminConfigResponse; readonly command: UiCommand };"
    )
    types.append(
        'export type WriteOutcome = { readonly type: "success"; readonly value: WriteResponse } | { readonly type: "rejected"; readonly value: Exclude<AdminErrorResponse, DurabilityResponse> } | { readonly type: "unknown" } | { readonly type: "uncertain"; readonly value: DurabilityResponse };'
    )
    types.append(
        'export type ViewState = { readonly type: "loading" | "authentication" } | ({ readonly type: "draft" | "pending" | "conflict" | "busy" } & EditState) | { readonly type: "success"; readonly value: AdminConfigResponse } | { readonly type: "incompatible"; readonly value: AdminErrorResponse } | { readonly type: "unknown" } | { readonly type: "uncertain"; readonly value: DurabilityResponse };'
    )

    (PRIVATE / "contracts.d.ts").write_text("\n".join(types) + "\n", encoding="utf-8", newline="\n")
    write(
        "calls.json",
        [
            {"path": path, "method": method, "request": request}
            for (path, method), request in zip(WRITE_ROUTES, requests, strict=True)
        ],
    )


if __name__ == "__main__":
    main()
