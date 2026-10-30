"""Installed typed PG16 pipeline -> encoder -> receiver, no operational listener.

Run with -I from a temporary cwd and explicit installed target. Dependencies
come from the existing test interpreter; not a dependency-isolated app gate.
MASKGW_TEST_DSN must refer to the executor-owned disposable database.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any


def source_path(module: ModuleType) -> Path:
    filename = module.__file__
    assert isinstance(filename, str)
    return Path(filename).resolve()


def run(target: Path) -> dict[str, Any]:
    assert target.is_absolute() and (target / "maskgw/pgwire/result_encoder.py").is_file()
    sys.path.insert(0, str(target))
    names = (
        "db.result",
        "db.postgres",
        "pgwire.result_encoder",
        "pgwire.result_frame",
        "pgwire.result_receiver",
        "pgwire.transport",
        "runtime.budget",
    )
    modules = {name: importlib.import_module("maskgw." + name) for name in names}
    config = importlib.import_module("maskgw.config")
    engine_module = importlib.import_module("maskgw.masking.engine")
    for name, module in tuple(sys.modules.items()):
        if name == "maskgw" or name.startswith("maskgw."):
            assert module is not None and source_path(module).is_relative_to(target)
    encoder = modules["pgwire.result_encoder"]
    frame = modules["pgwire.result_frame"]
    receiver = modules["pgwire.result_receiver"]
    transport = modules["pgwire.transport"]
    budget = modules["runtime.budget"]
    engine = engine_module.MaskingEngine(
        config.load_config_text(
            'masking:\n  - match: cpf\n    transformer: fixed\n    config: {value: "***"}\n'
        )
    )
    identity = frame.ResultIdentity(
        session_id=b"S" * 16, datasource_id=b"D" * 16, generation=1, record_revision=2, job_id=3
    )
    limits = frame.ResultLimits(max_rows=1000, max_frame_bytes=4096)

    def deadline() -> Any:
        return frame.ResultDeadline(expires_at=time.monotonic() + 5)

    with modules["db.postgres"].PostgresAdapter(os.environ["MASKGW_TEST_DSN"], engine) as adapter:
        item = adapter._execute_typed_validated(
            "SELECT 42::int2 AS id, 'SYNTHETIC_ORIGINAL'::text AS cpf"
        )
        assert item.type_oids == (21, 25) and item.masked.rows == ((42, "***"),)
        raw = encoder.encode_result(item, identity=identity, limits=limits, deadline=deadline())
        assert b"SYNTHETIC_ORIGINAL" not in raw
        assert b"***" in raw
    ledger = budget.BudgetLedger(
        budget.BudgetLimits(1024 * 1024, 10, 10, 8, 2, 2, 2, 2, 2),
        (budget.DatasourceCapacity(2, 2),),
    )
    generation = ledger.reserve_candidate(0, shared_bytes=10)
    ledger.publish(generation)
    token = ledger.reserve_session(generation, worker_bytes=100, parent_bytes=2 * 4096 + 524288)
    ledger.mark_live(token)
    result = receiver.ResultReceiver(
        ledger,
        token,
        lock=threading.Lock(),
        expected=identity,
        limits=limits,
        overhead_bytes=524288,
        deadline=deadline(),
    )
    source, peer = socket.socketpair()
    output, client = socket.socketpair()

    def channel(sock: socket.socket) -> Any:
        return transport.RawChannel(sock, stop=lambda: False, limits=transport.TransportLimits())

    try:
        for sock in (source, peer, output, client):
            sock.settimeout(5)
        peer.sendall(raw)
        result.receive(channel(source))
        summary = result.send_to(channel(output), deadline=deadline())
        output_body = bytearray()
        while len(output_body) < len(raw) - 76:
            part = client.recv(4096)
            assert part
            output_body += part
        assert output_body == raw[76:]
        assert (summary.rows, summary.columns, summary.truncated) == (1, 2, False)
        assert ledger.status.entries[token._slot].output_pinned
        assert result.close(deadline=deadline()) is budget.OutputReleaseOutcome.CLEARED
    finally:
        for sock in (source, peer, output, client):
            sock.close()
    return {
        "scenario": "real_pg16_typed_masked_encoder_receiver",
        "python": sys.version.split()[0],
        "frame_bytes": len(raw),
        "module_hashes": {
            name: hashlib.sha256(source_path(module).read_bytes()).hexdigest()
            for name, module in modules.items()
        },
        "all_maskgw_from_target": True,
        "dependencies": "existing interpreter, not isolated",
    }


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1]).resolve()), sort_keys=True))
