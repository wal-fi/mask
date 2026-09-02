"""Apoio dos testes da fronteira HTTP administrativa (Fase 7, Etapa 7).

Nao e um arquivo de teste: o pytest so coleta `test_*.py`. Aqui vivem o cliente
HTTP cru e a montagem de um `AdminConfigService` real sobre um filesystem real.

## Por que um cliente por socket, e nao um TestClient

Metade do que esta etapa precisa provar nao passa por um cliente educado:

- um `Host` alheio (`evil.example:1`), que e o teste de DNS rebinding;
- um corpo `Transfer-Encoding: chunked` de varios MiB **sem** `Content-Length`;
- um `HEAD` cujo corpo precisa vir literalmente vazio no fio;
- um token em query string, que precisa ser ignorado.

Um cliente de alto nivel normaliza justamente essas coisas. `http.client`, com
`skip_host=True`, deixa cada header sob controle do teste.
"""

from __future__ import annotations

import http.client
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, cast

from maskgw.admin.http import AdminHttpServer, build_admin_app
from maskgw.admin.service import AdminConfigService
from maskgw.config.filesystem import ConfigFileStore
from maskgw.config.gateway import build_gateway_config
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import MappingSecretProvider

#: Token valido de teste. 40 caracteres, acima do minimo de 32.
TOKEN = "admin-token-para-teste-com-40-caracteres"

#: Marcadores que NUNCA podem aparecer numa resposta, header ou registro.
#:
#: As partes do DSN sao nomeadas separadamente de proposito. Um DSN realista
#: comeca por `postgresql://`, e "postgres" aparece legitimamente em texto de
#: politica — `statement_timeout_enforced_by: "postgresql"` em
#: `GET /admin/v1/protected`. Um teste que procurasse os 8 primeiros caracteres
#: do DSN acusaria esse texto e nao acusaria vazamento nenhum. Procurar pelas
#: PARTES secretas — usuario, senha, host e banco — e a verificacao que de fato
#: distingue as duas coisas.
DSN_USER = "maskgw_leak_user"
DSN_PASSWORD = "maskgw-leak-password-marker"
DSN_HOST = "leak-host.example.invalid"
DSN_DATABASE = "leak_database_marker"
SENSITIVE_DSN = f"postgresql://{DSN_USER}:{DSN_PASSWORD}@{DSN_HOST}:5432/{DSN_DATABASE}"
DSN_PARTS = (DSN_USER, DSN_PASSWORD, DSN_HOST, DSN_DATABASE)

SENSITIVE_HMAC = "hmac-key-marker-com-mais-de-32-caracteres"
SENSITIVE_SQL = "SELECT cpf FROM cliente WHERE cpf = '11122233344'"
SENSITIVE_VALUE = "11122233344"

RULE_ID = "rul_" + "a" * 32
SECOND_RULE_ID = "rul_" + "c" * 32
EXCEPTION_ID = "exc_" + "b" * 32

ADOPTED_DOCUMENT: dict[str, Any] = {
    "revision": 3,
    "masking": [
        {"id": RULE_ID, "match": "cpf", "transformer": "sha256"},
        {
            "id": SECOND_RULE_ID,
            "match": "email",
            "transformer": "regex",
            "config": {"pattern": "^(.).*@(.*)$", "replacement": r"\1***@\2"},
        },
    ],
    "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
    "database": {"statement_timeout_ms": 2000, "max_rows": 10},
    "sql": {"allowed_pg_functions": ["pg_typeof"], "denied_functions": ["dblink_exec"]},
}

#: Sem `revision` e sem `id`: o estado de compatibilidade da secao 5.2. Le-se
#: normalmente, `adopted` e falso e nenhum ID e inventado.
UNADOPTED_DOCUMENT: dict[str, Any] = {
    "masking": [{"match": "cpf", "transformer": "md5"}],
    "exceptions": [{"match": "tipo_cpf"}],
}


class FakeAdapter:
    """Adapter sem banco. A Admin API nao executa SQL (D-049), entao nenhuma
    rota desta etapa deveria toca-lo — e um contador prova isso."""

    instances: ClassVar[list[FakeAdapter]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.connect_calls = 0
        self.close_calls = 0
        self.execute_calls = 0
        type(self).instances.append(self)

    def connect(self) -> None:
        self.connect_calls += 1

    def close(self) -> None:
        self.close_calls += 1

    def execute_validated(self, _sql: str) -> object:  # pragma: no cover - nunca chamado
        self.execute_calls += 1
        msg = "a Admin API nao executa SQL"
        raise AssertionError(msg)


@dataclass
class Harness:
    """Servico administrativo real, servidor real, cliente cru."""

    service: AdminConfigService
    store: ConfigFileStore
    registry: RuntimeRegistry
    adapter: FakeAdapter
    config_path: Path
    server: AdminHttpServer | None = None
    _closables: list[Any] = field(default_factory=list)

    @property
    def port(self) -> int:
        assert self.server is not None
        return self.server.port

    def start(self, **kwargs: Any) -> AdminHttpServer:
        secrets = MappingSecretProvider(
            kwargs.pop(
                "secret_values",
                {"MASKGW_DATABASE_DSN": SENSITIVE_DSN, "MASKGW_HMAC_KEY": SENSITIVE_HMAC},
            )
        )
        token = kwargs.pop("token", TOKEN)

        def factory(bound_port: int) -> Any:
            return build_admin_app(
                self.service,
                token=token,
                port=bound_port,
                secrets=secrets,
                database_dsn_env="MASKGW_DATABASE_DSN",
            )

        self.server = AdminHttpServer(
            app_factory=factory,
            host=kwargs.pop("host", "127.0.0.1"),
            port=kwargs.pop("port", 0),
            **kwargs,
        )
        self.server.start()
        return self.server

    def close(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None
        self.registry.close_all()
        self.store.close()


@dataclass(frozen=True, slots=True)
class Reply:
    """Resposta crua: status, headers em minusculas e o corpo em bytes."""

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def cors_headers(self) -> list[str]:
        return sorted(name for name in self.headers if name.startswith("access-control-"))

    def json(self) -> Any:
        import json

        return json.loads(self.body)

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def request(
    port: int,
    method: str = "GET",
    path: str = "/admin/v1/status",
    *,
    token: str | None = TOKEN,
    host: str | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 10.0,
) -> Reply:
    """Uma requisicao com controle total dos headers.

    `token=None` omite o `Authorization` por completo — nao envia um vazio.
    `host=None` usa a forma canonica aceita pela allowlist.
    """
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", host if host is not None else f"127.0.0.1:{port}")
        if token is not None:
            connection.putheader("Authorization", f"Bearer {token}")
        if content_type is not None:
            connection.putheader("Content-Type", content_type)
        for name, value in (headers or {}).items():
            connection.putheader(name, value)
        if body is not None:
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(message_body=body)

        response = connection.getresponse()
        payload = response.read()
        return Reply(
            status=response.status,
            headers={name.lower(): value for name, value in response.getheaders()},
            body=payload,
        )
    finally:
        connection.close()


def chunked_request(
    port: int,
    *,
    total_bytes: int,
    chunk_size: int = 64 * 1024,
    token: str | None = TOKEN,
    path: str = "/admin/v1/status",
    timeout: float = 15.0,
) -> Reply:
    """Envia `total_bytes` em chunks, SEM `Content-Length`, e le a resposta.

    Escrito no socket cru porque o objetivo e justamente nao ter
    `Content-Length`: o servidor precisa cortar o envio contando os bytes que
    chegam. Se o servidor responder antes do fim — que e o comportamento
    esperado —, a escrita falha com `BrokenPipe`/`ConnectionReset`, e isso e
    tratado como sucesso do corte, nao como erro do teste.
    """
    connection = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        head = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Content-Type: application/json\r\n"
        )
        if token is not None:
            head += f"Authorization: Bearer {token}\r\n"
        connection.sendall((head + "\r\n").encode("ascii"))

        payload = b"x" * chunk_size
        sent = 0
        try:
            while sent < total_bytes:
                size = min(chunk_size, total_bytes - sent)
                frame = f"{size:x}\r\n".encode("ascii") + payload[:size] + b"\r\n"
                connection.sendall(frame)
                sent += size
            connection.sendall(b"0\r\n\r\n")
        except OSError:
            # O servidor cortou antes do fim: e o desfecho esperado.
            pass

        raw = b""
        try:
            while b"\r\n\r\n" not in raw:
                piece = connection.recv(65536)
                if not piece:
                    break
                raw += piece
            while True:
                piece = connection.recv(65536)
                if not piece:
                    break
                raw += piece
        except OSError:
            pass
    finally:
        connection.close()

    return _parse_raw_reply(raw)


def _parse_raw_reply(raw: bytes) -> Reply:
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1]) if lines and " " in lines[0] else 0
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name:
            headers[name.strip().lower()] = value.strip()
    return Reply(status=status, headers=headers, body=body)


def build_runtime(
    payload: dict[str, Any],
    *,
    secrets: MappingSecretProvider | None = None,
) -> Runtime:
    """Um `Runtime` completo a partir de um documento cru, sem banco.

    Serve aos testes que precisam de MAIS de um runtime — os de coerencia de
    snapshot, que provocam um swap de verdade entre revisions distintas.
    """
    provider = secrets if secrets is not None else MappingSecretProvider({})
    parsed = validate_file_config(payload)
    policy = compile_policy(parsed, secrets=provider)
    return Runtime(
        revision=parsed.revision,
        file_config=parsed,
        config=build_gateway_config(parsed, policy),
        engine=MaskingEngine(policy),
        # O runtime exige um `PostgresAdapter`; nenhuma rota de leitura o
        # toca, e um contador no duble prova isso.
        adapter=FakeAdapter(),  # type: ignore[arg-type]
    )


def build_service(
    tmp_path: Path,
    document: dict[str, Any] | None = None,
    *,
    secrets: MappingSecretProvider | None = None,
    registry_factory: Callable[[Runtime], RuntimeRegistry] = RuntimeRegistry,
) -> Harness:
    """Monta um `AdminConfigService` real sobre um `masking.yaml` real.

    `registry_factory` existe para que um teste possa injetar um registry que
    troque o runtime publicado em momentos escolhidos. Sem isso nao ha como
    provocar um swap deterministico no ponto exato em que uma resposta e
    montada.
    """
    import yaml

    payload = document if document is not None else ADOPTED_DOCUMENT
    config_path = tmp_path / "masking.yaml"
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    provider = secrets if secrets is not None else MappingSecretProvider({})

    FakeAdapter.instances = []
    initial = build_runtime(payload, secrets=provider)
    adapter = cast(FakeAdapter, initial.adapter)
    registry = registry_factory(initial)

    store = ConfigFileStore.open(config_path)
    service = AdminConfigService(
        store=store,
        registry=registry,
        adapter_factory=_unused_factory,
        reference_digest=store.read_snapshot().digest,
        secrets=provider,
    )
    return Harness(
        service=service,
        store=store,
        registry=registry,
        adapter=adapter,
        config_path=config_path,
    )


def _unused_factory(*, config: object, engine: object) -> PostgresAdapter:  # pragma: no cover
    msg = "nenhuma rota de leitura constroi adapter"
    raise AssertionError(msg)


def free_port() -> int:
    """Uma porta livre no momento da consulta, para o teste de porta ocupada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def thread_snapshot() -> set[tuple[int | None, str]]:
    return {(thread.ident, thread.name) for thread in threading.enumerate()}
