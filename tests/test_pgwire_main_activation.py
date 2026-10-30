"""D-110: ativacao local do PGWire no `main` (autorizada em 2026-10-15).

Prova, sem PostgreSQL, sem rede externa e sem SQL:

- flag desligada (qualquer valor que nao seja `1` bruto): o caminho legado
  inteiro, com as leituras normais de UI e Admin, sem importar `maskgw.pgwire`
  nem o catalogo e sem ler os caminhos do catalogo;
- flag ligada: Admin e/ou UI ligados sao recusados ANTES de qualquer efeito;
  settings PGWire invalidos falham fechados; caminhos do catalogo resolvidos
  UMA vez a partir do `MASKGW_CONFIG` efetivo; store ou ancora ausentes,
  inseguros ou ambiguos recusados sem criar nada ao lado da config;
- erro sempre o `STARTUP_FAILURE` fixo, sem valor, caminho ou segredo; stdout
  intocado (e do MCP);
- composicao positiva: `build_application` recebe o catalogo e o PGWire
  explicitos, sem Admin; a linha do listener so sai com o bind confirmado;
- caminho REAL (catalogo vazio, legado e MCP duble, porta em loopback): o
  listener sobe, o fim do MCP (EOF) encerra tudo e libera a porta.

A prova com PG16 real (autenticacao SCRAM/-PLUS e `0A000` sem repasse da SQL
do cliente) e do lote seguinte, depois da revisao.
"""

from __future__ import annotations

import io
import os
import socket
import stat
import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest

import maskgw.bootstrap.application as application_module
import maskgw.bootstrap.main as main_module
import maskgw.datasource.store as store_module
from maskgw.bootstrap.settings import (
    DATASOURCE_ANCHOR_DIRECTORY,
    DATASOURCE_ANCHOR_ENV,
    DATASOURCE_ANCHOR_NAME,
    DATASOURCE_STORE_ENV,
    DATASOURCE_STORE_NAME,
    MappingRawSettings,
    resolve_catalog_paths,
)
from maskgw.datasource import CatalogStore
from maskgw.errors import ConfigError
from maskgw.pgwire.composition import PgwireComposition
from maskgw.pgwire.listener import ListenerState
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from tests.admin_http_support import TOKEN, free_port
from tests.datasource_runtime_support import KEY
from tests.pgwire_driver_support import watchdog
from tests.pgwire_listener_support import listener_threads

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FLAG = "MASKGW_PGWIRE_ENABLED"
PASSWORD = "senha-canario-ativacao-main"  # noqa: S105 - canario sintetico de teste
STARTUP_FAILURE = "maskgw: falha na inicializacao\n"
LEGACY_CONFIG = "database:\n  statement_timeout_ms: 2000\n  max_rows: 10\n"


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Nenhuma variavel MASKGW_*/PG* herdada chega ao `main`."""
    for name in list(os.environ):
        if name.startswith(("MASKGW_", "PG")):
            monkeypatch.delenv(name)
    with watchdog(120):
        yield
    assert not listener_threads(), [t.name for t in listener_threads()]


@pytest.fixture
def layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Config, store e ancora regulares no layout default (sem conteudo real)."""
    config = tmp_path / "conf" / "masking.yaml"
    config.parent.mkdir()
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    store = config.parent / DATASOURCE_STORE_NAME
    anchor = config.parent / DATASOURCE_ANCHOR_DIRECTORY / DATASOURCE_ANCHOR_NAME
    anchor.parent.mkdir()
    store.write_bytes(b"duble")
    anchor.write_bytes(b"duble")
    monkeypatch.setenv("MASKGW_CONFIG", str(config))
    return {"config": config, "store": store, "anchor": anchor}


def _enable(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    monkeypatch.setenv(FLAG, "1")
    monkeypatch.setenv("MASKGW_PGWIRE_USERNAME", "gwuser")
    monkeypatch.setenv("MASKGW_PGWIRE_PASSWORD", PASSWORD)
    for name, value in extra.items():
        monkeypatch.setenv(name, value)


class _FakeListener:
    def __init__(self, port: int | BaseException) -> None:
        self._port = port

    @property
    def port(self) -> int:
        if isinstance(self._port, BaseException):
            raise self._port
        return self._port


class _FakeApp:
    revision = 7
    admin_http = None

    def __init__(self, listener: _FakeListener | None = None, run_error: bool = False) -> None:
        self.pgwire_listener = listener
        self.run_error = run_error
        self.runs = 0
        self.closes = 0

    def run(self) -> None:
        self.runs += 1
        if self.run_error:
            msg = f"falha com {PASSWORD}"
            raise RuntimeError(msg)

    def close(self) -> None:
        self.closes += 1


class _Builds:
    """Duble de `build_application` no `main`: registra cada chamada."""

    def __init__(self, result: _FakeApp | BaseException) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _forbid_build(monkeypatch: pytest.MonkeyPatch) -> _Builds:
    builds = _Builds(AssertionError("build_application nao pode ser chamado"))
    monkeypatch.setattr(main_module, "build_application", builds)
    return builds


def _run_main(raw: Any = None) -> tuple[int, str]:
    sink = io.StringIO()
    code = main_module.main(stderr=sink, raw_settings=raw)
    return code, sink.getvalue()


class _RecordingRaw(MappingRawSettings):
    """`RawSettings` sobre um mapa, registrando cada nome lido."""

    def __init__(self, values: dict[str, str]) -> None:
        super().__init__(values)
        self.reads: list[str] = []

    def get_raw(self, name: str) -> str | None:
        self.reads.append(name)
        return super().get_raw(name)


# ---- constantes espelhadas do catalogo ---------------------------------------


def test_catalog_constants_mirror_the_store_module() -> None:
    assert DATASOURCE_STORE_ENV == store_module.STORE_ENV
    assert DATASOURCE_ANCHOR_ENV == store_module.ANCHOR_ENV
    assert store_module.DEFAULT_STORE_PATH.name == DATASOURCE_STORE_NAME
    assert DATASOURCE_ANCHOR_DIRECTORY == store_module._ANCHOR_DIRECTORY
    assert DATASOURCE_ANCHOR_NAME == store_module._ANCHOR_NAME


# ---- flag desligada: legado intacto -----------------------------------------


@pytest.mark.parametrize("flag", [None, "", "0", "true", "yes", " 1", "1 ", "01", "\uff11"])
def test_disabled_preserves_legacy_reads_and_composition(
    monkeypatch: pytest.MonkeyPatch, flag: str | None
) -> None:
    values = {} if flag is None else {FLAG: flag}
    # Caminhos do catalogo presentes e invalidos: desligado, nunca sao lidos.
    values |= {DATASOURCE_STORE_ENV: "", DATASOURCE_ANCHOR_ENV: "relativo"}
    raw = _RecordingRaw(values)
    app = _FakeApp()
    builds = _Builds(app)
    monkeypatch.setattr(main_module, "build_application", builds)
    code, err = _run_main(raw)
    assert code == 0
    # Leituras normais do legado: a flag e a flag de UI, nada do catalogo.
    assert raw.reads == [FLAG, "MASKGW_ADMIN_UI_ENABLED"]
    (call,) = builds.calls
    assert set(call) == {"config_path", "admin_http", "admin_ui_enabled"}
    assert call["admin_http"] is None
    assert call["admin_ui_enabled"] is False
    assert (app.runs, app.closes) == (1, 1)
    assert err == f"{main_module.REVISION_LOADED_PREFIX}7\n"


def test_disabled_keeps_normal_admin_ui_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Desligado, a UI sem Admin continua sendo o erro de sempre do legado.
    builds = _forbid_build(monkeypatch)
    code, err = _run_main(_RecordingRaw({"MASKGW_ADMIN_UI_ENABLED": "1"}))
    assert (code, err) == (1, STARTUP_FAILURE)
    assert builds.calls == []


@pytest.mark.parametrize("flag", [None, "0", " 1"])
def test_disabled_imports_neither_pgwire_nor_catalog(tmp_path: Path, flag: str | None) -> None:
    script = textwrap.dedent(
        """
        import sys
        import maskgw.bootstrap.main as m

        class App:
            revision = 0
            admin_http = None
            def run(self): pass
            def close(self): pass

        m.build_application = lambda **kw: App()
        rc = m.main()
        loaded = sorted(x for x in sys.modules if x.startswith("maskgw.pgwire")
                        or x in ("maskgw.datasource.store", "maskgw.runtime.datasource_service"))
        print(loaded, file=sys.stderr)
        sys.exit(rc)
        """
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MASKGW_", "PG"))}
    env |= {"PYTHONPATH": str(SRC), "MASKGW_CONFIG": str(tmp_path / "masking.yaml")}
    if flag is not None:
        env[FLAG] = flag
    result = subprocess.run(  # noqa: S603 - interpretador e codigo fixos do teste
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr.splitlines()[-1] == "[]"


def test_failure_reading_the_flag_is_a_fixed_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Broken:
        def get_raw(self, _name: str) -> str | None:
            msg = f"leitura com {PASSWORD}"
            raise RuntimeError(msg)

    builds = _forbid_build(monkeypatch)
    assert _run_main(Broken()) == (1, STARTUP_FAILURE)
    assert builds.calls == []


# ---- flag ligada: recusas antes de qualquer efeito --------------------------


@pytest.mark.parametrize(
    ("admin", "ui"),
    [("1", None), (" 1 ", None), (None, "1"), ("1", "1"), ("0", "1")],
    ids=["admin", "admin-com-espacos", "ui", "admin-e-ui", "ui-com-admin-desligado"],
)
def test_admin_or_ui_with_pgwire_is_refused_before_any_effect(
    monkeypatch: pytest.MonkeyPatch,
    layout: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
    admin: str | None,
    ui: str | None,
) -> None:
    _enable(monkeypatch)
    if admin is not None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", admin)
        monkeypatch.setenv("MASKGW_ADMIN_TOKEN", TOKEN)
    if ui is not None:
        monkeypatch.setenv("MASKGW_ADMIN_UI_ENABLED", ui)
    builds = _forbid_build(monkeypatch)
    before = sorted(p.name for p in layout["config"].parent.iterdir())
    assert _run_main() == (1, STARTUP_FAILURE)
    assert builds.calls == []
    assert sorted(p.name for p in layout["config"].parent.iterdir()) == before
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "admin_value", [None, "0", "", "true"], ids=["ausente", "zero", "vazio", "true"]
)
@pytest.mark.usefixtures("layout")
def test_admin_not_exactly_enabled_does_not_block_activation(
    monkeypatch: pytest.MonkeyPatch, admin_value: str | None
) -> None:
    _enable(monkeypatch)
    if admin_value is not None:
        monkeypatch.setenv("MASKGW_ADMIN_ENABLED", admin_value)
    builds = _Builds(_FakeApp(_FakeListener(6432)))
    monkeypatch.setattr(main_module, "build_application", builds)
    code, _ = _run_main()
    assert code == 0
    assert len(builds.calls) == 1


@pytest.mark.parametrize(
    ("changes", "removed"),
    [
        ({}, ("MASKGW_PGWIRE_USERNAME",)),
        ({}, ("MASKGW_PGWIRE_PASSWORD",)),
        ({"MASKGW_PGWIRE_BIND": "10.0.0.5"}, ()),  # externo sem TLS
        ({"MASKGW_PGWIRE_BIND": "nome invalido!"}, ()),
        ({"MASKGW_PGWIRE_PORT": "0"}, ()),
        ({"MASKGW_PGWIRE_PORT": "70000"}, ()),
        ({"MASKGW_PGWIRE_PORT": "abc"}, ()),
        ({"MASKGW_PGWIRE_MAX_SESSIONS": "0"}, ()),
        ({"MASKGW_PGWIRE_IDLE_TIMEOUT_MS": "01"}, ()),
        ({"MASKGW_PGWIRE_TLS_CERT": "so-o-cert.pem"}, ()),
    ],
)
def test_invalid_pgwire_settings_fail_closed_before_catalog(
    monkeypatch: pytest.MonkeyPatch,
    layout: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
    changes: dict[str, str],
    removed: tuple[str, ...],
) -> None:
    _enable(monkeypatch, **changes)
    for name in removed:
        monkeypatch.delenv(name)
    builds = _forbid_build(monkeypatch)
    before = sorted(p.name for p in layout["config"].parent.iterdir())
    code, err = _run_main()
    assert (code, err) == (1, STARTUP_FAILURE)
    assert PASSWORD not in err
    assert builds.calls == []
    assert sorted(p.name for p in layout["config"].parent.iterdir()) == before
    assert capsys.readouterr().out == ""


# ---- caminhos do catalogo ----------------------------------------------------


def _paths(values: dict[str, str], config: str | Path) -> tuple[Path, Path]:
    return resolve_catalog_paths(MappingRawSettings(values), config)


def test_default_store_is_next_to_the_effective_config(tmp_path: Path) -> None:
    config = tmp_path / "x" / "masking.yaml"
    store, anchor = _paths({}, config)
    assert store == (tmp_path / "x" / "datasources.store").resolve()
    assert anchor == (tmp_path / "x" / ".maskgw-anchor" / "datasources.anchor").resolve()


def test_relative_default_config_never_doubles_the_config_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store, anchor = _paths({}, "config/masking.yaml")
    assert store == Path(os.path.abspath(tmp_path / "config" / "datasources.store"))
    assert "config" + os.sep + "config" not in str(store)
    assert anchor.parent.parent == store.parent


def test_explicit_absolute_store_stays_and_anchor_follows_it(tmp_path: Path) -> None:
    target = tmp_path / "outro" / "cat.store"
    store, anchor = _paths({DATASOURCE_STORE_ENV: str(target)}, tmp_path / "c" / "m.yaml")
    assert store == Path(os.path.abspath(target))
    assert anchor == Path(os.path.abspath(target.parent / ".maskgw-anchor" / "datasources.anchor"))


@pytest.mark.parametrize(
    "relative",
    ["cat.store", os.path.join("sub", "cat.store"), os.path.join("..", "irmao", "cat.store")],
)
def test_explicit_relative_store_is_relative_to_the_config_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    other = tmp_path / "cwd-diferente"
    other.mkdir()
    monkeypatch.chdir(other)  # o cwd nao influencia
    config = tmp_path / "conf" / "masking.yaml"
    store, _ = _paths({DATASOURCE_STORE_ENV: relative}, config)
    assert store == Path(os.path.abspath(config.parent / relative))


def test_explicit_absolute_anchor_is_kept(tmp_path: Path) -> None:
    anchor_target = tmp_path / "privado" / "a.anchor"
    _, anchor = _paths({DATASOURCE_ANCHOR_ENV: str(anchor_target)}, tmp_path / "m.yaml")
    assert anchor == Path(os.path.abspath(anchor_target))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (DATASOURCE_STORE_ENV, ""),
        (DATASOURCE_STORE_ENV, "   "),
        (DATASOURCE_STORE_ENV, "a\x00b"),
        (DATASOURCE_ANCHOR_ENV, ""),
        (DATASOURCE_ANCHOR_ENV, "   "),
        (DATASOURCE_ANCHOR_ENV, "a\x00b"),
        (DATASOURCE_ANCHOR_ENV, "relativa.anchor"),
        (DATASOURCE_ANCHOR_ENV, os.path.join("sub", "a.anchor")),
    ],
)
def test_invalid_or_relative_anchor_and_empty_store_are_refused(
    tmp_path: Path, name: str, value: str
) -> None:
    with pytest.raises(ConfigError) as caught:
        _paths({name: value}, tmp_path / "m.yaml")
    # Mensagens fixas: o nome da variavel, nunca o valor recebido.
    assert str(caught.value) in {
        f"caminho invalido em {name}",
        f"{DATASOURCE_ANCHOR_ENV} precisa ser um caminho absoluto",
    }


@pytest.mark.parametrize("name", [DATASOURCE_STORE_ENV, DATASOURCE_ANCHOR_ENV])
def test_rooted_or_drive_relative_paths_are_ambiguous(tmp_path: Path, name: str) -> None:
    # `\x` (raiz sem drive) e `C:x` (drive sem raiz) no Windows; no POSIX so
    # um caminho com raiz e absoluto, e um nome com `:` e relativo comum.
    if os.name == "nt":
        for value in ("\\sem-drive\\x.store", "C:sem-raiz.store"):
            with pytest.raises(ConfigError):
                _paths({name: value}, tmp_path / "m.yaml")
    else:
        store, anchor = _paths({name: "/abs/x.file"}, tmp_path / "m.yaml")
        assert (store if name == DATASOURCE_STORE_ENV else anchor) == Path("/abs/x.file")


# ---- recusa antecipada de store/ancora ausentes ou inseguros --------------


@pytest.mark.parametrize("missing", ["store", "anchor"])
def test_missing_store_or_anchor_is_refused_without_creating_anything(
    monkeypatch: pytest.MonkeyPatch,
    layout: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    layout[missing].unlink()
    _enable(monkeypatch)
    builds = _forbid_build(monkeypatch)
    snapshot = sorted(
        str(p.relative_to(layout["config"].parent)) for p in layout["config"].parent.rglob("*")
    )
    assert _run_main() == (1, STARTUP_FAILURE)
    assert builds.calls == []
    assert (
        sorted(
            str(p.relative_to(layout["config"].parent)) for p in layout["config"].parent.rglob("*")
        )
        == snapshot
    )
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("target", ["store", "anchor"])
def test_directory_in_place_of_a_catalog_file_is_refused(
    monkeypatch: pytest.MonkeyPatch, layout: dict[str, Path], target: str
) -> None:
    layout[target].unlink()
    layout[target].mkdir()
    _enable(monkeypatch)
    builds = _forbid_build(monkeypatch)
    assert _run_main() == (1, STARTUP_FAILURE)
    assert builds.calls == []


def test_symlink_catalog_file_is_refused_by_the_early_check(tmp_path: Path) -> None:
    class _Link:
        def lstat(self) -> os.stat_result:
            return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    with pytest.raises(ConfigError) as caught:
        main_module._require_existing_regular_file(cast(Path, _Link()))
    assert str(caught.value) == "catalogo de datasources ausente ou inseguro"
    # Symlink real, quando a instalacao permite criar um.
    real = tmp_path / "real.store"
    real.write_bytes(b"x")
    link = tmp_path / "link.store"
    try:
        link.symlink_to(real)
    except OSError:
        return  # o duble acima ja cobriu a regra
    with pytest.raises(ConfigError):
        main_module._require_existing_regular_file(link)


# ---- composicao positiva (duble) ---------------------------------------------


def test_enabled_passes_explicit_catalog_and_pgwire_without_admin(
    monkeypatch: pytest.MonkeyPatch, layout: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _enable(monkeypatch, MASKGW_PGWIRE_PORT="6543", MASKGW_PGWIRE_MAX_SESSIONS="40")
    app = _FakeApp(_FakeListener(6543))
    builds = _Builds(app)
    monkeypatch.setattr(main_module, "build_application", builds)
    code, err = _run_main()
    assert code == 0
    (call,) = builds.calls
    assert set(call) == {"config_path", "datasource_catalog", "pgwire"}
    catalog = call["datasource_catalog"]
    assert isinstance(catalog, DatasourceCatalogSettings)
    assert catalog.store_path is not None and catalog.anchor_path is not None
    assert Path(catalog.store_path) == layout["store"].resolve()
    assert Path(catalog.anchor_path) == layout["anchor"].resolve()
    assert catalog.resolver is None and catalog.adapter_factory is None and catalog.verifier is None
    composition = call["pgwire"]
    assert isinstance(composition, PgwireComposition)
    assert composition.resolved_addresses is None and composition.test_port is None
    assert composition.settings.username == "gwuser"
    assert composition.settings.port == 6543
    assert composition.settings.max_sessions == 40
    assert err == (
        f"{main_module.REVISION_LOADED_PREFIX}7\n"
        f"{main_module.PGWIRE_LISTENING_PREFIX}127.0.0.1:6543\n"
    )
    assert PASSWORD not in err
    assert (app.runs, app.closes) == (1, 1)
    assert capsys.readouterr().out == ""


def test_catalog_paths_are_read_once_and_passed_explicitly(
    monkeypatch: pytest.MonkeyPatch, layout: dict[str, Path]
) -> None:
    values = {
        FLAG: "1",
        DATASOURCE_STORE_ENV: str(layout["store"]),
        DATASOURCE_ANCHOR_ENV: str(layout["anchor"]),
    }
    _enable(monkeypatch)  # a senha vem do secret provider (ambiente)
    raw = _RecordingRaw(values | {"MASKGW_PGWIRE_USERNAME": "gwuser"})
    builds = _Builds(_FakeApp(_FakeListener(1)))
    monkeypatch.setattr(main_module, "build_application", builds)
    assert _run_main(raw)[0] == 0
    assert raw.reads.count(DATASOURCE_STORE_ENV) == 1
    assert raw.reads.count(DATASOURCE_ANCHOR_ENV) == 1
    (call,) = builds.calls
    assert call["datasource_catalog"].store_path is not None
    assert call["datasource_catalog"].anchor_path is not None


@pytest.mark.parametrize(
    ("bind", "extra", "line"),
    [
        ("::1", {}, "maskgw: pgwire escutando em [::1]:7001\n"),
        ("127.0.0.1", {}, "maskgw: pgwire escutando em 127.0.0.1:7001\n"),
        (
            "gateway.test",
            {"MASKGW_PGWIRE_TLS_CERT": "c.pem", "MASKGW_PGWIRE_TLS_KEY": "k.pem"},
            "maskgw: pgwire escutando na porta 7001\n",
        ),
    ],
)
@pytest.mark.usefixtures("layout")
def test_listener_line_uses_numeric_host_or_port_only(
    monkeypatch: pytest.MonkeyPatch,
    bind: str,
    extra: dict[str, str],
    line: str,
) -> None:
    _enable(monkeypatch, MASKGW_PGWIRE_BIND=bind, **extra)
    monkeypatch.setattr(main_module, "build_application", _Builds(_FakeApp(_FakeListener(7001))))
    code, err = _run_main()
    assert code == 0
    assert err.endswith(line)
    assert "gateway.test" not in err


@pytest.mark.usefixtures("layout")
def test_unreadable_listener_port_closes_and_fails_without_partial_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    app = _FakeApp(_FakeListener(RuntimeError(f"porta com {PASSWORD}")))
    monkeypatch.setattr(main_module, "build_application", _Builds(app))
    assert _run_main() == (1, STARTUP_FAILURE)
    assert (app.runs, app.closes) == (0, 1)


@pytest.mark.usefixtures("layout")
def test_composition_failure_is_fixed_and_never_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    builds = _Builds(ConfigError(f"detalhe interno {PASSWORD}"))
    monkeypatch.setattr(main_module, "build_application", builds)
    code, err = _run_main()
    assert (code, err) == (1, STARTUP_FAILURE)
    (call,) = builds.calls  # uma unica tentativa, a moderna
    assert "pgwire" in call and "datasource_catalog" in call


@pytest.mark.usefixtures("layout")
def test_runtime_failure_after_activation_is_the_fixed_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    app = _FakeApp(_FakeListener(6432), run_error=True)
    monkeypatch.setattr(main_module, "build_application", _Builds(app))
    code, err = _run_main()
    assert code == 1
    assert err.endswith(main_module.RUNTIME_FAILURE)
    assert PASSWORD not in err
    assert (app.runs, app.closes) == (1, 1)


# ---- caminho REAL: catalogo vazio, legado/MCP duble, loopback ----------------


class _LegacyAdapter:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass


class _ObservingMcp:
    """MCP duble: observa o listener vivo e devolve (equivale ao EOF do stdio)."""

    seen: ClassVar[list[object]] = []

    def run(self, transport: str = "stdio", **_kwargs: Any) -> None:
        del transport
        _ObservingMcp.seen.append("run")


def _bound(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
        return False


def test_real_activation_starts_the_listener_and_mcp_eof_ends_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "conf" / "masking.yaml"
    config.parent.mkdir()
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    store = config.parent / DATASOURCE_STORE_NAME
    anchor = config.parent / DATASOURCE_ANCHOR_DIRECTORY / DATASOURCE_ANCHOR_NAME
    with CatalogStore.initialize(store, anchor_path=anchor, master_key=KEY):
        pass  # catalogo vazio: nenhum upstream e verificado
    port = free_port()
    _enable(monkeypatch, MASKGW_PGWIRE_PORT=str(port))
    monkeypatch.setenv("MASKGW_CONFIG", str(config))
    monkeypatch.setenv("MASKGW_DATASOURCE_MASTER_KEY", KEY)
    monkeypatch.setenv("MASKGW_DATABASE_DSN", "host=127.0.0.1 dbname=duble")
    monkeypatch.setattr(application_module, "PostgresAdapter", _LegacyAdapter)
    observed: list[tuple[str, bool, object]] = []

    class _Mcp(_ObservingMcp):
        def run(self, transport: str = "stdio", **kwargs: Any) -> None:
            listener = holder["app"].pgwire_listener
            observed.append(("listener", _bound(port), listener.status().state))
            super().run(transport, **kwargs)

    holder: dict[str, Any] = {}
    original_build = application_module.build_application

    def build(**kwargs: Any) -> Any:
        app = original_build(**kwargs)
        holder["app"] = app
        return app

    monkeypatch.setattr(main_module, "build_application", build)
    monkeypatch.setattr(application_module, "build_mcp_server", lambda _gateway: cast(Any, _Mcp()))
    before = {t.ident for t in threading.enumerate()}
    code, err = _run_main()
    assert code == 0, err
    assert err == (
        f"{main_module.REVISION_LOADED_PREFIX}0\n"
        f"{main_module.PGWIRE_LISTENING_PREFIX}127.0.0.1:{port}\n"
    )
    assert observed == [("listener", True, ListenerState.RUNNING)]
    app = holder["app"]
    assert app.pgwire_listener.status().state is ListenerState.STOPPED
    assert not _bound(port), "porta liberada depois do fim do MCP"
    assert not listener_threads()
    assert {t.ident for t in threading.enumerate()} - before == set()
    assert capsys.readouterr().out == ""
    # Nada novo foi criado no diretorio da config alem dos sidecars do catalogo.
    names = sorted(p.name for p in config.parent.iterdir())
    assert DATASOURCE_STORE_NAME in names


def test_disabled_keeps_previous_behavior_when_stderr_metadata_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Decisao registrada: a contencao de falha de metadata vale SO para a
    # ativacao; o legado (flag desligada) mantem o comportamento anterior.
    app = _FakeApp()
    monkeypatch.setattr(main_module, "build_application", _Builds(app))

    class Broken(io.StringIO):
        def write(self, _value: str) -> int:
            msg = "stderr quebrado"
            raise OSError(msg)

    with pytest.raises(OSError, match="stderr quebrado"):
        main_module.main(stderr=Broken(), raw_settings=_RecordingRaw({}))
    assert (app.runs, app.closes) == (0, 0)
