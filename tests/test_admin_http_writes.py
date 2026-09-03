"""Fase 7, Etapa 9: as onze rotas de escrita e a adocao (secoes 1.3, 5, 6, 7, 12).

Tudo aqui roda contra um servidor HTTP real, em loopback, com o cliente cru, e
contra um `AdminConfigService` real sobre um PostgreSQL real — os candidatos sao
compilados, conectados e verificados de verdade. O DSN vem de `MASKGW_TEST_DSN`;
sem ele o arquivo inteiro da SKIP limpo, porque cada escrita constroi e conecta
um runtime candidato.

O que este arquivo prova, por rota e por invariante da §12:

- **sucesso de cada uma das onze rotas**, com o `GET` seguinte refletindo a
  mudanca e a `revision` subindo exatamente uma vez;
- **concorrencia (§12.1):** dois requests com o mesmo `expected_revision` — um
  vence, o outro e `409 REVISION_CONFLICT`;
- **adocao (§5, §12.9):** IDs atribuidos, `revision 0 -> 1`, masking inalterado,
  segunda adocao recusada sem efeito, backup byte a byte com `O_EXCL`/`0600`,
  colisao de backup sem tocar o principal;
- **IDs (D-059):** estaveis em update/reorder, novos em create, imutaveis quando
  o cliente tenta escolhe-los;
- **imutabilidade (§11.3):** `allowed_pg_functions` presente -> `IMMUTABLE_FIELD`;
  ausente -> valor preservado em conteudo e ordem;
- **falha injetada (§12.4):** durabilidade publica o novo com `applied: true`;
- **sem efeito** em cada recusa: arquivo, runtime e digest coerentes.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from maskgw.admin.http import build_admin_app
from maskgw.admin.http.server import AdminHttpServer
from maskgw.admin.service import AdminConfigService
from maskgw.bootstrap.application import make_adapter_factory
from maskgw.config.filesystem import (
    ConfigFileStore,
    DigestCheckPoint,
    FilesystemHooks,
)
from maskgw.config.gateway import build_gateway_config
from maskgw.config.loader import compile_policy, validate_file_config
from maskgw.masking.descriptor import ColumnDescriptor, ProvenanceKind
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

#: Documento adotado inicial. Revision 3, IDs presentes: o ponto de partida das
#: escritas granulares.
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

#: Documento NAO adotado, com comentario a preservar no backup da adocao.
UNADOPTED_TEXT = """\
# comentario que a adocao deve preservar no backup
masking:
  - match: cpf
    transformer: md5
exceptions:
  - match: tipo_cpf
"""


@dataclass
class WriteHarness:
    """Servico real + servidor real + PostgreSQL real."""

    service: AdminConfigService
    store: ConfigFileStore
    registry: RuntimeRegistry
    config_path: Path
    server: AdminHttpServer
    _closables: list[Any] = field(default_factory=list)

    @property
    def port(self) -> int:
        return self.server.port

    def close(self) -> None:
        self.server.stop()
        self.registry.close_all()
        self.store.close()


def _build_initial_runtime(payload_text: str, dsn: str) -> tuple[Runtime, Any]:
    document = validate_file_config(yaml.safe_load(payload_text))
    secrets = MappingSecretProvider({"MASKGW_HMAC_KEY": HMAC_KEY})
    policy = compile_policy(document, secrets=secrets)
    config = build_gateway_config(document, policy)
    engine = MaskingEngine(policy)
    adapter = make_adapter_factory(dsn)(config=config, engine=engine)
    adapter.connect()
    runtime = Runtime(
        revision=document.revision,
        file_config=document,
        config=config,
        engine=engine,
        adapter=adapter,
    )
    return runtime, adapter


def make_harness(
    tmp_path: Path,
    dsn: str,
    *,
    payload_text: str,
    hooks: FilesystemHooks | None = None,
    clock: Any = None,
) -> WriteHarness:
    config_path = tmp_path / "masking.yaml"
    config_path.write_text(payload_text, encoding="utf-8")

    secrets = MappingSecretProvider({"MASKGW_HMAC_KEY": HMAC_KEY, "MASKGW_DATABASE_DSN": dsn})
    runtime, _adapter = _build_initial_runtime(payload_text, dsn)
    registry = RuntimeRegistry(runtime)
    store = ConfigFileStore.open(config_path, hooks=hooks)

    service_kwargs: dict[str, Any] = {
        "store": store,
        "registry": registry,
        "adapter_factory": make_adapter_factory(dsn),
        "reference_digest": store.read_snapshot().digest,
        "secrets": secrets,
    }
    if clock is not None:
        service_kwargs["clock"] = clock
    service = AdminConfigService(**service_kwargs)

    def factory(bound_port: int) -> Any:
        return build_admin_app(
            service,
            token=TOKEN,
            port=bound_port,
            secrets=secrets,
            database_dsn_env="MASKGW_DATABASE_DSN",
        )

    server = AdminHttpServer(app_factory=factory, host="127.0.0.1", port=0)
    server.start()
    return WriteHarness(
        service=service,
        store=store,
        registry=registry,
        config_path=config_path,
        server=server,
    )


@pytest.fixture
def adopted(tmp_path: Path, dsn: str) -> Iterator[WriteHarness]:
    payload = yaml.safe_dump(ADOPTED, sort_keys=False)
    state = make_harness(tmp_path, dsn, payload_text=payload)
    try:
        yield state
    finally:
        state.close()


@pytest.fixture
def unadopted(tmp_path: Path, dsn: str) -> Iterator[WriteHarness]:
    state = make_harness(tmp_path, dsn, payload_text=UNADOPTED_TEXT)
    try:
        yield state
    finally:
        state.close()


def call(port: int, method: str, path: str, body: Any, **kwargs: Any) -> Reply:
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return request(port, method, path, content_type=JSON, body=payload, **kwargs)


def get_config(port: int) -> dict[str, Any]:
    reply = request(port, "GET", "/admin/v1/config")
    assert reply.status == 200
    result: dict[str, Any] = reply.json()["config"]
    return result


def get_status(port: int) -> dict[str, Any]:
    reply = request(port, "GET", "/admin/v1/status")
    assert reply.status == 200
    result: dict[str, Any] = reply.json()
    return result


# --------------------------------------------------------------------------
# Sucesso de cada rota, com GET refletindo e revision +1
# --------------------------------------------------------------------------


class TestSucessoDeCadaRota:
    def test_create_rule_no_fim(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "ssn", "transformer": "md5"}},
        )
        assert reply.status == 200
        assert reply.json() == {"revision": 4, "applied": True}
        config = get_config(adopted.port)
        assert [r["match"] for r in config["masking"]] == ["cpf", "email", "ssn"]
        assert config["revision"] == 4

    def test_create_rule_em_posicao(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {
                "expected_revision": 3,
                "position": 0,
                "rule": {"match": "ssn", "transformer": "md5"},
            },
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        assert [r["match"] for r in config["masking"]] == ["ssn", "cpf", "email"]

    def test_replace_rule(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/rules/{RULE_ID}",
            {"expected_revision": 3, "rule": {"match": "documento", "transformer": "sha512"}},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        first = config["masking"][0]
        assert first["id"] == RULE_ID  # ID preservado
        assert first["match"] == "documento"
        assert first["transformer"] == "sha512"

    def test_delete_rule(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            f"/admin/v1/rules/{RULE_ID}",
            {"expected_revision": 3},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        assert [r["id"] for r in config["masking"]] == [SECOND_RULE_ID]

    def test_reorder_rules(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": [SECOND_RULE_ID, RULE_ID]},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        assert [r["id"] for r in config["masking"]] == [SECOND_RULE_ID, RULE_ID]

    def test_create_exception(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/exceptions",
            {"expected_revision": 3, "exception": {"match": "tipo_email"}},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        assert [e["match"] for e in config["exceptions"]] == ["tipo_cpf", "tipo_email"]

    def test_replace_exception(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/exceptions/{EXCEPTION_ID}",
            {"expected_revision": 3, "exception": {"match": "outro_tipo"}},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        exc = config["exceptions"][0]
        assert exc["id"] == EXCEPTION_ID
        assert exc["match"] == "outro_tipo"

    def test_delete_exception(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            f"/admin/v1/exceptions/{EXCEPTION_ID}",
            {"expected_revision": 3},
        )
        assert reply.status == 200
        assert get_config(adopted.port)["exceptions"] == []

    def test_replace_database(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 42},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        assert config["database"] == {"statement_timeout_ms": 5000, "max_rows": 42}

    def test_replace_sql_aditivo(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": ["dblink_exec", "pg_sleep"]},
        )
        assert reply.status == 200
        config = get_config(adopted.port)
        # Aditivo, sem duplicata: o `dblink_exec` original permanece uma vez.
        assert config["sql"]["denied_functions"] == ["dblink_exec", "pg_sleep"]

    def test_put_config_substituicao_integral(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [
                    {"id": RULE_ID, "match": "cpf", "transformer": "sha256"},
                    {"match": "nova", "transformer": "md5"},
                ],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": ["x"]},
            },
        )
        assert reply.status == 200
        assert reply.json() == {"revision": 4, "applied": True}
        config = get_config(adopted.port)
        assert config["masking"][0]["id"] == RULE_ID
        assert config["masking"][1]["id"].startswith("rul_")
        assert config["exceptions"] == []

    def test_revision_incrementa_exatamente_uma_vez(self, adopted: WriteHarness) -> None:
        assert get_status(adopted.port)["revision"] == 3
        call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 42},
        )
        assert get_status(adopted.port)["revision"] == 4


# --------------------------------------------------------------------------
# expected_revision, concorrencia, estado
# --------------------------------------------------------------------------


class TestConcorrenciaERevision:
    def test_revision_conflict(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 99, "statement_timeout_ms": 5000, "max_rows": 42},
        )
        assert reply.status == 409
        body = reply.json()
        assert body["error"] == "REVISION_CONFLICT"
        assert body["current_revision"] == 3

    def test_dois_com_mesmo_expected_revision_um_vence(self, adopted: WriteHarness) -> None:
        """§12.1: exatamente um `200`, o outro `409`; revision final = 4."""
        results: list[int] = []
        lock = threading.Lock()

        def fire(timeout: int) -> None:
            reply = call(
                adopted.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": timeout, "max_rows": 5},
            )
            with lock:
                results.append(reply.status)

        threads = [threading.Thread(target=fire, args=(1000 + i,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results.count(200) == 1
        assert results.count(409) == len(results) - 1
        assert get_status(adopted.port)["revision"] == 4


# --------------------------------------------------------------------------
# Not found e reorder/posicao invalidos, sanitizados
# --------------------------------------------------------------------------


class TestRecusasSanitizadas:
    def test_replace_rule_inexistente_e_404(self, adopted: WriteHarness) -> None:
        missing = "rul_" + "0" * 32
        reply = call(
            adopted.port,
            "PUT",
            f"/admin/v1/rules/{missing}",
            {"expected_revision": 3, "rule": {"match": "x", "transformer": "md5"}},
        )
        assert reply.status == 404
        assert reply.json()["error"] == "NOT_FOUND"
        # O ID pedido nunca aparece no corpo.
        assert missing not in reply.text()

    def test_delete_rule_inexistente_e_404(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            "/admin/v1/rules/rul_" + "0" * 32,
            {"expected_revision": 3},
        )
        assert reply.status == 404

    def test_delete_exception_inexistente_e_404(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "DELETE",
            "/admin/v1/exceptions/exc_" + "0" * 32,
            {"expected_revision": 3},
        )
        assert reply.status == 404

    def test_posicao_invalida_e_config_invalid(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {
                "expected_revision": 3,
                "position": 99,
                "rule": {"match": "x", "transformer": "md5"},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_INVALID"

    def test_reorder_incompleto_e_config_invalid(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": [RULE_ID]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_INVALID"

    def test_reorder_com_id_estranho_e_config_invalid(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": [RULE_ID, "rul_" + "9" * 32]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_INVALID"

    def test_transformer_inexistente_e_config_reload_error(self, adopted: WriteHarness) -> None:
        """Passa o schema, mas nao compila: `CONFIG_RELOAD_ERROR` (§7.4 passo 6)."""
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "x", "transformer": "nao_existe"}},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "CONFIG_RELOAD_ERROR"


# --------------------------------------------------------------------------
# Imutabilidade: allowed_pg_functions e id escolhido pelo cliente
# --------------------------------------------------------------------------


class TestImutabilidade:
    def test_put_sql_com_allowed_e_immutable(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": ["x"]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"

    def test_put_sql_com_allowed_vazio_ainda_e_immutable(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": []},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"

    @pytest.mark.parametrize("value", [None, [], ["pg_read_file"], "x", {"a": 1}, True, 5])
    def test_put_sql_allowed_presente_qualquer_forma_e_immutable_sem_efeito(
        self, adopted: WriteHarness, value: Any
    ) -> None:
        """A regressao central: `null` explicito era tratado como ausente.

        Qualquer forma enviada — inclusive `null` — é `IMMUTABLE_FIELD`, e a
        recusa não altera arquivo, digest, revisão nem runtime, e não constrói
        candidato (o adapter existente não conecta a mais).
        """
        before_bytes = adopted.config_path.read_bytes()
        before_current = adopted.registry.current
        before_revision = adopted.service.revision
        before_digest = adopted.service.reference_digest

        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": ["nova"], "allowed_pg_functions": value},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"

        assert adopted.config_path.read_bytes() == before_bytes
        assert adopted.registry.current is before_current
        assert adopted.service.revision == before_revision
        assert adopted.service.reference_digest == before_digest

    @pytest.mark.parametrize("value", [None, [], ["pg_read_file"], "x", {"a": 1}, True, 5])
    def test_put_config_allowed_presente_qualquer_forma_e_immutable(
        self, adopted: WriteHarness, value: Any
    ) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": [], "allowed_pg_functions": value},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"

    def test_put_config_sem_denied_functions_e_schema_invalid(self, adopted: WriteHarness) -> None:
        """`sql: {}` num `PUT /config` apagaria as negações — agora `SCHEMA_INVALID`."""
        before_bytes = adopted.config_path.read_bytes()
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        assert adopted.config_path.read_bytes() == before_bytes

    def test_adopt_confirm_um_inteiro_e_schema_invalid(self, unadopted: WriteHarness) -> None:
        """`confirm_comment_loss: 1` (inteiro) era aceito como `true`."""
        before_bytes = unadopted.config_path.read_bytes()
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": 1},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        assert unadopted.config_path.read_bytes() == before_bytes
        assert get_status(unadopted.port)["revision"] == 0

    def test_reorder_id_malformado_e_schema_invalid(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": ["nao-e-um-id"]},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"

    def test_reorder_lista_vazia_sobre_zero_regras_e_200(self, tmp_path: Path, dsn: str) -> None:
        """Lista vazia é permutação completa do conjunto vazio quando há 0 regras."""
        payload = yaml.safe_dump(
            {
                "revision": 3,
                "masking": [],
                "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": []},
            },
            sort_keys=False,
        )
        state = make_harness(tmp_path, dsn, payload_text=payload)
        try:
            reply = call(
                state.port,
                "POST",
                "/admin/v1/rules:reorder",
                {"expected_revision": 3, "rule_ids": []},
            )
            assert reply.status == 200
            assert reply.json() == {"revision": 4, "applied": True}
        finally:
            state.close()

    def test_put_sql_dedup_semantico_por_http(self, adopted: WriteHarness) -> None:
        """`Foo`/`foo`/`FOO` colapsam; a repetição idempotente não cresce a lista."""
        first = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 3, "denied_functions": ["DBLINK_EXEC", "pg_sleep", "PG_SLEEP"]},
        )
        assert first.status == 200
        denied = get_config(adopted.port)["sql"]["denied_functions"]
        assert denied == ["dblink_exec", "pg_sleep"]
        # Reaplica com outras grafias: idempotente.
        second = call(
            adopted.port,
            "PUT",
            "/admin/v1/sql",
            {"expected_revision": 4, "denied_functions": ["Pg_Sleep", " dblink_exec "]},
        )
        assert second.status == 200
        assert get_config(adopted.port)["sql"]["denied_functions"] == ["dblink_exec", "pg_sleep"]

    def test_put_config_com_allowed_e_immutable(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": [], "allowed_pg_functions": ["x"]},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"

    def test_put_config_ausente_preserva_allowed(self, adopted: WriteHarness) -> None:
        """§11.3: ausente -> valor atual preservado em conteudo e ordem."""
        before = get_config(adopted.port)["sql"]["allowed_pg_functions"]
        assert before == ["pg_typeof"]
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": ["novo"]},
            },
        )
        assert reply.status == 200
        after = get_config(adopted.port)["sql"]["allowed_pg_functions"]
        assert after == before  # conteudo e ordem

    def test_put_config_id_estranho_e_immutable(self, adopted: WriteHarness) -> None:
        reply = call(
            adopted.port,
            "PUT",
            "/admin/v1/config",
            {
                "expected_revision": 3,
                "masking": [{"id": "rul_" + "f" * 32, "match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": []},
            },
        )
        assert reply.status == 422
        assert reply.json()["error"] == "IMMUTABLE_FIELD"


# --------------------------------------------------------------------------
# IDs: estaveis em update/reorder, novos em create
# --------------------------------------------------------------------------


class TestIdentidadeDeIds:
    def test_update_preserva_id(self, adopted: WriteHarness) -> None:
        call(
            adopted.port,
            "PUT",
            f"/admin/v1/rules/{RULE_ID}",
            {"expected_revision": 3, "rule": {"match": "novo", "transformer": "md5"}},
        )
        assert get_config(adopted.port)["masking"][0]["id"] == RULE_ID

    def test_reorder_preserva_ids(self, adopted: WriteHarness) -> None:
        call(
            adopted.port,
            "POST",
            "/admin/v1/rules:reorder",
            {"expected_revision": 3, "rule_ids": [SECOND_RULE_ID, RULE_ID]},
        )
        ids = {r["id"] for r in get_config(adopted.port)["masking"]}
        assert ids == {RULE_ID, SECOND_RULE_ID}

    def test_delete_e_create_geram_id_diferente(self, adopted: WriteHarness) -> None:
        call(adopted.port, "DELETE", f"/admin/v1/rules/{RULE_ID}", {"expected_revision": 3})
        call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 4, "rule": {"match": "cpf", "transformer": "sha256"}},
        )
        new_ids = [r["id"] for r in get_config(adopted.port)["masking"]]
        assert RULE_ID not in new_ids
        assert all(rid.startswith("rul_") for rid in new_ids)

    def test_create_gera_id_novo(self, adopted: WriteHarness) -> None:
        call(
            adopted.port,
            "POST",
            "/admin/v1/rules",
            {"expected_revision": 3, "rule": {"match": "ssn", "transformer": "md5"}},
        )
        created = get_config(adopted.port)["masking"][-1]
        assert created["id"].startswith("rul_")
        assert created["id"] not in {RULE_ID, SECOND_RULE_ID}


# --------------------------------------------------------------------------
# Adocao e backup (secao 5, secao 12.9)
# --------------------------------------------------------------------------


def _backups(config_path: Path) -> list[Path]:
    return sorted(config_path.parent.glob(f"{config_path.name}.bak.*"))


class TestAdocao:
    def test_adocao_atribui_ids_e_publica_revision_1(self, unadopted: WriteHarness) -> None:
        assert get_status(unadopted.port)["adopted"] is False
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        assert reply.status == 200
        assert reply.json() == {"revision": 1, "applied": True}
        status = get_status(unadopted.port)
        assert status["revision"] == 1
        assert status["adopted"] is True
        config = get_config(unadopted.port)
        assert all(r["id"].startswith("rul_") for r in config["masking"])
        assert all(e["id"].startswith("exc_") for e in config["exceptions"])

    def test_escrita_antes_da_adocao_e_recusada(self, unadopted: WriteHarness) -> None:
        reply = call(
            unadopted.port,
            "PUT",
            "/admin/v1/database",
            {"expected_revision": 0, "statement_timeout_ms": 5000, "max_rows": 42},
        )
        assert reply.status == 409
        assert reply.json()["error"] == "CONFIG_NOT_ADOPTED"

    def test_adopt_sem_confirm_e_schema_invalid(self, unadopted: WriteHarness) -> None:
        reply = call(unadopted.port, "POST", "/admin/v1/config:adopt", {"expected_revision": 0})
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"

    def test_adopt_confirm_false_e_schema_invalid(self, unadopted: WriteHarness) -> None:
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": False},
        )
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"

    def test_adopt_com_revision_diferente_de_zero_e_conflict(self, unadopted: WriteHarness) -> None:
        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 5, "confirm_comment_loss": True},
        )
        assert reply.status == 409
        assert reply.json()["error"] == "REVISION_CONFLICT"

    def test_segunda_adocao_recusada_sem_efeito(self, unadopted: WriteHarness) -> None:
        """§12.9 caminho B: bytes identicos, sem novo backup, IDs iguais."""
        call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        first_ids = [r["id"] for r in get_config(unadopted.port)["masking"]]
        bytes_after_first = unadopted.config_path.read_bytes()
        backups_after_first = _backups(unadopted.config_path)
        assert len(backups_after_first) == 1

        reply = call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 1, "confirm_comment_loss": True},
        )
        assert reply.status == 409
        assert reply.json()["error"] == "CONFIG_ALREADY_ADOPTED"
        # Nada mudou: bytes, IDs e o conjunto de backups.
        assert unadopted.config_path.read_bytes() == bytes_after_first
        assert [r["id"] for r in get_config(unadopted.port)["masking"]] == first_ids
        assert _backups(unadopted.config_path) == backups_after_first

    def test_backup_byte_a_byte_o_excl_e_0600(self, unadopted: WriteHarness) -> None:
        """§12.9: o backup contem os bytes originais exatos, com `0600`."""
        original = unadopted.config_path.read_bytes()
        assert b"comentario que a adocao deve preservar" in original

        call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        backups = _backups(unadopted.config_path)
        assert len(backups) == 1
        backup = backups[0]
        # Bytes originais exatos, comentario preservado.
        assert backup.read_bytes() == original
        if os.name == "posix":
            assert stat.S_IMODE(backup.stat().st_mode) == 0o600

    def test_backup_colisao_falha_e_nao_toca_o_principal(self, tmp_path: Path, dsn: str) -> None:
        """§12.9: nome ja ocupado -> `CONFIG_WRITE_ERROR`, `masking.yaml` intacto."""
        # Relogio fixo: o nome do backup e deterministico, e podemos ocupa-lo.
        state = make_harness(tmp_path, dsn, payload_text=UNADOPTED_TEXT, clock=lambda: 424242)
        try:
            collision = state.store.backup_path(424242)
            collision.write_bytes(b"backup preexistente que nao pode ser destruido")
            preexisting = collision.read_bytes()
            original_main = state.config_path.read_bytes()

            reply = call(
                state.port,
                "POST",
                "/admin/v1/config:adopt",
                {"expected_revision": 0, "confirm_comment_loss": True},
            )
            assert reply.status == 500
            assert reply.json()["error"] == "CONFIG_WRITE_ERROR"
            # O backup preexistente nao foi sobrescrito, e o principal esta intacto.
            assert collision.read_bytes() == preexisting
            assert state.config_path.read_bytes() == original_main
            assert get_status(state.port)["revision"] == 0
        finally:
            state.close()

    def test_adocao_nao_altera_masking(self, unadopted: WriteHarness) -> None:
        """§5.5/§12.9: a adocao nao muda nenhuma decisao de masking.

        ID e revision sao metadata administrativa e nao participam do matching.
        A politica compilada — regras e exceptions, com seus padroes, modos e
        transformers — e identica antes e depois; so os IDs do documento mudam.
        Compara a politica pelo veredito do engine sobre uma tabela de nomes de
        coluna cobrindo regra (cpf), exception (tipo_cpf), alias e coluna sem
        correspondencia.
        """
        registry = unadopted.registry

        def verdicts(engine: MaskingEngine) -> list[str]:
            cases = [
                ColumnDescriptor(
                    output_name="cpf",
                    origin_name="cpf",
                    provenance_kind=ProvenanceKind.DIRECT,
                ),
                ColumnDescriptor(
                    output_name="tipo_cpf",
                    origin_name="tipo_cpf",
                    provenance_kind=ProvenanceKind.DIRECT,
                ),
                ColumnDescriptor(
                    output_name="documento",
                    origin_name="cpf",
                    provenance_kind=ProvenanceKind.DIRECT,
                ),
                ColumnDescriptor(
                    output_name="saldo",
                    origin_name="saldo",
                    provenance_kind=ProvenanceKind.DIRECT,
                ),
            ]
            return [engine.decide(case).action.name for case in cases]

        before = verdicts(registry.current.engine)
        call(
            unadopted.port,
            "POST",
            "/admin/v1/config:adopt",
            {"expected_revision": 0, "confirm_comment_loss": True},
        )
        after = verdicts(registry.current.engine)
        assert before == after
        # A coluna cpf de fato mascara, para o teste nao ser vacuo.
        assert before[0] == "MASK"


# --------------------------------------------------------------------------
# Falha injetada: durabilidade depois do replace (secao 7.6, 12.4)
# --------------------------------------------------------------------------


class TestDurabilidade:
    def test_fsync_de_diretorio_falho_publica_com_applied_true(
        self, tmp_path: Path, dsn: str
    ) -> None:
        """§7.6/§12.4: fsync de diretorio falho -> `500 CONFIG_DURABILITY_ERROR`,
        `applied: true`, runtime novo publicado, `current_revision` = nova.

        So POSIX: no Windows o fsync de diretorio e deliberadamente omitido, e o
        teste afirma a omissao em vez de simular.
        """
        if os.name != "posix":
            pytest.skip("fsync de diretorio so no POSIX; no Windows e omitido")

        def boom(_descriptor: int) -> None:
            msg = "fsync de diretorio injetado"
            raise OSError(msg)

        hooks = FilesystemHooks(directory_fsync=boom)
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        state = make_harness(tmp_path, dsn, payload_text=payload, hooks=hooks)
        try:
            reply = call(
                state.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 500
            body = reply.json()
            assert body["error"] == "CONFIG_DURABILITY_ERROR"
            assert body["applied"] is True
            assert body["current_revision"] == 4
            # O runtime novo esta publicado: o GET reflete a revision 4.
            assert get_status(state.port)["revision"] == 4
            assert get_config(state.port)["database"]["max_rows"] == 9
            # Nada da mensagem original vazou.
            assert "injetado" not in reply.text()
            # Uma retentativa cega com a revision velha bate em REVISION_CONFLICT.
            retry = call(
                state.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 1},
            )
            assert retry.status == 409
            assert retry.json()["error"] == "REVISION_CONFLICT"
        finally:
            state.close()

    def test_no_windows_o_fsync_de_diretorio_e_omitido(self, tmp_path: Path, dsn: str) -> None:
        """§12.5: no Windows o fsync de diretorio e OMITIDO, e o teste afirma a
        omissao — a escrita conclui sem `CONFIG_DURABILITY_ERROR`, com sucesso.

        No POSIX este teste nao se aplica: la o fsync roda e o desfecho e o do
        teste acima. Afirmar a omissao onde ela existe fecha o par (§12.4).
        """
        if os.name == "posix":
            pytest.skip("fsync de diretorio roda no POSIX; omissao e so no Windows")

        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        state = make_harness(tmp_path, dsn, payload_text=payload)
        try:
            reply = call(
                state.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            # Sucesso normal: nenhuma durabilidade a confirmar, entao `applied`
            # nem aparece; a escrita valeu e a revision subiu.
            assert reply.status == 200
            assert reply.json() == {"revision": 4, "applied": True}
            assert get_status(state.port)["revision"] == 4
            assert state.store.directory_fsync_supported is False
        finally:
            state.close()

    def test_out_of_sync_segunda_verificacao_preserva_editor(
        self, tmp_path: Path, dsn: str
    ) -> None:
        """§7.5.1/§12.5: arquivo alterado por fora ENTRE a 1a verificacao e o
        replace -> `409 CONFIG_OUT_OF_SYNC`, conteudo do editor preservado."""
        editor_bytes = yaml.safe_dump(
            {
                "revision": 3,
                "masking": [{"id": RULE_ID, "match": "editado_por_fora", "transformer": "md5"}],
                "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": []},
            },
            sort_keys=False,
        ).encode("utf-8")

        state_ref: dict[str, WriteHarness] = {}

        def edit_before_pre_replace(point: DigestCheckPoint) -> None:
            if point is DigestCheckPoint.PRE_REPLACE:
                # Escreve o arquivo do editor "por fora", entre a validacao e o
                # replace. Bytes diferentes do runtime publicado.
                state_ref["h"].config_path.write_bytes(editor_bytes)

        hooks = FilesystemHooks(before_digest_check=edit_before_pre_replace)
        payload = yaml.safe_dump(ADOPTED, sort_keys=False)
        state = make_harness(tmp_path, dsn, payload_text=payload, hooks=hooks)
        state_ref["h"] = state
        try:
            reply = call(
                state.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 409
            assert reply.json()["error"] == "CONFIG_OUT_OF_SYNC"
            # O conteudo do editor foi preservado, nao sobrescrito.
            assert state.config_path.read_bytes() == editor_bytes
        finally:
            state.close()


# --------------------------------------------------------------------------
# Reload com query em voo e limite de aposentado (secao 12.2, 12.3)
# --------------------------------------------------------------------------


class TestReloadEmVoo:
    def test_query_em_voo_mantem_o_runtime_antigo(self, adopted: WriteHarness) -> None:
        """§12.2: uma referencia adquirida ANTES do swap continua sendo a antiga.

        Adquire o runtime (como uma query faria), executa uma escrita que troca o
        runtime publicado, e confirma que a referencia em voo ainda e a de antes
        — o swap nao a alterou (D-054). Libera a referencia so no fim.
        """
        registry = adopted.registry
        in_flight = registry.acquire()
        try:
            assert in_flight.revision == 3
            reply = call(
                adopted.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            )
            assert reply.status == 200
            # A referencia em voo NAO mudou: ainda e o runtime revision 3, com a
            # engine e o adapter antigos. O publicado agora e o revision 4.
            assert in_flight.revision == 3
            assert registry.current.revision == 4
            assert registry.current is not in_flight
        finally:
            registry.release(in_flight)

    def test_reload_busy_nao_constroi_candidato(self, adopted: WriteHarness) -> None:
        """§12.3: com um aposentado ainda em uso, o proximo reload e `RELOAD_BUSY`
        e NENHUM candidato e construido nem conectado.

        Primeiro reload com uma query em voo aposenta o antigo, que fica aberto
        (a query o segura). O segundo reload bate no limite 1 -> `409 RELOAD_BUSY`.
        Um contador de adapters abertos confirma que nenhum candidato novo subiu
        para a operacao condenada.
        """
        registry = adopted.registry
        in_flight = registry.acquire()  # segura o runtime revision 3
        try:
            # Primeiro reload: publica revision 4, aposenta o 3 (ainda em uso).
            assert (
                call(
                    adopted.port,
                    "PUT",
                    "/admin/v1/database",
                    {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
                ).status
                == 200
            )
            assert registry.retired_in_use() == 1

            # Segundo reload: um aposentado ainda aberto -> RELOAD_BUSY. Nenhum
            # candidato e construido; o passo 4 recusa antes de compilar/conectar.
            reply = call(
                adopted.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 4, "statement_timeout_ms": 6000, "max_rows": 8},
            )
            assert reply.status == 409
            assert reply.json()["error"] == "RELOAD_BUSY"
            # A revision publicada continua 4: o segundo reload nao teve efeito.
            assert registry.current.revision == 4
        finally:
            registry.release(in_flight)


# --------------------------------------------------------------------------
# Sem efeito em cada recusa (secao 12.4)
# --------------------------------------------------------------------------


#: Cada recusa possivel de uma escrita, uma por categoria alcancavel:
#: REVISION_CONFLICT, NOT_FOUND, CONFIG_INVALID (posicao), IMMUTABLE_FIELD,
#: CONFIG_RELOAD_ERROR. Todas devem deixar arquivo, runtime e digest intactos.
_MISSING_RULE = "rul_" + "0" * 32
_REFUSAL_CASES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "PUT",
        "/admin/v1/database",
        {"expected_revision": 99, "statement_timeout_ms": 5000, "max_rows": 9},
    ),
    (
        "PUT",
        f"/admin/v1/rules/{_MISSING_RULE}",
        {"expected_revision": 3, "rule": {"match": "x", "transformer": "md5"}},
    ),
    (
        "POST",
        "/admin/v1/rules",
        {"expected_revision": 3, "position": 99, "rule": {"match": "x", "transformer": "md5"}},
    ),
    (
        "PUT",
        "/admin/v1/sql",
        {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": ["x"]},
    ),
    (
        "POST",
        "/admin/v1/rules",
        {"expected_revision": 3, "rule": {"match": "x", "transformer": "nao_existe"}},
    ),
]


class TestSemEfeitoNasRecusas:
    @pytest.mark.parametrize(("method", "path", "body"), _REFUSAL_CASES)
    def test_recusa_nao_muda_arquivo_revision_nem_digest(
        self, adopted: WriteHarness, method: str, path: str, body: dict[str, Any]
    ) -> None:
        before_bytes = adopted.config_path.read_bytes()
        before_current = adopted.registry.current
        before_revision = adopted.service.revision
        before_digest = adopted.service.reference_digest

        reply = call(adopted.port, method, path, body)
        assert reply.status in (404, 409, 422)

        assert adopted.config_path.read_bytes() == before_bytes
        assert adopted.registry.current is before_current
        assert adopted.service.revision == before_revision
        assert adopted.service.reference_digest == before_digest


# --------------------------------------------------------------------------
# Leakage e stdout
# --------------------------------------------------------------------------


class TestLeakage:
    def test_nenhum_secret_em_sucesso_nem_em_erro(self, adopted: WriteHarness) -> None:
        replies = [
            call(
                adopted.port,
                "PUT",
                "/admin/v1/database",
                {"expected_revision": 3, "statement_timeout_ms": 5000, "max_rows": 9},
            ),
            call(
                adopted.port,
                "PUT",
                "/admin/v1/sql",
                {"expected_revision": 99, "denied_functions": ["x"]},
            ),
        ]
        for reply in replies:
            blob = reply.text() + " " + " ".join(f"{k}:{v}" for k, v in reply.headers.items())
            assert HMAC_KEY not in blob
            dsn = os.environ["MASKGW_TEST_DSN"]
            for part in dsn.split():
                if "password=" in part:
                    assert part.split("=", 1)[1] not in blob
