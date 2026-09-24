"""Apoio dos testes da Admin API v2 (Fase 9, Etapa 4). Nao e arquivo de teste.

Monta, sobre `tmp_path`, o que o composition root monta: a secao critica v1
real (`AdminConfigService` sobre um `masking.yaml` real), o catalogo cifrado
real, o registry e o coordenador reais, e o servidor HTTP real escutando em
loopback. Os adapters upstream sao os dubles da Etapa 3 — a Admin API nao
executa SQL, e o candidato so abre e fecha a conexao de verificacao.

Os valores de destino e segredo sao CANARIOS distintos, para que um teste de
vazamento procure strings que nao aparecem por acaso em texto de politica.
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maskgw.admin.http import AdminHttpServer, build_admin_app
from maskgw.audit import AuditLog
from maskgw.datasource import CatalogHooks, CatalogStore, CatalogWriteError, CrashPoint
from maskgw.datasource.destination import AddressResolver
from maskgw.runtime.datasource_service import DatasourceRuntime, DatasourceRuntimeService
from maskgw.runtime.datasources import DatasourceRegistry, RegistryLimits
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import (
    SENSITIVE_DSN,
    SENSITIVE_HMAC,
    TOKEN,
    Harness,
    Reply,
    build_service,
    request,
)
from tests.datasource_runtime_support import KEY, FakeFactory

HMAC_KEY = "chave-de-teste-para-hmac-com-tamanho-suficiente"

#: Canarios. Nenhum deles pode aparecer em erro, auditoria ou resposta de outro
#: plano; host/database/usuario aparecem SO na leitura administrativa do detalhe.
SECRET = "upstream-canary-password-7f3a"  # noqa: S105 - marcador sintetico
OTHER_SECRET = "rotated-canary-password-91bd"  # noqa: S105 - marcador sintetico
HOST = "db-canary.internal.example"
OTHER_HOST = "db-other-canary.internal.example"
ADDRESS = "10.20.30.40"
OTHER_ADDRESS = "10.20.30.41"
DATABASE = "canary_database"
USERNAME = "canary_user"
ALIAS = "crm-canary"
OTHER_ALIAS = "fin-canary"

UPSTREAM_CANARIES = (
    SECRET,
    OTHER_SECRET,
    HOST,
    OTHER_HOST,
    ADDRESS,
    OTHER_ADDRESS,
    DATABASE,
    USERNAME,
)

POLICY: dict[str, Any] = {
    "masking": [{"match": "cpf", "transformer": "hmac_sha256"}],
    "exceptions": [{"match": "tipo_cpf"}],
    "database": {"statement_timeout_ms": 5_000, "max_rows": 500},
    "sql": {"denied_functions": ["dblink_exec"]},
}


def dns(host: str, _port: int) -> tuple[str, ...]:
    """DNS sintetico: cada canario resolve para o seu endereco privado."""
    table = {HOST: (ADDRESS,), OTHER_HOST: (OTHER_ADDRESS,)}
    return table.get(host, (host,))


def create_body(  # noqa: PLR0913 - campos do corpo, todos keyword-only
    *,
    alias: str = ALIAS,
    host: str = HOST,
    enabled: bool = True,
    expected: int = 1,
    password: str = SECRET,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "expected_catalog_revision": expected,
        "alias": alias,
        "display_name": alias.upper(),
        "enabled": enabled,
        "connection": {
            "host": host,
            "port": 5432,
            "database": DATABASE,
            "username": USERNAME,
            "tls": {"mode": "disable", "server_name": None},
        },
        "credential": {"password": password},
        "limits": {"statement_timeout_ms": 30_000, "max_rows": 100, "max_sessions": 4},
        "destination_policy": {"allow_public": False, "allow_loopback": False, "allowed_hosts": []},
        "policy": copy.deepcopy(POLICY if policy is None else policy),
    }


def draft_body(**kwargs: Any) -> dict[str, Any]:
    body = create_body(**kwargs)
    del body["expected_catalog_revision"], body["enabled"]
    return body


def update_body(expected: int, *, host: str = HOST, display_name: str = "Novo") -> dict[str, Any]:
    body = create_body(host=host)
    return {
        "expected_revision": expected,
        "display_name": display_name,
        "connection": body["connection"],
        "limits": {"statement_timeout_ms": 20_000, "max_rows": 50, "max_sessions": 2},
        "destination_policy": body["destination_policy"],
    }


class AuditCapture(logging.Handler):
    """Coleta os campos estruturados de cada registro do logger isolado."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append(dict(record.__dict__.get("maskgw", {})))

    def datasource_events(self) -> list[dict[str, Any]]:
        return [e for e in self.events if str(e.get("operation", "")).startswith("datasource_")]


class Crash:
    """Falha armada sob demanda num ponto do protocolo de commit."""

    def __init__(self) -> None:
        self.point: CrashPoint | None = None

    def __call__(self, point: CrashPoint) -> None:
        if point == self.point:
            self.point = None
            msg = f"falha sintetica {HOST} {SECRET}"
            raise CatalogWriteError(msg)


@dataclass
class V2Harness:
    tmp_path: Path
    v1: Harness
    store: CatalogStore
    registry: DatasourceRegistry
    service: DatasourceRuntimeService
    runtime: DatasourceRuntime
    factory: FakeFactory
    crash: Crash
    audit: AuditCapture
    audit_log: AuditLog
    secrets: MappingSecretProvider
    server: AdminHttpServer | None = None
    _logger: logging.Logger | None = field(default=None, repr=False)

    @property
    def port(self) -> int:
        assert self.server is not None
        return self.server.port

    def start(self, *, with_v2: bool = True) -> AdminHttpServer:
        def factory(bound_port: int) -> Any:
            return build_admin_app(
                self.v1.service,
                token=TOKEN,
                port=bound_port,
                secrets=self.secrets,
                database_dsn_env="MASKGW_DATABASE_DSN",
                audit=self.audit_log,
                datasources=self.runtime if with_v2 else None,
            )

        self.server = AdminHttpServer(app_factory=factory, host="127.0.0.1", port=0)
        self.server.start()
        return self.server

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        raw: bytes | None = None,
        **kwargs: Any,
    ) -> Reply:
        payload = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        content_type = kwargs.pop(
            "content_type", "application/json" if payload is not None else None
        )
        return request(self.port, method, path, body=payload, content_type=content_type, **kwargs)

    def create(self, **kwargs: Any) -> dict[str, Any]:
        expected = kwargs.pop("expected", self.store.revision)
        reply = self.call("POST", "/admin/v2/datasources", create_body(expected=expected, **kwargs))
        assert reply.status == 200, reply.text()
        result: dict[str, Any] = reply.json()
        return result

    def disk(self) -> tuple[bytes, bytes]:
        return self.store.store_path.read_bytes(), self.store.anchor_path.read_bytes()

    def published(self) -> dict[str, int]:
        return {item.alias: item.generation for item in self.registry.status().published}

    def state(self) -> tuple[Any, ...]:
        """Tudo que uma operacao sem efeito nao pode mudar."""
        return (
            self.disk(),
            self.store.revision,
            self.published(),
            tuple(
                (record.id, record.revision, record.last_test)
                for record in self.store.snapshot().datasources
            ),
            self.registry.status().candidates,
        )

    def close(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None
        self.runtime.close()
        self.v1.close()
        if self._logger is not None:
            self._logger.removeHandler(self.audit)


def build_v2(
    tmp_path: Path,
    *,
    limits: RegistryLimits | None = None,
    resolver: AddressResolver | None = dns,
) -> V2Harness:
    secrets = MappingSecretProvider(
        {
            "MASKGW_DATABASE_DSN": SENSITIVE_DSN,
            "MASKGW_HMAC_KEY": HMAC_KEY,
            "MASKGW_DATASOURCE_MASTER_KEY": KEY,
        }
    )
    v1 = build_service(tmp_path, secrets=MappingSecretProvider({"MASKGW_HMAC_KEY": SENSITIVE_HMAC}))
    store_path = tmp_path / "catalog" / "datasources.store"
    store_path.parent.mkdir()
    anchor_path = tmp_path / "catalog-anchor" / "datasources.anchor"
    CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY).close()
    crash = Crash()
    store = CatalogStore.open(
        store_path, anchor_path=anchor_path, master_key=KEY, hooks=CatalogHooks(after_point=crash)
    )
    factory = FakeFactory()
    registry = DatasourceRegistry(limits)
    service = DatasourceRuntimeService(
        store=store,
        registry=registry,
        secrets=secrets,
        resolver=resolver,
        adapter_factory=factory,
    )
    runtime = DatasourceRuntime(store=store, registry=registry, service=service)
    logger = logging.getLogger(f"maskgw.audit.test.{uuid.uuid4().hex}")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    capture = AuditCapture()
    logger.addHandler(capture)
    return V2Harness(
        tmp_path=tmp_path,
        v1=v1,
        store=store,
        registry=registry,
        service=service,
        runtime=runtime,
        factory=factory,
        crash=crash,
        audit=capture,
        audit_log=AuditLog(logger),
        secrets=secrets,
        _logger=logger,
    )


def scan(text: str, canaries: tuple[str, ...] = UPSTREAM_CANARIES) -> list[str]:
    """Canarios presentes no texto."""
    return [canary for canary in canaries if canary in text]
