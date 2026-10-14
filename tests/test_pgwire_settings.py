"""Fase 9, Etapa 7 (D-110, lote 1): settings externos do listener PGWire.

So leitura e validacao: nada aqui abre socket, resolve DNS ou toca arquivo.
Prova:

- `MASKGW_PGWIRE_ENABLED` liga SO com o valor bruto `1`; desligado, nenhum
  outro setting e lido nem validado e nenhum segredo e consultado;
- defaults da spec §5.1 (bind `127.0.0.1`, porta 6432, 32 sessoes, idle
  300000 ms) e parse estrito de inteiros;
- usuario e senha obrigatorios; a senha vem do `SecretProvider` existente,
  com a normalizacao antiga intacta;
- cert/key pareados; TLS exigido fora dos literais `127.0.0.1` e `::1`;
  hostname preservado como veio e tratado como externo, sem DNS;
- `repr` e erros sem senha, usuario, caminho ou valor; sem cadeia de excecao.
"""

from __future__ import annotations

import socket

import pytest

from maskgw.bootstrap.settings import MappingRawSettings
from maskgw.errors import ConfigError
from maskgw.pgwire import settings as pgwire_settings
from maskgw.pgwire.settings import (
    DEFAULT_BIND,
    DEFAULT_IDLE_TIMEOUT_MS,
    DEFAULT_MAX_SESSIONS,
    DEFAULT_PORT,
    MAX_INTEGER_VALUE,
    PgwireLimits,
    PgwireSettings,
    resolve,
)
from maskgw.secretsource import MappingSecretProvider

PASSWORD = "senha-canario-pgwire"
USERNAME = "usuario-canario"
CERT = "C:/caminho-canario/server.crt"
KEY = "C:/caminho-canario/server.key"


def raw(**values: str) -> MappingRawSettings:
    names = {
        "enabled": "MASKGW_PGWIRE_ENABLED",
        "bind": "MASKGW_PGWIRE_BIND",
        "port": "MASKGW_PGWIRE_PORT",
        "username": "MASKGW_PGWIRE_USERNAME",
        "cert": "MASKGW_PGWIRE_TLS_CERT",
        "key": "MASKGW_PGWIRE_TLS_KEY",
        "sessions": "MASKGW_PGWIRE_MAX_SESSIONS",
        "idle": "MASKGW_PGWIRE_IDLE_TIMEOUT_MS",
    }
    return MappingRawSettings({names[key]: value for key, value in values.items()})


def secrets(password: str | None = PASSWORD) -> MappingSecretProvider:
    if password is None:
        return MappingSecretProvider({})
    return MappingSecretProvider({"MASKGW_PGWIRE_PASSWORD": password})


def enabled(**values: str) -> PgwireSettings:
    values.setdefault("enabled", "1")
    values.setdefault("username", USERNAME)
    result = resolve(raw(**values), secrets())
    assert result is not None
    return result


def config_error(**values: str) -> ConfigError:
    values.setdefault("enabled", "1")
    values.setdefault("username", USERNAME)
    with pytest.raises(ConfigError) as info:
        resolve(raw(**values), secrets())
    error = info.value
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


class _SpyRaw:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.read: list[str] = []

    def get_raw(self, name: str) -> str | None:
        self.read.append(name)
        return self.values.get(name)


class _SpySecrets:
    def __init__(self) -> None:
        self.read: list[str] = []

    def get(self, name: str) -> str | None:
        self.read.append(name)
        return None


class TestDesligado:
    @pytest.mark.parametrize("value", [None, "", "0", "true", "yes", " 1", "1 ", "01", "1\n"])
    def test_so_o_valor_bruto_1_liga(self, value):
        values = {} if value is None else {"enabled": value}
        assert resolve(raw(**values), secrets()) is None

    def test_desligado_nao_le_nem_valida_mais_nada(self):
        spy = _SpyRaw(
            {
                "MASKGW_PGWIRE_ENABLED": "0",
                "MASKGW_PGWIRE_PORT": "nao-e-porta",
                "MASKGW_PGWIRE_BIND": "0.0.0.0",  # noqa: S104 - nunca chega a ser lido
                "MASKGW_PGWIRE_TLS_CERT": CERT,
            }
        )
        spy_secrets = _SpySecrets()
        assert resolve(spy, spy_secrets) is None
        assert spy.read == ["MASKGW_PGWIRE_ENABLED"]
        assert spy_secrets.read == []

    def test_importar_nao_le_ambiente(self, monkeypatch):
        # O modulo so le quando `resolve` e chamado: nenhum efeito de import.
        monkeypatch.setenv("MASKGW_PGWIRE_ENABLED", "1")
        assert not hasattr(pgwire_settings, "SETTINGS")


class TestDefaults:
    def test_defaults_da_spec(self):
        result = enabled()
        assert result.bind == DEFAULT_BIND == "127.0.0.1"
        assert result.port == DEFAULT_PORT == 6432
        assert result.max_sessions == DEFAULT_MAX_SESSIONS == 32
        assert result.idle_timeout_ms == DEFAULT_IDLE_TIMEOUT_MS == 300_000
        assert result.username == USERNAME
        assert result.password == PASSWORD
        assert result.tls_cert is None
        assert result.tls_key is None
        assert result.bind_is_loopback
        assert not result.tls_required
        assert result.limits == PgwireLimits()

    def test_default_de_sessoes_igual_ao_do_registry(self):
        # Mesmo default da §5.1 nos dois lados; a coerencia em runtime e da
        # integracao (lote futuro), que usa o MESMO valor nos dois.
        from maskgw.runtime.datasources import MAX_GLOBAL_SESSIONS  # noqa: PLC0415

        assert DEFAULT_MAX_SESSIONS == MAX_GLOBAL_SESSIONS

    @pytest.mark.parametrize(
        ("field", "value", "attribute", "expected"),
        [
            ("port", "1", "port", 1),
            ("port", "65535", "port", 65535),
            ("sessions", "1", "max_sessions", 1),
            ("sessions", "100000", "max_sessions", 100_000),  # sem teto oculto de 32
            ("sessions", "999999999", "max_sessions", MAX_INTEGER_VALUE),  # maximo efetivo
            ("idle", "999999999", "idle_timeout_ms", MAX_INTEGER_VALUE),
            ("idle", "1", "idle_timeout_ms", 1),
            ("idle", "86400000", "idle_timeout_ms", 86_400_000),
        ],
    )
    def test_inteiros_validos(self, field, value, attribute, expected):
        assert getattr(enabled(**{field: value}), attribute) == expected


class TestInvalidos:
    @pytest.mark.parametrize(
        "value",
        ["", "0", "65536", "-1", "+1", " 1", "1 ", "1.0", "0x10", "6432a", "０", "06432", "1" * 10],
    )
    def test_porta_invalida(self, value):
        assert "MASKGW_PGWIRE_PORT" in str(config_error(port=value))

    @pytest.mark.parametrize("field", ["sessions", "idle"])
    @pytest.mark.parametrize(
        "value", ["", "0", "-5", "abc", " 3", "3 ", "1_000", "٣", "1" * 10, "1000000000"]
    )
    def test_inteiro_positivo_invalido(self, field, value):
        config_error(**{field: value})

    def test_usuario_ausente(self):
        with pytest.raises(ConfigError) as info:
            resolve(raw(enabled="1"), secrets())
        assert info.value.__context__ is None

    @pytest.mark.parametrize("username", ["", "a" * 64, "a\x00b", "é" * 32])
    def test_usuario_invalido(self, username):
        config_error(username=username)

    @pytest.mark.parametrize("password", [None, "", "   "])
    def test_senha_ausente_pela_normalizacao_existente(self, password):
        with pytest.raises(ConfigError) as info:
            resolve(raw(enabled="1", username=USERNAME), secrets(password))
        assert "MASKGW_PGWIRE_PASSWORD" in str(info.value)

    def test_senha_com_bordas_segue_a_normalizacao_existente(self):
        result = resolve(raw(enabled="1", username=USERNAME), secrets(f"  {PASSWORD}  "))
        assert result is not None
        assert result.password == PASSWORD

    @pytest.mark.parametrize("pair", [{"cert": CERT}, {"key": KEY}, {"cert": CERT, "key": ""}])
    def test_cert_e_chave_pareados(self, pair):
        config_error(**pair)

    @pytest.mark.parametrize("path", ["", "a\x00b"])
    def test_caminho_invalido(self, path):
        config_error(cert=path, key=KEY)


class TestBindETls:
    @pytest.mark.parametrize("bind", ["127.0.0.1", "::1"])
    def test_literais_de_loopback_dispensam_tls(self, bind):
        result = enabled(bind=bind)
        assert result.bind_is_loopback
        assert not result.tls_required

    @pytest.mark.parametrize("bind", ["127.0.0.1", "::1"])
    def test_loopback_com_tls_opcional(self, bind):
        result = enabled(bind=bind, cert=CERT, key=KEY)
        assert result.tls_configured
        assert not result.tls_required

    @pytest.mark.parametrize(
        "bind",
        [
            "0.0.0.0",  # noqa: S104 - e o bind externo que precisa exigir TLS
            "::",
            "192.168.10.20",
            "127.0.0.2",
            "0:0:0:0:0:0:0:1",
            "fe80::1%2",
            "localhost",
            "gateway.example",
            "Gateway-01.Example.",
        ],
    )
    def test_externo_exige_tls(self, bind):
        config_error(bind=bind)
        result = enabled(bind=bind, cert=CERT, key=KEY)
        assert result.bind == bind  # preservado exatamente, sem normalizar
        assert result.tls_required
        assert not result.bind_is_loopback

    def test_hostname_preservado_e_marcado_sem_dns(self, monkeypatch):
        def no_dns(*_args, **_kwargs):
            raise AssertionError("DNS nao pode ser consultado nas settings")

        monkeypatch.setattr(socket, "getaddrinfo", no_dns)
        monkeypatch.setattr(socket, "gethostbyname", no_dns)
        result = enabled(bind="localhost", cert=CERT, key=KEY)
        assert result.bind == "localhost"
        assert result.bind_is_hostname
        assert enabled().bind_is_hostname is False

    @pytest.mark.parametrize(
        "bind",
        [
            "",
            " ",
            "a b",
            "host:6432",
            "[::1]",
            "-bad",
            "bad-.x",
            "a" * 254,
            "x" * 64 + ".com",
            "exa_mple.com",
            "http://x",
            "1.2.3",
            "::1 ",
            "\u00e9.com",
        ],
    )
    def test_bind_invalido(self, bind):
        assert "MASKGW_PGWIRE_BIND" in str(config_error(bind=bind, cert=CERT, key=KEY))


class TestSegredos:
    def test_repr_sem_segredo_nem_identificadores(self):
        result = enabled(cert=CERT, key=KEY, bind="gateway.example")
        text = repr(result) + str(result)
        for canary in (PASSWORD, USERNAME, "caminho-canario"):
            assert canary not in text

    def test_erro_nao_carrega_valor(self):
        error = config_error(port="porta-canario")
        assert "porta-canario" not in str(error) + repr(error)
        error = config_error(bind="bind canario")
        assert "canario" not in str(error) + repr(error)


class TestLimitesAuxiliares:
    def test_defaults_delegados(self):
        limits = PgwireLimits()
        assert limits.startup_deadline_ms == 10_000
        assert limits.pre_auth_slots == 8
        assert limits.admission_burst == 20
        assert limits.admission_refill_per_s == 5
        assert limits.poll_ms == 250

    @pytest.mark.parametrize(
        "field",
        [
            "startup_deadline_ms",
            "pre_auth_slots",
            "admission_burst",
            "admission_refill_per_s",
            "poll_ms",
        ],
    )
    @pytest.mark.parametrize("value", [0, -1, True, 1.5])
    def test_limites_internos_estritos(self, field, value):
        with pytest.raises(ValueError, match="limite"):
            PgwireLimits(**{field: value})

    def test_limites_configuraveis_so_internamente(self):
        result = resolve(
            raw(enabled="1", username=USERNAME), secrets(), limits=PgwireLimits(pre_auth_slots=2)
        )
        assert result is not None
        assert result.limits.pre_auth_slots == 2
