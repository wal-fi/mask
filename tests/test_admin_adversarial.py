"""Fase 7, Etapa 11: suite adversarial administrativa geral (secoes 12.6-12.8).

Esta suite NAO reimplementa a cobertura que ja existe — a fronteira
(`test_admin_http_boundary.py`), a superficie (`test_admin_http_surface.py`), o
leakage de leitura (`test_admin_http_leakage.py`), a separacao de planos
(`test_plan_separation.py`, `test_purity.py`), a escrita e a adocao
(`test_admin_http_writes.py`, `_adversarial.py`, `_e2e.py`) e a auditoria
(`test_admin_audit*.py`, `test_admin_http_audit.py`). A matriz de rastreabilidade
em `docs/TEST-PLAN.md` liga cada requisito de §12.6-§12.8 a essa cobertura.

O que este arquivo fecha sao as LACUNAS reais que a matriz revelou, todas sobre
o caminho de ESCRITA real contra PostgreSQL e a auditoria — territorio que os
testes de leitura com adapter falso nao alcancam:

- **leakage nos grupos de erro de escrita**, inclusive falhas injetadas ANTES e
  DEPOIS de `os.replace`, e no proprio `AdminAudit` emitido (§12.6);
- **`__cause__`/`__context__` nulos** no `AdminError` de uma falha real (§10.1);
- **leakage no caminho de adocao** — bytes originais, backup, caminho do arquivo;
- **imutabilidade adversarial**: `allowed_pg_functions` por alias, capitalizacao,
  aninhamento e mistura com campos validos — recusado, e sem efeito (§11.3, §12.7);
- **MCP nao tem caminho para configuracao administrativa** (D-049);
- **corpo hostil a uma rota de escrita real** nao persiste, nao troca runtime e
  nao emite auditoria (§12.7 limites + §12.6 sem efeito);
- **concorrencia adversarial**: um vencedor, estado coerente, uma auditoria por
  tentativa com `request_id` distinto, e nenhum secret sob concorrencia (§12.1).

Cada cenario e classificado no docstring como BLOCKED (a protecao existe e o
teste a afirma), MASKED ou KNOWN LIMITATION (D-041): um limite conhecido vira
teste que afirma o comportamento real, nunca `skip`/`xfail`.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import socket
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from maskgw.admin.errors import AdminError
from maskgw.admin.http import build_admin_app
from maskgw.admin.http.server import AdminHttpServer
from maskgw.admin.service import AdminConfigService, AdminOperation
from maskgw.audit import ADMIN_MESSAGE, AuditLog
from maskgw.bootstrap.application import make_adapter_factory
from maskgw.config.filesystem import ConfigFileStore, DigestCheckPoint, FilesystemHooks
from maskgw.config.gateway import build_gateway_config
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.gateway.service import Gateway
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import Reply, request

pytestmark = pytest.mark.integration

TOKEN = "admin-token-para-teste-com-40-caracteres"  # noqa: S105 - token de teste
JSON = "application/json"
HMAC_KEY = "hmac-key-marker-com-mais-de-32-caracteres"

RULE_ID = "rul_" + "a" * 32
SECOND_RULE_ID = "rul_" + "c" * 32
EXCEPTION_ID = "exc_" + "b" * 32

#: Documento adotado (revision 3), com marcadores sensiveis no conteudo que NAO
#: podem vazar para a resposta nem para a auditoria: um `match` (que e nome de
#: coluna) e uma config de transformer.
SENSITIVE_MATCH = "numero_cpf_sensivel_marcador"
SENSITIVE_PATTERN = "PADRAO_SECRETO_MARCADOR"
SENSITIVE_REPLACEMENT = "REPL_SECRETO_MARCADOR"

ADOPTED: dict[str, Any] = {
    "revision": 3,
    "masking": [
        {"id": RULE_ID, "match": "cpf", "transformer": "sha256"},
        {"id": SECOND_RULE_ID, "match": "email", "transformer": "md5"},
    ],
    "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
    "database": {"statement_timeout_ms": 2000, "max_rows": 10},
    "sql": {"allowed_pg_functions": ["pg_typeof"], "denied_functions": ["dblink_exec"]},
}

UNADOPTED_TEXT = """\
# comentario_secreto_que_so_vive_no_backup
masking:
  - match: cpf
    transformer: md5
exceptions:
  - match: tipo_cpf
"""


class RecordingHandler(logging.Handler):
    """Captura os `LogRecord` administrativos, num logger proprio por teste."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            self.records.append(record)

    def admin_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(record.maskgw)
                for record in self.records
                if record.getMessage() == ADMIN_MESSAGE and hasattr(record, "maskgw")
            ]

    def rendered(self) -> str:
        """Tudo que os records carregam, como texto — para varredura de leakage."""
        with self._lock:
            parts: list[str] = []
            for record in self.records:
                parts.append(record.getMessage())
                if hasattr(record, "maskgw"):
                    parts.append(json.dumps(record.maskgw))
            return " ".join(parts)


class CountingAdapterFactory:
    """Envolve `make_adapter_factory` e conta as TENTATIVAS de construir um
    adapter candidato — uma por candidato de runtime que o servico monta.

    E o instrumento do `TestCorpoHostilSemEfeito`: um corpo que a fronteira
    recusa nunca alcanca `AdminConfigService.apply`, entao a fabrica jamais e
    chamada, e o contador prova a ausencia de candidato (secao 6, correcao).
    """

    def __init__(self, dsn: str) -> None:
        self._factory = make_adapter_factory(dsn)
        self.calls = 0

    def __call__(self, *, config: Any, engine: Any) -> Any:
        self.calls += 1
        return self._factory(config=config, engine=engine)


@dataclass
class Harness:
    service: AdminConfigService
    store: ConfigFileStore
    registry: RuntimeRegistry
    config_path: Path
    server: AdminHttpServer
    handler: RecordingHandler
    logger: logging.Logger
    dsn: str
    adapter_factory: CountingAdapterFactory
    _closables: list[Any] = field(default_factory=list)

    @property
    def port(self) -> int:
        return self.server.port

    @property
    def candidate_builds(self) -> int:
        """Quantas vezes a `adapter_factory` foi chamada (passo 6 do apply)."""
        return self.adapter_factory.calls

    def events(self) -> list[dict[str, Any]]:
        return self.handler.admin_events()

    def audit_text(self) -> str:
        return self.handler.rendered()

    def close(self) -> None:
        self.server.stop()
        self.registry.close_all()
        self.store.close()
        self.logger.removeHandler(self.handler)


def _initial_runtime(payload_text: str, dsn: str) -> Runtime:
    document = validate_file_config(yaml.safe_load(payload_text))
    secrets = MappingSecretProvider({"MASKGW_HMAC_KEY": HMAC_KEY})
    policy = compile_policy(document, secrets=secrets)
    config = build_gateway_config(document, policy)
    engine = MaskingEngine(policy)
    adapter = make_adapter_factory(dsn)(config=config, engine=engine)
    adapter.connect()
    return Runtime(
        revision=document.revision,
        file_config=document,
        config=config,
        engine=engine,
        adapter=adapter,
    )


def make_harness(
    tmp_path: Path,
    dsn: str,
    *,
    payload_text: str,
    hooks: FilesystemHooks | None = None,
) -> Harness:
    config_path = tmp_path / "masking.yaml"
    config_path.write_text(payload_text, encoding="utf-8")

    secrets = MappingSecretProvider({"MASKGW_HMAC_KEY": HMAC_KEY, "MASKGW_DATABASE_DSN": dsn})
    registry = RuntimeRegistry(_initial_runtime(payload_text, dsn))
    store = ConfigFileStore.open(config_path, hooks=hooks)
    adapter_factory = CountingAdapterFactory(dsn)
    service = AdminConfigService(
        store=store,
        registry=registry,
        adapter_factory=adapter_factory,
        reference_digest=store.read_snapshot().digest,
        secrets=secrets,
    )

    logger = logging.getLogger(f"test.adversarial.{uuid.uuid4().hex}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RecordingHandler()
    logger.addHandler(handler)
    audit = AuditLog(logger)

    def factory(bound_port: int) -> Any:
        return build_admin_app(
            service,
            token=TOKEN,
            port=bound_port,
            secrets=secrets,
            database_dsn_env="MASKGW_DATABASE_DSN",
            audit=audit,
        )

    server = AdminHttpServer(app_factory=factory, host="127.0.0.1", port=0)
    server.start()
    return Harness(
        service=service,
        store=store,
        registry=registry,
        config_path=config_path,
        server=server,
        handler=handler,
        logger=logger,
        dsn=dsn,
        adapter_factory=adapter_factory,
    )


@pytest.fixture
def adopted(tmp_path: Path, dsn: str) -> Iterator[Harness]:
    payload = yaml.safe_dump(ADOPTED, sort_keys=False)
    state = make_harness(tmp_path, dsn, payload_text=payload)
    try:
        yield state
    finally:
        state.close()


@pytest.fixture
def unadopted(tmp_path: Path, dsn: str) -> Iterator[Harness]:
    state = make_harness(tmp_path, dsn, payload_text=UNADOPTED_TEXT)
    try:
        yield state
    finally:
        state.close()


def call(port: int, method: str, path: str, body: Any, **kwargs: Any) -> Reply:
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return request(port, method, path, content_type=JSON, body=payload, **kwargs)


def secret_markers(dsn: str) -> list[str]:
    """Tudo que jamais pode aparecer numa resposta, header ou registro."""
    markers = [
        TOKEN,
        HMAC_KEY,
        SENSITIVE_MATCH,
        SENSITIVE_PATTERN,
        SENSITIVE_REPLACEMENT,
        "SELECT",
        "Traceback",
        "psycopg",
        "masking.yaml",
        "AdminConfigService",
        "RuntimeRegistry",
    ]
    for part in dsn.split():
        key, _, value = part.partition("=")
        if key in {"password", "user", "host", "dbname"} and value:
            markers.append(value)
    return markers


def assert_no_leak(blob: str, dsn: str, *, allow: tuple[str, ...] = ()) -> None:
    for marker in secret_markers(dsn):
        if marker in allow:
            continue
        assert marker not in blob, marker


# ==========================================================================
# 1. Leakage nos grupos de erro de escrita, inclusive falhas injetadas
# ==========================================================================


class TestLeakageNasFalhasDeEscrita:
    """BLOCKED. Nenhuma falha de escrita — recusa controlada ou erro injetado
    antes/depois de `os.replace` — vaza secret, SQL, mensagem interna, caminho ou
    traceback, nem na resposta nem no `AdminAudit` emitido (§12.6, §10.1)."""

    def _blob(self, reply: Reply, harness: Harness) -> str:
        return reply.text() + " " + repr(reply.headers) + " " + harness.audit_text()

    def test_revision_conflict_nao_vaza(self, adopted: Harness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 99, "rule": {"match": SENSITIVE_MATCH, "transformer": "md5"}},
        )
        assert reply.status == 409
        assert_no_leak(self._blob(reply, adopted), adopted.dsn)

    def test_reload_error_nao_vaza(self, adopted: Harness) -> None:
        # Regex invalido com o marcador dentro: passa o schema, falha a compilacao
        # (passo 6). O texto do padrao — e o erro do compilador de regex — nunca
        # podem voltar na resposta nem na auditoria.
        bad_pattern = "(" + SENSITIVE_PATTERN  # parentese sem fechar: nao compila
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {
                "expected_revision": 3,
                "rule": {
                    "match": SENSITIVE_MATCH,
                    "transformer": "regex",
                    "config": {"pattern": bad_pattern, "replacement": SENSITIVE_REPLACEMENT},
                },
            },
        )
        # Compilacao durante escrita (passo 6): o contrato fixa EXATAMENTE
        # `CONFIG_RELOAD_ERROR` — regex invalido passa o schema (validate_file_config
        # aceita qualquer string) e falha em compile_policy. Nao e `CONFIG_INVALID`,
        # que e falha de SCHEMA (passo 5).
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_RELOAD_ERROR"
        blob = self._blob(reply, adopted)
        assert_no_leak(blob, adopted.dsn)
        # Nem o texto do padrao invalido nem a mensagem do compilador de regex.
        assert "unbalanced" not in blob
        assert "missing )" not in blob

    def test_write_error_injetado_antes_do_replace_nao_vaza(self, tmp_path: Path, dsn: str) -> None:
        def boom_replace(_src: str, _dst: str) -> None:
            # Uma mensagem cheia de coisa que nao pode vazar.
            msg = f"replace falhou {HMAC_KEY} {SENSITIVE_PATTERN} SELECT cpf"
            raise OSError(msg)

        harness = make_harness(
            tmp_path,
            dsn,
            payload_text=yaml.safe_dump(ADOPTED, sort_keys=False),
            hooks=FilesystemHooks(replace=boom_replace),
        )
        try:
            reply = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 500
            assert reply.json()["error"] == "CONFIG_WRITE_ERROR"
            assert_no_leak(self._blob(reply, harness), dsn)
            # A mensagem injetada tampouco vaza.
            blob = self._blob(reply, harness)
            assert "replace falhou" not in blob
        finally:
            harness.close()

    def test_out_of_sync_injetado_antes_do_replace_nao_vaza(self, tmp_path: Path, dsn: str) -> None:
        # Um editor externo escreve entre a validacao e o replace: CONFIG_OUT_OF_SYNC.
        config_path = tmp_path / "masking.yaml"

        def edit_before_replace(point: DigestCheckPoint) -> None:
            if point is DigestCheckPoint.PRE_REPLACE:
                config_path.write_text("masking: []\n", encoding="utf-8")

        harness = make_harness(
            tmp_path,
            dsn,
            payload_text=yaml.safe_dump(ADOPTED, sort_keys=False),
            hooks=FilesystemHooks(before_digest_check=edit_before_replace),
        )
        try:
            reply = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 409
            assert reply.json()["error"] == "CONFIG_OUT_OF_SYNC"
            assert_no_leak(self._blob(reply, harness), dsn)
        finally:
            harness.close()

    def test_durability_error_depois_do_replace_nao_vaza(  # noqa: PLR0915 - contraprova de durabilidade: muitas assercoes deliberadas
        self, tmp_path: Path, dsn: str
    ) -> None:
        """POSIX. Falha DEPOIS de `os.replace`: `fsync` de diretorio levanta uma
        excecao cheia de secret. A mudanca FOI publicada (§7.6), e nada vaza.

        No Windows o `fsync` de diretorio e deliberadamente omitido — a
        durabilidade nunca falha por essa via —, entao este e um **skip de
        plataforma legitimo**, nao um finding ignorado. A omissao ja e afirmada
        por `test_admin_http_writes.py::test_no_windows_o_fsync_de_diretorio_e_omitido`.
        """
        if os.name != "posix":
            pytest.skip("fsync de diretorio so no POSIX; no Windows e omitido (§7.6)")

        config_path = tmp_path / "masking.yaml"
        # A mensagem injetada carrega TUDO que nao pode vazar: token, HMAC, o DSN
        # COMPLETO, SQL, os marcadores sensiveis e o CAMINHO COMPLETO do arquivo.
        sql_marker = "SELECT cpf FROM cliente"  # marcador de SQL, nao uma consulta
        injected = (
            f"fsync falhou token={TOKEN} hmac={HMAC_KEY} dsn={dsn} {sql_marker} "
            f"{SENSITIVE_PATTERN} {SENSITIVE_REPLACEMENT} {SENSITIVE_MATCH} path={config_path}"
        )

        def boom_dir_fsync(_descriptor: int) -> None:
            raise OSError(injected)

        harness = make_harness(
            tmp_path,
            dsn,
            payload_text=yaml.safe_dump(ADOPTED, sort_keys=False),
            hooks=FilesystemHooks(directory_fsync=boom_dir_fsync),
        )
        try:
            # Estado ANTES da escrita: o runtime publicado e os bytes do arquivo.
            runtime_antes = harness.registry.current
            bytes_antes = config_path.read_bytes()

            reply = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            # HTTP 500, categoria exata, applied: true, revision publicada 3 -> 4.
            assert reply.status == 500
            body = reply.json()
            assert body["error"] == "CONFIG_DURABILITY_ERROR"
            assert body["applied"] is True
            assert body["current_revision"] == 4
            assert harness.service.revision == 4

            # A mudanca FOI publicada: o runtime publicado NAO e mais o anterior.
            runtime_depois = harness.registry.current
            assert runtime_depois is not runtime_antes
            assert runtime_depois.revision == 4

            # Os bytes do arquivo mudaram e correspondem a revision 4.
            bytes_depois = config_path.read_bytes()
            assert bytes_depois != bytes_antes
            assert b"revision: 4" in bytes_depois

            # Digest, arquivo, runtime e resposta coerentes entre si: o digest de
            # referencia corresponde ao arquivo, e o GET reflete a revision nova.
            snapshot = harness.store.read_snapshot()
            assert harness.service.reference_digest == snapshot.digest
            config = request(harness.port, "GET", "/admin/v1/config").json()["config"]
            assert config["revision"] == 4
            assert config["database"]["max_rows"] == 9

            # AdminAudit coerente: error, before 3, after 4, categoria exata.
            events = harness.events()
            assert len(events) == 1
            event = events[0]
            assert event["outcome"] == "error"
            assert event["revision_before"] == 3
            assert event["revision_after"] == 4
            assert event["error_category"] == "CONFIG_DURABILITY_ERROR"

            # Nenhum marcador na resposta, headers ou auditoria. A mensagem
            # injetada — com DSN completo e caminho — tambem nao vaza.
            blob = self._blob(reply, harness)
            assert_no_leak(blob, dsn)
            assert "fsync falhou" not in blob
            assert str(config_path) not in blob
            assert str(config_path.parent) not in blob

            # Retentativa cega com a revision velha: 409 REVISION_CONFLICT, sem
            # mudar o estado ja publicado.
            retry = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 6000, "max_rows": 8},
            )
            assert retry.status == 409
            assert retry.json()["error"] == "REVISION_CONFLICT"
            assert harness.service.revision == 4
            assert harness.registry.current is runtime_depois
            assert harness.service.reference_digest == harness.store.read_snapshot().digest

            # Varredura COMPLETA novamente, agora sobre a segunda resposta e sobre
            # TODOS os eventos de auditoria acumulados: nem a recusa da retentativa
            # nem o segundo evento vazam nada.
            retry_blob = retry.text() + " " + repr(retry.headers) + " " + harness.audit_text()
            assert_no_leak(retry_blob, dsn)
            assert "fsync falhou" not in retry_blob
            assert str(config_path) not in retry_blob
            assert str(config_path.parent) not in retry_blob
            assert len(harness.events()) == 2  # o durabilidade e o revision_conflict
        finally:
            harness.close()

    def test_error_category_de_falha_e_fechada_nunca_str_exc(self, adopted: Harness) -> None:
        # O AdminError que sobe de uma falha real carrega so a categoria fechada;
        # nem __cause__ nem __context__ apontam para a excecao interna (§10.1).
        def boom(_current: object) -> dict[str, Any]:
            msg = f"interno {HMAC_KEY} SELECT cpf FROM cliente"  # noqa: S608 - texto de teste, nao SQL
            raise RuntimeError(msg)

        with pytest.raises(AdminError) as excinfo:
            adopted.service.apply(boom, expected_revision=3, operation=AdminOperation.WRITE)
        err = excinfo.value
        assert err.__cause__ is None
        assert err.__context__ is None
        assert HMAC_KEY not in str(err)
        assert "SELECT" not in str(err)


# ==========================================================================
# 2. Leakage no caminho de adocao
# ==========================================================================


class TestLeakageNaAdocao:
    """BLOCKED. A adocao le os bytes originais (com comentario secreto) e grava um
    backup; nem os bytes originais, nem o caminho do backup, nem o do arquivo
    aparecem na resposta ou na auditoria (§5.4, §12.6)."""

    def test_adocao_sucesso_nao_vaza_bytes_originais(self, unadopted: Harness) -> None:
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        assert reply.status == 200
        blob = reply.text() + " " + repr(reply.headers) + " " + unadopted.audit_text()
        assert "comentario_secreto_que_so_vive_no_backup" not in blob
        assert str(unadopted.config_path) not in blob
        assert str(unadopted.config_path.parent) not in blob
        assert_no_leak(blob, unadopted.dsn)

    def test_segunda_adocao_recusada_nao_vaza(self, unadopted: Harness) -> None:
        call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 1, "confirm_comment_loss": True},
        )
        assert reply.status == 409
        assert reply.json()["error"] == "CONFIG_ALREADY_ADOPTED"
        # Varredura completa: corpo, headers, auditoria, e os caminhos do arquivo
        # e do diretorio — nenhum vaza na recusa da segunda adocao.
        blob = reply.text() + " " + repr(reply.headers) + " " + unadopted.audit_text()
        assert "comentario_secreto_que_so_vive_no_backup" not in blob
        assert str(unadopted.config_path) not in blob
        assert str(unadopted.config_path.parent) not in blob
        assert_no_leak(blob, unadopted.dsn)


# ==========================================================================
# 3. Imutabilidade adversarial de `allowed_pg_functions`
# ==========================================================================


class TestImutabilidadeAdversarial:
    """BLOCKED. Nenhuma forma de contrabandear `allowed_pg_functions` numa escrita
    passa: presenca direta (qualquer valor), alias por capitalizacao, aninhamento
    ou mistura com campos validos. Recusado com `IMMUTABLE_FIELD` (chave exata) ou
    `SCHEMA_INVALID` (alias/aninhamento, pelo `extra=forbid`), e sem efeito
    (§11.3, §12.7)."""

    def _state(self, h: Harness) -> tuple[bytes, Any, int, str]:
        return (
            h.config_path.read_bytes(),
            h.registry.current,
            h.service.revision,
            h.service.reference_digest,
        )

    def _assert_unchanged(self, h: Harness, before: tuple[bytes, Any, int, str]) -> None:
        assert h.config_path.read_bytes() == before[0]
        assert h.registry.current is before[1]
        assert h.service.revision == before[2]
        assert h.service.reference_digest == before[3]

    @pytest.mark.parametrize(
        "value",
        [None, [], ["pg_read_file"], "pg_read_file", {"x": 1}, True, 3],
    )
    def test_put_sql_allowed_qualquer_valor_e_immutable_sem_efeito(
        self, adopted: Harness, value: Any
    ) -> None:
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": value},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"
        self._assert_unchanged(adopted, before)

    @pytest.mark.parametrize(
        "alias",
        [
            "Allowed_Pg_Functions",
            "ALLOWED_PG_FUNCTIONS",
            "allowedPgFunctions",
            "allowed-pg-functions",
        ],
    )
    def test_put_sql_alias_por_capitalizacao_e_schema_invalid(
        self, adopted: Harness, alias: str
    ) -> None:
        # Um alias nao casa a chave exata: cai no `extra=forbid` do schema, nunca
        # abre o campo real. `SCHEMA_INVALID`, sem efeito.
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": [], alias: ["pg_read_file"]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        self._assert_unchanged(adopted, before)

    def test_put_config_allowed_aninhado_no_sql_e_immutable(self, adopted: Harness) -> None:
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": [], "allowed_pg_functions": ["pg_read_file"]},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"
        self._assert_unchanged(adopted, before)

    def test_put_config_allowed_misturado_com_campos_validos_e_immutable(
        self, adopted: Harness
    ) -> None:
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "ssn", "transformer": "sha256"}],
                "exceptions": [{"match": "tipo_ssn"}],
                "database": {"statement_timeout_ms": 4000, "max_rows": 5},
                "sql": {"denied_functions": ["pg_sleep"], "allowed_pg_functions": []},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"
        self._assert_unchanged(adopted, before)

    def test_put_config_omitir_preserva_allowed_em_conteudo_e_ordem(self, adopted: Harness) -> None:
        # A omissao preserva o valor semantico (§11.3): modelo validado contra
        # modelo validado, nunca fatia de texto.
        antes = adopted.service.document.sql.allowed_pg_functions
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": []},
            },
        )
        assert reply.status == 200
        depois = adopted.service.document.sql.allowed_pg_functions
        assert list(depois) == list(antes)


# ==========================================================================
# 4. MCP nao tem caminho para configuracao administrativa
# ==========================================================================


class TestMcpNaoAlcancaConfig:
    """BLOCKED. O plano MCP nao le nem altera configuracao administrativa: o
    Gateway nao tem superficie para isso, e a unica tool e `query_database(sql)`
    (D-049; a superficie da tool ja e afirmada em `test_mcp_server.py`)."""

    def test_gateway_nao_expoe_mutacao_de_config(self) -> None:
        publicos = {name for name in dir(Gateway) if not name.startswith("_")}
        # Nenhum metodo administrativo: adotar, escrever, aplicar, mutar, reload.
        for proibido in ("apply", "adopt", "write", "mutate", "reload", "snapshot", "config_store"):
            assert proibido not in publicos, proibido
        # A superficie publica e query + lifecycle, e nada de admin.
        assert publicos <= {"query", "revision", "close"}

    def test_gateway_nao_conhece_o_servico_administrativo(self) -> None:
        # Estrutural: nenhum modulo de gateway/ importa maskgw.admin. Reforca
        # test_plan_separation por um angulo proprio da Etapa 11.
        gateway_dir = Path(__file__).resolve().parents[1] / "src" / "maskgw" / "gateway"
        for path in gateway_dir.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("maskgw.admin"), path


# ==========================================================================
# 5. Corpo hostil a uma rota de escrita real: sem efeito, sem auditoria
# ==========================================================================


class TestCorpoHostilSemEfeito:
    """BLOCKED. Um corpo que a fronteira recusa (grande demais, tipo errado, sem
    token, malformado) numa rota de ESCRITA real nunca persiste arquivo, constroi
    candidato, troca runtime nem emite `AdminAudit` — o handler nem roda
    (§12.7 limites; §12.6 sem efeito)."""

    def _state(self, h: Harness) -> tuple[bytes, Any, int, str, int, int]:
        return (
            h.config_path.read_bytes(),
            h.registry.current,
            h.service.revision,
            h.service.reference_digest,
            h.service.operations_total,
            h.candidate_builds,
        )

    def _assert_untouched(self, h: Harness, before: tuple[bytes, Any, int, str, int, int]) -> None:
        assert h.config_path.read_bytes() == before[0]
        assert h.registry.current is before[1]
        assert h.service.revision == before[2]
        assert h.service.reference_digest == before[3]
        # Nem contador de operacoes nem auditoria: o handler nao entrou.
        assert h.service.operations_total == before[4]
        # E NENHUM candidato de runtime foi construido: a `adapter_factory` nao
        # foi chamada (a recusa vem da fronteira, antes de `apply`).
        assert h.candidate_builds == before[5]
        assert h.events() == []

    def test_corpo_grande_demais_nao_toca_estado_nem_audita(self, adopted: Harness) -> None:
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            b"x" * (1024 * 1024 + 1),
        )
        assert reply.status == 413
        self._assert_untouched(adopted, before)

    def test_content_type_errado_nao_toca_estado_nem_audita(self, adopted: Harness) -> None:
        before = self._state(adopted)
        reply = request(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            content_type="text/plain",
            body=b"nao-e-json",
        )
        assert reply.status == 415
        self._assert_untouched(adopted, before)

    def test_sem_token_nao_toca_estado_nem_audita(self, adopted: Harness) -> None:
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            token=None,
        )
        assert reply.status == 401
        self._assert_untouched(adopted, before)

    def test_json_malformado_nao_toca_estado_nem_audita(self, adopted: Harness) -> None:
        before = self._state(adopted)
        reply = request(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            content_type=JSON,
            body=b'{"expected_revision": 3, ',
        )
        assert reply.status == 422
        self._assert_untouched(adopted, before)

    def test_schema_invalido_com_campos_extras_nao_toca_estado_nem_audita(
        self, adopted: Harness
    ) -> None:
        # Campos extras (o `extra=forbid`) num corpo por outro lado plausivel.
        before = self._state(adopted)
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {
                "expected_revision": 3,
                "statement_timeout_ms": 5000,
                "max_rows": 9,
                "campo_desconhecido": 1,
                "outro_extra": "x",
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        self._assert_untouched(adopted, before)

    def test_json_profundamente_aninhado_nao_toca_estado_nem_audita(self, adopted: Harness) -> None:
        # JSON valido, mas profundamente aninhado num campo que espera escalar:
        # o schema recusa (tipo errado / extra), sem tocar estado nem auditar.
        before = self._state(adopted)
        nested: Any = 0
        for _ in range(500):
            nested = {"n": nested}
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 3, "statement_timeout_ms": nested, "max_rows": 9},
        )
        assert reply.status == 422
        self._assert_untouched(adopted, before)

    def test_content_length_declarado_acima_do_limite_e_413_sem_efeito(
        self, adopted: Harness
    ) -> None:
        """`Content-Length` que declara > 1 MiB e cortado em `413` pela fronteira,
        ANTES de ler o corpo (§12.7), numa rota de escrita real — sem efeito.

        **Limite da prova:** isto verifica o corte pelo `Content-Length`
        DECLARADO. Nao se afirma nada sobre comprimento *incompativel* com o
        corpo real (declarar N e enviar outra quantidade): isso e territorio de
        request smuggling / proxy / TLS, que uma aplicacao local em loopback nao
        pode provar, e esta suite nao alega cobrir.
        """
        before = self._state(adopted)
        reply = self._raw_write(
            adopted.port,
            content_length=1024 * 1024 + 1,
            body=b"{}",  # corpo pequeno; o header declarado e que decide
        )
        assert reply.status == 413
        self._assert_untouched(adopted, before)

    @staticmethod
    def _raw_write(port: int, *, content_length: int, body: bytes) -> Reply:
        """`PUT` cru com um `Content-Length` DECLARADO arbitrario (o helper padrao
        sempre o deriva do corpo, entao aqui vai no socket)."""
        conn = socket.create_connection(("127.0.0.1", port), timeout=10)
        try:
            head = (
                f"PUT /admin/v1/database HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Authorization: Bearer {TOKEN}\r\n"
                f"Content-Type: {JSON}\r\n"
                f"Content-Length: {content_length}\r\n"
                f"\r\n"
            ).encode("ascii")
            conn.sendall(head + body)
            raw = b""
            try:
                while b"\r\n\r\n" not in raw:
                    piece = conn.recv(65536)
                    if not piece:
                        break
                    raw += piece
            except OSError:
                pass
        finally:
            conn.close()
        head_bytes, _, rest = raw.partition(b"\r\n\r\n")
        lines = head_bytes.decode("latin-1").split("\r\n")
        status = int(lines[0].split(" ")[1]) if lines and " " in lines[0] else 0
        return Reply(status=status, headers={}, body=rest)


# ==========================================================================
# 6. Estado completo sob ataque: IDs e decisoes de masking preservados
# ==========================================================================


def _masking_verdicts(engine: MaskingEngine) -> list[str]:
    """Veredito do engine sobre uma tabela de colunas cobrindo regra, exception,
    alias e coluna sem correspondencia — a assinatura da politica compilada."""
    cases = [
        ColumnDescriptor(
            output_name="cpf", origin_name="cpf", provenance_kind=ProvenanceKind.DIRECT
        ),
        ColumnDescriptor(
            output_name="email", origin_name="email", provenance_kind=ProvenanceKind.DIRECT
        ),
        ColumnDescriptor(
            output_name="tipo_cpf", origin_name="tipo_cpf", provenance_kind=ProvenanceKind.DIRECT
        ),
        ColumnDescriptor(
            output_name="documento", origin_name="cpf", provenance_kind=ProvenanceKind.DIRECT
        ),
        ColumnDescriptor(
            output_name="saldo", origin_name="saldo", provenance_kind=ProvenanceKind.DIRECT
        ),
    ]
    return [engine.decide(case).action.name for case in cases]


def _rule_ids(document: Any) -> list[str | None]:
    return [rule.id for rule in document.masking]


def _exception_ids(document: Any) -> list[str | None]:
    return [exc.id for exc in document.exceptions]


class TestEstadoCompletoSobAtaque:
    """BLOCKED. Uma recusa nao altera NENHUMA faceta do estado publicado: bytes,
    digest, revision, o objeto runtime publicado, os IDs de regras/exceptions, nem
    as decisoes de masking. Completa `TestSemEfeitoNasRecusas` (que ja prova bytes/
    digest/revision/runtime) com os dois itens que faltavam — IDs e masking (§12.7)."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            (
                "PUT",
                "/admin/v1/sql",
                {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": ["x"]},
            ),
            ("DELETE", "/admin/v1/rules/" + "rul_" + "f" * 32, {"expected_revision": 3}),
            (
                "POST",
                "/admin/v1/rules",
                {"expected_revision": 99, "rule": {"match": "x", "transformer": "md5"}},
            ),
            ("PUT", "/admin/v1/database", {"lixo": 1}),
        ],
    )
    def test_recusa_preserva_ids_e_decisoes_de_masking(
        self, adopted: Harness, method: str, path: str, body: dict[str, Any]
    ) -> None:
        current = adopted.registry.current
        before_bytes = adopted.config_path.read_bytes()
        before_digest = adopted.service.reference_digest
        before_revision = adopted.service.revision
        before_rule_ids = _rule_ids(current.file_config)
        before_exc_ids = _exception_ids(current.file_config)
        before_verdicts = _masking_verdicts(current.engine)

        reply = call(adopted.port, method, path, body)
        assert reply.status in (404, 409, 422)

        after = adopted.registry.current
        assert after is current  # o MESMO objeto runtime publicado
        assert adopted.config_path.read_bytes() == before_bytes
        assert adopted.service.reference_digest == before_digest
        assert adopted.service.revision == before_revision
        assert _rule_ids(after.file_config) == before_rule_ids
        assert _exception_ids(after.file_config) == before_exc_ids
        assert _masking_verdicts(after.engine) == before_verdicts

    def test_a_tabela_de_masking_nao_e_vacua(self, adopted: Harness) -> None:
        # cpf e email mascaram, tipo_cpf e exception, saldo passa — senao a
        # preservacao acima nao provaria nada.
        verdicts = _masking_verdicts(adopted.registry.current.engine)
        assert verdicts[0] == "MASK"  # cpf
        assert verdicts[2] == "EXCEPTION"  # tipo_cpf
        assert verdicts[4] == "ALLOW"  # saldo


# ==========================================================================
# 7. Concorrencia adversarial: estado + auditoria + sem secret
# ==========================================================================


class TestConcorrenciaAdversarial:
    """BLOCKED. Sob N escritas concorrentes com o mesmo `expected_revision`, um so
    vence; o estado fica coerente (revision +1, bytes/digest correspondentes); ha
    exatamente uma auditoria por tentativa, com `request_id` distintos e revisoes
    coerentes; e nenhum secret aparece em resposta ou auditoria (§12.1, §12.6)."""

    def test_n_escritas_concorrentes_um_vencedor_estado_e_audit_coerentes(
        self, adopted: Harness
    ) -> None:
        results: list[Reply] = []
        lock = threading.Lock()
        n = 8

        def worker() -> None:
            reply = call(
                adopted.port,
                "POST",
                "/admin/v1/rules",
                {
                    "expected_revision": 3,
                    "rule": {"match": SENSITIVE_MATCH, "transformer": "md5"},
                },
            )
            with lock:
                results.append(reply)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        statuses = sorted(r.status for r in results)
        assert statuses == [200] + [409] * (n - 1)

        # Estado coerente: exatamente uma publicacao, revision 4.
        assert adopted.service.revision == 4
        assert adopted.service.reference_digest == adopted.store.read_snapshot().digest

        # Uma auditoria por tentativa, request_ids distintos.
        events = adopted.events()
        assert len(events) == n
        assert len({e["request_id"] for e in events}) == n
        vencedores = [e for e in events if e["outcome"] == "success"]
        perdedores = [e for e in events if e["outcome"] == "rejected"]
        assert len(vencedores) == 1
        assert len(perdedores) == n - 1
        assert vencedores[0]["revision_before"] == 3
        assert vencedores[0]["revision_after"] == 4
        # Cada perdedor observou 4 na secao critica (serializado depois do vencedor).
        for e in perdedores:
            assert e["revision_before"] == 4
            assert e["revision_after"] is None
            assert e["error_category"] == "REVISION_CONFLICT"

        # Nenhum secret na resposta nem na auditoria, sob concorrencia.
        blob = " ".join(r.text() for r in results) + " " + adopted.audit_text()
        assert_no_leak(blob, adopted.dsn)

    def test_ataques_concorrentes_nao_corrompem_estado(self, adopted: Harness) -> None:
        # Mistura de ataques (schema invalido, immutable, not found, conflito) em
        # paralelo com uma escrita legitima: a legitima vence, os ataques nao
        # deixam residuo, e o estado final e exatamente uma publicacao.
        before_bytes = adopted.config_path.read_bytes()
        results: dict[str, Reply] = {}
        lock = threading.Lock()

        attacks = {
            "immutable": (
                "PUT",
                "/admin/v1/sql",
                {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": ["x"]},
            ),
            "not_found": (
                "DELETE",
                f"/admin/v1/rules/{'rul_' + 'f' * 32}",
                {"expected_revision": 3},
            ),
            "schema": ("PUT", "/admin/v1/database", {"lixo": 1}),
            "conflict": (
                "POST",
                "/admin/v1/rules",
                {"expected_revision": 999, "rule": {"match": "x", "transformer": "md5"}},
            ),
            "legit": (
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            ),
        }

        def worker(name: str, method: str, path: str, body: Any) -> None:
            reply = call(adopted.port, method, path, body)
            with lock:
                results[name] = reply

        threads = [
            threading.Thread(target=worker, args=(name, m, p, b))
            for name, (m, p, b) in attacks.items()
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["legit"].status == 200
        assert results["immutable"].status == 422
        assert results["schema"].status == 422
        assert results["conflict"].status == 409
        assert results["not_found"].status in (404, 409)

        # Exatamente uma publicacao: revision 4, e os bytes mudaram uma vez.
        assert adopted.service.revision == 4
        assert adopted.config_path.read_bytes() != before_bytes
        assert adopted.service.reference_digest == adopted.store.read_snapshot().digest
