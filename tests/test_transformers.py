"""Criterios de aceite 7 a 11 da Fase 1 (docs/ROADMAP.md).

Cada transformer e testado com: entrada normal, NULL, string vazia, Unicode,
valor grande e entrada invalida quando aplicavel.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from maskgw.errors import ConfigError
from maskgw.masking.transformers import build_default_registry
from maskgw.masking.transformers.base import REDACTED
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.masking.transformers.randomize import RandomStrategy
from maskgw.secretsource import MappingSecretProvider
from tests.conftest import OTHER_HMAC_KEY, TEST_HMAC_KEY

UNICODE = "José da Silva — 中文 — 🙂"
LARGE = "9" * 100_000

ALL_TRANSFORMERS = [
    ("md5", {}),
    ("sha256", {}),
    ("sha512", {}),
    ("hmac_sha256", {}),
    ("regex", {"pattern": "^(.{2}).*(@.*)$", "replacement": r"\1***\2"}),
    ("random", {"strategy": "alphanumeric"}),
    ("fixed", {"value": "[REDACTED]"}),
    ("truncate", {"length": 3}),
]

DETERMINISTIC = [item for item in ALL_TRANSFORMERS if item[0] != "random"]


@pytest.fixture
def registry():
    return build_default_registry()


@pytest.fixture
def build(registry, secrets):
    def _build(name, config=None):
        return registry.build(name, config or {}, secrets)

    return _build


class TestRegistry:
    def test_all_mvp_transformers_available(self, registry):
        assert registry.available() == (
            "fixed",
            "hmac_sha256",
            "md5",
            "random",
            "regex",
            "sha256",
            "sha512",
            "truncate",
        )

    def test_unknown_transformer_raises(self, registry, secrets):
        with pytest.raises(ConfigError, match="transformer desconhecido"):
            registry.build("md6", {}, secrets)

    def test_duplicate_registration_rejected(self, registry):
        with pytest.raises(ConfigError, match="ja registrado"):
            registry.register("md5", lambda _config, _secrets: None)

    def test_registry_is_extensible_without_touching_core(self, registry, secrets):
        """Criterio de arquitetura: novo transformer sem alterar o engine."""

        class Shout:
            deterministic = True

            def apply(self, value):
                return None if value is None else str(value).upper()

        registry.register("shout", lambda _config, _secrets: Shout())
        assert registry.build("shout", {}, secrets).apply("abc") == "ABC"


class TestContractForEveryTransformer:
    @pytest.mark.parametrize(("name", "config"), ALL_TRANSFORMERS)
    def test_null_stays_null(self, build, name, config):
        """Criterio 7: NULL permanece NULL em todos os transformers."""
        assert build(name, config).apply(None) is None

    @pytest.mark.parametrize(("name", "config"), ALL_TRANSFORMERS)
    def test_empty_string(self, build, name, config):
        result = build(name, config).apply("")
        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.parametrize(("name", "config"), ALL_TRANSFORMERS)
    def test_unicode(self, build, name, config):
        result = build(name, config).apply(UNICODE)
        assert isinstance(result, str)

    @pytest.mark.parametrize(("name", "config"), ALL_TRANSFORMERS)
    def test_large_value(self, build, name, config):
        result = build(name, config).apply(LARGE)
        assert isinstance(result, str)

    @pytest.mark.parametrize(("name", "config"), ALL_TRANSFORMERS)
    def test_non_string_input_is_coerced(self, build, name, config):
        assert isinstance(build(name, config).apply(12345), str)

    @pytest.mark.parametrize(("name", "config"), DETERMINISTIC)
    def test_deterministic(self, build, name, config):
        """Criterio 9."""
        transformer = build(name, config)
        first = transformer.apply("teste@exemplo.com")
        second = transformer.apply("teste@exemplo.com")
        assert first == second
        assert transformer.deterministic is True

    @pytest.mark.parametrize(("name", "config"), DETERMINISTIC)
    def test_deterministic_across_instances(self, build, name, config):
        assert build(name, config).apply("a@b.co") == build(name, config).apply("a@b.co")


class TestHashes:
    @pytest.mark.parametrize(
        ("name", "digest"),
        [("md5", hashlib.md5), ("sha256", hashlib.sha256), ("sha512", hashlib.sha512)],
    )
    def test_matches_reference_digest(self, build, name, digest):
        value = "12345678901"
        expected = digest(value.encode("utf-8"), usedforsecurity=False).hexdigest()
        assert build(name).apply(value) == expected

    def test_hashes_reject_parameters(self, build):
        with pytest.raises(ConfigError, match="nao aceita parametros"):
            build("md5", {"length": 3})

    def test_different_inputs_differ(self, build):
        assert build("sha256").apply("a") != build("sha256").apply("b")


class TestHmacSha256:
    def test_matches_reference(self, build):
        value = "12345678901"
        expected = hmac.new(
            TEST_HMAC_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        assert build("hmac_sha256").apply(value) == expected

    def test_different_keys_produce_different_output(self, registry):
        """Criterio 11."""
        value = "12345678901"
        first = registry.build(
            "hmac_sha256", {}, MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY})
        )
        second = registry.build(
            "hmac_sha256", {}, MappingSecretProvider({HMAC_KEY_ENV: OTHER_HMAC_KEY})
        )
        assert first.apply(value) != second.apply(value)

    def test_differs_from_plain_sha256(self, build):
        value = "12345678901"
        assert build("hmac_sha256").apply(value) != build("sha256").apply(value)

    def test_key_absent_from_repr_and_errors(self, build):
        transformer = build("hmac_sha256")
        assert TEST_HMAC_KEY not in repr(transformer)
        assert "redacted" in repr(transformer)


class TestRegex:
    @pytest.fixture
    def email(self, build):
        return build("regex", {"pattern": "^(.{2}).*(@.*)$", "replacement": r"\1***\2"})

    def test_masks_email(self, email):
        assert email.apply("joao.silva@empresa.com.br") == "jo***@empresa.com.br"

    def test_non_matching_value_is_redacted_not_leaked(self, email):
        """Fail-closed: sem match, jamais devolver o original (D-003)."""
        assert email.apply("sem-arroba") == REDACTED
        assert email.apply("") == REDACTED

    def test_missing_required_params(self, build):
        with pytest.raises(ConfigError, match="obrigatorio"):
            build("regex", {"pattern": "a"})

    def test_non_string_pattern(self, build):
        with pytest.raises(ConfigError, match="deve ser string"):
            build("regex", {"pattern": 42, "replacement": "x"})

    def test_pattern_not_in_repr_leak(self, email):
        assert "joao.silva" not in repr(email)


class TestRandom:
    def test_not_deterministic(self, build):
        """Criterio 10."""
        transformer = build("random", {"strategy": "alphanumeric"})
        assert transformer.deterministic is False
        results = {transformer.apply("12345678901") for _ in range(20)}
        assert len(results) > 1

    def test_preserve_length_is_default(self, build):
        transformer = build("random", {"strategy": "digits"})
        assert len(transformer.apply("12345678901")) == 11

    def test_digits_strategy_alphabet(self, build):
        result = build("random", {"strategy": "digits"}).apply("1234567890")
        assert result.isdigit()

    def test_alphanumeric_strategy_alphabet(self, build):
        result = build("random", {"strategy": "alphanumeric"}).apply("x" * 200)
        assert result.isalnum()
        assert result.isascii()

    def test_fixed_length_when_not_preserving(self, build):
        transformer = build("random", {"strategy": "digits", "preserve_length": False, "length": 6})
        assert len(transformer.apply("1")) == 6
        assert len(transformer.apply("1234567890")) == 6

    def test_empty_string_with_preserve_length(self, build):
        assert build("random", {"strategy": "digits"}).apply("") == ""

    def test_strategy_is_required(self, build):
        with pytest.raises(ConfigError, match="obrigatorio"):
            build("random", {})

    def test_unknown_strategy(self, build):
        with pytest.raises(ConfigError, match="strategy 'base64' invalida"):
            build("random", {"strategy": "base64"})

    def test_length_required_when_not_preserving(self, build):
        with pytest.raises(ConfigError, match="'length' e obrigatorio"):
            build("random", {"strategy": "digits", "preserve_length": False})

    def test_length_forbidden_when_preserving(self, build):
        with pytest.raises(ConfigError, match="ambigua"):
            build("random", {"strategy": "digits", "preserve_length": True, "length": 4})

    def test_non_boolean_preserve_length(self, build):
        with pytest.raises(ConfigError, match="booleano"):
            build("random", {"strategy": "digits", "preserve_length": "yes"})

    def test_negative_length(self, build):
        with pytest.raises(ConfigError, match=">= 0"):
            build("random", {"strategy": "digits", "preserve_length": False, "length": -1})

    def test_all_strategies_are_covered(self):
        assert {item.value for item in RandomStrategy} == {"alphanumeric", "digits"}


class TestFixed:
    def test_replaces_any_value(self, build):
        transformer = build("fixed", {"value": "[REDACTED]"})
        assert transformer.apply("qualquer") == "[REDACTED]"
        assert transformer.apply(UNICODE) == "[REDACTED]"

    def test_value_required(self, build):
        with pytest.raises(ConfigError, match="obrigatorio"):
            build("fixed", {})

    def test_value_must_be_string(self, build):
        with pytest.raises(ConfigError, match="deve ser string"):
            build("fixed", {"value": 5})


class TestTruncate:
    def test_keeps_prefix(self, build):
        assert build("truncate", {"length": 3}).apply("12345678901") == "123"

    def test_shorter_than_length(self, build):
        assert build("truncate", {"length": 10}).apply("abc") == "abc"

    def test_zero_length(self, build):
        assert build("truncate", {"length": 0}).apply("abc") == ""

    def test_length_required(self, build):
        with pytest.raises(ConfigError, match="obrigatorio"):
            build("truncate", {})

    def test_negative_length(self, build):
        with pytest.raises(ConfigError, match=">= 0"):
            build("truncate", {"length": -1})

    def test_boolean_is_not_an_integer(self, build):
        with pytest.raises(ConfigError, match="deve ser inteiro"):
            build("truncate", {"length": True})
