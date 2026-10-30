"""B-1: real compiler/engine equivalence, no worker, socket or SQL ingress.

All credentials and rows are synthetic. No real environment secret is read.
"""

from __future__ import annotations

import dataclasses
import json
import secrets as entropy
import string
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from maskgw.datasource.models import DatasourceLimits, DatasourcePolicy
from maskgw.masking.descriptor import ColumnDescriptor
from maskgw.masking.engine import Action
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import (
    CandidateFailure,
    CandidateSpec,
    DatasourceCandidateError,
    PreparedRuntime,
    build_candidate,
)
from maskgw.runtime.snapshot import (
    MAX_SNAPSHOT_BYTES,
    RecompiledSnapshot,
    RecordingSecrets,
    SnapshotError,
    SnapshotFailure,
    SnapshotIdentity,
    SnapshotTemplate,
    recompile_snapshot,
)
from maskgw.secretsource import EnvSecretProvider, MappingSecretProvider, SecretProvider
from maskgw.sql.sensitivity import analyze_sensitivity
from maskgw.sql.validator import validate_select
from tests.datasource_runtime_support import DS_A, DS_B, FakeFactory, draft, resolver

IDENTITY = SnapshotIdentity(DS_A, 1, 1)
KEY_A = "synthetic-hmac-key-A-000000000000000000000"
KEY_B = "synthetic-hmac-key-B-111111111111111111111"
UPSTREAM = "synthetic-snapshot-upstream-canary"
MASTER = "synthetic-master-must-not-be-captured"


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def prepare(
    raw: Mapping[str, object] | None = None,
    *,
    provider: SecretProvider | None = None,
    capture: bool = True,
    limits: DatasourceLimits | None = None,
) -> PreparedRuntime:
    original = draft()
    spec = CandidateSpec.from_draft(original, UPSTREAM)
    spec = dataclasses.replace(
        spec,
        policy=DatasourcePolicy.from_mapping(raw or {}),
        limits=limits or DatasourceLimits(),
    )
    return build_candidate(
        spec,
        secrets=provider
        or MappingSecretProvider({HMAC_KEY_ENV: KEY_A, "MASKGW_DATASOURCE_MASTER_KEY": MASTER}),
        resolver=resolver,
        adapter_factory=FakeFactory(),
        verifier=lambda _prepared: None,
        capture_snapshot=capture,
    )


def encoded(prepared: PreparedRuntime, identity: SnapshotIdentity = IDENTITY) -> bytes:
    template = prepared.snapshot_template
    assert template is not None
    return template.bind(identity)


def rebuild(prepared: PreparedRuntime, identity: SnapshotIdentity = IDENTITY) -> RecompiledSnapshot:
    return recompile_snapshot(encoded(prepared, identity), expected=identity)


def assert_closed(error: pytest.ExceptionInfo[SnapshotError]) -> None:
    assert str(error.value) == "snapshot de compilacao recusado"
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert error.value.args == ("snapshot de compilacao recusado",)
    for canary in (KEY_A, KEY_B, UPSTREAM, MASTER):
        assert canary not in repr(error.value)


TRANSFORMERS = [
    ("md5", {}),
    ("sha256", {}),
    ("sha512", {}),
    ("hmac_sha256", {}),
    ("fixed", {"value": 'substituto-\u00e7-\\"'}),
    ("truncate", {"length": 4}),
    ("truncate", {"length": 0}),
    ("regex", {"pattern": r"^(.*)$", "replacement": r"mask:\1"}),
    ("regex", {"pattern": r"^[0-9]+$", "replacement": "digits"}),
]
VALUES = [
    None,
    "",
    "123456789",
    "nao-casa",
    "\u00e7\u00e3\u6f22\U0001f600",
    123,
    -17,
    True,
    Decimal("12.300"),
    b"binary",
    bytearray(b"abc"),
    datetime(2020, 1, 2, 3, 4, tzinfo=UTC),
    UUID(int=123),
    [1, "a"],
    {"b": 2, "a": 1},
]


@pytest.mark.parametrize(("transformer", "config"), TRANSFORMERS)
@pytest.mark.parametrize("value", VALUES)
def test_deterministic_transformers_preserve_decision_and_value(transformer, config, value):
    raw = {"masking": [{"match": "cpf", "transformer": transformer, "config": config}]}
    original = prepare(raw)
    copied = rebuild(original)
    column = ColumnDescriptor(output_name="documento", origin_name="CPF")
    assert copied.engine.decide(column) == original.engine.decide(column)
    first = original.engine.mask_value(column, value)
    second = copied.engine.mask_value(column, value)
    assert type(first) is type(second)
    assert first == second
    if isinstance(first, str):
        assert first.encode("utf-8") == second.encode("utf-8")


@pytest.mark.parametrize(
    ("column", "action"),
    [
        (ColumnDescriptor("documento", origin_name="CPF"), Action.MASK),
        (ColumnDescriptor("tipo_cpf", origin_name="cpf"), Action.MASK),
        (ColumnDescriptor("documento", origin_name="tipo_cpf"), Action.EXCEPTION),
        (ColumnDescriptor("tipo_cpf"), Action.EXCEPTION),
        (ColumnDescriptor("cpf_outra", origin_name="irrelevante"), Action.MASK),
        (ColumnDescriptor("sem_match"), Action.ALLOW),
        (ColumnDescriptor("tipo_cpf", derived_rule_index=0), Action.MASK),
    ],
)
def test_authoritative_exceptions_aliases_derived_and_allow_survive(column, action):
    original = prepare(
        {
            "masking": [{"match": "cpf", "transformer": "fixed", "config": {"value": "masked"}}],
            "exceptions": [{"match": "tipo_cpf"}],
        }
    )
    copied = rebuild(original)
    assert copied.engine.decide(column) == original.engine.decide(column)
    assert copied.engine.decide(column).action is action
    assert copied.engine.mask_value(column, "synthetic") == original.engine.mask_value(
        column, "synthetic"
    )
    assert copied.engine.mask_value(column, None) is None


def test_rule_order_matching_modes_case_and_row_arity_are_preserved():
    raw = {
        "masking": [
            {
                "match": "CPF",
                "mode": "exact",
                "case_sensitive": True,
                "transformer": "fixed",
                "config": {"value": "first"},
            },
            {"match": "cpf", "transformer": "fixed", "config": {"value": "second"}},
        ]
    }
    original = prepare(raw)
    copied = rebuild(original)
    columns = [ColumnDescriptor(name) for name in ("CPF", "cpf", "num_cpf", "plain", "CPF")]
    row = ("one", "two", "three", "four", None)
    assert copied.engine.mask_row(columns, row) == ["first", "second", "second", "four", None]
    assert copied.engine.mask_rows(columns, [row, row]) == original.engine.mask_rows(
        columns, [row, row]
    )
    for engine in (original.engine, copied.engine):
        with pytest.raises(ValueError):
            engine.mask_row(columns, ("wrong-arity",))


@pytest.mark.parametrize(
    ("strategy", "preserve", "length"),
    [
        ("digits", True, None),
        ("alphanumeric", True, None),
        ("digits", False, 0),
        ("digits", False, 13),
        ("alphanumeric", False, 9),
    ],
)
def test_random_effective_parameters_and_invariants(strategy, preserve, length, monkeypatch):
    config = {"strategy": strategy, "preserve_length": preserve}
    if length is not None:
        config["length"] = length
    original = prepare({"masking": [{"match": "cpf", "transformer": "random", "config": config}]})
    copied = rebuild(original)
    assert repr(original.engine.policy.rules[0].transformer) == repr(
        copied.engine.policy.rules[0].transformer
    )
    column = ColumnDescriptor("cpf")
    alphabet = string.digits if strategy == "digits" else string.ascii_letters + string.digits
    real_choice = entropy.choice
    # Test-scoped patch only, explicitly restored. No seed or hook in product.
    with monkeypatch.context() as patch:
        patch.setattr(entropy, "choice", lambda available: available[0])
        for value in ("", "a", "longer-input", 1234):
            assert original.engine.mask_value(column, value) == copied.engine.mask_value(
                column, value
            )
    assert entropy.choice is real_choice
    for value in ("", "a", "longer-input"):
        for engine in (original.engine, copied.engine):
            for _ in range(12):
                output = engine.mask_value(column, value)
                assert len(output) == (len(value) if preserve else length)
                assert set(output) <= set(alphabet)
            assert engine.mask_value(column, None) is None


def test_effective_database_settings_sql_and_pinned_target_are_preserved(monkeypatch):
    raw = {
        "database": {"max_rows": 900, "statement_timeout_ms": 1500},
        "sql": {"allowed_pg_functions": ["pg_custom_safe"], "denied_functions": ["lower"]},
    }
    original = prepare(raw, limits=DatasourceLimits(max_rows=7, statement_timeout_ms=3000))
    monkeypatch.setattr(EnvSecretProvider, "get", lambda *_: pytest.fail("environment reread"))
    copied = rebuild(original)
    assert copied.config.database == original.config.database
    assert copied.config.database.max_rows == 7
    assert copied.config.database.statement_timeout_ms == 1500
    assert copied.config.sql == original.config.sql
    assert copied.connection_target() == original.verify_target()[0]
    assert "hostaddr=10.0.0.7" in copied.connection_target()
    assert MASTER.encode() not in encoded(original)


def test_capture_is_explicit_and_does_not_limit_existing_candidate_path():
    raw = {
        "masking": [
            {"match": "cpf", "transformer": "fixed", "config": {"value": "x" * MAX_SNAPSHOT_BYTES}}
        ]
    }
    assert prepare(raw, capture=False).snapshot_template is None
    with pytest.raises(DatasourceCandidateError) as error:
        prepare(raw, capture=True)
    assert error.value.category is CandidateFailure.POLICY
    assert error.value.__context__ is None


def test_hmac_capture_reads_once_and_old_generation_survives_rotation(monkeypatch):
    class RotatingProvider:
        calls = 0

        def get(self, name):
            assert name == HMAC_KEY_ENV
            self.calls += 1
            return KEY_A if self.calls == 1 else KEY_B

    provider = RotatingProvider()
    raw = {
        "masking": [
            {"match": "cpf", "transformer": "hmac_sha256"},
            {"match": "email", "transformer": "hmac_sha256"},
        ]
    }
    first = prepare(raw, provider=provider)
    assert provider.calls == 1
    first_bytes = encoded(first)
    monkeypatch.setenv(HMAC_KEY_ENV, KEY_B)
    second = prepare(raw, provider=MappingSecretProvider({HMAC_KEY_ENV: KEY_B}))
    later = SnapshotIdentity(DS_A, 2, 2)
    first_copy = recompile_snapshot(first_bytes, expected=IDENTITY)
    second_copy = rebuild(second, later)
    for name in ("cpf", "email"):
        column = ColumnDescriptor(name)
        assert first.engine.mask_value(column, "same") == first_copy.engine.mask_value(
            column, "same"
        )
        assert second.engine.mask_value(column, "same") == second_copy.engine.mask_value(
            column, "same"
        )
        assert first_copy.engine.mask_value(column, "same") != second_copy.engine.mask_value(
            column, "same"
        )
    assert provider.calls == 1


def test_custom_provider_values_are_not_renormalized():
    class ExactProvider:
        def get(self, _name):
            return "  " + KEY_A + "  "

    original = prepare(
        {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}, provider=ExactProvider()
    )
    column = ColumnDescriptor("cpf")
    assert rebuild(original).engine.mask_value(column, "same") == original.engine.mask_value(
        column, "same"
    )


def test_template_is_detached_immutable_redacted_and_canonical():
    original = prepare({"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]})
    before = encoded(original)
    original.file_config.masking.clear()
    assert encoded(original) == before
    assert canonical(json.loads(before)) == before
    assert len(before) <= MAX_SNAPSHOT_BYTES
    template, copied = original.snapshot_template, rebuild(original)
    for value in (template, copied, copied.engine.policy.rules[0].transformer):
        for render in (str, repr, format):
            for canary in (KEY_A, UPSTREAM, MASTER):
                assert canary not in render(value)
        with pytest.raises(TypeError):
            json.dumps(value)
    with pytest.raises(dataclasses.FrozenInstanceError):
        attribute = dataclasses.fields(SnapshotTemplate)[0].name
        setattr(template, attribute, b"tampered")


def test_policy_roundtrip_and_mapping_key_order_have_stable_canonical_bytes():
    first = prepare(
        {
            "database": {"max_rows": 17},
            "masking": [{"match": "cpf", "transformer": "fixed", "config": {"value": "yes"}}],
        }
    )
    second = prepare(
        {
            "masking": [{"config": {"value": "yes"}, "transformer": "fixed", "match": "cpf"}],
            "database": {"max_rows": 17},
        }
    )
    assert encoded(first) == encoded(second)
    raw = json.loads(encoded(first))["runtime"]["policy"]
    assert canonical(DatasourcePolicy.from_mapping(raw).to_mapping()) == canonical(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update(extra="not-allowed"),
        lambda raw: raw.update(version=True),
        lambda raw: raw.update(version=2),
        lambda raw: raw["identity"].update(generation=True),
        lambda raw: raw["identity"].update(record_revision=1.0),
        lambda raw: raw["identity"].update(datasource_id=DS_B),
        lambda raw: raw["identity"].update(extra="not-allowed"),
        lambda raw: raw["runtime"].update(extra="not-allowed"),
        lambda raw: raw["runtime"].update(conninfo=""),
        lambda raw: raw["runtime"].update(conninfo="secret\x00input"),
        lambda raw: raw["runtime"]["database"].update(max_rows=True),
        lambda raw: raw["runtime"]["database"].update(max_rows=1001),
        lambda raw: raw["runtime"]["database"].update(statement_timeout_ms=99),
        lambda raw: raw["runtime"]["secrets"].update(MASKGW_DATASOURCE_MASTER_KEY=MASTER),
        lambda raw: raw["runtime"]["secrets"].clear(),
        lambda raw: raw["runtime"]["policy"].update(unknown=UPSTREAM),
        lambda raw: raw["runtime"]["policy"]["masking"][0].update(transformer="unknown"),
    ],
)
def test_closed_schema_and_compilation_failures_have_no_sensitive_chain(mutation):
    original = prepare({"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]})
    raw = json.loads(encoded(original))
    mutation(raw)
    with pytest.raises(SnapshotError) as error:
        recompile_snapshot(canonical(raw), expected=IDENTITY)
    assert_closed(error)


def test_unused_secret_is_rejected_and_empty_policy_never_reads_environment(monkeypatch):
    monkeypatch.setattr(EnvSecretProvider, "get", lambda *_: pytest.fail("environment read"))
    original = prepare({})
    raw = json.loads(encoded(original))
    assert raw["runtime"]["secrets"] == {}
    raw["runtime"]["secrets"][HMAC_KEY_ENV] = KEY_A
    with pytest.raises(SnapshotError) as error:
        recompile_snapshot(canonical(raw), expected=IDENTITY)
    assert error.value.category is SnapshotFailure.POLICY
    assert_closed(error)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]",
        b"null",
        b"{}",
        b"\xff",
        b"NaN",
        b"Infinity",
        b'{"x":1,"x":2}',
        b'{"x":{"y":1,"y":2}}',
        b"[" * 33 + b"]" * 33,
        b"x" * (MAX_SNAPSHOT_BYTES + 1),
    ],
    ids=[
        "empty",
        "array",
        "null",
        "empty-object",
        "bad-ascii",
        "nan",
        "infinity",
        "duplicate",
        "nested-duplicate",
        "too-deep",
        "too-large",
    ],
)
def test_invalid_bounded_wire_data_is_sanitized(payload):
    with pytest.raises(SnapshotError) as error:
        recompile_snapshot(payload, expected=IDENTITY)
    assert_closed(error)


@pytest.mark.parametrize(
    "transform",
    [
        lambda data: b" " + data,
        lambda data: data + b"\n",
        lambda data: data[:-1],
        lambda data: data.replace(b'"version":1', b'"version":1.0'),
    ],
)
def test_noncanonical_or_truncated_valid_snapshot_is_refused(transform):
    with pytest.raises(SnapshotError) as error:
        recompile_snapshot(transform(encoded(prepare())), expected=IDENTITY)
    assert_closed(error)


@pytest.mark.parametrize(
    "identity", [(DS_A, True, 1), (DS_A, 1, False), (DS_A, 0, 1), (DS_A, 1, -1), ("not-id", 1, 1)]
)
def test_identity_requires_exact_positive_integers(identity):
    with pytest.raises(SnapshotError) as error:
        SnapshotIdentity(*identity)
    assert_closed(error)


def test_recorder_and_template_failures_are_closed():
    class FailingProvider:
        def get(self, _name):
            raise RuntimeError(KEY_A)

    recorder = RecordingSecrets(FailingProvider())
    with pytest.raises(SnapshotError) as error:
        recorder.get(HMAC_KEY_ENV)
    assert_closed(error)
    with pytest.raises(SnapshotError) as error:
        recorder.get("MASKGW_DATASOURCE_MASTER_KEY")
    assert_closed(error)
    with pytest.raises(SnapshotError) as error:
        SnapshotTemplate(b"not-json")
    assert_closed(error)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT substr(cpf, 1, 3) AS tipo_cpf FROM customer",
        "SELECT min(cpf) AS documento FROM customer",
        "SELECT cpf AS documento FROM customer UNION ALL SELECT 'literal' AS documento",
        "SELECT substr(tipo_cpf, 1, 3) AS documento FROM customer",
    ],
)
def test_real_ast_sensitivity_keeps_the_same_rule_indices_and_masking(query):
    original = prepare(
        {
            "masking": [{"match": "cpf", "transformer": "fixed", "config": {"value": "masked"}}],
            "exceptions": [{"match": "tipo_cpf"}],
        }
    )
    copied = rebuild(original)
    first = analyze_sensitivity(
        validate_select(query, policy=original.config.sql), original.engine.policy
    )
    second = analyze_sensitivity(
        validate_select(query, policy=copied.config.sql), copied.engine.policy
    )
    assert first == second
    assert first is not None
    columns = [ColumnDescriptor("tipo_cpf", derived_rule_index=index) for index in first]
    values = ["synthetic" for _ in first]
    assert copied.engine.mask_row(columns, values) == original.engine.mask_row(columns, values)


def test_adopted_policy_ids_and_revision_survive_without_affecting_identity():
    raw = {
        "revision": 8,
        "masking": [{"id": "rul_" + "a" * 32, "match": "cpf", "transformer": "sha256"}],
        "exceptions": [{"id": "exc_" + "b" * 32, "match": "tipo_cpf"}],
    }
    original = prepare(raw)
    decoded = json.loads(encoded(original))
    assert decoded["runtime"]["policy"]["revision"] == 8
    assert decoded["runtime"]["policy"]["masking"][0]["id"] == "rul_" + "a" * 32
    assert rebuild(original).identity.record_revision == 1
    assert canonical(
        DatasourcePolicy.from_mapping(decoded["runtime"]["policy"]).to_mapping()
    ) == canonical(decoded["runtime"]["policy"])


def test_failing_provider_in_candidate_is_a_closed_policy_error():
    class FailingProvider:
        def get(self, _name):
            raise RuntimeError(KEY_A)

    with pytest.raises(DatasourceCandidateError) as error:
        prepare(
            {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]},
            provider=FailingProvider(),
        )
    assert error.value.category is CandidateFailure.POLICY
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert KEY_A not in repr(error.value)


@pytest.mark.parametrize("raised", [MemoryError, RecursionError])
def test_resource_exception_in_recompilation_has_a_closed_unavailable_category(monkeypatch, raised):
    data = encoded(prepare())

    def fail(_policy):
        raise raised(UPSTREAM)

    monkeypatch.setattr("maskgw.runtime.snapshot.MaskingEngine", fail)
    with pytest.raises(SnapshotError) as error:
        recompile_snapshot(data, expected=IDENTITY)
    assert error.value.category is SnapshotFailure.UNAVAILABLE
    assert_closed(error)
