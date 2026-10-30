"""Public-API counterproofs for the IPv6 type-narrowing-only correction.

No DNS, socket, database or environment secret is used. These invariants
must pass both before and after the typing correction, on both runtimes.
"""

import pytest

from maskgw.datasource.destination import (
    DestinationChangedError,
    DestinationValidationError,
    resolve_destination,
)
from maskgw.datasource.models import DestinationPolicy

HOST = "db.example.test"
POLICIES = (
    DestinationPolicy(),
    DestinationPolicy(allow_loopback=True),
    DestinationPolicy(allow_public=True, allowed_hosts=(HOST,)),
    DestinationPolicy(allow_public=True, allow_loopback=True, allowed_hosts=(HOST,)),
)
IPV4_CASES = (
    "10.23.45.67",
    "172.16.1.2",
    "192.168.2.3",
    "127.0.0.1",
    "0.0.0.0",  # noqa: S104 - classifier input, never a bind
    "169.254.169.254",
    "169.254.170.2",
    "100.100.100.200",
    "169.254.1.1",
    "224.0.0.1",
    "8.8.8.8",
    "192.0.2.1",
    "255.255.255.255",
)


def _outcome(
    addresses: tuple[str, ...], policy: DestinationPolicy
) -> tuple[str, ...] | type[DestinationValidationError]:
    try:
        return resolve_destination(
            HOST, 5432, policy=policy, resolver=lambda _host, _port: addresses
        ).addresses
    except DestinationValidationError as error:
        return type(error)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("address", IPV4_CASES)
def test_mapped_ipv4_preserves_literal_policy_result(address, policy):
    assert _outcome((f"::ffff:{address}",), policy) == _outcome((address,), policy)


@pytest.mark.parametrize("policy_index", range(len(POLICIES)))
@pytest.mark.parametrize(
    ("address", "allowed"),
    (
        ("fd00::1", (True, True, True, True)),
        ("::1", (False, True, False, True)),
        ("::", (False, False, False, False)),
        ("fe80::1", (False, False, False, False)),
        ("ff02::1", (False, False, False, False)),
        ("2001:4860:4860::8888", (False, False, True, True)),
    ),
)
def test_native_ipv6_keeps_its_own_policy_classification(address, allowed, policy_index):
    outcome = _outcome((address,), POLICIES[policy_index])
    if allowed[policy_index]:
        assert outcome == (address,)
    else:
        assert outcome is DestinationValidationError


@pytest.mark.parametrize("address", ("169.254.169.254", "169.254.170.2", "100.100.100.200"))
@pytest.mark.parametrize("mapped", (False, True))
def test_metadata_stays_forbidden_even_with_both_opt_ins(address, mapped):
    supplied = f"::ffff:{address}" if mapped else address
    assert _outcome((supplied,), POLICIES[-1]) is DestinationValidationError


@pytest.mark.parametrize(
    "bad", ("::ffff:169.254.169.254", "::ffff:127.0.0.1", "8.8.8.8", "fe80::1")
)
@pytest.mark.parametrize("bad_first", (False, True))
def test_one_forbidden_answer_rejects_the_complete_set(bad, bad_first):
    answers = (bad, "10.23.45.67") if bad_first else ("10.23.45.67", bad)
    assert _outcome(answers, POLICIES[0]) is DestinationValidationError


def test_pinning_normalizes_duplicates_mapped_ipv4_and_native_ipv6_once():
    calls: list[tuple[str, int]] = []
    answers = ("::ffff:10.1.2.3", "10.1.2.3", "FD00:0:0:0:0:0:0:1", "fd00::1")

    def resolver(host: str, port: int) -> tuple[str, ...]:
        calls.append((host, port))
        return answers

    result = resolve_destination(
        HOST,
        5432,
        resolver=resolver,
        expected_addresses=("fd00::1", "::ffff:10.1.2.3"),
    )
    assert result.addresses == ("10.1.2.3", "fd00::1")
    assert calls == [(HOST, 5432)]


@pytest.mark.parametrize(
    ("actual", "expected"),
    (("10.1.2.3", "10.1.2.4"), ("::ffff:10.1.2.3", "::ffff:10.1.2.4"), ("fd00::1", "fd00::2")),
)
def test_changed_pin_is_still_refused(actual, expected):
    with pytest.raises(DestinationChangedError):
        resolve_destination(
            HOST,
            5432,
            resolver=lambda _host, _port: (actual,),
            expected_addresses=(expected,),
        )


@pytest.mark.parametrize(
    "answers", ((), ("not-ip",), ("",), ("127.0.0.1:5432",), ("10.1.2.3", "::ffff:not-ip"))
)
def test_empty_or_malformed_resolution_never_becomes_usable(answers):
    assert _outcome(answers, POLICIES[-1]) is DestinationValidationError
