"""Independent checks of the deliberately closed operational activation gate."""

from __future__ import annotations

import contextlib
import gc
import io
import secrets
import weakref
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import maskgw.bootstrap.application as application_module
import maskgw.bootstrap.main as main_module
from maskgw.admin import AdminConfigService
from maskgw.admin.http import AdminHttpServer
from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.bootstrap.application import Application
from maskgw.bootstrap.settings import RawSettings
from maskgw.datasource import CatalogStore
from maskgw.pgwire.composition import PgwireComposition
from maskgw.pgwire.listener import PgwireListener, PgwireListenerIncompleteError
from maskgw.runtime import admin_work as work_module
from maskgw.runtime.admin_work import AdminWorkQueue
from maskgw.runtime.datasource_service import DatasourceRuntime
from tests.admin_http_support import TOKEN, free_port
from tests.datasource_runtime_support import KEY, FakeFactory, draft, secrets_provider
from tests.pgwire_driver_support import watchdog
from tests.pgwire_listener_support import listener_threads, make_settings, wait_until
from tests.test_datasource_bootstrap import LEGACY_CONFIG, _catalog, _compose

FLAG = "MASKGW_PGWIRE_ENABLED"


@pytest.fixture(autouse=True)
def _bounded_review() -> Iterator[None]:
    with watchdog(30):
        yield


class _Raw(RawSettings):
    def __init__(self, flag: str | None) -> None:
        self.flag = flag
        self.reads: list[str] = []

    def get_raw(self, name: str) -> str | None:
        self.reads.append(name)
        if name == FLAG:
            return self.flag
        if name.startswith("MASKGW_PGWIRE_"):
            pytest.fail("disabled ingress must not read further PGWire fields")
        return None


class _App:
    revision = 0
    admin_http = None

    def __init__(self) -> None:
        self.runs = 0
        self.closes = 0

    def run(self) -> None:
        self.runs += 1

    def close(self) -> None:
        self.closes += 1


def test_exact_enable_is_refused_before_admin_secrets_or_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _Raw("1")
    forbidden_calls: list[str] = []
    monkeypatch.setattr(main_module, "resolve_admin_ui_enabled", lambda _raw: False)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        forbidden_calls.append("forbidden")
        pytest.fail("operational activation must stop before secrets/resources")

    monkeypatch.setattr(main_module, "resolve_admin_settings", forbidden)
    monkeypatch.setattr(main_module, "build_application", forbidden)
    sink = io.StringIO()
    assert main_module.main(stderr=sink, raw_settings=raw) == 1
    assert sink.getvalue() == main_module.STARTUP_FAILURE
    assert raw.reads == [FLAG]
    assert forbidden_calls == []


@pytest.mark.parametrize("flag", [None, "0", "true", " 1", "1 ", "01", ""])
def test_non_exact_enable_does_not_expand_legacy_startup(
    monkeypatch: pytest.MonkeyPatch, flag: str | None
) -> None:
    raw = _Raw(flag)
    app = _App()
    monkeypatch.setattr(main_module, "resolve_admin_ui_enabled", lambda _raw: False)
    monkeypatch.setattr(main_module, "resolve_admin_settings", lambda: None)
    monkeypatch.setattr(main_module, "build_application", lambda **_kwargs: cast(Application, app))
    sink = io.StringIO()
    assert main_module.main(stderr=sink, raw_settings=raw) == 0
    assert raw.reads == [FLAG]
    assert (app.runs, app.closes) == (1, 1)
    assert sink.getvalue() == f"{main_module.REVISION_LOADED_PREFIX}0\n"


def test_partial_pgwire_startup_closes_v1_admission_before_draining_v2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed build has no Application.close to seal v1 on its behalf."""
    _compose(monkeypatch, [])
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    catalog = replace(_catalog(tmp_path, draft("crm")), adapter_factory=FakeFactory())
    holder: list[AdminConfigService] = []
    closed_when_draining: list[bool] = []

    class QuietHttp:
        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    def http_factory(
        admin: AdminConfigService, *_args: object, **_kwargs: object
    ) -> AdminHttpServer:
        holder.append(admin)
        return cast(AdminHttpServer, QuietHttp())

    original_drain = AdminWorkQueue.drain

    def observed_drain(work: AdminWorkQueue) -> bool:
        closed_when_draining.append(holder[0].closed)
        return original_drain(work)

    def fail_mcp(_gateway: object) -> None:
        raise RuntimeError("review-startup-failure")

    monkeypatch.setattr(application_module, "_build_admin_http", http_factory)
    monkeypatch.setattr(application_module, "build_mcp_server", fail_mcp)
    monkeypatch.setattr(AdminWorkQueue, "drain", observed_drain)
    request = PgwireComposition(make_settings(secrets.token_urlsafe(16)), test_port=0)
    with pytest.raises(RuntimeError, match="review-startup-failure"):
        application_module.build_application(
            config_path=config,
            conninfo="host=x",
            secrets=secrets_provider(),
            admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=free_port()),
            datasource_catalog=catalog,
            pgwire=request,
        )
    assert closed_when_draining == [True]


def test_incomplete_close_keeps_catalog_owned_after_caller_drops_application(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An error return must not make an unknown resource depend on caller GC."""
    retained: list[object] = []
    monkeypatch.setattr(work_module, "_RETAINED", retained)
    _compose(monkeypatch, [])
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    catalog = replace(_catalog(tmp_path, draft("crm")), adapter_factory=FakeFactory())
    app = application_module.build_application(
        config_path=config,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=catalog,
        pgwire=PgwireComposition(make_settings(secrets.token_urlsafe(16)), test_port=0),
    )
    original_stop = PgwireListener.stop
    assert app.pgwire_listener is not None
    listener_ref = weakref.ref(app.pgwire_listener)

    def unknown_stop(_listener: PgwireListener) -> None:
        raise PgwireListenerIncompleteError

    monkeypatch.setattr(PgwireListener, "stop", unknown_stop)
    try:
        with pytest.raises(PgwireListenerIncompleteError):
            app.close()
        del app
        assert wait_until(lambda: not listener_threads())
        gc.collect()
        assert listener_ref() is not None, "caller GC destroyed an unproven listener owner"
        reopened = None
        with contextlib.suppress(Exception):
            reopened = CatalogStore.open(
                catalog.store_path, anchor_path=catalog.anchor_path, master_key=KEY
            )
        if reopened is not None:
            reopened.close()
            pytest.fail("uncertain close lost ownership and released the catalog lock via GC")
        assert any(isinstance(owner, (Application, PgwireListener)) for owner in retained)
        assert any(isinstance(owner, (Application, DatasourceRuntime)) for owner in retained)
    finally:
        monkeypatch.setattr(PgwireListener, "stop", original_stop)
        for owner in list(retained):
            if isinstance(owner, Application):
                owner.close()
        for owner in list(retained):
            if isinstance(owner, PgwireListener):
                owner.stop()
        for owner in list(retained):
            if isinstance(owner, DatasourceRuntime):
                owner.close()
        work_module.release_retained(*retained)
