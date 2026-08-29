"""Fixtures compartilhadas da Fase 1."""

from __future__ import annotations

from pathlib import Path

import pytest

from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import MappingSecretProvider, SecretProvider

#: Chave de teste. Nao e segredo real; existe apenas para exercitar o HMAC.
TEST_HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"
OTHER_HMAC_KEY = "outra-chave-de-teste-para-hmac-com-tamanho-ok"

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_CONFIG = REPO_ROOT / "config" / "masking.yaml"


@pytest.fixture
def secrets() -> SecretProvider:
    """Provider com a chave HMAC disponivel."""
    return MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY})


@pytest.fixture
def no_secrets() -> SecretProvider:
    """Provider sem nenhum segredo."""
    return MappingSecretProvider({})
