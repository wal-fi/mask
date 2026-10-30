"""Exact opaque-slot association, using fakes only; no Docker or native imports."""

from __future__ import annotations

import json
import time
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests import test_linux_imports_probe as lab_fixtures
from tests.test_linux_imports_batch import ending
from tests.test_linux_imports_probe import HOST, PROBE, audit_event, normal

attached_native = lab_fixtures.attached_native
isolated_supervisor = lab_fixtures.isolated_supervisor

NAME = "_openssl.lib"
PROVIDER = "cryptography.hazmat.bindings._rust"
RELATIVE = "cryptography/hazmat/bindings/_rust.abi3.so"
ROW = [NAME, "cryptography", "attached-by-identity-slot/lib/installed/" + RELATIVE]


def opaque(reads: list[str]) -> Any:
    class Hostile:
        def __getattribute__(self, name):
            reads.append(name)
            raise AssertionError("SECRET candidate attribute")

        def __getattr__(self, name):
            reads.append(name)
            raise AssertionError("SECRET candidate fallback")

        def __eq__(self, _other):
            reads.append("equality")
            raise AssertionError("SECRET candidate equality")

        def __hash__(self):
            reads.append("hash")
            raise AssertionError("SECRET candidate hash")

        def __repr__(self):
            reads.append("repr")
            raise AssertionError("SECRET candidate representation")

        def __bool__(self):
            reads.append("bool")
            raise AssertionError("SECRET candidate truthiness")

    return Hostile()


def lib_error(stage: int = 0, category: str = "FILELESS_UNATTRIBUTED") -> dict[str, Any]:
    return {
        **audit_event(stage),
        "module": NAME,
        "category": category,
        "has_file": None,
        "under_installed": None,
    }


@pytest.mark.parametrize("stage", [-1, 0, 1, 2])
def test_exact_slot_success_never_observes_candidate(attached_native, stage):
    child, _provider, modules, owners = attached_native
    reads: list[str] = []
    candidate = opaque(reads)
    child.__dict__["lib"] = modules[NAME] = candidate
    emitted: list[dict[str, Any]] = []
    accepted = PROBE.audit_module(
        SimpleNamespace(emit=emitted.append), stage, NAME, candidate, owners, {}
    )
    assert reads == []
    assert accepted
    assert emitted == [
        {"phase": "baseline", "row": ROW}
        if stage == -1
        else {"phase": "module", "stage": stage, "row": ROW}
    ]
    assert PROBE.audit_context(candidate, NAME) == (None, None)
    assert reads == []


def test_matching_batch_slot_is_lib_without_candidate_observation(attached_native):
    child, _provider, modules, owners = attached_native
    reads: list[str] = []
    candidate = opaque(reads)
    child.__dict__["lib"] = modules[NAME] = candidate
    details, terminal = PROBE.batch_candidates(0, [NAME], set(), owners, {}, time.monotonic() + 5)
    assert reads == []
    assert details == [
        {
            "phase": "batch_detail",
            "stage": 0,
            "module": NAME,
            "kind": "NON_MODULE",
            "dict_file": None,
            "identity_slot": "LIB",
        }
    ]
    assert terminal == ending(1)


@pytest.mark.parametrize(
    "fault",
    [
        "slot_missing",
        "slot_none",
        "slot_different",
        "cache_missing",
        "cache_different",
        "anchor_missing",
        "anchor_wrong_type",
        "anchor_file",
        "provider_missing",
        "provider_wrong_type",
        "provider_link_missing",
        "provider_link_different",
        "provider_file_missing",
        "provider_path_wrong",
        "provider_owner_wrong",
        "provider_owner_missing",
    ],
)
def test_exact_slot_refusal_and_batch_never_observe_candidate(attached_native, fault):
    child, provider, modules, owners = attached_native
    reads: list[str] = []
    candidate = opaque(reads)
    child.__dict__["lib"] = modules[NAME] = candidate
    mutations = {
        "slot_missing": lambda: child.__dict__.pop("lib"),
        "slot_none": lambda: child.__dict__.update(lib=None),
        "slot_different": lambda: child.__dict__.update(lib=object()),
        "cache_missing": lambda: modules.pop(NAME),
        "cache_different": lambda: modules.update({NAME: object()}),
        "anchor_missing": lambda: modules.pop("_openssl"),
        "anchor_wrong_type": lambda: modules.update(_openssl=object()),
        "anchor_file": lambda: setattr(child, "__file__", "/installed/cryptography/fake.py"),
        "provider_missing": lambda: modules.pop(PROVIDER),
        "provider_wrong_type": lambda: modules.update({PROVIDER: object()}),
        "provider_link_missing": lambda: provider.__dict__.pop("_openssl"),
        "provider_link_different": lambda: provider.__dict__.update(
            _openssl=ModuleType("_openssl")
        ),
        "provider_file_missing": lambda: provider.__dict__.pop("__file__"),
        "provider_path_wrong": lambda: setattr(
            provider, "__file__", "/installed/cryptography/wrong.so"
        ),
        "provider_owner_wrong": lambda: owners.update(cryptography="wrong-owner"),
        "provider_owner_missing": owners.clear,
    }
    mutations[fault]()
    emitted: list[dict[str, Any]] = []
    accepted = PROBE.audit_module(
        SimpleNamespace(emit=emitted.append),
        0,
        NAME,
        candidate,
        owners,
        {},
        batch=([NAME], set(), time.monotonic() + 5),
    )
    assert reads == []
    assert not accepted
    assert emitted[0] == lib_error()
    assert emitted[-1]["phase"] == "batch_end"
    assert "SECRET" not in json.dumps(emitted)


@pytest.mark.parametrize("cache_present", [False, True])
def test_none_is_never_a_slot_identity(attached_native, cache_present):
    child, _provider, modules, owners = attached_native
    child.__dict__["lib"] = None
    if cache_present:
        modules[NAME] = None
    with pytest.raises(PROBE.AuditFault) as caught:
        PROBE.module_row(NAME, None, owners)
    assert caught.value.category == "FILELESS_UNATTRIBUTED"


def test_equal_but_different_is_not_identity(attached_native):
    child, _provider, modules, owners = attached_native
    comparisons: list[bool] = []

    class Equal:
        __hash__ = object.__hash__

        def __eq__(self, _other):
            comparisons.append(True)
            return True

    candidate = Equal()
    child.__dict__["lib"] = Equal()
    modules[NAME] = candidate
    with pytest.raises(PROBE.AuditFault) as caught:
        PROBE.module_row(NAME, candidate, owners)
    assert caught.value.category == "FILELESS_UNATTRIBUTED"
    assert comparisons == []


def test_anchor_rechecked_after_its_previous_row(attached_native):
    child, provider, modules, owners = attached_native
    candidate = object()
    child.__dict__["lib"] = modules[NAME] = candidate
    assert PROBE.module_row("_openssl", child, owners)[2].startswith("attached-by-identity/")
    provider.__dict__["_openssl"] = ModuleType("_openssl")
    with pytest.raises(PROBE.AuditFault) as caught:
        PROBE.module_row(NAME, candidate, owners)
    assert caught.value.category == "FILELESS_UNATTRIBUTED"


def test_unexpected_anchor_error_is_other_without_candidate_read(attached_native):
    child, _provider, modules, _owners = attached_native
    reads: list[str] = []
    candidate = opaque(reads)
    child.__dict__["lib"] = modules[NAME] = candidate

    class BrokenOwners(dict[str, str]):
        def get(self, *_args):
            raise RuntimeError("SECRET anchor path")

    owners = BrokenOwners()
    emitted: list[dict[str, Any]] = []
    assert not PROBE.audit_module(
        SimpleNamespace(emit=emitted.append), 0, NAME, candidate, owners, {}
    )
    assert reads == []
    assert emitted == [lib_error(category="OTHER")]
    assert PROBE.batch_anchor(owners, {}) is None
    assert "SECRET" not in json.dumps(emitted)


def test_emission_error_uses_unmeasured_context_without_read(attached_native):
    child, _provider, modules, owners = attached_native
    reads: list[str] = []
    candidate = opaque(reads)
    child.__dict__["lib"] = modules[NAME] = candidate
    emitted: list[dict[str, Any]] = []

    def emit(event):
        emitted.append(event)
        if len(emitted) == 1:
            raise OSError("SECRET emission")

    assert not PROBE.audit_module(SimpleNamespace(emit=emit), 0, NAME, candidate, owners, {})
    assert reads == []
    assert emitted == [{"phase": "module", "stage": 0, "row": ROW}, lib_error(category="OTHER")]
    assert "SECRET" not in json.dumps(emitted)


@pytest.mark.parametrize("name", ["_openssl.ffi", "_openssl.lib.extra", "prefix._openssl.lib"])
def test_no_prefix_or_other_slot_rule(attached_native, name):
    child, _provider, modules, owners = attached_native
    candidate = SimpleNamespace()
    child.__dict__["lib"] = child.__dict__["ffi"] = candidate
    modules[name] = candidate
    with pytest.raises(PROBE.AuditFault) as caught:
        PROBE.module_row(name, candidate, owners)
    assert caught.value.category == "FILELESS_UNATTRIBUTED"


@pytest.mark.parametrize("stage", [-1, 0, 1, 2])
def test_only_exact_lib_error_accepts_unmeasured_pair(stage):
    assert PROBE.valid_audit_error(lib_error(stage), stage)
    assert PROBE.valid_audit_error(audit_event(stage), stage)


@pytest.mark.parametrize("name", [None, "fixture.generated", "_openssl", "_openssl.lib.extra"])
def test_null_context_on_any_other_name_is_protocol(name):
    assert not PROBE.valid_audit_error({**lib_error(), "module": name}, 0)


@pytest.mark.parametrize(
    "has_file,under", [(None, False), (False, None), (False, False), (True, True)]
)
def test_lib_context_cannot_forge_boolean_or_mixed_measurement(has_file, under):
    assert not PROBE.valid_audit_error(
        {**lib_error(), "has_file": has_file, "under_installed": under}, 0
    )


def test_null_context_error_stays_inconclusive_in_supervisor_and_host(isolated_supervisor):
    result = isolated_supervisor([{"phase": "start", "stage": 0}, lib_error(), ending(0)])
    assert result["diagnostic_failure"] == "AUDIT_ERROR"
    assert result["audit_error"] == lib_error()
    assert result["outcome"] == "inconclusive"
    assert result["cleanup_confirmed"] and result["member_returncode"] == 75
    assert HOST.classify_limited(normal(), result) == "inconclusive"
    assert (
        HOST.classify_limited({**normal(), "audit_error": lib_error()}, normal()) == "inconclusive"
    )


@pytest.mark.parametrize("category", ["FILELESS_UNATTRIBUTED", "OTHER"])
def test_unmeasured_lib_error_never_becomes_accepted_inventory(isolated_supervisor, category):
    terminal = [ending(0)] if category == "FILELESS_UNATTRIBUTED" else []
    result = isolated_supervisor(
        [{"phase": "start", "stage": 0}, lib_error(category=category), *terminal]
    )
    assert result["diagnostic_failure"] == "AUDIT_ERROR"
    assert PROBE.unpack_inventory(result["module_inventory"]) == []
