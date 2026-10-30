"""Pure import-lab preparation tests: no network, pip install or native import."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import stat
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "docs/poc/prepare_linux_imports.py"
SPEC = importlib.util.spec_from_file_location("imports_preparation", SOURCE)
assert SPEC is not None and SPEC.loader is not None
PREP: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)


def metadata(filename: str) -> dict[str, Any]:
    return {
        "info": {"name": "annotated-types", "version": "0.8.0"},
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "yanked": False,
                "filename": filename,
                "url": "https://files.pythonhosted.org/packages/fixture/" + filename,
                "digests": {"sha256": "a" * 64},
                "size": 100,
            }
        ],
    }


def test_only_pinned_compatible_wheel_is_selected():
    data = metadata("annotated_types-0.8.0-py3-none-any.whl")
    chosen = PREP.choose_wheel(data, "annotated-types", "0.8.0")
    assert chosen["filename"] == data["urls"][0]["filename"]
    assert chosen["size"] == 100 and chosen["sha256"] == "a" * 64


@pytest.mark.parametrize(
    "filename",
    [
        "annotated_types-0.8.0-cp311-cp311-win_amd64.whl",
        "annotated_types-0.8.0-cp311-cp311-musllinux_1_2_x86_64.whl",
        "annotated_types-0.8.0-cp312-cp312-manylinux_2_34_x86_64.whl",
        "annotated_types-0.8.0-cp311-cp311-manylinux_2_37_x86_64.whl",
        "annotated_types-0.8.0-cp311-cp311-manylinux_2_34_aarch64.whl",
    ],
)
def test_incompatible_or_unknown_platform_is_not_downloadable(filename):
    with pytest.raises(PREP.PreparationError):
        PREP.choose_wheel(metadata(filename), "annotated-types", "0.8.0")


@pytest.mark.parametrize(
    "url",
    [
        "http://files.pythonhosted.org/x",
        "https://pypi.org/x",
        "https://files.pythonhosted.org.evil.invalid/x",
        "https://u:p@files.pythonhosted.org/x",
        "https://files.pythonhosted.org/x?token=hidden",
        "https://files.pythonhosted.org:8443/x",
    ],
)
def test_foreign_cleartext_credential_or_nonstandard_origin_is_refused(url):
    with pytest.raises(PREP.PreparationError):
        PREP.url_allowed(url, "files.pythonhosted.org")


def test_redirect_and_implicit_proxy_are_refused(monkeypatch):
    def forbidden_proxy_lookup():
        raise AssertionError("must not consult environment/Windows proxy registry")

    monkeypatch.setattr(urllib.request, "getproxies", forbidden_proxy_lookup)
    PREP.network_opener()  # builds handlers, does not perform any request
    with pytest.raises(PREP.PreparationError):
        PREP.NoRedirect().redirect_request(
            None, None, None, None, None, "https://elsewhere.invalid"
        )


@pytest.mark.parametrize(
    "size,sha,category", [(2, "a" * 64, "DOWNLOAD_LIMIT"), (3, "a" * 64, "DOWNLOAD_INTEGRITY")]
)
def test_streaming_download_refuses_oversize_or_bad_hash(tmp_path, size, sha, category):
    class Response:
        def __init__(self) -> None:
            self.parts = iter([b"abc", b""])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self):
            return "https://files.pythonhosted.org/x"

        def read(self, _size):
            return next(self.parts)

    opener = type("Opener", (), {"open": lambda *_args, **_kwargs: Response()})()
    target = tmp_path / "download.whl"
    with pytest.raises(PREP.PreparationError) as caught:
        PREP.download_one(
            opener,
            {"url": "https://files.pythonhosted.org/x", "size": size, "sha256": sha},
            target,
            float("inf"),
        )
    assert caught.value.category == category and not target.exists()


def wheel(path: Path, extra: Sequence[tuple[str | zipfile.ZipInfo, bytes]]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("fixture-1.dist-info/METADATA", b"Name: fixture\nVersion: 1\n")
        archive.writestr("fixture-1.dist-info/WHEEL", b"Wheel-Version: 1.0\nTag: py3-none-any\n")
        for name, data in extra:
            if isinstance(name, str):
                entry = zipfile.ZipInfo("placeholder")
                entry.filename = name  # preserve malicious backslash on Windows too
                archive.writestr(entry, data)
            else:
                archive.writestr(name, data)
    return path


@pytest.mark.parametrize("name", ["../escape.py", "/escape.py", "x\\escape.py", "x.pth"])
def test_archive_paths_are_checked_before_install(tmp_path, name):
    source = wheel(tmp_path / "fixture-1-py3-none-any.whl", [(name, b"x")])
    with pytest.raises(PREP.PreparationError):
        PREP.wheel_details(source)


def test_archive_links_and_case_collisions_are_rejected(tmp_path):
    link = zipfile.ZipInfo("fixture/link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    for entries in ([(link, b"target")], [("fixture/A.py", b"x"), ("fixture/a.py", b"x")]):
        source = wheel(tmp_path / "fixture-1-py3-none-any.whl", entries)
        with pytest.raises(PREP.PreparationError):
            PREP.wheel_details(source)


def test_requires_dist_evaluates_linux_markers_and_binary_extra():
    details: list[dict[str, Any]] = [
        {"name": "maskgw", "version": "0.1.0", "requires": ["psycopg[binary]>=3", "mcp>=2"]},
        {
            "name": "psycopg",
            "version": "3.3.4",
            "requires": ["tzdata; sys_platform=='win32'", "psycopg-binary==3.3.4; extra=='binary'"],
        },
        {"name": "psycopg-binary", "version": "3.3.4", "requires": []},
    ]
    assert PREP.check_dependencies(details) == ["mcp"]
    with pytest.raises(PREP.PreparationError):
        PREP.check_dependencies(details[:-1])
    details[1]["requires"].append("unexpected>=1")
    with pytest.raises(PREP.PreparationError):
        PREP.check_dependencies(details)


def test_requires_dist_exceptions_only_belong_to_product():
    with pytest.raises(PREP.PreparationError):
        PREP.check_dependencies([{"name": "other", "version": "1", "requires": ["mcp>=2"]}])


def tree(tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "installed"
    (target / "fixture-1.dist-info").mkdir(parents=True)
    module = target / "fixture.py"
    module.write_bytes(b"fixture")
    digest = base64.urlsafe_b64encode(hashlib.sha256(b"fixture").digest()).decode().rstrip("=")
    record = target / "fixture-1.dist-info/RECORD"
    record.write_text(
        f"fixture.py,sha256={digest},7\nfixture-1.dist-info/RECORD,,\n", encoding="ascii"
    )
    return target, module


def test_target_bytes_checked_against_record_and_unlisted_files_refused(tmp_path):
    target, module = tree(tmp_path)
    report = PREP.verify_tree(target, set())
    assert report["file_count"] == 2
    module.write_bytes(b"changed")
    with pytest.raises(PREP.PreparationError):
        PREP.verify_tree(target, set())
    module.write_bytes(b"fixture")
    (target / "extra.py").write_bytes(b"extra")
    with pytest.raises(PREP.PreparationError):
        PREP.verify_tree(target, set())


def test_unsafe_record_path_never_reads_outside_target(tmp_path):
    target, _module = tree(tmp_path)
    (target / "fixture-1.dist-info/RECORD").write_text("../outside.py,,\n", encoding="ascii")
    with pytest.raises(PREP.PreparationError):
        PREP.verify_tree(target, set())


def test_no_external_action_on_import_and_no_implicit_index_configuration():
    assert PREP.PINS["maskgw"] == "0.1.0"
    data = json.loads(json.dumps(PREP.PINS))
    assert data == PREP.PINS
    assert "--require-hashes" in SOURCE.read_text(encoding="utf-8")


def test_artifact_root_cannot_be_inside_or_above_checkout(tmp_path):
    checkout = tmp_path / "repo"
    for root in (
        checkout / "maskgw-linux-imports-x",
        checkout,
        tmp_path / "maskgw-linux-imports-parent",
    ):
        repository = root / "repo" if root.name == "maskgw-linux-imports-parent" else checkout
        with pytest.raises(PREP.PreparationError):
            PREP.check_placement(root, repository)
    PREP.check_placement(tmp_path / "maskgw-linux-imports-external", checkout)


def test_cross_wheel_collision_and_declared_size_cap():
    details: list[dict[str, Any]] = [
        {"name": name, "version": version, "declared_bytes": 1, "members": [name + ".py"]}
        for name, version in PREP.PINS.items()
    ]
    PREP.validate_wheelhouse(details)
    details[1]["members"] = details[0]["members"]
    with pytest.raises(PREP.PreparationError):
        PREP.validate_wheelhouse(details)
    details[1]["members"] = ["unique.py"]
    details[0]["declared_bytes"] = PREP.ZIP_CAP
    with pytest.raises(PREP.PreparationError):
        PREP.validate_wheelhouse(details)


def test_relocated_launcher_is_verified_by_exact_allowlist(tmp_path):
    target, _module = tree(tmp_path)
    (target / "bin").mkdir()
    launcher = target / "bin/pgpp"
    launcher.write_bytes(b"fixture")
    digest = base64.urlsafe_b64encode(hashlib.sha256(b"fixture").digest()).decode().rstrip("=")
    record = target / "fixture-1.dist-info/RECORD"
    with record.open("a", encoding="ascii") as handle:
        handle.write(f"../../bin/pgpp,sha256={digest},7\n")
    assert PREP.verify_tree(target, {"bin/pgpp"})["file_count"] == 3
    with pytest.raises(PREP.PreparationError):
        PREP.verify_tree(target, set())
