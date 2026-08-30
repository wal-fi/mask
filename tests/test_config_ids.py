"""Fase 7, etapa 1: `id` e `revision` no modelo do arquivo.

Dois requisitos, e o segundo e o que importa para a seguranca:

1. Compatibilidade: o `masking.yaml` de hoje — sem `id`, sem `revision` —
   continua carregando. O MCP sobe sem Admin API e sem adocao.
2. Neutralidade: `id` e `revision` sao metadata ADMINISTRATIVA. Acrescenta-los
   nao pode mudar NENHUMA decisao de masking.

Ver a spec da Fase 7, secoes 5.2 e 5.5, e docs/DECISIONS.md (D-051, D-052).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from maskgw.config.ids import (
    EXCEPTION_ID_PATTERN,
    RULE_ID_PATTERN,
    new_exception_id,
    new_rule_id,
)
from maskgw.config.loader import compile_policy, load_config_text, validate_file_config
from maskgw.config.models import UNADOPTED_REVISION, MaskingFileConfig
from maskgw.errors import ConfigError
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingException, MaskingRule
from maskgw.secretsource import MappingSecretProvider

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config" / "masking.yaml"

SECRETS = MappingSecretProvider({"MASKGW_HMAC_KEY": "k" * 32})

#: Cobre regra direta, alias sobre coluna sensivel, exception legitima,
#: alias PARA o nome de uma exception (D-042), substring, coluna sem
#: correspondencia e posicao sem origem.
NEUTRALITY_COLUMNS = (
    ColumnDescriptor(output_name="cpf", origin_name="cpf"),
    ColumnDescriptor(output_name="documento", origin_name="cpf"),
    ColumnDescriptor(output_name="tipo_cpf", origin_name="tipo_cpf"),
    ColumnDescriptor(output_name="tipo_cpf", origin_name="cpf"),
    ColumnDescriptor(output_name="cliente_cpf", origin_name="cliente_cpf"),
    ColumnDescriptor(output_name="email", origin_name="email"),
    ColumnDescriptor(output_name="nome", origin_name="nome"),
    ColumnDescriptor(output_name="saldo", origin_name=None),
    ColumnDescriptor(output_name="x", origin_name=None, provenance_kind=ProvenanceKind.DERIVED),
)


class TestIdGeneration:
    def test_rule_id_matches_pattern(self) -> None:
        assert re.match(RULE_ID_PATTERN, new_rule_id())

    def test_exception_id_matches_pattern(self) -> None:
        assert re.match(EXCEPTION_ID_PATTERN, new_exception_id())

    def test_ids_are_unique(self) -> None:
        assert len({new_rule_id() for _ in range(500)}) == 500

    def test_rule_and_exception_ids_do_not_collide_in_prefix(self) -> None:
        assert not re.match(EXCEPTION_ID_PATTERN, new_rule_id())
        assert not re.match(RULE_ID_PATTERN, new_exception_id())


class TestBackwardCompatibility:
    """O arquivo de hoje carrega. E o requisito da secao 5.2."""

    def test_repo_config_still_loads(self) -> None:
        policy = load_config_text(REPO_CONFIG.read_text(encoding="utf-8"), secrets=SECRETS)
        assert policy.rules
        assert policy.exceptions

    def test_repo_config_is_unadopted(self) -> None:
        parsed = validate_file_config(yaml.safe_load(REPO_CONFIG.read_text(encoding="utf-8")))
        assert parsed.revision == UNADOPTED_REVISION
        assert all(rule.id is None for rule in parsed.masking)
        assert all(exc.id is None for exc in parsed.exceptions)

    def test_empty_document_is_unadopted(self) -> None:
        assert validate_file_config({}).revision == UNADOPTED_REVISION

    def test_file_without_revision_defaults_to_zero(self) -> None:
        parsed = validate_file_config({"masking": [{"match": "cpf", "transformer": "md5"}]})
        assert parsed.revision == UNADOPTED_REVISION
        assert parsed.masking[0].id is None


class TestAdoptedDocument:
    def test_revision_with_ids_is_accepted(self) -> None:
        parsed = validate_file_config(
            {
                "revision": 1,
                "masking": [{"match": "cpf", "transformer": "md5", "id": new_rule_id()}],
                "exceptions": [{"match": "tipo_cpf", "id": new_exception_id()}],
            }
        )
        assert parsed.revision == 1

    def test_revision_without_rule_id_is_rejected(self) -> None:
        with pytest.raises(ConfigError) as exc:
            validate_file_config(
                {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5"}]}
            )
        assert "masking[0]" in str(exc.value)

    def test_revision_without_exception_id_is_rejected(self) -> None:
        with pytest.raises(ConfigError) as exc:
            validate_file_config({"revision": 2, "exceptions": [{"match": "tipo_cpf"}]})
        assert "exceptions[0]" in str(exc.value)

    def test_rejection_message_says_what_to_do(self) -> None:
        with pytest.raises(ConfigError) as exc:
            validate_file_config(
                {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5"}]}
            )
        message = str(exc.value)
        assert "id" in message
        assert "revision" in message

    def test_adopted_with_no_items_is_valid(self) -> None:
        assert validate_file_config({"revision": 7}).revision == 7


class TestIdValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "rul_short",
            "rul_" + "f" * 31,
            "rul_" + "f" * 33,
            "rul_" + "F" * 32,  # hex maiusculo nao e o formato canonico
            "exc_" + "a" * 32,  # prefixo de exception num campo de regra
            "f" * 32,
            "",
            "rul_" + "g" * 32,
        ],
    )
    def test_invalid_rule_id_is_rejected(self, bad: str) -> None:
        with pytest.raises(ConfigError):
            validate_file_config(
                {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5", "id": bad}]}
            )

    def test_rule_id_in_exception_field_is_rejected(self) -> None:
        with pytest.raises(ConfigError):
            validate_file_config(
                {"revision": 1, "exceptions": [{"match": "tipo_cpf", "id": new_rule_id()}]}
            )

    def test_negative_revision_is_rejected(self) -> None:
        with pytest.raises(ConfigError):
            validate_file_config({"revision": -1})

    def test_unknown_top_level_key_still_forbidden(self) -> None:
        with pytest.raises(ConfigError):
            validate_file_config({"revisions": 1})


class TestAdministrativeMetadataIsNeutral:
    """A garantia da secao 5.5: adotar nao muda decisao de masking.

    Este teste e o que protege a migracao. Se um dia `id` ou `revision`
    vazarem para o matching, ele quebra.
    """

    @staticmethod
    def _decisions(raw: dict[str, object]) -> list[tuple[str, str | None, int | None]]:
        policy = compile_policy(validate_file_config(raw), secrets=SECRETS)
        engine = MaskingEngine(policy)
        out = []
        for column in NEUTRALITY_COLUMNS:
            decision = engine.decide(column)
            out.append((decision.action.value, decision.transformer_name, decision.rule_index))
        return out

    def test_decisions_identical_before_and_after_adoption(self) -> None:
        plain: dict[str, object] = {
            "masking": [
                {"match": "cpf", "transformer": "md5"},
                {"match": "email", "transformer": "fixed", "config": {"value": "x"}},
            ],
            "exceptions": [{"match": "tipo_cpf"}],
        }
        adopted: dict[str, object] = {
            "revision": 1,
            "masking": [
                {"match": "cpf", "transformer": "md5", "id": new_rule_id()},
                {
                    "match": "email",
                    "transformer": "fixed",
                    "config": {"value": "x"},
                    "id": new_rule_id(),
                },
            ],
            "exceptions": [{"match": "tipo_cpf", "id": new_exception_id()}],
        }
        assert self._decisions(plain) == self._decisions(adopted)

    def test_repo_config_decisions_survive_adoption(self) -> None:
        raw = yaml.safe_load(REPO_CONFIG.read_text(encoding="utf-8"))
        before = self._decisions(raw)

        adopted = dict(raw)
        adopted["revision"] = 1
        adopted["masking"] = [{**item, "id": new_rule_id()} for item in raw["masking"]]
        adopted["exceptions"] = [{**item, "id": new_exception_id()} for item in raw["exceptions"]]

        assert self._decisions(adopted) == before

    def test_revision_alone_changes_nothing(self) -> None:
        base: dict[str, object] = {"masking": [{"match": "cpf", "transformer": "md5"}]}
        with_revision = {**base, "revision": 0}
        assert self._decisions(base) == self._decisions(with_revision)


class TestModelSurface:
    def test_file_config_is_frozen(self) -> None:
        parsed = MaskingFileConfig()
        with pytest.raises(ValidationError):
            parsed.revision = 5

    def test_ids_are_not_part_of_match_spec(self) -> None:
        """O ID nao pode chegar ao nucleo puro: `masking/` nao o conhece."""
        assert not hasattr(MaskingRule, "id")
        assert not hasattr(MaskingException, "id")
