"""Settings externos do listener PGWire (Fase 9, Etapa 7, D-110, lote 1).

Leitura e validacao fail-closed das variaveis aprovadas na spec §5.1. Nada aqui
abre socket, resolve nome, toca arquivo ou deriva a credencial: e o passo 1 do
lifecycle (§11), testavel sem efeito. O listener que consome estes valores e
um lote posterior; o `main` NAO le este modulo nesta etapa.

- `MASKGW_PGWIRE_ENABLED` liga somente com o valor BRUTO `1`. Desligado,
  nenhum outro setting e lido ou validado e nenhum segredo e consultado: o
  processo legado fica exatamente como antes.
- Valores nao secretos vem de `RawSettings` (sem strip nem coercao). A senha
  vem do `SecretProvider` existente, com a normalizacao antiga intacta: vazio
  ou so espacos e ausente, e as bordas sao removidas.
- `MASKGW_PGWIRE_BIND` e preservado EXATAMENTE como veio. So os literais
  `127.0.0.1` e `::1` sao loopback; qualquer outro IP e qualquer hostname sao
  externos e exigem cert e chave. Nenhum DNS e consultado aqui: a estrategia de
  resolucao limitada do bind por hostname e do lote do listener.
- Inteiros: so digitos ASCII, sem sinal, espaco nem zero a esquerda, e no
  maximo 9 digitos. Esse limite de representacao/parse (escolha delegada,
  D-110) IMPOE uma faixa efetiva exata: `MAX_SESSIONS` e `IDLE_TIMEOUT_MS`
  aceitam de 1 a 999.999.999; a porta, de 1 a 65535. Nao ha teto oculto de
  32 sessoes: 32 e so o default da §5.1, e a integracao usara o MESMO valor
  no registry de datasources.

`PgwireLimits` reune os numeros auxiliares do listener futuro. Sao defaults
escolhidos sob delegacao do usuario (D-110), nao aprovados individualmente, e
so configuraveis internamente (composition root/testes), nunca por ambiente.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Final

from maskgw.bootstrap.settings import RawSettings
from maskgw.errors import ConfigError
from maskgw.pgwire.credential import MAX_USERNAME_BYTES
from maskgw.secretsource import SecretProvider

ENABLED_ENV: Final = "MASKGW_PGWIRE_ENABLED"
ENABLED_VALUE: Final = "1"
BIND_ENV: Final = "MASKGW_PGWIRE_BIND"
PORT_ENV: Final = "MASKGW_PGWIRE_PORT"
USERNAME_ENV: Final = "MASKGW_PGWIRE_USERNAME"
#: Nome da variavel, nao o valor.
PASSWORD_ENV: Final = "MASKGW_PGWIRE_PASSWORD"  # noqa: S105 - nome de variavel
TLS_CERT_ENV: Final = "MASKGW_PGWIRE_TLS_CERT"
TLS_KEY_ENV: Final = "MASKGW_PGWIRE_TLS_KEY"
MAX_SESSIONS_ENV: Final = "MASKGW_PGWIRE_MAX_SESSIONS"
IDLE_TIMEOUT_MS_ENV: Final = "MASKGW_PGWIRE_IDLE_TIMEOUT_MS"

# Defaults da spec §5.1.
DEFAULT_BIND: Final = "127.0.0.1"
DEFAULT_PORT: Final = 6432
DEFAULT_MAX_SESSIONS: Final = 32
DEFAULT_IDLE_TIMEOUT_MS: Final = 300_000

MIN_PORT: Final = 1
MAX_PORT: Final = 65535
#: Limite de representacao/parse dos inteiros. Impoe o maximo efetivo
#: `MAX_INTEGER_VALUE` para sessoes e idle (a porta tem seu proprio maximo).
MAX_INTEGER_DIGITS: Final = 9
MAX_INTEGER_VALUE: Final = 999_999_999
MAX_HOSTNAME_LENGTH: Final = 253

#: Os UNICOS binds loopback (§5.2). `localhost` e outros IPs de loopback sao
#: externos para a exigencia de TLS.
LOOPBACK_LITERALS: Final[frozenset[str]] = frozenset({"127.0.0.1", "::1"})

_DIGITS: Final = re.compile(r"[1-9][0-9]*")
_LABEL: Final = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def _invalid(name: str) -> ConfigError:
    return ConfigError(f"pgwire: {name} invalido")


@dataclass(frozen=True, slots=True)
class PgwireLimits:
    """Numeros auxiliares do listener (D-110): defaults delegados, internos.

    - `startup_deadline_ms`: prazo absoluto do accept ao fim do startup;
    - `pre_auth_slots`: conexoes nao autenticadas simultaneas;
    - `admission_burst` / `admission_refill_per_s`: token bucket global que
      reserva um token por conexao aceita;
    - `poll_ms`: fatia maxima de espera para conferir o pedido de parada.
    """

    startup_deadline_ms: int = 10_000
    pre_auth_slots: int = 8
    admission_burst: int = 20
    admission_refill_per_s: int = 5
    poll_ms: int = 250

    def __post_init__(self) -> None:
        for value in (
            self.startup_deadline_ms,
            self.pre_auth_slots,
            self.admission_burst,
            self.admission_refill_per_s,
            self.poll_ms,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                msg = "limite do listener pgwire invalido"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True, repr=False)
class PgwireSettings:
    """Settings validados. Construir direto NAO valida: use `resolve`."""

    username: str
    password: str
    bind: str = DEFAULT_BIND
    port: int = DEFAULT_PORT
    tls_cert: str | None = None
    tls_key: str | None = None
    max_sessions: int = DEFAULT_MAX_SESSIONS
    idle_timeout_ms: int = DEFAULT_IDLE_TIMEOUT_MS
    bind_is_hostname: bool = False
    limits: PgwireLimits = field(default_factory=PgwireLimits)

    @property
    def bind_is_loopback(self) -> bool:
        return self.bind in LOOPBACK_LITERALS

    @property
    def tls_configured(self) -> bool:
        return self.tls_cert is not None

    @property
    def tls_required(self) -> bool:
        return not self.bind_is_loopback

    def __repr__(self) -> str:
        # Sem senha, usuario, bind nem caminhos: so a forma.
        return (
            f"PgwireSettings(port={self.port}, loopback={self.bind_is_loopback}, "
            f"tls_configured={self.tls_configured}, max_sessions={self.max_sessions}, "
            f"idle_timeout_ms={self.idle_timeout_ms})"
        )


def _integer(raw: RawSettings, name: str, default: int, *, maximum: int | None = None) -> int:
    value = raw.get_raw(name)
    if value is None:
        return default
    if not value.isascii() or len(value) > MAX_INTEGER_DIGITS or _DIGITS.fullmatch(value) is None:
        raise _invalid(name)
    number = int(value)
    if maximum is not None and number > maximum:
        raise _invalid(name)
    return number


def _is_hostname(value: str) -> bool:
    name = value[:-1] if value.endswith(".") else value
    if not name or not name.isascii() or len(name) > MAX_HOSTNAME_LENGTH:
        return False
    labels = name.split(".")
    if not all(_LABEL.fullmatch(label) for label in labels):
        return False
    # Rotulos so numericos parecem um IP malformado (`1.2.3`): recusado.
    return not all(label.isdigit() for label in labels)


def _bind_kind(value: object) -> bool | None:
    """`False` = IP literal, `True` = hostname, `None` = invalido. Sem DNS."""
    if not isinstance(value, str):
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        is_ip = False
    else:
        is_ip = True
    if is_ip:
        return False
    if _is_hostname(value):
        return True
    return None


def _bind(raw: RawSettings) -> tuple[str, bool]:
    value = raw.get_raw(BIND_ENV)
    if value is None:
        return DEFAULT_BIND, False
    kind = _bind_kind(value)
    if kind is None:
        raise _invalid(BIND_ENV)
    return value, kind


def _path(raw: RawSettings, name: str) -> str | None:
    value = raw.get_raw(name)
    if value is None:
        return None
    if not value or "\x00" in value:
        raise _invalid(name)
    return value


def _username(raw: RawSettings) -> str:
    value = raw.get_raw(USERNAME_ENV)
    if value is None or not value or "\x00" in value:
        raise _invalid(USERNAME_ENV)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        size = MAX_USERNAME_BYTES + 1
    if size > MAX_USERNAME_BYTES:
        raise _invalid(USERNAME_ENV)
    return value


def resolve(
    raw: RawSettings,
    secrets: SecretProvider,
    *,
    limits: PgwireLimits | None = None,
) -> PgwireSettings | None:
    """`None` se desligado; senao, settings validados. Erro fixo, sem valor."""
    if raw.get_raw(ENABLED_ENV) != ENABLED_VALUE:
        return None
    username = _username(raw)
    password = secrets.get(PASSWORD_ENV)
    if password is None:
        raise _invalid(PASSWORD_ENV)
    bind, is_hostname = _bind(raw)
    port = _integer(raw, PORT_ENV, DEFAULT_PORT, maximum=MAX_PORT)
    cert = _path(raw, TLS_CERT_ENV)
    key = _path(raw, TLS_KEY_ENV)
    if (cert is None) != (key is None):
        raise ConfigError("pgwire: certificado e chave TLS devem vir juntos")
    max_sessions = _integer(raw, MAX_SESSIONS_ENV, DEFAULT_MAX_SESSIONS)
    idle_timeout_ms = _integer(raw, IDLE_TIMEOUT_MS_ENV, DEFAULT_IDLE_TIMEOUT_MS)
    result = PgwireSettings(
        username=username,
        password=password,
        bind=bind,
        port=port,
        tls_cert=cert,
        tls_key=key,
        max_sessions=max_sessions,
        idle_timeout_ms=idle_timeout_ms,
        bind_is_hostname=is_hostname,
        limits=limits if limits is not None else PgwireLimits(),
    )
    if result.tls_required and not result.tls_configured:
        raise ConfigError("pgwire: bind fora de loopback exige certificado e chave TLS")
    return result


def _strict_int(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and "\x00" not in value


def validate(settings: PgwireSettings) -> None:
    """Revalida um `PgwireSettings` recebido pronto (a dataclass nao se valida).

    Mesmas regras do `resolve`, para quem recebe settings injetados (listener,
    composition root): falha fechada, com texto fixo, ANTES de qualquer bind.
    """
    if not isinstance(settings, PgwireSettings):
        raise ConfigError("pgwire: settings invalidos")
    username = settings.username
    if not _valid_text(username) or len(username.encode("utf-8", "replace")) > MAX_USERNAME_BYTES:
        raise _invalid(USERNAME_ENV)
    if not _valid_text(settings.password):
        raise _invalid(PASSWORD_ENV)
    kind = _bind_kind(settings.bind)
    if kind is None or kind != settings.bind_is_hostname:
        raise _invalid(BIND_ENV)
    if not _strict_int(settings.port, MIN_PORT, MAX_PORT):
        raise _invalid(PORT_ENV)
    if not _strict_int(settings.max_sessions, 1, MAX_INTEGER_VALUE):
        raise _invalid(MAX_SESSIONS_ENV)
    if not _strict_int(settings.idle_timeout_ms, 1, MAX_INTEGER_VALUE):
        raise _invalid(IDLE_TIMEOUT_MS_ENV)
    cert, key = settings.tls_cert, settings.tls_key
    if (cert is None) != (key is None):
        raise ConfigError("pgwire: certificado e chave TLS devem vir juntos")
    if cert is not None and (not _valid_text(cert) or not _valid_text(key)):
        raise _invalid(TLS_CERT_ENV)
    if not isinstance(settings.limits, PgwireLimits):
        raise ConfigError("pgwire: limites do listener invalidos")
    if settings.tls_required and not settings.tls_configured:
        raise ConfigError("pgwire: bind fora de loopback exige certificado e chave TLS")


__all__ = [
    "DEFAULT_BIND",
    "DEFAULT_IDLE_TIMEOUT_MS",
    "DEFAULT_MAX_SESSIONS",
    "DEFAULT_PORT",
    "ENABLED_ENV",
    "LOOPBACK_LITERALS",
    "MAX_INTEGER_VALUE",
    "PgwireLimits",
    "PgwireSettings",
    "resolve",
    "validate",
]
