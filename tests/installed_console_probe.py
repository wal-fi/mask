"""Run explicitly with isolated installed Python; never included in the package.

Phase 9, Stage 5: the installed package serves the read-only console v2 without
the checkout or Node. The composition root is built with a real encrypted
catalog of fictitious datasources and stub upstream adapters; every request is
a GET, and the private presentation is format 2 with only reads under the
second prefix. Phase 9, Stage 6: besides the four reads, exactly the nine
approved writes (D-093/D-103), checked against the installed router.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path

from maskgw.admin.http.settings import build
from maskgw.admin.http.v2.routes import V2_READ_PATHS, V2_WRITE_ROUTES
from maskgw.admin.ui.protocol import V2_WRITES
from maskgw.admin.ui.resources import load_resources
from maskgw.bootstrap.application import build_application
from maskgw.datasource import CatalogStore
from maskgw.datasource.models import DatasourceDraft, DatasourcePolicy
from maskgw.runtime.datasource_service import DatasourceCatalogSettings
from maskgw.secretsource import MappingSecretProvider
from tests.admin_http_support import free_port, request
from tests.datasource_runtime_support import KEY, FakeFactory
from tests.installed_support import verify_environment

HMAC = "chave-de-teste-para-hmac-com-tamanho-suficiente"


def resolver(_host: str, _port: int) -> tuple[str, ...]:
    return ("10.40.0.21",)


def main() -> None:
    verify_environment()
    data = load_resources()
    presentation = json.loads(data["presentation.json"])
    assert presentation["format"] == 2
    second = [c for c in presentation["calls"] if c["path"].startswith("/admin/v2/")]
    reads = [c for c in second if c["method"] == "GET"]
    writes = [c for c in second if c["method"] != "GET"]
    assert {c["path"] for c in reads} == set(V2_READ_PATHS) and len(reads) == 4
    assert all(c["operation"] == "read" and c["input"] is None for c in reads)
    assert {(c["method"], c["path"], c["operation"]) for c in writes} == set(V2_WRITES)
    assert {(c["method"], c["path"]) for c in writes} == {(m, p) for p, m in V2_WRITE_ROUTES}
    assert len(writes) == 9
    token = secrets.token_hex(32)
    with tempfile.TemporaryDirectory(prefix="maskgw-installed-console-") as name:
        root = Path(name)
        config = root / "masking.yaml"
        config.write_text("masking: []\nexceptions: []\n", encoding="utf-8")
        store = root / "catalog" / "datasources.store"
        store.parent.mkdir()
        anchor = root / "anchor" / "datasources.anchor"
        with CatalogStore.initialize(store, anchor_path=anchor, master_key=KEY) as catalog:
            catalog.create(
                DatasourceDraft(
                    alias="crm-demo",
                    display_name="CRM de demonstração",
                    host="db-crm.example.internal",
                    port=5432,
                    database="app_demo",
                    username="gateway_demo",
                    policy=DatasourcePolicy.from_mapping(
                        {"masking": [{"match": "cpf", "transformer": "hmac_sha256"}]}
                    ),
                ),
                "installed-canary-secret",
                resolver=resolver,
            )
        port = free_port()
        app = build_application(
            config_path=config,
            conninfo=os.environ["MASKGW_TEST_DSN"],
            secrets=MappingSecretProvider(
                {"MASKGW_DATASOURCE_MASTER_KEY": KEY, "MASKGW_HMAC_KEY": HMAC}
            ),
            admin_http=build(token=token, host="127.0.0.1", port=port),
            admin_ui_enabled=True,
            datasource_catalog=DatasourceCatalogSettings(
                store_path=store,
                anchor_path=anchor,
                resolver=resolver,
                adapter_factory=FakeFactory(),
            ),
        )
        try:
            ui = request(port, path="/admin/ui", token=None)
            assert ui.status == 200 and ui.body == data["index.html"]
            served = request(port, path="/admin/ui/presentation.json", token=token)
            assert served.status == 200 and served.body == data["presentation.json"]
            for path in ("/admin/v2/status", "/admin/v2/datasources"):
                reply = request(port, path=path, token=token)
                assert reply.status == 200, path
                assert "installed-canary-secret" not in reply.text()
            listing = request(port, path="/admin/v2/datasources", token=token).json()
            (row,) = listing["datasources"]
            for path in (
                "/admin/v2/datasources/" + row["id"],
                "/admin/v2/datasources/" + row["id"] + "/policy",
            ):
                reply = request(port, path=path, token=token)
                assert reply.status == 200 and "installed-canary-secret" not in reply.text()
        finally:
            app.close()
    verify_environment()
    print("Installed console v2: format 2, four reads, nine approved writes, no secret: passed.")


if __name__ == "__main__":
    main()
