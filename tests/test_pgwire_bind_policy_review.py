"""Revisao independente da politica DNS: limites numericos e mistura de respostas."""

from __future__ import annotations

import ipaddress
import json
import random
import socket

from maskgw.pgwire.bind_resolution import decide_answer


def _answer(entries: list[object]) -> bytes:
    return json.dumps(entries, separators=(",", ":")).encode("ascii")


def test_dns_policy_matches_explicit_numeric_ranges_at_boundaries() -> None:
    """Oracle numerico, independente de classificadores/regras de producao."""
    random_source = random.Random(1947)  # noqa: S311 - amostras deterministicas do teste
    ranges = (
        (32, 0, 0),
        (32, 0xFFFFFFFF, 0xFFFFFFFF),
        (32, 0xE0000000, 0xEFFFFFFF),
        (32, 0xA9FE0000, 0xA9FEFFFF),
        (128, 0, 0),
        (128, 0xFF << 120, (1 << 128) - 1),
        (128, 0xFFFF << 32, (0xFFFF << 32) + (1 << 32) - 1),
        (128, 2, (1 << 32) - 1),
        (128, 0xFE80 << 112, (0xFEBF << 112) + (1 << 112) - 1),
    )
    for bits, family in ((32, socket.AF_INET), (128, socket.AF_INET6)):
        samples = {0, 1, (1 << bits) - 1}
        samples.update(random_source.getrandbits(bits) for _ in range(400))
        relevant = [(lo, hi) for width, lo, hi in ranges if width == bits]
        for lo, hi in relevant:
            samples.update(
                n for n in (lo - 1, lo, lo + 1, hi - 1, hi, hi + 1) if 0 <= n < 1 << bits
            )
        address_type = ipaddress.IPv4Address if bits == 32 else ipaddress.IPv6Address
        for number in samples:
            text = str(address_type(number))
            expected = None if any(lo <= number <= hi for lo, hi in relevant) else text
            entry = [int(family), text, 0]
            assert decide_answer(_answer([entry])) == expected, text
            # O limite bruto precede a deduplicacao; 64 iguais nao viram 65 validos.
            assert decide_answer(_answer([entry] * 64)) == expected, text
            assert decide_answer(_answer([entry] * 65)) is None, text


def test_dns_never_filters_bad_answers_or_selects_first_distinct_address() -> None:
    valid = [int(socket.AF_INET), "127.0.0.1", 0]
    bad_entries: list[object] = [
        [int(socket.AF_INET), "0.0.0.0", 0],  # noqa: S104 - entrada recusada, nenhum bind
        [int(socket.AF_INET), "224.0.0.1", 0],
        [int(socket.AF_INET6), "::ffff:127.0.0.1", 0],
        [int(socket.AF_INET6), "fe80::1", 0],
        [int(socket.AF_INET6), "::1", 1],
        [int(socket.AF_INET6), "::1%0", 0],
        [int(socket.AF_INET), "::1", 0],
        [int(socket.AF_INET6), "127.0.0.1", 0],
        [int(socket.AF_INET), "127.0.0.1", False],
        [int(socket.AF_INET), "127.0.0.1", 0.0],
        [float(socket.AF_INET), "127.0.0.1", 0],
        [True, "127.0.0.1", 0],
        [int(socket.AF_INET), "127.0.0.2", 0],
        [int(socket.AF_INET6), "::1", 0],
        None,
        {},
        [],
    ]
    for bad in bad_entries:
        for entries in ([bad, valid], [valid, bad], [valid, bad, valid]):
            assert decide_answer(_answer(entries)) is None, entries


def test_dns_wire_shape_and_json_fail_closed_without_recursive_exception() -> None:
    invalid = (
        b"[" * 2000 + b"]" * 2000,
        b'[[2,"127.0.0.1",0]] trailing',
        b'[[2,"127.0.0.1",0], NaN]',
        b"[" + b"9" * 10000 + b"]",
        b"[]",
        b"{}",
        b"null",
        b"\xff",
        b" " * 16385,
    )
    for raw in invalid:
        assert decide_answer(raw) is None
