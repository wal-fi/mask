"""Harness privado do console v2 somente leitura (Fase 9, Etapa 5).

Composition root real, PostgreSQL real para o runtime legado, catalogo cifrado
real com datasources FICTICIOS e adapters duble para o upstream (nenhuma
conexao a banco de negocio). As mesmas sondas do harness da Fase 8: nada de
token/DSN em log, nenhum metodo alem de GET/HEAD vindo do navegador e nenhuma
auditoria administrativa.

Comandos por stdin, so do harness: `remove` retira um datasource pelo
coordenador (estado "nao existe mais") e `block` provoca uma falha de
persistencia real no catalogo (estado "bloqueado ate reinicio").

Modo de escrita (Fase 9, Etapa 6, `MASKGW_BROWSER_WRITE=1`): o navegador pode
escrever pelas nove rotas v2; a sonda aceita so auditoria `datasource_*` e
procura, alem do segredo upstream, as senhas que os testes digitam. Comandos:
`connect-fail`, `capability` e `heal` (candidato), `fail-next` (falha de
persistencia antes do replace) e `uncertain` (falha depois do replace) na
proxima escrita; `expect-present|absent|enabled|disabled:<alias>` e
`expect-secret:<senha>` conferem o estado real e a senha usada pelo candidato.
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
from maskgw.runtime.datasource_service import DatasourceCatalogSettings, DatasourceRuntime
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import free_port
from tests.browser_server import MemoryProbe, network_probe
from tests.datasource_runtime_support import KEY, FakeFactory, capability_failure

HMAC = "chave-de-teste-para-hmac-com-tamanho-suficiente"
UPSTREAM_SECRET = "upstream-browser-canary-6d1f"  # noqa: S105 - marcador sintetico
#: Senhas que os testes de escrita digitam no navegador (marcadores sinteticos).
WRITE_SECRETS = ("senha-cadastro-6e1a", "senha-rotacao-9c3b")
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
        rendered = repr(record.__dict__)
        self.leaked |= any(secret in rendered for secret in (UPSTREAM_SECRET, *WRITE_SECRETS))
        if os.environ.get("MASKGW_BROWSER_WRITE") == "1" and record.name == "maskgw.audit":
            # So metadata da auditoria da v2 (D-095); nada alem de datasource_*.
            self.datasource_events += 1
            fields = getattr(record, "maskgw", {})
            self.failed |= record.getMessage() != "admin" or not str(
                fields.get("operation", "")
            ).startswith("datasource_")
            return
        super().emit(record)

    datasource_events = 0


def resolver(host: str, _port: int) -> tuple[str, ...]:
    return HOSTS.get(host, ("10.40.0.99",))


class Crash:
    def __init__(self) -> None:
        self.armed = False
        self.point = CrashPoint.AFTER_JOURNAL_FSYNC

    def __call__(self, point: CrashPoint) -> None:
        if self.armed and point == self.point:
            self.armed = False
            msg = "falha sintetica do harness"
            raise CatalogWriteError(msg)


def catalog(directory: Path, crash: Crash, factory: FakeFactory) -> DatasourceCatalogSettings:
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
        adapter_factory=factory,
    )


def read_command(order: str, runtime: DatasourceRuntime, crash: Crash) -> bool:
    """Comandos da Etapa 5: remover pelo coordenador e bloquear o catalogo."""
    if order == "remove":
        record = runtime.store.by_alias("financeiro-demo")
        runtime.service.remove(record.id, expected_datasource_revision=record.revision)
        return True
    if order == "block":
        record = runtime.store.by_alias("crm-demo")
        crash.armed = True
        with suppress(CatalogWriteError):
            runtime.service.set_enabled(
                record.id, False, expected_datasource_revision=record.revision
            )
        assert runtime.store.requires_reopen
        return True
    return False


def write_command(order: str, store: CatalogStore, crash: Crash, factory: FakeFactory) -> bool:
    """Comandos do modo de escrita; `False` encerra o harness como comando desconhecido."""
    if order in {"connect-fail", "capability", "heal"}:
        factory.connect_failure = (
            RuntimeError("falha sintetica do harness")
            if order == "connect-fail"
            else capability_failure()
            if order == "capability"
            else None
        )
        return True
    if order in {"fail-next", "uncertain"}:
        # Antes do replace: CATALOG_WRITE_ERROR; depois dele: resultado incerto.
        crash.point = (
            CrashPoint.AFTER_JOURNAL_FSYNC
            if order == "fail-next"
            else CrashPoint.AFTER_STORE_REPLACE
        )
        crash.armed = True
        return True
    if order.startswith("expect-secret:"):
        wanted = order.split(":", 1)[1]
        assert wanted in WRITE_SECRETS
        assert any("password=" + wanted in adapter.conninfo for adapter in factory.adapters)
        return True
    if order.startswith("expect-"):
        state, alias = order.removeprefix("expect-").split(":", 1)
        records = {r.alias: r for r in store.snapshot().datasources}
        if state == "absent":
            assert alias not in records
        else:
            assert alias in records
            if state in {"enabled", "disabled"}:
                assert records[alias].enabled is (state == "enabled")
        return True
    return False


def main() -> int:
    app = None
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        dsn = os.environ["MASKGW_TEST_DSN"]
        token = os.environ["MASKGW_BROWSER_TOKEN"]
        writing = os.environ.get("MASKGW_BROWSER_WRITE") == "1"
        if not writing:
            os.environ["MASKGW_BROWSER_READ_ONLY"] = "1"
        probe = ConsoleProbe(token, dsn)
        root.handlers = [probe]
        root.setLevel(logging.INFO)
        network_probe(probe)
        crash = Crash()
        factory = FakeFactory()
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
                    datasource_catalog=catalog(directory, crash, factory),
                )
                assert app.admin_http is not None and app.datasources is not None
                runtime = app.datasources
                print(app.admin_http.port, flush=True)
                for command in sys.stdin:
                    order = command.strip()
                    if not (
                        read_command(order, runtime, crash)
                        or (writing and write_command(order, runtime.store, crash, factory))
                    ):
                        break
                    print("ok", flush=True)
            finally:
                if app is not None:
                    app.close()
            assert not probe.leaked and not probe.failed and probe.admin_events == 0
            if not writing:
                assert probe.datasource_events == 0
    except BaseException:
        sys.stderr.write("Browser console harness failed.\n")
        return 1
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
