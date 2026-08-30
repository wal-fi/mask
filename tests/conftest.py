"""Fixtures compartilhadas.

Fase 1: chave HMAC de teste e providers de segredo.
Fase 2: DSN do PostgreSQL de integracao e dublês de conexao/cursor.

Nenhum usuario, senha ou DSN e escrito no codigo: o DSN de teste vem
exclusivamente da variavel de ambiente `MASKGW_TEST_DSN`, e os testes marcados
`integration` dao SKIP limpo quando ela nao esta definida.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest

from maskgw.config.gateway import DatabaseSettings, GatewayConfig
from maskgw.config.models import MaskingFileConfig
from maskgw.db.columns import DERIVED_ORIGIN, UNKNOWN_ORIGIN, ColumnOrigin
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingPolicy
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import MappingSecretProvider, SecretProvider
from maskgw.sql.policy import DEFAULT_SQL_POLICY

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

#: `(ftable, ftablecol)` de uma coluna. Ver maskgw.db.provenance.
ProvenanceKey = tuple[int, int]

#: O que o PostgreSQL devolve quando nao ha coluna de origem unica.
NO_ORIGIN: ProvenanceKey = (0, 0)


def origin_key(index: int) -> ProvenanceKey:
    """Chave sintetica e estavel para a coluna `index` dos dublês."""
    return (1000 + index, 1)


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


class FakePgResult:
    """Imita `psycopg.pq.PGresult` nos dois metodos de proveniencia."""

    def __init__(self, keys: Sequence[ProvenanceKey]) -> None:
        self._keys = list(keys)

    def ftable(self, column_number: int) -> int:
        return self._keys[column_number][0]

    def ftablecol(self, column_number: int) -> int:
        return self._keys[column_number][1]


class FakeResolver:
    """Resolver de proveniencia sem catalogo, para os testes sem banco."""

    def __init__(self, origins: Mapping[ProvenanceKey, ColumnOrigin] | None = None) -> None:
        self._origins = dict(origins or {})
        self.calls: list[tuple[ProvenanceKey, ...]] = []

    def resolve(self, keys: Sequence[ProvenanceKey]) -> tuple[ColumnOrigin, ...]:
        self.calls.append(tuple(keys))
        return tuple(
            DERIVED_ORIGIN if key == NO_ORIGIN else self._origins.get(key, UNKNOWN_ORIGIN)
            for key in keys
        )


class FakeCursor:
    def __init__(
        self,
        description: list[FakeColumn] | None,
        rows: Sequence[Sequence[Any]] = (),
        *,
        error: BaseException | None = None,
        keys: Sequence[ProvenanceKey] | None = None,
    ) -> None:
        self.description = description
        width = 0 if description is None else len(description)
        self.pgresult = FakePgResult(list(keys) if keys is not None else [NO_ORIGIN] * width)
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

    def fetchall(self) -> list[tuple[Any, ...]]:
        batch, self._pending = self._pending, []
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


# --------------------------------------------------------------------------
# Fase 7: montar um Runtime/Registry em volta de um adapter duble.
#
# O Gateway passou a adquirir e liberar um runtime por query (D-054), entao um
# teste que antes passava um adapter agora precisa do agregado. Nada aqui e
# especifico de um teste: e a mesma montagem minima em todos.
# --------------------------------------------------------------------------


def make_test_runtime(adapter: object, *, revision: int = 1) -> Runtime:
    """Runtime minimo em volta de um adapter duble."""
    policy = MaskingPolicy(exceptions=(), rules=())
    return Runtime(
        revision=revision,
        file_config=MaskingFileConfig(),
        config=GatewayConfig(
            masking=policy,
            database=DatabaseSettings(statement_timeout_ms=30_000, max_rows=1_000),
            sql=DEFAULT_SQL_POLICY,
        ),
        engine=MaskingEngine(policy),
        adapter=cast(PostgresAdapter, adapter),
    )


def make_test_registry(adapter: object) -> RuntimeRegistry:
    """Registry de um runtime so, para testes que nao exercitam reload."""
    return RuntimeRegistry(make_test_runtime(adapter))
