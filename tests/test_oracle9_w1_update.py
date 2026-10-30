"""Native payload logic with public fixtures/fake effects, no pip or container."""

import ast
import base64
import hashlib
import json
import runpy
import zlib
from copy import deepcopy
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "deploy/oracle9_w1_update.py"


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(SOURCE))


@pytest.fixture
def inputs(module: Any) -> Any:
    origin, core = module["libraries"]()
    manifest = json.loads(
        (REPO / "docs/poc/evidence/oracle9-w1-context-manifest-20261027.json").read_bytes()
    )
    old = json.loads(
        (REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json").read_bytes()
    )
    return origin, core, manifest, old


def test_captured_libraries_have_exact_hash_and_deep_filenames(module):
    origin, core = module["libraries"]()
    assert origin["__file__"] == "/opt/maskgw/lab/origin.py"
    assert core["__file__"] == "/opt/maskgw/lab/context.py"
    assert origin["verify_install"].__code__.co_filename == origin["__file__"]
    assert core["check_delta"].__code__.co_filename == core["__file__"]
    assert core["WHEEL_SHA"] == "6b63f239fadbc051f8fa850a96b69fbebba4f6b3eb12d3a12e49a9313429877b"


@pytest.mark.parametrize("fault", ["hash", "tail", "truncated", "expanded", "role"])
def test_thaw_refuses_before_exec(module, fault):
    raw = b"raise AssertionError('MUST_NOT_EXECUTE')"
    if fault == "expanded":
        raw = b"#" * 65537
    compressed = zlib.compress(raw)
    if fault == "tail":
        compressed += b"tail"
    if fault == "truncated":
        compressed = compressed[:-1]
    blob = base64.b64encode(compressed).decode()
    expected = "0" * 64 if fault == "hash" else hashlib.sha256(raw).hexdigest()
    with pytest.raises(module["UpdateRefusal"]):
        module["thaw"](blob, expected, "unknown" if fault == "role" else "context")


def test_closed_manifest_derives_same_target_from_old_not_copied_dependency_claims(module, inputs):
    _, core, manifest, old = inputs
    target, own = module["validate_manifest"](manifest, old, core)
    assert len(target["installed_files"]) == 1387 and len(own) == 127
    assert manifest["app_wheel_sha256"] == core["WHEEL_SHA"]


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("extra", "MANIFEST"),
        ("image", "MANIFEST_ID"),
        ("wheel", "MANIFEST_ID"),
        ("size_bool", "MANIFEST_ID"),
        ("delta", "TARGET"),
        ("other_owner", "TARGET"),
        ("rewrite", "ROW"),
        ("source_count", "SOURCE_MANIFEST"),
    ],
)
def test_manifest_mutations_cannot_weaken_native_verification(module, inputs, fault, reason):
    _, core, manifest, old = inputs
    if fault == "extra":
        manifest["extra"] = True
    elif fault == "image":
        manifest["base_image"] = "sha256:" + "0" * 64
    elif fault == "wheel":
        manifest["app_wheel_sha256"] = "0" * 64
    elif fault == "size_bool":
        manifest["app_wheel_bytes"] = True
    elif fault == "delta":
        manifest["delta"]["removed"] = ["maskgw/__init__.py"]
    elif fault == "other_owner":
        key = next(
            k for k, v in manifest["target"]["installed_files"].items() if v["owner"] != "maskgw"
        )
        manifest["target"]["installed_files"][key]["sha256"] = "0" * 64
    elif fault == "rewrite":
        manifest["target"]["installed_files"]["maskgw/db/postgres.py"]["rewritten_record"] = True
    else:
        manifest["source_manifest"].pop()
    with pytest.raises(module["UpdateRefusal"], match=rf"^{reason}$"):
        module["validate_manifest"](manifest, old, core)


def test_w1_imports_check_installed_path_and_exact_bytes_without_app_import(
    module, inputs, tmp_path, monkeypatch
):
    _, _, manifest, _ = inputs
    site = tmp_path / "site"
    globals_ = module["w1_imports"].__globals__
    monkeypatch.setitem(globals_, "SITE", site)
    modules = {}
    for name in module["W1_MODULES"]:
        relative = name.replace(".", "/") + ".py"
        path = site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO / "src" / relative).read_bytes())
        modules[name] = SimpleNamespace(__file__=str(path))
    calls = []

    def fake_import(name):
        calls.append(name)
        return modules[name]

    monkeypatch.setitem(globals_, "importlib", SimpleNamespace(import_module=fake_import))
    monkeypatch.setitem(
        globals_, "sys", SimpleNamespace(modules={"maskgw.db.session_state": object()})
    )
    fake_origin = {"read_regular": lambda path, _limit: path.read_bytes()}
    result = module["w1_imports"](fake_origin, manifest["target"]["installed_files"])
    assert calls == list(module["W1_MODULES"]) and len(result["modules"]) == 5
    assert result["preloaded"] == ["maskgw.db.session_state"]
    path.write_bytes(b"changed")
    with pytest.raises(module["UpdateRefusal"], match=r"^W1_MODULE$"):
        module["w1_imports"](fake_origin, manifest["target"]["installed_files"])


class InputPath:
    def __init__(self, name: str = "root", events: list[str] | None = None) -> None:
        self.name = name
        self.events = [] if events is None else events

    def __truediv__(self, other):
        return InputPath(self.name + "/" + other, self.events)

    def __str__(self) -> str:
        return self.name

    def unlink(self):
        self.events.append("unlink:" + self.name)

    def rmdir(self):
        self.events.append("rmdir:" + self.name)

    def exists(self):
        return False


def modeled_prefix(old: Any, target: Any) -> Any:
    before = deepcopy(old["installed_snapshot"])
    after = deepcopy(before)
    for name, item in target["installed_files"].items():
        if item["owner"] != "maskgw":
            continue
        path = "lib/python3.11/site-packages/" + name
        row = dict(after.get(path, {"kind": "file", "mode": 0o644, "uid": 0, "gid": 0}))
        row.update(bytes=item["bytes"], sha256=item["sha256"])
        if item["rewritten_record"]:
            row.update(bytes=12345, sha256=hashlib.sha256(b"MODEL_RECORD_ONLY").hexdigest())
        after[path] = row
    return before, after


@pytest.mark.parametrize("fault", ["none", "other_owner", "record", "native", "imports", "cleanup"])
def test_install_order_exact_flags_and_probe_reads_only_new_attestation(  # noqa: PLR0915 - explicit effect/failure matrix and post-probe
    module, inputs, monkeypatch, fault
):
    _, core, manifest, old = inputs
    globals_ = module["install"].__globals__
    before, after = modeled_prefix(old, manifest["target"])
    events: list[Any] = []
    attestation: dict[str, bytes] = {}

    def pip(args, label):
        events.append((label, args))
        return {"exit": 0}

    scans = iter([before, after, after])

    def profile(probe):
        events.append(("profile", probe))
        return {"MODEL": True}

    def verify(_target, _base, _snapshot):
        events.append("verify")
        if fault == "record" and events.count("verify") == 2:
            raise RuntimeError("MODEL_INVALID_RECORD")
        return old["versions"]

    fake = {
        "runtime_profile": profile,
        "parent_environment": lambda: events.append("environment"),
        "scan_prefix": lambda: next(scans),
        "verify_install": verify,
        "base_pth": lambda: old["base_pth"],
        "run_pip": pip,
        "imports_and_native": lambda: {} if fault == "native" else old["native"],
        "write_new": lambda _path, raw: attestation.update(new=raw),
    }
    monkeypatch.setitem(
        globals_,
        "os",
        SimpleNamespace(getpid=lambda: 1, umask=lambda value: events.append(("umask", value))),
    )
    monkeypatch.setitem(globals_, "ATTEST", InputPath("new-attestation"))
    monkeypatch.setitem(globals_, "read_old", lambda _: old)
    loads = []

    def load(*_args):
        loads.append(True)
        if fault == "cleanup" and len(loads) == 2:
            raise module["UpdateRefusal"]("MANIFEST")
        return manifest, old, {}

    monkeypatch.setitem(globals_, "load_context", load)

    def imports(*_args):
        if fault == "imports":
            raise module["UpdateRefusal"]("W1_MODULE")
        return {"MODEL": "no import executed"}

    monkeypatch.setitem(globals_, "w1_imports", imports)
    monkeypatch.setitem(
        globals_,
        "importlib",
        SimpleNamespace(invalidate_caches=lambda: events.append("invalidate")),
    )
    root = InputPath()
    if fault == "other_owner":
        after["lib64"]["target"] = "unexpected"
    if fault != "none":
        with pytest.raises(RuntimeError):
            module["install"](root, fake, core)
        assert bool(attestation) is (fault == "cleanup")
        assert root.events == []
        assert len([e for e in events if isinstance(e, tuple) and e[0] == "pip-install"]) == 1
        return
    result = module["install"](root, fake, core)
    assert result["outcome"] == "W1_APP_UPDATE_VERIFIED" and result["prefix_paths"] == 3337
    assert events.index(("umask", 0o022)) < events.index("verify")
    assert events.index("invalidate") > next(
        i for i, e in enumerate(events) if isinstance(e, tuple) and e[0] == "pip-install"
    )
    # Find only actual pip tuples; other events deliberately differ in shape.
    install_args = next(e[1] for e in events if isinstance(e, tuple) and e[0] == "pip-install")
    assert install_args == [
        "install",
        "--no-input",
        "--no-index",
        "--no-deps",
        "--require-hashes",
        "--only-binary=:all:",
        "--no-compile",
        "--no-cache-dir",
        "--force-reinstall",
        "--find-links",
        "root/wheels",
        "-r",
        "root/requirements.lock",
    ]
    assert len(loads) == 2 and events.count("verify") == 2
    assert root.events == [
        "unlink:root/wheels/" + core["WHEEL_NAME"],
        "rmdir:root/wheels",
        "unlink:root/requirements.lock",
        "unlink:root/manifest.json",
        "rmdir:root",
    ]
    assert hashlib.sha256(attestation["new"]).hexdigest() == result["attestation_sha256"]
    read_paths = []
    fake["scan_prefix"] = lambda: after

    def read_new(path, _limit):
        read_paths.append(str(path))
        return attestation["new"]

    fake["read_regular"] = read_new
    probe = module["probe"](result["attestation_sha256"], fake, core)
    assert probe["outcome"] == "W1_APP_PROBE_VERIFIED" and read_paths == ["new-attestation"]
    assert events.count("verify") == 3


def test_prefix_mismatch_before_pip_never_attests_or_installs(module, inputs, monkeypatch):
    _, core, manifest, old = inputs
    globals_ = module["install"].__globals__

    def forbidden(*_args):
        raise AssertionError("NO_PIP_OR_ATTEST")

    fake = {
        "runtime_profile": lambda _: {"MODEL": True},
        "parent_environment": lambda: None,
        "scan_prefix": lambda: {},
        "run_pip": forbidden,
        "write_new": forbidden,
    }
    monkeypatch.setitem(globals_, "os", SimpleNamespace(getpid=lambda: 1, umask=lambda _: None))
    monkeypatch.setitem(globals_, "ATTEST", InputPath("new-attestation"))
    monkeypatch.setitem(globals_, "load_context", lambda *_: (manifest, old, {}))
    with pytest.raises(module["UpdateRefusal"], match=r"^PREFIX_BEFORE$"):
        module["install"](InputPath(), fake, core)


def test_origin_attestation_read_hash_before_using_metadata(module, inputs, tmp_path):
    origin, _, _, old = inputs
    path = tmp_path / "old.json"
    raw = (REPO / "docs/poc/evidence/oracle9-installed-attestation-20261026.json").read_bytes()
    path.write_bytes(raw)
    origin["ATTEST"] = path
    assert module["read_old"](origin) == old
    path.write_bytes(raw + b" ")
    with pytest.raises(module["UpdateRefusal"], match=r"^ORIGIN_ATTEST$"):
        module["read_old"](origin)


@pytest.mark.parametrize("bad_owner", [False, True])
def test_load_context_native_owner_and_inventory_contract_with_fake_paths(
    module, inputs, monkeypatch, bad_owner
):
    _, core, manifest, old = inputs
    raw = (REPO / "docs/poc/evidence/oracle9-w1-context-manifest-20261027.json").read_bytes()
    events: list[Any] = []
    root_name = "/opt/maskgw/w1-inputs-" + "a" * 32

    class FakePath:
        def __init__(self, path: str) -> None:
            self.path = PurePosixPath(path)

        def __str__(self):
            return str(self.path)

        def __truediv__(self, value):
            return FakePath(str(self.path / value))

        def relative_to(self, other):
            return self.path.relative_to(other.path)

        def lstat(self):
            is_dir = str(self) in (root_name, root_name + "/wheels")
            return SimpleNamespace(
                st_uid=int(bad_owner), st_gid=0, st_mode=(0o040755 if is_dir else 0o100644)
            )

    globals_ = module["load_context"].__globals__
    monkeypatch.setitem(globals_, "Path", FakePath)
    monkeypatch.setitem(
        globals_, "os", SimpleNamespace(chmod=lambda path, mode: events.append((str(path), mode)))
    )
    monkeypatch.setitem(globals_, "read_old", lambda _: old)
    fake_origin = {"read_regular": lambda *_: raw}

    def check(_root, data):
        assert data == raw
        events.append("context-checked")

    fake_core = dict(core, check_context=check)
    if bad_owner:
        with pytest.raises(module["UpdateRefusal"], match=r"^INPUT_OWNER$"):
            module["load_context"](FakePath(root_name), fake_origin, fake_core)
        assert events == ["context-checked"]
    else:
        value, original, modes = module["load_context"](FakePath(root_name), fake_origin, fake_core)
        assert value == manifest and original == old and len(modes) == 5
        assert len(events) == 6 and events[0] == "context-checked"


def test_probe_bad_new_hash_never_falls_back_to_old(module):
    paths = []

    def read(path, _limit):
        paths.append(str(path))
        return b"MODEL_BAD_ATTEST"

    fake = {
        "runtime_profile": lambda _: {"MODEL": True},
        "parent_environment": lambda: None,
        "read_regular": read,
    }
    with pytest.raises(module["UpdateRefusal"], match=r"^ATTEST_HASH$"):
        module["probe"]("0" * 64, fake, {})
    assert paths == [str(module["ATTEST"])]


@pytest.mark.parametrize("kind", ["origin", "context"])
def test_known_reused_refusal_keeps_closed_reason(module, inputs, kind):
    _, core, _, _ = inputs
    error = (
        RuntimeError("RECORD_HASH")
        if kind == "origin"
        else core["ContextRefusal"]("OTHER_OWNER_CHANGED")
    )
    assert module["failure_metadata"](error)["reason"] == (
        "RECORD_HASH" if kind == "origin" else "OTHER_OWNER_CHANGED"
    )


def test_probe_embedded_manifest_bound_before_scan(module, inputs):
    _, _, manifest, _ = inputs
    manifest["base_image"] = "different"
    raw = (
        json.dumps(
            {
                "kind": "oracle9-w1-installed-v1",
                "context_manifest_sha256": module["MANIFEST_SHA"],
                "origin_attestation_sha256": module["OLD_ATTEST_SHA"],
                "manifest": manifest,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()

    def forbidden():
        raise AssertionError("DO_NOT_SCAN_UNBOUND_TARGET")

    fake = {
        "runtime_profile": lambda _: {},
        "parent_environment": lambda: None,
        "read_regular": lambda *_: raw,
        "scan_prefix": forbidden,
    }
    with pytest.raises(module["UpdateRefusal"], match=r"^MANIFEST$"):
        module["probe"](hashlib.sha256(raw).hexdigest(), fake, {})


def test_origin_category_table_exactly_matches_frozen_need_literals(module):
    raw = zlib.decompress(base64.b64decode(module["ORIGIN_BLOB"]))
    assert hashlib.sha256(raw).hexdigest() == module["ORIGIN_SHA"]
    expected = {
        n.args[1].value
        for n in ast.walk(ast.parse(raw))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "need"
        and len(n.args) == 2
        and isinstance(n.args[1], ast.Constant)
        and type(n.args[1].value) is str
    }
    assert module["_ORIGIN_REASONS"] == expected


def test_failure_metadata_never_stringifies_or_leaks_unknown_error(module, inputs):
    _, core, _, _ = inputs

    class NeverStringify:
        def __str__(self):
            raise AssertionError("MUST_NOT_STRINGIFY")

    class DerivedError(RuntimeError):
        pass

    for error in (
        RuntimeError("PUBLIC_UNKNOWN_NOT_SERIALIZED"),
        RuntimeError(NeverStringify()),
        DerivedError("RECORD_HASH"),
        ExceptionGroup("PUBLIC_GROUP", [RuntimeError("RECORD_HASH")]),
    ):
        value = module["failure_metadata"](error)
        assert value["reason"] is None and "PUBLIC_" not in json.dumps(value)
    invalid = core["ContextRefusal"]("STATE")
    invalid.category = "PUBLIC_UNKNOWN_NOT_SERIALIZED"
    assert module["failure_metadata"](invalid)["reason"] is None


@pytest.mark.parametrize("fault", ["platform", "isolated", "bytecode", "optimize", "argc"])
def test_entry_refuses_before_libraries_or_any_effect(module, monkeypatch, fault):
    globals_ = module["main"].__globals__

    def forbidden():
        raise AssertionError("NO_LIBRARY_OR_EFFECT")

    monkeypatch.setitem(globals_, "libraries", forbidden)
    flags = SimpleNamespace(
        isolated=int(fault != "isolated"),
        dont_write_bytecode=int(fault != "bytecode"),
        optimize=int(fault == "optimize"),
    )
    monkeypatch.setitem(
        globals_,
        "sys",
        SimpleNamespace(
            platform="win32" if fault == "platform" else "linux",
            flags=flags,
            argv=["payload"] if fault == "argc" else ["payload", "probe", "0" * 64],
        ),
    )
    with pytest.raises(module["UpdateRefusal"]):
        module["main"]()
