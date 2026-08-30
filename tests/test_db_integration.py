"""Fase 2 contra PostgreSQL real.

Fecha os seis criterios de aceite da fase (docs/ROADMAP.md) contra um banco de
verdade, e nao apenas contra dublês.

O DSN vem exclusivamente de `MASKGW_TEST_DSN`. Sem ela, todo este arquivo da
SKIP limpo — nenhum usuario, senha ou host esta escrito aqui.

Todos os dados abaixo sao FICTICIOS.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from maskgw.config import load_config_text
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import DatabaseError, TransformerError
from maskgw.masking.descriptor import ProvenanceKind
from maskgw.masking.engine import Action, MaskingEngine
from tests.conftest import TEST_HMAC_KEY

pytestmark = pytest.mark.integration

SCHEMA = "maskgw_fase2"
TABLE = f"{SCHEMA}.cliente"
APP_NAME = "maskgw_fase2_tests"

CPF = "11122233344"
OTHER_CPF = "55566677788"
EMAIL = "joao.silva@empresa.com.br"
TELEFONE = "11987654321"
UID = UUID("2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42")
CRIADO_EM = dt.datetime(2026, 8, 29, 13, 45, 7, tzinfo=dt.UTC)
NASCIMENTO = dt.date(1985, 3, 17)
SALDO = Decimal("1234.50")
DADOS = {"origem": "web", "ativo": True}
ANEXO = b"conteudo binario ficticio"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
  - match: telefone
    transformer: fixed
    config:
      value: "[TELEFONE]"

exceptions:
  - match: tipo_cpf
    mode: exact
"""

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (
    id          integer PRIMARY KEY,
    nome        text,
    cpf         text,
    email       text,
    telefone    text,
    tipo_cpf    text,
    observacao  text,
    saldo       numeric(12,2),
    criado_em   timestamptz,
    nascimento  date,
    ativo       boolean,
    uid         uuid,
    dados       jsonb,
    anexo       bytea
);
CREATE VIEW {SCHEMA}.cliente_vw AS SELECT id, cpf, email FROM {TABLE};
CREATE VIEW {SCHEMA}.cliente_alias_vw AS SELECT id, cpf AS documento FROM {TABLE};
CREATE TABLE {SCHEMA}."Cliente Maiusculo" (id integer, "CPF" text);
"""

INSERT_MAIUSCULO = f'INSERT INTO {SCHEMA}."Cliente Maiusculo" VALUES (1, %s)'

INSERT = f"""
INSERT INTO {TABLE} VALUES
  (1, 'Maria Ficticia', %s, %s, %s, 'fisica', 'sem observacao',
   %s, %s, %s, true, %s, %s, %s),
  (2, 'Joao Ficticio', %s, NULL, NULL, 'juridica', NULL,
   NULL, NULL, NULL, NULL, NULL, NULL, NULL);
"""


def hmac_of(text: str) -> str:
    """HMAC esperado, calculado independentemente do codigo sob teste."""
    return hmac.new(TEST_HMAC_KEY.encode(), text.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    """Cria o schema de teste, popula e remove ao final. Devolve o DSN."""
    values = [
        CPF,
        EMAIL,
        TELEFONE,
        SALDO,
        CRIADO_EM,
        NASCIMENTO,
        UID,
        Jsonb(DADOS),
        ANEXO,
        OTHER_CPF,
    ]
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(DDL)
        setup.execute(INSERT, values)
        setup.execute(INSERT_MAIUSCULO, [CPF])
    yield dsn
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def app_dsn(database: str) -> str:
    """DSN com `application_name`, para localizar a sessao em pg_stat_activity."""
    return make_conninfo(database, application_name=APP_NAME)


@pytest.fixture
def engine(secrets):
    return MaskingEngine(load_config_text(CONFIG, secrets=secrets))


@pytest.fixture
def adapter(app_dsn, engine):
    with PostgresAdapter(app_dsn, engine) as built:
        yield built


@pytest.fixture
def control(database):
    """Conexao separada, para observar a sessao do adapter de fora."""
    with psycopg.connect(database, autocommit=True) as connection:
        yield connection


class TestAcceptanceCriteria:
    """Os seis criterios de aceite da Fase 2, contra banco real."""

    def test_select_cpf_returns_masked_value(self, adapter):
        result = adapter.execute(f"SELECT cpf FROM {TABLE} WHERE id = 1")
        assert result.rows == ((hmac_of(CPF),),)
        assert CPF not in str(result.rows)

    def test_select_star_masks_every_matching_column(self, adapter):
        result = adapter.execute(f"SELECT * FROM {TABLE} WHERE id = 1")
        row = dict(zip(result.column_names, result.rows[0], strict=True))
        assert row["cpf"] == hmac_of(CPF)
        assert row["email"] == "jo***@empresa.com.br"
        assert row["telefone"] == "[TELEFONE]"
        # Nao casam regra: passam em claro (default ALLOW).
        assert row["nome"] == "Maria Ficticia"
        assert row["id"] == 1
        # Exception tem prioridade sobre a regra `cpf`.
        assert row["tipo_cpf"] == "fisica"

    def test_distinct_transformers_per_column(self, adapter):
        result = adapter.execute(f"SELECT cpf, email FROM {TABLE} WHERE id = 1")
        assert result.rows[0][0] == hmac_of(CPF)
        assert result.rows[0][1] == "jo***@empresa.com.br"
        assert result.decisions[0].transformer_name == "hmac_sha256"
        assert result.decisions[1].transformer_name == "regex"

    def test_null_from_the_database_stays_null(self, adapter):
        result = adapter.execute(
            f"SELECT email, telefone, observacao, saldo FROM {TABLE} WHERE id = 2"
        )
        assert result.rows == ((None, None, None, None),)

    def test_postgres_error_never_reaches_the_caller(self, adapter):
        """A mensagem do servidor carregaria o proprio CPF."""
        with pytest.raises(DatabaseError) as info:
            adapter.execute(f"SELECT cpf::integer FROM {TABLE} WHERE id = 1")
        message = str(info.value)
        assert CPF not in message
        assert "invalid input syntax" not in message
        assert info.value.__cause__ is None
        assert info.value.__context__ is None

    def test_no_log_records_during_a_real_query(self, adapter, caplog):
        with caplog.at_level(logging.DEBUG):
            adapter.execute(f"SELECT * FROM {TABLE}")
        assert caplog.records == []


class TestAliasProtection:
    """Criterio central da Fase 3, contra banco real.

    INVERTE `TestPhaseTwoAliasGap`, que na Fase 2 fixava este mesmo cenario
    passando em claro.
    """

    def test_alias_is_masked(self, adapter):
        result = adapter.execute(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1")
        assert result.rows == ((hmac_of(CPF),),)
        assert CPF not in str(result.rows)
        assert result.decisions[0].action is Action.MASK

    def test_alias_descriptor_carries_the_origin(self, adapter):
        column = adapter.execute(f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1").columns[0]
        assert column.output_name == "documento"
        assert column.origin_name == "cpf"
        assert column.origin_schema == SCHEMA
        assert column.origin_table == "cliente"
        assert column.provenance_kind is ProvenanceKind.DIRECT
        assert column.qualified_origin == f"{SCHEMA}.cliente.cpf"

    def test_alias_that_also_matches_by_name_is_masked(self, adapter):
        result = adapter.execute(f"SELECT cpf AS cpf_do_cliente FROM {TABLE} WHERE id = 1")
        assert result.rows == ((hmac_of(CPF),),)

    def test_alias_chosen_to_look_harmless(self, adapter):
        for alias in ("doc", "ni", "campo1", "x"):
            result = adapter.execute(f"SELECT cpf AS {alias} FROM {TABLE} WHERE id = 1")
            assert result.rows == ((hmac_of(CPF),),), alias

    def test_alias_inside_subquery_is_masked(self, adapter):
        query = f"SELECT d FROM (SELECT cpf AS d FROM {TABLE} WHERE id = 1) x"
        result = adapter.execute(query)
        assert result.rows == ((hmac_of(CPF),),)
        assert result.columns[0].origin_name == "cpf"

    def test_alias_inside_cte_is_masked(self, adapter):
        query = f"WITH x AS (SELECT cpf AS d FROM {TABLE} WHERE id = 1) SELECT d FROM x"
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_alias_over_join_is_masked(self, adapter):
        query = (
            f"SELECT a.cpf AS documento FROM {TABLE} a JOIN {TABLE} b ON a.id = b.id WHERE a.id = 1"
        )
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_alias_over_cast_is_masked(self, adapter):
        query = f"SELECT cpf::text AS documento FROM {TABLE} WHERE id = 1"
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_alias_over_view_is_masked(self, adapter):
        query = f"SELECT cpf AS documento FROM {SCHEMA}.cliente_vw WHERE id = 1"
        result = adapter.execute(query)
        assert result.rows == ((hmac_of(CPF),),)
        assert result.columns[0].provenance_kind is ProvenanceKind.VIEW

    def test_alias_cannot_create_an_exception(self, adapter):
        """Fase 6.1 (D-042): o alias nao converte coluna sensivel em excecao."""
        query = f"SELECT cpf AS tipo_cpf FROM {TABLE} WHERE id = 1"
        result = adapter.execute(query)
        assert result.rows == ((hmac_of(CPF),),)
        assert result.decisions[0].action is Action.MASK

    def test_exception_still_applies_to_its_own_column(self, adapter):
        query = f"SELECT tipo_cpf FROM {TABLE} WHERE id = 1"
        result = adapter.execute(query)
        assert result.rows == (("fisica",),)
        assert result.decisions[0].action is Action.EXCEPTION


class TestProvenanceByScenario:
    """Cada cenario medido em test_pgresult_metadata, agora ponta a ponta."""

    def test_direct_column(self, adapter):
        column = adapter.execute(f"SELECT cpf FROM {TABLE}").columns[0]
        assert (column.origin_name, column.provenance_kind) == ("cpf", ProvenanceKind.DIRECT)

    def test_select_star_resolves_each_column(self, adapter):
        result = adapter.execute(f"SELECT * FROM {TABLE} WHERE id = 1")
        origins = dict(zip(result.column_names, result.columns, strict=True))
        assert origins["cpf"].origin_name == "cpf"
        assert origins["nome"].origin_name == "nome"
        assert all(column.origin_table == "cliente" for column in result.columns)
        assert all(column.provenance_kind is ProvenanceKind.DIRECT for column in result.columns)

    def test_join_keeps_one_origin_per_position(self, adapter):
        query = (
            f"SELECT c.cpf, c.nome FROM {TABLE} c "
            f"JOIN {SCHEMA}.cliente_vw v ON v.id = c.id WHERE c.id = 1"
        )
        result = adapter.execute(query)
        assert [column.origin_name for column in result.columns] == ["cpf", "nome"]

    def test_duplicate_names_keep_distinct_origins(self, adapter):
        query = (
            f"SELECT c.id, v.id FROM {TABLE} c "
            f"JOIN {SCHEMA}.cliente_vw v ON v.id = c.id WHERE c.id = 1"
        )
        result = adapter.execute(query)
        assert result.column_names == ("id", "id")
        assert [column.origin_table for column in result.columns] == ["cliente", "cliente_vw"]
        assert [column.provenance_kind for column in result.columns] == [
            ProvenanceKind.DIRECT,
            ProvenanceKind.VIEW,
        ]

    def test_subquery(self, adapter):
        query = f"SELECT cpf FROM (SELECT cpf FROM {TABLE}) x"
        assert adapter.execute(query).columns[0].origin_name == "cpf"

    def test_cte(self, adapter):
        query = f"WITH x AS (SELECT cpf FROM {TABLE}) SELECT cpf FROM x"
        assert adapter.execute(query).columns[0].origin_name == "cpf"

    def test_cast(self, adapter):
        column = adapter.execute(f"SELECT cpf::text FROM {TABLE}").columns[0]
        assert column.origin_name == "cpf"
        assert column.provenance_kind is ProvenanceKind.DIRECT

    def test_view_points_to_the_view_not_the_base_table(self, adapter):
        """Decisao da fase: sem lineage recursivo. Ver D-022."""
        column = adapter.execute(f"SELECT cpf FROM {SCHEMA}.cliente_vw").columns[0]
        assert column.origin_name == "cpf"
        assert column.origin_table == "cliente_vw"
        assert column.origin_schema == SCHEMA
        assert column.provenance_kind is ProvenanceKind.VIEW

    def test_view_that_renames_reports_the_view_column(self, adapter):
        """Limitacao conhecida: a view apaga o nome original nesta camada."""
        query = f"SELECT documento FROM {SCHEMA}.cliente_alias_vw WHERE id = 1"
        result = adapter.execute(query)
        assert result.columns[0].origin_name == "documento"
        assert result.columns[0].provenance_kind is ProvenanceKind.VIEW
        assert result.rows == ((CPF,),), "limitacao documentada em FUTURE-HARDENING"

    def test_union_has_no_provenance(self, adapter):
        query = (
            f"SELECT cpf FROM {TABLE} WHERE id = 1 UNION ALL SELECT cpf FROM {TABLE} WHERE id = 2"
        )
        result = adapter.execute(query)
        assert result.columns[0].origin_name is None
        assert result.columns[0].provenance_kind is ProvenanceKind.DERIVED
        # `output_name` ainda casa a regra: o valor continua mascarado.
        assert set(result.rows) == {(hmac_of(CPF),), (hmac_of(OTHER_CPF),)}

    def test_union_with_alias_is_the_residual_bypass(self, adapter):
        """Sem nome e sem origem, o default ALLOW deixa passar. Documentado."""
        query = (
            f"SELECT cpf AS documento FROM {TABLE} WHERE id = 1 "
            f"UNION ALL SELECT cpf FROM {TABLE} WHERE id = 2"
        )
        result = adapter.execute(query)
        assert result.columns[0].provenance_kind is ProvenanceKind.DERIVED
        assert (CPF,) in result.rows

    def test_expression_has_no_provenance(self, adapter):
        query = f"SELECT substr(cpf, 1, 3) AS x FROM {TABLE} WHERE id = 1"
        result = adapter.execute(query)
        assert result.columns[0].origin_name is None
        assert result.columns[0].provenance_kind is ProvenanceKind.DERIVED
        assert result.decisions[0].action is Action.ALLOW

    def test_literal_has_no_provenance(self, adapter):
        column = adapter.execute("SELECT 'x' AS documento").columns[0]
        assert column.origin_name is None
        assert column.provenance_kind is ProvenanceKind.DERIVED

    def test_null_does_not_affect_provenance(self, adapter):
        """Proveniencia vem da metadata, nunca do conteudo das linhas."""
        result = adapter.execute(f"SELECT email AS x FROM {TABLE} WHERE id = 2")
        assert result.rows == ((None,),)
        assert result.columns[0].origin_name == "email"

    def test_provenance_is_the_same_with_zero_rows(self, adapter):
        result = adapter.execute(f"SELECT cpf AS documento FROM {TABLE} WHERE false")
        assert result.rows == ()
        assert result.columns[0].origin_name == "cpf"

    def test_quoted_uppercase_identifiers(self, adapter):
        query = f'SELECT "CPF" AS "Documento" FROM {SCHEMA}."Cliente Maiusculo"'
        result = adapter.execute(query)
        assert result.columns[0].output_name == "Documento"
        assert result.columns[0].origin_name == "CPF"
        assert result.columns[0].origin_table == "Cliente Maiusculo"
        # Matching e case-insensitive: `CPF` casa a regra `cpf`.
        assert result.rows == ((hmac_of(CPF),),)

    def test_system_column_resolves(self, adapter):
        column = adapter.execute(f"SELECT ctid FROM {TABLE}").columns[0]
        assert column.origin_name == "ctid"
        assert column.provenance_kind is ProvenanceKind.DIRECT


class TestProvenanceCache:
    """Resolver uma vez por coluna, nunca por linha (D-021)."""

    def test_many_rows_do_not_multiply_the_lookups(self, app_dsn, engine):
        with PostgresAdapter(app_dsn, engine) as adapter:
            adapter.execute(
                f"SELECT cpf AS documento FROM {TABLE} CROSS JOIN generate_series(1, 200) AS s"
            )
            assert adapter._provenance is not None
            assert adapter._provenance.cache_size == 1

    def test_repeated_queries_reuse_the_cache(self, app_dsn, engine):
        with PostgresAdapter(app_dsn, engine) as adapter:
            for _ in range(5):
                adapter.execute(f"SELECT cpf AS documento FROM {TABLE}")
            assert adapter._provenance is not None
            assert adapter._provenance.cache_size == 1

    def test_select_star_caches_one_entry_per_column(self, app_dsn, engine):
        with PostgresAdapter(app_dsn, engine) as adapter:
            result = adapter.execute(f"SELECT * FROM {TABLE}")
            assert adapter._provenance is not None
            assert adapter._provenance.cache_size == len(result.columns)

    def test_derived_columns_do_not_enter_the_cache(self, app_dsn, engine):
        with PostgresAdapter(app_dsn, engine) as adapter:
            adapter.execute("SELECT 1 AS um, 'x' AS dois")
            assert adapter._provenance is not None
            assert adapter._provenance.cache_size == 0


class TestBypassAttempts:
    """Cenarios de docs/THREAT-MODEL.md que a Fase 2 ja cobre por nome."""

    def test_join_keeps_masking(self, adapter):
        query = f"SELECT a.cpf FROM {TABLE} a JOIN {TABLE} b ON a.id = b.id WHERE a.id = 1"
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_subquery_keeps_masking(self, adapter):
        query = f"SELECT cpf FROM (SELECT cpf FROM {TABLE} WHERE id = 1) x"
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_cte_keeps_masking(self, adapter):
        query = f"WITH x AS (SELECT cpf FROM {TABLE} WHERE id = 1) SELECT cpf FROM x"
        assert adapter.execute(query).rows == ((hmac_of(CPF),),)

    def test_union_keeps_masking(self, adapter):
        query = (
            f"SELECT cpf FROM {TABLE} WHERE id = 1 UNION ALL SELECT cpf FROM {TABLE} WHERE id = 2"
        )
        assert set(adapter.execute(query).rows) == {(hmac_of(CPF),), (hmac_of(OTHER_CPF),)}

    def test_view_keeps_masking(self, adapter):
        result = adapter.execute(f"SELECT * FROM {SCHEMA}.cliente_vw WHERE id = 1")
        assert result.rows[0][1] == hmac_of(CPF)

    @pytest.mark.parametrize("alias", ["CPF", "Cpf", "cPf", "num_cpf", "cpf_cliente", "nr_cpf"])
    def test_case_and_affixes_still_match(self, adapter, alias):
        result = adapter.execute(f'SELECT cpf AS "{alias}" FROM {TABLE} WHERE id = 1')
        assert result.rows == ((hmac_of(CPF),),)

    def test_expression_without_alias_uses_the_default_name(self, adapter):
        """`md5(cpf)` recebe o nome default `md5`, que nao casa regra."""
        result = adapter.execute(f"SELECT md5(cpf) FROM {TABLE} WHERE id = 1")
        assert result.column_names == ("md5",)
        assert result.decisions[0].action is Action.ALLOW


class TestTypes:
    """Coluna sem transformacao preserva o objeto Python do psycopg."""

    def test_unmatched_columns_keep_their_types(self, adapter):
        result = adapter.execute(
            f"SELECT id, saldo, criado_em, nascimento, ativo, uid, dados, anexo, nome "
            f"FROM {TABLE} WHERE id = 1"
        )
        row = result.rows[0]
        assert row[0] == 1 and isinstance(row[0], int)
        assert row[1] == SALDO and isinstance(row[1], Decimal)
        assert row[2] == CRIADO_EM and isinstance(row[2], dt.datetime)
        assert row[3] == NASCIMENTO and isinstance(row[3], dt.date)
        assert row[4] is True
        assert row[5] == UID and isinstance(row[5], UUID)
        assert row[6] == DADOS and isinstance(row[6], dict)
        assert row[7] == ANEXO and isinstance(row[7], bytes)
        assert row[8] == "Maria Ficticia" and isinstance(row[8], str)

    @pytest.mark.parametrize(
        ("column", "canonical"),
        [
            ("saldo", "1234.50"),
            ("criado_em", "2026-08-29T13:45:07+00:00"),
            ("nascimento", "1985-03-17"),
            ("ativo", "true"),
            ("uid", "2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42"),
            ("dados", '{"ativo":true,"origem":"web"}'),
            ("id", "1"),
        ],
    )
    def test_masked_columns_use_the_canonical_form(self, adapter, column, canonical):
        """Aliased para um nome que casa a regra `cpf`, forcando transformacao."""
        result = adapter.execute(f"SELECT {column} AS cpf_x FROM {TABLE} WHERE id = 1")
        assert result.rows == ((hmac_of(canonical),),)

    def test_bytea_is_masked_deterministically(self, adapter):
        """`str(memoryview)` embutiria um endereco de memoria."""
        query = f"SELECT anexo AS cpf_anexo FROM {TABLE} WHERE id = 1"
        first = adapter.execute(query).rows[0][0]
        second = adapter.execute(query).rows[0][0]
        assert first == second
        assert "memory at" not in first
        assert "0x" not in first

    def test_unsupported_type_fails_closed(self, adapter):
        """`interval` vira `timedelta`, que nao tem forma canonica definida."""
        with pytest.raises(TransformerError, match="tipo nao suportado"):
            adapter.execute("SELECT interval '1 day' AS cpf_intervalo")

    def test_timezone_aware_timestamp_is_deterministic(self, adapter):
        query = f"SELECT criado_em AS cpf_data FROM {TABLE} WHERE id = 1"
        assert adapter.execute(query).rows == adapter.execute(query).rows


class TestResultShape:
    def test_duplicate_column_names_are_not_collapsed(self, adapter):
        result = adapter.execute(f"SELECT cpf, cpf FROM {TABLE} WHERE id = 1")
        assert result.column_names == ("cpf", "cpf")
        assert result.rows == ((hmac_of(CPF), hmac_of(CPF)),)

    def test_select_star_on_a_self_join_repeats_names(self, adapter):
        query = f"SELECT a.id, b.id FROM {TABLE} a JOIN {TABLE} b ON a.id = b.id WHERE a.id = 1"
        result = adapter.execute(query)
        assert result.column_names == ("id", "id")
        assert result.rows == ((1, 1),)

    def test_empty_result_set(self, adapter):
        result = adapter.execute(f"SELECT cpf, email FROM {TABLE} WHERE false")
        assert result.rows == ()
        assert result.column_names == ("cpf", "email")

    def test_unicode_survives_the_round_trip(self, adapter):
        result = adapter.execute("SELECT 'coração ção 日本'::text AS nome")
        assert result.rows == (("coração ção 日本",),)

    def test_unicode_is_masked_deterministically(self, adapter):
        result = adapter.execute("SELECT 'coração'::text AS cpf_u")
        assert result.rows == ((hmac_of("coração"),),)

    def test_empty_string_is_not_null(self, adapter):
        result = adapter.execute("SELECT ''::text AS cpf_vazio")
        assert result.rows[0][0] == hmac_of("")
        assert result.rows[0][0] is not None


class TestBatching:
    def test_more_rows_than_the_batch_size(self, app_dsn, engine):
        with PostgresAdapter(app_dsn, engine, batch_size=7) as adapter:
            result = adapter.execute(
                "SELECT lpad(i::text, 11, '0') AS cpf FROM generate_series(1, 50) AS i"
            )
        assert result.row_count == 50
        assert result.rows[0] == (hmac_of("00000000001"),)
        assert result.rows[-1] == (hmac_of("00000000050"),)

    def test_batch_size_does_not_change_the_output(self, app_dsn, engine):
        query = "SELECT lpad(i::text, 11, '0') AS cpf FROM generate_series(1, 20) AS i"
        with PostgresAdapter(app_dsn, engine, batch_size=1) as small:
            first = small.execute(query).rows
        with PostgresAdapter(app_dsn, engine, batch_size=1000) as big:
            second = big.execute(query).rows
        assert first == second


class TestTransactionState:
    """A sessao nunca pode ficar `idle in transaction` (D-016)."""

    def session_state(self, control: psycopg.Connection[tuple[Any, ...]]) -> str | None:
        row = control.execute(
            "SELECT state FROM pg_stat_activity WHERE application_name = %s",
            [APP_NAME],
        ).fetchone()
        return None if row is None else row[0]

    def test_idle_after_a_successful_query(self, adapter, control):
        adapter.execute(f"SELECT cpf FROM {TABLE}")
        assert self.session_state(control) == "idle"

    def test_idle_after_a_failed_query(self, adapter, control):
        with pytest.raises(DatabaseError):
            adapter.execute(f"SELECT cpf::integer FROM {TABLE} WHERE id = 1")
        assert self.session_state(control) == "idle"

    def test_the_connection_is_still_usable_after_an_error(self, adapter):
        with pytest.raises(DatabaseError):
            adapter.execute("SELECT * FROM tabela_que_nao_existe")
        assert adapter.execute(f"SELECT cpf FROM {TABLE} WHERE id = 1").rows == ((hmac_of(CPF),),)

    def test_idle_after_a_canonicalization_failure(self, adapter, control):
        with pytest.raises(TransformerError):
            adapter.execute("SELECT interval '1 day' AS cpf_intervalo")
        assert self.session_state(control) == "idle"

    def test_close_ends_the_session(self, app_dsn, engine, control):
        adapter = PostgresAdapter(app_dsn, engine)
        adapter.connect()
        adapter.execute("SELECT 1 AS um")
        adapter.close()
        assert self.session_state(control) is None


class TestSanitizedErrors:
    @pytest.mark.parametrize(
        ("query", "leaked"),
        [
            (f"SELECT cpf::integer FROM {TABLE} WHERE id = 1", CPF),
            ("SELECT 'segredo-ficticio'::integer AS x", "segredo-ficticio"),
            ("SELECT 1/0 AS x", "division"),
            ("SELECT * FROM tabela_que_nao_existe", "tabela_que_nao_existe"),
            ("SELECT FROM WHERE", "syntax"),
        ],
    )
    def test_nothing_from_the_server_reaches_the_caller(self, adapter, query, leaked):
        with pytest.raises(DatabaseError) as info:
            adapter.execute(query)
        assert leaked not in str(info.value)

    def test_error_does_not_leak_through_logs(self, adapter, caplog):
        with caplog.at_level(logging.DEBUG), pytest.raises(DatabaseError):
            adapter.execute(f"SELECT cpf::integer FROM {TABLE} WHERE id = 1")
        assert all(CPF not in record.getMessage() for record in caplog.records)

    def test_connect_failure_leaks_no_credentials(self, dsn, engine):
        """Mesmo DSN real, porta errada: a falha nao pode citar a credencial."""
        unreachable = make_conninfo(dsn, port=1, connect_timeout=2)
        with pytest.raises(DatabaseError) as info:
            PostgresAdapter(unreachable, engine).connect()

        message = str(info.value)
        settings = conninfo_to_dict(dsn)
        for field in ("password", "user", "host", "dbname"):
            value = settings.get(field)
            if value:
                assert str(value) not in message, field
