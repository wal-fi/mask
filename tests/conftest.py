"""Fixtures compartilhadas.

Fase 1: chave HMAC de teste e providers de segredo.
Fase 2: DSN do PostgreSQL de integracao e dublês de conexao/cursor.

Nenhum usuario, senha ou DSN e escrito no codigo: o DSN de teste vem
exclusivamente da variavel de ambiente `MASKGW_TEST_DSN`, e os testes marcados
`integration` dao SKIP limpo quando ela nao esta definida.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import psycopg
import pytest

from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import MappingSecretProvider, SecretProvider

#: Chave de teste. Nao e segredo real; existe apenas para exercitar o HMAC.
TEST_HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"
OTHER_HMAC_KEY = "outra-chave-de-teste-para-hmac-com-tamanho-ok"

#: Variavel que carrega o DSN do PostgreSQL usado nos testes de integracao.
DSN_ENV = "MASKGW_TEST_DSN"

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_CONFIG = REPO_ROOT / "config" / "masking.yaml"

TransactionStatus = psycopg.pq.TransactionStatus
IDLE = TransactionStatus.IDLE
INTRANS = TransactionStatus.INTRANS


@pytest.fixture
def secrets() -> SecretProvider:
    """Provider com a chave HMAC disponivel."""
    return MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY})


@pytest.fixture
def no_secrets() -> SecretProvider:
    """Provider sem nenhum segredo."""
    return MappingSecretProvider({})


@pytest.fixture
def dsn() -> str:
    """DSN do PostgreSQL de integracao, ou SKIP limpo quando ausente."""
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        pytest.skip(f"{DSN_ENV} nao definida: teste de integracao pulado")
    return value


# --------------------------------------------------------------------------
# Dublês: permitem exercitar o adapter inteiro sem banco, mantendo a suite
# verde em qualquer maquina. O contrato imitado e o minimo que o adapter usa.
# --------------------------------------------------------------------------


class FakeColumn:
    """Imita `psycopg.Column` no unico atributo consumido: `name`."""

    def __init__(self, name: str) -> None:
        self.name = name


class FakeCursor:
    def __init__(
        self,
        description: list[FakeColumn] | None,
        rows: Sequence[Sequence[Any]] = (),
        *,
        error: BaseException | None = None,
    ) -> None:
        self.description = description
        self._pending = [tuple(row) for row in rows]
        self._error = error
        self.executed: list[tuple[str, Any]] = []
        self.batch_sizes: list[int] = []
        self.closed = False

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True

    def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))
        if self._error is not None:
            raise self._error

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        self.batch_sizes.append(size)
        batch, self._pending = self._pending[:size], self._pending[size:]
        return batch


class FakeInfo:
    def __init__(self, transaction_status: TransactionStatus) -> None:
        self.transaction_status = transaction_status


class FakeConnection:
    def __init__(
        self,
        cursor: FakeCursor,
        *,
        transaction_status: TransactionStatus = IDLE,
        rollback_error: BaseException | None = None,
    ) -> None:
        self._cursor = cursor
        self._rollback_error = rollback_error
        self.info = FakeInfo(transaction_status)
        self.closed = False
        self.rollbacks = 0
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return self._cursor

    def rollback(self) -> None:
        self.rollbacks += 1
        if self._rollback_error is not None:
            raise self._rollback_error
        self.info.transaction_status = IDLE

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True
