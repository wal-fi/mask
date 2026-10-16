"""D-110: ativacao local do PGWire pelo ponto de entrada REAL (`python -I -B -m maskgw`).

Integracao com o PostgreSQL de `MASKGW_TEST_DSN` (descartavel, em loopback).
Nada aqui e duble do `main` nem do `build_application`:

- o catalogo e provisionado EXPLICITAMENTE pelo harness, pela API interna
  (`CatalogStore.initialize` + `create`), nunca pelo startup; o datasource
  aponta para um banco DEDICADO criado no mesmo servidor de teste;
- o processo roda com ambiente reconstruido (sem `MASKGW_*`/`PG*` herdados,
  sem `PYTHONPATH`), MCP stdio real com o stdin MANTIDO aberto durante os
  handshakes; o fim (EOF do stdin) encerra o processo e libera a porta;
- SCRAM-SHA-256 e SCRAM-SHA-256-PLUS com `verify-full` contra uma CA de teste;
  senha e alias errados falham de forma uniforme;
- SQL de cliente recebe `0A000`. Prova OBSERVAVEL de que nada foi repassado:
  o contador cumulativo `pg_stat_database.sessions` do banco do datasource nao
  muda durante as sessoes PGWire (nenhuma sessao upstream nova), com
  contraprova positiva (uma conexao direta faz o contador subir). As
  consultas de capability do startup sao esperadas e acontecem ANTES da
  linha de base; nao se afirma ausencia global de SQL no upstream;
- recusas reais (Admin junto, catalogo ausente/adulterado, chave errada, TLS
  invalido) saem com o `STARTUP_FAILURE` fixo, sem porta, sem segredo e sem
  queda para o legado. Nenhum bind externo.
"""

from __future__ import annotations

import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from maskgw.datasource import CatalogStore
from maskgw.datasource.models import DatasourceDraft, DestinationPolicy
from tests.pgwire_support import make_certificate

pytestmark = pytest.mark.integration

STARTUP_FAILURE = "maskgw: falha na inicializacao\n"
REVISION_PREFIX = "maskgw: revision carregada: "
LISTENING_PREFIX = "maskgw: pgwire escutando em 127.0.0.1:"
LEGACY_CONFIG = "database:\n  statement_timeout_ms: 2000\n  max_rows: 10\n"
USER = "gwuser"
ALIAS = "crm"
STARTUP_TIMEOUT = 90.0
EXIT_TIMEOUT = 60.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _bound(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
        return False


@dataclass(repr=False)
class Gateway:
    """Um processo `python -I -B -m maskgw` e o que ele precisa."""

    root: Path
    config: Path
    store: Path
    anchor: Path
    env: dict[str, str]
    port: int
    password: str
    ca_path: Path
    upstream_db: str
    owner_dsn: str
    process: subprocess.Popen[bytes] | None = None
    stderr_thread: threading.Thread | None = None
    lines: queue.Queue[str] = field(default_factory=queue.Queue)
    stderr_text: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-m", "maskgw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
            env=self.env,
        )
        stderr = self.process.stderr
        assert stderr is not None

        def pump() -> None:
            for raw in iter(stderr.readline, b""):
                # No Windows o stderr em modo texto traduz `\n` para `\r\n`;
                # o conteudo comparado e o mesmo, so o fim de linha muda.
                text = raw.decode("utf-8", "replace").replace("\r\n", "\n")
                self.stderr_text.append(text)
                self.lines.put(text)
            self.lines.put("")

        self.stderr_thread = threading.Thread(target=pump, name="teste-stderr-gateway", daemon=True)
        self.stderr_thread.start()

    def wait_line(self, prefix: str, timeout: float = STARTUP_TIMEOUT) -> str:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                pytest.fail(f"linha nao apareceu: {prefix!r}; stderr={self.stderr_text!r}")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line == "":
                pytest.fail(f"processo encerrou antes de {prefix!r}: {self.stderr_text!r}")
            if line.startswith(prefix):
                return line

    def close_stdin_and_wait(self) -> tuple[int, bytes]:
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.close()  # EOF do MCP stdio
        code = self.process.wait(timeout=EXIT_TIMEOUT)
        assert self.process.stdout is not None
        output = self.process.stdout.read()
        self._close_pipes()
        return code, output

    def kill(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=30)
        self._close_pipes()

    def _close_pipes(self) -> None:
        if self.process is None:
            return
        assert self.process.poll() is not None, "processo deve terminar antes dos pipes"
        if self.stderr_thread is not None:
            self.stderr_thread.join(timeout=5)
            assert not self.stderr_thread.is_alive(), "leitor de stderr nao foi recolhido"
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def connect(self, **extra: Any) -> psycopg.Connection[Any]:
        options: dict[str, Any] = {
            "host": "127.0.0.1",
            "port": self.port,
            "user": USER,
            "dbname": ALIAS,
            "password": self.password,
            "sslmode": "verify-full",
            "sslrootcert": str(self.ca_path),
            "gssencmode": "disable",
            "connect_timeout": 10,
            **extra,
        }
        return psycopg.connect(**options)


def _owner(dsn: str, **changes: str) -> str:
    parts = conninfo_to_dict(dsn)
    parts.update(changes)
    return make_conninfo("", **parts)


def _upstream_sessions(owner_dsn: str, database: str) -> int:
    """`sessions` cumulativo do banco, com snapshot de estatistica novo."""
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_stat_clear_snapshot()")
        row = conn.execute(
            "SELECT sessions FROM pg_stat_database WHERE datname = %s", (database,)
        ).fetchone()
    assert row is not None
    return int(row[0])


def _stable_sessions(owner_dsn: str, database: str, *, timeout: float = 20.0) -> int:
    """Le ate duas leituras iguais com 1 s de intervalo (flush das saidas)."""
    deadline = time.monotonic() + timeout
    previous = _upstream_sessions(owner_dsn, database)
    while time.monotonic() < deadline:
        time.sleep(1.0)
        current = _upstream_sessions(owner_dsn, database)
        if current == previous:
            return current
        previous = current
    pytest.fail("contador de sessoes upstream nao estabilizou")


def _upstream_backends(owner_dsn: str, database: str) -> int:
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (database,),
        ).fetchone()
    assert row is not None
    return int(row[0])


@pytest.fixture
def gateway(dsn: str, tmp_path: Path) -> Iterator[Gateway]:
    parts = conninfo_to_dict(dsn)
    host = str(parts.get("host", ""))
    assert host in {"127.0.0.1", "localhost"}, "integracao so contra PostgreSQL em loopback"
    owner_dsn = dsn
    upstream_db = "maskgw_opds_" + secrets.token_hex(4)
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(upstream_db)))
    root = tmp_path / "run"
    config = root / "conf" / "masking.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(LEGACY_CONFIG, encoding="utf-8")
    store = config.parent / "datasources.store"
    anchor = config.parent / ".maskgw-anchor" / "datasources.anchor"
    master_key = secrets.token_hex(32)
    with CatalogStore.initialize(store, anchor_path=anchor, master_key=master_key) as catalog:
        catalog.create(
            DatasourceDraft(
                alias=ALIAS,
                display_name="CRM",
                host="127.0.0.1",
                port=int(str(parts["port"])),
                database=upstream_db,
                username=str(parts["user"]),
                destination_policy=DestinationPolicy(allow_loopback=True),
            ),
            str(parts["password"]),
            resolver=lambda _host, _port: ("127.0.0.1",),
        )
    tls_dir = root / "tls"
    tls_dir.mkdir()
    ca, ca_cert, ca_key = make_certificate(tls_dir, common_name="ca.test")
    leaf, _, _ = make_certificate(tls_dir, issuer=(ca_cert, ca_key))
    password = "senha-gw-" + secrets.token_urlsafe(16)
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MASKGW_", "PG", "PYTHON"))}
    env |= {
        "MASKGW_CONFIG": str(config),
        "MASKGW_DATABASE_DSN": dsn,
        "MASKGW_DATASOURCE_MASTER_KEY": master_key,
        "MASKGW_PGWIRE_ENABLED": "1",
        "MASKGW_PGWIRE_USERNAME": USER,
        "MASKGW_PGWIRE_PASSWORD": password,
        "MASKGW_PGWIRE_PORT": str(port),
        "MASKGW_PGWIRE_TLS_CERT": str(leaf.cert_path),
        "MASKGW_PGWIRE_TLS_KEY": str(leaf.key_path),
    }
    value = Gateway(
        root=root,
        config=config,
        store=store,
        anchor=anchor,
        env=env,
        port=port,
        password=password,
        ca_path=ca.cert_path,
        upstream_db=upstream_db,
        owner_dsn=owner_dsn,
    )
    try:
        yield value
    finally:
        value.kill()
        with psycopg.connect(owner_dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(upstream_db)
                )
            )


def _secrets_absent(text: str, gateway: Gateway) -> None:
    for secret in (
        gateway.password,
        gateway.env["MASKGW_DATASOURCE_MASTER_KEY"],
        str(conninfo_to_dict(gateway.owner_dsn)["password"]),
    ):
        assert secret not in text


# ---- caminho positivo --------------------------------------------------------


def test_real_activation_authenticates_rejects_client_sql_and_ends_on_mcp_eof(
    gateway: Gateway,
) -> None:
    gateway.start()
    listening = gateway.wait_line(LISTENING_PREFIX)
    assert listening == f"{LISTENING_PREFIX}{gateway.port}\n"
    assert _bound(gateway.port)
    # Linha de base DEPOIS do startup (o verificador ja consultou o upstream).
    baseline = _stable_sessions(gateway.owner_dsn, gateway.upstream_db)

    # SCRAM-SHA-256 (sem -PLUS) e SCRAM-SHA-256-PLUS, ambos com verify-full.
    with gateway.connect(channel_binding="disable") as plain:
        assert plain.info.transaction_status is not None
        assert _upstream_backends(gateway.owner_dsn, gateway.upstream_db) == 0
    with gateway.connect(channel_binding="require") as plus:
        assert plus.pgconn.ssl_in_use
        assert _upstream_backends(gateway.owner_dsn, gateway.upstream_db) == 0

    # Senha e alias errados: a MESMA falha, sem enumerar.
    failures: list[str] = []
    for extra in ({"password": gateway.password + "x"}, {"dbname": "nao-existe"}):
        with pytest.raises(psycopg.OperationalError) as caught:
            gateway.connect(channel_binding="require", **extra).close()
        failures.append(str(caught.value))
    assert failures[0] == failures[1]
    assert "authentication failed" in failures[0]
    assert "nao-existe" not in failures[0]

    # Simple Query real, sem BEGIN implicito: o payload SELECT chega ao
    # ingresso, que deve recusa-lo. ClientCursor usa PQsendQuery fora de
    # pipeline; autocommit impede que o teste recuse so o BEGIN automatico.
    marker = "maskgw-marcador-" + secrets.token_hex(6)
    with gateway.connect(
        channel_binding="require", autocommit=True, cursor_factory=psycopg.ClientCursor
    ) as conn:
        with pytest.raises(psycopg.Error) as rejected:
            conn.execute(sql.SQL("SELECT {}").format(sql.Literal(marker)))
        assert rejected.value.sqlstate == "0A000"

    # Prova observavel: nenhuma sessao upstream nova durante as sessoes PGWire.
    time.sleep(2.0)
    assert _stable_sessions(gateway.owner_dsn, gateway.upstream_db) == baseline
    assert _upstream_backends(gateway.owner_dsn, gateway.upstream_db) == 0
    # O legado tem uma conexao persistente em OUTRO banco: conferir so a
    # criacao de sessoes do datasource nao detectaria um repasse errado a ela.
    # Consultamos apenas uma contagem, nunca devolvemos SQL de outros backends.
    with psycopg.connect(gateway.owner_dsn, autocommit=True) as observer:
        forwarded = observer.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE pid <> pg_backend_pid() AND strpos(query, %s) > 0",
            (marker,),
        ).fetchone()
    assert forwarded == (0,), "marcador do cliente chegou a um backend upstream"
    # Contraprova: uma conexao direta ao mesmo banco FAZ o contador subir.
    with psycopg.connect(_owner(gateway.owner_dsn, dbname=gateway.upstream_db)) as direct:
        direct.execute("SELECT 1")
    deadline = time.monotonic() + 20
    while (
        _upstream_sessions(gateway.owner_dsn, gateway.upstream_db) <= baseline
        and time.monotonic() < deadline
    ):
        time.sleep(0.5)
    assert _upstream_sessions(gateway.owner_dsn, gateway.upstream_db) == baseline + 1

    # MCP stdio ficou aberto ate aqui; o EOF encerra tudo.
    assert gateway.process is not None and gateway.process.poll() is None
    code, stdout = gateway.close_stdin_and_wait()
    assert code == 0, gateway.stderr_text
    assert stdout == b""  # stdout e exclusivo do MCP, que nada recebeu
    assert not _bound(gateway.port), "porta do listener liberada"
    assert _upstream_backends(gateway.owner_dsn, gateway.upstream_db) == 0
    text = "".join(gateway.stderr_text)
    assert text.startswith(REVISION_PREFIX)
    assert marker not in text
    _secrets_absent(text, gateway)


def test_real_disabled_flag_keeps_legacy_and_never_binds(gateway: Gateway) -> None:
    gateway.env.pop("MASKGW_PGWIRE_ENABLED")
    gateway.start()
    gateway.wait_line(REVISION_PREFIX)
    assert not _bound(gateway.port)
    code, stdout = gateway.close_stdin_and_wait()
    assert code == 0, gateway.stderr_text
    assert stdout == b""
    text = "".join(gateway.stderr_text)
    assert "pgwire" not in text
    _secrets_absent(text, gateway)


# ---- recusas reais, sem queda para o legado --------------------------------


def _flip_one_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))


@pytest.mark.parametrize(
    "case",
    [
        "admin-junto",
        "ui-junto",
        "store-ausente",
        "ancora-ausente",
        "store-adulterado",
        "chave-errada",
        "tls-inexistente",
        "senha-ausente",
    ],
)
def test_real_refusals_are_fixed_and_never_bind_or_fall_back(gateway: Gateway, case: str) -> None:
    if case == "admin-junto":
        gateway.env |= {"MASKGW_ADMIN_ENABLED": "1", "MASKGW_ADMIN_TOKEN": "t" * 40}
    elif case == "ui-junto":
        gateway.env |= {"MASKGW_ADMIN_UI_ENABLED": "1"}
    elif case == "store-ausente":
        gateway.store.unlink()
    elif case == "ancora-ausente":
        gateway.anchor.unlink()
    elif case == "store-adulterado":
        _flip_one_byte(gateway.store)
    elif case == "chave-errada":
        gateway.env["MASKGW_DATASOURCE_MASTER_KEY"] = secrets.token_hex(32)
    elif case == "tls-inexistente":
        gateway.env["MASKGW_PGWIRE_TLS_CERT"] = str(gateway.root / "nao-existe.crt")
    elif case == "senha-ausente":
        gateway.env.pop("MASKGW_PGWIRE_PASSWORD")
    gateway.start()
    assert gateway.process is not None
    code = gateway.process.wait(timeout=STARTUP_TIMEOUT)
    assert gateway.process.stdout is not None
    stdout = gateway.process.stdout.read()
    deadline = time.monotonic() + 5
    while "".join(gateway.stderr_text).count("\n") < 1 and time.monotonic() < deadline:
        time.sleep(0.05)
    text = "".join(gateway.stderr_text)
    assert code == 1
    assert stdout == b""
    assert text == STARTUP_FAILURE  # nenhuma linha de revision: sem queda para o legado
    assert not _bound(gateway.port)
    _secrets_absent(text, gateway)
    assert _upstream_backends(gateway.owner_dsn, gateway.upstream_db) == 0
