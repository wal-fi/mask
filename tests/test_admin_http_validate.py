"""Fase 7, Etapa 8: `POST /admin/v1/config:validate` (secoes 1.2, 12.11).

A rota valida o schema, **compila** os transformers e a policy, e descarta o
resultado. Compilar e o ponto: um `regex` invalido, um transformer inexistente
ou um parametro ausente so aparecem na compilacao, e um dry-run que parasse no
schema aprovaria o que a escrita real recusaria (secao 1.2).

O que este arquivo prova, alem do contrato de request/response:

- **as duas categorias de `422`**: `SCHEMA_INVALID` para o que o schema HTTP
  recusa (tipos, limites, campo desconhecido, `expected_revision`, formato de
  ID, adotado sem ID), e `CONFIG_INVALID` para o que so a COMPILACAO recusa
  (regex, transformer, parametro, HMAC sem chave);
- **ausencia total de efeito**: para sucesso e para cada tipo de falha, os bytes
  do arquivo, a revision, a identidade de `registry.current`, o digest de
  referencia, os contadores, o numero de adapters e de sessoes PostgreSQL, e o
  numero de threads ficam identicos. Doubles estruturais provam que a rota
  compila mas nao alcanca adapter, registry, filesystem nem secao critica.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.http import build_admin_app
from maskgw.admin.http.schemas import ConfigValidateRequest, ConfigValidateResponse
from maskgw.admin.http.validate import validate_candidate
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import (
    DSN_PARTS,
    EXCEPTION_ID,
    RULE_ID,
    SECOND_RULE_ID,
    SENSITIVE_HMAC,
    TOKEN,
    Harness,
    Reply,
    build_service,
    request,
)

VALIDATE = "/admin/v1/config:validate"
JSON = "application/json"

#: O HMAC precisa da chave no ambiente; o harness a expoe como `MASKGW_HMAC_KEY`.
HMAC_SECRETS = MappingSecretProvider({"MASKGW_HMAC_KEY": SENSITIVE_HMAC})

#: Um documento adotado completo, com todos os tipos de transformer validos.
FULL_DOCUMENT: dict[str, Any] = {
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

SUCCESS_BODY: dict[str, Any] = {
    "valid": True,
    "schema_validated": True,
    "policy_compiled": True,
    "database_checks_performed": False,
}


def post(port: int, body: Any, **kwargs: Any) -> Reply:
    """POST em `config:validate` com corpo JSON, salvo `body` ja em bytes."""
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return request(port, "POST", VALIDATE, content_type=JSON, body=payload, **kwargs)


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    state = build_service(tmp_path, secrets=HMAC_SECRETS)
    state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
    try:
        yield state
    finally:
        state.close()


# --------------------------------------------------------------------------
# Sucesso
# --------------------------------------------------------------------------


class TestSucesso:
    def test_documento_minimo_e_200(self, harness: Harness) -> None:
        reply = post(harness.port, {})
        assert reply.status == 200
        assert reply.json() == SUCCESS_BODY

    def test_documento_completo_adotado_e_200(self, harness: Harness) -> None:
        reply = post(harness.port, FULL_DOCUMENT)
        assert reply.status == 200
        assert reply.json() == SUCCESS_BODY

    def test_regex_valida_e_realmente_compilada(self, harness: Harness) -> None:
        """A regex passa; a mesma rota com regex invalida recusa (proximo bloco).

        As duas juntas provam que a regex e COMPILADA, e nao so aceita pelo
        schema: uma string qualquer no lugar do padrao passaria pelo schema.
        """
        doc = {
            "masking": [
                {
                    "match": "email",
                    "transformer": "regex",
                    "config": {"pattern": r"^(.).*@(.*)$", "replacement": r"\1***@\2"},
                }
            ]
        }
        assert post(harness.port, doc).status == 200

    @pytest.mark.parametrize(
        "config",
        [
            {"transformer": "md5", "config": {}},
            {"transformer": "sha256", "config": {}},
            {"transformer": "sha512", "config": {}},
            {"transformer": "hmac_sha256", "config": {}},
            {"transformer": "fixed", "config": {"value": "REDACTED"}},
            {"transformer": "truncate", "config": {"length": 4}},
            {"transformer": "random", "config": {"strategy": "alphanumeric"}},
            {
                "transformer": "random",
                "config": {"strategy": "digits", "preserve_length": False, "length": 6},
            },
        ],
    )
    def test_cada_transformer_valido_compila(
        self,
        harness: Harness,
        config: dict[str, Any],
    ) -> None:
        doc = {"masking": [{"match": "x", **config}]}
        assert post(harness.port, doc).status == 200

    def test_resposta_tem_exatamente_os_quatro_campos(self, harness: Harness) -> None:
        body = post(harness.port, {}).json()
        assert set(body) == {
            "valid",
            "schema_validated",
            "policy_compiled",
            "database_checks_performed",
        }
        # Nenhum campo de identidade de configuracao nem de efeito.
        for proibido in ("revision", "applied", "config", "secrets", "current_revision"):
            assert proibido not in body

    def test_no_store_e_sem_cors_no_sucesso(self, harness: Harness) -> None:
        reply = post(harness.port, {})
        assert reply.headers["cache-control"] == "no-store"
        assert reply.cors_headers == []

    def test_database_checks_sempre_false(self, harness: Harness) -> None:
        """Nao conecta ao PostgreSQL: a resposta diz isso na propria forma."""
        assert post(harness.port, FULL_DOCUMENT).json()["database_checks_performed"] is False


# --------------------------------------------------------------------------
# Autenticacao e fronteira
# --------------------------------------------------------------------------


class TestAutenticacaoEFronteira:
    def test_sem_token_e_401(self, harness: Harness) -> None:
        reply = post(harness.port, {}, token=None)
        assert reply.status == 401
        assert reply.json()["error"] == "UNAUTHORIZED"

    def test_token_errado_e_401(self, harness: Harness) -> None:
        reply = post(harness.port, {}, token="x" * 40)
        assert reply.status == 401

    def test_token_em_query_string_e_401(self, harness: Harness) -> None:
        reply = request(
            harness.port,
            "POST",
            f"{VALIDATE}?token=admin-token-para-teste-com-40-caracteres",
            token=None,
            content_type=JSON,
            body=b"{}",
        )
        assert reply.status == 401

    def test_token_em_cookie_e_401(self, harness: Harness) -> None:
        reply = post(
            harness.port,
            {},
            token=None,
            headers={"Cookie": "Authorization=admin-token-para-teste-com-40-caracteres"},
        )
        assert reply.status == 401

    def test_sem_token_e_corpo_invalido_ainda_e_401(self, harness: Harness) -> None:
        """A autenticacao roda ANTES do schema: nunca um `422` sem credencial.

        Se o `422` chegasse antes, o schema viraria oraculo para quem nao tem
        token (secao 2).
        """
        reply = post(harness.port, b"{not valid json", token=None)
        assert reply.status == 401
        assert reply.json()["error"] == "UNAUTHORIZED"

    def test_content_type_text_plain_e_415(self, harness: Harness) -> None:
        reply = request(
            harness.port,
            "POST",
            VALIDATE,
            content_type="text/plain",
            body=b"{}",
        )
        assert reply.status == 415
        assert reply.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_json_malformado_e_422_sanitizado(self, harness: Harness) -> None:
        reply = post(harness.port, b"{not json")
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"
        # Sem `str(exc)` do parser, sem trecho do corpo enviado.
        assert "not json" not in reply.text()

    def test_origin_presente_e_403(self, harness: Harness) -> None:
        reply = post(harness.port, {}, headers={"Origin": "https://evil.example"})
        assert reply.status == 403
        assert reply.json()["error"] == "CROSS_ORIGIN_REJECTED"

    def test_referer_presente_e_403(self, harness: Harness) -> None:
        reply = post(harness.port, {}, headers={"Referer": "https://evil.example/p"})
        assert reply.status == 403

    def test_host_alheio_e_400(self, harness: Harness) -> None:
        reply = post(harness.port, {}, host="evil.example:1")
        assert reply.status == 400
        assert reply.json()["error"] == "HOST_NOT_ALLOWED"

    def test_corpo_acima_de_1mib_por_content_length_e_413(self, harness: Harness) -> None:
        big = b'{"x":"' + b"a" * (1024 * 1024 + 10) + b'"}'
        reply = post(harness.port, big)
        assert reply.status == 413
        assert reply.json()["error"] == "PAYLOAD_TOO_LARGE"

    def test_corpo_chunked_acima_de_1mib_e_413(self, tmp_path: Path) -> None:
        """Sem `Content-Length`, cortado em 1 MiB (secao 12.7).

        Exercitado direto sobre a app ASGI completa — fronteira MAIS router —,
        com o corpo entregue em pedacos e `more_body` verdadeiro ate o fim. Isso
        e deterministico: o `BodyLimitMiddleware` conta os bytes que chegam e
        corta assim que a soma passa do limite, sem a corrida de keep-alive que
        um envio por socket cru introduz. O corte generico ja e provado na suite
        de fronteira; aqui prova-se que ele cobre a rota `config:validate`, que
        de fato le o corpo para parsear o JSON.
        """
        app = build_admin_app(
            build_service(tmp_path).service,
            token=TOKEN,
            port=8765,
            secrets=MappingSecretProvider({}),
            database_dsn_env="MASKGW_DATABASE_DSN",
        )
        # 24 pedacos de 64 KiB = 1.5 MiB, todos com `more_body=True` ate o fim:
        # a soma passa de 1 MiB no meio do fluxo.
        chunks = [b"x" * (64 * 1024) for _ in range(24)]
        reply = _drive_chunked(app, VALIDATE, chunks, port=8765)
        assert reply.status == 413
        assert reply.json()["error"] == "PAYLOAD_TOO_LARGE"

    @pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "PATCH", "DELETE"])
    def test_outros_metodos_nao_validam(self, harness: Harness, method: str) -> None:
        """So `POST` valida. Os demais nao executam a validacao.

        `GET`/`HEAD` sem corpo caem no router (405); `PUT`/`PATCH`/`DELETE` com
        `text/plain` sao cortados no `Content-Type` (415). Em nenhum caso a
        funcao de validacao roda — e o que importa e que a rota nao os aceita.
        """
        if method in {"GET", "HEAD"}:
            reply = request(harness.port, method, VALIDATE)
            assert reply.status == 405
        else:
            reply = request(harness.port, method, VALIDATE, content_type="text/plain", body=b"x")
            assert reply.status == 415

    def test_options_e_405_sem_cors(self, harness: Harness) -> None:
        reply = request(harness.port, "OPTIONS", VALIDATE)
        assert reply.status == 405
        assert reply.cors_headers == []


# --------------------------------------------------------------------------
# Schema (SCHEMA_INVALID) vs compilacao (CONFIG_INVALID)
# --------------------------------------------------------------------------


class TestSchemaInvalid:
    def _fields(self, reply: Reply) -> list[dict[str, str]]:
        payload = reply.json()
        assert reply.status == 422
        assert payload["error"] == "SCHEMA_INVALID"
        fields: list[dict[str, str]] = payload.get("fields", [])
        return fields

    def test_expected_revision_e_422_schema(self, harness: Harness) -> None:
        reply = post(harness.port, {"expected_revision": 5})
        fields = self._fields(reply)
        assert any(f["path"] == "body.expected_revision" for f in fields)
        assert all(f["reason"] == "unknown_field" for f in fields)
        # O valor `5` nunca aparece.
        assert "5" not in reply.text()

    def test_campo_desconhecido_no_topo_e_422(self, harness: Harness) -> None:
        assert post(harness.port, {"bogus": 1}).status == 422

    def test_campo_desconhecido_aninhado_e_422(self, harness: Harness) -> None:
        doc = {"masking": [{"match": "x", "transformer": "md5", "bogus": 1}]}
        assert post(harness.port, doc).status == 422

    def test_tipo_errado_e_422(self, harness: Harness) -> None:
        assert post(harness.port, {"revision": "nao-e-int"}).status == 422

    def test_limite_invalido_e_422(self, harness: Harness) -> None:
        # statement_timeout_ms abaixo do minimo.
        doc = {"database": {"statement_timeout_ms": 1, "max_rows": 10}}
        assert post(harness.port, doc).status == 422

    def test_id_ausente_em_documento_adotado_e_schema_invalid(self, harness: Harness) -> None:
        """`revision >= 1` exige `id` em todo item, recusado NO SCHEMA HTTP.

        A regressao: antes desta correcao o schema aceitava o documento (`id`
        opcional), e so `validate_file_config` o recusava, produzindo
        `CONFIG_INVALID`. D-058 classifica "adotado sem ID" como falha de forma,
        `SCHEMA_INVALID`. Conferir o STATUS 422 nao bastava — as duas categorias
        sao 422 —, entao aqui se afirma a categoria, que e o que regride.
        """
        doc = {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5"}]}
        reply = post(harness.port, doc)
        assert reply.status == 422
        assert reply.json()["error"] == "SCHEMA_INVALID"

    def test_id_malformado_e_422(self, harness: Harness) -> None:
        doc = {"masking": [{"id": "nao-e-um-id", "match": "cpf", "transformer": "md5"}]}
        assert post(harness.port, doc).status == 422

    def test_exception_com_transformer_e_422(self, harness: Harness) -> None:
        """Exception nao tem `transformer`/`config`: cai no `extra=forbid`."""
        doc = {"exceptions": [{"match": "x", "transformer": "md5"}]}
        assert post(harness.port, doc).status == 422

    def test_nenhum_422_de_schema_carrega_valor(self, harness: Harness) -> None:
        doc = {"database": {"statement_timeout_ms": 999999999, "max_rows": 10}}
        reply = post(harness.port, doc)
        assert reply.status == 422
        assert "999999999" not in reply.text()


class TestSchemaEstrito:
    """Regressoes de D-058: adotado-sem-ID e coercao de tipo sao SCHEMA_INVALID.

    Duas classes de defeito que o contrato ja exigia e o codigo nao aplicava:

    1. um documento adotado (`revision >= 1`) sem `id` em algum item era aceito
       pelo schema e so recusado depois, como `CONFIG_INVALID`;
    2. o schema coagia tipos JSON errados — `"1"` -> `1`, `1` -> `True`,
       `True` -> `1` — em vez de recusa-los como `SCHEMA_INVALID`.

    Ambas devem falhar no BINDING, antes de `validate_candidate`, e a resposta
    nunca pode carregar o valor rejeitado.
    """

    def _assert_schema_invalid(self, reply: Reply) -> None:
        payload = reply.json()
        assert reply.status == 422
        assert payload["error"] == "SCHEMA_INVALID"

    # -- adotado sem ID -> SCHEMA_INVALID, sem chegar a validacao/compilacao --

    def test_regra_adotada_sem_id_e_schema_invalid(self, harness: Harness) -> None:
        doc = {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5"}]}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_exception_adotada_sem_id_e_schema_invalid(self, harness: Harness) -> None:
        doc = {"revision": 2, "exceptions": [{"match": "tipo_cpf"}]}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_adotado_com_todos_os_ids_e_200(self, harness: Harness) -> None:
        """Contraparte: com ID em todo item, o documento adotado passa o schema."""
        assert post(harness.port, FULL_DOCUMENT).status == 200

    def test_adotado_sem_id_nao_chega_a_validacao_nem_compilacao(self, tmp_path: Path) -> None:
        """A recusa acontece no binding: `validate_file_config` e
        `compile_policy` nao sao chamados para o documento adotado sem ID."""
        state = build_service(tmp_path, secrets=HMAC_SECRETS)
        state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
        try:
            with (
                patch("maskgw.admin.http.validate.validate_file_config") as vfc,
                patch("maskgw.admin.http.validate.compile_policy") as cp,
            ):
                reply = post(
                    state.port,
                    {"revision": 1, "masking": [{"match": "cpf", "transformer": "md5"}]},
                )
            assert reply.status == 422
            assert reply.json()["error"] == "SCHEMA_INVALID"
            assert vfc.call_count == 0
            assert cp.call_count == 0
        finally:
            state.close()

    def test_adotado_sem_id_nao_vaza_id_padrao_nem_indice(self, harness: Harness) -> None:
        """A resposta cita so o caminho do campo e um reason fechado."""
        doc = {"revision": 7, "masking": [{"match": "cpf", "transformer": "md5"}]}
        reply = post(harness.port, doc)
        text = reply.text()
        # Nenhum indice, nenhum valor de match, nenhuma revision submetida, nada
        # do texto interno do validator.
        assert "cpf" not in text
        assert "7" not in text
        assert "adopted" not in text.lower()
        assert "masking[0]" not in text

    # -- coercao de tipo -> SCHEMA_INVALID ----------------------------------

    def test_revision_string_numerica_e_schema_invalid(self, harness: Harness) -> None:
        self._assert_schema_invalid(post(harness.port, {"revision": "1"}))

    def test_statement_timeout_string_e_schema_invalid(self, harness: Harness) -> None:
        doc = {"database": {"statement_timeout_ms": "100", "max_rows": 1}}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_max_rows_string_e_schema_invalid(self, harness: Harness) -> None:
        doc = {"database": {"statement_timeout_ms": 100, "max_rows": "1"}}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_case_sensitive_um_nao_e_booleano(self, harness: Harness) -> None:
        """`0`/`1` JSON nao sao aceitos como booleano."""
        doc = {"masking": [{"match": "cpf", "transformer": "md5", "case_sensitive": 1}]}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_case_sensitive_zero_nao_e_booleano(self, harness: Harness) -> None:
        doc = {"exceptions": [{"match": "x", "case_sensitive": 0}]}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_revision_booleano_nao_e_inteiro(self, harness: Harness) -> None:
        """Um booleano JSON nao e aceito como inteiro."""
        self._assert_schema_invalid(post(harness.port, {"revision": True}))

    def test_case_sensitive_booleano_continua_aceito(self, harness: Harness) -> None:
        """A contraparte: o booleano legitimo passa."""
        doc = {"masking": [{"match": "x", "transformer": "md5", "case_sensitive": True}]}
        assert post(harness.port, doc).status == 200

    @pytest.mark.parametrize("mode", ["contains", "exact"])
    def test_enum_textual_json_continua_aceito(self, harness: Harness, mode: str) -> None:
        """`strict` por campo NAO alcanca `mode`: o enum textual JSON funciona."""
        doc = {"masking": [{"match": "x", "transformer": "md5", "mode": mode}]}
        assert post(harness.port, doc).status == 200

    def test_mode_inteiro_e_schema_invalid(self, harness: Harness) -> None:
        """Ainda assim, um `mode` que nao e string do enum e recusado."""
        doc = {"masking": [{"match": "x", "transformer": "md5", "mode": 0}]}
        self._assert_schema_invalid(post(harness.port, doc))

    def test_coercao_recusada_nao_vaza_o_valor(self, harness: Harness) -> None:
        """Nenhum valor rejeitado aparece na resposta."""
        doc = {"revision": "12345"}
        reply = post(harness.port, doc)
        assert reply.status == 422
        assert "12345" not in reply.text()


class TestConfigInvalid:
    def _assert_config_invalid(self, reply: Reply) -> None:
        payload = reply.json()
        assert reply.status == 422
        assert payload["error"] == "CONFIG_INVALID"
        # CONFIG_INVALID nao lista campos nem cita a causa.
        assert "fields" not in payload
        assert payload["detail"] == "The candidate configuration is not valid."

    def test_regex_invalida_e_config_invalid(self, harness: Harness) -> None:
        doc = {
            "masking": [
                {
                    "match": "x",
                    "transformer": "regex",
                    "config": {"pattern": "([", "replacement": "y"},
                }
            ]
        }
        self._assert_config_invalid(post(harness.port, doc))

    def test_transformer_inexistente_e_config_invalid(self, harness: Harness) -> None:
        doc = {"masking": [{"match": "x", "transformer": "nao_existe"}]}
        self._assert_config_invalid(post(harness.port, doc))

    def test_parametro_obrigatorio_ausente_e_config_invalid(self, harness: Harness) -> None:
        doc = {"masking": [{"match": "x", "transformer": "fixed"}]}
        self._assert_config_invalid(post(harness.port, doc))

    def test_parametro_desconhecido_e_config_invalid(self, harness: Harness) -> None:
        doc = {
            "masking": [
                {"match": "x", "transformer": "fixed", "config": {"value": "y", "bogus": 1}}
            ]
        }
        self._assert_config_invalid(post(harness.port, doc))

    def test_hmac_sem_secret_e_config_invalid(self, tmp_path: Path) -> None:
        """Sem `MASKGW_HMAC_KEY` no provider, `hmac_sha256` recusa na compilacao."""
        state = build_service(tmp_path, secrets=MappingSecretProvider({}))
        state.start(secret_values={})
        try:
            doc = {"masking": [{"match": "x", "transformer": "hmac_sha256"}]}
            self._assert_config_invalid(post(state.port, doc))
        finally:
            state.close()

    def test_config_invalid_nao_vaza_a_causa(self, harness: Harness) -> None:
        """Nem o nome do transformer, nem o padrao, nem a mensagem do pglast."""
        doc = {
            "masking": [
                {
                    "match": "x",
                    "transformer": "regex",
                    "config": {"pattern": "(?P<bad", "replacement": "y"},
                }
            ]
        }
        reply = post(harness.port, doc)
        text = reply.text()
        assert "(?P<bad" not in text
        assert "regex" not in text
        assert "pglast" not in text.lower()


# --------------------------------------------------------------------------
# Ausencia de efeitos
# --------------------------------------------------------------------------


def _drive_chunked(
    app: Any,
    path: str,
    chunks: list[bytes],
    *,
    port: int,
) -> Reply:
    """Invoca a app ASGI direto, entregando o corpo em pedacos, sem socket.

    Deterministico: nao ha corrida de keep-alive nem reset a meio caminho. Cada
    pedaco chega com `more_body=True` ate o ultimo, exatamente como um corpo
    chunked sem `Content-Length` chega ao ASGI. E o mesmo padrao do `drive` da
    suite de fronteira, aqui sobre a app completa (fronteira + router).
    """

    async def run() -> Reply:
        sent: list[dict[str, Any]] = []
        pending = list(chunks)

        async def receive() -> dict[str, Any]:
            if pending:
                body = pending.pop(0)
                return {"type": "http.request", "body": body, "more_body": bool(pending)}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        headers = [
            (b"host", f"127.0.0.1:{port}".encode()),
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {TOKEN}".encode()),
        ]
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", port),
        }
        await app(scope, receive, send)

        status = 0
        response_headers: dict[str, str] = {}
        body = b""
        for message in sent:
            if message["type"] == "http.response.start":
                status = int(message["status"])
                response_headers = {
                    key.decode().lower(): value.decode() for key, value in message["headers"]
                }
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
        return Reply(status=status, headers=response_headers, body=body)

    return asyncio.run(run())


def _admin_thread_names() -> set[str]:
    return {t.name for t in threading.enumerate() if t.name == "maskgw-admin-http"}


class TestAusenciaDeEfeitos:
    """Para sucesso E para cada falha: nada muda no processo."""

    CASES: ClassVar[dict[str, Any]] = {
        "sucesso_minimo": {},
        "sucesso_completo": FULL_DOCUMENT,
        "schema_expected_revision": {"expected_revision": 1},
        "schema_campo_desconhecido": {"bogus": 1},
        "schema_id_malformado": {"masking": [{"id": "x", "match": "a", "transformer": "md5"}]},
        "schema_adotado_sem_id": {"revision": 1, "masking": [{"match": "a", "transformer": "md5"}]},
        "schema_revision_string": {"revision": "1"},
        "schema_case_sensitive_int": {
            "masking": [{"match": "a", "transformer": "md5", "case_sensitive": 1}]
        },
        "config_regex": {
            "masking": [
                {
                    "match": "x",
                    "transformer": "regex",
                    "config": {"pattern": "(", "replacement": "y"},
                }
            ]
        },
        "config_transformer": {"masking": [{"match": "x", "transformer": "nope"}]},
        "config_param_ausente": {"masking": [{"match": "x", "transformer": "fixed"}]},
    }

    @pytest.mark.parametrize("case", list(CASES))
    def test_nenhum_efeito_para_cada_caso(self, tmp_path: Path, case: str) -> None:
        state = build_service(tmp_path, FULL_DOCUMENT, secrets=HMAC_SECRETS)
        state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
        try:
            svc = state.service
            registry = state.registry

            before_bytes = state.config_path.read_bytes()
            before_current = registry.current
            before_revision = svc.revision
            before_digest = svc.reference_digest
            before_ops = svc.operations_total
            before_queries = svc.queries_total
            before_retired = svc.retired_runtimes_open
            before_adapters = len(type(state.adapter).instances)
            before_threads = _admin_thread_names()

            post(state.port, self.CASES[case])

            # Arquivo, revision, identidade do runtime e digest: intactos.
            assert state.config_path.read_bytes() == before_bytes
            assert svc.revision == before_revision
            assert registry.current is before_current
            assert svc.reference_digest == before_digest
            # Contadores: a validacao nao e uma operacao de escrita nem uma query.
            assert svc.operations_total == before_ops
            assert svc.queries_total == before_queries
            assert svc.retired_runtimes_open == before_retired
            # Nenhum adapter novo: a rota nunca constroi `PostgresAdapter`.
            assert len(type(state.adapter).instances) == before_adapters
            # O adapter existente nao foi conectado nem executou SQL.
            assert state.adapter.connect_calls == 0
            assert state.adapter.execute_calls == 0
            assert state.adapter.close_calls == 0
            # Nenhuma thread administrativa a mais.
            assert _admin_thread_names() == before_threads
        finally:
            state.close()

    def test_a_rota_nao_le_snapshot(self, tmp_path: Path) -> None:
        """A funcao de validacao nao recebe o `service`, entao nao chama
        `snapshot()`. Um espiao no metodo prova que ele nao e tocado."""
        state = build_service(tmp_path, secrets=HMAC_SECRETS)
        state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
        try:
            calls = 0
            original = type(state.service).snapshot

            def counting(self: Any) -> Any:
                nonlocal calls
                calls += 1
                return original(self)

            with patch.object(type(state.service), "snapshot", counting):
                post(state.port, FULL_DOCUMENT)
                post(state.port, {"masking": [{"match": "x", "transformer": "nope"}]})

            assert calls == 0
        finally:
            state.close()

    def test_a_secao_critica_nunca_e_adquirida(self, tmp_path: Path) -> None:
        """`operations_total` so cresce sob a secao critica. Se a rota entrasse
        nela, o contador subiria — e nao sobe."""
        state = build_service(tmp_path, FULL_DOCUMENT, secrets=HMAC_SECRETS)
        state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
        try:
            before = state.service.operations_total
            for _ in range(5):
                post(state.port, FULL_DOCUMENT)
                post(state.port, {"masking": [{"match": "x", "transformer": "nope"}]})
            assert state.service.operations_total == before
        finally:
            state.close()


# --------------------------------------------------------------------------
# Leakage
# --------------------------------------------------------------------------


class TestLeakage:
    def test_nenhum_secret_em_sucesso_nem_em_erro(self, harness: Harness) -> None:
        replies = [
            post(harness.port, FULL_DOCUMENT),
            post(harness.port, {"masking": [{"match": "x", "transformer": "hmac_sha256"}]}),
            post(harness.port, {"expected_revision": 1}),
        ]
        for reply in replies:
            blob = reply.text() + " " + " ".join(f"{k}:{v}" for k, v in reply.headers.items())
            assert SENSITIVE_HMAC not in blob
            for part in DSN_PARTS:
                assert part not in blob

    def test_erro_interno_nao_carrega_str_exc(self, tmp_path: Path) -> None:
        """Uma falha inesperada na compilacao vira `INTERNAL_ERROR` sanitizado.

        Injeta uma excecao NAO-`ConfigError` dentro de `compile_policy` e
        confirma que o corpo nao carrega nada dela.
        """
        state = build_service(tmp_path, secrets=HMAC_SECRETS)
        state.start(secret_values={"MASKGW_HMAC_KEY": SENSITIVE_HMAC})
        marker = "segredo-que-nao-pode-vazar-xyz"
        try:

            def boom(*_a: Any, **_k: Any) -> Any:
                raise RuntimeError(marker)

            with patch("maskgw.admin.http.validate.compile_policy", boom):
                reply = post(state.port, {})

            assert reply.status == 500
            assert reply.json()["error"] == "INTERNAL_ERROR"
            assert marker not in reply.text()
        finally:
            state.close()


# --------------------------------------------------------------------------
# A funcao de validacao, isolada
# --------------------------------------------------------------------------


class TestFuncaoIsolada:
    def test_sucesso_devolve_o_modelo_congelado(self) -> None:
        result = validate_candidate(ConfigValidateRequest(), secrets=MappingSecretProvider({}))
        assert isinstance(result, ConfigValidateResponse)
        assert result.valid is True
        assert result.database_checks_performed is False
        with pytest.raises(ValidationError):
            result.valid = False  # frozen: reatribuir levanta

    def test_config_invalid_tem_cause_e_context_nulos(self) -> None:
        """D-017: o erro sanitizado nao encadeia a excecao interna."""
        req = ConfigValidateRequest.model_validate(
            {"masking": [{"match": "x", "transformer": "nope"}]}
        )
        with pytest.raises(AdminError) as raised:
            validate_candidate(req, secrets=MappingSecretProvider({}))
        assert raised.value.category is AdminErrorCategory.CONFIG_INVALID
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
