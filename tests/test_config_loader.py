"""Criterios de aceite 1, 2, 12 e 13 da Fase 1 (docs/ROADMAP.md).

Configuracao invalida deve IMPEDIR a inicializacao.
"""

from __future__ import annotations

import dataclasses

import pytest

from maskgw.config import load_config, load_config_text, parse_config
from maskgw.errors import ConfigError
from maskgw.masking.rules import MatchMode
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import MappingSecretProvider
from tests.conftest import REPO_CONFIG, TEST_HMAC_KEY

VALID = """
masking:
  - match: cpf
    mode: contains
    case_sensitive: false
    transformer: md5

exceptions:
  - match: tipo_cpf
    mode: exact
"""


class TestValidConfig:
    def test_loads_and_compiles(self, secrets):
        policy = load_config_text(VALID, secrets=secrets)
        assert len(policy.rules) == 1
        assert len(policy.exceptions) == 1
        assert policy.rules[0].transformer_name == "md5"
        assert policy.rules[0].spec.mode is MatchMode.CONTAINS
        assert policy.exceptions[0].spec.mode is MatchMode.EXACT

    def test_defaults_are_case_insensitive_contains(self, secrets):
        text = "masking:\n  - match: cpf\n    transformer: md5\n"
        policy = load_config_text(text, secrets=secrets)
        spec = policy.rules[0].spec
        assert spec.mode is MatchMode.CONTAINS
        assert spec.case_sensitive is False

    def test_policy_is_immutable(self, secrets):
        """Criterio: o cliente nao pode alterar regras em runtime."""
        policy = load_config_text(VALID, secrets=secrets)
        with pytest.raises(dataclasses.FrozenInstanceError):
            policy.rules[0].spec.pattern = "outro"  # type: ignore[misc]
        assert isinstance(policy.rules, tuple)
        assert isinstance(policy.exceptions, tuple)

    def test_empty_file_is_valid_and_masks_nothing(self, secrets):
        policy = load_config_text("", secrets=secrets)
        assert policy.rules == ()
        assert policy.exceptions == ()

    def test_repository_config_loads(self, secrets):
        """Criterio 1: o config/masking.yaml do repositorio carrega."""
        policy = load_config(REPO_CONFIG, secrets=secrets)
        assert [rule.transformer_name for rule in policy.rules] == [
            "hmac_sha256",
            "hmac_sha256",
            "regex",
            "random",
            "fixed",
        ]
        assert [exc.spec.pattern for exc in policy.exceptions] == ["tipo_cpf"]


class TestFailClosed:
    """Criterio 2: cada item abaixo impede a inicializacao."""

    def test_malformed_yaml(self, secrets):
        with pytest.raises(ConfigError, match="malformado"):
            load_config_text("masking: [unclosed\n", secrets=secrets)

    def test_top_level_not_a_mapping(self, secrets):
        with pytest.raises(ConfigError, match="mapa no topo"):
            load_config_text("- just\n- a\n- list\n", secrets=secrets)

    def test_unknown_top_level_key(self, secrets):
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text("masking: []\nmaskingg: []\n", secrets=secrets)

    def test_unknown_rule_key(self, secrets):
        """Erro de digitacao em campo de regra e fatal."""
        text = "masking:\n  - match: cpf\n    transfomer: md5\n"
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text(text, secrets=secrets)

    def test_unknown_transformer(self, secrets):
        text = "masking:\n  - match: cpf\n    transformer: md6\n"
        with pytest.raises(ConfigError, match="transformer desconhecido"):
            load_config_text(text, secrets=secrets)

    def test_invalid_mode(self, secrets):
        text = "masking:\n  - match: cpf\n    mode: fuzzy\n    transformer: md5\n"
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text(text, secrets=secrets)

    def test_empty_match_pattern(self, secrets):
        text = "masking:\n  - match: ''\n    transformer: md5\n"
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text(text, secrets=secrets)

    def test_missing_transformer_field(self, secrets):
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text("masking:\n  - match: cpf\n", secrets=secrets)

    def test_exception_cannot_declare_transformer(self, secrets):
        text = "exceptions:\n  - match: tipo_cpf\n    transformer: md5\n"
        with pytest.raises(ConfigError, match="configuracao invalida"):
            load_config_text(text, secrets=secrets)

    def test_invalid_regex_pattern(self, secrets):
        text = (
            "masking:\n"
            "  - match: email\n"
            "    transformer: regex\n"
            "    config:\n"
            "      pattern: '([unclosed'\n"
            "      replacement: 'x'\n"
        )
        with pytest.raises(ConfigError, match="pattern invalido"):
            load_config_text(text, secrets=secrets)

    def test_invalid_regex_replacement_backreference(self, secrets):
        text = (
            "masking:\n"
            "  - match: email\n"
            "    transformer: regex\n"
            "    config:\n"
            "      pattern: '(a)'\n"
            "      replacement: '\\9'\n"
        )
        with pytest.raises(ConfigError, match="replacement invalido"):
            load_config_text(text, secrets=secrets)

    def test_invalid_regex_replacement_named_group(self, secrets):
        text = (
            "masking:\n"
            "  - match: email\n"
            "    transformer: regex\n"
            "    config:\n"
            "      pattern: '(a)'\n"
            "      replacement: '\\g<inexistente>'\n"
        )
        with pytest.raises(ConfigError, match="grupo inexistente"):
            load_config_text(text, secrets=secrets)

    def test_missing_required_transformer_param(self, secrets):
        text = "masking:\n  - match: senha\n    transformer: fixed\n"
        with pytest.raises(ConfigError, match="obrigatorio"):
            load_config_text(text, secrets=secrets)

    def test_unknown_transformer_param(self, secrets):
        text = (
            "masking:\n"
            "  - match: senha\n"
            "    transformer: fixed\n"
            "    config:\n"
            "      value: 'x'\n"
            "      extra: 'y'\n"
        )
        with pytest.raises(ConfigError, match="desconhecido"):
            load_config_text(text, secrets=secrets)

    def test_error_identifies_offending_rule(self, secrets):
        text = (
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: md5\n"
            "  - match: senha\n"
            "    transformer: fixed\n"
        )
        with pytest.raises(ConfigError, match=r"regra #1 \(match='senha'\)"):
            load_config_text(text, secrets=secrets)

    def test_missing_file(self, secrets, tmp_path):
        with pytest.raises(ConfigError, match="nao foi possivel ler"):
            load_config(tmp_path / "ausente.yaml", secrets=secrets)


class TestHmacKeyHandling:
    """Criterios 12 e 13."""

    def test_missing_key_blocks_startup(self, no_secrets):
        text = "masking:\n  - match: cpf\n    transformer: hmac_sha256\n"
        with pytest.raises(ConfigError, match="chave HMAC ausente"):
            load_config_text(text, secrets=no_secrets)

    def test_blank_key_counts_as_missing(self):
        text = "masking:\n  - match: cpf\n    transformer: hmac_sha256\n"
        provider = MappingSecretProvider({HMAC_KEY_ENV: "   "})
        with pytest.raises(ConfigError, match="chave HMAC ausente"):
            load_config_text(text, secrets=provider)

    def test_short_key_blocks_startup(self):
        text = "masking:\n  - match: cpf\n    transformer: hmac_sha256\n"
        provider = MappingSecretProvider({HMAC_KEY_ENV: "curta"})
        with pytest.raises(ConfigError, match="muito curta"):
            load_config_text(text, secrets=provider)

    @pytest.mark.parametrize("param", ["key", "secret", "hmac_key", "salt", "pepper", "token"])
    def test_secret_in_yaml_is_rejected(self, secrets, param):
        """Criterio 13: o YAML nao pode carregar a chave."""
        text = (
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: hmac_sha256\n"
            "    config:\n"
            f"      {param}: 'algum-segredo'\n"
        )
        with pytest.raises(ConfigError) as info:
            load_config_text(text, secrets=secrets)
        assert param in str(info.value)
        assert "algum-segredo" not in str(info.value)

    def test_secret_param_rejected_for_any_transformer(self, secrets):
        text = (
            "masking:\n"
            "  - match: cpf\n"
            "    transformer: md5\n"
            "    config:\n"
            "      key: 'algum-segredo'\n"
        )
        with pytest.raises(ConfigError) as info:
            load_config_text(text, secrets=secrets)
        assert "algum-segredo" not in str(info.value)

    def test_hmac_accepts_no_parameters(self, secrets):
        text = (
            "masking:\n  - match: cpf\n    transformer: hmac_sha256\n    config:\n      rounds: 2\n"
        )
        with pytest.raises(ConfigError, match="nao aceita parametros"):
            load_config_text(text, secrets=secrets)

    def test_key_never_appears_in_repr(self, secrets):
        text = "masking:\n  - match: cpf\n    transformer: hmac_sha256\n"
        policy = load_config_text(text, secrets=secrets)
        rendered = repr(policy)
        assert TEST_HMAC_KEY not in rendered
        assert "redacted" in rendered


class TestParseConfig:
    def test_accepts_already_parsed_mapping(self, secrets):
        policy = parse_config(
            {"masking": [{"match": "cpf", "transformer": "md5"}]},
            secrets=secrets,
        )
        assert len(policy.rules) == 1

    def test_none_is_empty_policy(self, secrets):
        assert parse_config(None, secrets=secrets).rules == ()
