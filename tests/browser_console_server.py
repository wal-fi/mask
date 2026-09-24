"""Harness privado do console v2 somente leitura (Fase 9, Etapa 5).

Composition root real, PostgreSQL real para o runtime legado, catalogo cifrado
real com datasources FICTICIOS e adapters duble para o upstream (nenhuma
conexao a banco de negocio). As mesmas sondas do harness da Fase 8: nada de
token/DSN em log, nenhum metodo alem de GET/HEAD vindo do navegador e nenhuma
auditoria administrativa.

Comandos por stdin, so do harness: `remove` retira um datasource pelo
coordenador (estado "nao existe mais") e `block` provoca uma falha de
persistencia real no catalogo (estado "bloqueado ate reinicio").
"""

import logging
import os
import sys
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from maskgw.admin.http.settings import build
from maskgw.bootstrap.application import build_application
from maskgw.datasource import CatalogHooks, CatalogStore, CatalogWriteError, CrashPoint
from maskgw.datasource.models import DatasourceDraft, DatasourcePolicy, DestinationPolicy
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import free_port
from tests.browser_server import MemoryProbe, network_probe
from tests.datasource_runtime_support import KEY, FakeFactory

HMAC = "chave-de-teste-para-hmac-com-tamanho-suficiente"
UPSTREAM_SECRET = "upstream-browser-canary-6d1f"  # noqa: S105 - marcador sintetico
HOSTS = {
    "db-crm.example.internal": ("10.40.0.11",),
    "db-fin.example.internal": ("10.40.0.12",),
    "db-legado.example.internal": ("10.40.0.13",),
}
POLICY = {
    "masking": [
        {"match": "cpf", "transformer": "hmac_sha256"},
        {"match": "email", "transformer": "fixed", "config": {"value": "[EMAIL]"}},
    ],
    "exceptions": [{"match": "tipo_cpf"}],
    "database": {"statement_timeout_ms": 5000, "max_rows": 200},
    "sql": {"allowed_pg_functions": [], "denied_functions": ["dblink_exec"]},
}


class ConsoleProbe(MemoryProbe):
    """A sonda da Fase 8, que tambem procura a senha upstream ficticia."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.leaked |= UPSTREAM_SECRET in repr(record.__dict__)


def resolver(host: str, _port: int) -> tuple[str, ...]:
    return HOSTS.get(host, ("10.40.0.99",))


class Crash:
    def __init__(self) -> None:
        self.armed = False

    def __call__(self, point: CrashPoint) -> None:
        if self.armed and point == CrashPoint.AFTER_JOURNAL_FSYNC:
            self.armed = False
            msg = "falha sintetica do harness"
            raise CatalogWriteError(msg)


def catalog(directory: Path, crash: Crash) -> DatasourceCatalogSettings:
    store_path = directory / "catalog" / "datasources.store"
    store_path.parent.mkdir()
    anchor = directory / "catalog-anchor" / "datasources.anchor"
    records = (
        []
        if os.environ.get("MASKGW_BROWSER_CATALOG") == "empty"
        else [
            ("crm-demo", "CRM de demonstração", "db-crm.example.internal", True),
            ("financeiro-demo", "Financeiro de demonstração", "db-fin.example.internal", True),
            ("legado-demo", "Legado desabilitado", "db-legado.example.internal", False),
        ]
    )
    with CatalogStore.initialize(store_path, anchor_path=anchor, master_key=KEY) as store:
        for alias, name, host, enabled in records:
            store.create(
                DatasourceDraft(
                    alias=alias,
                    display_name=name,
                    host=host,
                    port=5432,
                    database="app_demo",
                    username="gateway_demo",
                    enabled=enabled,
                    policy=DatasourcePolicy.from_mapping(POLICY),
                    destination_policy=DestinationPolicy(),
                ),
                UPSTREAM_SECRET,
                resolver=resolver,
            )
    # O hook de crash precisa estar no store aberto pelo composition root.
    original_open = CatalogStore.open

    def open_with_hooks(*args: object, **kwargs: object) -> CatalogStore:
        kwargs["hooks"] = CatalogHooks(after_point=crash)
        return original_open(*args, **kwargs)  # type: ignore[arg-type]

    CatalogStore.open = open_with_hooks  # type: ignore[method-assign]
    return DatasourceCatalogSettings(
        store_path=store_path,
        anchor_path=anchor,
        resolver=resolver,
        adapter_factory=FakeFactory(),
    )


def main() -> int:
    app = None
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        dsn = os.environ["MASKGW_TEST_DSN"]
        token = os.environ["MASKGW_BROWSER_TOKEN"]
        os.environ["MASKGW_BROWSER_READ_ONLY"] = "1"
        probe = ConsoleProbe(token, dsn)
        root.handlers = [probe]
        root.setLevel(logging.INFO)
        network_probe(probe)
        crash = Crash()
        with TemporaryDirectory(prefix="maskgw-console-") as name:
            directory = Path(name)
            config = directory / "masking.yaml"
            config.write_text("masking: []\nexceptions: []\n", encoding="utf-8")
            try:
                app = build_application(
                    config_path=config,
                    conninfo=dsn,
                    secrets=MappingSecretProvider(
                        {"MASKGW_DATASOURCE_MASTER_KEY": KEY, "MASKGW_HMAC_KEY": HMAC}
                    ),
                    admin_http=build(token=token, host="127.0.0.1", port=free_port()),
                    admin_ui_enabled=True,
                    datasource_catalog=catalog(directory, crash),
                )
                assert app.admin_http is not None and app.datasources is not None
                runtime = app.datasources
                print(app.admin_http.port, flush=True)
                for command in sys.stdin:
                    order = command.strip()
                    if order == "remove":
                        record = runtime.store.by_alias("financeiro-demo")
                        runtime.service.remove(
                            record.id, expected_datasource_revision=record.revision
                        )
                        print("ok", flush=True)
                    elif order == "block":
                        record = runtime.store.by_alias("crm-demo")
                        crash.armed = True
                        with suppress(CatalogWriteError):
                            runtime.service.set_enabled(
                                record.id, False, expected_datasource_revision=record.revision
                            )
                        assert runtime.store.requires_reopen
                        print("ok", flush=True)
                    else:
                        break
            finally:
                if app is not None:
                    app.close()
            assert not probe.leaked and not probe.failed and probe.admin_events == 0
    except BaseException:
        sys.stderr.write("Browser console harness failed.\n")
        return 1
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
