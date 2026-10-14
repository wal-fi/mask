"""Resolucao limitada do hostname do bind PGWire (Fase 9, Etapa 7, D-110, lote 2).

Politica das respostas DNS do bind por hostname. O trabalho limitado (filho
descartavel supervisionado, prazo, capacidade e recolhimento) e o job fixo de
`maskgw.datasource.verify` (lote 1); aqui so se decide sobre a resposta BRUTA
que ele devolve: triplas JSON ASCII `[family, ip, scope_id]`.

Vale SO para respostas vindas de DNS. Bind literal e o colaborador interno
explicito `resolved_addresses` nao passam por aqui e mantem a semantica
anterior.

- Esquema estrito: ate 16 KiB, ASCII, lista de 1 a 64 entradas BRUTAS (antes
  de deduplicar); cada entrada e exatamente `[family, ip, scope_id]`, com
  `family` int exato (nao `bool`) igual a `AF_INET`/`AF_INET6`, `ip` texto
  ASCII (IPv4 ate 15 caracteres, IPv6 sem escopo ate 45), sem `%`, da MESMA
  familia, e `scope_id` int exato igual a 0.
- Politica, por endereco, na ordem (a primeira regra que casa decide): recusa
  `0.0.0.0`/`::`; aceita `::1`; recusa `255.255.255.255`; recusa multicast
  (`224.0.0.0/4`, `ff00::/8`); recusa IPv4-mapped (`::ffff:0:0/96`); recusa o
  restante de `::/96` (IPv4-compatible); recusa link-local (`169.254.0.0/16`,
  `fe80::/10`); aceita `127.0.0.0/8`; aceita os demais, sujeitos ao bind. Redes
  explicitas: nenhum classificador do `ipaddress` que varie entre versoes
  (`is_reserved`, `is_private`, `is_global`).
- Uma entrada malformada ou proibida em QUALQUER posicao recusa a resposta
  inteira: nada e filtrado. Depois da deduplicacao canonica, so EXATAMENTE um
  endereco e aceito; dois ou mais distintos (inclusive dual stack) recusam.
  Sem escolher o primeiro, sem preferir familia, sem fallback nem retry.
- O hostname continua exigindo TLS mesmo quando resolve para loopback: quem
  decide isso e `bind_is_hostname`, que nao muda.

Toda falha e a MESMA `ConfigError` de texto fixo, levantada fora de `except`:
sem causa, sem contexto, sem host e sem endereco.
"""

from __future__ import annotations

import ipaddress
import json
import socket
from typing import Final, TypeGuard

from maskgw.datasource import verify as _verify
from maskgw.errors import ConfigError

#: Teto da resposta: o mesmo do leitor do job DNS.
MAX_ANSWER_BYTES: Final = 16 * 1024

#: Entradas BRUTAS aceitas, antes de qualquer deduplicacao.
MAX_ANSWER_ENTRIES: Final = 64

#: Maior texto de IPv4 (`255.255.255.255`) e de IPv6 sem escopo
#: (`ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255`).
MAX_IPV4_TEXT: Final = 15
MAX_IPV6_TEXT: Final = 45

_FAMILY_INET: Final = int(socket.AF_INET)
_FAMILY_INET6: Final = int(socket.AF_INET6)

_ERROR: Final = "pgwire: bind por hostname nao resolvido"

_Address = ipaddress.IPv4Address | ipaddress.IPv6Address

_V4_WILDCARD: Final = ipaddress.IPv4Address("0.0.0.0")  # noqa: S104 - recusado, nao usado
_V6_WILDCARD: Final = ipaddress.IPv6Address("::")
_V6_LOOPBACK: Final = ipaddress.IPv6Address("::1")
_V4_BROADCAST: Final = ipaddress.IPv4Address("255.255.255.255")
_V4_MULTICAST: Final = ipaddress.IPv4Network("224.0.0.0/4")
_V6_MULTICAST: Final = ipaddress.IPv6Network("ff00::/8")
_V6_MAPPED: Final = ipaddress.IPv6Network("::ffff:0:0/96")
_V6_COMPATIBLE: Final = ipaddress.IPv6Network("::/96")
_V4_LINK_LOCAL: Final = ipaddress.IPv4Network("169.254.0.0/16")
_V6_LINK_LOCAL: Final = ipaddress.IPv6Network("fe80::/10")
_V4_LOOPBACK: Final = ipaddress.IPv4Network("127.0.0.0/8")


def _is_exact_int(value: object) -> TypeGuard[int]:
    """Inteiro EXATO: `bool` (subclasse de `int`) e `float` nao contam."""
    return type(value) is int


def _shape(item: object) -> tuple[int, str] | None:
    """`(family, ip)` de uma tripla com tipos EXATOS e `scope_id` 0; ou `None`."""
    if type(item) is not list or len(item) != 3:  # noqa: PLR2004 - [family, ip, scope_id]
        return None
    family, text, scope = item
    if not _is_exact_int(family) or not _is_exact_int(scope) or scope != 0:
        return None
    if type(text) is not str or not text.isascii() or "%" in text:
        return None
    return family, text


def _entry(item: object) -> _Address | None:
    """Uma tripla bruta validada como endereco da MESMA familia; ou `None`."""
    shape = _shape(item)
    if shape is None:
        return None
    family, text = shape
    try:
        if family == _FAMILY_INET and len(text) <= MAX_IPV4_TEXT:
            return ipaddress.IPv4Address(text)
        if family == _FAMILY_INET6 and len(text) <= MAX_IPV6_TEXT:
            address = ipaddress.IPv6Address(text)
            return address if address.scope_id is None else None
    except ValueError:
        return None
    return None


def _acceptable(address: _Address) -> bool:
    """Politica por endereco, na ORDEM documentada; a primeira regra decide."""
    if isinstance(address, ipaddress.IPv4Address):
        rules_v4: tuple[tuple[bool, bool], ...] = (
            (address == _V4_WILDCARD, False),
            (address == _V4_BROADCAST, False),
            (address in _V4_MULTICAST, False),
            (address in _V4_LINK_LOCAL, False),
            (address in _V4_LOOPBACK, True),
        )
        return next((decision for matched, decision in rules_v4 if matched), True)
    rules_v6: tuple[tuple[bool, bool], ...] = (
        (address == _V6_WILDCARD, False),
        (address == _V6_LOOPBACK, True),
        (address in _V6_MULTICAST, False),
        (address in _V6_MAPPED, False),
        (address in _V6_COMPATIBLE, False),
        (address in _V6_LINK_LOCAL, False),
    )
    return next((decision for matched, decision in rules_v6 if matched), True)


def _parse(raw: object) -> list[object] | None:
    """A lista bruta, se a resposta e JSON ASCII limitado; `None` se nao."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ANSWER_BYTES:
        return None
    if not raw.isascii():
        return None
    try:
        value = json.loads(raw.decode("ascii"))
    except (ValueError, RecursionError):
        # `RecursionError`: aninhamento profundo dentro do teto de bytes.
        return None
    if type(value) is not list or not 0 < len(value) <= MAX_ANSWER_ENTRIES:
        return None
    return value


def decide_answer(raw: object) -> str | None:
    """O UNICO endereco aceitavel da resposta bruta, canonico; `None` se nao.

    Recusa a resposta inteira se qualquer entrada for malformada ou proibida;
    deduplica de forma canonica e exige exatamente um endereco.
    """
    entries = _parse(raw)
    if entries is None:
        return None
    addresses: list[_Address] = []
    for item in entries:
        address = _entry(item)
        if address is None or not _acceptable(address):
            return None
        addresses.append(address)
    unique = list(dict.fromkeys(addresses))
    if len(unique) != 1:
        return None
    return str(unique[0])


def resolve_bind_address(host: str) -> str:
    """Resolve o hostname do bind UMA vez, pelo job DNS supervisionado.

    Devolve o literal canonico que o listener vai usar (`AI_NUMERICHOST`, sem
    DNS posterior). Levanta somente `ConfigError` de texto fixo.
    """
    raw: bytes | None = None
    try:
        raw = _verify.resolve_bind_host_in_child(host)
    except _verify.BindDnsError:
        raw = None
    address = None if raw is None else decide_answer(raw)
    if address is None:
        # Fora do `except`: nem `__cause__` nem `__context__` (D-017).
        raise ConfigError(_ERROR)
    return address


__all__ = [
    "MAX_ANSWER_BYTES",
    "MAX_ANSWER_ENTRIES",
    "MAX_IPV4_TEXT",
    "MAX_IPV6_TEXT",
    "decide_answer",
    "resolve_bind_address",
]
