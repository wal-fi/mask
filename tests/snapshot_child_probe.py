"""Test-only process probe: synthetic observations, NOT a worker/result codec.

Importing this helper in pytest installs no audit hook. Only its executable
entry point installs a test guard, before importing maskgw. -I is Python path
isolation, not OS containment. All returned digests aggregate synthetic data;
they prove observable equivalence for these fixtures, not literal-byte identity.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import secrets
import string
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

if TYPE_CHECKING:
    from maskgw.config.gateway import GatewayConfig
    from maskgw.masking.engine import MaskingEngine

MAX_PROBE_OUTPUT = 16 * 1024
BLOCKED_EVENTS = ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system")
RANDOM_SHAPES: tuple[tuple[str, bool, int | None], ...] = (
    ("digits", True, None),
    ("alphanumeric", True, None),
    ("digits", False, 0),
    ("digits", False, 13),
    ("alphanumeric", False, 9),
)
QUERIES = (
    "SELECT substr(cpf, 1, 3) AS tipo_cpf FROM customer",
    "SELECT min(cpf) AS documento FROM customer",
    "SELECT cpf AS documento FROM customer UNION ALL SELECT 'literal' AS documento",
    "SELECT substr(tipo_cpf, 1, 3) AS documento FROM customer",
)


def fixture_values() -> tuple[object, ...]:
    return (
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
    )


def fingerprint(value: object) -> str:
    """Only trusted fixtures; sorted mappings and no set/hash() iteration."""
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=repr,
    ).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def observe(
    config: GatewayConfig, engine: MaskingEngine, conninfo: str, random_case: int = -1
) -> dict[str, str | bool]:
    from maskgw.masking.descriptor import ColumnDescriptor  # noqa: PLC0415
    from maskgw.sql.sensitivity import analyze_sensitivity  # noqa: PLC0415
    from maskgw.sql.validator import validate_select  # noqa: PLC0415

    columns = [
        ColumnDescriptor("documento", origin_name="CPF"),
        ColumnDescriptor("tipo_cpf", origin_name="cpf"),
        ColumnDescriptor("documento", origin_name="tipo_cpf"),
        ColumnDescriptor("tipo_cpf"),
        ColumnDescriptor("cpf_outra", origin_name="irrelevante"),
        ColumnDescriptor("sem_match"),
        ColumnDescriptor("tipo_cpf", derived_rule_index=0),
        ColumnDescriptor("CPF"),
        ColumnDescriptor("cpf"),
    ]
    matrix = []
    real_choice = secrets.choice
    # Test-only patch, restored in BOTH parent and child. No product seed/hook.
    with patch(
        "maskgw.masking.transformers.randomize.secrets_module.choice",
        lambda alphabet: alphabet[0],
    ):
        for column in columns:
            row = []
            for value in fixture_values():
                output = engine.mask_value(column, value)
                row.append((type(output).__module__, type(output).__qualname__, output))
            matrix.append(row)
    assert secrets.choice is real_choice

    arity_rejected = False
    try:
        engine.mask_row(columns, ("wrong-arity",))
    except ValueError:
        arity_rejected = True

    ast_observations: list[object] = []
    for query in QUERIES:
        indices = analyze_sensitivity(validate_select(query, policy=config.sql), engine.policy)
        ast_observations.append(indices)

    random_valid = True
    if random_case >= 0:
        strategy, preserve, length = RANDOM_SHAPES[random_case]
        alphabet = string.digits if strategy == "digits" else string.ascii_letters + string.digits
        column = ColumnDescriptor("cpf")
        for value in ("", "a", "longer-input"):
            for _ in range(12):
                output = engine.mask_value(column, value)
                random_valid &= (
                    type(output) is str
                    and len(output) == (len(value) if preserve else length)
                    and set(output) <= set(alphabet)
                )
        random_valid &= engine.mask_value(column, None) is None

    sql = config.sql
    return {
        "matrix": fingerprint(matrix),
        "decisions": fingerprint([dataclasses.astuple(engine.decide(c)) for c in columns]),
        "parameters": fingerprint(
            [(r.index, r.transformer_name, repr(r.transformer)) for r in engine.policy.rules]
        ),
        "database": fingerprint(dataclasses.astuple(config.database)),
        "sql": fingerprint(
            (
                sorted(sql.allowed_pg_functions),
                sorted(sql.denied_functions),
                list(sql.denied_prefixes),
                sorted(sql.denied_relations),
            )
        ),
        "target": fingerprint(conninfo),
        "ast": fingerprint(ast_observations),
        "arity_rejected": arity_rejected,
        "entropy_restored": secrets.choice is real_choice,
        "random_valid": bool(random_valid),
    }


def deny_external_io(event: str, _args: tuple[object, ...]) -> None:
    if event.startswith(("socket.", "subprocess.")) or event == "os.system":
        raise RuntimeError("test probe external I/O refused")


def main() -> None:
    # Irreversible hook: CHILD ONLY, never installed when pytest imports helper.
    sys.addaudithook(deny_external_io)

    from maskgw.runtime.snapshot import (  # noqa: PLC0415
        MAX_SNAPSHOT_BYTES,
        SnapshotError,
        SnapshotIdentity,
        recompile_snapshot,
    )
    from maskgw.secretsource import EnvSecretProvider  # noqa: PLC0415

    guards = []
    for event in BLOCKED_EVENTS:
        try:
            sys.audit(event, None, None)
        except RuntimeError:
            guards.append(True)
        else:
            guards.append(False)

    def refuse_environment(_self: EnvSecretProvider, _name: str) -> None:
        raise RuntimeError("test probe environment reread refused")

    result: dict[str, object] = {
        "pid": os.getpid(),
        "isolated": bool(sys.flags.isolated),
        "ignore_environment": bool(sys.flags.ignore_environment),
        "guards": guards,
        "user_site_disabled": bool(sys.flags.no_user_site),
    }
    try:
        expected = SnapshotIdentity(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        data = sys.stdin.buffer.read(MAX_SNAPSHOT_BYTES + 1)
        with patch.object(EnvSecretProvider, "get", refuse_environment):
            copied = recompile_snapshot(data, expected=expected)
            result.update(
                status="ok",
                observations=observe(
                    copied.config, copied.engine, copied.connection_target(), int(sys.argv[4])
                ),
                identity=dataclasses.astuple(copied.identity),
            )
    except SnapshotError as error:
        result.update(
            status="rejected",
            category=error.category.value,
            sanitized=(
                error.args == ("snapshot de compilacao recusado",)
                and error.__cause__ is None
                and error.__context__ is None
            ),
        )
    output = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("ascii")
    assert len(output) <= MAX_PROBE_OUTPUT
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
