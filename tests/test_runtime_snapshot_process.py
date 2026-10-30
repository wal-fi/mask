"""B-1 cross-process proof only: no product worker, DB or SQL ingress."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from maskgw.datasource.models import DatasourceLimits
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.runtime.candidate import PreparedRuntime
from maskgw.runtime.snapshot import MAX_SNAPSHOT_BYTES, SnapshotIdentity
from maskgw.secretsource import MappingSecretProvider
from tests.snapshot_child_probe import MAX_PROBE_OUTPUT, RANDOM_SHAPES, observe
from tests.test_runtime_snapshot import (
    IDENTITY,
    KEY_A,
    KEY_B,
    MASTER,
    TRANSFORMERS,
    UPSTREAM,
    canonical,
    encoded,
    prepare,
)

PROBE = Path(__file__).with_name("snapshot_child_probe.py").resolve()
POISON = "synthetic-child-environment-must-not-be-used"


def run_probe(
    tmp_path: Path,
    data: bytes,
    *,
    expected: SnapshotIdentity = IDENTITY,
    random_case: int = -1,
    poisoned: bool = False,
) -> dict[str, Any]:
    env = {
        name: value
        for name in ("SystemRoot", "WINDIR", "TEMP", "TMP")
        if (value := os.environ.get(name)) is not None
    }
    if poisoned:
        env[HMAC_KEY_ENV] = POISON
        env["MASKGW_DATASOURCE_MASTER_KEY"] = POISON
        env["PGHOST"] = "synthetic-do-not-connect.invalid"
        env["PYTHONPATH"] = str(tmp_path)
        env["PYTHONHASHSEED"] = "1"  # -I ignores this; sorting must suffice.
    command = [
        sys.executable,
        "-I",
        "-B",
        str(PROBE),
        expected.datasource_id,
        str(expected.generation),
        str(expected.record_revision),
        str(random_case),
    ]
    for canary in (KEY_A, KEY_B, UPSTREAM, MASTER, POISON):
        assert all(canary not in arg for arg in command)
    process = subprocess.run(  # noqa: S603 - fixed local probe, no shell/client inputs
        command, input=data, capture_output=True, timeout=15, cwd=tmp_path, env=env, check=False
    )
    assert process.returncode == 0, "snapshot test probe failed"
    assert process.stderr == b"", "snapshot test probe wrote stderr"
    assert 0 < len(process.stdout) <= MAX_PROBE_OUTPUT
    for canary in (KEY_A, KEY_B, UPSTREAM, MASTER, POISON):
        assert canary.encode() not in process.stdout
        assert canary.encode() not in process.stderr
    result: dict[str, Any] = json.loads(process.stdout)
    assert result["pid"] != os.getpid()
    assert result["isolated"] and result["ignore_environment"] and result["user_site_disabled"]
    assert result["guards"] == [True] * 4
    return result


def assert_equivalent(
    result: dict[str, Any],
    original: PreparedRuntime,
    *,
    identity: SnapshotIdentity = IDENTITY,
    random_case: int = -1,
) -> None:
    assert result["status"] == "ok"
    assert result["identity"] == [
        identity.datasource_id,
        identity.generation,
        identity.record_revision,
    ]
    assert result["observations"] == observe(
        original.config, original.engine, original.verify_target()[0], random_case
    )
    assert result["observations"]["arity_rejected"]
    assert result["observations"]["random_valid"]
    assert result["observations"]["entropy_restored"]


@pytest.mark.parametrize(("transformer", "config"), TRANSFORMERS)
def test_deterministic_observations_equal_in_real_isolated_child(tmp_path, transformer, config):
    original = prepare(
        {
            "masking": [{"match": "cpf", "transformer": transformer, "config": config}],
            "exceptions": [{"match": "tipo_cpf"}],
        }
    )
    result = run_probe(tmp_path, encoded(original))
    assert_equivalent(result, original)


@pytest.mark.parametrize("case", range(len(RANDOM_SHAPES)))
def test_random_parameters_controlled_observations_and_real_invariants_in_child(tmp_path, case):
    strategy, preserve, length = RANDOM_SHAPES[case]
    config = {"strategy": strategy, "preserve_length": preserve}
    if length is not None:
        config["length"] = length
    original = prepare({"masking": [{"match": "cpf", "transformer": "random", "config": config}]})
    result = run_probe(tmp_path, encoded(original), random_case=case)
    assert_equivalent(result, original, random_case=case)


def test_order_case_sql_effective_limits_and_pinned_target_survive_process_boundary(tmp_path):
    original = prepare(
        {
            "database": {"max_rows": 900, "statement_timeout_ms": 1500},
            "sql": {"allowed_pg_functions": ["pg_custom_safe"], "denied_functions": ["lower"]},
            "masking": [
                {
                    "match": "CPF",
                    "mode": "exact",
                    "case_sensitive": True,
                    "transformer": "fixed",
                    "config": {"value": "first"},
                },
                {"match": "cpf", "transformer": "fixed", "config": {"value": "second"}},
            ],
            "exceptions": [{"match": "tipo_cpf"}],
        },
        limits=DatasourceLimits(max_rows=7, statement_timeout_ms=3000),
    )
    assert_equivalent(run_probe(tmp_path, encoded(original)), original)


def test_hmac_old_generation_survives_parent_rotation_and_poisoned_child_environment(
    tmp_path, monkeypatch
):
    raw = {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
    old = prepare(raw)
    old_data = encoded(old)
    monkeypatch.setenv(HMAC_KEY_ENV, KEY_B)
    newer = prepare(raw, provider=MappingSecretProvider({HMAC_KEY_ENV: KEY_B}))
    newer_identity = SnapshotIdentity(IDENTITY.datasource_id, 12, 31)
    first = run_probe(tmp_path, old_data, poisoned=True)
    second = run_probe(
        tmp_path, encoded(newer, newer_identity), expected=newer_identity, poisoned=True
    )
    assert_equivalent(first, old)
    assert_equivalent(second, newer, identity=newer_identity)
    assert first["observations"]["matrix"] != second["observations"]["matrix"]
    assert first["pid"] != second["pid"]


def test_custom_secret_provider_whitespace_is_preserved_in_child(tmp_path):
    class ExactProvider:
        def get(self, _name: str) -> str:
            return "  " + KEY_A + "  "

    raw = {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
    original = prepare(raw, provider=ExactProvider())
    payload = encoded(original)
    assert json.loads(payload)["runtime"]["secrets"][HMAC_KEY_ENV] == "  " + KEY_A + "  "
    result = run_probe(tmp_path, payload, poisoned=True)
    assert_equivalent(result, original)
    normalized = prepare(raw)
    assert (
        result["observations"]["matrix"]
        != observe(normalized.config, normalized.engine, normalized.verify_target()[0])["matrix"]
    )


def test_empty_policy_does_not_fall_back_to_poisoned_environment_or_cwd(tmp_path):
    shadow = tmp_path / "maskgw"
    shadow.mkdir()
    (shadow / "__init__.py").write_text(
        "raise RuntimeError('synthetic-cwd-shadow-must-not-import')", encoding="ascii"
    )
    original = prepare({})
    assert_equivalent(run_probe(tmp_path, encoded(original), poisoned=True), original)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"\xff",
        b"NaN",
        b'{"x":1,"x":2}',
        b"[" * 33 + b"]" * 33,
        b"x" * (MAX_SNAPSHOT_BYTES + 1),
    ],
    ids=["empty", "object", "bad-ascii", "nan", "duplicate", "depth", "size"],
)
def test_invalid_snapshot_is_refused_by_real_child_without_sensitive_error(tmp_path, payload):
    result = run_probe(tmp_path, payload, poisoned=True)
    assert result["status"] == "rejected"
    assert result["category"] == "INVALID"
    assert result["sanitized"]
    assert "observations" not in result


@pytest.mark.parametrize(
    "kind",
    [
        "noncanonical",
        "truncated",
        "identity",
        "missing-secret",
        "unknown-secret",
        "policy",
        "version",
        "datasource",
        "record-revision",
        "bool-generation",
    ],
)
def test_tampered_snapshot_is_refused_in_child(tmp_path, kind):
    original = prepare({"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]})
    payload = encoded(original)
    raw = json.loads(payload)
    category = "INVALID"
    if kind == "noncanonical":
        payload = b" " + payload
    elif kind == "truncated":
        payload = payload[:-1]
    else:
        if kind == "identity":
            raw["identity"]["generation"] += 1
        elif kind == "datasource":
            raw["identity"]["datasource_id"] = "dso_" + "b" * 32
        elif kind == "record-revision":
            raw["identity"]["record_revision"] += 1
        elif kind == "bool-generation":
            raw["identity"]["generation"] = True
        elif kind == "missing-secret":
            raw["runtime"]["secrets"].clear()
            category = "POLICY"
        elif kind == "unknown-secret":
            raw["runtime"]["secrets"]["MASKGW_DATASOURCE_MASTER_KEY"] = MASTER
        elif kind == "policy":
            raw["runtime"]["policy"]["masking"][0]["transformer"] = "unknown"
            category = "POLICY"
        else:
            raw["version"] = True
        payload = canonical(raw)
    result = run_probe(tmp_path, payload, poisoned=True)
    assert result["status"] == "rejected"
    assert result["category"] == category
    assert result["sanitized"]
    assert "observations" not in result
