"""Pure policy and fake-stat cache cases; no POSIX/runtime certification."""

import json
import runpy
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "deploy/oracle9_python_payload.py"


def policy() -> dict[str, Any]:
    return runpy.run_path(str(SOURCE))


def facts(p: dict[str, Any]) -> dict[str, Any]:
    return {
        path: {"kind": "directory", "symlink": False, "uid": 0, "gid": 0, "mode": 0o755}
        for path in p["RESTORED_DIRS"]
    }


def baseline(p: dict[str, Any]) -> str:
    return "".join("missing     " + path + "\n" for path in p["RESTORED_DIRS"])


def test_only_exact_observed_directory_restoration_can_pass():
    p = policy()
    v = p["compare_verification"](baseline(p), "", facts(p))
    assert v["base_verify_accepted"] is True and v["base_verify_unchanged"] is False
    assert v["restored_directories"] == list(p["RESTORED_DIRS"])
    v["aux_cache"] = {"action": "absent"}
    p["validate_verification_report"](v)
    same = p["compare_verification"]("same\n", "same\n")
    assert same["base_verify_unchanged"] is True and same["restored_directories"] == []
    same["aux_cache"] = {"action": "absent"}
    p["validate_verification_report"](same)


@pytest.mark.parametrize(
    "variant", ["spacing", "config-marker", "extra", "duplicate", "new-error", "subset"]
)
def test_other_differences_are_not_called_directory_restoration(variant):
    p = policy()
    before, after = baseline(p), ""
    if variant == "spacing":
        before = before.replace("missing     ", "missing    ")
    elif variant == "config-marker":
        before = before.replace("missing     ", "missing   c ")
    elif variant == "extra":
        before += "missing     /etc/secret\n"
    elif variant == "duplicate":
        before += before.splitlines()[0] + "\n"
    elif variant == "new-error":
        after = "S.5....T. /usr/bin/python3.11\n"
    else:
        after = before.splitlines()[0] + "\n"
    with pytest.raises(RuntimeError):
        p["compare_verification"](before, after, facts(p))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("kind", "regular"),
        ("symlink", True),
        ("uid", 10001),
        ("gid", 1),
        ("uid", False),
        ("mode", True),
        ("mode", 0o777),
        ("mode", 0o4755),
        ("mode", 0o1755),
        ("mode", 0o400),
    ],
)
def test_missing_or_unsafe_directory_proof_refuses(key, value):
    p = policy()
    f = facts(p)
    f[p["RESTORED_DIRS"][0]][key] = value
    with pytest.raises(RuntimeError):
        p["compare_verification"](baseline(p), "", f)
    with pytest.raises(RuntimeError):
        p["compare_verification"](baseline(p), "", None)


@pytest.mark.parametrize("bad", ["unchanged", "accepted", "list", "facts", "policy"])
def test_report_never_claims_restoration_was_unchanged(bad):
    p = policy()
    v = p["compare_verification"](baseline(p), "", facts(p))
    v["aux_cache"] = {"action": "absent"}
    if bad == "unchanged":
        v["base_verify_unchanged"] = True
    elif bad == "accepted":
        v["base_verify_accepted"] = False
    elif bad == "list":
        v["restored_directories"] = []
    elif bad == "facts":
        v["restored_directory_facts"] = {}
    else:
        v["verification_policy"] = "generic-improvements"
    with pytest.raises(RuntimeError):
        p["validate_verification_report"](v)


def cache_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner: str
) -> tuple[dict[str, Any], Path, SimpleNamespace]:
    p = policy()
    target = tmp_path / "cache" / "aux-cache"
    target.parent.mkdir()
    target.write_bytes(b"public fake cache")
    (tmp_path / "cache-dir-before.txt").write_bytes(b"absent\n")
    g = p["handle_aux_cache"].__globals__
    monkeypatch.setitem(g, "AUX_CACHE", target)
    monkeypatch.setitem(g, "ROOT", tmp_path)
    native = type(target).lstat
    fake = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600, st_uid=0, st_gid=0, st_size=target.stat().st_size
    )
    monkeypatch.setattr(
        type(target), "lstat", lambda self: fake if self == target else native(self)
    )
    stdout = (
        b"glibc|x86_64\n"
        if owner == "glibc"
        else f"file {target} is not owned by any package\n".encode()
    )
    if owner == "other":
        stdout = b"other|x86_64\n"
    proc = SimpleNamespace(returncode=1 if owner == "unowned" else 0, stdout=stdout, stderr=b"")
    monkeypatch.setattr(p["subprocess"], "run", lambda *_, **_kw: proc)
    return p, target, proc


@pytest.mark.parametrize("owner", ["glibc", "unowned"])
def test_only_known_cache_owner_or_proven_new_unowned_file_is_handled(tmp_path, monkeypatch, owner):
    p, target, _ = cache_case(tmp_path, monkeypatch, owner)
    value = p["handle_aux_cache"](baseline(p), facts(p))
    assert value["action"] == ("retained-base-glibc" if owner == "glibc" else "removed-unowned")
    assert target.exists() is (owner == "glibc")
    v = p["compare_verification"](baseline(p), "", facts(p))
    v["aux_cache"] = value
    p["validate_verification_report"](v)


@pytest.mark.parametrize("bad", ["other-owner", "stderr", "preexisting-dir", "extra-file"])
def test_cache_failure_never_deletes_unknown_or_preexisting_data(tmp_path, monkeypatch, bad):
    p, target, proc = cache_case(
        tmp_path, monkeypatch, "other" if bad == "other-owner" else "unowned"
    )
    if bad == "stderr":
        proc.stderr = b"public error"
    elif bad == "preexisting-dir":
        (tmp_path / "cache-dir-before.txt").write_bytes(b"present\n")
    elif bad == "extra-file":
        (target.parent / "keep-me").write_bytes(b"unknown")
    with pytest.raises(RuntimeError):
        p["handle_aux_cache"](baseline(p), facts(p))
    assert target.read_bytes() == b"public fake cache"


def test_missing_directory_preserves_rpm_delta_diagnostic(monkeypatch, capsys):
    p = policy()
    g = p["directory_facts"].__globals__

    class FakePath:
        def __init__(self, name):
            self.name = name

        def lstat(self):
            if self.name == "/usr/share/man/man1":
                raise FileNotFoundError
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)

    monkeypatch.setitem(g, "pathlib", SimpleNamespace(Path=FakePath))
    observed = p["directory_facts"]()
    assert observed["/usr/share/man/man1"] == {"kind": "absent"}
    with pytest.raises(RuntimeError):
        p["compare_verification"](baseline(p), "missing     /usr/share/man/man1\n", observed)
    assert "@@RPM_VERIFY_DIFF@@" in capsys.readouterr().out


def test_cache_check_does_not_require_unrelated_man_directories(tmp_path, monkeypatch):
    p, target, _ = cache_case(tmp_path, monkeypatch, "glibc")
    observed = facts(p)
    observed["/usr/share/man/man1"] = {"kind": "absent"}
    assert p["handle_aux_cache"](baseline(p), observed)["action"] == "retained-base-glibc"
    assert target.exists()


def test_absent_cache_directory_requires_no_filesystem_query(monkeypatch):
    p = policy()
    observed = facts(p)
    observed["/var/cache/ldconfig"] = {"kind": "absent"}
    g = p["handle_aux_cache"].__globals__
    monkeypatch.setitem(g, "AUX_CACHE", None)
    assert p["handle_aux_cache"](baseline(p), observed) == {"action": "absent"}


def test_unowned_diagnostic_is_bounded_and_never_accepts(capsys):
    p = policy()
    unknown = ["/usr/" + "x" * 600 + str(i) for i in range(45)]
    with pytest.raises(RuntimeError):
        p["require_owned_new_paths"](unknown)
    line = capsys.readouterr().out.strip()
    assert line.startswith("@@RPM_UNOWNED_NEW@@")
    value = json.loads(line.removeprefix("@@RPM_UNOWNED_NEW@@"))
    assert value["count"] == 45 and len(value["paths"]) == 40
    assert all(len(path) == 512 for path in value["paths"])
    assert len(value["paths_sha256"]) == 64
    p["require_owned_new_paths"]([])
    assert capsys.readouterr().out == ""
