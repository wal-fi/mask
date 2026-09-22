"""Validacao de destino e pinning de DNS contra SSRF/rebinding."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from maskgw.datasource.models import DatasourceValidationError, DestinationPolicy, validate_host

AddressResolver = Callable[[str, int], Sequence[str]]
_METADATA_ADDRESSES: Final = frozenset(
    {
        "100.100.100.200",  # Alibaba metadata
        "169.254.169.254",  # common cloud metadata
        "169.254.170.2",  # ECS metadata
    }
)
_IPV6: Final = 6
_MAX_PORT: Final = 65_535


class DestinationValidationError(DatasourceValidationError):
    """Destino ausente, proibido ou sem resolucao segura."""


class DestinationChangedError(DestinationValidationError):
    """DNS resolveu para um conjunto diferente do validado/persistido."""


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedDestination:
    host: str
    port: int
    addresses: tuple[str, ...]

    def __repr__(self) -> str:
        return f"ResolvedDestination(host={self.host!r}, port={self.port}, addresses=<redacted>)"


def _system_resolver(host: str, port: int) -> Sequence[str]:
    try:
        results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise DestinationValidationError("destino nao resolvido") from None
    addresses: list[str] = []
    for result in results:
        address = result[4][0]
        if not isinstance(address, str):
            raise DestinationValidationError("endereco resolvido invalido")
        addresses.append(address)
    return tuple(addresses)


def _canonical_addresses(addresses: Sequence[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            raise DestinationValidationError("endereco resolvido invalido") from None
        if address.version == _IPV6 and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        normalized.add(address.compressed)
    if not normalized:
        raise DestinationValidationError("destino nao resolvido")
    return tuple(sorted(normalized))


def _validate_address(address_text: str, *, host: str, policy: DestinationPolicy) -> None:
    address = ipaddress.ip_address(address_text)
    if address.version == _IPV6 and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    canonical = address.compressed
    if canonical in _METADATA_ADDRESSES:
        raise DestinationValidationError("destino de metadata recusado")
    if address.is_loopback:
        if not policy.allow_loopback:
            raise DestinationValidationError("loopback recusado")
        return
    if address.is_unspecified or address.is_link_local or address.is_multicast:
        raise DestinationValidationError("destino especial recusado")
    if address.is_private:
        return
    if not address.is_global:
        raise DestinationValidationError("destino reservado recusado")
    if not policy.allow_public or host.lower() not in policy.allowed_hosts:
        raise DestinationValidationError("destino global nao autorizado")


def resolve_destination(
    host: str,
    port: int,
    *,
    policy: DestinationPolicy | None = None,
    resolver: AddressResolver | None = None,
    expected_addresses: Sequence[str] | None = None,
) -> ResolvedDestination:
    """Resolve e valida todas as respostas, comparando pinning quando pedido."""
    normalized_host = validate_host(host)
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= _MAX_PORT:
        raise DestinationValidationError("porta invalida")
    effective_policy = policy if policy is not None else DestinationPolicy()
    effective_resolver = resolver if resolver is not None else _system_resolver
    resolved = _canonical_addresses(effective_resolver(normalized_host, port))
    for address in resolved:
        _validate_address(address, host=normalized_host, policy=effective_policy)
    if expected_addresses is not None:
        try:
            expected = _canonical_addresses(tuple(expected_addresses))
        except DestinationValidationError:
            raise DestinationChangedError() from None
        if resolved != expected:
            raise DestinationChangedError()
    return ResolvedDestination(host=normalized_host, port=port, addresses=resolved)
