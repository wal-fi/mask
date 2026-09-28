"""Escritas declaradas do console v2 (Fase 9, Etapa 6, D-103-D-106).

A apresentacao privada declara so caminhos, rotulos e textos: o JS publico
monta o corpo por caminho e nunca conhece nomes de campo. O validador recusa
acao sobre leitura, campo fora do modelo de entrada, segredo com origem de
leitura, carimbo de revision sem origem, teste que escreve e assistente que
esconde ou inventa campo.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.errors import AdminErrorCategory
from maskgw.admin.http.responses import CLOSED_REASONS
from maskgw.admin.http.v2.errors import V2_SHARED_CATEGORIES, DatasourceErrorCategory
from maskgw.admin.ui.protocol import InvalidPresentationError, validate_presentation

PRIVATE = Path("frontend/private/presentation.json")
Mutation = Callable[[dict[str, Any]], None]


def _document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(PRIVATE.read_bytes())
    return document


def _encode(document: dict[str, Any]) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _action(document: dict[str, Any], label: str) -> dict[str, Any]:
    found: dict[str, Any] = next(a for a in document["console"]["actions"] if a["label"] == label)
    return found


def _call(document: dict[str, Any], operation: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in document["calls"] if c["operation"] == operation)
    return found


def _walk(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for field in fields:
        found.append(field)
        found.extend(_walk(field.get("items", [])))
    return found


def test_every_write_has_one_action_and_secrets_are_write_only():
    document = _document()
    actions = document["console"]["actions"]
    calls = {c["id"]: c for c in document["calls"]}
    operations = sorted(calls[a["call"]]["operation"] for a in actions)
    assert operations == sorted(
        ["register", "revise", "renew", "probe", "resume", "pause", "retire", "amend"]
    )
    for action in actions:
        for field in _walk(
            [*action["fields"], *([action["typed"]] if action.get("typed") else [])]
        ):
            if field["kind"] == "secret":
                assert field.get("source") is None
                assert field["path"] == ["credential", "password"]
    secrets = {
        calls[a["call"]]["operation"]
        for a in actions
        if any(f["kind"] == "secret" for f in _walk(a["fields"]))
    }
    # Senha write-only: so no cadastro (e no teste do rascunho) e na troca.
    assert secrets == {"register", "renew"}
    register = _action(document, "Novo datasource")
    assert calls[register["probe"]]["path"] == "/admin/v2/datasources:test"
    assert register["drop"] == [["expected_catalog_revision"], ["enabled"]]


def test_outcomes_cover_every_write_category_and_reasons_are_closed():
    document = _document()
    console = document["console"]
    values = {o["value"] for o in console["outcomes"]}
    own = {c.value for c in DatasourceErrorCategory}
    shared = {c.value for c in V2_SHARED_CATEGORIES}
    boundary = {
        AdminErrorCategory.HOST_NOT_ALLOWED.value,
        AdminErrorCategory.CROSS_ORIGIN_REJECTED.value,
        AdminErrorCategory.METHOD_NOT_ALLOWED.value,
        AdminErrorCategory.PAYLOAD_TOO_LARGE.value,
        AdminErrorCategory.UNSUPPORTED_MEDIA_TYPE.value,
    }
    assert values == own | shared | boundary
    kinds = {o["value"]: o["kind"] for o in console["outcomes"]}
    assert kinds["REVISION_CONFLICT"] == "conflict"
    assert kinds["CATALOG_OUTCOME_UNCERTAIN"] == "uncertain"
    assert kinds["INTERNAL_ERROR"] == "uncertain"
    assert kinds["CATALOG_BLOCKED"] == "blocked"
    assert kinds["CATALOG_WRITE_ERROR"] == "blocked"
    assert kinds["DATASOURCE_BUSY"] == "busy"
    assert {r["value"] for r in console["reasons"]} == set(CLOSED_REASONS)
    assert console["latest"] == ["current_revision"]
    # D-068: a UI mostra que um unico principal controla todos os datasources.
    assert any("não há permissões" in note for note in console["summary"]["notes"])


def test_write_error_envelope_is_the_declared_outcome_set():
    document = _document()
    envelope = next(
        m for m in document["models"] if m["id"] == _call(document, "register")["error"]
    )
    variants = {v["value"] for v in envelope["shape"]["variants"]}
    assert variants == {o["value"] for o in document["console"]["outcomes"]}


def _probe_that_writes(document: dict[str, Any]) -> None:
    _action(document, "Novo datasource")["probe"] = _call(document, "register")["id"]


def _action_on_read(document: dict[str, Any]) -> None:
    read = next(c for c in document["calls"] if c["path"].startswith("/admin/v2/datasources/{"))
    _action(document, "Editar conexão e limites")["call"] = read["id"]


def _field_outside_input(document: dict[str, Any]) -> None:
    _action(document, "Editar conexão e limites")["fields"][0]["path"] = ["nowhere"]


def _secret_read_back(document: dict[str, Any]) -> None:
    field = next(f for f in _action(document, "Trocar senha")["fields"] if f["kind"] == "secret")
    field["source"] = ["datasource", "display_name"]


def _records_without_items(document: dict[str, Any]) -> None:
    _action(document, "Editar política")["fields"][0]["items"] = []


def _stamp_without_origin(document: dict[str, Any]) -> None:
    _action(document, "Editar conexão e limites")["origin"] = None


def _stamp_on_text(document: dict[str, Any]) -> None:
    _action(document, "Editar conexão e limites")["stamp"] = ["display_name"]


def _typed_as_secret(document: dict[str, Any]) -> None:
    _action(document, "Remover")["typed"]["kind"] = "secret"


def _wrong_place(document: dict[str, Any]) -> None:
    _action(document, "Remover")["place"] = "collection"


def _foreign_wizard_field(document: dict[str, Any]) -> None:
    document["console"]["guide"]["steps"][0]["fields"].append("y999999")


def _hidden_wizard_field(document: dict[str, Any]) -> None:
    document["console"]["guide"]["steps"][0]["fields"].pop()


def _open_without_lands(document: dict[str, Any]) -> None:
    _action(document, "Novo datasource")["lands"] = None


def _write_on_first_prefix(document: dict[str, Any]) -> None:
    _call(document, "retire")["path"] = "/admin/v1/rules/{rule_id}"


def _unapproved_second_prefix_write(document: dict[str, Any]) -> None:
    _call(document, "retire")["path"] = "/admin/v2/datasources/{datasource_id}:purge"


def _write_with_other_method(document: dict[str, Any]) -> None:
    _call(document, "retire")["method"] = "POST"


def _v1_view_offers_v2_write(document: dict[str, Any]) -> None:
    document["views"][0]["actions"].append(_call(document, "retire")["id"])


def _duplicate_outcome(document: dict[str, Any]) -> None:
    outcomes = document["console"]["outcomes"]
    outcomes.append(dict(outcomes[0]))


@pytest.mark.parametrize(
    "mutation",
    [
        _probe_that_writes,
        _action_on_read,
        _field_outside_input,
        _secret_read_back,
        _records_without_items,
        _stamp_without_origin,
        _stamp_on_text,
        _typed_as_secret,
        _wrong_place,
        _foreign_wizard_field,
        _hidden_wizard_field,
        _open_without_lands,
        _write_on_first_prefix,
        _unapproved_second_prefix_write,
        _write_with_other_method,
        _v1_view_offers_v2_write,
        _duplicate_outcome,
    ],
)
def test_declared_writes_fail_closed(mutation: Mutation) -> None:
    document = copy.deepcopy(_document())
    validate_presentation(_encode(document))
    mutation(document)
    with pytest.raises(InvalidPresentationError):
        validate_presentation(_encode(document))
