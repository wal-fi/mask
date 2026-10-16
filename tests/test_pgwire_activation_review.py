"""Independent counterproofs for the narrowly authorized main activation."""

from __future__ import annotations

import io
import secrets
from pathlib import Path
from typing import cast

import pytest

import maskgw.bootstrap.main as process
from maskgw.bootstrap.application import Application
from maskgw.bootstrap.settings import MappingRawSettings
from maskgw.runtime.datasource_service import DatasourceCatalogSettings


class _Listener:
    @property
    def port(self) -> int:
        return 6432


class _Application:
    revision = 0
    admin_http = None

    def __init__(self) -> None:
        self.runs = 0
        self.closes = 0
        self.pgwire_listener = _Listener()

    def run(self) -> None:
        self.runs += 1

    def close(self) -> None:
        self.closes += 1


def _activation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app: _Application
) -> MappingRawSettings:
    config = tmp_path / "custom" / "masking.yaml"
    config.parent.mkdir()
    store = config.parent / "datasources.store"
    store.write_bytes(b"not parsed by the composition double")
    anchor = store.parent / ".maskgw-anchor" / "datasources.anchor"
    anchor.parent.mkdir()
    anchor.write_bytes(b"not parsed by the composition double")
    monkeypatch.setenv("MASKGW_CONFIG", str(config))
    monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "0")
    monkeypatch.setenv("MASKGW_PGWIRE_PASSWORD", secrets.token_urlsafe(24))
    monkeypatch.setattr(process, "build_application", lambda **_kwargs: cast(Application, app))
    return MappingRawSettings(
        {"MASKGW_PGWIRE_ENABLED": "1", "MASKGW_PGWIRE_USERNAME": "review-user"}
    )


def test_valid_activation_reaches_composition_and_closes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)
    sink = io.StringIO()
    assert process.main(stderr=sink, raw_settings=raw) == 0
    assert (app.runs, app.closes) == (1, 1)
    assert sink.getvalue() == (
        f"{process.REVISION_LOADED_PREFIX}0\nmaskgw: pgwire escutando em 127.0.0.1:6432\n"
    )


def test_listener_metadata_failure_and_failed_close_never_escape_raw(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)

    def bad_port(_listener: _Listener) -> int:
        raise OSError("review-private-listener-marker")

    def bad_close() -> None:
        app.closes += 1
        raise OSError("review-private-close-marker")

    monkeypatch.setattr(_Listener, "port", property(bad_port))
    monkeypatch.setattr(app, "close", bad_close)
    sink = io.StringIO()
    assert process.main(stderr=sink, raw_settings=raw) == 1
    assert sink.getvalue() == process.STARTUP_FAILURE
    assert (app.runs, app.closes) == (0, 1)


@pytest.mark.parametrize("fail_at", ["revision", "listener"])
def test_metadata_output_failure_cannot_skip_application_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail_at: str
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)

    class FailsOnce(io.StringIO):
        failed = False

        def write(self, value: str) -> int:
            prefix = (
                process.REVISION_LOADED_PREFIX
                if fail_at == "revision"
                else "maskgw: pgwire escutando"
            )
            if not self.failed and value.startswith(prefix):
                self.failed = True
                raise OSError("review-private-stderr-marker")
            return super().write(value)

    sink = FailsOnce()
    assert process.main(stderr=sink, raw_settings=raw) == 1
    assert (app.runs, app.closes) == (0, 1)
    assert "review-private" not in sink.getvalue()


def test_permanently_broken_stderr_still_closes_without_raw_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)

    class Broken(io.StringIO):
        def write(self, _value: str) -> int:
            raise OSError("review-private-permanent-stderr-marker")

    assert process.main(stderr=Broken(), raw_settings=raw) == 1
    assert (app.runs, app.closes) == (0, 1)


def test_validated_paths_are_explicit_and_cannot_be_reread_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)
    captured: list[dict[str, object]] = []

    def build(**kwargs: object) -> Application:
        captured.append(kwargs)
        return cast(Application, app)

    monkeypatch.setattr(process, "build_application", build)
    monkeypatch.setenv("MASKGW_DATASOURCE_STORE", str(tmp_path / "wrong-store"))
    monkeypatch.setenv("MASKGW_DATASOURCE_ANCHOR", str(tmp_path / "wrong-anchor"))
    assert process.main(stderr=io.StringIO(), raw_settings=raw) == 0
    assert len(captured) == 1
    catalog = captured[0]["datasource_catalog"]
    assert isinstance(catalog, DatasourceCatalogSettings)
    assert catalog.store_path == tmp_path / "custom" / "datasources.store"
    assert catalog.anchor_path == (tmp_path / "custom" / ".maskgw-anchor" / "datasources.anchor")
    assert "admin_http" not in captured[0] or captured[0]["admin_http"] is None
    assert "admin_ui_enabled" not in captured[0] or captured[0]["admin_ui_enabled"] is False


@pytest.mark.parametrize("phase", ["run", "close"])
def test_runtime_failure_reporting_is_best_effort_after_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str
) -> None:
    app = _Application()
    raw = _activation(monkeypatch, tmp_path, app)

    def bad_run() -> None:
        app.runs += 1
        raise OSError("review-private-runtime-marker")

    def bad_close() -> None:
        app.closes += 1
        raise OSError("review-private-shutdown-marker")

    if phase == "run":
        monkeypatch.setattr(app, "run", bad_run)
    else:
        monkeypatch.setattr(app, "close", bad_close)

    class CannotReportFailure(io.StringIO):
        def write(self, value: str) -> int:
            if value == process.RUNTIME_FAILURE:
                raise OSError("review-private-runtime-stderr-marker")
            return super().write(value)

    assert process.main(stderr=CannotReportFailure(), raw_settings=raw) == 1
    assert (app.runs, app.closes) == (1, 1)


def test_invalid_activation_with_broken_stderr_does_not_escape_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "0")
    raw = MappingRawSettings({"MASKGW_PGWIRE_ENABLED": "1"})
    calls: list[dict[str, object]] = []

    def build(**kwargs: object) -> Application:
        calls.append(kwargs)
        return cast(Application, _Application())

    class Broken(io.StringIO):
        def write(self, _value: str) -> int:
            raise OSError("review-private-startup-stderr-marker")

    monkeypatch.setattr(process, "build_application", build)
    assert process.main(stderr=Broken(), raw_settings=raw) == 1
    assert calls == []
