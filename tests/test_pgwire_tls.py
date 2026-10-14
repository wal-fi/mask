"""Fase 9, Etapa 7 (D-110, lote 1): preparo do TLS de servidor, sem socket.

Certificados gerados em `tmp_path` pelo `cryptography`; nenhum certificado
real, nenhuma conexao de rede. Prova:

- contexto com minimo TLS 1.2, sem compressao/renegociacao, binding do leaf
  efetivamente apresentado (igual ao do PEM lido);
- recusas fechadas: inexistente, diretorio, symlink, junction/reparse point,
  pai inseguro, tamanho acima do limite, vencido, futuro, chave que nao casa,
  chave cifrada (sem prompt), Ed25519, PEM invalido;
- cert/chave trocados durante o load sao detectados;
- handshake em memoria limitado em voltas, bytes e prazo;
- erros sem caminho, PEM, cadeia ou causa; nenhum arquivo temporario.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import ssl
import stat
import subprocess
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

import maskgw.pgwire.tls as tls_module
from maskgw.errors import ConfigError
from maskgw.pgwire.tls import ServerTls, TlsLimits, prepare_server_tls
from tests.pgwire_support import (
    PRIVATE_KEY_MODE,
    make_certificate,
    presented_leaf,
    write_private_key,
)

WINDOWS = os.name == "nt"


def refused(*args: Any, **kwargs: Any) -> ConfigError:
    with pytest.raises(ConfigError) as info:
        prepare_server_tls(*args, **kwargs)
    error = info.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert str(error).startswith("pgwire: ")
    return error


def leaf_of(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificates(path.read_bytes())[0]


@pytest.fixture
def rsa(tmp_path):
    directory = tmp_path / "rsa"
    directory.mkdir()
    cert, _, _ = make_certificate(directory, "rsa-sha256")
    return cert


class TestGeradorDeTeste:
    """O gerador cumpre o contrato do produto; o produto nao e relaxado."""

    @pytest.mark.skipif(WINDOWS, reason="bits de modo POSIX")
    def test_chave_gerada_com_modo_privado(self, rsa):
        assert stat.S_IMODE(rsa.key_path.stat().st_mode) == PRIVATE_KEY_MODE

    def test_gravacao_da_chave_e_exclusiva(self, rsa):
        with pytest.raises(FileExistsError):
            write_private_key(rsa.key_path, b"sobrescrita")


class TestAceito:
    def test_contexto_e_binding_do_leaf_apresentado(self, rsa):
        result = prepare_server_tls(rsa.cert_path, rsa.key_path)
        assert isinstance(result, ServerTls)
        context = result.context
        assert context.minimum_version is ssl.TLSVersion.TLSv1_2
        assert context.options & ssl.OP_NO_COMPRESSION
        assert context.options & ssl.OP_NO_RENEGOTIATION
        assert context.verify_mode is ssl.CERT_NONE
        assert presented_leaf(context) == rsa.der
        assert result.channel_binding == hashlib.sha256(rsa.der).digest()

    def test_ecdsa_p384_usa_sha384(self, tmp_path):
        cert, _, _ = make_certificate(tmp_path, "ecdsa-p384-sha384")
        result = prepare_server_tls(cert.cert_path, cert.key_path)
        assert result.channel_binding == hashlib.sha384(cert.der).digest()

    def test_cadeia_no_pem_usa_o_primeiro_como_leaf(self, tmp_path):
        ca, ca_cert, ca_key = make_certificate(tmp_path, "rsa-sha256", common_name="ca.test")
        leaf, _, _ = make_certificate(tmp_path, "rsa-sha256", issuer=(ca_cert, ca_key))
        leaf.cert_path.write_bytes(leaf.cert_path.read_bytes() + ca.cert_path.read_bytes())
        result = prepare_server_tls(leaf.cert_path, leaf.key_path)
        assert result.channel_binding == hashlib.sha256(leaf.der).digest()

    def test_repr_sem_caminho_nem_binding(self, rsa):
        result = prepare_server_tls(rsa.cert_path, rsa.key_path)
        assert repr(result) == "ServerTls(<configurado>)"

    def test_nenhum_arquivo_temporario(self, rsa):
        before = sorted(p.name for p in rsa.cert_path.parent.iterdir())
        prepare_server_tls(rsa.cert_path, rsa.key_path)
        assert sorted(p.name for p in rsa.cert_path.parent.iterdir()) == before

    @pytest.mark.filterwarnings("ignore:ssl.TLSVersion.TLSv1:DeprecationWarning")
    def test_cliente_tls_1_1_nao_negocia(self, rsa):
        context = prepare_server_tls(rsa.cert_path, rsa.key_path).context
        client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client.check_hostname = False
        client.verify_mode = ssl.CERT_NONE
        client.minimum_version = ssl.TLSVersion.TLSv1
        client.maximum_version = ssl.TLSVersion.TLSv1_1
        s_in, s_out, c_in, c_out = (ssl.MemoryBIO() for _ in range(4))
        server = context.wrap_bio(s_in, s_out, server_side=True)
        peer = client.wrap_bio(c_in, c_out)
        failed = False
        for _ in range(10):
            for side in (peer, server):
                try:
                    side.do_handshake()
                except ssl.SSLWantReadError:
                    pass
                except ssl.SSLError:
                    failed = True
            if failed:
                break
            s_in.write(c_out.read())
            c_in.write(s_out.read())
        assert failed


class TestArquivos:
    def test_inexistentes(self, rsa, tmp_path):
        refused(tmp_path / "nao-existe.crt", rsa.key_path)
        refused(rsa.cert_path, tmp_path / "nao-existe.key")

    def test_nul_no_caminho_nao_trunca_para_outro_arquivo(self, rsa):
        # No Windows, `abspath` trunca no NUL: sem a recusa explicita, o caminho
        # abaixo carregaria o certificado REAL que precede o NUL.
        refused(f"{rsa.cert_path}\x00lixo", rsa.key_path)
        refused(rsa.cert_path, f"{rsa.key_path}\x00lixo")

    @pytest.mark.parametrize("path", ["", None, 5, b"bytes.crt"])
    def test_caminho_de_tipo_ou_forma_invalida(self, rsa, path):
        refused(path, rsa.key_path)

    def test_diretorio(self, rsa, tmp_path):
        refused(tmp_path, rsa.key_path)
        refused(rsa.cert_path, tmp_path)

    def test_symlink_do_arquivo(self, rsa, tmp_path):
        link = tmp_path / "link.crt"
        try:
            link.symlink_to(rsa.cert_path)
        except OSError:
            pytest.skip("criacao de symlink indisponivel nesta instalacao")
        refused(link, rsa.key_path)

    @pytest.mark.skipif(not WINDOWS, reason="junction e do Windows")
    def test_pai_junction_e_recusado(self, rsa, tmp_path):
        junction = tmp_path / "junction"
        result = subprocess.run(  # noqa: S603 - comando fixo do proprio teste
            ["cmd", "/c", "mklink", "/J", str(junction), str(rsa.cert_path.parent)],  # noqa: S607
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        try:
            via = junction / rsa.cert_path.name
            assert via.read_bytes() == rsa.cert_path.read_bytes()  # a junction funciona
            refused(via, rsa.key_path)
            refused(rsa.cert_path, junction / rsa.key_path.name)
        finally:
            os.rmdir(junction)

    def test_arquivo_reparse_point_e_recusado(self, rsa, monkeypatch):
        original = Path.lstat

        def fake_lstat(self):
            info = original(self)
            if self.name != rsa.cert_path.name:
                return info
            return types.SimpleNamespace(
                st_mode=info.st_mode,
                st_size=info.st_size,
                st_dev=info.st_dev,
                st_ino=info.st_ino,
                st_mtime_ns=info.st_mtime_ns,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )

        monkeypatch.setattr(Path, "lstat", fake_lstat)
        refused(rsa.cert_path, rsa.key_path)

    def test_cert_acima_do_limite(self, rsa):
        size = len(rsa.cert_path.read_bytes())
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(max_cert_bytes=size - 1))
        prepare_server_tls(rsa.cert_path, rsa.key_path, limits=TlsLimits(max_cert_bytes=size))

    def test_chave_acima_do_limite(self, rsa):
        size = len(rsa.key_path.read_bytes())
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(max_key_bytes=size - 1))

    def test_leitura_incremental_para_em_limite_mais_um(self, rsa, monkeypatch):
        size = len(rsa.cert_path.read_bytes())
        budget = {"left": size + 1}
        requests: list[int] = []
        original = os.read

        def counted(descriptor, wanted):
            # Nenhum pedido passa do orcamento restante de `limite + 1`.
            assert wanted <= budget["left"]
            requests.append(wanted)
            chunk = original(descriptor, wanted)
            budget["left"] -= len(chunk)
            return chunk

        monkeypatch.setattr("maskgw.pgwire.tls.os.read", counted)
        prepare_server_tls(rsa.cert_path, rsa.key_path, limits=TlsLimits(max_cert_bytes=size))
        assert size + 1 - budget["left"] == size  # devolvidos: exatamente o arquivo
        assert max(requests) <= 4096

    def test_arquivo_que_cresce_alem_do_limite_e_recusado(self, rsa, monkeypatch):
        # O `lstat` ve o tamanho permitido; a leitura recebe mais: recusa.
        size = len(rsa.cert_path.read_bytes())
        original = os.read

        def grows(descriptor, wanted):
            chunk = original(descriptor, wanted)
            return chunk if chunk else b"x" * wanted

        monkeypatch.setattr("maskgw.pgwire.tls.os.read", grows)
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(max_cert_bytes=size))

    @pytest.mark.skipif(WINDOWS, reason="bits de modo POSIX")
    @pytest.mark.parametrize("mode", [0o640, 0o604, 0o644])
    def test_chave_com_modo_aberto(self, rsa, mode):
        rsa.key_path.chmod(mode)
        refused(rsa.cert_path, rsa.key_path)

    @pytest.mark.skipif(WINDOWS, reason="bits de modo POSIX")
    def test_cert_gravavel_por_outros(self, rsa):
        rsa.key_path.chmod(0o600)
        rsa.cert_path.chmod(0o666)
        refused(rsa.cert_path, rsa.key_path)

    @pytest.mark.skipif(WINDOWS, reason="bits de modo POSIX")
    def test_pai_gravavel_por_outros(self, rsa):
        rsa.key_path.chmod(0o600)
        rsa.cert_path.parent.chmod(0o777)
        refused(rsa.cert_path, rsa.key_path)


class TestCertificado:
    def test_vencido(self, rsa):
        after = leaf_of(rsa.cert_path).not_valid_after_utc
        refused(rsa.cert_path, rsa.key_path, now=after + datetime.timedelta(seconds=1))
        prepare_server_tls(rsa.cert_path, rsa.key_path, now=after)

    def test_ainda_nao_valido(self, rsa):
        before = leaf_of(rsa.cert_path).not_valid_before_utc
        refused(rsa.cert_path, rsa.key_path, now=before - datetime.timedelta(seconds=1))
        prepare_server_tls(rsa.cert_path, rsa.key_path, now=before)

    def test_ed25519_incompativel_com_plus(self, tmp_path):
        cert, _, _ = make_certificate(tmp_path, "ed25519")
        refused(cert.cert_path, cert.key_path)

    @pytest.mark.parametrize("content", [b"", b"nao e pem", b"-----BEGIN CERTIFICATE-----\nxx\n"])
    def test_pem_invalido(self, rsa, content):
        rsa.cert_path.write_bytes(content)
        refused(rsa.cert_path, rsa.key_path)

    def test_chave_que_nao_casa(self, tmp_path):
        first, _, _ = make_certificate(tmp_path, "rsa-sha256")
        second, _, _ = make_certificate(tmp_path, "rsa-sha256")
        refused(first.cert_path, second.key_path)

    def test_chave_cifrada_sem_prompt(self, rsa):
        key = serialization.load_pem_private_key(rsa.key_path.read_bytes(), password=None)
        rsa.key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(b"frase-canario"),
            )
        )
        refused(rsa.cert_path, rsa.key_path)

    @pytest.mark.parametrize("content", [b"", b"lixo"])
    def test_chave_invalida(self, rsa, content):
        rsa.key_path.write_bytes(content)
        refused(rsa.cert_path, rsa.key_path)


class TestTrocaDuranteOLoad:
    def _swap_during_load(
        self, monkeypatch: pytest.MonkeyPatch, action: Callable[[], None]
    ) -> None:
        original = ssl.SSLContext.load_cert_chain

        def swapping(self, *args, **kwargs):
            action()
            return original(self, *args, **kwargs)

        monkeypatch.setattr(ssl.SSLContext, "load_cert_chain", swapping)

    def test_par_trocado_por_outro_par_valido(self, rsa, tmp_path, monkeypatch):
        other, _, _ = make_certificate(tmp_path, "rsa-sha256")

        def swap():
            os.replace(other.cert_path, rsa.cert_path)
            os.replace(other.key_path, rsa.key_path)

        self._swap_during_load(monkeypatch, swap)
        error = refused(rsa.cert_path, rsa.key_path)
        assert "alterado" in str(error)

    def test_mesmo_conteudo_regravado_muda_a_identidade(self, rsa, monkeypatch):
        content = rsa.cert_path.read_bytes()

        def rewrite():
            replacement = rsa.cert_path.with_suffix(".novo")
            replacement.write_bytes(content)
            os.replace(replacement, rsa.cert_path)

        self._swap_during_load(monkeypatch, rewrite)
        error = refused(rsa.cert_path, rsa.key_path)
        assert "alterado" in str(error)

    def test_leaf_apresentado_diferente_do_lido(self, rsa, tmp_path, monkeypatch):
        other, _, _ = make_certificate(tmp_path, "rsa-sha256")
        monkeypatch.setattr(tls_module, "presented_leaf", lambda _context, _limits: other.der)
        error = refused(rsa.cert_path, rsa.key_path)
        assert "alterado" in str(error)


class TestHandshakeLimitado:
    def test_voltas_insuficientes(self, rsa):
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(handshake_rounds=1))

    def test_bytes_insuficientes(self, rsa):
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(handshake_bytes=100))

    def test_prazo_estourado(self, rsa, monkeypatch):
        clock = iter([0.0, *[10.0] * 100])
        monkeypatch.setattr("maskgw.pgwire.tls.time.monotonic", lambda: next(clock))
        refused(rsa.cert_path, rsa.key_path, limits=TlsLimits(handshake_deadline_ms=1_000))

    @pytest.mark.parametrize(
        "field",
        [
            "max_cert_bytes",
            "max_key_bytes",
            "handshake_rounds",
            "handshake_bytes",
            "handshake_deadline_ms",
        ],
    )
    @pytest.mark.parametrize("value", [0, -1, True])
    def test_limites_estritos(self, field, value):
        with pytest.raises(ValueError, match="limite"):
            TlsLimits(**{field: value})


class TestSegredos:
    def test_erro_sem_caminho_pem_nem_openssl(self, tmp_path):
        first, _, _ = make_certificate(tmp_path, "rsa-sha256")
        second, _, _ = make_certificate(tmp_path, "rsa-sha256")
        error = refused(first.cert_path, second.key_path)
        text = str(error) + repr(error) + repr(error.args)
        assert str(tmp_path) not in text
        assert "BEGIN" not in text
        assert "SSL" not in text
        assert "key values mismatch" not in text.lower()
