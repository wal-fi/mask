"""Grupos, tons e titulo do console v2 somente leitura (Fase 9, Etapa 5).

Os campos sao so de apresentacao: arrumam itens ja declarados, nunca criam
leitura, chamada ou caminho novo. O validador recusa grupo que esconda ou
duplique um item, tom desconhecido e titulo que nao aponte para texto.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.ui.protocol import InvalidPresentationError, validate_presentation

PRIVATE = Path("frontend/private/presentation.json")


def _document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(PRIVATE.read_bytes())
    return document


def _encode(document: dict[str, Any]) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")


def test_current_presentation_groups_every_entry_once():
    document = _document()
    validate_presentation(_encode(document))
    grouped = [tab for tab in document["console"]["detail"]["tabs"] if tab["groups"]]
    assert [tab["label"] for tab in grouped] == ["Visão geral", "Conexão", "Limites", "SQL"]
    for tab in grouped:
        members = [m for group in tab["groups"] for m in group["members"]]
        assert sorted(members) == sorted(entry["id"] for entry in tab["entries"])


def test_overview_does_not_repeat_the_title_and_never_checked_is_neutral():
    detail = _document()["console"]["detail"]
    overview = detail["tabs"][0]
    assert detail["title"] == ["datasource", "display_name"]
    assert all(entry["path"] != detail["title"] for entry in overview["entries"])
    tones = {
        word["value"]: word.get("tone")
        for entry in overview["entries"]
        for word in entry["wording"]
        if entry["path"][-1] == "status"
    }
    assert tones == {"never": "neutral", "passed": "good", "failed": "attention"}


def _first_grouped_tab(document: dict[str, Any]) -> dict[str, Any]:
    tab: dict[str, Any] = document["console"]["detail"]["tabs"][0]
    return tab


def _hide_entry(document: dict[str, Any]) -> None:
    _first_grouped_tab(document)["groups"][0]["members"].pop()


def _duplicate_entry(document: dict[str, Any]) -> None:
    groups = _first_grouped_tab(document)["groups"]
    groups[1]["members"].append(groups[0]["members"][0])


def _unknown_member(document: dict[str, Any]) -> None:
    _first_grouped_tab(document)["groups"][0]["members"][0] = "r999999"


def _unknown_tone(document: dict[str, Any]) -> None:
    document["console"]["summary"]["figures"][7]["wording"][0]["tone"] = "danger"


def _unknown_show(document: dict[str, Any]) -> None:
    _first_grouped_tab(document)["entries"][0]["show"] = "html"


def _title_not_text(document: dict[str, Any]) -> None:
    document["console"]["detail"]["title"] = ["datasource", "revision"]


def _title_outside_model(document: dict[str, Any]) -> None:
    document["console"]["detail"]["title"] = ["datasource", "nowhere"]


def _unknown_group_key(document: dict[str, Any]) -> None:
    _first_grouped_tab(document)["groups"][0]["script"] = "x"


@pytest.mark.parametrize(
    "mutation",
    [
        _hide_entry,
        _duplicate_entry,
        _unknown_member,
        _unknown_tone,
        _unknown_show,
        _title_not_text,
        _title_outside_model,
        _unknown_group_key,
    ],
)
def test_presentation_only_fields_fail_closed(mutation):
    document = copy.deepcopy(_document())
    mutation(document)
    with pytest.raises(InvalidPresentationError):
        validate_presentation(_encode(document))


# ---- Politica v1: paginas que so arrumam leituras aprovadas -----------------


def _views(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {view["label"]: view for view in document["views"]}


def test_every_v1_view_has_one_page_covering_exactly_its_reads():
    document = _document()
    pages = document["console"]["pages"]
    views = _views(document)
    assert [page["view"] for page in pages] == [view["id"] for view in document["views"]]
    for page in pages:
        view = next(v for v in document["views"] if v["id"] == page["view"])
        roots = [c["path"] for c in view["controls"] if c["type"] == "read"]
        shown = [e["path"] for s in page["sections"] for e in s["entries"]]
        assert all(any(path[: len(root)] == root for root in roots) for path in shown)
    assert views["Visão geral"]["id"] == pages[0]["view"]
    # Nenhum grupo repete o titulo da propria vista (dois cabecalhos iguais).
    for page in pages:
        view = next(v for v in document["views"] if v["id"] == page["view"])
        assert all(section["label"] != view["label"] for section in page["sections"])


def test_secrets_are_shown_only_as_declared_states():
    page = _document()["console"]["pages"][0]
    secrets = [e for s in page["sections"] for e in s["entries"] if e["path"][0] == "secrets"]
    assert len(secrets) == 3
    for entry in secrets:
        assert entry["kind"] == "text"
        assert {word["value"] for word in entry["wording"]} == {"configured", "missing"}


def _page_omits_field(document: dict[str, Any]) -> None:
    document["console"]["pages"][0]["sections"][0]["entries"].pop()


def _page_adds_field_outside_view(document: dict[str, Any]) -> None:
    entries = document["console"]["pages"][4]["sections"][1]["entries"]
    extra = copy.deepcopy(entries[0])
    extra.update(id="w99999", path=["config", "masking"], kind="tree")
    entries.append(extra)


def _page_unknown_view(document: dict[str, Any]) -> None:
    document["console"]["pages"][0]["view"] = "v99"


def _page_duplicate_view(document: dict[str, Any]) -> None:
    pages = document["console"]["pages"]
    pages[1]["view"] = pages[0]["view"]


def _page_list_index(document: dict[str, Any]) -> None:
    document["console"]["pages"][2]["sections"][1]["entries"][0]["path"] = ["rules", 0, "match"]


def _page_duplicate_id(document: dict[str, Any]) -> None:
    pages = document["console"]["pages"]
    pages[0]["sections"][0]["entries"][0]["id"] = pages[0]["sections"][0]["entries"][1]["id"]


@pytest.mark.parametrize(
    "mutation",
    [
        _page_omits_field,
        _page_adds_field_outside_view,
        _page_unknown_view,
        _page_duplicate_view,
        _page_list_index,
        _page_duplicate_id,
    ],
)
def test_v1_pages_fail_closed(mutation):
    document = copy.deepcopy(_document())
    mutation(document)
    with pytest.raises(InvalidPresentationError):
        validate_presentation(_encode(document))
