"""One internal job with the real adapter/engine/codec and a fake connection."""

from __future__ import annotations

import ast
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest

import maskgw.runtime.worker_job as module
from maskgw.config.gateway import DatabaseSettings
from maskgw.db.columns import ColumnOrigin
from maskgw.db.execution_error import ExecutionFailure, TypedExecutionError, TypedExecutionTimeout
from maskgw.db.postgres import PostgresAdapter
from maskgw.db.result import DatabaseResultIntegrityError, DatabaseResultTypeError
from maskgw.errors import (
    CapabilityError,
    DatabaseError,
    InvalidQuery,
    QueryRejected,
    QueryTimeout,
    TransformerError,
)
from maskgw.masking.descriptor import ProvenanceKind
from maskgw.pgwire.result_encoder import EncodeError, EncodeFailure
from maskgw.pgwire.result_encoder import encode_result as real_encode
from maskgw.pgwire.result_frame import ResultDeadline, ResultIdentity, ResultLimits, validate_result
from maskgw.runtime.worker_job import JobFailure, JobOutcome, run_job
from tests.conftest import FakePgResult, FakeResolver
from tests.test_db_typed_result import TypedColumn, adapter

CANARY = "CANARY_JOB_SECRET_932"


class Clock:
    now = 1.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def job():
    item, cursor, connection = adapter(
        [TypedColumn("cpf", 23)],
        [(123456,)],
        'masking:\n  - match: cpf\n    transformer: fixed\n    config:\n      value: "[MASK]"\n',
    )
    connection.broken = False
    connection.info.status = psycopg.pq.ConnStatus.OK
    connection.info.transaction_status = psycopg.pq.TransactionStatus.IDLE
    clock = Clock()
    identity = ResultIdentity(
        session_id=b"s" * 16, datasource_id=b"d" * 16, generation=2, record_revision=3, job_id=1
    )
    limits = ResultLimits(max_rows=item.settings.max_rows)
    deadline = ResultDeadline(expires_at=10.0, clock=clock)
    return item, cursor, connection, identity, limits, deadline, clock


def perform(job: Any, sql: Any = "SELECT 123456 AS cpf", **changes: Any) -> Any:
    item, _, _, identity, limits, deadline, _ = job
    args = {"identity": identity, "limits": limits, "deadline": deadline}
    args.update(changes)
    return run_job(item, sql, **args)


def test_masking_pipeline_precedes_the_only_complete_frame(job):
    item, cursor, connection, identity, limits, deadline, _ = job
    outcome = perform(job)
    assert outcome.failure is None and outcome.can_continue is True
    assert type(outcome.frame) is bytes
    assert b"123456" not in outcome.frame and b"[MASK]" in outcome.frame
    wire = validate_result(outcome.frame, expected=identity, limits=limits, deadline=deadline)
    assert wire.rows == 1
    assert len(cursor.executed) == 1 and connection.commits == 0
    assert connection.rollbacks == 0 and item._connection is connection
    assert "MASK" not in repr(outcome) and "123456" not in repr(outcome)
    with pytest.raises(TypeError):
        bool(outcome)
    with pytest.raises(FrozenInstanceError):
        outcome.can_continue = False


def test_two_jobs_keep_connection_and_do_not_share_metadata(job):
    _, cursor, connection, _, _, _, _ = job
    first = perform(job)
    cursor._pending = [(789012,)]
    second = perform(
        job,
        identity=ResultIdentity(
            session_id=b"s" * 16, datasource_id=b"d" * 16, generation=2, record_revision=3, job_id=2
        ),
    )
    assert first.failure is None and second.failure is None
    assert first.frame != second.frame
    assert b"789012" not in second.frame and b"[MASK]" in second.frame
    assert len(cursor.executed) == 2 and connection.closed is False


@pytest.mark.parametrize("sql", ["", "not sql", "DELETE FROM clients", "SELECT 1; SELECT 2"])
def test_valid_envelope_rejected_query_is_healthy_candidate_without_execution(job, sql):
    outcome = perform(job, sql)
    assert outcome.failure is JobFailure.QUERY and outcome.can_continue is True
    assert outcome.frame is None and not job[1].executed


@pytest.mark.parametrize(
    "sql",
    [None, b"SELECT 1", 3, True, "\0", "SELECT '\ud800'", "a" * 65537, "é" * 32769],
    ids=["none", "bytes", "int", "bool", "nul", "surrogate", "long-ascii", "long-utf8"],
)
def test_bad_sql_envelope_never_touches_adapter(job, sql):
    outcome = perform(job, sql)
    assert outcome.failure is JobFailure.PROTOCOL and outcome.can_continue is False
    assert outcome.frame is None and not job[1].executed


@pytest.mark.parametrize("unit,count", [("a", 65536), ("é", 32768), ("😀", 16384)])
def test_sql_exact_byte_limit_reaches_validator_but_plus_one_does_not(job, unit, count):
    accepted = perform(job, unit * count)
    assert accepted.failure is JobFailure.QUERY and accepted.can_continue
    rejected = perform(job, unit * count + "a")
    assert rejected.failure is JobFailure.PROTOCOL and not rejected.can_continue
    assert not job[1].executed


@pytest.mark.parametrize("which", ["identity", "limits", "deadline"])
def test_bad_structural_inputs_never_execute(job, which):
    outcome = perform(job, **{which: None})
    assert outcome.failure is JobFailure.PROTOCOL and not outcome.can_continue
    assert not job[1].executed


def test_rows_limit_is_generation_limit_not_an_independent_truncation_setting(job):
    outcome = perform(job, limits=ResultLimits(max_rows=job[4].max_rows - 1))
    assert outcome.failure is JobFailure.PROTOCOL and not outcome.can_continue
    assert not job[1].executed


@pytest.mark.parametrize(
    "error,category,recoverable",
    [
        (InvalidQuery(CANARY), JobFailure.QUERY, True),
        (QueryRejected(CANARY), JobFailure.QUERY, True),
        (DatabaseResultTypeError(), JobFailure.TYPE, True),
        (TypedExecutionTimeout(), JobFailure.TIMEOUT, True),
        (TypedExecutionError(ExecutionFailure.QUERY), JobFailure.QUERY, True),
        (TypedExecutionError(ExecutionFailure.RESOURCE), JobFailure.RESOURCE, False),
        (TypedExecutionError(ExecutionFailure.CONNECTION), JobFailure.CONNECTION, False),
        (TypedExecutionError(ExecutionFailure.INTERNAL), JobFailure.INTERNAL, False),
        (DatabaseResultIntegrityError(), JobFailure.INTERNAL, False),
        (QueryTimeout(CANARY), JobFailure.INTERNAL, False),
        (DatabaseError(CANARY), JobFailure.INTERNAL, False),
        (MemoryError(CANARY), JobFailure.MEMORY, False),
        (RuntimeError(CANARY), JobFailure.INTERNAL, False),
        (SystemExit(CANARY), JobFailure.INTERNAL, False),
        (KeyboardInterrupt(CANARY), JobFailure.INTERNAL, False),
        (ExceptionGroup(CANARY, [MemoryError(CANARY)]), JobFailure.INTERNAL, False),
    ],
)
def test_error_intent_is_closed_and_never_retains_native_error(
    job, monkeypatch, error, category, recoverable
):
    calls = []

    def fail(_self, _sql):
        calls.append(1)
        raise error

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert outcome.failure is category and outcome.can_continue is recoverable
    assert outcome.frame is None and calls == [1]
    assert CANARY not in str(outcome) and CANARY not in repr(outcome)
    assert not hasattr(outcome, "error") and job[2].closed is False


@pytest.mark.parametrize("kind", list(EncodeFailure))
def test_encoder_error_does_not_publish_even_complete_intermediate_result(job, monkeypatch, kind):
    def fail(*_args, **_kwargs):
        raise EncodeError(kind)

    monkeypatch.setattr(module, "encode_result", fail)
    outcome = perform(job)
    assert outcome.frame is None
    assert outcome.failure is JobFailure[kind.name]
    assert outcome.can_continue is (kind in (EncodeFailure.TYPE, EncodeFailure.LIMIT))
    assert len(job[1].executed) == 1


@pytest.mark.parametrize(
    "state,category,recoverable",
    [
        ("22012", JobFailure.QUERY, True),
        ("57014", JobFailure.TIMEOUT, True),
        ("53200", JobFailure.RESOURCE, False),
        (None, JobFailure.CONNECTION, False),
        ("25P02", JobFailure.INTERNAL, False),
    ],
)
def test_real_adapter_sanitizes_driver_and_settles_before_continuity(
    job, state, category, recoverable
):
    error = psycopg.Error(CANARY)
    error.sqlstate = state
    job[1]._error = error
    job[2].info.transaction_status = psycopg.pq.TransactionStatus.INTRANS
    # The initial health is positive; cursor begins its transaction on execution.
    job[2].info.transaction_status = psycopg.pq.TransactionStatus.IDLE
    original = job[1].execute

    def execute(*args, **kwargs):
        job[2].info.transaction_status = psycopg.pq.TransactionStatus.INTRANS
        original(*args, **kwargs)

    job[1].execute = execute
    outcome = perform(job)
    assert outcome.failure is category and outcome.can_continue is recoverable
    assert outcome.frame is None and job[2].rollbacks == 1
    assert CANARY not in repr(outcome) and len(job[1].executed) == 1


@pytest.mark.parametrize("phase", ["before", "execute", "encode"])
def test_health_loss_at_any_phase_prevents_success_or_continuation(job, monkeypatch, phase):
    if phase == "before":
        job[2].broken = True
    elif phase == "execute":
        original_execute = PostgresAdapter._execute_typed_validated

        def execute(self, sql):
            value = original_execute(self, sql)
            job[2].broken = True
            return value

        monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", execute)
    else:
        original_encode = real_encode

        def encode(*args, **kwargs):
            value = original_encode(*args, **kwargs)
            job[2].broken = True
            return value

        monkeypatch.setattr(module, "encode_result", encode)
    outcome = perform(job)
    assert outcome.failure is JobFailure.CONNECTION and not outcome.can_continue
    assert outcome.frame is None
    assert len(job[1].executed) == (0 if phase == "before" else 1)


def test_recoverable_error_cannot_continue_after_health_loss(job, monkeypatch):
    def execute(_self, _sql):
        job[2].broken = True
        raise TypedExecutionTimeout()

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", execute)
    outcome = perform(job)
    assert outcome.failure is JobFailure.CONNECTION and not outcome.can_continue
    assert outcome.frame is None


@pytest.mark.parametrize("phase", ["before", "execute", "encode", "health"])
def test_single_absolute_deadline_is_not_renewed_by_progress(job, monkeypatch, phase):
    if phase == "before":
        job[6].now = 10.0
    elif phase == "execute":
        original_execute = PostgresAdapter._execute_typed_validated

        def execute(self, sql):
            value = original_execute(self, sql)
            job[6].now = 10.0
            return value

        monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", execute)
    elif phase == "encode":
        original_encode = real_encode

        def encode(*args, **kwargs):
            value = original_encode(*args, **kwargs)
            job[6].now = 10.0
            return value

        monkeypatch.setattr(module, "encode_result", encode)
    else:
        original_health = PostgresAdapter._typed_connection_healthy
        calls = []

        def health(self):
            calls.append(1)
            if len(calls) > 1:
                job[6].now = 10.0
            return original_health(self)

        monkeypatch.setattr(PostgresAdapter, "_typed_connection_healthy", health)
    outcome = perform(job)
    assert outcome.failure is JobFailure.DEADLINE and not outcome.can_continue
    assert outcome.frame is None


def test_truncated_frame_uses_the_same_row_limit_as_the_adapter(job):
    job[0]._settings = DatabaseSettings(statement_timeout_ms=1000, max_rows=1)
    job[1]._pending = [(123456,), (789012,)]
    limits = ResultLimits(max_rows=1)
    outcome = perform(job, limits=limits)
    assert outcome.failure is None
    parsed = validate_result(outcome.frame, expected=job[3], limits=limits, deadline=job[5])
    assert parsed.rows == 1 and parsed.truncated is True
    assert b"789012" not in outcome.frame


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frame": b"", "failure": None, "can_continue": True},
        {"frame": bytearray(100), "failure": None, "can_continue": True},
        {"frame": b"a" * 100, "failure": JobFailure.QUERY, "can_continue": True},
        {"frame": None, "failure": JobFailure.MEMORY, "can_continue": True},
        {"frame": None, "failure": "QUERY", "can_continue": True},
        {"frame": None, "failure": JobFailure.QUERY, "can_continue": 1},
        {"frame": None, "failure": None, "can_continue": False},
    ],
)
def test_outcome_cannot_claim_incoherent_success_or_continuation(kwargs):
    with pytest.raises(ValueError, match="resultado de job invalido"):
        JobOutcome(**kwargs)


def operational_importers(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(base + "." + alias.name for alias in node.names)
    return {s for s in names if s.endswith("worker_job") or s == "run_job"}


def test_worker_job_has_no_operational_importer():
    root = Path(__file__).parents[1] / "src/maskgw"
    for path in root.rglob("*.py"):
        if path in (root / "runtime/worker_job.py", root / "runtime/worker_process.py"):
            continue
        assert not operational_importers(path.read_text("utf8")), path


def test_private_job_body_has_only_the_reviewed_composition_dependencies():
    source = Path(__file__).parents[1] / "src/maskgw/runtime/worker_job.py"
    tree = ast.parse(source.read_text("utf8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module is not None
            modules.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "connect",
                    "close",
                    "cancel",
                    "execute",
                    "execute_validated",
                }
            elif isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "open", "__import__", "print"}
    assert modules == {
        "__future__",
        "traceback",
        "dataclasses",
        "enum",
        "typing",
        "maskgw.db.execution_error",
        "maskgw.db.postgres",
        "maskgw.db.result",
        "maskgw.errors",
        "maskgw.pgwire.result_encoder",
        "maskgw.pgwire.result_frame",
    }


@pytest.mark.parametrize(
    "statement",
    [
        "import maskgw.runtime.worker_job",
        "from maskgw.runtime import worker_job",
        "from .worker_job import run_job",
        "from . import worker_job",
    ],
)
def test_operational_import_guard_counterexamples(statement):
    assert operational_importers(statement)


@pytest.mark.parametrize(
    "base,args",
    [
        (TypedExecutionTimeout, ()),
        (TypedExecutionError, (ExecutionFailure.QUERY,)),
        (InvalidQuery, (CANARY,)),
        (QueryRejected, (CANARY,)),
        (DatabaseResultTypeError, ()),
        (EncodeError, (EncodeFailure.TYPE,)),
        (MemoryError, (CANARY,)),
    ],
)
def test_unlisted_subclass_never_inherits_recoverable_intent(job, monkeypatch, base, args):
    subclass = type("Unlisted", (base,), {})

    def fail(_self, _sql):
        raise subclass(*args)

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None and CANARY not in repr(outcome)


@pytest.mark.parametrize(
    "error",
    [
        CapabilityError(CANARY),
        TransformerError(CANARY),
        GeneratorExit(CANARY),
        BaseExceptionGroup(CANARY, [KeyboardInterrupt(CANARY)]),
    ],
)
def test_remaining_unknown_or_control_failures_are_fatal_without_original(job, monkeypatch, error):
    def fail(_self, _sql):
        raise error

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None and not hasattr(outcome, "__context__")
    assert not hasattr(outcome, "__cause__") and CANARY not in repr(outcome)


@pytest.mark.parametrize("extra", [-1, 1])
def test_both_rows_limit_mismatches_are_refused(job, extra):
    outcome = perform(job, limits=ResultLimits(max_rows=job[4].max_rows + extra))
    assert outcome.failure is JobFailure.PROTOCOL and not outcome.can_continue
    assert not job[1].executed


def test_inexact_generation_setting_cannot_compare_equal_as_bool(job):
    job[0]._settings = DatabaseSettings(statement_timeout_ms=1000, max_rows=1)
    object.__setattr__(job[0]._settings, "max_rows", True)
    outcome = perform(job, limits=ResultLimits(max_rows=1))
    assert outcome.failure is JobFailure.PROTOCOL and not outcome.can_continue
    assert not job[1].executed


@pytest.mark.parametrize("field", ["identity", "limits"])
def test_structural_objects_are_revalidated_before_adapter_access(job, field):
    if field == "identity":
        object.__setattr__(job[3], "job_id", 0)
    else:
        object.__setattr__(job[4], "max_rows", True)
    outcome = perform(job)
    assert outcome.failure is JobFailure.PROTOCOL and not outcome.can_continue
    assert not job[1].executed


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf")])
def test_invalid_clock_always_deadline_not_recoverable(job, value):
    deadline = ResultDeadline(expires_at=10, clock=lambda: value)
    outcome = perform(job, deadline=deadline)
    assert outcome.failure is JobFailure.DEADLINE and not outcome.can_continue
    assert not job[1].executed


def test_clock_failure_never_returns_message_or_executes(job):
    def clock():
        raise RuntimeError(CANARY)

    outcome = perform(job, deadline=ResultDeadline(expires_at=10, clock=clock))
    assert outcome.failure is JobFailure.DEADLINE and not outcome.can_continue
    assert not job[1].executed and CANARY not in repr(outcome)


@pytest.mark.parametrize("phase", ["execution", "cleanup"])
def test_failing_health_or_cleanup_never_restores_candidacy(job, monkeypatch, phase):
    def fail(_self, _sql):
        raise InvalidQuery(CANARY)

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    if phase == "cleanup":

        def cleanup(_traceback):
            raise MemoryError(CANARY)

        monkeypatch.setattr(traceback, "clear_frames", cleanup)
    else:
        calls = []

        def health(_self):
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError(CANARY)
            return True

        monkeypatch.setattr(PostgresAdapter, "_typed_connection_healthy", health)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None and CANARY not in repr(outcome)


@pytest.mark.parametrize("bad_frame", [None, b"", bytearray(100)])
def test_encoder_contract_failure_cannot_be_success(job, monkeypatch, bad_frame):
    monkeypatch.setattr(module, "encode_result", lambda *_args, **_kwargs: bad_frame)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None


def test_over_limit_encoder_contract_failure_cannot_publish_frame(job, monkeypatch):
    monkeypatch.setattr(module, "encode_result", lambda *_args, **_kwargs: b"a" * 1025)
    outcome = perform(job, limits=ResultLimits(max_rows=job[4].max_rows, max_frame_bytes=1024))
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None


def test_tampered_category_does_not_become_recoverable_string(job, monkeypatch):
    error = TypedExecutionError(ExecutionFailure.QUERY)
    cast(Any, error).category = "QUERY"

    def fail(_self, _sql):
        raise error

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue


def test_exactly_one_typed_execution_and_one_encode_no_legacy_fallback(job, monkeypatch):
    typed = PostgresAdapter._execute_typed_validated
    encode = real_encode
    calls = []

    def execute(self, sql):
        assert self is job[0]
        calls.append("execute")
        return typed(self, sql)

    def encode_once(*args, **kwargs):
        assert kwargs["identity"] is job[3] and kwargs["limits"] is job[4]
        assert kwargs["deadline"] is job[5]
        calls.append("encode")
        return encode(*args, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy/connect/close called")

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", execute)
    monkeypatch.setattr(PostgresAdapter, "execute", forbidden)
    monkeypatch.setattr(PostgresAdapter, "connect", forbidden)
    monkeypatch.setattr(PostgresAdapter, "close", forbidden)
    monkeypatch.setattr(module, "encode_result", encode_once)
    assert perform(job).failure is None
    assert calls == ["execute", "encode"]


def test_authoritative_exception_alias_and_derived_rule_keep_pipeline_semantics(job):
    config = """
exceptions:
  - match: public_id
masking:
  - match: cpf
    transformer: fixed
    config: {value: "[MASK]"}
"""
    item, cursor, conn = adapter(
        [TypedColumn("public_id", 23), TypedColumn("cpf", 23), TypedColumn("derived", 25)],
        [(123456, 789, 123456)],
        config,
    )
    conn.broken = False
    conn.info.status = psycopg.pq.ConnStatus.OK
    conn.info.transaction_status = psycopg.pq.TransactionStatus.IDLE
    cursor.pgresult = FakePgResult([(10, 1), (10, 2), (0, 0)])
    item._provenance = FakeResolver(
        {
            (10, 1): ColumnOrigin(kind=ProvenanceKind.DIRECT, name="cpf"),
            (10, 2): ColumnOrigin(kind=ProvenanceKind.DIRECT, name="public_id"),
        }
    )
    outcome = run_job(
        item,
        "SELECT cpf AS public_id, public_id AS cpf, cpf || '' AS derived FROM clients",
        identity=job[3],
        limits=job[4],
        deadline=job[5],
    )
    assert outcome.failure is None
    assert outcome.frame is not None
    assert b"123456" not in outcome.frame and outcome.frame.count(b"[MASK]") == 2
    assert b"789" in outcome.frame
    parsed = validate_result(outcome.frame, expected=job[3], limits=job[4], deadline=job[5])
    assert parsed.columns == 3 and parsed.rows == 1


@pytest.mark.parametrize("limit", ["cell", "frame"])
def test_real_encoder_refuses_limit_without_partial_output_and_keeps_healthy_connection(job, limit):
    limits = ResultLimits(
        max_rows=job[4].max_rows,
        max_cell_bytes=3 if limit == "cell" else 1024,
        max_frame_bytes=100 if limit == "frame" else 1024,
    )
    outcome = perform(job, limits=limits)
    assert outcome.failure is JobFailure.LIMIT and outcome.can_continue
    assert outcome.frame is None and len(job[1].executed) == 1
    assert job[0]._typed_connection_healthy() and job[2].closed is False


def test_real_encoder_type_refusal_has_no_value_or_frame_and_does_not_retry(job):
    job[1].description = [TypedColumn("x", 25)]
    job[1]._pending = [(CANARY + "\0",)]
    outcome = perform(job, "SELECT 'value' AS x")
    assert outcome.failure is JobFailure.TYPE and outcome.can_continue
    assert outcome.frame is None and CANARY not in repr(outcome)
    assert len(job[1].executed) == 1


def test_local_failure_outcome_has_no_console_side_channel(job, monkeypatch, capsys):
    def fail(_self, _sql):
        raise RuntimeError(CANARY)

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert not outcome.can_continue and outcome.failure is JobFailure.INTERNAL
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_metaclass_equality_cannot_impersonate_an_exact_query_error(job, monkeypatch):
    class EqualMeta(type):
        def __eq__(cls, _other):
            return True

        __hash__ = type.__hash__

    class OpaqueError(Exception, metaclass=EqualMeta):
        pass

    def fail(_self, _sql):
        raise OpaqueError(CANARY)

    monkeypatch.setattr(PostgresAdapter, "_execute_typed_validated", fail)
    outcome = perform(job)
    assert outcome.failure is JobFailure.INTERNAL and not outcome.can_continue
    assert outcome.frame is None
