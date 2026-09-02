"""Fase 7, Etapa 7: coerencia do snapshot administrativo (D-057).

O defeito que estes testes fecham nao e teorico. Enquanto as views liam
`service.document` e depois `service.revision`, um reload concorrente cabia
entre as duas leituras, e a resposta saia com o conteudo do runtime ANTIGO
carimbado com a revision NOVA.

Uma leitura incoerente ja e ruim; o dano real aparece na Etapa 9. O
`expected_revision` do passo 2 da secao 7.4 promete que ninguem sobrescreve uma
mudanca que nao viu — mas essa promessa depende inteiramente de a revision que
o administrador leu descrever o conteudo que ele leu. Com o par misturado, ele
editaria o documento antigo enviando a revision nova, o passo 2 aprovaria, e a
mudanca de outra pessoa desapareceria sem conflito algum.

## Como o swap e provocado

`SwappingRegistry` troca o runtime publicado a cada leitura de `current`,
imediatamente DEPOIS de devolve-la — que e exatamente onde a janela ficava. O
efeito e deterministico, e nao uma corrida que as vezes acontece:

- codigo que le a referencia publicada DUAS vezes ve dois runtimes diferentes,
  sempre;
- codigo que le UMA vez ve um runtime so, sempre.

`TestOPadraoAntigoMisturaDeVerdade` prova a primeira metade — e a contraprova
que impede estes testes de passarem por nao provocarem nada.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from maskgw.admin.http.views import (
    build_config,
    build_exceptions,
    build_protected,
    build_rules,
    build_status,
    build_transformers,
    find_exception,
    find_rule,
)
from maskgw.runtime import Runtime, RuntimeRegistry
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import (
    EXCEPTION_ID,
    RULE_ID,
    SECOND_RULE_ID,
    Harness,
    build_runtime,
    build_service,
    request,
)

#: Marcadores da politica SQL de cada revision. Nenhum deles esta em
#: `DEFAULT_ALLOWED_PG_FUNCTIONS`: um default apareceria nas duas revisions e
#: nao distinguiria nada.
PG_MARKER_3: Final = "pg_backend_pid"
PG_MARKER_4: Final = "pg_postmaster_start_time"

#: Revision 3: duas regras, uma exception, `PG_MARKER_3` liberada.
REVISION_3: dict[str, Any] = {
    "revision": 3,
    "masking": [
        {"id": RULE_ID, "match": "cpf", "transformer": "sha256"},
        {"id": SECOND_RULE_ID, "match": "email", "transformer": "md5"},
    ],
    "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
    "database": {"statement_timeout_ms": 2000, "max_rows": 10},
    "sql": {"allowed_pg_functions": [PG_MARKER_3], "denied_functions": ["dblink_exec"]},
}

#: Revision 4: a primeira regra e a exception FORAM REMOVIDAS, a segunda mudou
#: de transformer, e a politica SQL e outra. Nenhum campo observavel coincide
#: com a revision 3 — qualquer mistura fica visivel.
REVISION_4: dict[str, Any] = {
    "revision": 4,
    "masking": [{"id": SECOND_RULE_ID, "match": "email", "transformer": "sha256"}],
    "exceptions": [],
    "database": {"statement_timeout_ms": 3000, "max_rows": 20},
    "sql": {"allowed_pg_functions": [PG_MARKER_4], "denied_functions": ["dblink_connect"]},
}

#: Sem `revision`: `adopted` e falso. O par com `REVISION_1` e o que distingue
#: `adopted` derivado da revision capturada de `adopted` lido de novo.
UNADOPTED: dict[str, Any] = {"masking": [{"match": "cpf", "transformer": "md5"}]}

ADOPTED_1: dict[str, Any] = {
    "revision": 1,
    "masking": [{"id": RULE_ID, "match": "cpf", "transformer": "md5"}],
}


class SwappingRegistry(RuntimeRegistry):
    """Troca o runtime publicado a cada leitura de `current`.

    A troca acontece DEPOIS de a referencia ser devolvida, entao quem leu
    recebe o runtime anterior e a proxima leitura recebe o seguinte. E a
    reproducao exata da janela: no codigo antigo, o `document` vinha da
    primeira leitura e a `revision` da segunda.
    """

    def __init__(self, initial: Runtime, followups: list[Runtime] | None = None) -> None:
        super().__init__(initial)
        self.followups: list[Runtime] = list(followups or [])
        self.reads = 0

    @property
    def current(self) -> Runtime:
        runtime = super().current
        self.reads += 1
        if self.followups:
            # `swap` devolve o aposentado quando ja nao ha usuarios; sem query
            # em voo, o antigo fecha aqui mesmo e o limite de aposentados nunca
            # e atingido.
            retired = self.swap(self.followups.pop(0))
            if retired is not None:
                retired.adapter.close()
        return runtime


def harness(tmp_path: Path, *, first: dict[str, Any], then: list[dict[str, Any]]) -> Harness:
    """Servico real cujo runtime publicado troca a cada leitura."""
    secrets = MappingSecretProvider({})
    followups = [build_runtime(payload, secrets=secrets) for payload in then]
    return build_service(
        tmp_path,
        first,
        secrets=secrets,
        registry_factory=lambda initial: SwappingRegistry(initial, followups),
    )


@pytest.fixture
def swapping(tmp_path: Path) -> Iterator[Harness]:
    built = harness(tmp_path, first=REVISION_3, then=[REVISION_4])
    try:
        yield built
    finally:
        built.close()


# --------------------------------------------------------------------------
# A contraprova: o cenario realmente provoca a mistura
# --------------------------------------------------------------------------


class TestOPadraoAntigoMisturaDeVerdade:
    """Sem isto, os testes abaixo poderiam passar por nao provocarem nada."""

    def test_duas_leituras_separadas_veem_runtimes_diferentes(self, swapping: Harness) -> None:
        # Exatamente o que as views faziam: documento de uma leitura, revision
        # de outra.
        document = swapping.service.document
        revision = swapping.service.revision

        assert document.revision == 3
        assert revision == 4
        # O par que sairia na resposta: conteudo da 3 rotulado como 4.
        assert document.revision != revision

    def test_a_politica_tambem_se_separa_da_revision(self, swapping: Harness) -> None:
        policy = swapping.service.sql_policy
        revision = swapping.service.revision

        assert PG_MARKER_3 in policy.allowed_pg_functions
        assert PG_MARKER_4 not in policy.allowed_pg_functions
        assert revision == 4

    def test_adopted_lido_a_parte_contradiz_a_revision(self, tmp_path: Path) -> None:
        built = harness(tmp_path, first=UNADOPTED, then=[ADOPTED_1])
        try:
            revision = built.service.revision
            adopted = built.service.adopted

            assert revision == 0
            # `revision == 0` significa NAO adotada; a segunda leitura afirma o
            # contrario sobre a mesma resposta.
            assert adopted is True
        finally:
            built.close()


# --------------------------------------------------------------------------
# O snapshot
# --------------------------------------------------------------------------


class TestSnapshotCoerente:
    def test_uma_unica_leitura_da_referencia_publicada(self, swapping: Harness) -> None:
        registry = swapping.registry
        assert isinstance(registry, SwappingRegistry)
        antes = registry.reads

        swapping.service.snapshot()

        assert registry.reads - antes == 1

    def test_documento_revision_e_politica_vem_do_mesmo_runtime(self, swapping: Harness) -> None:
        snapshot = swapping.service.snapshot()

        assert snapshot.revision == 3
        assert snapshot.document.revision == 3
        assert [rule.id for rule in snapshot.document.masking] == [RULE_ID, SECOND_RULE_ID]
        assert PG_MARKER_3 in snapshot.sql_policy.allowed_pg_functions
        # E o runtime publicado JA e outro: o snapshot descreve o instante da
        # leitura, e nao o presente.
        assert swapping.registry.current.revision == 4

    def test_adopted_deriva_da_revision_capturada(self, tmp_path: Path) -> None:
        built = harness(tmp_path, first=UNADOPTED, then=[ADOPTED_1])
        try:
            snapshot = built.service.snapshot()
            assert snapshot.revision == 0
            assert snapshot.adopted is False
            assert snapshot.document.revision == 0
        finally:
            built.close()

    def test_o_documento_continua_sendo_copia_profunda(self, swapping: Harness) -> None:
        snapshot = swapping.service.snapshot()
        publicado = swapping.registry.current

        snapshot.document.masking.clear()

        assert publicado.file_config.masking != []

    def test_o_lock_do_registry_nao_e_segurado_durante_a_copia(self, tmp_path: Path) -> None:
        """A copia profunda acontece FORA da secao critica do registry.

        Segura-la ali bloquearia a aquisicao de toda query nova pelo tempo de
        uma serializacao — e o registry existe justamente para que reload e
        query nao esperem um pelo outro (D-054).
        """
        built = build_service(tmp_path, REVISION_3)
        try:
            registry = built.registry
            publicado = registry.current
            spy = _CopySpy(publicado.file_config, registry)
            # O `Runtime` guarda o documento num slot; trocar o objeto e o modo
            # de observar a copia sem alterar o codigo de producao.
            publicado._file_config = spy  # type: ignore[assignment]

            built.service.snapshot()

            assert spy.copies == 1
            # `Lock.locked()` nao depende da thread dona: se `current` ainda o
            # segurasse, isto seria verdadeiro.
            assert spy.lock_held_during_copy is False
        finally:
            built.close()


class _CopySpy:
    """Documento que registra se o lock do registry estava preso na copia."""

    def __init__(self, inner: Any, registry: RuntimeRegistry) -> None:
        self._inner = inner
        self._registry = registry
        self.copies = 0
        self.lock_held_during_copy: bool | None = None

    def model_copy(self, *, deep: bool = False) -> Any:
        self.copies += 1
        self.lock_held_during_copy = self._registry._lock.locked()
        return self._inner.model_copy(deep=deep)


# --------------------------------------------------------------------------
# As views, uma a uma
# --------------------------------------------------------------------------


class TestViewsNaoMisturamRuntimes:
    def test_config(self, swapping: Harness) -> None:
        response = build_config(swapping.service.snapshot())

        assert response.revision == 3
        assert response.config.revision == 3
        assert response.adopted is True
        assert response.config.sql.allowed_pg_functions == [PG_MARKER_3]

    def test_rules(self, swapping: Harness) -> None:
        response = build_rules(swapping.service.snapshot())

        assert response.revision == 3
        assert [rule.id for rule in response.rules] == [RULE_ID, SECOND_RULE_ID]
        assert [rule.transformer for rule in response.rules] == ["sha256", "md5"]

    def test_rule_por_id(self, swapping: Harness) -> None:
        response = find_rule(swapping.service.snapshot(), RULE_ID)

        assert response is not None
        assert response.revision == 3
        assert response.rule.transformer == "sha256"

    def test_exceptions(self, swapping: Harness) -> None:
        response = build_exceptions(swapping.service.snapshot())

        assert response.revision == 3
        assert [item.id for item in response.exceptions] == [EXCEPTION_ID]

    def test_exception_por_id(self, swapping: Harness) -> None:
        response = find_exception(swapping.service.snapshot(), EXCEPTION_ID)

        assert response is not None
        assert response.revision == 3
        assert response.exception.match == "tipo_cpf"

    def test_protected(self, swapping: Harness) -> None:
        response = build_protected(swapping.service.snapshot())

        assert response.revision == 3
        # A politica EFETIVA soma os defaults do produto; o que distingue as
        # duas revisions e o marcador de cada uma.
        assert PG_MARKER_3 in response.allowed_pg_functions
        assert PG_MARKER_4 not in response.allowed_pg_functions
        assert "dblink_exec" in response.denied_functions

    def test_transformers(self, swapping: Harness) -> None:
        response = build_transformers(swapping.service.snapshot())

        assert response.revision == 3

    def test_status(self, swapping: Harness) -> None:
        response = build_status(
            swapping.service.snapshot(),
            swapping.service,
            secrets=MappingSecretProvider({}),
            hmac_key_env="MASKGW_HMAC_KEY",
            database_dsn_env="MASKGW_DATABASE_DSN",
        )

        assert response.revision == 3
        assert response.runtime.revision == 3
        assert response.adopted is True

    def test_status_nao_adotado(self, tmp_path: Path) -> None:
        built = harness(tmp_path, first=UNADOPTED, then=[ADOPTED_1])
        try:
            response = build_status(
                built.service.snapshot(),
                built.service,
                secrets=MappingSecretProvider({}),
                hmac_key_env="MASKGW_HMAC_KEY",
                database_dsn_env="MASKGW_DATABASE_DSN",
            )

            assert response.revision == 0
            assert response.runtime.revision == 0
            assert response.adopted is False
        finally:
            built.close()


# --------------------------------------------------------------------------
# Pelo fio, com o servidor real
# --------------------------------------------------------------------------


class TestPeloServidorReal:
    def test_config_nunca_rotula_conteudo_de_outra_revision(self, swapping: Harness) -> None:
        swapping.start()
        payload = request(swapping.port, "GET", "/admin/v1/config").json()

        assert payload["revision"] == payload["config"]["revision"]
        assert payload["revision"] == 3
        assert payload["config"]["sql"]["allowed_pg_functions"] == [PG_MARKER_3]

    def test_rules_carimba_a_revision_do_proprio_conteudo(self, swapping: Harness) -> None:
        swapping.start()
        payload = request(swapping.port, "GET", "/admin/v1/rules").json()

        assert payload["revision"] == 3
        assert [rule["id"] for rule in payload["rules"]] == [RULE_ID, SECOND_RULE_ID]

    def test_protected_casa_politica_e_revision(self, swapping: Harness) -> None:
        swapping.start()
        payload = request(swapping.port, "GET", "/admin/v1/protected").json()

        assert payload["revision"] == 3
        assert PG_MARKER_3 in payload["allowed_pg_functions"]
        assert PG_MARKER_4 not in payload["allowed_pg_functions"]

    def test_status_concorda_consigo_mesmo(self, swapping: Harness) -> None:
        swapping.start()
        payload = request(swapping.port, "GET", "/admin/v1/status").json()

        assert payload["revision"] == payload["runtime"]["revision"] == 3
        assert payload["adopted"] is True

    def test_id_removido_no_reload_some_inteiro_ou_aparece_inteiro(
        self,
        swapping: Harness,
    ) -> None:
        """A regra `RULE_ID` existe na revision 3 e nao existe na 4.

        Cada requisicao ve um estado inteiro. A primeira encontra a regra sob a
        revision 3; a segunda, ja sobre a revision 4, responde `NOT_FOUND`. O
        que nao pode existir e o meio-termo: a regra da 3 rotulada como 4.
        """
        swapping.start()

        primeira = request(swapping.port, "GET", f"/admin/v1/rules/{RULE_ID}")
        segunda = request(swapping.port, "GET", f"/admin/v1/rules/{RULE_ID}")

        assert primeira.status == 200
        payload = primeira.json()
        assert payload["revision"] == 3
        assert payload["rule"]["id"] == RULE_ID

        assert segunda.status == 404
        assert segunda.json()["error"] == "NOT_FOUND"

    def test_exception_removida_no_reload(self, swapping: Harness) -> None:
        swapping.start()

        primeira = request(swapping.port, "GET", f"/admin/v1/exceptions/{EXCEPTION_ID}")
        segunda = request(swapping.port, "GET", f"/admin/v1/exceptions/{EXCEPTION_ID}")

        assert primeira.status == 200
        assert primeira.json()["revision"] == 3
        assert segunda.status == 404

    def test_regra_alterada_no_reload_nao_vaza_pela_revision(self, tmp_path: Path) -> None:
        """`SECOND_RULE_ID` sobrevive ao reload, mas com outro transformer."""
        built = harness(tmp_path, first=REVISION_3, then=[REVISION_4])
        try:
            built.start()
            primeira = request(built.port, "GET", f"/admin/v1/rules/{SECOND_RULE_ID}").json()
            segunda = request(built.port, "GET", f"/admin/v1/rules/{SECOND_RULE_ID}").json()

            assert (primeira["revision"], primeira["rule"]["transformer"]) == (3, "md5")
            assert (segunda["revision"], segunda["rule"]["transformer"]) == (4, "sha256")
        finally:
            built.close()

    def test_toda_rota_de_leitura_permanece_coerente_sob_swap_continuo(
        self,
        tmp_path: Path,
    ) -> None:
        """Alternar entre duas revisions a cada leitura, indefinidamente."""
        built = harness(tmp_path, first=REVISION_3, then=[REVISION_4, REVISION_3] * 12)
        marcador_por_revision = {3: PG_MARKER_3, 4: PG_MARKER_4}
        ids_por_revision = {3: [RULE_ID, SECOND_RULE_ID], 4: [SECOND_RULE_ID]}
        try:
            built.start()
            for _ in range(8):
                config = request(built.port, "GET", "/admin/v1/config").json()
                rules = request(built.port, "GET", "/admin/v1/rules").json()
                protected = request(built.port, "GET", "/admin/v1/protected").json()

                assert config["revision"] == config["config"]["revision"]
                assert config["config"]["sql"]["allowed_pg_functions"] == [
                    marcador_por_revision[config["revision"]]
                ]
                assert [rule["id"] for rule in rules["rules"]] == ids_por_revision[
                    rules["revision"]
                ]
                assert (
                    marcador_por_revision[protected["revision"]]
                    in protected["allowed_pg_functions"]
                )
        finally:
            built.close()


# --------------------------------------------------------------------------
# Concorrencia de verdade, para alem do swap encenado
# --------------------------------------------------------------------------


class TestSwapConcorrenteReal:
    def test_leituras_sob_reload_continuo_nunca_saem_incoerentes(self, tmp_path: Path) -> None:
        """Uma thread troca o runtime; outra le. Nenhuma resposta se contradiz.

        O swap encenado prova o ponto exato; este prova que nao ha outro ponto.
        """
        secrets = MappingSecretProvider({})
        built = build_service(tmp_path, REVISION_3, secrets=secrets)
        parar = threading.Event()
        falhas: list[str] = []

        def reloader() -> None:
            alterna = [REVISION_4, REVISION_3]
            indice = 0
            while not parar.is_set():
                runtime = build_runtime(alterna[indice % 2], secrets=secrets)
                retired = built.registry.swap(runtime)
                if retired is not None:
                    retired.adapter.close()
                indice += 1

        try:
            built.start()
            thread = threading.Thread(target=reloader, name="reloader")
            thread.start()
            try:
                for _ in range(60):
                    payload = request(built.port, "GET", "/admin/v1/config").json()
                    if payload["revision"] != payload["config"]["revision"]:
                        falhas.append(str(payload["revision"]))
                    rules = request(built.port, "GET", "/admin/v1/rules").json()
                    quantidade = {3: 2, 4: 1}[rules["revision"]]
                    if len(rules["rules"]) != quantidade:
                        falhas.append(str(rules["revision"]))
            finally:
                parar.set()
                thread.join(timeout=10)
        finally:
            built.close()

        assert falhas == []
