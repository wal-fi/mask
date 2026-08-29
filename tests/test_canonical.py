"""Canonicalizacao deterministica de valores (Fase 2, D-015).

Um transformer opera sobre texto, mas o banco devolve objetos Python. A
conversao precisa ser explicita e deterministica: `str()` produziria
`<memory at 0x...>` para `memoryview` — endereco que muda a cada execucao —
e repr de Python para `dict`.

Tipo fora da tabela FALHA FECHADA, nunca cai em `str()`.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
from decimal import Decimal
from uuid import UUID

import pytest

from maskgw.errors import TransformerError
from maskgw.masking.canonical import canonicalize

UID = UUID("2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42")


class TestScalars:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("texto", "texto"),
            ("", ""),
            ("acentuacao: cao, coracao", "acentuacao: cao, coracao"),
            (0, "0"),
            (42, "42"),
            (-7, "-7"),
            (10**30, "1" + "0" * 30),
            (1.5, "1.5"),
            (0.1, "0.1"),
            (-0.0, "-0.0"),
            (Decimal("1234.50"), "1234.50"),
            (Decimal("0"), "0"),
            (dt.date(2026, 8, 29), "2026-08-29"),
            (dt.time(13, 45, 7), "13:45:07"),
            (UID, "2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42"),
        ],
    )
    def test_canonical_form(self, value, expected):
        assert canonicalize(value) == expected

    def test_datetime_is_iso8601(self):
        moment = dt.datetime(2026, 8, 29, 13, 45, 7, tzinfo=dt.UTC)
        assert canonicalize(moment) == "2026-08-29T13:45:07+00:00"

    def test_naive_datetime(self):
        assert canonicalize(dt.datetime(2026, 8, 29, 13, 45, 7)) == "2026-08-29T13:45:07"


class TestSubclassOrdering:
    """`bool` e subclasse de `int`; `datetime` e subclasse de `date`.

    Inverter a ordem dos testes de tipo produziria saida silenciosamente
    errada — `True` viraria `"1"` e um `datetime` perderia a hora.
    """

    def test_bool_is_not_rendered_as_int(self):
        assert canonicalize(True) == "true"
        assert canonicalize(False) == "false"

    def test_int_still_works(self):
        assert canonicalize(1) == "1"
        assert canonicalize(0) == "0"

    def test_bool_and_int_do_not_collide(self):
        assert canonicalize(True) != canonicalize(1)
        assert canonicalize(False) != canonicalize(0)

    def test_datetime_keeps_the_time(self):
        moment = dt.datetime(2026, 8, 29, 13, 45, 7)
        assert canonicalize(moment) != canonicalize(dt.date(2026, 8, 29))
        assert "13:45:07" in canonicalize(moment)


class TestBinary:
    """`str()` sobre binario embutiria o endereco do objeto."""

    def test_bytes_are_base64(self):
        assert canonicalize(b"ab") == "YWI="

    def test_bytearray_matches_bytes(self):
        assert canonicalize(bytearray(b"ab")) == canonicalize(b"ab")

    def test_memoryview_matches_bytes(self):
        assert canonicalize(memoryview(b"ab")) == canonicalize(b"ab")

    def test_memoryview_is_deterministic(self):
        first = canonicalize(memoryview(b"conteudo binario"))
        second = canonicalize(memoryview(b"conteudo binario"))
        assert first == second

    def test_memoryview_has_no_python_repr(self):
        result = canonicalize(memoryview(b"x"))
        assert "memory at" not in result
        assert "0x" not in result

    def test_empty_bytes(self):
        assert canonicalize(b"") == ""


class TestJson:
    def test_keys_are_sorted(self):
        assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_insertion_order_does_not_matter(self):
        assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})

    def test_separators_have_no_spaces(self):
        assert canonicalize({"a": [1, 2]}) == '{"a":[1,2]}'

    def test_nested_keys_are_sorted(self):
        assert canonicalize({"z": {"b": 1, "a": 2}}) == '{"z":{"a":2,"b":1}}'

    def test_unicode_is_preserved_not_escaped(self):
        assert canonicalize({"nome": "coracao"}) == '{"nome":"coracao"}'
        assert canonicalize({"n": "ção"}) == '{"n":"ção"}'

    def test_no_python_repr(self):
        result = canonicalize({"a": True, "b": None})
        assert "'" not in result
        assert "True" not in result
        assert "None" not in result
        assert result == '{"a":true,"b":null}'

    def test_list_at_top_level(self):
        assert canonicalize([3, 1, 2]) == "[3,1,2]"

    def test_empty_structures(self):
        assert canonicalize({}) == "{}"
        assert canonicalize([]) == "[]"

    def test_scalars_inside_json_use_the_same_table(self):
        value = {"quando": dt.date(2026, 8, 29), "quanto": Decimal("1.50")}
        assert canonicalize(value) == '{"quando":"2026-08-29","quanto":"1.50"}'

    def test_binary_inside_json(self):
        assert canonicalize([b"ab"]) == '["YWI="]'


class TestFailClosed:
    """Tipo sem forma canonica definida falha fechado, sem cair em `str()`."""

    @pytest.mark.parametrize(
        "value",
        [
            dt.timedelta(days=1),
            (1, 2),
            {1, 2},
            object(),
            ipaddress.IPv4Address("10.0.0.1"),
            range(3),
        ],
    )
    def test_unsupported_type_raises(self, value):
        with pytest.raises(TransformerError, match="tipo nao suportado"):
            canonicalize(value)

    def test_error_names_the_type_not_the_value(self):
        with pytest.raises(TransformerError) as info:
            canonicalize(dt.timedelta(days=1))
        message = str(info.value)
        assert "timedelta" in message
        assert "1 day" not in message

    def test_unsupported_nested_in_json_fails_closed(self):
        with pytest.raises(TransformerError, match="tipo nao suportado"):
            canonicalize({"intervalo": dt.timedelta(days=1)})

    def test_nan_inside_json_fails_closed(self):
        with pytest.raises(TransformerError, match="nao canonicalizavel"):
            canonicalize([float("nan")])

    def test_json_error_does_not_echo_the_value(self):
        with pytest.raises(TransformerError) as info:
            canonicalize({("chave", "tupla"): 1})
        assert "tupla" not in str(info.value)


class TestDeterminism:
    """A promessa de determinismo dos hashes depende inteiramente disto."""

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: memoryview(b"binario"),
            lambda: {"b": 1, "a": [2, {"d": 4, "c": 3}]},
            lambda: Decimal("1234.50"),
            lambda: dt.datetime(2026, 8, 29, 13, 45, 7, tzinfo=dt.UTC),
            lambda: UUID("2f6b0e5c-2b4a-4c1e-9a3d-6f1c0b8e7d42"),
        ],
    )
    def test_repeated_canonicalization_is_stable(self, factory):
        assert len({canonicalize(factory()) for _ in range(20)}) == 1
