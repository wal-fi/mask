"""Fase 9, Etapa 7 (D-109): framing limitado do startup, sem socket.

Prova o perfil minimo: protocolo 3.0 exato, SSLRequest de 8 bytes, GSSENC e
Cancel recusados, so quatro chaves no StartupMessage, limites aplicados antes
de alocar o corpo, alias decidido depois (nunca aqui) e erros fechados.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

import pytest

from maskgw.pgwire import framing
from maskgw.pgwire.errors import (
    PgwireErrorCategory,
    PgwireStartupError,
    error_response,
)

PV = PgwireErrorCategory.PROTOCOL_VIOLATION
UNSUPPORTED = PgwireErrorCategory.FEATURE_NOT_SUPPORTED


def startup_body(*pairs: tuple[bytes, bytes], code: int = 196608) -> bytes:
    payload = b"".join(key + b"\x00" + value + b"\x00" for key, value in pairs)
    return struct.pack("!I", code) + payload + b"\x00"


def category_of(
    call: Callable[..., object], *args: object, **kwargs: object
) -> PgwireErrorCategory:
    with pytest.raises(PgwireStartupError) as info:
        call(*args, **kwargs)
    error = info.value
    assert error.__cause__ is None
    assert error.__context__ is None
    return error.category


class TestInitialPacket:
    @pytest.mark.parametrize("length", [0, 3, 7, 10_001, 0xFFFFFFFF])
    def test_comprimento_fora_do_limite_e_recusado_antes_do_corpo(self, length):
        assert category_of(framing.initial_length, struct.pack("!I", length)) is PV

    @pytest.mark.parametrize("length", [8, 10_000])
    def test_limites_inclusivos(self, length):
        assert framing.initial_length(struct.pack("!I", length)) == length

    def test_cabecalho_truncado(self):
        assert category_of(framing.initial_length, b"\x00\x00\x08") is PV

    def test_ssl_request_exato(self):
        body = struct.pack("!I", framing.SSL_REQUEST_CODE)
        assert framing.classify_initial(body) is framing.InitialKind.SSL_REQUEST

    def test_ssl_request_com_bytes_extras_e_violacao(self):
        body = struct.pack("!I", framing.SSL_REQUEST_CODE) + b"\x00"
        assert category_of(framing.classify_initial, body) is PV

    @pytest.mark.parametrize("code", [80877104, 80877102])
    def test_gssenc_e_cancel_recusados(self, code):
        body = struct.pack("!I", code) + b"\x00" * 8
        assert category_of(framing.classify_initial, body) is UNSUPPORTED

    @pytest.mark.parametrize("code", [(3 << 16) | 1, (3 << 16) | 2, (3 << 16) | 0xFFFF])
    def test_versao_menor_diferente_de_zero_recusada_sem_negociacao(self, code):
        body = startup_body((b"user", b"u"), code=code)
        assert category_of(framing.classify_initial, body) is UNSUPPORTED

    @pytest.mark.parametrize("code", [2 << 16, 4 << 16, 0, 1234 << 16])
    def test_codigo_desconhecido_e_violacao(self, code):
        assert category_of(framing.classify_initial, struct.pack("!I", code)) is PV


class TestStartupMessage:
    def test_perfil_minimo_aceito(self):
        message = framing.parse_startup(
            startup_body(
                (b"user", b"gw"),
                (b"database", b"crm"),
                (b"application_name", "aplicação".encode()),
                (b"client_encoding", b"UTF8"),
            )
        )
        assert message == framing.StartupMessage("gw", "crm", "aplicação")

    def test_database_ausente_nao_falha_no_framing(self):
        # O alias ausente e decidido depois da prova, com falha uniforme.
        message = framing.parse_startup(startup_body((b"user", b"gw")))
        assert message.database is None
        assert not framing.valid_alias(message.database)

    @pytest.mark.parametrize(
        "key", [b"options", b"replication", b"DateStyle", b"TimeZone", b"_pq_.x", b"search_path"]
    )
    def test_chave_fora_do_perfil_e_recusada(self, key):
        body = startup_body((b"user", b"gw"), (key, b"v"))
        assert category_of(framing.parse_startup, body) is UNSUPPORTED

    @pytest.mark.parametrize("encoding", [b"LATIN1", b"SQL_ASCII", b"WIN1252", b""])
    def test_client_encoding_nao_utf8_recusado(self, encoding):
        body = startup_body((b"user", b"gw"), (b"client_encoding", encoding))
        assert category_of(framing.parse_startup, body) is UNSUPPORTED

    @pytest.mark.parametrize("encoding", [b"UTF8", b"utf8", b"UTF-8", b"unicode"])
    def test_client_encoding_utf8_aceito(self, encoding):
        body = startup_body((b"user", b"gw"), (b"client_encoding", encoding))
        assert framing.parse_startup(body).user == "gw"

    @pytest.mark.parametrize(
        "body",
        [
            startup_body((b"database", b"crm")),  # sem user
            startup_body((b"user", b"")),  # user vazio
            startup_body((b"user", b"a"), (b"user", b"b")),  # duplicata
            startup_body((b"user", b"\xff\xfe")),  # UTF-8 invalido
            startup_body((b"user", b"gw"), (b"\xc3", b"x")),  # chave invalida
            startup_body((b"user", b"x" * 257)),  # valor > 256
            startup_body((b"user", b"gw"), (b"k" * 64, b"x")),  # chave > 63
            struct.pack("!I", 196608) + b"user\x00gw\x00",  # sem terminador
            struct.pack("!I", 196608) + b"user\x00gw\x00database\x00",  # impar
            struct.pack("!I", 196608) + b"\x00",  # nenhum par
            struct.pack("!I", 196608) + b"\x00\x00",  # chave vazia
        ],
    )
    def test_forma_invalida_e_violacao(self, body):
        assert category_of(framing.parse_startup, body) is PV

    def test_mais_de_32_pares_recusado(self):
        pairs = [(b"user", b"gw")] + [(f"k{i}".encode(), b"v") for i in range(32)]
        assert category_of(framing.parse_startup, startup_body(*pairs)) is PV

    def test_erro_nao_carrega_a_entrada(self):
        body = startup_body((b"user", b"gw"), (b"segredo-canario", b"valor-canario"))
        with pytest.raises(PgwireStartupError) as info:
            framing.parse_startup(body)
        text = str(info.value) + repr(info.value) + repr(info.value.args)
        assert "canario" not in text


class TestAlias:
    @pytest.mark.parametrize("alias", ["crm", "a", "crm_prod-2", "0x", "a" * 63])
    def test_alias_valido(self, alias):
        assert framing.valid_alias(alias)

    @pytest.mark.parametrize("alias", [None, "", "CRM", "-x", "_x", "a" * 64, "crm.x", "çrm"])
    def test_alias_invalido(self, alias):
        assert not framing.valid_alias(alias)


class TestSaslMessages:
    @pytest.mark.parametrize("length", [0, 3, 2_053, 0x7FFFFFFF])
    def test_mensagem_sasl_fora_do_limite(self, length):
        header = b"p" + struct.pack("!I", length)
        assert category_of(framing.message_length, header, expected_type=b"p") is PV

    def test_tipo_inesperado_e_violacao(self):
        header = b"Q" + struct.pack("!I", 10)
        assert category_of(framing.message_length, header, expected_type=b"p") is PV

    def test_limite_inclusivo(self):
        header = b"p" + struct.pack("!I", 2_048)
        assert framing.message_length(header, expected_type=b"p") == 2_044

    def test_sasl_initial_valido(self):
        data = b"n,,n=,r=abcdefgh"
        body = b"SCRAM-SHA-256\x00" + struct.pack("!i", len(data)) + data
        assert framing.parse_sasl_initial(body) == ("SCRAM-SHA-256", data)

    @pytest.mark.parametrize(
        "body",
        [
            b"",
            b"\x00" + struct.pack("!i", 0),
            b"SCRAM-SHA-256",  # sem NUL
            b"SCRAM-SHA-256\x00\x00\x00",  # int32 truncado
            b"SCRAM-SHA-256\x00" + struct.pack("!i", -1),
            b"SCRAM-SHA-256\x00" + struct.pack("!i", 5) + b"abc",
            b"SCRAM-SHA-256\x00" + struct.pack("!i", 1) + b"abc",
            "SCRAM-ÇHA\x00".encode() + struct.pack("!i", 0),
            b"M" * 33 + b"\x00" + struct.pack("!i", 0),
        ],
    )
    def test_sasl_initial_invalido(self, body):
        assert category_of(framing.parse_sasl_initial, body) is PV


class TestServerMessages:
    def test_authentication_sasl_lista_mecanismos(self):
        message = framing.authentication_sasl(("SCRAM-SHA-256-PLUS", "SCRAM-SHA-256"))
        body = struct.pack("!I", 10) + b"SCRAM-SHA-256-PLUS\x00SCRAM-SHA-256\x00\x00"
        assert message == b"R" + struct.pack("!I", len(body) + 4) + body

    def test_authentication_ok(self):
        assert framing.authentication_ok() == b"R\x00\x00\x00\x08\x00\x00\x00\x00"

    @pytest.mark.parametrize(
        ("category", "code"),
        [
            (PgwireErrorCategory.AUTHENTICATION_FAILED, b"28P01"),
            (PgwireErrorCategory.PROTOCOL_VIOLATION, b"08P01"),
            (PgwireErrorCategory.FEATURE_NOT_SUPPORTED, b"0A000"),
            (PgwireErrorCategory.INTERNAL_ERROR, b"XX000"),
        ],
    )
    def test_error_response_fixo(self, category, code):
        message = error_response(category)
        assert message[:1] == b"E"
        (length,) = struct.unpack("!I", message[1:5])
        assert length == len(message) - 1
        assert b"SFATAL\x00VFATAL\x00C" + code + b"\x00M" in message
        assert message.endswith(b"\x00\x00")
