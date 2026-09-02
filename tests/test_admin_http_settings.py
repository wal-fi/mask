"""Fase 7, Etapa 7: o passo 1 do startup — enable, token, bind e porta.

Estes testes nao sobem servidor. E deliberado: a validacao acontece ANTES de
verificar filesystem, adquirir lock ou conectar (secao 9.2), e provar isso sem
recursos e a forma mais direta de fixar a ordem.
"""

from __future__ import annotations

import pytest

from maskgw.admin.http import settings as settings_module
from maskgw.admin.http.settings import (
    ADMIN_BIND_ENV,
    ADMIN_ENABLED_ENV,
    ADMIN_PORT_ENV,
    ADMIN_TOKEN_ENV,
    ADMIN_TOKEN_MIN_LENGTH,
    DEFAULT_ADMIN_BIND,
    DEFAULT_ADMIN_PORT,
    LOOPBACK_BINDS,
)
from maskgw.errors import ConfigError
from maskgw.secretsource import MappingSecretProvider

VALID_TOKEN = "x" * ADMIN_TOKEN_MIN_LENGTH


def provider(**values: str) -> MappingSecretProvider:
    return MappingSecretProvider(values)


class TestHabilitacao:
    def test_ausente_mantem_o_processo_de_hoje(self) -> None:
        assert settings_module.resolve(provider()) is None
        assert not settings_module.is_enabled(provider())

    @pytest.mark.parametrize("value", ["0", "true", "yes", "on", "TRUE", "2", " ", "01", "1 1"])
    def test_somente_o_valor_1_habilita(self, value: str) -> None:
        """`ausente ou diferente disso` e literal.

        Aceitar sinonimos convidaria a um typo que LIGA a superficie
        administrativa sem que ninguem tenha pedido.
        """
        secrets = provider(**{ADMIN_ENABLED_ENV: value, ADMIN_TOKEN_ENV: VALID_TOKEN})
        assert settings_module.resolve(secrets) is None

    def test_valor_1_com_token_valido_habilita_com_os_defaults(self) -> None:
        resolved = settings_module.resolve(
            provider(**{ADMIN_ENABLED_ENV: "1", ADMIN_TOKEN_ENV: VALID_TOKEN})
        )
        assert resolved is not None
        assert resolved.host == DEFAULT_ADMIN_BIND
        assert resolved.port == DEFAULT_ADMIN_PORT
        assert resolved.token == VALID_TOKEN

    def test_espacos_em_volta_do_valor_ainda_habilitam(self) -> None:
        """`EnvSecretProvider` ja normaliza; a regra vale para os dois providers."""
        resolved = settings_module.resolve(
            provider(**{ADMIN_ENABLED_ENV: "  1  ", ADMIN_TOKEN_ENV: VALID_TOKEN})
        )
        assert resolved is not None


class TestToken:
    def test_token_ausente_com_admin_habilitado_impede_o_startup(self) -> None:
        with pytest.raises(ConfigError):
            settings_module.resolve(provider(**{ADMIN_ENABLED_ENV: "1"}))

    def test_token_vazio_conta_como_ausente(self) -> None:
        with pytest.raises(ConfigError):
            settings_module.resolve(provider(**{ADMIN_ENABLED_ENV: "1", ADMIN_TOKEN_ENV: "   "}))

    @pytest.mark.parametrize("length", [0, 1, 8, ADMIN_TOKEN_MIN_LENGTH - 1])
    def test_token_curto_impede_o_startup(self, length: int) -> None:
        with pytest.raises(ConfigError):
            settings_module.build(token="x" * length, host="127.0.0.1", port=8765)

    def test_exatamente_o_minimo_e_aceito(self) -> None:
        built = settings_module.build(token=VALID_TOKEN, host="127.0.0.1", port=8765)
        assert built.token == VALID_TOKEN

    def test_a_mensagem_de_erro_nunca_contem_o_token(self) -> None:
        secret = "segredo-curto"
        with pytest.raises(ConfigError) as raised:
            settings_module.build(token=secret, host="127.0.0.1", port=8765)
        assert secret not in str(raised.value)

    def test_repr_nao_expoe_valor_tamanho_prefixo_nem_hash(self) -> None:
        """Secao 11.1: nunca o valor, e nunca um derivado dele."""
        built = settings_module.build(token=VALID_TOKEN, host="127.0.0.1", port=8765)
        rendered = repr(built)

        assert VALID_TOKEN not in rendered
        assert VALID_TOKEN[:4] not in rendered
        assert str(len(VALID_TOKEN)) not in rendered
        assert "<redacted>" in rendered


class TestBind:
    @pytest.mark.parametrize("host", sorted(LOOPBACK_BINDS))
    def test_os_tres_loopbacks_sao_aceitos(self, host: str) -> None:
        assert settings_module.build(token=VALID_TOKEN, host=host, port=8765).host == host

    @pytest.mark.parametrize(
        "host",
        [
            "0.0.0.0",
            "::",
            "192.168.0.10",
            "10.0.0.1",
            "example.com",
            "127.0.0.2",
            "",
            "127.0.0.1 ",
        ],
    )
    def test_qualquer_bind_fora_de_loopback_impede_o_startup(self, host: str) -> None:
        """Sem TLS, interface externa poria o bearer token em HTTP claro.

        `127.0.0.1 ` com espaco passa porque e normalizado; os demais falham.
        """
        if host.strip().casefold() in LOOPBACK_BINDS:
            assert settings_module.build(token=VALID_TOKEN, host=host, port=8765) is not None
            return
        with pytest.raises(ConfigError):
            settings_module.build(token=VALID_TOKEN, host=host, port=8765)

    def test_nao_existe_variavel_de_escape_para_bind_externo(self) -> None:
        """`MASKGW_ADMIN_ALLOW_NONLOOPBACK` foi removida da especificacao.

        Se alguem a reintroduzir, este teste continua passando — mas o de cima
        quebra, porque o bind externo passaria a ser aceito. O valor deste aqui
        e afirmar que o modulo nao conhece nome algum de escape.
        """
        names = [name for name in dir(settings_module) if "NONLOOPBACK" in name.upper()]
        assert names == []
        assert "ALLOW" not in "".join(dir(settings_module)).upper()


class TestPorta:
    def test_default_e_8765(self) -> None:
        assert DEFAULT_ADMIN_PORT == 8765

    @pytest.mark.parametrize("port", [1, 80, 8765, 65535])
    def test_intervalo_aceito(self, port: int) -> None:
        assert settings_module.build(token=VALID_TOKEN, host="::1", port=port).port == port

    @pytest.mark.parametrize("port", [0, -1, 65536, 100000])
    def test_fora_do_intervalo_impede_o_startup(self, port: int) -> None:
        with pytest.raises(ConfigError):
            settings_module.build(token=VALID_TOKEN, host="127.0.0.1", port=port)

    @pytest.mark.parametrize("raw", ["", "abc", "8765.0", "0x1", "8 7 6 5"])
    def test_valor_nao_inteiro_impede_o_startup(self, raw: str) -> None:
        secrets = provider(
            **{
                ADMIN_ENABLED_ENV: "1",
                ADMIN_TOKEN_ENV: VALID_TOKEN,
                ADMIN_PORT_ENV: raw,
            }
        )
        if not raw.strip():
            # Vazio e tratado como ausente pelo provider: cai no default.
            resolved = settings_module.resolve(secrets)
            assert resolved is not None
            assert resolved.port == DEFAULT_ADMIN_PORT
            return
        with pytest.raises(ConfigError):
            settings_module.resolve(secrets)

    def test_a_mensagem_nao_ecoa_o_valor_recebido(self) -> None:
        marcador = "porta-invalida-marcador"
        secrets = provider(
            **{
                ADMIN_ENABLED_ENV: "1",
                ADMIN_TOKEN_ENV: VALID_TOKEN,
                ADMIN_PORT_ENV: marcador,
            }
        )
        with pytest.raises(ConfigError) as raised:
            settings_module.resolve(secrets)
        assert marcador not in str(raised.value)


class TestResolucaoCompleta:
    def test_bind_do_ambiente_e_respeitado(self) -> None:
        resolved = settings_module.resolve(
            provider(
                **{
                    ADMIN_ENABLED_ENV: "1",
                    ADMIN_TOKEN_ENV: VALID_TOKEN,
                    ADMIN_BIND_ENV: "::1",
                    ADMIN_PORT_ENV: "9000",
                }
            )
        )
        assert resolved is not None
        assert (resolved.host, resolved.port) == ("::1", 9000)

    def test_bind_externo_no_ambiente_impede_o_startup(self) -> None:
        with pytest.raises(ConfigError):
            settings_module.resolve(
                provider(
                    **{
                        ADMIN_ENABLED_ENV: "1",
                        ADMIN_TOKEN_ENV: VALID_TOKEN,
                        ADMIN_BIND_ENV: "0.0.0.0",
                    }
                )
            )

    def test_sem_admin_habilitado_token_invalido_nao_importa(self) -> None:
        """Desabilitado e desabilitado: nada de admin e sequer olhado."""
        assert settings_module.resolve(provider(**{ADMIN_TOKEN_ENV: "curto"})) is None
