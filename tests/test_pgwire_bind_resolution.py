"""D-110, lote 2: politica do bind PGWire por hostname e integracao na composicao.

Sem DNS de rede: as respostas vem de bytes controlados ou do codigo REAL do
filho com um `getaddrinfo` substituido. Prova:

- esquema estrito das triplas `[family, ip, scope_id]` (tipos exatos, sem
  `bool`/`float`, ASCII, tetos de bytes, entradas e texto, sem escopo);
- politica por endereco na ORDEM documentada, sem classificadores do
  `ipaddress` sensiveis a versao (`::1` aceito apesar de `is_reserved`);
- resposta inteira recusada por UMA entrada ruim, em qualquer posicao;
  deduplicacao canonica e exatamente um endereco; dual stack recusado;
- erro fixo, sem host, endereco, causa ou contexto; UMA chamada, sem retry;
- composicao: validacao, TLS e principal ANTES da resolucao; literal e
  colaborador explicito (inclusive wildcard e escopo) sem resolucao;
- o literal fica selado no `PreparedPgwire`; listener e cliente sem DNS.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

import maskgw.datasource.verify as verify_module
import maskgw.pgwire.bind_resolution as bind_module
import maskgw.pgwire.composition as composition_module
from maskgw.datasource.verify import BindDnsError, BindDnsFailure
from maskgw.errors import ConfigError
from maskgw.pgwire.bind_resolution import decide_answer, resolve_bind_address
from maskgw.pgwire.composition import PgwireComposition, build_listener, prepare_pgwire
from maskgw.pgwire.listener import ListenerState
from tests.pgwire_driver_support import watchdog
from tests.pgwire_listener_support import USER, listener_threads, make_settings, new_credential
from tests.pgwire_support import make_certificate
from tests.test_datasource_verify_supervisor import _CountingSlots

INET = int(socket.AF_INET)
INET6 = int(socket.AF_INET6)
HOST = "gateway.test"
ERROR = "pgwire: bind por hostname nao resolvido"
DNS_CODE = verify_module._BIND_DNS_CHILD_CODE


def _raw(*entries: object) -> bytes:
    return json.dumps(list(entries), separators=(",", ":")).encode("ascii")


def _fake_child(entries: str) -> str:
    """O codigo REAL do filho, com `getaddrinfo` controlado (sem DNS de rede)."""
    return f"import socket\nsocket.getaddrinfo = lambda *a, **k: {entries}\n" + DNS_CODE


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dns = _CountingSlots(verify_module._BIND_DNS_MAX_CONCURRENT)
    monkeypatch.setattr(verify_module, "_BIND_SLOTS", dns)
    monkeypatch.setattr(verify_module, "_BIND_LEDGER", verify_module._Ledger(dns))
    with watchdog(120):
        yield
    assert verify_module._BIND_LEDGER.pending == 0
    assert not listener_threads()


@pytest.fixture(scope="module")
def credential() -> tuple[Any, str]:
    return new_credential()


@pytest.fixture
def tls_files(tmp_path: Path) -> tuple[str, str]:
    cert, _, _ = make_certificate(tmp_path, "rsa-sha256")
    return str(cert.cert_path), str(cert.key_path)


def _hostname_settings(password: str, tls_files: tuple[str, str], /, **changes: Any) -> Any:
    settings = make_settings(password, bind=HOST, bind_is_hostname=True, tls=True)
    fields = {f: getattr(settings, f) for f in settings.__dataclass_fields__}
    fields.update({"tls_cert": tls_files[0], "tls_key": tls_files[1], **changes})
    return type(settings)(**fields)


class _Spy:
    """Substitui o job DNS: conta chamadas e devolve a resposta configurada."""

    def __init__(self, answer: bytes | BaseException) -> None:
        self.answer = answer
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, host: str, **kwargs: Any) -> bytes:
        self.calls.append((host, kwargs))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def _spy(monkeypatch: pytest.MonkeyPatch, answer: bytes | BaseException) -> _Spy:
    spy = _Spy(answer)
    monkeypatch.setattr(verify_module, "resolve_bind_host_in_child", spy)
    return spy


def _refused(monkeypatch: pytest.MonkeyPatch, answer: bytes | BaseException) -> None:
    spy = _spy(monkeypatch, answer)
    with pytest.raises(ConfigError) as caught:
        resolve_bind_address(HOST)
    error = caught.value
    assert str(error) == ERROR
    assert error.__cause__ is None
    assert error.__context__ is None
    assert len(spy.calls) == 1, "uma chamada, sem retry"


# ---- esquema estrito ---------------------------------------------------------


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([[INET, "10.0.0.7", 0]], "10.0.0.7"),
        ([[INET6, "2001:db8::1", 0]], "2001:db8::1"),
        ([[INET6, "2001:0DB8:0000::0001", 0]], "2001:db8::1"),  # canonico
        (
            [[INET6, "2001:ffff:ffff:ffff:ffff:ffff:255.255.255.255", 0]],  # 45 caracteres
            "2001:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
        ),
    ],
)
def test_valid_single_answer_returns_the_canonical_literal(
    entries: list[object], expected: str
) -> None:
    assert decide_answer(_raw(*entries)) == expected


_MALFORMED: list[tuple[str, bytes]] = [
    ("vazio", b""),
    ("nao-json", b"[[2,"),
    ("nao-ascii", '[[2,"10.0.0.1",0]]\u00e9'.encode()),
    ("objeto", b'{"a":1}'),
    ("texto", b'"10.0.0.1"'),
    ("numero", b"1"),
    ("nulo", b"null"),
    ("lista-vazia", b"[]"),
    ("entrada-objeto", b'[{"f":2}]'),
    ("entrada-texto", b'["10.0.0.1"]'),
    ("entrada-com-2", _raw([INET, "10.0.0.1"])),
    ("entrada-com-4", _raw([INET, "10.0.0.1", 0, 0])),
    ("family-true", _raw([True, "10.0.0.1", 0])),
    ("family-false", _raw([False, "10.0.0.1", 0])),
    ("family-float", _raw([float(INET), "10.0.0.1", 0])),
    ("family-texto", _raw([str(INET), "10.0.0.1", 0])),
    ("family-desconhecida", _raw([999, "10.0.0.1", 0])),
    ("family-nula", _raw([None, "10.0.0.1", 0])),
    ("ip-nulo", _raw([INET, None, 0])),
    ("ip-numero", _raw([INET, 167772161, 0])),
    ("ip-vazio", _raw([INET, "", 0])),
    ("ip-nao-ascii", _raw([INET, "\uff11\uff10.0.0.1", 0])),
    ("ip-zero-a-esquerda", _raw([INET, "010.0.0.1", 0])),
    ("ip-hostname", _raw([INET, "gateway.test", 0])),
    ("ipv4-texto-acima-de-15", _raw([INET, "1" * 16, 0])),
    ("ipv6-texto-acima-de-45", _raw([INET6, "1" * 46, 0])),
    ("ipv6-com-escopo-no-texto", _raw([INET6, "fe80::1%1", 0])),
    ("ipv6-com-escopo-numerico", _raw([INET6, "2001:db8::1", 5])),
    ("ipv4-com-percent", _raw([INET, "10.0.0.1%1", 0])),
    ("scope-false", _raw([INET, "10.0.0.1", False])),
    ("scope-true", _raw([INET, "10.0.0.1", True])),
    ("scope-float", _raw([INET, "10.0.0.1", 0.0])),
    ("scope-nulo", _raw([INET, "10.0.0.1", None])),
    ("scope-nan", b'[[2,"10.0.0.1",NaN]]'),
    ("familia-trocada-v4-com-v6", _raw([INET, "::1", 0])),
    ("familia-trocada-v6-com-v4", _raw([INET6, "10.0.0.1", 0])),
    ("acima-de-16-kib", _raw(*[[INET, "10.0.0.1", 0]] * 64) + b" " * (16 * 1024)),
    ("aninhamento-profundo", b"[" * 5000 + b"]" * 5000),
]


@pytest.mark.parametrize(
    "raw", [raw for _, raw in _MALFORMED], ids=[name for name, _ in _MALFORMED]
)
def test_malformed_answers_are_refused(raw: bytes) -> None:
    assert decide_answer(raw) is None


def test_non_bytes_answer_is_refused() -> None:
    for value in ('[[2,"10.0.0.1",0]]', None, 7, bytearray(b'[[2,"10.0.0.1",0]]')):
        assert decide_answer(value) is None


def test_deep_nesting_within_the_byte_bound_does_not_escape_as_recursion_error() -> None:
    raw = b"[" * 8000 + b"]" * 8000
    assert len(raw) <= bind_module.MAX_ANSWER_BYTES
    assert decide_answer(raw) is None


def test_exact_int_helper_rejects_bool_and_float() -> None:
    assert bind_module._is_exact_int(0)
    assert bind_module._is_exact_int(INET)
    for value in (True, False, 0.0, 2.0, "0", None):
        assert not bind_module._is_exact_int(value)


@pytest.mark.parametrize(("count", "accepted"), [(64, True), (65, False)])
def test_raw_entry_bound_applies_before_dedup(count: int, accepted: bool) -> None:
    raw = _raw(*[[INET, "10.0.0.1", 0]] * count)
    assert (decide_answer(raw) == "10.0.0.1") is accepted


def test_byte_bound_is_exact() -> None:
    body = _raw([INET, "10.0.0.1", 0])
    padded = body + b" " * (bind_module.MAX_ANSWER_BYTES - len(body))
    assert len(padded) == bind_module.MAX_ANSWER_BYTES
    assert decide_answer(padded) == "10.0.0.1"
    assert decide_answer(padded + b" ") is None


# ---- politica por endereco ---------------------------------------------------

_REFUSED_ADDRESSES = [
    (INET, "0.0.0.0"),  # noqa: S104 - recusado
    (INET6, "::"),
    (INET, "255.255.255.255"),
    (INET, "224.0.0.1"),
    (INET, "239.255.255.255"),
    (INET6, "ff02::1"),
    (INET6, "ff0e::1"),
    (INET6, "::ffff:127.0.0.1"),
    (INET6, "::ffff:10.0.0.1"),
    (INET6, "::7f00:1"),  # IPv4-compatible de 127.0.0.1
    (INET6, "::a00:1"),
    (INET6, "::2"),
    (INET, "169.254.1.1"),
    (INET6, "fe80::1"),
    (INET6, "febf::1"),
]
_ACCEPTED_ADDRESSES = [
    (INET6, "::1"),  # `is_reserved` verdadeiro no stdlib: a ordem aceita antes
    (INET, "127.0.0.1"),
    (INET, "127.255.255.254"),
    (INET, "10.0.0.1"),
    (INET, "192.168.1.1"),
    (INET, "100.64.0.1"),
    (INET, "8.8.8.8"),
    (INET, "240.0.0.1"),  # sem classificador de "reservado"
    (INET, "0.1.2.3"),  # so `0.0.0.0` e wildcard
    (INET6, "2001:db8::1"),
    (INET6, "fc00::1"),
    (INET6, "fec0::1"),
]


@pytest.mark.parametrize(("family", "text"), _REFUSED_ADDRESSES)
def test_forbidden_addresses_are_refused(family: int, text: str) -> None:
    assert decide_answer(_raw([family, text, 0])) is None


@pytest.mark.parametrize(("family", "text"), _ACCEPTED_ADDRESSES)
def test_acceptable_addresses_pass(family: int, text: str) -> None:
    assert decide_answer(_raw([family, text, 0])) == str(ipaddress.ip_address(text))


def test_ipv6_loopback_is_accepted_although_stdlib_marks_it_reserved() -> None:
    assert ipaddress.IPv6Address("::1").is_reserved  # o motivo da regra explicita
    assert decide_answer(_raw([INET6, "::1", 0])) == "::1"


@pytest.mark.parametrize(("family", "text"), _REFUSED_ADDRESSES[:6])
@pytest.mark.parametrize("position", ["primeira", "ultima"])
def test_one_forbidden_entry_anywhere_refuses_the_whole_answer(
    family: int, text: str, position: str
) -> None:
    good = [INET, "10.0.0.1", 0]
    bad = [family, text, 0]
    entries = [bad, good, good] if position == "primeira" else [good, good, bad]
    assert decide_answer(_raw(*entries)) is None


@pytest.mark.parametrize("bad", [[True, "10.0.0.1", 0], [INET, "10.0.0.1", 1], [INET, None, 0]])
def test_one_malformed_entry_anywhere_refuses_the_whole_answer(bad: list[object]) -> None:
    good = [INET, "10.0.0.1", 0]
    assert decide_answer(_raw(good, bad)) is None
    assert decide_answer(_raw(bad, good)) is None


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([[INET, "10.0.0.1", 0], [INET, "10.0.0.1", 0]], "10.0.0.1"),
        ([[INET6, "2001:db8::1", 0], [INET6, "2001:DB8:0:0::1", 0]], "2001:db8::1"),
        ([[INET6, "::1", 0], [INET6, "0:0:0:0:0:0:0:1", 0]], "::1"),
    ],
)
def test_canonical_duplicates_collapse_to_one(entries: list[object], expected: str) -> None:
    assert decide_answer(_raw(*entries)) == expected


@pytest.mark.parametrize(
    "entries",
    [
        [[INET, "10.0.0.1", 0], [INET, "10.0.0.2", 0]],
        [[INET, "127.0.0.1", 0], [INET6, "::1", 0]],  # localhost dual stack
        [[INET, "10.0.0.1", 0], [INET6, "2001:db8::1", 0]],
        [[INET6, "::1", 0], [INET, "127.0.0.1", 0]],  # ordem nao muda nada
    ],
)
def test_two_or_more_distinct_addresses_are_refused(entries: list[object]) -> None:
    assert decide_answer(_raw(*entries)) is None


# ---- resolve_bind_address: uma chamada, erro fixo --------------------------


def test_resolution_calls_the_supervised_job_once(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _spy(monkeypatch, _raw([INET, "127.0.0.1", 0]))
    assert resolve_bind_address(HOST) == "127.0.0.1"
    assert spy.calls == [(HOST, {})], "o prazo default do job comeca la, antes da admissao"


@pytest.mark.parametrize("failure", list(BindDnsFailure))
def test_job_failures_become_the_fixed_config_error(
    monkeypatch: pytest.MonkeyPatch, failure: BindDnsFailure
) -> None:
    _refused(monkeypatch, BindDnsError(failure))


@pytest.mark.parametrize("answer", [b"[]", _raw([INET, "10.0.0.1", 0], [INET, "10.0.0.2", 0])])
def test_refused_answers_become_the_fixed_config_error(
    monkeypatch: pytest.MonkeyPatch, answer: bytes
) -> None:
    _refused(monkeypatch, answer)


def test_error_never_cites_host_or_address(monkeypatch: pytest.MonkeyPatch) -> None:
    _spy(monkeypatch, _raw([INET, "10.9.8.7", 0], [INET, "10.9.8.6", 0]))
    with pytest.raises(ConfigError) as caught:
        resolve_bind_address("segredo-host.test")
    text = f"{caught.value!s}{caught.value!r}"
    assert "segredo-host.test" not in text
    assert "10.9.8" not in text


def test_unexpected_exception_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    # So `BindDnsError` vira `ConfigError`; outra excecao propaga intacta.
    _spy(monkeypatch, KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        resolve_bind_address(HOST)


def test_real_child_with_controlled_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = "[(socket.AF_INET, 1, 6, '', ('127.0.0.1', 0))] * 3"
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_child(entries))
    assert resolve_bind_address(HOST) == "127.0.0.1"
    scoped = "[(socket.AF_INET6, 1, 6, '', ('fe80::1', 0, 0, 7))]"
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_child(scoped))
    with pytest.raises(ConfigError):
        resolve_bind_address(HOST)
    dual = (
        "[(socket.AF_INET6, 1, 6, '', ('::1', 0, 0, 0)),"
        " (socket.AF_INET, 1, 6, '', ('127.0.0.1', 0))]"
    )
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_child(dual))
    with pytest.raises(ConfigError):
        resolve_bind_address(HOST)


# ---- composicao: ordem, colaborador explicito e literal --------------------


def test_hostname_without_collaborator_resolves_once_after_tls_and_principal(
    monkeypatch: pytest.MonkeyPatch, credential: tuple[Any, str], tls_files: tuple[str, str]
) -> None:
    _, password = credential
    events: list[str] = []
    for name, label in (("prepare_server_tls", "tls"), ("prepare_principal", "principal")):
        original = getattr(composition_module, name)

        def recording(*a: Any, _o: Any = original, _l: str = label, **k: Any) -> Any:
            events.append(_l)
            return _o(*a, **k)

        monkeypatch.setattr(composition_module, name, recording)
    spy = _spy(monkeypatch, _raw([INET, "127.0.0.1", 0]))
    original_resolve = bind_module.resolve_bind_address

    def recording_resolve(host: str) -> str:
        events.append("dns")
        return original_resolve(host)

    monkeypatch.setattr(composition_module, "resolve_bind_address", recording_resolve)
    prepared = prepare_pgwire(PgwireComposition(_hostname_settings(password, tls_files)))
    assert events == ["tls", "principal", "dns"]
    assert spy.calls == [(HOST, {})]
    assert prepared.resolved_addresses == ("127.0.0.1",)
    # Hostname continua externo para TLS mesmo resolvendo para loopback.
    assert prepared.settings.bind_is_hostname
    assert prepared.settings.tls_required
    assert prepared.tls is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"port": 0},
        {"max_sessions": 0},
        {"tls_cert": None, "tls_key": None},  # hostname exige TLS
        {"tls_cert": "nao-existe.crt"},
        {"password": ""},
    ],
)
def test_invalid_settings_or_tls_fail_before_any_resolution(
    monkeypatch: pytest.MonkeyPatch,
    credential: tuple[Any, str],
    tls_files: tuple[str, str],
    changes: dict[str, Any],
) -> None:
    _, password = credential
    spy = _spy(monkeypatch, _raw([INET, "127.0.0.1", 0]))
    with pytest.raises(ConfigError):
        prepare_pgwire(PgwireComposition(_hostname_settings(password, tls_files, **changes)))
    assert spy.calls == []


def test_invalid_collaborator_shape_fails_before_tls_and_resolution(
    monkeypatch: pytest.MonkeyPatch, credential: tuple[Any, str], tls_files: tuple[str, str]
) -> None:
    _, password = credential
    spy = _spy(monkeypatch, _raw([INET, "127.0.0.1", 0]))
    tls_calls: list[str] = []
    monkeypatch.setattr(
        composition_module, "prepare_server_tls", lambda *_a, **_k: tls_calls.append("tls")
    )
    settings = _hostname_settings(password, tls_files)
    for resolved in ((), ("127.0.0.1", "127.0.0.2"), ("gateway.test",), ["127.0.0.1"]):
        with pytest.raises(ConfigError):
            prepare_pgwire(PgwireComposition(settings, resolved_addresses=resolved))  # type: ignore[arg-type]
    assert tls_calls == []
    assert spy.calls == []


def test_resolution_failure_leaves_no_prepared_object(
    monkeypatch: pytest.MonkeyPatch, credential: tuple[Any, str], tls_files: tuple[str, str]
) -> None:
    _, password = credential
    built: list[object] = []
    original = composition_module.PreparedPgwire

    def recording(*a: Any, **k: Any) -> Any:
        value = original(*a, **k)
        built.append(value)
        return value

    monkeypatch.setattr(composition_module, "PreparedPgwire", recording)
    _spy(monkeypatch, BindDnsError(BindDnsFailure.FAILED))
    with pytest.raises(ConfigError) as caught:
        prepare_pgwire(PgwireComposition(_hostname_settings(password, tls_files)))
    assert built == [], "nenhum PreparedPgwire sem o literal final"
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "injected",
    [("127.0.0.1",), ("0.0.0.0",), ("fe80::1%1",), ("::ffff:127.0.0.1",)],  # noqa: S104
)
def test_explicit_collaborator_semantics_are_unchanged_and_never_resolve(
    monkeypatch: pytest.MonkeyPatch,
    credential: tuple[Any, str],
    tls_files: tuple[str, str],
    injected: tuple[str, ...],
) -> None:
    # Colaborador interno confiavel: a politica de DNS NAO se aplica a ele.
    _, password = credential
    spy = _spy(monkeypatch, _raw([INET, "10.0.0.1", 0]))
    prepared = prepare_pgwire(
        PgwireComposition(_hostname_settings(password, tls_files), resolved_addresses=injected)
    )
    assert prepared.resolved_addresses == injected
    assert spy.calls == []


@pytest.mark.parametrize("bind", ["127.0.0.1", "::1"])
def test_literal_bind_never_resolves(
    monkeypatch: pytest.MonkeyPatch, credential: tuple[Any, str], bind: str
) -> None:
    _, password = credential
    spy = _spy(monkeypatch, _raw([INET, "10.0.0.1", 0]))
    prepared = prepare_pgwire(PgwireComposition(make_settings(password, bind=bind), test_port=0))
    assert prepared.resolved_addresses is None
    assert prepared.settings.bind == bind
    assert spy.calls == []


# ---- literal selado; nenhum DNS depois ---------------------------------------


def test_sealed_literal_binds_and_clients_authenticate_without_any_dns(
    monkeypatch: pytest.MonkeyPatch, credential: tuple[Any, str], tls_files: tuple[str, str]
) -> None:
    _, password = credential
    entries = "[(socket.AF_INET, 1, 6, '', ('127.0.0.1', 0))]"
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", _fake_child(entries))
    prepared = prepare_pgwire(
        PgwireComposition(_hostname_settings(password, tls_files), test_port=0)
    )
    assert prepared.resolved_addresses == ("127.0.0.1",)
    # Daqui em diante, qualquer DNS no processo falha o teste: so numerico.
    flags: list[int] = []
    original = socket.getaddrinfo

    def numeric_only(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        flag = kwargs.get("flags", 0)
        flags.append(flag)
        if not flag & socket.AI_NUMERICHOST:
            pytest.fail("DNS depois da composicao")
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", numeric_only)
    monkeypatch.setattr(socket, "gethostbyname", lambda *_a: pytest.fail("DNS"))
    child_calls: list[str] = []
    monkeypatch.setattr(
        verify_module, "resolve_bind_host_in_child", lambda *_a, **_k: child_calls.append("x")
    )
    listener = build_listener(prepared, alias_accepted=lambda alias: alias == "crm")
    try:
        listener.start()
        for _ in range(2):
            started = time.monotonic()
            with psycopg.connect(
                host="127.0.0.1",
                port=listener.port,
                user=USER,
                dbname="crm",
                password=password,
                sslmode="require",
                channel_binding="require",
                gssencmode="disable",
                connect_timeout=5,
            ):
                pass  # sem SQL; o fechamento envia Terminate
            assert time.monotonic() - started < 10
    finally:
        listener.stop()
    assert listener.status().state is ListenerState.STOPPED
    assert flags and all(flag & socket.AI_NUMERICHOST for flag in flags)
    assert child_calls == [], "nenhuma resolucao nova no startup dos clientes"
