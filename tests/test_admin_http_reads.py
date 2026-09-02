"""Fase 7, Etapa 7: o conteudo das oito rotas de leitura (secao 1.1).

Duas propriedades atravessam o arquivo inteiro:

- **nenhum secret aparece**, em forma alguma — nem valor, nem tamanho, nem
  prefixo, nem hash (secao 11.1);
- **a resposta vem do modelo validado do arquivo**, e nao dos objetos runtime
  compilados (D-047), e **nao compartilha referencia mutavel** com o runtime
  publicado (D-055).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from maskgw.admin.http.views import (
    PG_NAMESPACE_DEFAULT,
    PIPELINE,
    UNMATCHED_POLICY,
    VALIDATOR_RULES,
)
from maskgw.errors import ConfigError
from maskgw.masking.transformers.registry import build_default_registry
from maskgw.secretsource import MappingSecretProvider
from maskgw.sql.policy import (
    DEFAULT_ALLOWED_PG_FUNCTIONS,
    DEFAULT_DENIED_FUNCTIONS,
    DEFAULT_DENIED_PREFIXES,
    DENIED_RELATIONS,
)
from tests.admin_http_support import (
    ADOPTED_DOCUMENT,
    EXCEPTION_ID,
    RULE_ID,
    SECOND_RULE_ID,
    SENSITIVE_DSN,
    SENSITIVE_HMAC,
    TOKEN,
    UNADOPTED_DOCUMENT,
    Harness,
    build_service,
    request,
)


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    state = build_service(tmp_path)
    state.start()
    try:
        yield state
    finally:
        state.close()


@pytest.fixture
def unadopted(tmp_path: Path) -> Iterator[Harness]:
    state = build_service(tmp_path, UNADOPTED_DOCUMENT)
    state.start()
    try:
        yield state
    finally:
        state.close()


def get(harness: Harness, path: str) -> Any:
    reply = request(harness.port, "GET", path)
    assert reply.status == 200, reply.text()
    return reply.json()


# --------------------------------------------------------------------------
# /status
# --------------------------------------------------------------------------


class TestStatus:
    def test_revision_estado_runtime_e_contadores(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/status")

        assert payload["revision"] == ADOPTED_DOCUMENT["revision"]
        assert payload["adopted"] is True
        assert payload["runtime"] == {"revision": 3, "retired_runtimes_open": 0}
        assert payload["counters"] == {"queries_total": 0, "admin_operations_total": 0}

    def test_o_contador_de_queries_acompanha_as_aquisicoes(self, harness: Harness) -> None:
        """Uma query adquire o runtime exatamente uma vez (D-054)."""
        for _ in range(3):
            with harness.registry.borrow():
                pass

        assert get(harness, "/admin/v1/status")["counters"]["queries_total"] == 3

    def test_aposentado_aberto_aparece_no_status(self, harness: Harness) -> None:
        published = harness.registry.current
        held = harness.registry.acquire()
        replacement = _clone_runtime(published)
        harness.registry.swap(replacement)
        try:
            payload = get(harness, "/admin/v1/status")
            assert payload["runtime"]["retired_runtimes_open"] == 1
        finally:
            harness.registry.release(held)

    def test_secrets_sao_apenas_configured_ou_missing(self, harness: Harness) -> None:
        secrets = get(harness, "/admin/v1/status")["secrets"]

        assert set(secrets) == {"hmac_sha256_key", "admin_token", "database_dsn"}
        assert set(secrets.values()) <= {"configured", "missing"}

    def test_secret_presente_e_configured_e_ausente_e_missing(self, tmp_path: Path) -> None:
        state = build_service(tmp_path)
        state.start(secret_values={"MASKGW_DATABASE_DSN": SENSITIVE_DSN})
        try:
            secrets = get(state, "/admin/v1/status")["secrets"]
            assert secrets["database_dsn"] == "configured"
            assert secrets["hmac_sha256_key"] == "missing"
            # Sem token o processo nao teria subido.
            assert secrets["admin_token"] == "configured"
        finally:
            state.close()

    def test_nenhum_valor_tamanho_prefixo_ou_hash_de_secret_aparece(self, harness: Harness) -> None:
        """Secao 11.1: nunca o valor, e nunca um derivado dele."""
        import hashlib

        raw = request(harness.port, "GET", "/admin/v1/status").text()

        for secret in (SENSITIVE_DSN, SENSITIVE_HMAC, TOKEN):
            assert secret not in raw
            assert secret[:8] not in raw
            assert secret[-8:] not in raw
            assert str(len(secret)) not in raw
            assert hashlib.sha256(secret.encode()).hexdigest() not in raw
            assert hashlib.md5(secret.encode(), usedforsecurity=False).hexdigest() not in raw

    def test_nao_existe_campo_de_data_de_secret(self, harness: Harness) -> None:
        secrets = get(harness, "/admin/v1/status")["secrets"]
        assert all(isinstance(value, str) for value in secrets.values())

    def test_status_de_configuracao_nao_adotada(self, unadopted: Harness) -> None:
        payload = get(unadopted, "/admin/v1/status")

        assert payload["revision"] == 0
        assert payload["adopted"] is False


def _clone_runtime(published: Any) -> Any:
    from maskgw.runtime import Runtime
    from tests.admin_http_support import FakeAdapter

    return Runtime(
        revision=published.revision + 1,
        file_config=published.file_config,
        config=published.config,
        engine=published.engine,
        adapter=FakeAdapter(),  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------
# /config
# --------------------------------------------------------------------------


class TestConfig:
    def test_documento_completo_e_revision(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/config")

        assert payload["revision"] == 3
        assert payload["adopted"] is True
        config = payload["config"]
        assert set(config) == {"revision", "masking", "exceptions", "database", "sql"}
        assert config["revision"] == 3
        assert len(config["masking"]) == 2
        assert len(config["exceptions"]) == 1

    def test_os_limites_de_execucao_sao_fieis_ao_arquivo(self, harness: Harness) -> None:
        database = get(harness, "/admin/v1/config")["config"]["database"]
        assert database == {"statement_timeout_ms": 2000, "max_rows": 10}

    def test_a_secao_sql_do_ARQUIVO_e_devolvida(self, harness: Harness) -> None:
        """`/config` mostra o que o arquivo DECLARA; `/protected`, o que vale."""
        sql = get(harness, "/admin/v1/config")["config"]["sql"]
        assert sql == {"allowed_pg_functions": ["pg_typeof"], "denied_functions": ["dblink_exec"]}

    def test_nao_existe_dsn_host_nem_credencial_no_documento(self, harness: Harness) -> None:
        raw = request(harness.port, "GET", "/admin/v1/config").text().lower()

        for forbidden in ("dsn", "password", "passwd", "host", "hmac_key", "secret", "token"):
            assert forbidden not in raw

    def test_a_resposta_nao_compartilha_referencia_com_o_runtime(self, harness: Harness) -> None:
        """`frozen=True` do Pydantic nao congela as listas de dentro (D-055)."""
        before = harness.registry.current.file_config
        document = harness.service.document

        document.masking.clear()
        document.exceptions.clear()
        document.sql.allowed_pg_functions.clear()

        assert len(before.masking) == 2
        assert len(before.exceptions) == 1
        assert before.sql.allowed_pg_functions == ["pg_typeof"]
        # E a resposta HTTP continua completa.
        assert len(get(harness, "/admin/v1/config")["config"]["masking"]) == 2

    def test_o_config_de_uma_regra_tambem_e_copia(self, harness: Harness) -> None:
        original = harness.registry.current.file_config.masking[1].config
        copia = harness.service.document.masking[1].config

        assert copia == original
        assert copia is not original
        copia["pattern"] = "destruido"
        assert original["pattern"] != "destruido"

    def test_configuracao_nao_adotada_continua_legivel(self, unadopted: Harness) -> None:
        """Secao 5.2: um arquivo sem `revision` e sem `id` carrega e e lido."""
        payload = get(unadopted, "/admin/v1/config")

        assert payload["adopted"] is False
        assert payload["revision"] == 0
        assert payload["config"]["masking"][0]["id"] is None
        assert payload["config"]["exceptions"][0]["id"] is None

    def test_ids_nao_sao_inventados_para_preencher_o_campo(self, unadopted: Harness) -> None:
        """Um ID instavel e pior que nenhum ID (secao 5.5)."""
        primeiro = get(unadopted, "/admin/v1/config")
        segundo = get(unadopted, "/admin/v1/config")

        assert primeiro == segundo
        assert all(rule["id"] is None for rule in primeiro["config"]["masking"])


# --------------------------------------------------------------------------
# /rules e /exceptions
# --------------------------------------------------------------------------


class TestRules:
    def test_ordem_do_arquivo_com_id_e_position(self, harness: Harness) -> None:
        rules = get(harness, "/admin/v1/rules")["rules"]

        assert [rule["id"] for rule in rules] == [RULE_ID, SECOND_RULE_ID]
        assert [rule["position"] for rule in rules] == [0, 1]
        assert [rule["match"] for rule in rules] == ["cpf", "email"]

    def test_position_e_derivado_e_nao_um_campo_do_arquivo(self, harness: Harness) -> None:
        config_rules = get(harness, "/admin/v1/config")["config"]["masking"]
        assert all("position" not in rule for rule in config_rules)

    def test_a_regra_traz_transformer_e_config(self, harness: Harness) -> None:
        rules = get(harness, "/admin/v1/rules")["rules"]

        assert rules[0]["transformer"] == "sha256"
        assert rules[0]["config"] == {}
        assert rules[1]["transformer"] == "regex"
        assert set(rules[1]["config"]) == {"pattern", "replacement"}

    def test_defaults_de_matching_aparecem_explicitos(self, harness: Harness) -> None:
        """`contains` e o default das REGRAS (D-045)."""
        rules = get(harness, "/admin/v1/rules")["rules"]
        assert rules[0]["mode"] == "contains"
        assert rules[0]["case_sensitive"] is False

    def test_uma_regra_por_id(self, harness: Harness) -> None:
        payload = get(harness, f"/admin/v1/rules/{RULE_ID}")

        assert payload["rule"]["id"] == RULE_ID
        assert payload["rule"]["position"] == 0
        assert payload["revision"] == 3

    @pytest.mark.parametrize(
        "rule_id",
        ["rul_" + "f" * 32, "nao-existe", "", "rul_", EXCEPTION_ID, "../config", "%2e%2e"],
    )
    def test_regra_inexistente_ou_malformada_e_not_found(
        self,
        harness: Harness,
        rule_id: str,
    ) -> None:
        """Distinguir "malformado" de "inexistente" seria um oraculo de formato."""
        reply = request(harness.port, "GET", f"/admin/v1/rules/{rule_id}")

        assert reply.status == 404
        assert reply.json() == {
            "error": "NOT_FOUND",
            "detail": "The requested resource does not exist.",
        }

    def test_o_404_nao_repete_o_id_pedido(self, harness: Harness) -> None:
        marcador = "rul_marcador-que-nao-pode-voltar"
        reply = request(harness.port, "GET", f"/admin/v1/rules/{marcador}")
        assert marcador not in reply.text()

    def test_sem_adocao_nenhuma_regra_e_alcancavel_por_id(self, unadopted: Harness) -> None:
        assert get(unadopted, "/admin/v1/rules")["rules"][0]["id"] is None
        assert request(unadopted.port, "GET", f"/admin/v1/rules/{RULE_ID}").status == 404


class TestExceptions:
    def test_exceptions_com_ids(self, harness: Harness) -> None:
        exceptions = get(harness, "/admin/v1/exceptions")["exceptions"]

        assert [item["id"] for item in exceptions] == [EXCEPTION_ID]
        assert exceptions[0]["match"] == "tipo_cpf"
        assert exceptions[0]["position"] == 0

    def test_o_default_de_mode_das_exceptions_e_exact(self, harness: Harness) -> None:
        """A assimetria com as regras e uma correcao de seguranca (D-045)."""
        exceptions = get(harness, "/admin/v1/exceptions")["exceptions"]
        assert exceptions[0]["mode"] == "exact"

    def test_exception_nao_tem_transformer(self, harness: Harness) -> None:
        exceptions = get(harness, "/admin/v1/exceptions")["exceptions"]
        assert "transformer" not in exceptions[0]
        assert "config" not in exceptions[0]

    def test_uma_exception_por_id(self, harness: Harness) -> None:
        payload = get(harness, f"/admin/v1/exceptions/{EXCEPTION_ID}")
        assert payload["exception"]["id"] == EXCEPTION_ID

    @pytest.mark.parametrize("exception_id", ["exc_" + "f" * 32, "nao-existe", RULE_ID])
    def test_exception_inexistente_e_NOT_FOUND(self, harness: Harness, exception_id: str) -> None:
        reply = request(harness.port, "GET", f"/admin/v1/exceptions/{exception_id}")

        assert reply.status == 404
        assert reply.json()["error"] == "NOT_FOUND"

    def test_id_de_regra_nao_alcanca_uma_exception(self, harness: Harness) -> None:
        """Prefixos distintos existem para que um ID nao aponte para o lugar errado."""
        assert request(harness.port, "GET", f"/admin/v1/exceptions/{RULE_ID}").status == 404
        assert request(harness.port, "GET", f"/admin/v1/rules/{EXCEPTION_ID}").status == 404


# --------------------------------------------------------------------------
# /transformers
# --------------------------------------------------------------------------


class TestTransformers:
    def test_o_catalogo_e_o_do_registry(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/transformers")
        names = [item["name"] for item in payload["transformers"]]

        assert names == list(build_default_registry().available())

    def test_somente_nome_e_parametros(self, harness: Harness) -> None:
        """Nenhum objeto, nenhum callable, nenhum secret."""
        for item in get(harness, "/admin/v1/transformers")["transformers"]:
            assert set(item) == {"name", "required_parameters", "optional_parameters"}
            assert all(isinstance(value, str) for value in item["required_parameters"])
            assert all(isinstance(value, str) for value in item["optional_parameters"])

    def test_os_parametros_declarados(self, harness: Harness) -> None:
        catalog = {
            item["name"]: (item["required_parameters"], item["optional_parameters"])
            for item in get(harness, "/admin/v1/transformers")["transformers"]
        }

        assert catalog["regex"] == (["pattern", "replacement"], [])
        assert catalog["random"] == (["strategy"], ["preserve_length", "length"])
        assert catalog["fixed"] == (["value"], [])
        assert catalog["truncate"] == (["length"], [])
        assert catalog["sha256"] == ([], [])

    def test_hmac_nao_declara_parametro_de_chave(self, harness: Harness) -> None:
        """A chave vem do ambiente; declarar `key` sugeriria o arquivo (D-006)."""
        catalog = {
            item["name"]: item for item in get(harness, "/admin/v1/transformers")["transformers"]
        }
        entry = catalog["hmac_sha256"]

        assert entry["required_parameters"] == []
        assert entry["optional_parameters"] == []
        assert "key" not in request(harness.port, "GET", "/admin/v1/transformers").text()

    def test_nenhum_valor_default_ou_exemplo_e_publicado(self, harness: Harness) -> None:
        raw = request(harness.port, "GET", "/admin/v1/transformers").text()
        for leaked in ("default", "example", "alphanumeric", "digits"):
            assert leaked not in raw


class TestCatalogMatchesBuilders:
    """O catalogo declarado precisa refletir o que os builders aceitam.

    Sem isto, a declaracao em `build_default_registry` viraria documentacao
    que envelhece em silencio: alguem acrescenta um parametro ao builder e o
    `GET /admin/v1/transformers` passa a mentir. Aqui o confronto e com o
    comportamento efetivo, chamando os builders de verdade.
    """

    VALID: dict[str, dict[str, Any]] = {
        "md5": {},
        "sha256": {},
        "sha512": {},
        "hmac_sha256": {},
        "regex": {"pattern": "a", "replacement": "b"},
        "random": {"strategy": "digits"},
        "fixed": {"value": "x"},
        "truncate": {"length": 3},
    }

    def secrets(self) -> MappingSecretProvider:
        return MappingSecretProvider({"MASKGW_HMAC_KEY": "k" * 32})

    def test_a_tabela_cobre_todo_transformer_registrado(self) -> None:
        assert set(self.VALID) == set(build_default_registry().available())

    def test_os_parametros_obrigatorios_declarados_bastam(self) -> None:
        registry = build_default_registry()
        for spec in registry.specs():
            config = self.VALID[spec.name]
            assert set(spec.required_parameters) <= set(config) or not spec.required_parameters
            registry.build(spec.name, config, self.secrets())

    def test_omitir_um_obrigatorio_declarado_faz_o_builder_falhar(self) -> None:
        registry = build_default_registry()
        for spec in registry.specs():
            for missing in spec.required_parameters:
                config = {k: v for k, v in self.VALID[spec.name].items() if k != missing}
                with pytest.raises(ConfigError):
                    registry.build(spec.name, config, self.secrets())

    def test_um_parametro_fora_do_declarado_e_recusado(self) -> None:
        registry = build_default_registry()
        for spec in registry.specs():
            config = {**self.VALID[spec.name], "parametro_inexistente": 1}
            with pytest.raises(ConfigError):
                registry.build(spec.name, config, self.secrets())

    def test_todo_opcional_declarado_e_de_fato_aceito(self) -> None:
        registry = build_default_registry()
        aceitos = {"preserve_length": False, "length": 4}
        for spec in registry.specs():
            if not spec.optional_parameters:
                continue
            config = {**self.VALID[spec.name]}
            config.update({name: aceitos[name] for name in spec.optional_parameters})
            registry.build(spec.name, config, self.secrets())


# --------------------------------------------------------------------------
# /protected
# --------------------------------------------------------------------------


class TestProtected:
    def test_as_relacoes_de_estatistica_bloqueadas(self, harness: Harness) -> None:
        """D-039 fechou F-05, um finding CRITICAL."""
        payload = get(harness, "/admin/v1/protected")
        assert payload["denied_relations"] == sorted(DENIED_RELATIONS)
        assert "pg_stats" in payload["denied_relations"]
        assert "pg_statistic" in payload["denied_relations"]

    def test_as_quatro_regras_do_validator(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/protected")
        assert payload["validator_rules"] == list(VALIDATOR_RULES)
        assert len(payload["validator_rules"]) == 4

    def test_pg_e_deny_by_default_com_allowlist_visivel(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/protected")

        assert payload["pg_namespace_default"] == PG_NAMESPACE_DEFAULT == "deny"
        assert payload["denied_function_prefixes"] == sorted(DEFAULT_DENIED_PREFIXES)

    def test_allowed_pg_functions_aparece_como_politica_EFETIVA(self, harness: Harness) -> None:
        """Defaults do produto mais o que o arquivo acrescentou (secao 11.3)."""
        payload = get(harness, "/admin/v1/protected")
        esperado = sorted(DEFAULT_ALLOWED_PG_FUNCTIONS | {"pg_typeof"})

        assert payload["allowed_pg_functions"] == esperado

    def test_denied_functions_tambem_e_a_politica_efetiva(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/protected")
        assert payload["denied_functions"] == sorted(DEFAULT_DENIED_FUNCTIONS | {"dblink_exec"})

    def test_sessao_read_only_e_capability_de_proveniencia(self, harness: Harness) -> None:
        session = get(harness, "/admin/v1/protected")["session"]

        assert session["read_only"] is True
        assert session["provenance_capability_required"] is True
        assert session["statement_timeout_enforced_by"] == "postgresql"

    def test_a_ordem_do_pipeline_e_o_default_allow(self, harness: Harness) -> None:
        payload = get(harness, "/admin/v1/protected")

        assert payload["pipeline"] == list(PIPELINE)
        assert payload["pipeline"] == ["DERIVED", "EXCEPTION", "MASKING", "ORIGINAL"]
        assert payload["unmatched_policy"] == UNMATCHED_POLICY == "allow"

    def test_a_resposta_AFIRMA_que_nada_disso_e_editavel(self, harness: Harness) -> None:
        assert get(harness, "/admin/v1/protected")["editable"] is False

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_nao_existe_escrita_em_protected(self, harness: Harness, method: str) -> None:
        """D-050: item criado para fechar vulnerabilidade nao se desliga por API."""
        reply = request(
            harness.port,
            method,
            "/admin/v1/protected",
            content_type="application/json",
            body=b"{}",
        )
        assert reply.status == 405

    @pytest.mark.parametrize(
        "path",
        [
            "/admin/v1/protected/denied_relations",
            "/admin/v1/protected/allowed_pg_functions",
            "/admin/v1/protected/read_only",
        ],
    )
    def test_nao_existe_subrecurso_de_protected(self, harness: Harness, path: str) -> None:
        assert request(harness.port, "GET", path).status == 404

    def test_a_resposta_nao_carrega_referencia_mutavel_da_politica(self, harness: Harness) -> None:
        """`SqlPolicy` e congelada sobre `frozenset` e `tuple`: nao ha o que mutar."""
        policy = harness.service.sql_policy

        assert isinstance(policy.denied_relations, frozenset)
        assert isinstance(policy.allowed_pg_functions, frozenset)
        assert isinstance(policy.denied_prefixes, tuple)
        assert policy is harness.registry.current.config.sql
