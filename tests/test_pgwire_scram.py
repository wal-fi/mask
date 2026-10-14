"""Fase 9, Etapa 7 (D-109): credencial e troca SCRAM do servidor, sem socket.

Prova:

- o vetor normativo da RFC 7677 §3, byte a byte;
- a identidade vem do `user` do StartupMessage; o `n=` e ignorado, pode ser
  vazio e entra no AuthMessage exatamente como chegou;
- usuario desconhecido usa verifier simulado com salt publico de mesmo formato
  e as mesmas iteracoes, e falha igual a senha errada e a alias recusado;
- consistencia mecanismo / flag gs2 / channel binding, incluindo downgrade;
- forma invalida e `PROTOCOL_VIOLATION`; maquina de uso unico;
- SASLprep pela `scramp`: senha proibida recusada ao preparar, sem fallback;
- erros e `repr` sem segredo, sem `__cause__`/`__context__`.

Nao ha prova de tempo constante: as comparacoes usam `compare_digest` e a
decisao e tomada no fim, mas nenhuma medicao de tempo e feita aqui.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Callable

import pytest
from scramp import ScramMechanism  # type: ignore[import-untyped]

from maskgw.errors import ConfigError
from maskgw.pgwire.credential import (
    SCRAM_ITERATIONS,
    ScramVerifier,
    prepare_principal,
)
from maskgw.pgwire.errors import PgwireErrorCategory, PgwireStartupError
from maskgw.pgwire.scram import (
    SCRAM_SHA_256,
    SCRAM_SHA_256_PLUS,
    ScramServerExchange,
)

PV = PgwireErrorCategory.PROTOCOL_VIOLATION
AUTH = PgwireErrorCategory.AUTHENTICATION_FAILED
PASSWORD = "senha-de-teste-canario"
USER = "gwuser"
CLIENT_NONCE = "rOprNGfwEbeRWgbNEkqO"
CB = hashlib.sha256(b"certificado-de-teste").digest()
PLUS_FLAG = "p=tls-server-end-point"
SERVER_FIRST = re.compile(r"r=([\x21-\x2b\x2d-\x7e]+),s=([A-Za-z0-9+/]+={0,2}),i=(\d+)")


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def client_final(
    password: str,
    server_first: bytes,
    bare: str,
    *,
    header: str = "n,,",
    cb: bytes = b"",
    nonce: str | None = None,
) -> tuple[bytes, bytes]:
    """Cliente SCRAM minimo do teste: client-final e a assinatura esperada."""
    match = SERVER_FIRST.fullmatch(server_first.decode("ascii"))
    assert match is not None
    full_nonce, salt, iterations = match.group(1), match.group(2), int(match.group(3))
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    without_proof = f"c={b64(header.encode() + cb)},r={nonce or full_nonce}"
    auth = f"{bare},{server_first.decode()},{without_proof}".encode()
    signature = hmac.new(stored, auth, hashlib.sha256).digest()
    proof = bytes(a ^ b for a, b in zip(client_key, signature, strict=True))
    expected = b"v=" + base64.b64encode(hmac.new(server_key, auth, hashlib.sha256).digest())
    return f"{without_proof},p={b64(proof)}".encode(), expected


def category_of(
    call: Callable[..., object], *args: object, **kwargs: object
) -> PgwireErrorCategory:
    with pytest.raises(PgwireStartupError) as info:
        call(*args, **kwargs)
    error = info.value
    assert error.__cause__ is None
    assert error.__context__ is None
    return error.category


@pytest.fixture(scope="module")
def principal():
    return prepare_principal(USER, PASSWORD)


def run(
    verifier: ScramVerifier,
    *,
    password: str = PASSWORD,
    mechanism: str = SCRAM_SHA_256,
    header: str = "n,,",
    bare: str = f"n=,r={CLIENT_NONCE}",
    channel_binding: bytes | None = None,
    client_cb: bytes = b"",
    identity_accepted: bool = True,
) -> bytes:
    exchange = ScramServerExchange(verifier, channel_binding=channel_binding)
    server_first = exchange.client_first(mechanism, (header + bare).encode())
    final, expected = client_final(password, server_first, bare, header=header, cb=client_cb)
    result = exchange.client_final(final, identity_accepted=identity_accepted)
    assert result == expected
    return result


class TestRfc7677Vector:
    def test_vetor_normativo(self):
        salt = base64.b64decode("W22ZaJ0SNY7soEsUEjb6gQ==")
        _, stored, server, iterations = ScramMechanism("SCRAM-SHA-256").make_auth_info(
            "pencil", iteration_count=4096, salt=salt
        )
        verifier = ScramVerifier(
            salt=salt, iterations=iterations, stored_key=stored, server_key=server, real=True
        )
        exchange = ScramServerExchange(
            verifier, channel_binding=None, server_nonce="%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0"
        )
        server_first = exchange.client_first(SCRAM_SHA_256, b"n,,n=user,r=rOprNGfwEbeRWgbNEkqO")
        assert server_first == (
            b"r=rOprNGfwEbeRWgbNEkqO%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0,"
            b"s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096"
        )
        server_final = exchange.client_final(
            b"c=biws,r=rOprNGfwEbeRWgbNEkqO%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0,"
            b"p=dHzbZapWIk4jUhN+Ute9ytag9zjfMHgsqmmiz7AndVQ=",
            identity_accepted=True,
        )
        assert server_final == b"v=6rriTRBi23WpRR/wtup+mMhUZUn/dB5nLTJRsjl95G4="


class TestIdentityAndUniformFailure:
    def test_n_vazio_do_libpq_autentica(self, principal):
        run(principal.verifier_for(USER))

    @pytest.mark.parametrize("name", ["outro", "a=2Cb=3Dc", "usuário", USER])
    def test_n_e_ignorado_e_nao_reescrito(self, principal, name):
        # A identidade e o user do Startup; o `n=` entra no AuthMessage como veio.
        run(principal.verifier_for(USER), bare=f"n={name},r={CLIENT_NONCE}")

    def test_senha_errada(self, principal):
        assert category_of(run, principal.verifier_for(USER), password="errada") is AUTH

    def test_usuario_desconhecido_mesmo_com_a_senha_certa(self, principal):
        assert category_of(run, principal.verifier_for("desconhecido")) is AUTH

    def test_alias_recusado_mesmo_com_a_senha_certa(self, principal):
        verifier = principal.verifier_for(USER)
        assert category_of(run, verifier, identity_accepted=False) is AUTH

    def test_as_tres_falhas_sao_indistinguiveis(self, principal):
        errors = []
        for verifier, password, accepted in (
            (principal.verifier_for(USER), "errada", True),
            (principal.verifier_for("desconhecido"), PASSWORD, True),
            (principal.verifier_for(USER), PASSWORD, False),
        ):
            with pytest.raises(PgwireStartupError) as info:
                run(verifier, password=password, identity_accepted=accepted)
            errors.append((type(info.value), info.value.args, info.value.category))
        assert len(set(errors)) == 1

    def test_verifier_simulado_tem_o_mesmo_formato_publico(self, principal):
        real = principal.verifier_for(USER)
        mock = principal.verifier_for("desconhecido")
        assert real.real is True
        assert mock.real is False
        assert len(mock.salt) == len(real.salt) == 16
        assert mock.iterations == real.iterations == SCRAM_ITERATIONS
        assert len(mock.stored_key) == len(real.stored_key) == 32
        assert len(mock.server_key) == len(real.server_key) == 32

    def test_salt_e_iteracoes_simulados_identicos_ao_real(self, principal):
        real = principal.verifier_for(USER)
        for user in ("x", "y", "desconhecido"):
            mock = principal.verifier_for(user)
            assert mock.salt == real.salt
            assert mock.iterations == real.iterations
            assert mock.stored_key != real.stored_key
            assert mock.server_key != real.server_key

    def test_chaves_simuladas_estaveis_por_usuario_e_por_processo(self, principal):
        assert principal.verifier_for("x").stored_key == principal.verifier_for("x").stored_key
        assert principal.verifier_for("x").stored_key != principal.verifier_for("y").stored_key
        other = prepare_principal(USER, PASSWORD)
        assert other.verifier_for("x").stored_key != principal.verifier_for("x").stored_key

    def test_server_first_simulado_e_real_diferem_so_no_nonce(self, principal):
        materials = set()
        for user in (USER, "desconhecido"):
            exchange = ScramServerExchange(principal.verifier_for(user), channel_binding=None)
            first = exchange.client_first(SCRAM_SHA_256, f"n,,n=,r={CLIENT_NONCE}".encode())
            match = SERVER_FIRST.fullmatch(first.decode())
            assert match is not None
            assert len(base64.b64decode(match.group(2))) == 16
            assert match.group(3) == "4096"
            materials.add((match.group(2), match.group(3)))
        assert len(materials) == 1


class TestNonce:
    def test_nonce_do_servidor_imprevisivel(self, principal):
        suffixes = set()
        for _ in range(50):
            exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
            first = exchange.client_first(SCRAM_SHA_256, f"n,,n=,r={CLIENT_NONCE}".encode())
            match = SERVER_FIRST.fullmatch(first.decode())
            assert match is not None
            nonce = match.group(1)
            assert nonce.startswith(CLIENT_NONCE)
            suffix = nonce[len(CLIENT_NONCE) :]
            assert len(base64.b64decode(suffix, validate=True)) == 18
            suffixes.add(suffix)
        assert len(suffixes) == 50

    def test_nonce_adulterado_no_final(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256, ("n,," + bare).encode())
        final, _ = client_final(PASSWORD, first, bare, nonce=CLIENT_NONCE + "outro")
        assert category_of(exchange.client_final, final, identity_accepted=True) is AUTH

    @pytest.mark.parametrize("nonce", ["curto7c", "x" * 257, "abc\x7fdefgh", "abcdéfghi", ""])
    def test_nonce_do_cliente_fora_da_forma(self, principal, nonce):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        data = f"n,,n=,r={nonce}".encode()
        assert category_of(exchange.client_first, SCRAM_SHA_256, data) is PV


class TestChannelBinding:
    def test_mecanismos_oferecidos(self, principal):
        verifier = principal.verifier_for(USER)
        assert ScramServerExchange(verifier, channel_binding=None).mechanisms == (SCRAM_SHA_256,)
        assert ScramServerExchange(verifier, channel_binding=CB).mechanisms == (
            SCRAM_SHA_256_PLUS,
            SCRAM_SHA_256,
        )

    def test_plus_com_o_binding_certo(self, principal):
        run(
            principal.verifier_for(USER),
            mechanism=SCRAM_SHA_256_PLUS,
            header=f"{PLUS_FLAG},,",
            channel_binding=CB,
            client_cb=CB,
        )

    def test_plus_com_binding_de_outro_certificado(self, principal):
        other = hashlib.sha256(b"outro").digest()
        result = category_of(
            run,
            principal.verifier_for(USER),
            mechanism=SCRAM_SHA_256_PLUS,
            header=f"{PLUS_FLAG},,",
            channel_binding=CB,
            client_cb=other,
        )
        assert result is AUTH

    def test_sha256_com_n_quando_plus_oferecido(self, principal):
        # Cliente com channel_binding=disable: legitimo, sem binding.
        run(principal.verifier_for(USER), channel_binding=CB)

    def test_y_sem_plus_oferecido(self, principal):
        run(principal.verifier_for(USER), header="y,,")

    @pytest.mark.parametrize(
        ("mechanism", "header", "binding"),
        [
            (SCRAM_SHA_256, "y,,", CB),  # downgrade
            (SCRAM_SHA_256, f"{PLUS_FLAG},,", CB),  # p= sem -PLUS
            (SCRAM_SHA_256, f"{PLUS_FLAG},,", None),
            (SCRAM_SHA_256_PLUS, "n,,", CB),  # -PLUS sem p=
            (SCRAM_SHA_256_PLUS, "y,,", CB),
            (SCRAM_SHA_256_PLUS, "p=tls-unique,,", CB),
            (SCRAM_SHA_256_PLUS, f"{PLUS_FLAG},,", None),  # -PLUS nao oferecido
            ("SCRAM-SHA-1", "n,,", None),
            ("PLAIN", "n,,", None),
            ("MD5", "n,,", None),
        ],
    )
    def test_combinacoes_inconsistentes(self, principal, mechanism, header, binding):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=binding)
        data = f"{header}n=,r={CLIENT_NONCE}".encode()
        assert category_of(exchange.client_first, mechanism, data) is PV

    def test_c_de_sha256_nao_vale_para_plus(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=CB)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256_PLUS, f"{PLUS_FLAG},,{bare}".encode())
        final, _ = client_final(PASSWORD, first, bare, header="n,,")
        assert category_of(exchange.client_final, final, identity_accepted=True) is AUTH


class TestMessageShape:
    @pytest.mark.parametrize(
        "data",
        [
            b"n,a=admin,n=,r=abcdefgh",  # authzid
            b"n,,n=,r=abcdefgh,x=ext",  # extensao
            b"n,,m=ext,n=,r=abcdefgh",
            b"n,,r=abcdefgh,n=",  # ordem
            b"n,,n=a=41,r=abcdefgh",  # escape invalido
            b"n,,n=a\x00b,r=abcdefgh",  # controle no nome
            b"n,,n=a\nb,r=abcdefgh",
            b"n,,n=a\x7fb,r=abcdefgh",
            b"n,,n=" + b"a" * 2_048 + b",r=abcdefgh",  # acima do teto SASL
            b"n,,n=,r=abcdefgh,",
            b"n,n=,r=abcdefgh",
            b"n",
            b"",
            b"\xff,,n=,r=abcdefgh",
        ],
    )
    def test_client_first_invalido(self, principal, data):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        assert category_of(exchange.client_first, SCRAM_SHA_256, data) is PV

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda f: f.replace(b",p=", b",x=1,p="),  # extensao
            lambda f: b",".join(reversed(f.split(b","))),  # ordem
            lambda f: f.rsplit(b",p=", 1)[0],  # sem prova
            lambda f: f.rsplit(b",p=", 1)[0] + b",p=AAAA",  # prova curta
            lambda f: f.rsplit(b",p=", 1)[0] + b",p=@@@",  # base64 invalido
            lambda f: f.rsplit(b",p=", 1)[0] + b",p=" + b"A" * 43,  # sem padding
            lambda f: f + b"\xff",
        ],
    )
    def test_client_final_invalido(self, principal, mutate):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256, ("n,," + bare).encode())
        final, _ = client_final(PASSWORD, first, bare)
        assert category_of(exchange.client_final, mutate(final), identity_accepted=True) is PV

    def test_prova_adulterada(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256, ("n,," + bare).encode())
        final, _ = client_final(PASSWORD, first, bare)
        head, proof = final.rsplit(b",p=", 1)
        raw = bytearray(base64.b64decode(proof))
        raw[0] ^= 1
        tampered = head + b",p=" + base64.b64encode(bytes(raw))
        assert category_of(exchange.client_final, tampered, identity_accepted=True) is AUTH


class TestStateMachine:
    def test_final_antes_do_first(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        assert category_of(exchange.client_final, b"c=biws", identity_accepted=True) is PV

    def test_first_duas_vezes(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        data = f"n,,n=,r={CLIENT_NONCE}".encode()
        exchange.client_first(SCRAM_SHA_256, data)
        assert category_of(exchange.client_first, SCRAM_SHA_256, data) is PV

    def test_falha_da_fonte_de_nonce_e_fechada_e_terminal(self, principal, monkeypatch):
        def broken(_size):
            raise OSError("canario-da-fonte")

        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        monkeypatch.setattr("maskgw.pgwire.scram.secrets.token_bytes", broken)
        data = f"n,,n=,r={CLIENT_NONCE}".encode()
        category = category_of(exchange.client_first, SCRAM_SHA_256, data)
        assert category is PgwireErrorCategory.INTERNAL_ERROR
        assert repr(exchange) == "ScramServerExchange(stage=failed)"
        monkeypatch.undo()
        assert category_of(exchange.client_first, SCRAM_SHA_256, data) is PV

    def test_falha_e_terminal(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256, ("n,," + bare).encode())
        good, _ = client_final(PASSWORD, first, bare)
        assert category_of(exchange.client_final, b"lixo", identity_accepted=True) is PV
        assert category_of(exchange.client_final, good, identity_accepted=True) is PV

    def test_sucesso_e_terminal(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        bare = f"n=,r={CLIENT_NONCE}"
        first = exchange.client_first(SCRAM_SHA_256, ("n,," + bare).encode())
        good, _ = client_final(PASSWORD, first, bare)
        exchange.client_final(good, identity_accepted=True)
        assert category_of(exchange.client_final, good, identity_accepted=True) is PV


class TestPreparePrincipal:
    def test_sasl_prep_equivalencia_documentada(self):
        # "Ⅸ" normaliza para "IX" (NFKC) e o espaco nao separavel (U+00A0) para
        # espaco comum: as duas formas sao a mesma senha.
        principal = prepare_principal(USER, "senhaⅨ final")
        run(principal.verifier_for(USER), password="senhaIX final")

    @pytest.mark.parametrize(
        "password",
        [
            "",
            "­",  # normaliza para vazio (B.1)
            "abc\x07def",  # controle
            "abc",  # uso privado
            "اabc",  # bidi invalido
            "abcȡ",  # nao atribuido no Unicode 3.2
        ],
    )
    def test_senha_recusada_sem_fallback(self, password):
        with pytest.raises(ConfigError) as info:
            prepare_principal(USER, password)
        assert info.value.__cause__ is None
        assert info.value.__context__ is None
        assert "abc" not in str(info.value)

    @pytest.mark.parametrize("username", ["", "a" * 64, "a\x00b", "é" * 32, None, 1])
    def test_usuario_invalido(self, username):
        with pytest.raises(ConfigError) as info:
            prepare_principal(username, PASSWORD)
        assert info.value.__context__ is None

    def test_repr_sem_segredo(self, principal):
        verifier = principal.verifier_for(USER)
        text = (
            repr(principal)
            + repr(verifier)
            + repr(ScramServerExchange(verifier, channel_binding=None))
        )
        assert USER not in text
        assert PASSWORD not in text
        assert b64(verifier.salt) not in text
        assert verifier.stored_key.hex() not in text

    def test_erro_de_troca_nao_carrega_entrada(self, principal):
        exchange = ScramServerExchange(principal.verifier_for(USER), channel_binding=None)
        with pytest.raises(PgwireStartupError) as info:
            exchange.client_first(SCRAM_SHA_256, b"n,a=canario,n=canario,r=canario123")
        assert "canario" not in str(info.value) + repr(info.value)
