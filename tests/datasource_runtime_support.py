"""Apoio dos testes da Fase 9, Etapa 3: adapters dublês e montagem minima.

O dublê imita somente o contrato que o registry e a sessao consomem do
`PostgresAdapter`: `connect`, `close`, `cancel` e `execute_validated`. Ele
registra cada chamada e pode bloquear a execucao para simular uma consulta em
voo, que so termina quando o teste libera ou quando `cancel()` chega — como o
cancelamento do PostgreSQL faria.
"""

from __future__ import annotations

import ipaddress
import threading
from dataclasses import dataclass, field
from typing import cast

from maskgw.config.gateway import DatabaseSettings, GatewayConfig
from maskgw.config.models import MaskingFileConfig
from maskgw.datasource.models import DatasourceDraft, DestinationPolicy
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.result import MaskedResult
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingPolicy
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import PreparedRuntime
from maskgw.secretsource import MappingSecretProvider
from maskgw.sql.policy import DEFAULT_SQL_POLICY

KEY = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
SECRET = "synthetic-upstream-canary-7f3a"  # noqa: S105 - marcador sintetico de teste
OTHER_SECRET = "synthetic-rotated-canary-91bd"  # noqa: S105 - marcador sintetico de teste
HOST = "db.internal.example"
ADDRESS = "10.0.0.7"
HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"


def secrets_provider() -> MappingSecretProvider:
    return MappingSecretProvider({"MASKGW_DATASOURCE_MASTER_KEY": KEY, HMAC_KEY_ENV: HMAC_KEY})


def resolver(host: str, _port: int) -> tuple[str, ...]:
    """DNS sintetico: IP literal resolve para si mesmo; nome, para `ADDRESS`."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return (ADDRESS,)
    return (host,)


def draft(
    alias: str = "primary",
    *,
    enabled: bool = True,
    host: str = HOST,
    max_rows: int | None = None,
) -> DatasourceDraft:
    from maskgw.datasource.models import DatasourceLimits, DatasourcePolicy  # noqa: PLC0415

    policy = DatasourcePolicy.from_mapping(
        {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
    )
    limits = DatasourceLimits() if max_rows is None else DatasourceLimits(max_rows=max_rows)
    return DatasourceDraft(
        alias=alias,
        display_name=alias.title(),
        host=host,
        port=5432,
        database="app",
        username="gateway",
        enabled=enabled,
        policy=policy,
        limits=limits,
        destination_policy=DestinationPolicy(),
    )


class FakeAdapter:
    """Dublê do `PostgresAdapter` com contagem e bloqueio controlados."""

    def __init__(self, factory: FakeFactory, conninfo: str) -> None:
        self.factory = factory
        self.conninfo = conninfo
        self.connected = False
        self.connects = 0
        self.closes = 0
        self.cancels = 0
        self.executions = 0
        self._release = threading.Event()
        self._cancelled = threading.Event()
        self.started = threading.Event()

    @property
    def closed(self) -> bool:
        return not self.connected

    def connect(self) -> None:
        self.connects += 1
        failure = self.factory.connect_failure
        if failure is not None:
            raise failure
        gate = self.factory.connect_gate
        if gate is not None:
            self.factory.connect_started.set()
            gate.wait(timeout=10)
        self.connected = True

    def close(self) -> None:
        self.closes += 1
        self.connected = False

    def cancel(self) -> None:
        self.cancels += 1
        self._cancelled.set()
        self._release.set()

    def release(self) -> None:
        self._release.set()

    def execute_validated(self, _sql: str) -> MaskedResult:
        if not self.connected:
            msg = "conexao com o banco de dados nao esta aberta"
            raise DatabaseError(msg)
        self.executions += 1
        if self.factory.block_execution:
            self.started.set()
            self._release.wait(timeout=10)
            if self._cancelled.is_set():
                msg = "consulta cancelada"
                raise DatabaseError(msg)
        return MaskedResult(columns=(), decisions=(), rows=(), truncated=False)


@dataclass
class FakeFactory:
    """Fabrica de adapters dublês; guarda todos os que criou."""

    connect_failure: BaseException | None = None
    block_execution: bool = False
    connect_gate: threading.Event | None = None
    connect_started: threading.Event = field(default_factory=threading.Event)
    adapters: list[FakeAdapter] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __call__(
        self,
        conninfo: str,
        *,
        config: GatewayConfig,
        engine: MaskingEngine,
    ) -> PostgresAdapter:
        del config, engine
        adapter = FakeAdapter(self, conninfo)
        with self.lock:
            self.adapters.append(adapter)
        return cast(PostgresAdapter, adapter)

    def open_adapters(self) -> list[FakeAdapter]:
        with self.lock:
            return [adapter for adapter in self.adapters if adapter.connected]


def capability_failure() -> CapabilityError:
    return CapabilityError("capability sintetica ausente")


def prepared(factory: FakeFactory, *, max_sessions: int = 8) -> PreparedRuntime:
    """Candidato ja pronto, sem passar por destino nem conexao."""
    policy = MaskingPolicy(exceptions=(), rules=())
    config = GatewayConfig(
        masking=policy,
        database=DatabaseSettings(statement_timeout_ms=30_000, max_rows=1_000),
        sql=DEFAULT_SQL_POLICY,
    )
    return PreparedRuntime(
        file_config=MaskingFileConfig(),
        config=config,
        engine=MaskingEngine(policy),
        conninfo=f"host={HOST} password={SECRET}",
        addresses=(ADDRESS,),
        max_sessions=max_sessions,
        adapter_factory=factory,
    )


DS_A = "dso_" + "a" * 32
DS_B = "dso_" + "b" * 32
DS_C = "dso_" + "c" * 32
