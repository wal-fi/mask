"""Configuracao de startup da Admin API: habilitacao, token, bind e porta.

Este e o passo 1 da secao 9.2, e ele acontece ANTES de verificar o filesystem,
adquirir o lock e construir o runtime. Um token curto ou um bind fora de
loopback nao devem chegar a abrir arquivo algum.

Nada aqui e HTTP ainda: e leitura e validacao de ambiente. Isso torna a regra
testavel sem subir servidor, e mantem o unico ponto onde a decisao
"admin ligado ou desligado" acontece.

## Por que so loopback, sem valvula de escape

Nao ha TLS nesta fase. Um bind em interface externa poria o bearer token em
HTTP claro, em todo request, na rede. A especificacao REMOVEU deliberadamente a
variavel `MASKGW_ADMIN_ALLOW_NONLOOPBACK` que uma versao anterior propunha
(secao 3.1): nao existe opt-in, e bind externo pertence a Fase 9, junto com o
resto do problema de deployment.

## Por que o token nunca vem do `masking.yaml`

Pela mesma razao da chave HMAC (D-006): o `masking.yaml` e um documento gerido
pela propria Admin API, e um segredo dentro dele seria legivel por
`GET /admin/v1/config`. O token vem de `MASKGW_ADMIN_TOKEN` e de mais lugar
nenhum — nem de argumento de linha de comando, que aparece em `ps`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from maskgw.errors import ConfigError
from maskgw.secretsource import EnvSecretProvider, SecretProvider

#: `MASKGW_ADMIN_ENABLED=1` liga a Admin API. Ausente ou com qualquer outro
#: valor, o processo e exatamente o de hoje: nenhuma porta, nenhuma thread,
#: nenhum lock de arquivo e nenhum caminho de escrita.
ADMIN_ENABLED_ENV: Final = "MASKGW_ADMIN_ENABLED"

#: O unico valor que habilita. Comparado apos `strip`, sem interpretacao de
#: "true"/"yes"/"on": um conjunto amplo de sinonimos convida a um typo que
#: LIGA a superficie administrativa sem que ninguem tenha pedido.
ADMIN_ENABLED_VALUE: Final = "1"

#: Nome da variavel, nao o valor dela. O token em si nunca aparece no codigo.
ADMIN_TOKEN_ENV: Final = "MASKGW_ADMIN_TOKEN"  # noqa: S105 - nome de variavel
ADMIN_BIND_ENV: Final = "MASKGW_ADMIN_BIND"
ADMIN_PORT_ENV: Final = "MASKGW_ADMIN_PORT"

#: Mesmo minimo da chave HMAC (D-006). Um token de 8 caracteres num endpoint
#: sem rate limit e um convite.
ADMIN_TOKEN_MIN_LENGTH: Final = 32

DEFAULT_ADMIN_BIND: Final = "127.0.0.1"

#: Porta default aprovada na secao 14.1 da especificacao.
DEFAULT_ADMIN_PORT: Final = 8765

MIN_PORT: Final = 1
MAX_PORT: Final = 65535

#: Os UNICOS binds aceitos. Qualquer outro endereco — inclusive `0.0.0.0`,
#: `::` e um IP de interface real — impede o startup.
LOOPBACK_BINDS: Final[frozenset[str]] = frozenset({"127.0.0.1", "::1", "localhost"})


@dataclass(frozen=True, slots=True)
class AdminHttpSettings:
    """Parametros validados da fronteira HTTP administrativa.

    Construir esta dataclass diretamente NAO valida nada; use `resolve` ou
    `build`. O `repr` e redefinido porque a dataclass carrega o token.
    """

    token: str
    host: str = DEFAULT_ADMIN_BIND
    port: int = DEFAULT_ADMIN_PORT

    def __repr__(self) -> str:
        # Nem o valor, nem o tamanho, nem um prefixo, nem um hash do token
        # (secao 11.1). `host` e `port` sao parametros de operacao, nao
        # segredos, e aparecem porque ajudam a diagnosticar startup.
        return f"AdminHttpSettings(host={self.host!r}, port={self.port!r}, token=<redacted>)"


def is_enabled(secrets: SecretProvider | None = None) -> bool:
    """Se a Admin API foi explicitamente habilitada no ambiente."""
    provider = secrets if secrets is not None else EnvSecretProvider()
    return (provider.get(ADMIN_ENABLED_ENV) or "") == ADMIN_ENABLED_VALUE


def build(*, token: str, host: str, port: int) -> AdminHttpSettings:
    """Valida token, bind e porta. Qualquer violacao e `ConfigError` fatal."""
    if len(token) < ADMIN_TOKEN_MIN_LENGTH:
        # Nem o token, nem o tamanho recebido: a mensagem diz o requisito, e
        # nao o que chegou.
        msg = (
            f"token administrativo muito curto: {ADMIN_TOKEN_ENV} exige ao menos "
            f"{ADMIN_TOKEN_MIN_LENGTH} caracteres"
        )
        raise ConfigError(msg)

    normalized_host = host.strip().casefold()
    if normalized_host not in LOOPBACK_BINDS:
        msg = (
            f"bind administrativo fora de loopback: {ADMIN_BIND_ENV} aceita somente "
            f"{sorted(LOOPBACK_BINDS)}. Sem TLS, uma interface externa poria o token "
            "em HTTP claro; bind externo pertence a Fase 9"
        )
        raise ConfigError(msg)

    if not MIN_PORT <= port <= MAX_PORT:
        msg = f"porta administrativa invalida: {ADMIN_PORT_ENV} aceita {MIN_PORT}..{MAX_PORT}"
        raise ConfigError(msg)

    return AdminHttpSettings(token=token, host=normalized_host, port=port)


def resolve(secrets: SecretProvider | None = None) -> AdminHttpSettings | None:
    """Le o ambiente. Devolve None quando a Admin API nao esta habilitada.

    Com a Admin API habilitada, token ausente, token curto, bind nao-loopback
    ou porta invalida levantam `ConfigError` — e o processo nao sobe. Falhar no
    startup e o comportamento correto: subir com a Admin API silenciosamente
    desligada deixaria o administrador convencido de que ela esta no ar.
    """
    provider = secrets if secrets is not None else EnvSecretProvider()
    if not is_enabled(provider):
        return None

    token = provider.get(ADMIN_TOKEN_ENV)
    if token is None:
        msg = (
            f"Admin API habilitada por {ADMIN_ENABLED_ENV}={ADMIN_ENABLED_VALUE} sem token: "
            f"defina {ADMIN_TOKEN_ENV} com ao menos {ADMIN_TOKEN_MIN_LENGTH} caracteres. "
            "O token nunca e lido do masking.yaml"
        )
        raise ConfigError(msg)

    host = provider.get(ADMIN_BIND_ENV) or DEFAULT_ADMIN_BIND
    return build(token=token, host=host, port=_resolve_port(provider))


def _resolve_port(provider: SecretProvider) -> int:
    raw = provider.get(ADMIN_PORT_ENV)
    if raw is None:
        return DEFAULT_ADMIN_PORT

    port: int | None = None
    try:
        port = int(raw)
    except ValueError:
        port = None
    if port is None:
        # O valor recebido nao entra na mensagem: e entrada do operador, e a
        # regra e nao ecoar entrada em erro.
        msg = f"porta administrativa invalida: {ADMIN_PORT_ENV} deve ser um inteiro"
        raise ConfigError(msg)
    return port
