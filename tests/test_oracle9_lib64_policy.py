"""Pure/fake-filesystem assertions, not native Linux proof of the alias/cache."""

import copy
import hashlib
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "deploy/oracle9_python_payload.py"


def policy() -> dict[str, Any]:
    return runpy.run_path(str(SOURCE))


def report(p: dict[str, Any]) -> dict[str, Any]:
    alias = {
        "link": "usr/lib64",
        "alias": {"kind": "symlink", "dev": 1, "ino": 2, "uid": 0, "gid": 0, "mode": 0o777},
        "target": {"kind": "directory", "dev": 1, "ino": 3, "uid": 0, "gid": 0, "mode": 0o755},
    }
    nodes = {}
    for i, name in enumerate(p["TIRPC_NAMES"]):
        link = i == 0
        nodes["/usr/lib64/" + name] = {
            "rpm_path": "/lib64/" + name,
            "owner": ["libtirpc", "x86_64"],
            "alias_dev": 1,
            "alias_ino": i + 10,
            "physical_dev": 1,
            "physical_ino": i + 10,
            "kind": "symlink" if link else "regular",
            "linkto": p["TIRPC_LINK"] if link else "",
            "sha256": hashlib.sha256(p["TIRPC_LINK"].encode()).hexdigest()
            if link
            else p["TIRPC_DIGEST"],
            "declared_digest": "" if link else p["TIRPC_DIGEST"],
        }
    return {
        "verification_policy": p["VERIFY_POLICY"],
        "base_verify_accepted": True,
        "base_verify_unchanged": True,
        "restored_directories": [],
        "restored_directory_facts": {},
        "aux_cache": {"action": "absent"},
        "runtime_attestation_policy": p["RUNTIME_POLICY"],
        "lib64": {"before": alias, "after": copy.deepcopy(alias), "nodes": nodes},
        "linker_cache": {
            "before": {"kind": "absent"},
            "after": {
                "path": "/etc/ld.so.cache",
                "kind": "regular",
                "uid": 0,
                "gid": 0,
                "mode": 0o644,
                "bytes": 123,
                "sha256": "a" * 64,
                "owner": ["glibc", "x86_64"],
            },
        },
        "new_paths": list(nodes),
    }


def test_full_report_preserves_both_inventory_forms_and_previous_cache_hash():
    p = policy()
    v = report(p)
    p["validate_runtime_report"](v)
    v["new_nodes"] = {
        path: {k: node[k] for k in ("owner", "sha256", "kind")}
        for path, node in v["lib64"]["nodes"].items()
    }
    p["validate_runtime_report"](v)
    v["linker_cache"]["before"] = {"kind": "regular", "sha256": "b" * 64}
    p["validate_runtime_report"](v)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("lib64", "before", "link"), "/elsewhere"),
        (("lib64", "before", "alias", "kind"), "directory"),
        (("lib64", "before", "alias", "uid"), 1),
        (("lib64", "before", "target", "kind"), "symlink"),
        (("lib64", "before", "target", "mode"), 0o777),
        (("lib64", "after", "alias", "ino"), 99),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3", "physical_ino"), 99),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3", "alias_ino"), True),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3", "owner"), ["other", "x86_64"]),
        (("lib64", "nodes", "/usr/lib64/third"), {}),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3", "linkto"), "different"),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3", "sha256"), "c" * 64),
        (("lib64", "nodes", "/usr/lib64/libtirpc.so.3.0.0", "declared_digest"), "c" * 64),
        (("lib64", "after", "target", "extra"), True),
        (("new_paths",), []),
        (("new_nodes",), {"/usr/lib64/libtirpc.so.3": {}, "/usr/lib64/libtirpc.so.3.0.0": {}}),
        (("runtime_attestation_policy",), "generic"),
    ],
)
def test_alias_report_refuses_wrong_identity_content_owner_or_schema(path, value):
    p = policy()
    v = report(p)
    target = v
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(RuntimeError):
        p["validate_runtime_report"](v)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("kind", "symlink"),
        ("uid", 1),
        ("gid", True),
        ("mode", 0o666),
        ("mode", 0o4644),
        ("bytes", 0),
        ("bytes", 16 * 1024 * 1024 + 1),
        ("bytes", True),
        ("owner", ["other", "x86_64"]),
        ("path", "/etc/other"),
        ("sha256", "wrong"),
        ("extra", 1),
    ],
)
def test_linker_cache_report_requires_exact_safe_facts(key, value):
    p = policy()
    v = report(p)
    v["linker_cache"]["after"][key] = value
    with pytest.raises(RuntimeError):
        p["validate_runtime_report"](v)


@pytest.mark.parametrize("bad", ["ok", "inode", "owner", "collision", "linkto", "header-digest"])
def test_native_mapping_builder_refuses_before_adding_unsafe_alias(monkeypatch, bad):
    p = policy()
    g = p["attest_lib64"].__globals__
    fake_digest = hashlib.sha256(b"public fake library").hexdigest()
    monkeypatch.setitem(g, "TIRPC_DIGEST", fake_digest)
    valid = report(p)["lib64"]["before"]
    monkeypatch.setitem(g, "read_alias_before", lambda: valid)
    monkeypatch.setitem(
        g, "stat_fact", lambda path: valid["alias" if path == "/lib64" else "target"]
    )
    monkeypatch.setattr(
        p["os"],
        "readlink",
        lambda path: (
            "usr/lib64" if path == "/lib64" else "bad" if bad == "linkto" else p["TIRPC_LINK"]
        ),
    )
    monkeypatch.setitem(
        g,
        "rpm",
        lambda *args: (
            "8\n"
            if args[-1] == "%{FILEDIGESTALGO}\n"
            else (
                "/lib64/libtirpc.so.3|120777||libtirpc.so.3.0.0\n/lib64/libtirpc.so.3.0.0|100755|"
                + ("0" * 64 if bad == "header-digest" else fake_digest)
                + "|\n"
            )
        ),
    )

    class FakePath:
        def __init__(self, name):
            self.name = name

        def lstat(self):
            link = self.name.endswith(".3")
            return SimpleNamespace(
                st_dev=1,
                st_ino=11 if bad == "inode" and self.name.startswith("/usr") else 10,
                st_uid=0,
                st_gid=0,
                st_mode=0o120777 if link else 0o100755,
            )

        def read_bytes(self):
            return b"public fake library"

    monkeypatch.setitem(g, "pathlib", SimpleNamespace(Path=FakePath))
    owned = {"/lib64/" + name: ("libtirpc", "x86_64") for name in p["TIRPC_NAMES"]}
    if bad == "owner":
        owned["/lib64/libtirpc.so.3"] = ("other", "x86_64")
    elif bad == "collision":
        owned["/usr/lib64/libtirpc.so.3"] = ("libtirpc", "x86_64")
    if bad == "ok":
        result = p["attest_lib64"](owned)
        assert set(result["nodes"]) == {"/usr/lib64/" + name for name in p["TIRPC_NAMES"]}
        assert all(owned[path] == ("libtirpc", "x86_64") for path in result["nodes"])
    else:
        with pytest.raises(RuntimeError):
            p["attest_lib64"](owned)


@pytest.mark.parametrize(
    ("exists", "action", "valid"),
    [
        (False, "A", True),
        (True, "C", True),
        (True, "A", False),
        (False, "C", False),
    ],
)
def test_cache_diff_action_must_match_real_previous_state(exists, action, valid):
    m = runpy.run_path(str(SOURCE.parents[1] / "docs/poc/oracle9_python_prepare.py"))
    cache = report(policy())["linker_cache"]
    if exists:
        cache["before"] = {"kind": "regular", "sha256": "b" * 64}
    v = {"directories": [], "linker_cache": cache}
    if valid:
        m["validate_diff"]((action + " /etc/ld.so.cache\n").encode(), v)
    else:
        with pytest.raises(RuntimeError):
            m["validate_diff"]((action + " /etc/ld.so.cache\n").encode(), v)
