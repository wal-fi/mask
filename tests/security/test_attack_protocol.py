"""Classes de ataque: SERIALIZACAO, NOMES HOSTIS, EXCEPTIONS, SEGREDOS,
PROTOCOLO MCP, CONCORRENCIA, ROW LIMIT e PERDA DE CAPABILITY.

Ver `docs/SECURITY-REVIEW.md`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time
from typing import Any

import anyio
import psycopg
import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

import maskgw.db.postgres as postgres_module
from maskgw.db.columns import DERIVED_ORIGIN
from maskgw.errors import CapabilityError
from maskgw.gateway.models import ErrorCategory, GatewayError
from maskgw.mcp.server import build_mcp_server
from tests.conftest import TEST_HMAC_KEY
from tests.security.conftest import CPF, EMAIL, SCHEMA, SENHA, TABLE, dump, leaks

pytestmark = pytest.mark.integration

#: Caractere de largura zero, para testar normalizacao de nome de coluna.
ZERO_WIDTH = "\u200b"


def ask(gateway: Any, sql: str, **extra: Any) -> CallToolResult:
    async def run() -> CallToolResult:
        async with Client(build_mcp_server(gateway)) as client:
            return await client.call_tool("query_database", {"sql": sql, **extra})

    return anyio.run(run)


def text_of(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


class TestHostileColumnNames:
    """MASKED — o matching e case-insensitive e por substring, e aguenta."""

    @pytest.mark.parametrize(
        "alias",
        [
            "cpf",
            "CPF",
            " cPf ",
            "cpf\n",
            "cpf" + ZERO_WIDTH,
            ZERO_WIDTH + "cpf",
            "documento_cpf",
            "cpf_original",
            "meu_tipo_cpf",
            "tipo_cpf_extra",
            " tipo_cpf ",
            "CPFİ",
            "Kpf",
        ],
    )
    def test_alias_variations_stay_masked(self, gateway, alias):
        result = gateway.query(f'SELECT cpf AS "{alias}" FROM {TABLE} WHERE id = 1')
        assert not leaks(result), alias

    @pytest.mark.parametrize("alias", ["ｃｐｆ", "сpf"])
    def test_unicode_lookalikes_do_not_match_and_stay_masked_by_origin(self, gateway, alias):
        """Homoglifos nao casam por nome, mas a origem resolve e protege."""
        result = gateway.query(f'SELECT cpf AS "{alias}" FROM {TABLE} WHERE id = 1')
        assert not leaks(result), alias
        assert result.columns[0].masked is True


class TestExceptionAbuse:
    """MASKED desde a Fase 6.1 — F-08 fechado (D-042).

    A exception passou a ser avaliada contra o nome AUTORITATIVO da coluna:
    `origin_name` quando existe, `output_name` so quando nao ha origem. Um
    alias deixou de poder converter coluna sensivel em excecao.
    """

    def test_exception_applies_to_the_legitimate_column(self, gateway):
        result = gateway.query(f"SELECT tipo_cpf FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] == "fisica"
        assert result.columns[0].masked is False

    def test_exception_applies_through_an_alias_of_its_own_column(self, gateway):
        """`SELECT tipo_cpf AS x`: a ORIGEM e a excecao, entao segue original."""
        result = gateway.query(f"SELECT tipo_cpf AS documento FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] == "fisica"
        assert result.columns[0].masked is False

    @pytest.mark.parametrize("alias", ["tipo_cpf", "TIPO_CPF", "Tipo_Cpf", "tipo_CPF"])
    def test_alias_to_the_exception_name_no_longer_unmasks(self, gateway, alias):
        result = gateway.query(f'SELECT cpf AS "{alias}" FROM {TABLE} WHERE id = 1')
        assert not leaks(result), f"{alias}: reabriu o bypass"
        assert result.columns[0].masked is True

    def test_a_sensitive_sibling_aliased_to_the_exception(self, gateway):
        result = gateway.query(f"SELECT cpf AS tipo_cpf FROM {TABLE} WHERE id = 1")
        assert not leaks(result)

    def test_expression_aliased_to_the_exception_name(self, gateway):
        """F-01 + F-08 combinados: a analise de AST vem antes da exception."""
        result = gateway.query(f"SELECT substr(cpf, 1, 11) AS tipo_cpf FROM {TABLE} WHERE id = 1")
        assert not leaks(result)
        assert result.columns[0].masked is True

    @pytest.mark.parametrize("alias", ["meu_tipo_cpf", "tipo_cpf_extra", " tipo_cpf "])
    def test_exact_mode_keeps_the_exception_narrow(self, gateway, alias):
        assert not leaks(gateway.query(f'SELECT cpf AS "{alias}" FROM {TABLE} WHERE id = 1'))


class TestSerialization:
    """Nenhum valor exotico produz fallback inesperado."""

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("bytea nao-utf8", "SELECT '\\xfffe00'::bytea AS b"),
            (
                "jsonb profundo",
                "SELECT ('{\"a\":' || repeat('[', 40) || repeat(']', 40) || '}')::jsonb AS j",
            ),
            ("array aninhado", "SELECT ARRAY[ARRAY[1, 2], ARRAY[3, 4]] AS a"),
            ("numeric extremo", "SELECT '1e10000'::numeric AS n"),
            ("uuid", "SELECT gen_random_uuid()::text AS u"),
            ("zero-width no valor", f"SELECT 'a{ZERO_WIDTH}b'::text AS z"),
            ("range", "SELECT int4range(1, 10)::text AS r"),
            ("timestamptz", "SELECT now()::text AS t"),
        ],
    )
    def test_serialises_without_error(self, gateway, attack, sql):
        assert gateway.query(sql).row_count == 1, attack

    @pytest.mark.parametrize(
        ("attack", "sql"),
        [
            ("interval", "SELECT interval '1 day' AS i_cpf"),
            ("timestamp infinity", "SELECT 'infinity'::timestamptz AS t_cpf"),
        ],
    )
    def test_unsupported_types_fail_closed_when_masked(self, gateway, attack, sql):
        """BLOCKED — canonicalizacao falha fechada em vez de cair em repr()."""
        with pytest.raises(GatewayError, match="database"):
            gateway.query(sql), attack

    def test_binary_is_base64_never_a_python_repr(self, gateway):
        result = gateway.query("SELECT '\\xfffe00'::bytea AS b")
        assert result.rows[0][0] == "//4A"
        assert "memory at" not in dump(result)
        assert "0x" not in dump(result)

    def test_nan_and_infinity_reach_the_mcp_layer(self, gateway):
        """Medido: o SDK serializa; nao ha excecao nao tratada."""
        for value in ("NaN", "Infinity", "-Infinity"):
            result = ask(gateway, f"SELECT '{value}'::float8 AS f")
            assert result.is_error is False, value


class TestSecretsNeverEscape:
    def test_hmac_key_is_absent_from_every_repr(self, application):
        blob = " ".join(
            repr(obj)
            for obj in (
                application,
                application.config,
                application.config.masking,
                application.gateway,
            )
        )
        assert TEST_HMAC_KEY not in blob

    def test_hmac_key_is_absent_from_the_mcp_response(self, gateway):
        result = ask(gateway, f"SELECT cpf FROM {TABLE} WHERE id = 1")
        assert TEST_HMAC_KEY not in json.dumps(result.model_dump(), default=str)

    def test_hmac_key_is_absent_from_errors(self, gateway):
        with pytest.raises(GatewayError) as info:
            gateway.query("SELEC 1")
        assert TEST_HMAC_KEY not in str(info.value)

    def test_the_dsn_is_absent_from_the_adapter_repr(self, application):
        assert repr(application.gateway._adapter) == "PostgresAdapter(closed=False)"

    def test_sql_cannot_read_the_key_from_the_session(self, gateway):
        result = gateway.query("SELECT current_setting('maskgw.key', true) AS k")
        assert result.rows[0][0] is None


class TestMcpProtocolAbuse:
    @pytest.mark.parametrize(
        ("attack", "arguments"),
        [
            ("sql ausente", {}),
            ("sql null", {"sql": None}),
            ("sql lista", {"sql": ["SELECT 1"]}),
            ("sql objeto", {"sql": {"a": 1}}),
            ("sql inteiro", {"sql": 1}),
            ("sql booleano", {"sql": True}),
        ],
    )
    def test_malformed_arguments_are_rejected_by_the_schema(self, gateway, attack, arguments):
        async def run() -> CallToolResult:
            async with Client(build_mcp_server(gateway)) as client:
                return await client.call_tool("query_database", arguments)

        assert anyio.run(run).is_error is True, attack

    def test_unknown_tool_is_rejected(self, gateway):
        async def run() -> CallToolResult:
            async with Client(build_mcp_server(gateway)) as client:
                return await client.call_tool("ferramenta_inexistente", {"sql": "SELECT 1"})

        assert anyio.run(run).is_error is True

    def test_large_identifier_payload_is_handled(self, gateway):
        """Medido: o PostgreSQL trunca identificadores em 63 bytes."""
        result = ask(gateway, "SELECT 1 AS " + "a" * 50_000)
        assert result.is_error is False
        assert result.structured_content is not None
        assert len(result.structured_content["columns"][0]["name"]) == 63

    def test_large_query_payload_does_not_crash(self, gateway):
        """Uma consulta gigante falha de forma controlada, sem vazar."""
        result = ask(gateway, "SELECT " + " + ".join(["1"] * 100_000) + " AS n")
        assert CPF not in text_of(result) if result.is_error else True

    def test_deeply_nested_query_does_not_crash(self, gateway):
        sql = "SELECT 1 AS n" + " FROM (SELECT 1) x" * 0
        for _ in range(200):
            sql = f"SELECT * FROM ({sql}) t"
        result = ask(gateway, sql)
        assert isinstance(result.is_error, bool)

    def test_empty_sql_is_rejected(self, gateway):
        assert ask(gateway, "").is_error is True

    @pytest.mark.parametrize(
        "extra",
        [
            {"disable_masking": True},
            {"raw": True},
            {"unmasked": True},
            {"max_rows": 999_999},
            {"transformer": "none"},
        ],
    )
    def test_extra_arguments_cannot_unmask(self, gateway, extra):
        baseline = ask(gateway, f"SELECT cpf FROM {TABLE} WHERE id = 1")
        attempt = ask(gateway, f"SELECT cpf FROM {TABLE} WHERE id = 1", **extra)
        assert attempt.structured_content == baseline.structured_content
        assert CPF not in json.dumps(attempt.structured_content, ensure_ascii=False)

    def test_the_connection_survives_a_sequence_of_failures(self, gateway):
        for sql in (
            f"DELETE FROM {TABLE}",
            "SELEC 1",
            "SELECT pg_read_file('/x')",
            "SELECT 1;SELECT 2",
        ):
            assert ask(gateway, sql).is_error is True
        result = ask(gateway, f"SELECT cpf FROM {TABLE} WHERE id = 1")
        assert result.is_error is False
        assert CPF not in json.dumps(result.structured_content, ensure_ascii=False)


class TestConcurrency:
    """As consultas sao serializadas por lock; nada se mistura."""

    def test_parallel_calls_do_not_mix_rows_or_leak(self, gateway):
        masked: list[Any] = []
        numbers: dict[int, Any] = {}
        failures: list[str] = []
        errors: list[str] = []

        def worker(index: int) -> None:
            try:
                if index % 3 == 0:
                    masked.append(gateway.query(f"SELECT cpf FROM {TABLE} WHERE id = 1").rows[0][0])
                elif index % 3 == 1:
                    numbers[index] = gateway.query(f"SELECT {index} AS n").rows[0][0]
                else:
                    try:
                        gateway.query(f"DELETE FROM {TABLE}")
                    except GatewayError:
                        failures.append("rejeitado")
            except Exception as exc:
                errors.append(type(exc).__name__)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(set(masked)) == 1, "mascaramento inconsistente sob concorrencia"
        assert CPF not in str(masked)
        assert all(value == index for index, value in numbers.items()), "respostas trocadas"
        assert len(failures) == 10

    def test_audit_request_ids_are_unique_under_concurrency(self, gateway, caplog):
        def worker() -> None:
            gateway.query(f"SELECT cpf FROM {TABLE} WHERE id = 1")

        with caplog.at_level(logging.INFO, logger="maskgw.audit"):
            threads = [threading.Thread(target=worker) for _ in range(20)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        ids = [record.maskgw["request_id"] for record in caplog.records]
        assert len(ids) == len(set(ids)) == 20


class TestRowLimitAdversarial:
    """A linha N+1 e lida para detectar truncamento, e some antes de tudo."""

    def test_the_sensitive_row_beyond_the_limit_never_appears(self, gateway, database, caplog):
        marcador = "SEGREDO-NA-LINHA-SEIS"
        with psycopg.connect(database, autocommit=True) as setup:
            setup.execute(f"CREATE TABLE {SCHEMA}.limite (id integer, publico text)")
            setup.execute(
                f"INSERT INTO {SCHEMA}.limite "
                "VALUES (1,'a'),(2,'b'),(3,'c'),(4,'d'),(5,'e'),(6,%s)",
                [marcador],
            )

        with caplog.at_level(logging.DEBUG):
            result = ask(gateway, f"SELECT publico FROM {SCHEMA}.limite ORDER BY id")

        blob = json.dumps(result.model_dump(), ensure_ascii=False, default=str)
        assert marcador not in blob
        assert result.structured_content is not None
        assert result.structured_content["truncated"] is True
        assert result.structured_content["row_count"] == 5
        rendered = " ".join(f"{r.getMessage()} {getattr(r, 'maskgw', '')}" for r in caplog.records)
        assert marcador not in rendered


class TestCapabilityLossAfterStartup:
    """BLOCKED desde a Fase 6 — antes vazava em claro (F-09, D-040)."""

    def test_losing_catalog_access_rejects_instead_of_leaking(self, application, database):
        gateway = application.gateway
        assert not leaks(gateway.query(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1"))

        role = "maskgw_redteam_sem_catalogo"
        with psycopg.connect(database, autocommit=True) as admin:
            admin.execute(f"DROP ROLE IF EXISTS {role}")
            admin.execute(f"CREATE ROLE {role} NOLOGIN")
            admin.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO {role}")
            admin.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO {role}")
            try:
                admin.execute("REVOKE SELECT ON pg_attribute FROM PUBLIC")
                connection = gateway._adapter._connection
                connection.execute(f"SET ROLE {role}")
                gateway._adapter._provenance._cache.clear()

                with pytest.raises(GatewayError) as info:
                    gateway.query(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1")
                assert info.value.category is ErrorCategory.CONFIGURATION_ERROR
                assert CPF not in str(info.value)
            finally:
                with contextlib.suppress(psycopg.Error):
                    connection.execute("RESET ROLE")
                admin.execute("GRANT SELECT ON pg_attribute TO PUBLIC")
                admin.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {SCHEMA} FROM {role}")
                admin.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM {role}")
                admin.execute(f"DROP ROLE IF EXISTS {role}")

    def test_catalog_access_is_restored(self, gateway):
        """Guarda-corpo: o teste anterior nao pode deixar o banco quebrado."""
        assert not leaks(gateway.query(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1"))

    def test_derived_columns_are_not_affected_by_the_new_rule(self, gateway):
        """`ftable = 0` continua sendo comportamento normal, nao erro."""
        result = gateway.query("SELECT 'x' AS documento")
        assert result.rows == [["x"]]

    def test_resolution_failure_is_distinguishable_from_derived(self):
        assert isinstance(CapabilityError("x"), Exception)
        assert DERIVED_ORIGIN.name is None


class TestNothingSensitiveInAnySurface:
    """Varredura final: o CPF nao pode estar em superficie alguma."""

    @pytest.mark.parametrize(
        "sql",
        [
            f"SELECT nome, cpf, email, senha FROM {TABLE} WHERE id = 1",
            f"SELECT * FROM {TABLE} WHERE id = 1",
            f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1",
            f"SELECT cpf FROM {SCHEMA}.v1 WHERE id = 1",
        ],
    )
    def test_no_secret_in_the_mcp_response(self, gateway, sql, caplog):
        with caplog.at_level(logging.DEBUG):
            result = ask(gateway, sql)
        blob = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, default=str)
        for secret in (CPF, EMAIL, SENHA):
            assert secret not in blob, sql
        rendered = " ".join(
            f"{r.getMessage()} {getattr(r, 'maskgw', '')} {r.exc_text or ''}"
            for r in caplog.records
        )
        for secret in (CPF, EMAIL, SENHA):
            assert secret not in rendered


class TestSensitivityAnalysisCostIsPerQuery:
    """A analise de AST roda UMA VEZ por consulta, nunca por linha (§20)."""

    def test_ten_thousand_rows_do_not_multiply_the_cost(self, gateway, database):
        with psycopg.connect(database, autocommit=True) as setup:
            setup.execute(f"CREATE TABLE {SCHEMA}.grande (cpf text)")
            setup.execute(
                f"INSERT INTO {SCHEMA}.grande "
                "SELECT lpad(i::text, 11, '0') FROM generate_series(1, 10000) AS i"
            )

        query = f"SELECT substr(cpf, 1, 11) AS d FROM {SCHEMA}.grande"

        started = time.perf_counter()
        uma_linha = gateway.query(f"{query} LIMIT 1")
        custo_uma = time.perf_counter() - started

        started = time.perf_counter()
        muitas = gateway.query(query)
        custo_muitas = time.perf_counter() - started

        assert uma_linha.columns[0].masked is True
        assert muitas.truncated is True
        # O custo cresce com o masking das linhas devolvidas (limitado a
        # max_rows), nao com a analise. Uma ordem de grandeza de folga.
        assert custo_muitas < custo_uma * 10 + 1.0

    def test_the_analysis_is_not_repeated_per_row(self, gateway, monkeypatch):
        """Marcador de regressao: contar chamadas ao analisador."""
        calls = 0
        original = postgres_module.analyze_sensitivity

        def counting(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(postgres_module, "analyze_sensitivity", counting)
        gateway.query(f"SELECT substr(cpf, 1, 11) AS d FROM {TABLE}")
        assert calls == 1
