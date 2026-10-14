"""Fase 9, Etapa 7 (D-110, lote 4): composicao INTERNA do listener PGWire.

`build_application(pgwire=PgwireComposition(...))` e o unico caminho, so
interno e testavel; o `main` recusa a ativacao (`MASKGW_PGWIRE_ENABLED=1`).
Catalogo com adapters duble, legado com adapter duble, MCP duble; socket real
so em `127.0.0.1` efemero; libpq so faz handshake, sem SQL. Prova:

- `pgwire=None`: nenhum modulo `maskgw.pgwire` carregado;
- exige catalogo e valida settings/TLS/principal/hostname ANTES de efeitos;
- ordem TLS -> principal -> catalogo -> legado -> listener -> MCP;
- S do PGWire e o `max_sessions` do registry (> 32, demais limites intactos);
- alias so pelo selo (`service.view()`), falha uniforme;
- fechamento: todas as admissoes antes da drenagem; listener parado antes do
  catalogo; incerteza retem e `close()` repetido retenta;
- startup parcial: erro original preservado; retencao forte sem prova;
- `close()` de thread PGWire recusado antes de efeitos; `run()` apos fechar.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from contextlib import suppress
from pathlib import Path
from typing import Any, ClassVar, cast

import psycopg
import pytest
from mcp.server import MCPServer

import maskgw.bootstrap.application as application_module
import maskgw.datasource.verify as verify_module
import maskgw.pgwire.composition as composition_module
from maskgw.admin.http.settings import build as build_admin_settings
from maskgw.datasource import CatalogStore
from maskgw.errors import ConfigError
from maskgw.pgwire.composition import PgwireComposition, sealed_alias_check
from maskgw.pgwire.listener import (
    ListenerState,
    PgwireListener,
    PgwireListenerIncompleteError,
)
from maskgw.runtime import admin_work as admin_work_module
from maskgw.runtime.datasource_service import DatasourceCatalogSettings, DatasourceRuntime
from maskgw.runtime.datasources import RegistryLimits
from tests.admin_http_support import TOKEN, free_port
from tests.datasource_runtime_support import KEY, SECRET, FakeFactory, draft, resolver
from tests.datasource_runtime_support import secrets_provider as catalog_secrets
from tests.pgwire_driver_support import ScramClient, authenticate, watchdog
from tests.pgwire_listener_support import (
    USER,
    connect_raw,
    listener_threads,
    make_settings,
    new_credential,
)
from tests.pgwire_support import make_certificate

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
LEGACY_CONFIG = """
database:
  statement_timeout_ms: 2000
  max_rows: 10
"""


class _LegacyAdapter:
    events: ClassVar[list[str]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def connect(self) -> None:
        type(self).events.append("legacy:connect")

    def close(self) -> None:
        type(self).events.append("legacy:close")


class _McpServer:
    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        del transport


@pytest.fixture(autouse=True)
def _limpo():
    _LegacyAdapter.events = []
    with watchdog(120):
        yield
    assert not listener_threads(), [t.name for t in listener_threads()]


@pytest.fixture(scope="module")
def credential():
    return new_credential()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "masking.yaml"
    path.write_text(LEGACY_CONFIG, encoding="utf-8")
    return path


def _catalog(tmp_path: Path, factory: FakeFactory) -> DatasourceCatalogSettings:
    store_path = tmp_path / "catalog" / "datasources.store"
    store_path.parent.mkdir(mode=0o755)
    anchor_path = tmp_path / "catalog-anchor" / "datasources.anchor"
    with CatalogStore.initialize(store_path, anchor_path=anchor_path, master_key=KEY) as store:
        for item in (draft("crm"), draft("hml", enabled=False)):
            store.create(item, SECRET, resolver=resolver)
    return DatasourceCatalogSettings(
        store_path=store_path, anchor_path=anchor_path, resolver=resolver, adapter_factory=factory
    )


def _compose(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    monkeypatch.setattr(application_module, "PostgresAdapter", _LegacyAdapter)

    def recording_mcp(_gateway: object) -> MCPServer:
        events.append("mcp:build")
        return cast(MCPServer, _McpServer())

    monkeypatch.setattr(application_module, "build_mcp_server", recording_mcp)


def _record(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    for name, label in (
        ("prepare_server_tls", "pgwire:tls"),
        ("prepare_principal", "pgwire:principal"),
    ):
        original = getattr(composition_module, name)

        def recording(
            *args: Any, _original: Any = original, _label: str = label, **kwargs: Any
        ) -> Any:
            events.append(_label)
            return _original(*args, **kwargs)

        monkeypatch.setattr(composition_module, name, recording)
    original_start = PgwireListener.start

    def recording_start(self: PgwireListener) -> None:
        events.append("pgwire:start")
        original_start(self)

    monkeypatch.setattr(PgwireListener, "start", recording_start)
    original_call = FakeFactory.__call__

    def recording_call(self: FakeFactory, conninfo: str, **kwargs: Any) -> Any:
        events.append("datasource:candidate")
        return original_call(self, conninfo, **kwargs)

    monkeypatch.setattr(FakeFactory, "__call__", recording_call)


def build(
    config_file: Path,
    catalog: DatasourceCatalogSettings | None,
    pgwire: PgwireComposition | None,
    **extra: Any,
) -> application_module.Application:
    return application_module.build_application(
        config_path=config_file,
        conninfo="host=x",
        secrets=catalog_secrets(),
        datasource_catalog=catalog,
        pgwire=pgwire,
        **extra,
    )


def options(app: application_module.Application, password: str, **extra: Any) -> dict[str, Any]:
    listener = app.pgwire_listener
    assert listener is not None
    return {
        "host": "127.0.0.1",
        "port": listener.port,
        "user": USER,
        "dbname": "crm",
        "password": password,
        "sslmode": "disable",
        "gssencmode": "disable",
        "channel_binding": "disable",
        "connect_timeout": 5,
        **extra,
    }


# -- legado e validacao antes de efeitos -----------------------------------------


def test_sem_pgwire_nenhum_modulo_pgwire_e_carregado(tmp_path: Path) -> None:
    config = tmp_path / "masking.yaml"
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    script = textwrap.dedent(
        f"""
        import sys
        import maskgw.bootstrap.main
        import maskgw.bootstrap.application as app_module

        class Adapter:
            def __init__(self, *a, **k): pass
            def connect(self): pass
            def close(self): pass

        app_module.PostgresAdapter = Adapter
        app = app_module.build_application(config_path={str(config)!r}, conninfo="host=x")
        app.close()
        print(sorted(m for m in sys.modules if m.startswith("maskgw.pgwire")))
        """
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(  # noqa: S603 - interpretador e codigo fixos do teste
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_main_com_flag_exata_recusa_sem_importar_pgwire(tmp_path: Path) -> None:
    script = textwrap.dedent(
        """
        import sys
        import maskgw.bootstrap.main as main_module
        rc = main_module.main()
        print(sorted(m for m in sys.modules if m.startswith("maskgw.pgwire")), file=sys.stderr)
        sys.exit(rc)
        """
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "MASKGW_PGWIRE_ENABLED": "1",
        "MASKGW_CONFIG": str(tmp_path / "nao-existe.yaml"),
        "MASKGW_PGWIRE_PASSWORD": "senha-canario-main",
    }
    result = subprocess.run(  # noqa: S603 - interpretador e codigo fixos do teste
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert result.returncode == 1
    assert result.stdout == ""  # stdout continua so do protocolo
    assert result.stderr == "maskgw: falha na inicializacao\n[]\n"
    assert "canario" not in result.stderr


def test_pgwire_sem_catalogo_falha_antes_de_qualquer_efeito(
    tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    calls: list[str] = []
    request = PgwireComposition(make_settings(password), test_port=0)
    with pytest.raises(ConfigError) as info:
        application_module.build_application(
            config_path=tmp_path / "nao-existe.yaml", conninfo="host=x", pgwire=request
        )
    assert "pgwire" in str(info.value)
    assert info.value.__context__ is None
    assert calls == []


@pytest.mark.parametrize(
    ("changes", "composition"),
    [
        ({"port": 0}, {}),
        ({"max_sessions": 0}, {}),
        ({"password": ""}, {}),
        ({}, {"test_port": 5432}),
        ({}, {"resolved_addresses": ("127.0.0.1",)}),  # bind literal
        # Hostname SEM colaborador deixou de ser recusa de validacao: agora e
        # resolvido DEPOIS de TLS e principal (ver o teste dedicado abaixo).
        (
            {"bind": "gateway.test", "bind_is_hostname": True, "tls_cert": "c", "tls_key": "k"},
            {"resolved_addresses": ("gateway.test",)},
        ),
    ],
)
def test_composicao_invalida_falha_antes_do_catalogo(  # noqa: PLR0913, PLR0917 - fixtures + matriz
    monkeypatch: pytest.MonkeyPatch,
    config_file: Path,
    tmp_path: Path,
    credential: Any,
    changes: dict[str, Any],
    composition: dict[str, Any],
) -> None:
    principal_calls: list[str] = []
    _, password = credential
    opened: list[str] = []
    monkeypatch.setattr(
        application_module, "_open_datasources", lambda *_a, **_k: opened.append("catalogo")
    )
    monkeypatch.setattr(
        composition_module,
        "prepare_principal",
        lambda *_a, **_k: principal_calls.append("principal"),
    )
    settings = make_settings(password)
    fields = {f: getattr(settings, f) for f in settings.__dataclass_fields__}
    fields.update(changes)
    request = PgwireComposition(type(settings)(**fields), **{"test_port": 0, **composition})
    with pytest.raises(ConfigError) as info:
        build(config_file, _catalog(tmp_path, FakeFactory()), request)
    assert opened == []
    assert principal_calls == []
    assert password not in str(info.value)


def test_hostname_sem_colaborador_resolve_depois_de_tls_e_principal_e_falha_fechado(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    # TLS valido; a resolucao limitada falha de forma CONTROLADA (filho fixo
    # que sai sem resposta, sem DNS de rede). Ela roda depois de TLS e
    # principal, uma vez, e nada depois dela acontece.
    _, password = credential
    events: list[str] = []
    _compose(monkeypatch, events)
    _record(monkeypatch, events)
    for name, label in (
        ("_open_datasources", "catalogo"),
        ("_load_configuration", "config"),
        ("make_adapter_factory", "upstream"),
    ):
        monkeypatch.setattr(application_module, name, lambda *_a, _l=label, **_k: events.append(_l))
    monkeypatch.setattr(verify_module, "_BIND_DNS_CHILD_CODE", "import sys\nsys.exit(3)\n")
    original = verify_module.resolve_bind_host_in_child

    def recording_dns(host: str, **kwargs: Any) -> bytes:
        events.append("pgwire:dns")
        return original(host, **kwargs)

    monkeypatch.setattr(verify_module, "resolve_bind_host_in_child", recording_dns)
    cert, _, _ = make_certificate(tmp_path, "rsa-sha256")
    settings = make_settings(password, bind="gateway.test", bind_is_hostname=True, tls=True)
    settings = type(settings)(
        **{
            **{f: getattr(settings, f) for f in settings.__dataclass_fields__},
            "tls_cert": str(cert.cert_path),
            "tls_key": str(cert.key_path),
        }
    )
    with pytest.raises(ConfigError) as info:
        build(
            config_file, _catalog(tmp_path, FakeFactory()), PgwireComposition(settings, test_port=0)
        )
    assert events == ["pgwire:tls", "pgwire:principal", "pgwire:dns"]
    assert str(info.value) == "pgwire: bind por hostname nao resolvido"
    assert info.value.__cause__ is None
    assert info.value.__context__ is None
    assert "gateway.test" not in str(info.value)
    assert password not in str(info.value)


def test_tls_invalido_falha_antes_do_catalogo(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    opened: list[str] = []
    monkeypatch.setattr(
        application_module, "_open_datasources", lambda *_a, **_k: opened.append("catalogo")
    )
    settings = make_settings(password, tls=True)  # caminhos de cert/chave inexistentes
    with pytest.raises(ConfigError):
        build(
            config_file, _catalog(tmp_path, FakeFactory()), PgwireComposition(settings, test_port=0)
        )
    assert opened == []


# -- ordem, limites, alias -----------------------------------------------------------


def test_ordem_tls_principal_catalogo_legado_listener_mcp(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    events: list[str] = []
    _compose(monkeypatch, events)
    _record(monkeypatch, events)
    cert, _, _ = make_certificate(tmp_path, "rsa-sha256")
    settings = make_settings(password, tls=True)
    settings = type(settings)(
        **{
            **{f: getattr(settings, f) for f in settings.__dataclass_fields__},
            "tls_cert": str(cert.cert_path),
            "tls_key": str(cert.key_path),
        }
    )
    app = build(
        config_file, _catalog(tmp_path, FakeFactory()), PgwireComposition(settings, test_port=0)
    )
    try:
        assert events == [
            "pgwire:tls",
            "pgwire:principal",
            "datasource:candidate",
            "pgwire:start",
            "mcp:build",
        ]
        assert _LegacyAdapter.events == ["legacy:connect"]
        assert app.pgwire_listener is not None
        assert app.pgwire_listener.status().state is ListenerState.RUNNING
    finally:
        app.close()
    assert app.pgwire_listener.status().state is ListenerState.STOPPED


def test_s_do_pgwire_e_o_limite_do_registry(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password, max_sessions=40), test_port=0),
    )
    try:
        assert app.datasources is not None
        limits = app.datasources.registry.limits
        base = RegistryLimits()
        assert limits.max_sessions == 40  # > 32: sem teto oculto
        assert (limits.max_retired, limits.max_candidates) == (
            base.max_retired,
            base.max_candidates,
        )
    finally:
        app.close()


def test_sem_pgwire_limites_do_catalogo_inalterados(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    app = build(config_file, _catalog(tmp_path, FakeFactory()), None)
    try:
        assert app.pgwire_listener is None
        assert app.datasources is not None
        assert app.datasources.registry.limits == RegistryLimits()
    finally:
        app.close()


class _OnlyView:
    """Servico de teste que so expoe `view()`; qualquer outro acesso falha."""

    def __init__(self, view: Any) -> None:
        object.__setattr__(self, "_view", view)
        object.__setattr__(self, "touched", [])

    def view(self) -> Any:
        return object.__getattribute__(self, "_view")

    def __getattr__(self, name: str) -> Any:
        pytest.fail(f"o callback de alias tocou {name!r}")


def test_alias_so_pelo_selo(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    app = build(config_file, _catalog(tmp_path, FakeFactory()), None)
    try:
        assert app.datasources is not None
        view = app.datasources.service.view()
    finally:
        app.close()
    check = sealed_alias_check(_OnlyView(view))  # type: ignore[arg-type]
    assert check("crm") is True
    assert check("hml") is False  # desabilitado: nao publicado
    assert check("nao-existe") is False
    assert check("CRM") is False  # forma invalida
    unavailable = sealed_alias_check(_OnlyView(None))  # type: ignore[arg-type]
    assert unavailable("crm") is False  # selo indisponivel


def test_libpq_handshake_por_alias_sem_sql(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    try:
        with psycopg.connect(**options(app, password)):
            pass
        for dbname in ("hml", "nao-existe"):
            with pytest.raises(psycopg.OperationalError) as info:
                psycopg.connect(**options(app, password, dbname=dbname)).close()
            assert "authentication failed" in str(info.value)
            assert dbname not in str(info.value)
        assert password not in repr(app)
    finally:
        app.close()


# -- lifecycle ----------------------------------------------------------------------


def test_fechamento_admissoes_antes_da_drenagem_e_listener_antes_do_catalogo(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    events: list[str] = []
    _compose(monkeypatch, [])
    for owner, name, label in (
        (admin_work_module.AdminWorkQueue, "close_admission", "fila:admissao"),
        (admin_work_module.AdminWorkQueue, "drain", "fila:drenagem"),
        (PgwireListener, "request_stop", "pgwire:admissao"),
        (PgwireListener, "stop", "pgwire:stop"),
        (DatasourceRuntime, "close", "catalogo:close"),
    ):
        original = getattr(owner, name)

        def recording(
            self: Any, *args: Any, _original: Any = original, _label: str = label, **kwargs: Any
        ) -> Any:
            events.append(_label)
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(owner, name, recording)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
        admin_http=build_admin_settings(token=TOKEN, host="127.0.0.1", port=free_port()),
    )
    app.close()
    assert events.index("fila:admissao") < events.index("fila:drenagem")
    assert events.index("pgwire:admissao") < events.index("fila:drenagem")
    assert events.index("fila:drenagem") < events.index("pgwire:stop")
    assert events.index("pgwire:stop") < events.index("catalogo:close")


def test_parada_incerta_retem_catalogo_e_close_repetido_retenta(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    closed: list[str] = []
    original_close = DatasourceRuntime.close

    def recording_close(self: DatasourceRuntime) -> None:
        closed.append("catalogo")
        original_close(self)

    monkeypatch.setattr(DatasourceRuntime, "close", recording_close)
    original_stop = PgwireListener.stop
    attempts = {"n": 0}

    def flaky_stop(self: PgwireListener) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PgwireListenerIncompleteError
        original_stop(self)

    monkeypatch.setattr(PgwireListener, "stop", flaky_stop)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    with pytest.raises(PgwireListenerIncompleteError):
        app.close()
    assert closed == []  # nada que o listener possa consultar foi fechado
    assert "closing" in repr(app)
    with pytest.raises(RuntimeError):
        app.run()  # closing: o MCP nunca e oferecido
    app.close()  # retenta
    assert closed == ["catalogo"]
    assert "closed" in repr(app)


def test_close_de_thread_pgwire_recusado_antes_de_efeitos(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    holder: dict[str, Any] = {}
    refused: list[str] = []

    def factory(_service: Any) -> Any:
        def accepted(alias: str) -> bool:
            try:
                holder["app"].close()
            except RuntimeError:
                refused.append("recusado")
            return alias == "crm"

        return accepted

    monkeypatch.setattr(composition_module, "sealed_alias_check", factory)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    holder["app"] = app
    try:
        sock = connect_raw(app.pgwire_listener)  # type: ignore[arg-type]
        with sock:
            messages = authenticate(sock, ScramClient(password))
        assert messages[-1] == (b"Z", b"I")
        assert refused == ["recusado"]
        assert "closing" not in repr(app)  # nenhum efeito
    finally:
        app.close()


def test_start_parcial_preserva_o_erro_e_fecha_com_prova(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    original_start = PgwireListener.start

    def start_then_fail(self: PgwireListener) -> None:
        original_start(self)
        msg = "canario-start-pgwire"
        raise RuntimeError(msg)

    monkeypatch.setattr(PgwireListener, "start", start_then_fail)
    catalog = _catalog(tmp_path, FakeFactory())
    with pytest.raises(RuntimeError, match="canario-start-pgwire"):
        build(config_file, catalog, PgwireComposition(make_settings(password), test_port=0))
    assert not listener_threads()
    # Catalogo fechado com prova: os locks foram soltos.
    CatalogStore.open(catalog.store_path, anchor_path=catalog.anchor_path, master_key=KEY).close()
    assert not [r for r in admin_work_module._RETAINED if isinstance(r, PgwireListener)]


def test_start_parcial_com_parada_incerta_retem_listener_e_catalogo(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    original_start = PgwireListener.start
    original_stop = PgwireListener.stop
    closed: list[str] = []
    monkeypatch.setattr(DatasourceRuntime, "close", lambda _self: closed.append("catalogo"))

    def start_then_fail(self: PgwireListener) -> None:
        original_start(self)
        msg = "canario-start-incerto"
        raise RuntimeError(msg)

    def uncertain_stop(_self: PgwireListener) -> None:
        raise PgwireListenerIncompleteError

    monkeypatch.setattr(PgwireListener, "start", start_then_fail)
    monkeypatch.setattr(PgwireListener, "stop", uncertain_stop)
    with pytest.raises(RuntimeError, match="canario-start-incerto"):
        build(
            config_file,
            _catalog(tmp_path, FakeFactory()),
            PgwireComposition(make_settings(password), test_port=0),
        )
    assert closed == []  # o catalogo que o listener pode consultar NAO foi fechado
    retained = [r for r in admin_work_module._RETAINED if isinstance(r, PgwireListener)]
    datasources = [r for r in admin_work_module._RETAINED if isinstance(r, DatasourceRuntime)]
    assert len(retained) == 1 and len(datasources) == 1
    # Higiene do teste: recolhe o que o produto reteve, com os metodos reais.
    monkeypatch.setattr(PgwireListener, "stop", original_stop)
    retained[0].stop()
    admin_work_module.release_retained(retained[0], datasources[0])
    monkeypatch.undo()
    datasources[0].close()


def _ledger(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Ledger D-108 isolado para o teste (mesmo mecanismo, lista propria)."""
    ledger: list[object] = []
    monkeypatch.setattr(admin_work_module, "_RETAINED", ledger)
    return ledger


def test_close_bem_sucedido_nao_deixa_a_aplicacao_no_ledger(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    ledger = _ledger(monkeypatch)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    assert ledger == []  # construir nao retem nada
    app.close()
    app.close()  # idempotente
    assert ledger == []
    assert "closed" in repr(app)


def test_retry_com_prova_solta_a_retencao_sem_duplicar(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    ledger = _ledger(monkeypatch)
    original_stop = PgwireListener.stop
    attempts = {"n": 0}

    def flaky_stop(self: PgwireListener) -> None:
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise PgwireListenerIncompleteError
        original_stop(self)

    monkeypatch.setattr(PgwireListener, "stop", flaky_stop)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    for _ in range(2):
        with pytest.raises(PgwireListenerIncompleteError):
            app.close()
        assert ledger == [app]  # retida uma vez so, mesmo com retry sem prova
    app.close()
    assert ledger == []
    assert "closed" in repr(app)


def test_self_close_recusado_nao_retem(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    ledger = _ledger(monkeypatch)
    holder: dict[str, Any] = {}
    snapshots: list[list[object]] = []

    def factory(_service: Any) -> Any:
        def accepted(alias: str) -> bool:
            with suppress(RuntimeError):
                holder["app"].close()
            snapshots.append(list(ledger))
            return alias == "crm"

        return accepted

    monkeypatch.setattr(composition_module, "sealed_alias_check", factory)
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    holder["app"] = app
    try:
        sock = connect_raw(app.pgwire_listener)  # type: ignore[arg-type]
        with sock:
            authenticate(sock, ScramClient(password))
        assert snapshots == [[]]  # recusa ANTES de qualquer efeito, inclusive retencao
    finally:
        app.close()
    assert ledger == []


def test_sem_pgwire_close_nao_toca_o_ledger(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path
) -> None:
    _compose(monkeypatch, [])
    ledger = _ledger(monkeypatch)
    app = build(config_file, _catalog(tmp_path, FakeFactory()), None)
    app.close()
    assert ledger == []


def test_run_depois_de_fechar_e_recusado(
    monkeypatch: pytest.MonkeyPatch, config_file: Path, tmp_path: Path, credential: Any
) -> None:
    _, password = credential
    _compose(monkeypatch, [])
    app = build(
        config_file,
        _catalog(tmp_path, FakeFactory()),
        PgwireComposition(make_settings(password), test_port=0),
    )
    app.close()
    with pytest.raises(RuntimeError):
        app.run()
