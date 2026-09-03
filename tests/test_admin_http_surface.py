"""Fase 7, Etapa 7: a superficie HTTP, comparada literalmente (secao 12.7).

O teste central deste arquivo e `test_o_conjunto_de_rotas_e_exatamente_o_da_especificacao`:
ele compara o que o router registrou com a lista literal da secao 1.1. Uma rota
nova — inclusive uma acrescentada por engano numa etapa futura — quebra a suite
em vez de aparecer sem que ninguem tenha decidido.

Tudo aqui roda contra um servidor de verdade, em loopback, com um cliente que
controla cada header.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.routing import APIRoute

from maskgw.admin.http import (
    READ_METHODS,
    READ_PATHS,
    VALIDATE_METHODS,
    VALIDATE_PATH,
    build_router,
)
from maskgw.admin.http.app import API_PREFIX, WRITE_ROUTES
from maskgw.admin.service import AdminConfigService
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import (
    TOKEN,
    Harness,
    build_service,
    request,
)

#: Caminhos que a secao 1.5 declara inexistentes. Nao "recusados": inexistentes.
#: `/admin/v1/sql` e `/admin/v1/database` SAIRAM desta lista na Etapa 9 — passaram
#: a existir como `PUT`, entao um `GET` nelas e `405`, nao `404`. Continuam sem
#: DSN, sem execucao de SQL e sem `config:reload`.
FORBIDDEN_PATHS = [
    "/admin/v1/query",
    "/admin/v1/execute",
    "/admin/v1/explain",
    "/admin/v1/schema",
    "/admin/v1/tables",
    "/admin/v1/preview",
    "/admin/v1/secrets",
    "/admin/v1/hmac-key",
    "/admin/v1/token",
    "/admin/v1/dsn",
    "/admin/v1/database/dsn",
    "/admin/v1/config:reload",
    "/query",
    "/sql",
    "/execute",
]

#: Rotas de etapas futuras. Existirem AGORA seria antecipacao. `config:validate`
#: saiu na Etapa 8; as onze rotas de escrita sairam na Etapa 9 — existem agora e
#: sao testadas em `test_admin_http_writes.py`. So `AdminAudit` (Etapa 10)
#: continua inexistente.
FUTURE_PATHS = [
    "/admin/v1/audit",
    "/admin/v1/audit/entries",
]

#: Documentacao automatica: entregaria a superficie inteira a quem nao
#: autenticou. Desligada na construcao, e nao escondida.
DOC_PATHS = ["/docs", "/redoc", "/openapi.json", "/admin/v1/docs", "/admin/v1/openapi.json"]


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    state = build_service(tmp_path)
    state.start()
    try:
        yield state
    finally:
        state.close()


# --------------------------------------------------------------------------
# O conjunto literal
# --------------------------------------------------------------------------


class TestRouteSet:
    def registered(self) -> set[tuple[str, frozenset[str]]]:
        router = build_router(
            _service_stub(),
            secrets=MappingSecretProvider({}),
            database_dsn_env="MASKGW_DATABASE_DSN",
        )
        return {
            (route.path, frozenset(route.methods or set()))
            for route in router.routes
            if isinstance(route, APIRoute)
        }

    def _expected(self) -> set[tuple[str, frozenset[str]]]:
        """O conjunto literal da secao 1: 8 leituras + 1 validate + 11 escritas.

        Cada rota de escrita entra com o seu unico metodo. Onde dois metodos de
        escrita compartilham um path — `PUT` e `DELETE` de `/rules/{rule_id}` —,
        cada um e uma entrada `(path, {metodo})` separada, exatamente como o
        FastAPI registra.
        """
        expected = {(path, READ_METHODS) for path in READ_PATHS}
        expected.add((VALIDATE_PATH, VALIDATE_METHODS))
        for path, method in WRITE_ROUTES:
            expected.add((path, frozenset({method})))
        return expected

    def test_o_conjunto_de_rotas_e_exatamente_o_da_especificacao(self) -> None:
        """As oito leituras, o `config:validate` e as onze escritas da Etapa 9.

        Comparacao literal: uma rota nova — inclusive uma de escrita da Etapa 9
        acrescentada por engano, ou uma da Etapa 10 antecipada — quebra este
        teste em vez de aparecer.
        """
        assert self.registered() == self._expected()

    def test_contagem_de_rotas(self) -> None:
        assert len(READ_PATHS) == 8
        assert set(VALIDATE_METHODS) == {"POST"}
        assert len(WRITE_ROUTES) == 11
        # 20 entradas distintas `(path, metodos)`: 8 leituras GET/HEAD, 1 POST
        # validate, e 11 escritas — as duas de `/rules/{rule_id}` e as duas de
        # `/exceptions/{exception_id}` sao entradas separadas por metodo.
        assert len(self.registered()) == 20

    def test_todas_sob_o_prefixo_unico(self) -> None:
        assert all(path.startswith(f"{API_PREFIX}/") for path in READ_PATHS)
        assert VALIDATE_PATH.startswith(f"{API_PREFIX}/")
        assert all(path.startswith(f"{API_PREFIX}/") for path, _method in WRITE_ROUTES)

    def test_as_rotas_de_corpo_sao_validate_mais_as_onze_escritas(self) -> None:
        """`config:validate` mais as onze escritas — e nada alem delas.

        Nenhum `PATCH`, nenhuma rota de corpo fora do conjunto decidido.
        Registrar uma rota de escrita da Etapa 10, ou um `PATCH`, quebra aqui.
        """
        with_body = {
            (path, methods)
            for path, methods in self.registered()
            if methods & {"POST", "PUT", "PATCH", "DELETE"}
        }
        expected = {(VALIDATE_PATH, VALIDATE_METHODS)}
        for path, method in WRITE_ROUTES:
            expected.add((path, frozenset({method})))
        assert with_body == expected

    def test_nenhum_patch_em_lugar_algum(self) -> None:
        """Nao ha `PATCH`: merge parcial num documento de seguranca (secao 1.3)."""
        for _path, methods in self.registered():
            assert "PATCH" not in methods

    def test_reorder_registrada_antes_da_rota_dinamica_de_escrita(self) -> None:
        """`/rules:reorder` casa antes de `/rules/{rule_id}` no MESMO metodo.

        Nao ha `POST /rules/{rule_id}`, entao nenhum path dinamico compete com o
        `POST /rules:reorder` — mas registrar `:reorder` primeiro entre as
        escritas e a garantia estrutural de que, se um `POST /rules/{rule_id}`
        aparecer um dia, `:reorder` ainda casa antes. Confere a ordem de registro
        das rotas de escrita (secao 12.7). O casamento em si e teste de
        comportamento em `test_admin_http_writes.py`.
        """
        write_paths = [path for path, _method in WRITE_ROUTES]
        assert write_paths.index(f"{API_PREFIX}/rules:reorder") < write_paths.index(
            f"{API_PREFIX}/rules/{{rule_id}}"
        )

    def test_options_nunca_e_registrado(self) -> None:
        """Sem preflight handler: e o que faz a camada 1 da secao 3.3 valer."""
        for _path, methods in self.registered():
            assert "OPTIONS" not in methods

    def test_head_acompanha_todo_get_de_leitura(self) -> None:
        write_paths_methods = {(path, method) for path, method in WRITE_ROUTES}
        for path, methods in self.registered():
            if path == VALIDATE_PATH or any(path == wp for wp, _m in write_paths_methods):
                continue
            assert methods == frozenset({"GET", "HEAD"})


def _service_stub() -> AdminConfigService:
    """Servico minimo: `build_router` so o CAPTURA, nao o consulta na montagem.

    O conjunto de rotas e propriedade da montagem, nao do estado — construir um
    servico real aqui exigiria filesystem e lock para nao verificar nada a mais.
    """

    class Stub:
        revision = 0
        adopted = False

    return cast(AdminConfigService, Stub())


# --------------------------------------------------------------------------
# O que responde, e com que status
# --------------------------------------------------------------------------


class TestReachability:
    @pytest.mark.parametrize("path", ["/admin/v1/status", "/admin/v1/config", "/admin/v1/rules"])
    def test_get_autenticado_responde_200(self, harness: Harness, path: str) -> None:
        assert request(harness.port, "GET", path).status == 200

    @pytest.mark.parametrize("path", FORBIDDEN_PATHS)
    def test_rota_proibida_e_404(self, harness: Harness, path: str) -> None:
        """Inexistente, e nao recusada: o router nunca a conheceu (D-049)."""
        reply = request(harness.port, "GET", path)

        assert reply.status == 404
        assert reply.json()["error"] == "NOT_FOUND"

    @pytest.mark.parametrize("path", FUTURE_PATHS)
    def test_rota_de_etapa_futura_ainda_nao_existe(self, harness: Harness, path: str) -> None:
        assert request(harness.port, "GET", path).status == 404

    @pytest.mark.parametrize("path", DOC_PATHS)
    def test_documentacao_automatica_esta_desligada(self, harness: Harness, path: str) -> None:
        assert request(harness.port, "GET", path).status == 404

    def test_a_admin_api_nao_executa_sql(self, harness: Harness) -> None:
        """D-049, verificado por enumeracao e por contador no adapter.

        Nenhuma rota de leitura toca o adapter; se alguma tocasse, o duble
        levantaria em `execute_validated`.
        """
        for path in READ_PATHS:
            if "{" in path:
                continue
            request(harness.port, "GET", path)
        assert harness.adapter.execute_calls == 0
        assert harness.adapter.connect_calls == 0


class TestMethods:
    @pytest.mark.parametrize("path", [p for p in READ_PATHS if "{" not in p])
    def test_head_exige_autenticacao_mesmo_status_e_corpo_vazio(
        self,
        harness: Harness,
        path: str,
    ) -> None:
        """Secao 12.7: mesma autenticacao, mesmo status, corpo vazio."""
        head = request(harness.port, "HEAD", path)
        get = request(harness.port, "GET", path)

        assert head.status == get.status == 200
        assert head.body == b""
        assert get.body != b""
        assert head.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize("path", [p for p in READ_PATHS if "{" not in p])
    def test_head_sem_token_e_401_com_corpo_vazio(self, harness: Harness, path: str) -> None:
        reply = request(harness.port, "HEAD", path, token=None)

        assert reply.status == 401
        assert reply.body == b""

    @pytest.mark.parametrize("path", [p for p in READ_PATHS if "{" not in p])
    def test_options_responde_405_sem_header_cors(self, harness: Harness, path: str) -> None:
        reply = request(harness.port, "OPTIONS", path)

        assert reply.status == 405
        assert reply.json()["error"] == "METHOD_NOT_ALLOWED"
        assert reply.cors_headers == []

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_metodo_de_escrita_com_json_valido_e_405(self, harness: Harness, method: str) -> None:
        """Com `Content-Type` correto, a recusa vem do router: a rota nao aceita.

        `/admin/v1/status` e somente leitura (`GET`/`HEAD`): nenhum metodo de
        escrita e registrado nela, entao o router responde `405`.
        """
        reply = request(
            harness.port,
            method,
            "/admin/v1/status",
            content_type="application/json",
            body=b"{}",
        )

        assert reply.status == 405
        assert reply.json()["error"] == "METHOD_NOT_ALLOWED"

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_metodo_de_escrita_sem_json_e_415_na_fronteira(
        self,
        harness: Harness,
        method: str,
    ) -> None:
        """A camada de `Content-Type` decide antes do router, e e o correto:
        um `<form>` cross-origin e cortado sem que o caminho importe."""
        reply = request(
            harness.port,
            method,
            "/admin/v1/status",
            content_type="text/plain",
            body=b"x",
        )

        assert reply.status == 415
        assert reply.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"


class TestTrailingSlash:
    @pytest.mark.parametrize("path", [f"{p}/" for p in READ_PATHS if "{" not in p])
    def test_barra_final_e_404_e_nunca_307(self, harness: Harness, path: str) -> None:
        """`redirect_slashes` desligado: um redirect implicito e uma rota que
        ninguem registrou."""
        reply = request(harness.port, "GET", path)

        assert reply.status == 404
        assert reply.json()["error"] == "NOT_FOUND"
        assert "location" not in reply.headers

    @pytest.mark.parametrize("path", ["/admin/v1", "/admin/v1/", "/admin", "/", "/admin/v2/status"])
    def test_caminho_desconhecido_e_404(self, harness: Harness, path: str) -> None:
        reply = request(harness.port, "GET", path)

        assert reply.status == 404
        assert "location" not in reply.headers


# --------------------------------------------------------------------------
# Autenticacao pela fronteira real
# --------------------------------------------------------------------------


class TestAuthenticationOverTheWire:
    def test_sem_token_e_401(self, harness: Harness) -> None:
        assert request(harness.port, token=None).status == 401

    @pytest.mark.parametrize("token", ["", "errado", TOKEN[:-1], TOKEN + "x", TOKEN.upper()])
    def test_token_errado_e_401(self, harness: Harness, token: str) -> None:
        assert request(harness.port, token=token).status == 401

    def test_ausente_e_errado_sao_indistinguiveis(self, harness: Harness) -> None:
        ausente = request(harness.port, token=None)
        errado = request(harness.port, token="errado")
        malformado = request(harness.port, token=None, headers={"Authorization": "Basic abc"})

        assert ausente.status == errado.status == malformado.status == 401
        assert ausente.body == errado.body == malformado.body

    def test_token_em_query_string_nunca_e_aceito(self, harness: Harness) -> None:
        """Query string vaza em log de proxy, em historico e em `Referer`."""
        for path in (
            f"/admin/v1/status?token={TOKEN}",
            f"/admin/v1/status?access_token={TOKEN}",
            f"/admin/v1/status?authorization=Bearer%20{TOKEN}",
            f"/admin/v1/status?api_key={TOKEN}",
        ):
            assert request(harness.port, "GET", path, token=None).status == 401

    def test_token_em_cookie_nunca_e_aceito(self, harness: Harness) -> None:
        """Cookie e exatamente o que torna CSRF possivel."""
        for cookie in (
            f"token={TOKEN}",
            f"authorization=Bearer {TOKEN}",
            f"session={TOKEN}; other=1",
        ):
            reply = request(harness.port, token=None, headers={"Cookie": cookie})
            assert reply.status == 401

    def test_401_chega_ANTES_de_qualquer_422(self, harness: Harness) -> None:
        """Sem token nao se sonda o schema (secao 12.7).

        Um corpo malformado num metodo com corpo, sem credencial: a resposta
        precisa ser `401`, jamais `422`.
        """
        reply = request(
            harness.port,
            "POST",
            "/admin/v1/config",
            token=None,
            content_type="application/json",
            body=b'{"campo_que_nao_existe": 1}',
        )

        assert reply.status == 401
        assert reply.json()["error"] == "UNAUTHORIZED"

    def test_nenhuma_resposta_de_401_carrega_www_authenticate_com_dica(
        self,
        harness: Harness,
    ) -> None:
        reply = request(harness.port, token=None)
        rendered = repr(reply.headers) + reply.text()

        assert TOKEN not in rendered
        assert TOKEN[:6] not in rendered


class TestBrowserProtections:
    @pytest.mark.parametrize("header", ["Origin", "Referer"])
    @pytest.mark.parametrize("value", ["http://evil.example", "null", "http://127.0.0.1:1"])
    def test_origin_ou_referer_presentes_sao_403(
        self,
        harness: Harness,
        header: str,
        value: str,
    ) -> None:
        reply = request(harness.port, headers={header: value})

        assert reply.status == 403
        assert reply.json()["error"] == "CROSS_ORIGIN_REJECTED"

    def test_origin_e_403_mesmo_sem_token(self, harness: Harness) -> None:
        reply = request(harness.port, token=None, headers={"Origin": "http://evil.example"})
        assert reply.status == 403

    @pytest.mark.parametrize(
        "host",
        [
            "evil.example",
            "attacker.test:{port}",
            "127.0.0.1.evil.example:{port}",
            "127.0.0.1:1",
            "localhost",
            "[::1]",
            "0.0.0.0:{port}",
        ],
    )
    def test_dns_rebinding_e_400(self, harness: Harness, host: str) -> None:
        """O nome resolve para loopback; o `Host` enviado o denuncia."""
        reply = request(harness.port, host=host.format(port=harness.port))

        assert reply.status == 400
        assert reply.json()["error"] == "HOST_NOT_ALLOWED"

    @pytest.mark.parametrize("template", ["127.0.0.1:{port}", "localhost:{port}", "[::1]:{port}"])
    def test_as_tres_formas_canonicas_de_host_passam(
        self,
        harness: Harness,
        template: str,
    ) -> None:
        reply = request(harness.port, host=template.format(port=harness.port))
        assert reply.status == 200


# --------------------------------------------------------------------------
# Headers de toda resposta
# --------------------------------------------------------------------------


class TestResponseHeaders:
    def all_statuses(self, harness: Harness) -> list[tuple[int, dict[str, str], str]]:
        """Uma amostra que cobre 200, 400, 401, 403, 404, 405, 413, 415 e 500."""
        replies = [
            request(harness.port),
            request(harness.port, host="evil:1"),
            request(harness.port, token=None),
            request(harness.port, headers={"Origin": "http://e"}),
            request(harness.port, "GET", "/admin/v1/inexistente"),
            request(harness.port, "OPTIONS", "/admin/v1/status"),
            request(
                harness.port,
                "POST",
                "/admin/v1/config",
                content_type="application/json",
                body=b"x" * (1024 * 1024 + 1),
            ),
            request(harness.port, "POST", "/admin/v1/config", content_type="text/plain", body=b"x"),
        ]
        return [(reply.status, reply.headers, reply.text()) for reply in replies]

    def test_no_store_em_TODA_resposta_inclusive_erros(self, harness: Harness) -> None:
        for status, headers, _body in self.all_statuses(harness):
            assert headers.get("cache-control") == "no-store", status

    def test_a_amostra_cobre_os_status_esperados(self, harness: Harness) -> None:
        observed = {status for status, _headers, _body in self.all_statuses(harness)}
        assert observed == {200, 400, 401, 403, 404, 405, 413, 415}

    def test_nenhum_header_cors_em_sucesso_ou_erro(self, harness: Harness) -> None:
        for status, headers, _body in self.all_statuses(harness):
            cors = sorted(name for name in headers if name.startswith("access-control-"))
            assert cors == [], status
            assert "vary" not in headers or "origin" not in headers["vary"].lower()

    def test_nenhuma_resposta_anuncia_o_servidor(self, harness: Harness) -> None:
        """`Server:` e reconhecimento gratuito para quem sonda a porta."""
        for status, headers, _body in self.all_statuses(harness):
            assert "server" not in headers, status

    def test_todo_erro_tem_a_mesma_forma(self, harness: Harness) -> None:
        """Secao 4.4: `error` de conjunto fechado e `detail` fixo por categoria."""
        import json

        for status, _headers, body in self.all_statuses(harness):
            if status == 200:
                continue
            payload = json.loads(body)
            assert set(payload) >= {"error", "detail"}
            assert set(payload) <= {"error", "detail", "applied", "current_revision", "fields"}
            assert isinstance(payload["error"], str)
            assert payload["error"].isupper()
