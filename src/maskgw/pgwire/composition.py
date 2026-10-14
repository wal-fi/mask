"""Composicao interna do listener PGWire (Fase 9, Etapa 7, D-110, lote 4).

Ponte entre o composition root e o listener. Importado SO quando
`build_application` recebe `pgwire`: com ele `None`, nada de `maskgw.pgwire`
e carregado. O listener continua isolado do runtime; este modulo e o unico
que conhece os dois lados.

- `PgwireComposition`: settings mais os DOIS colaboradores internos
  explicitos: `resolved_addresses` (bind por hostname com exatamente um IP
  literal ja resolvido, confiavel e sem DNS; semantica inalterada) e
  `test_port` (so `0`, so testes). Nao vem de ambiente; a ativacao
  operacional segue bloqueada no `main`.
- `prepare_pgwire`, em duas fases. A primeira revalida settings, a forma do
  colaborador e o `test_port` e prepara TLS (le os arquivos de cert e chave)
  e principal. So depois, e so para hostname SEM colaborador, a segunda
  resolve o bind UMA vez pelo job DNS limitado (`bind_resolution`). Tudo
  antes de qualquer store, config, lock, upstream, bind, Admin HTTP ou MCP.
  Somente o `PreparedPgwire` final existe, e sempre com o literal final.
- `session_limits`: `MAX_SESSIONS` do PGWire e a fonte UNICA de S, tambem no
  `RegistryLimits` (candidatos e aposentados preservados). Sem teto 32.
- `sealed_alias_check`: o callback de alias le SOMENTE `service.view()`, que
  so toma o `_view_lock` curto da troca da referencia do selo (nao e
  lock-free). Sem lock do store nem da secao de escrita, sem snapshot,
  filesystem, DNS, sessao de registry ou upstream.
- `build_listener`: monta o listener SEM inicia-lo (quem chama adota antes
  do `start()`).
"""

from __future__ import annotations

import dataclasses
import ipaddress
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maskgw.errors import ConfigError
from maskgw.pgwire.bind_resolution import resolve_bind_address
from maskgw.pgwire.credential import PrincipalCredential, prepare_principal
from maskgw.pgwire.framing import valid_alias
from maskgw.pgwire.listener import PgwireListener
from maskgw.pgwire.settings import PgwireSettings, validate
from maskgw.pgwire.tls import ServerTls, prepare_server_tls

if TYPE_CHECKING:
    from maskgw.runtime.datasource_service import (
        DatasourceCatalogSettings,
        DatasourceRuntimeService,
    )


@dataclass(frozen=True, slots=True)
class PgwireComposition:
    """Pedido interno de composicao do listener. `repr` sem segredo."""

    settings: PgwireSettings
    resolved_addresses: tuple[str, ...] | None = None
    test_port: int | None = None

    def __repr__(self) -> str:
        return f"PgwireComposition(settings={self.settings!r})"


@dataclass(frozen=True, slots=True, repr=False)
class PreparedPgwire:
    """Settings revalidados, TLS e principal ja preparados."""

    settings: PgwireSettings
    principal: PrincipalCredential
    tls: ServerTls | None
    resolved_addresses: tuple[str, ...] | None
    test_port: int | None

    def __repr__(self) -> str:
        return "PreparedPgwire(<redigido>)"


def _is_ip_literal(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True, repr=False)
class _ValidatedPgwire:
    """Fase 1 concluida, privada: ainda SEM o literal de um hostname a resolver.

    Nunca sai deste modulo; so `_finalize` produz o `PreparedPgwire`.
    """

    settings: PgwireSettings
    principal: PrincipalCredential
    tls: ServerTls | None
    resolved_addresses: tuple[str, ...] | None
    test_port: int | None

    def __repr__(self) -> str:
        return "_ValidatedPgwire(<redigido>)"


def _validate(request: PgwireComposition) -> _ValidatedPgwire:
    """Fase 1: settings, colaborador, porta de teste, TLS e principal.

    Sem DNS. O TLS le os arquivos de cert e chave (nao e livre de efeito
    externo), mas tudo isto precede catalogo, config, lock, upstream e bind.
    """
    if not isinstance(request, PgwireComposition):
        raise ConfigError("pgwire: composicao invalida")
    settings = request.settings
    validate(settings)
    if request.test_port is not None and request.test_port != 0:
        raise ConfigError("pgwire: porta de teste so pode ser efemera")
    # A dataclass nao se valida: o valor injetado e conferido como `object`.
    raw_resolved: object = request.resolved_addresses
    if raw_resolved is not None and not isinstance(raw_resolved, tuple):
        raise ConfigError("pgwire: enderecos resolvidos invalidos")
    resolved = request.resolved_addresses
    # Colaborador explicito (confiavel, interno): semantica inalterada. Com
    # hostname, UM literal ja resolvido (o listener confere de novo); bind
    # literal nao aceita resolucao. Hostname SEM colaborador e resolvido na
    # fase 2, depois de TLS e principal.
    if settings.bind_is_hostname:
        if resolved is not None and (len(resolved) != 1 or not _is_ip_literal(resolved[0])):
            raise ConfigError("pgwire: bind por hostname exige um endereco literal resolvido")
    elif resolved is not None:
        raise ConfigError("pgwire: endereco resolvido so vale para bind por hostname")
    tls: ServerTls | None = None
    if settings.tls_cert is not None and settings.tls_key is not None:
        tls = prepare_server_tls(settings.tls_cert, settings.tls_key)
    principal = prepare_principal(settings.username, settings.password)
    return _ValidatedPgwire(settings, principal, tls, resolved, request.test_port)


def _finalize(validated: _ValidatedPgwire) -> PreparedPgwire:
    """Fase 2: o literal FINAL do bind; so aqui nasce o `PreparedPgwire`.

    Hostname sem colaborador: UMA resolucao limitada (`bind_resolution`), sem
    retry; falha e `ConfigError` fixa. Literal ou colaborador: sem DNS.
    """
    resolved = validated.resolved_addresses
    if validated.settings.bind_is_hostname and resolved is None:
        resolved = (resolve_bind_address(validated.settings.bind),)
    return PreparedPgwire(
        validated.settings, validated.principal, validated.tls, resolved, validated.test_port
    )


def prepare_pgwire(request: PgwireComposition) -> PreparedPgwire:
    """Valida, prepara e fixa o literal do bind. Falha fechada."""
    return _finalize(_validate(request))


def session_limits(
    catalog: DatasourceCatalogSettings, settings: PgwireSettings
) -> DatasourceCatalogSettings:
    """Catalogo com `max_sessions` = o MESMO S do PGWire (fonte unica)."""
    limits = dataclasses.replace(catalog.limits, max_sessions=settings.max_sessions)
    return dataclasses.replace(catalog, limits=limits)


def sealed_alias_check(service: DatasourceRuntimeService) -> Callable[[str], bool]:
    """Callback de alias sobre o selo D-108: so metadados imutaveis.

    Le a referencia do selo por `service.view()` (o `_view_lock` curto dela,
    nada mais): sem lock do store, secao de escrita, filesystem, DNS ou
    upstream.

    `True` so para alias valido, publicado no selo corrente e com o registro
    correspondente habilitado no MESMO selo. Selo indisponivel, alias
    invalido, ausente ou desabilitado: `False` (falha uniforme no driver).
    """

    def accepted(alias: str) -> bool:
        if not valid_alias(alias):
            return False
        view = service.view()
        if view is None:
            return False
        datasource_id = next(
            (item.datasource_id for item in view.published if item.alias == alias), None
        )
        if datasource_id is None:
            return False
        return any(
            record.id == datasource_id and record.alias == alias and record.enabled is True
            for record in view.datasources
        )

    return accepted


def build_listener(
    prepared: PreparedPgwire, *, alias_accepted: Callable[[str], bool]
) -> PgwireListener:
    """Listener montado e NAO iniciado."""
    resolved: Sequence[str] | None = prepared.resolved_addresses
    return PgwireListener(
        prepared.settings,
        principal=prepared.principal,
        tls=prepared.tls,
        alias_accepted=alias_accepted,
        resolved_addresses=resolved,
        test_port=prepared.test_port,
    )


__all__ = [
    "PgwireComposition",
    "PreparedPgwire",
    "build_listener",
    "prepare_pgwire",
    "sealed_alias_check",
    "session_limits",
]
