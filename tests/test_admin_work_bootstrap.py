"""Fase 9, Etapa 7 (D-108): a fila dedicada no composition root.

- so existe com catalogo + Admin HTTP; sem HTTP (ou sem catalogo) nada muda;
- o shutdown conclui TODAS as operacoes aceitas (na fila e em execucao) com o
  registry ainda aberto, e so depois para a admissao e a thread HTTP;
- `close()` de dentro de um worker e recusado ANTES de qualquer efeito;
- drenagem nao comprovada: catalogo/registry/store retidos, `closing`, e um
  `close()` posterior conclui;
- startup parcial com worker de inicio incerto, ou com a propria limpeza
  falhando, preserva o erro original e retem o dono do que nao pode soltar.
"""

from __future__ import annotations

import contextlib
import os
import socket
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

import maskgw.bootstrap.application as application_module
import maskgw.runtime.admin_work as work_module
from maskgw.admin.http import AdminHttpServer
from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.datasource import CatalogStore
from maskgw.runtime.admin_work import AdminWorkQueue, AdminWorkShutdownIncompleteError
from maskgw.runtime.datasource_service import DatasourceCatalogSettings, DatasourceRuntime
from tests.admin_http_support import TOKEN, free_port
from tests.datasource_runtime_support import KEY, FakeFactory, draft, resolver, secrets_provider
from tests.test_datasource_bootstrap import LEGACY_CONFIG, _catalog, _compose, _LegacyAdapter


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    _LegacyAdapter.events = []
    retained: list[object] = []
    monkeypatch.setattr(work_module, "_RETAINED", retained)
    timer = threading.Timer(90.0, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    try:
        yield retained
    finally:
        timer.cancel()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(LEGACY_CONFIG, encoding="utf-8")
    return path


def _settings(tmp_path: Path) -> DatasourceCatalogSettings:
    base = _catalog(tmp_path, draft("crm"))
    return DatasourceCatalogSettings(
        store_path=base.store_path,
        anchor_path=base.anchor_path,
        resolver=resolver,
        adapter_factory=FakeFactory(),
    )


def _build(config_file: Path, settings: DatasourceCatalogSettings, *, port: int) -> Any:
    return application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=port),
        datasource_catalog=settings,
    )


def _catalog_locked(settings: DatasourceCatalogSettings) -> bool:
    try:
        CatalogStore.open(
            settings.store_path, anchor_path=settings.anchor_path, master_key=KEY
        ).close()
    except Exception:  # qualquer recusa prova o lock retido
        return True
    return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


# ---- composicao --------------------------------------------------------------


def test_catalog_without_http_composes_no_queue(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    app = application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=secrets_provider(),
        datasource_catalog=_settings(tmp_path),
    )
    try:
        assert app.admin_work is None
    finally:
        app.close()


# ---- shutdown A1: concluir TODO o aceito com o registry aberto ----------------


def test_shutdown_completes_queued_and_running_work_before_closing_admission(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    settings = _settings(tmp_path)
    port = free_port()
    app = _build(config_file, settings, port=port)
    work: AdminWorkQueue = app.admin_work
    runtime: DatasourceRuntime = app.datasources
    gate = threading.Event()
    running = [threading.Event(), threading.Event()]
    seen: list[bool] = []

    def job(started: threading.Event | None) -> str:
        if started is not None:
            started.set()
        gate.wait(20)
        # O registry ainda admite reservas: a operacao aceita pode publicar.
        seen.append(runtime.registry.status().closing)
        return "ok"

    def bound(started: threading.Event | None) -> Callable[[], str]:
        return lambda: job(started)

    closer = threading.Thread(target=app.close, daemon=True)
    try:
        tickets = [work.submit(bound(event)) for event in running]
        tickets += [work.submit(bound(None)) for _ in range(2)]
        assert all(event.wait(5) for event in running)
        closer.start()
        closer.join(0.3)
        assert closer.is_alive(), "o shutdown espera o trabalho aceito"
    finally:
        # Mesmo com falha acima: barreira solta e aplicacao fechada.
        gate.set()
        if closer.is_alive():
            closer.join(30)
        else:
            app.close()
    assert not closer.is_alive()
    assert seen == [False] * 4
    assert [ticket.take() for ticket in tickets] == ["ok"] * 4
    assert "state='closed'" in repr(app)
    assert not _catalog_locked(settings)
    assert _port_free(port)


def test_close_from_a_worker_is_refused_before_any_effect(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    app = _build(config_file, _settings(tmp_path), port=free_port())
    seen: list[str] = []

    def job() -> str:
        try:
            app.close()
        except RuntimeError as exc:
            seen.append(str(exc))
        return "ok"

    try:
        ticket = app.admin_work.submit(job)
        for _ in range(500):
            if ticket.done:
                break
            threading.Event().wait(0.01)
        assert seen == ["encerramento recusado a partir de uma thread administrativa"]
        assert "state='ready'" in repr(app), "nenhum efeito: nem `closing`"
        assert not app.admin_work.closing
    finally:
        app.close()
    assert "state='closed'" in repr(app)


def test_unproven_drain_keeps_catalog_and_registry_until_a_later_close(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    settings = _settings(tmp_path)
    port = free_port()
    app = _build(config_file, settings, port=port)
    original_drain = AdminWorkQueue.drain

    def unproven(self: AdminWorkQueue) -> bool:
        original_drain(self)
        return False

    monkeypatch.setattr(AdminWorkQueue, "drain", unproven)
    try:
        with pytest.raises(AdminWorkShutdownIncompleteError) as caught:
            app.close()
        assert caught.value.__context__ is None
        assert "state='closing'" in repr(app)
        assert _catalog_locked(settings), "catalogo retido sob worker nao comprovado"
        assert _port_free(port), "o que nao depende do worker fechou"
        assert _LegacyAdapter.events == ["legacy:connect", "legacy:close"]
    finally:
        # Mesmo com falha acima: a drenagem real volta e a aplicacao fecha.
        monkeypatch.setattr(AdminWorkQueue, "drain", original_drain)
        app.close()
    assert "state='closed'" in repr(app)
    assert not _catalog_locked(settings)


# ---- startup parcial ----------------------------------------------------------


def _uncertain_second_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    real_start = threading.Thread.start

    def start(self: threading.Thread) -> None:
        if self.name == "maskgw-admin-work-1":
            msg = "inicio de worker injetado"
            raise RuntimeError(msg)
        real_start(self)

    monkeypatch.setattr(threading.Thread, "start", start)


def _release(retained: list[object]) -> None:
    for item in retained:
        if isinstance(item, DatasourceRuntime):
            with contextlib.suppress(Exception):
                item.close()
    for item in retained:
        close = getattr(item, "close", None) or getattr(item, "close_all", None)
        if close is not None and not isinstance(item, AdminWorkQueue | DatasourceRuntime):
            with contextlib.suppress(Exception):
                close()


def test_partial_startup_with_an_uncertain_worker_retains_owner_and_catalog(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    _isolated: list[object],
) -> None:
    _compose(monkeypatch, [])
    settings = _settings(tmp_path)
    _uncertain_second_worker(monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="inicio de worker injetado"):
            _build(config_file, settings, port=free_port())
        monkeypatch.undo()
        kinds = {type(item) for item in _isolated}
        assert AdminWorkQueue in kinds
        assert DatasourceRuntime in kinds
        assert _catalog_locked(settings), "catalogo nao solto sob worker incerto"
    finally:
        _release(_isolated)
    assert not _catalog_locked(settings)


@pytest.mark.parametrize("point", ["close_partial", "registry", "datasources", "store"])
def test_partial_startup_keeps_the_owner_when_cleanup_is_not_proven(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    _isolated: list[object],
    point: str,
) -> None:
    # A drenagem comprova os WORKERS (drain True) e o HTTP para de fato; mas o
    # fechamento de catalogo/registry/store falha. Sem prova de fechamento, o
    # dono NAO e solto, e o erro original do startup sai intacto.
    from maskgw.config import ConfigFileStore  # noqa: PLC0415
    from maskgw.runtime import RuntimeRegistry  # noqa: PLC0415

    _compose(monkeypatch, [])

    def failing_mcp(_gateway: object) -> Any:
        msg = "falha sintetica do MCP"
        raise RuntimeError(msg)

    def broken(*_args: Any, **_kwargs: Any) -> None:
        msg = "limpeza injetada"
        raise OSError(msg)

    monkeypatch.setattr(application_module, "build_mcp_server", failing_mcp)
    target: tuple[object, str] = {
        "close_partial": (application_module, "_close_partial"),
        "registry": (RuntimeRegistry, "close_all"),
        "datasources": (DatasourceRuntime, "close"),
        "store": (ConfigFileStore, "close"),
    }[point]
    monkeypatch.setattr(target[0], target[1], broken)
    settings = _settings(tmp_path)
    port = free_port()
    try:
        with pytest.raises(RuntimeError, match="falha sintetica do MCP") as caught:
            _build(config_file, settings, port=port)
        assert "limpeza" not in str(caught.value)
        kinds = {type(item) for item in _isolated}
        assert {AdminWorkQueue, DatasourceRuntime} <= kinds, "dono retido sem prova"
        assert RuntimeRegistry in kinds
        assert ConfigFileStore in kinds
        assert _port_free(port), "o que comprovadamente nao depende foi encerrado"
    finally:
        monkeypatch.undo()
        _release(_isolated)
    assert not _catalog_locked(settings)


def test_partial_startup_releases_the_owner_only_after_proven_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    _isolated: list[object],
) -> None:
    _compose(monkeypatch, [])

    def failing_mcp(_gateway: object) -> Any:
        msg = "falha sintetica do MCP"
        raise RuntimeError(msg)

    monkeypatch.setattr(application_module, "build_mcp_server", failing_mcp)
    settings = _settings(tmp_path)
    with pytest.raises(RuntimeError, match="falha sintetica do MCP"):
        _build(config_file, settings, port=free_port())
    assert _isolated == [], "tudo comprovadamente fechado: nada retido"
    assert not _catalog_locked(settings)


def test_partial_startup_cleanup_failures_never_replace_the_original_error(
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    _isolated: list[object],
) -> None:
    _compose(monkeypatch, [])

    def failing_mcp(_gateway: object) -> Any:
        msg = "falha sintetica do MCP"
        raise RuntimeError(msg)

    original_drain = AdminWorkQueue.drain
    original_stop = AdminHttpServer.stop

    def drain_then_fail(self: AdminWorkQueue) -> bool:
        original_drain(self)
        msg = "drenagem injetada"
        raise OSError(msg)

    def stop_then_fail(self: AdminHttpServer) -> None:
        original_stop(self)
        msg = "stop injetado"
        raise OSError(msg)

    monkeypatch.setattr(application_module, "build_mcp_server", failing_mcp)
    monkeypatch.setattr(AdminWorkQueue, "drain", drain_then_fail)
    monkeypatch.setattr(AdminHttpServer, "stop", stop_then_fail)
    settings = _settings(tmp_path)
    port = free_port()
    try:
        with pytest.raises(RuntimeError, match="falha sintetica do MCP"):
            _build(config_file, settings, port=port)
        kinds = {type(item) for item in _isolated}
        assert {AdminWorkQueue, DatasourceRuntime, AdminHttpServer} <= kinds
        assert _catalog_locked(settings)
        assert _port_free(port), "o stop real ocorreu; so o seu retorno falhou"
    finally:
        monkeypatch.undo()
        _release(_isolated)
    assert not _catalog_locked(settings)
