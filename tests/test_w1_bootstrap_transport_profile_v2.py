"""Measured profile v2 contracts. Public in-memory fixtures, no native effects."""

import ast
import asyncio
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.test_w1_bootstrap_probe import inventory

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_transport_profile_v2.py"))


@pytest.fixture
def factory() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_probe.py"))


@pytest.fixture
def namespaces() -> Any:
    value = {
        key: runpy.run_path(str(REPO / ("docs/poc/w1_bootstrap_" + key + ".py")))
        for key in ("channel", "identity", "emergency")
    }
    value["bounded"] = runpy.run_path(str(REPO / "docs/poc/run_linux_as_probe.py"))
    return value


def function(raw: bytes, name: str) -> Any:
    return next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == name)


def test_validator_only_changes_measured_boolean_and_explicit_collaborators(module):
    original = function(module["RAW"]["policy"], "validate_container")
    variant = function(Path(module["__file__"]).read_bytes(), "validate_container")
    assert [arg.arg for arg in variant.args.args] == ["info", "intent", "factory"]
    assert [n.targets[0].id for n in variant.body[:6]] == [
        "identity",
        "channel_bytes",
        "Case",
        "ENV",
        "need",
        "labels_for",
    ]
    for node in variant.body[:6]:
        assert isinstance(node.value, ast.Subscript)
        assert isinstance(node.value.value, ast.Name)
        assert isinstance(node.value.slice, ast.Constant)
        assert node.value.value.id == "factory" and node.value.slice.value == node.targets[0].id
    variant.body = variant.body[6:]
    variant.args.args.pop()
    changes = 0
    for node in ast.walk(variant):
        if isinstance(node, ast.Compare) and ast.dump(node.left) == ast.dump(
            ast.parse('config["StdinOnce"]', mode="eval").body
        ):
            assert len(node.ops) == 1 and isinstance(node.ops[0], ast.Is)
            assert isinstance(node.comparators[0], ast.Constant)
            assert node.comparators[0].value is True
            node.comparators[0].value = False
            changes += 1
    assert changes == 1 and ast.dump(variant) == ast.dump(original)


def test_publication_only_expands_exact_case_name_regex(module):
    original = function(module["RAW"]["core"], "publication")
    variant = function(Path(module["__file__"]).read_bytes(), "publication")
    old = r"maskgw-ol9-t4-[0-9a-f]{12}-(normal|retain)"
    new = old[:-1] + "|bad-ready|blackhole|flood|cancel-start|reader-negative)"
    nodes = [n for n in ast.walk(variant) if isinstance(n, ast.Constant) and n.value == new]
    assert len(nodes) == 1
    nodes[0].value = old
    assert ast.dump(variant) == ast.dump(original)


@pytest.mark.parametrize("index", range(7))
def test_all_seven_cases_accept_only_exact_measured_stdin_once(module, factory, index):
    info, intent = inventory(factory, list(factory["Case"])[index])
    before = deepcopy(info)
    with pytest.raises(RuntimeError, match="CONFIG"):
        module["validate_container"](info, intent, factory)
    info["Config"]["StdinOnce"] = True
    assert module["validate_container"](info, intent, factory) == info["Id"]
    assert before["Config"]["StdinOnce"] is False
    with pytest.raises(RuntimeError, match="CONFIG"):
        factory["validate_container"](info, intent)
    assert (
        module["publication"](
            json.dumps([info]).encode(),
            factory["ENV"],
            factory["labels_for"](intent.task),
            intent.command,
            factory["ENTRY"],
            cid=info["Id"],
            name=factory["name_for"](intent.task, intent.case),
        )["allowed"]
        is True
    )


@pytest.mark.parametrize("value", [0, 1, None, "true", False])
def test_stdin_once_is_boolean_identity_not_truthiness(module, factory, value):
    info, intent = inventory(factory, factory["Case"].NORMAL)
    info["Config"]["StdinOnce"] = value
    with pytest.raises(RuntimeError, match="CONFIG"):
        module["validate_container"](info, intent, factory)


@pytest.mark.parametrize(
    "where,value,code",
    [
        (("Config", "User"), "0:0", "CONFIG"),
        (("Config", "Labels"), {}, "OWNERSHIP"),
        (("HostConfig", "Memory"), 1, "PROFILE"),
        (("HostConfig", "NetworkMode"), "bridge", "PROFILE"),
        (("HostConfig", "LogConfig"), {"Type": "json-file", "Config": {}}, "ISOLATION"),
        (("HostConfig", "Tmpfs"), {"/public-canary-only": "rw"}, "SURFACE"),
    ],
)
def test_no_other_profile_constraint_is_relaxed(module, factory, where, value, code):
    info, intent = inventory(factory, factory["Case"].NORMAL)
    info["Config"]["StdinOnce"] = True
    info[where[0]][where[1]] = value
    with pytest.raises(RuntimeError, match=code):
        module["validate_container"](info, intent, factory)


def test_categories_are_derived_from_exact_captured_types_and_literal_sets(module, namespaces):
    codes = set()
    for name in (
        "w1_bootstrap_probe.py",
        "w1_bootstrap_t4_host.py",
        "oracle9_w1_run.py",
        "oracle9_w1_run_v2.py",
        "w1_bootstrap_t4_v2_run.py",
    ):
        for node in ast.walk(ast.parse((REPO / "docs/poc" / name).read_bytes())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "need"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and type(node.args[1].value) is str
            ):
                codes.add(node.args[1].value)
            if (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "RuntimeError"
                and len(node.exc.args) == 1
                and isinstance(node.exc.args[0], ast.Constant)
                and type(node.exc.args[0].value) is str
            ):
                codes.add(node.exc.args[0].value)
    assert module["RUNTIME_CODES"] == codes | {"T4_WATCHDOG_REFUSED"}
    for code in module["RUNTIME_CODES"]:
        assert module["closed_category"](RuntimeError(code), namespaces) == code


def test_other_exact_category_sets_match_captured_sources(module, namespaces):
    emergency_codes = set()
    for node in ast.walk(ast.parse((REPO / "docs/poc/w1_bootstrap_emergency.py").read_bytes())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EmergencyError"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            emergency_codes.add(node.args[0].value)
    assert module["EMERGENCY_CODES"] == emergency_codes
    for constant, names, constructor in (
        ("VALUE_CODES", ("oracle9_cycle_freshness.py", "oracle9_clock_sample.py"), "ValueError"),
        ("BOUNDED_CODES", ("run_linux_as_probe.py",), "HostFault"),
    ):
        literals = set()
        for name in names:
            for node in ast.walk(ast.parse((REPO / "docs/poc" / name).read_bytes())):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == constructor
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                ):
                    literals.add(node.args[0].value)
        assert module[constant] == literals
    classify = module["closed_category"]
    for code in emergency_codes:
        assert classify(namespaces["emergency"]["EmergencyError"](code), namespaces) == code
    for code in module["VALUE_CODES"]:
        assert classify(ValueError(code), namespaces) == code
    for code in module["BOUNDED_CODES"]:
        assert classify(namespaces["bounded"]["HostFault"](code), namespaces) == code
    for fault in namespaces["channel"]["Fault"]:
        assert classify(namespaces["channel"]["BootstrapError"](fault), namespaces) == fault.value
    assert classify(namespaces["identity"]["IdentityError"](), namespaces) == "IDENTITY_UNKNOWN"
    assert classify(asyncio.CancelledError("fake-private"), namespaces) == "CANCELLED"
    assert classify(TimeoutError("fake-private"), namespaces) == "DEADLINE"


def test_foreign_subclass_or_malformed_categories_are_internal_without_error_text(
    module, namespaces
):
    foreign = runpy.run_path(str(REPO / "docs/poc/w1_bootstrap_channel.py"))
    cls = namespaces["channel"]["BootstrapError"]
    malformed = cls(namespaces["channel"]["Fault"].IO)
    malformed.category = "fake-private"
    bad_args = namespaces["emergency"]["EmergencyError"]("INPUT")
    bad_args.args = ("INPUT", "fake-private")
    unknown_args = namespaces["emergency"]["EmergencyError"]("INPUT")
    unknown_args.args = ("fake-private",)
    child = type("Child", (cls,), {})
    errors = [
        foreign["BootstrapError"](foreign["Fault"].IO),
        child(namespaces["channel"]["Fault"].IO),
        malformed,
        RuntimeError("fake-private"),
        RuntimeError("CONFIG", "fake-private"),
        ValueError("CONFIG"),
        unknown_args,
        bad_args,
    ]
    assert {module["closed_category"](error, namespaces) for error in errors} == {"INTERNAL"}


def test_cleanup_checks_capture_without_reopening_changed_source(module, monkeypatch):
    module["pins"]()
    real = Path.read_bytes

    def changed(path):
        if path == REPO / module["DEPENDENCIES"]["policy"][0]:
            return b"changed"
        return real(path)

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        module["pins"]()
    module["pins"](cleanup=True)
    module["RAW"]["policy"] = b"changed capture"
    with pytest.raises(RuntimeError, match="SOURCE_PIN"):
        module["pins"](cleanup=True)


def test_consumed_dependency_pins_remain_exact(module):
    for key, (relative, digest) in module["DEPENDENCIES"].items():
        assert hashlib.sha256((REPO / relative).read_bytes()).hexdigest() == digest
        assert hashlib.sha256(module["RAW"][key]).hexdigest() == digest


def test_inherited_error_origins_have_closed_categories(module, namespaces):
    classify = module["closed_category"]
    for code in ("CYCLE_REFUSED", "WAIT_CLOCK", "APP_EXIT", "JOURNAL_CHAIN", "HOST_LOOP"):
        assert classify(RuntimeError(code), namespaces) == code
    for code in ("CYCLE_SCHEMA", "CLOCK_REFUSED"):
        assert classify(ValueError(code), namespaces) == code
    for code in ("CLI_CLEANUP", "OUTPUT_LIMIT"):
        assert classify(namespaces["bounded"]["HostFault"](code), namespaces) == code
    assert classify(ValueError("fake-private"), namespaces) == "INTERNAL"
    foreign = runpy.run_path(str(REPO / "docs/poc/run_linux_as_probe.py"))
    assert classify(foreign["HostFault"]("CLI_CLEANUP"), namespaces) == "INTERNAL"
