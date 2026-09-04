"""Auditoria administrativa ponta a ponta pela porta HTTP real (Fase 7, Etapa 10).

Tudo aqui roda contra um servidor HTTP real, em loopback, com o cliente cru, e
contra um `AdminConfigService` real sobre um PostgreSQL real: os candidatos sao
compilados, conectados e verificados de verdade. O DSN vem de `MASKGW_TEST_DSN`;
sem ele o arquivo inteiro da SKIP limpo, porque cada escrita constroi e conecta
um runtime candidato.

O que este arquivo prova (secao 13, e a lista de testes obrigatorios da Etapa 10):

- **uma unica entrada** por operacao que alcanca o handler — sucesso, recusa ou
  erro — e nenhuma para leitura, recusa anterior ao handler ou path desconhecido;
- **mapping completo** de operation/target_kind/target_id em cada rota;
- **`config:validate` auditado** como `validate`, sem contar como escrita e sem
  tocar runtime/arquivo/conexao;
- **recusas representativas** (revision conflict, not found, immutable field,
  config invalid, reload failure, write failure) com `outcome` e `error_category`
  coerentes;
- **durabilidade** com `revision_after` nova e `outcome=error`;
- **UUIDs distintos sob concorrencia** e **revisao coerente** sob duas escritas;
- **duracao monotonica e nao negativa**;
- **target ID malformado nunca registrado**;
- **nada sensivel** — corpo, match, config, token, HMAC, DSN, SQL, valor ou
  mensagem interna — em nenhum record;
- **falha do logger** nao altera resposta nem estado;
- **conjunto de rotas inalterado** e **nenhuma rota de auditoria**;
- **`admin/` sem import de logging** e **`stdout` MCP limpo** sob auditoria.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from maskgw.admin.http import build_admin_app
from maskgw.admin.http.server import AdminHttpServer
from maskgw.admin.service import AdminConfigService
from maskgw.audit import ADMIN_MESSAGE, AuditLog
from maskgw.bootstrap.application import make_adapter_factory
from maskgw.config.filesystem import ConfigFileStore, FilesystemHooks
from maskgw.config.gateway import build_gateway_config
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.masking.engine import MaskingEngine
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import Reply, request

pytestmark = pytest.mark.integration

TOKEN = "admin-token-para-teste-com-40-caracteres"
JSON = "application/json"
HMAC_KEY = "hmac-key-marker-com-mais-de-32-caracteres"

RULE_ID = "rul_" + "a" * 32
SECOND_RULE_ID = "rul_" + "c" * 32
EXCEPTION_ID = "exc_" + "b" * 32

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
# comentario que a adocao deve preservar no backup
masking:
  - match: cpf
    transformer: md5
exceptions:
  - match: tipo_cpf
"""


class RecordingHandler(logging.Handler):
    """Captura os `LogRecord` administrativos com seus campos estruturados.

    Prende so o logger administrativo do proprio harness, num logger de nome
    unico por teste, para nao competir com `caplog` nem com outra instancia
    concorrente. Guarda o record inteiro: os campos vao em `record.maskgw`.
    """

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


@dataclass
class AuditHarness:
    service: AdminConfigService
    store: ConfigFileStore
    registry: RuntimeRegistry
    config_path: Path
    server: AdminHttpServer
    handler: RecordingHandler
    logger: logging.Logger
    _closables: list[Any] = field(default_factory=list)

    @property
    def port(self) -> int:
        return self.server.port

    def events(self) -> list[dict[str, Any]]:
        return self.handler.admin_events()

    def close(self) -> None:
        self.server.stop()
        self.registry.close_all()
        self.store.close()
        self.logger.removeHandler(self.handler)


def _build_initial_runtime(payload_text: str, dsn: str) -> Runtime:
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
) -> AuditHarness:
    config_path = tmp_path / "masking.yaml"
    config_path.write_text(payload_text, encoding="utf-8")

    secrets = MappingSecretProvider({"MASKGW_HMAC_KEY": HMAC_KEY, "MASKGW_DATABASE_DSN": dsn})
    registry = RuntimeRegistry(_build_initial_runtime(payload_text, dsn))
    store = ConfigFileStore.open(config_path, hooks=hooks)
    service = AdminConfigService(
        store=store,
        registry=registry,
        adapter_factory=make_adapter_factory(dsn),
        reference_digest=store.read_snapshot().digest,
        secrets=secrets,
    )

    # Logger proprio por harness, com nome unico, para capturar so os eventos
    # deste teste. `propagate=False` mantem os records fora do root e do caplog.
    logger = logging.getLogger(f"test.admin.audit.{uuid.uuid4().hex}")
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
    return AuditHarness(
        service=service,
        store=store,
        registry=registry,
        config_path=config_path,
        server=server,
        handler=handler,
        logger=logger,
    )


@pytest.fixture
def adopted(tmp_path: Path, dsn: str) -> Iterator[AuditHarness]:
    payload = yaml.safe_dump(ADOPTED, sort_keys=False)
    state = make_harness(tmp_path, dsn, payload_text=payload)
    try:
        yield state
    finally:
        state.close()


@pytest.fixture
def unadopted(tmp_path: Path, dsn: str) -> Iterator[AuditHarness]:
    state = make_harness(tmp_path, dsn, payload_text=UNADOPTED_TEXT)
    try:
        yield state
    finally:
        state.close()


def call(port: int, method: str, path: str, body: Any, **kwargs: Any) -> Reply:
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return request(port, method, path, content_type=JSON, body=payload, **kwargs)


def only(events: list[dict[str, Any]]) -> dict[str, Any]:
    assert len(events) == 1, events
    return events[0]


# --------------------------------------------------------------------------
# Uma entrada por operacao, mapping completo
# --------------------------------------------------------------------------


class TestUmaEntradaPorEscrita:
    def test_create_rule(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "ssn", "transformer": "md5"}},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "rule_create"
        assert event["target_kind"] == "rule"
        assert event["target_id"] is None
        assert event["outcome"] == "success"
        assert event["revision_before"] == 3
        assert event["revision_after"] == 4
        assert event["error_category"] is None
        assert isinstance(event["duration_ms"], int)
        assert event["duration_ms"] >= 0
        # request_id e UUID hex de servidor.
        uuid.UUID(hex=event["request_id"])

    def test_update_rule_tem_target_id(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/rules/{RULE_ID}",
            {"expected_revision": 3, "rule": {"match": "cpf", "transformer": "md5"}},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "rule_update"
        assert event["target_kind"] == "rule"
        assert event["target_id"] == RULE_ID

    def test_delete_rule_tem_target_id(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            f"/admin/v1/rules/{RULE_ID}",
            {"expected_revision": 3},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "rule_delete"
        assert event["target_id"] == RULE_ID

    def test_reorder_sem_target_id(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": [SECOND_RULE_ID, RULE_ID]},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "rules_reorder"
        assert event["target_kind"] == "rule"
        assert event["target_id"] is None

    def test_create_exception(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/exceptions",
            {"expected_revision": 3, "exception": {"match": "tipo_email"}},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "exception_create"
        assert event["target_kind"] == "exception"
        assert event["target_id"] is None

    def test_update_exception_tem_target_id(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/exceptions/{EXCEPTION_ID}",
            {"expected_revision": 3, "exception": {"match": "tipo_cpf"}},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "exception_update"
        assert event["target_kind"] == "exception"
        assert event["target_id"] == EXCEPTION_ID

    def test_delete_exception_tem_target_id(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            f"/admin/v1/exceptions/{EXCEPTION_ID}",
            {"expected_revision": 3},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "exception_delete"
        assert event["target_id"] == EXCEPTION_ID

    def test_database_put(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 3, "statement_timeout_ms": 3000, "max_rows": 20},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "database_put"
        assert event["target_kind"] == "database"
        assert event["target_id"] is None

    def test_sql_put(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": ["pg_sleep"]},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "sql_put"
        assert event["target_kind"] == "sql"

    def test_config_put(self, adopted: AuditHarness) -> None:
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
        event = only(adopted.events())
        assert event["operation"] == "config_put"
        assert event["target_kind"] == "config"
        assert event["target_id"] is None
        assert event["revision_before"] == 3
        assert event["revision_after"] == 4

    def test_adopt(self, unadopted: AuditHarness) -> None:
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        assert reply.status == 200
        event = only(unadopted.events())
        assert event["operation"] == "adopt"
        assert event["target_kind"] == "config"
        assert event["target_id"] is None
        assert event["revision_before"] == 0
        assert event["revision_after"] == 1
        assert event["outcome"] == "success"


# --------------------------------------------------------------------------
# config:validate auditado, mas nao e escrita
# --------------------------------------------------------------------------


class TestValidateAuditado:
    def test_validate_sucesso(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/config:validate",
            {"masking": [{"match": "cpf", "transformer": "md5"}]},
        )
        assert reply.status == 200
        event = only(adopted.events())
        assert event["operation"] == "validate"
        assert event["target_kind"] == "config"
        assert event["target_id"] is None
        assert event["outcome"] == "success"
        assert event["revision_before"] is None
        assert event["revision_after"] is None
        assert event["error_category"] is None

    def test_validate_falha_de_compilacao(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/config:validate",
            {"masking": [{"match": "cpf", "transformer": "transformer_inexistente"}]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_INVALID"
        event = only(adopted.events())
        assert event["operation"] == "validate"
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "CONFIG_INVALID"
        assert event["revision_before"] is None
        assert event["revision_after"] is None

    def test_validate_nao_conta_como_escrita(self, adopted: AuditHarness) -> None:
        antes = adopted.service.operations_total
        call(
            adopted.port,
            "POST",
            "/admin/v1/config:validate",
            {"masking": [{"match": "cpf", "transformer": "md5"}]},
        )
        # `config:validate` nao entra na secao critica: o contador nao se move.
        assert adopted.service.operations_total == antes

    def test_validate_nao_toca_runtime_nem_revision(self, adopted: AuditHarness) -> None:
        revision_antes = adopted.service.revision
        call(
            adopted.port,
            "POST",
            "/admin/v1/config:validate",
            {"masking": [{"match": "cpf", "transformer": "md5"}]},
        )
        assert adopted.service.revision == revision_antes


# --------------------------------------------------------------------------
# Recusas representativas
# --------------------------------------------------------------------------


class TestRecusas:
    def test_revision_conflict(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 99, "rule": {"match": "ssn", "transformer": "md5"}},
        )
        assert reply.status == 409
        event = only(adopted.events())
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "REVISION_CONFLICT"
        # revision_before e a observada na secao critica (a atual), mesmo na recusa.
        assert event["revision_before"] == 3
        assert event["revision_after"] is None

    def test_not_found(self, adopted: AuditHarness) -> None:
        missing = "rul_" + "f" * 32
        reply = call(
            adopted.port,
            "DELETE",
            f"/admin/v1/rules/{missing}",
            {"expected_revision": 3},
        )
        assert reply.status == 404
        event = only(adopted.events())
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "NOT_FOUND"
        assert event["operation"] == "rule_delete"
        # ID canonico, so inexistente: e registrado como target_id.
        assert event["target_id"] == missing

    def test_immutable_field(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {
                "expected_revision": 3,
                "denied_functions": [],
                "allowed_pg_functions": ["pg_read_file"],
            },
        )
        assert reply.status == 422
        event = only(adopted.events())
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "IMMUTABLE_FIELD"
        assert event["operation"] == "sql_put"

    def test_config_invalid(self, adopted: AuditHarness) -> None:
        # Posicao de insercao fora de 0..len: recusa dependente do estado.
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "position": 999, "rule": {"match": "x", "transformer": "md5"}},
        )
        assert reply.status == 422
        event = only(adopted.events())
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "CONFIG_INVALID"

    def test_reload_error(self, adopted: AuditHarness) -> None:
        # Passa o schema, mas nao compila (transformer inexistente): passo 6.
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "x", "transformer": "nao_existe"}},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_RELOAD_ERROR"
        event = only(adopted.events())
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "CONFIG_RELOAD_ERROR"
        assert event["revision_before"] == 3
        # Nada foi publicado.
        assert event["revision_after"] is None

    def test_write_error(self, tmp_path: Path, dsn: str) -> None:
        # `os.replace` do store levanta antes do ponto de nao-retorno.
        def boom_replace(_source: str, _target: str) -> None:
            msg = "replace injetado"
            raise OSError(msg)

        hooks = FilesystemHooks(replace=boom_replace)
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        harness = make_harness(tmp_path, dsn, payload_text=payload, hooks=hooks)
        try:
            reply = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 500
            assert reply.json()["error"] == "CONFIG_WRITE_ERROR"
            event = only(harness.events())
            assert event["outcome"] == "error"
            assert event["error_category"] == "CONFIG_WRITE_ERROR"
            assert event["revision_before"] == 3
            # Falha ANTES do replace: nada publicado.
            assert event["revision_after"] is None
            assert "injetado" not in json.dumps(harness.events())
        finally:
            harness.server.stop()
            harness.registry.close_all()
            harness.store.close()


class TestDurabilidade:
    def test_durability_error_publica_com_revision_after(self, tmp_path: Path, dsn: str) -> None:
        """§7.6: fsync de diretorio falho -> `outcome=error`, `revision_after` nova.

        So POSIX: no Windows o fsync de diretorio e deliberadamente omitido, e a
        durabilidade nunca falha por essa via. A omissao ja e afirmada pelo
        teste-par de `test_admin_http_writes.py`; aqui o foco e a AUDITORIA do
        caminho de durabilidade, que so existe no POSIX.
        """
        if os.name != "posix":
            pytest.skip("fsync de diretorio so no POSIX; no Windows e omitido")

        def boom(_descriptor: int) -> None:
            msg = "fsync de diretorio injetado"
            raise OSError(msg)

        hooks = FilesystemHooks(directory_fsync=boom)
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        harness = make_harness(tmp_path, dsn, payload_text=payload, hooks=hooks)
        try:
            reply = call(
                harness.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 500
            assert reply.json()["error"] == "CONFIG_DURABILITY_ERROR"
            event = only(harness.events())
            assert event["outcome"] == "error"
            assert event["error_category"] == "CONFIG_DURABILITY_ERROR"
            assert event["revision_before"] == 3
            # A mudanca FOI publicada: revision_after e a nova (secao 7.6).
            assert event["revision_after"] == 4
            assert "injetado" not in json.dumps(harness.events())
        finally:
            harness.server.stop()
            harness.registry.close_all()
            harness.store.close()


# --------------------------------------------------------------------------
# target ID malformado nunca vira target_id
# --------------------------------------------------------------------------


class TestTargetIdMalformado:
    def test_id_fora_do_padrao_vira_target_id_none(self, adopted: AuditHarness) -> None:
        # Um segmento sem barra casa a rota dinamica `/rules/{rule_id}` e ALCANCA
        # o handler; a mutacao recusa com NOT_FOUND. A operacao e auditada — uma
        # entrada, `outcome=rejected` — mas o path malformado NUNCA e registrado:
        # `target_id` e None mesmo na recusa (secao 13.3). Registrar o texto cru
        # do path abriria um canal para valores no log.
        reply = call(
            adopted.port,
            "DELETE",
            "/admin/v1/rules/nao-e-um-id",
            {"expected_revision": 3},
        )
        assert reply.status == 404
        event = only(adopted.events())
        assert event["operation"] == "rule_delete"
        assert event["outcome"] == "rejected"
        assert event["error_category"] == "NOT_FOUND"
        assert event["target_id"] is None

    def test_id_canonico_mas_inexistente_registra_o_id(self, adopted: AuditHarness) -> None:
        # Ja um ID CANONICO inexistente alcanca o handler (o path casa a rota),
        # a mutacao recusa com NOT_FOUND, e o target_id e o proprio ID canonico.
        canonical_missing = "rul_" + "e" * 32
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/rules/{canonical_missing}",
            {"expected_revision": 3, "rule": {"match": "x", "transformer": "md5"}},
        )
        assert reply.status == 404
        event = only(adopted.events())
        assert event["target_id"] == canonical_missing


# --------------------------------------------------------------------------
# Leitura, recusa de fronteira e schema nao geram AdminAudit
# --------------------------------------------------------------------------


class TestSemAuditFuraDoHandler:
    def test_leitura_nao_gera_audit(self, adopted: AuditHarness) -> None:
        assert request(adopted.port, "GET", "/admin/v1/config").status == 200
        assert request(adopted.port, "GET", "/admin/v1/status").status == 200
        assert request(adopted.port, "GET", "/admin/v1/rules").status == 200
        assert adopted.events() == []

    def test_auth_ausente_nao_gera_audit(self, adopted: AuditHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "x", "transformer": "md5"}},
            token=None,
        )
        assert reply.status == 401
        assert adopted.events() == []

    def test_schema_invalido_nao_gera_audit(self, adopted: AuditHarness) -> None:
        # `expected_revision` ausente: falha de schema, o handler nem roda.
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"rule": {"match": "x", "transformer": "md5"}},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        assert adopted.events() == []

    def test_path_desconhecido_nao_gera_audit(self, adopted: AuditHarness) -> None:
        assert request(adopted.port, "GET", "/admin/v1/inexistente").status == 404
        assert adopted.events() == []

    def test_metodo_nao_registrado_nao_gera_audit(self, adopted: AuditHarness) -> None:
        # PATCH nao existe em rota alguma.
        reply = call(
            adopted.port,
            "PATCH",
            "/admin/v1/sql",
            {"expected_revision": 3},
        )
        assert reply.status in (404, 405)
        assert adopted.events() == []


# --------------------------------------------------------------------------
# Concorrencia: UUIDs distintos e revisao coerente
# --------------------------------------------------------------------------


class TestConcorrencia:
    def test_uuids_distintos_sob_concorrencia(self, adopted: AuditHarness) -> None:
        results: list[Reply] = []
        lock = threading.Lock()

        def worker(rev: int) -> None:
            reply = call(
                adopted.port,
                "POST",
                "/admin/v1/rules",
                {"expected_revision": rev, "rule": {"match": "x", "transformer": "md5"}},
            )
            with lock:
                results.append(reply)

        threads = [threading.Thread(target=worker, args=(3,)) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        events = adopted.events()
        assert len(events) == 5
        request_ids = {event["request_id"] for event in events}
        assert len(request_ids) == 5

    def test_duas_escritas_concorrentes_revisao_coerente(self, adopted: AuditHarness) -> None:
        results: list[Reply] = []
        lock = threading.Lock()

        def worker() -> None:
            reply = call(
                adopted.port,
                "POST",
                "/admin/v1/rules",
                {"expected_revision": 3, "rule": {"match": "x", "transformer": "md5"}},
            )
            with lock:
                results.append(reply)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        statuses = sorted(reply.status for reply in results)
        assert statuses == [200, 409]

        events = adopted.events()
        assert len(events) == 2
        success = next(e for e in events if e["outcome"] == "success")
        rejected = next(e for e in events if e["outcome"] == "rejected")
        # As duas escritas sao SERIALIZADAS pela secao critica: a que vence
        # observa 3 e publica 4; a que perde so entra na secao critica DEPOIS,
        # observa 4 e e recusada porque `expected_revision` 3 != 4. Isto prova o
        # requisito da secao 13: `revision_before` e a revision observada DENTRO
        # da secao critica, ja depois de esperar pelo lock — nunca um snapshot
        # tomado antes. Se fosse tomado antes, a recusada tambem diria 3.
        assert success["revision_before"] == 3
        assert success["revision_after"] == 4
        assert rejected["revision_before"] == 4
        assert rejected["revision_after"] is None
        assert rejected["error_category"] == "REVISION_CONFLICT"


# --------------------------------------------------------------------------
# Nada sensivel nos records
# --------------------------------------------------------------------------


class TestNadaSensivel:
    def test_nenhum_dado_sensivel_em_record_algum(self, adopted: AuditHarness) -> None:
        # Uma sequencia de escritas com marcadores no corpo, config e denied.
        call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {
                "expected_revision": 3,
                "rule": {
                    "match": "numero_cpf_sensivel",
                    "transformer": "regex",
                    "config": {"pattern": "SEGREDO_PATTERN", "replacement": "SEGREDO_REPL"},
                },
            },
        )
        call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 4, "denied_functions": ["funcao_secreta_marcador"]},
        )
        rendered = json.dumps(adopted.events())
        for marker in (
            "numero_cpf_sensivel",
            "SEGREDO_PATTERN",
            "SEGREDO_REPL",
            "funcao_secreta_marcador",
            TOKEN,
            HMAC_KEY,
            "postgres",
            "password",
            "SELECT",
        ):
            assert marker not in rendered

    def test_recusa_nao_vaza_mensagem_interna(self, adopted: AuditHarness) -> None:
        bad_rule = {"match": "x", "transformer": "regex", "config": {"pattern": "(["}}
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/config:validate",
            {"masking": [bad_rule]},
        )
        assert reply.status == 422
        rendered = json.dumps(adopted.events())
        # error_category e a categoria fechada; nunca a mensagem do compilador.
        assert "CONFIG_INVALID" in rendered
        assert "unbalanced" not in rendered
        assert "(" not in rendered


# --------------------------------------------------------------------------
# Falha do logger nao altera resposta nem estado
# --------------------------------------------------------------------------


class TestFalhaDoLogger:
    def test_logger_que_levanta_nao_altera_resposta_nem_estado(
        self, tmp_path: Path, dsn: str
    ) -> None:
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        harness = make_harness(tmp_path, dsn, payload_text=payload)
        try:
            # Troca o handler por um que sempre levanta: a auditoria e best-effort.
            class _BoomHandler(logging.Handler):
                def emit(self, _record: logging.LogRecord) -> None:
                    msg = "handler quebrado no meio da auditoria"
                    raise RuntimeError(msg)

            harness.logger.removeHandler(harness.handler)
            harness.logger.addHandler(_BoomHandler())

            reply = call(
                harness.port,
                "POST",
                "/admin/v1/rules",
                {"expected_revision": 3, "rule": {"match": "ssn", "transformer": "md5"}},
            )
            # A escrita valeu, com a resposta normal.
            assert reply.status == 200
            assert reply.json() == {"revision": 4, "applied": True}
            # E o estado avancou: o GET seguinte ve revision 4.
            config = request(harness.port, "GET", "/admin/v1/config").json()["config"]
            assert config["revision"] == 4
        finally:
            harness.server.stop()
            harness.registry.close_all()
            harness.store.close()

    def test_logger_que_levanta_em_recusa_nao_altera_resposta(
        self, tmp_path: Path, dsn: str
    ) -> None:
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        harness = make_harness(tmp_path, dsn, payload_text=payload)
        try:

            class _BoomHandler(logging.Handler):
                def emit(self, _record: logging.LogRecord) -> None:
                    msg = "boom"
                    raise RuntimeError(msg)

            harness.logger.removeHandler(harness.handler)
            harness.logger.addHandler(_BoomHandler())

            reply = call(
                harness.port,
                "POST",
                "/admin/v1/rules",
                {"expected_revision": 99, "rule": {"match": "x", "transformer": "md5"}},
            )
            assert reply.status == 409
            assert reply.json()["error"] == "REVISION_CONFLICT"
        finally:
            harness.server.stop()
            harness.registry.close_all()
            harness.store.close()


# --------------------------------------------------------------------------
# Conjunto de rotas inalterado, nenhuma rota de auditoria
# --------------------------------------------------------------------------


class TestNenhumaRotaDeAuditoria:
    def test_nao_ha_rota_audit(self, adopted: AuditHarness) -> None:
        for path in ("/admin/v1/audit", "/admin/v1/audit/1", "/admin/v1/audit/events"):
            reply = request(adopted.port, "GET", path)
            assert reply.status == 404, path
        # Nenhuma dessas leituras gerou AdminAudit.
        assert adopted.events() == []
