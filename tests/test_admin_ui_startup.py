"""Etapa 3: settings brutos, barreira pre-startup e compatibilidade sem UI HTTP."""

from __future__ import annotations

import hashlib
import io
import json
import re
import socket
import threading
from pathlib import Path
from typing import Any, cast

import pytest

import maskgw.bootstrap.application as composition
import maskgw.bootstrap.main as process
from maskgw.admin.http import AdminHttpSettings
from maskgw.admin.ui import resources
from maskgw.bootstrap.application import resolve_admin_ui_enabled
from maskgw.bootstrap.settings import (
    ADMIN_UI_ENABLED_ENV,
    EnvRawSettings,
    MappingRawSettings,
    RawSettings,
)
from maskgw.config import ConfigFileStore, load_config_bundle_text
from maskgw.db.postgres import PostgresAdapter
from maskgw.errors import ConfigError
from maskgw.masking.transformers.hashes import build_hmac_sha256
from maskgw.secretsource import EnvSecretProvider, MappingSecretProvider
from tests.admin_http_support import TOKEN, free_port, request, thread_snapshot
from tests.admin_ui_compat_support import snapshots
from tests.test_admin_http_lifecycle import (
    CONFIG,
    FailingStartHttpServer,
    FakeAdapter,
    FakeMcpServer,
    ObservableHttpServer,
    ObservableStore,
    compose,
    settings,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_VALUES = [
    None,
    "",
    "0",
    "true",
    "yes",
    "01",
    " 1",
    "1 ",
    "\t1",
    "1\n",
    "TRUE",
    "on",
    "2",
    "\uff11",
    "1\x00",
    "1",
]
ASSETS = ["index.html", "ui.js", "ui.css", "presentation.json", "manifest.json"]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in (
        ADMIN_UI_ENABLED_ENV,
        "MASKGW_ADMIN_ENABLED",
        "MASKGW_ADMIN_TOKEN",
        "MASKGW_ADMIN_BIND",
        "MASKGW_ADMIN_PORT",
    ):
        monkeypatch.delenv(key, raising=False)
    FakeAdapter.events = []
    FakeAdapter.instances = []


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "masking.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


@pytest.mark.parametrize("value", RAW_VALUES)
@pytest.mark.parametrize("environment", [False, True])
def test_exact_raw_flag(value, environment, monkeypatch):
    values = {} if value is None else {ADMIN_UI_ENABLED_ENV: value}
    source: RawSettings
    if environment:
        for key, item in values.items():
            monkeypatch.setenv(key, item)
        source = EnvRawSettings()
    else:
        source = MappingRawSettings(values)
    assert source.get_raw(ADMIN_UI_ENABLED_ENV) == value
    assert resolve_admin_ui_enabled(
        source, secrets=MappingSecretProvider({"MASKGW_ADMIN_ENABLED": "1"})
    ) is (value == "1")


@pytest.mark.parametrize("environment", [False, True])
def test_secrets_still_normalize_and_raw_source_does_not(environment, monkeypatch):
    values = {
        "MASKGW_ADMIN_ENABLED": " 1 ",
        "MASKGW_ADMIN_TOKEN": "  " + TOKEN + " \n",
        "MASKGW_DATABASE_DSN": "  private-dsn  ",
        "MASKGW_HMAC_KEY": "  " + "k" * 40 + "  ",
        ADMIN_UI_ENABLED_ENV: " 1 ",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    secrets = EnvSecretProvider() if environment else MappingSecretProvider(values)
    source = EnvRawSettings() if environment else MappingRawSettings(values)
    assert not resolve_admin_ui_enabled(source, secrets=secrets)
    resolved = composition.resolve_admin_settings(secrets)
    assert resolved is not None and resolved.token == TOKEN
    assert composition.resolve_dsn(secrets) == "private-dsn"
    assert build_hmac_sha256({}, secrets).transform("x") == build_hmac_sha256(
        {}, MappingSecretProvider({"MASKGW_HMAC_KEY": "k" * 40})
    ).transform("x")
    assert repr(source) in {"EnvRawSettings()", "MappingRawSettings()"}


def test_mapping_raw_source_owns_snapshot_and_empty_is_not_absent():
    values = {ADMIN_UI_ENABLED_ENV: ""}
    source = MappingRawSettings(values)
    values[ADMIN_UI_ENABLED_ENV] = "1"
    assert source.get_raw(ADMIN_UI_ENABLED_ENV) == ""
    assert source.get_raw("absent") is None


def block_operational_effects(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> list[str]:
    events: list[str] = []

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        events.append("forbidden")
        raise AssertionError("operational effect before validation")

    original_open = io.open

    def guarded_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file) == config_file:
            return forbidden()
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(composition, "_load_configuration", forbidden)
    monkeypatch.setattr(ConfigFileStore, "open", forbidden)
    monkeypatch.setattr(PostgresAdapter, "connect", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(composition, "build_mcp_server", forbidden)
    return events


def enable_process(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> None:
    monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "1")
    monkeypatch.setenv("MASKGW_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("MASKGW_CONFIG", str(config_file))


@pytest.mark.parametrize("admin", [None, "", "0", "true", "yes"])
def test_ui_requires_admin_before_settings_or_resources(admin, monkeypatch, config_file):
    if admin is not None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", admin)
    events = block_operational_effects(monkeypatch, config_file)

    def forbidden(*_args):
        events.append("settings/assets")
        raise AssertionError

    monkeypatch.setattr(process, "resolve_admin_settings", forbidden)
    monkeypatch.setattr(composition, "load_resources", forbidden)
    stderr = io.StringIO()
    assert (
        process.main(stderr=stderr, raw_settings=MappingRawSettings({ADMIN_UI_ENABLED_ENV: "1"}))
        == 1
    )
    assert stderr.getvalue() == process.STARTUP_FAILURE
    assert events == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("MASKGW_ADMIN_TOKEN", ""),
        ("MASKGW_ADMIN_TOKEN", "short"),
        ("MASKGW_ADMIN_BIND", "0.0.0.0"),  # noqa: S104 - bind que deve ser recusado
        ("MASKGW_ADMIN_PORT", "0"),
        ("MASKGW_ADMIN_PORT", "65536"),
        ("MASKGW_ADMIN_PORT", "private-marker"),
    ],
)
def test_invalid_admin_settings_precede_assets(key, value, monkeypatch, config_file):
    enable_process(monkeypatch, config_file)
    monkeypatch.setenv(key, value)
    events = block_operational_effects(monkeypatch, config_file)

    def forbidden():
        events.append("assets")
        raise AssertionError

    monkeypatch.setattr(composition, "load_resources", forbidden)
    stderr = io.StringIO()
    assert (
        process.main(stderr=stderr, raw_settings=MappingRawSettings({ADMIN_UI_ENABLED_ENV: "1"}))
        == 1
    )
    assert stderr.getvalue() == process.STARTUP_FAILURE and events == []


def package_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    package = tmp_path / "package"
    assets = package / "assets"
    assets.mkdir(parents=True)
    for name in ASSETS:
        (assets / name).write_bytes((ROOT / "src/maskgw/admin/ui/assets" / name).read_bytes())
    monkeypatch.setattr(resources, "files", lambda _package: package)
    return assets


def resign(assets: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    digest = hashlib.sha256((assets / "presentation.json").read_bytes()).hexdigest()
    javascript = (assets / "ui.js").read_bytes()
    javascript = re.sub(
        rb'export const digest="[a-f0-9]+";',
        b'export const digest="' + digest.encode() + b'";',
        javascript,
    )
    (assets / "ui.js").write_bytes(javascript)
    manifest = json.loads((assets / "manifest.json").read_bytes())
    for entry in manifest["entries"]:
        data = (assets / entry["path"]).read_bytes()
        entry["size"] = len(data)
        entry["sha256"] = hashlib.sha256(data).hexdigest()
    data = json.dumps(manifest).encode()
    (assets / "manifest.json").write_bytes(data)
    monkeypatch.setattr(resources, "MANIFEST_SHA256", hashlib.sha256(data).hexdigest())


def test_reanchored_valid_fixture_is_a_positive_control(monkeypatch, tmp_path):
    assets = package_copy(tmp_path, monkeypatch)
    document = json.loads((assets / "presentation.json").read_bytes())
    encoded = json.dumps(document).encode()
    (assets / "presentation.json").write_bytes(encoded)
    resign(assets, monkeypatch)
    assert resources.load_resources()["presentation.json"] == encoded


@pytest.mark.parametrize("name", ASSETS)
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_each_resource_failure_precedes_all_effects(
    name, damage, monkeypatch, tmp_path, config_file
):
    assets = package_copy(tmp_path, monkeypatch)
    if damage == "missing":
        (assets / name).unlink()
    else:
        (assets / name).write_bytes(b"private-marker\xff")
    enable_process(monkeypatch, config_file)
    events = block_operational_effects(monkeypatch, config_file)
    stderr = io.StringIO()
    assert (
        process.main(stderr=stderr, raw_settings=MappingRawSettings({ADMIN_UI_ENABLED_ENV: "1"}))
        == 1
    )
    assert stderr.getvalue() == "maskgw: falha na inicializacao\n"
    assert events == []


@pytest.mark.parametrize(
    "damage", ["format", "catalog", "model", "utf8", "duplicate", "extra_manifest", "js_digest"]
)
def test_incompatibility_with_valid_hashes_still_precedes_effects(
    damage, monkeypatch, tmp_path, config_file
):
    assets = package_copy(tmp_path, monkeypatch)
    data = json.loads((assets / "presentation.json").read_bytes())
    if damage == "format":
        data["format"] = 2
    elif damage == "catalog":
        data["calls"][0]["path"] = "/admin/v1/unapproved"
    elif damage == "model":
        data["calls"][0]["output"] = data["calls"][1]["output"]
    (assets / "presentation.json").write_bytes(json.dumps(data).encode())
    if damage == "utf8":
        (assets / "presentation.json").write_bytes(b"\xff")
    elif damage == "duplicate":
        (assets / "presentation.json").write_bytes(b'{"format":1,"format":1}')
    elif damage == "js_digest":
        (assets / "ui.js").write_bytes(b"export const digest='wrong';")
    resign(assets, monkeypatch)
    if damage == "extra_manifest":
        manifest = json.loads((assets / "manifest.json").read_bytes())
        manifest["private-marker"] = True
        encoded = json.dumps(manifest).encode()
        (assets / "manifest.json").write_bytes(encoded)
        monkeypatch.setattr(resources, "MANIFEST_SHA256", hashlib.sha256(encoded).hexdigest())
    enable_process(monkeypatch, config_file)
    events = block_operational_effects(monkeypatch, config_file)
    stderr = io.StringIO()
    assert (
        process.main(stderr=stderr, raw_settings=MappingRawSettings({ADMIN_UI_ENABLED_ENV: "1"}))
        == 1
    )
    assert stderr.getvalue() == process.STARTUP_FAILURE and events == []


@pytest.mark.parametrize(
    "admin_http",
    [
        None,
        AdminHttpSettings(token="short"),  # noqa: S106 - token invalido de teste
        AdminHttpSettings(token=TOKEN, host="0.0.0.0"),  # noqa: S104 - contraprova
        AdminHttpSettings(token=TOKEN, port=0),
    ],
)
def test_direct_composition_cannot_bypass_preconditions(admin_http, monkeypatch, config_file):
    events = block_operational_effects(monkeypatch, config_file)

    def forbidden():
        events.append("assets")
        raise AssertionError

    monkeypatch.setattr(composition, "load_resources", forbidden)
    with pytest.raises(ConfigError):
        composition.build_application(
            config_path=config_file,
            admin_enabled=True,
            admin_http=admin_http,
            admin_ui_enabled=True,
        )
    assert events == []


def test_positive_startup_order_and_shutdown(monkeypatch, config_file):
    enable_process(monkeypatch, config_file)
    monkeypatch.setenv("MASKGW_ADMIN_PORT", str(free_port()))
    monkeypatch.setenv("MASKGW_DATABASE_DSN", "private-dsn")
    events = FakeAdapter.events
    load = resources.load_resources
    configuration = composition._load_configuration
    resolve = composition.resolve_admin_settings
    compiled = load_config_bundle_text

    class Source:
        def get_raw(self, _name):
            events.append("flags")
            return "1"

    class Store(ObservableStore):
        @classmethod
        def open(cls, config_path, *, hooks=None):
            store = super().open(config_path, hooks=hooks)
            events.append("lock")
            return store

    def admin_settings():
        result = resolve()
        events.append("settings")
        return result

    def assets():
        result = load()
        events.append("assets")
        return result

    def config(*args, **kwargs):
        events.append("configuration")
        return configuration(*args, **kwargs)

    def compile_config(*args, **kwargs):
        result = compiled(*args, **kwargs)
        events.append("compiled")
        return result

    def mcp(_gateway):
        events.append("mcp:built")
        return FakeMcpServer()

    monkeypatch.setattr(process, "resolve_admin_settings", admin_settings)
    monkeypatch.setattr(composition, "load_resources", assets)
    monkeypatch.setattr(composition, "_load_configuration", config)
    monkeypatch.setattr(composition, "load_config_bundle_text", compile_config)
    monkeypatch.setattr(composition, "ConfigFileStore", Store)
    monkeypatch.setattr(composition, "PostgresAdapter", FakeAdapter)
    monkeypatch.setattr(composition, "AdminHttpServer", ObservableHttpServer)
    monkeypatch.setattr(composition, "build_mcp_server", mcp)
    before = thread_snapshot()
    stderr = io.StringIO()
    assert process.main(stderr=stderr, raw_settings=Source()) == 0
    assert events == [
        "flags",
        "settings",
        "assets",
        "configuration",
        "lock",
        "compiled",
        "runtime:connected",
        "http:listening",
        "mcp:built",
        "mcp:started",
        "mcp:stopped",
        "http:joined",
        "runtime:closed",
        "lock:released",
    ]
    assert thread_snapshot() == before
    with ConfigFileStore.open(config_file):
        pass
    assert stderr.getvalue().startswith(
        "maskgw: revision carregada: 0\nmaskgw: admin api escutando em 127.0.0.1:"
    )


def test_owned_bytes_survive_disk_changes_and_repr_is_boolean_only(
    monkeypatch, tmp_path, config_file
):
    assets = package_copy(tmp_path, monkeypatch)
    expected = resources.load_resources()
    app = compose(monkeypatch, config_file, admin_http=settings(), admin_ui_enabled=True)
    try:
        assert (
            repr(app)
            == "Application(revision=0, state='ready', admin=True, admin_http=True, admin_ui=True)"
        )
        owned = app.admin_ui_resources
        assert owned == expected
        assert owned is not None
        with pytest.raises(TypeError):
            cast(dict[str, bytes], owned)["index.html"] = b"changed"
        for name in ASSETS:
            (assets / name).write_bytes(b"private-marker")
        assert owned == expected
        with pytest.raises(Exception, match="Invalid presentation"):
            resources.load_resources()
    finally:
        app.close()
    assert (
        repr(app)
        == "Application(revision=0, state='closed', admin=True, admin_http=True, admin_ui=True)"
    )
    assert app.admin_ui_resources == expected


@pytest.mark.parametrize("failure", ["http_start", "mcp_build"])
def test_partial_failure_releases_thread_socket_runtime_and_lock(failure, monkeypatch, config_file):
    before = thread_snapshot()
    port = free_port()
    monkeypatch.setattr(composition, "PostgresAdapter", FakeAdapter)
    if failure == "http_start":
        FailingStartHttpServer.reset()
        monkeypatch.setattr(composition, "AdminHttpServer", FailingStartHttpServer)
    else:

        def fail(_gateway):
            raise RuntimeError("private-marker")

        monkeypatch.setattr(composition, "build_mcp_server", fail)
    with pytest.raises(RuntimeError):
        composition.build_application(
            config_path=config_file,
            conninfo="private-dsn",
            admin_http=settings(port),
            admin_ui_enabled=True,
        )
    assert thread_snapshot() == before
    assert FakeAdapter.instances[0].close_calls == 1
    with ConfigFileStore.open(config_file):
        pass
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.parametrize("enabled", [False, True])
def test_http_surface_remains_phase_seven_and_disabled_repr_exact(
    enabled, monkeypatch, config_file
):
    for name in ("MASKGW_DATABASE_DSN", "MASKGW_HMAC_KEY", "MASKGW_ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    if not enabled:

        def forbidden():
            raise AssertionError("UI off cannot read assets")

        monkeypatch.setattr(composition, "load_resources", forbidden)
    app = compose(monkeypatch, config_file, admin_http=settings(), admin_ui_enabled=enabled)
    try:
        assert app.admin_http is not None
        port = app.admin_http.port
        baseline = json.loads((ROOT / "tests/fixtures/phase7-ui-off.json").read_bytes())
        assert snapshots(port) == baseline["responses"]
        for path in (
            "/admin/ui",
            "/admin/ui/assets/ui.js",
            "/admin/ui/assets/ui.css",
            "/admin/ui/presentation.json",
        ):
            assert request(port, "GET", path, token=None).status == 401
            assert request(port, "GET", path, token=TOKEN).status == 404
        denied = request(
            port,
            "GET",
            "/admin/v1/status",
            token=TOKEN,
            headers={"Origin": f"http://127.0.0.1:{port}"},
        )
        assert denied.status == 403
        assert "content-security-policy" not in denied.headers
        if not enabled:
            assert app.admin_ui_resources is None
            assert (
                repr(app) == "Application(revision=0, state='ready', admin=True, admin_http=True)"
            )
    finally:
        app.close()


def test_stage_three_does_not_change_http_policy_or_secret_normalization():
    baseline = json.loads((ROOT / "tests/fixtures/phase7-ui-off.json").read_bytes())
    assert baseline["base"] == "d080886352920a663e8b0aa318761a083f54f7f7"
    for name, expected in baseline["protected_source_sha256"].items():
        # Git armazena LF; o checkout Windows pode usar CRLF nestas fontes antigas.
        source = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(source).hexdigest() == expected


@pytest.mark.parametrize("value", RAW_VALUES)
def test_process_uses_raw_flag_without_querying_secret_provider(value, monkeypatch):
    monkeypatch.setenv("MASKGW_ADMIN_ENABLED", "1")
    monkeypatch.setenv("MASKGW_ADMIN_TOKEN", TOKEN)
    if value is not None:
        monkeypatch.setenv(ADMIN_UI_ENABLED_ENV, value)
    resolved: list[bool] = []

    class App:
        revision = 0
        admin_http = None

        def run(self):
            pass

        def close(self):
            pass

    original = EnvSecretProvider.get

    def guarded_get(self, name):
        assert name != ADMIN_UI_ENABLED_ENV
        return original(self, name)

    def build(**kwargs):
        resolved.append(kwargs["admin_ui_enabled"])
        return App()

    monkeypatch.setattr(EnvSecretProvider, "get", guarded_get)
    monkeypatch.setattr(process, "build_application", build)
    stderr = io.StringIO()
    assert process.main(stderr=stderr) == 0
    assert resolved == [value == "1"]
    assert stderr.getvalue() == "maskgw: revision carregada: 0\n"
