"""Installed-package probe, invoked with -I outside checkout; no SQL or listener.

The explicit target supplies maskgw; dependencies come from the existing test
interpreter. This is NOT a dependency-isolated full application certification.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import socket
import struct
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


def packet(*, job: int = 3) -> bytes:
    def message(tag: bytes, payload: bytes) -> bytes:
        return tag + struct.pack("!I", 4 + len(payload)) + payload

    description = struct.pack("!H", 1) + b"x\0" + struct.pack("!IhIhih", 0, 0, 25, -1, -1, 0)
    body = (
        message(b"T", description)
        + message(b"D", struct.pack("!Hi", 1, 3) + b"***")
        + message(b"C", b"SELECT 1\0")
    )
    return (
        struct.pack(
            "!4sBBH16s16sQQQIII", b"MGWR", 1, 0, 0, b"S" * 16, b"D" * 16, 1, 2, job, 1, 1, len(body)
        )
        + body
    )


def run(target: Path) -> dict[str, Any]:
    if not target.is_absolute() or not (target / "maskgw/pgwire/result_receiver.py").is_file():
        raise ValueError("invalid installed target")
    sys.path.insert(0, str(target))
    modules = {
        name: importlib.import_module(f"maskgw.{name}")
        for name in (
            "pgwire.result_frame",
            "pgwire.result_receiver",
            "pgwire.transport",
            "runtime.budget",
        )
    }
    for name, module in tuple(sys.modules.items()):
        if name == "maskgw" or name.startswith("maskgw."):
            assert module is not None and source_path(module).is_relative_to(target)
    frame, receiver, transport, budget = modules.values()

    def deadline() -> Any:
        return frame.ResultDeadline(expires_at=time.monotonic() + 5)

    def channel(sock: socket.socket) -> Any:
        return transport.RawChannel(sock, stop=lambda: False, limits=transport.TransportLimits())

    def scenario(*, valid: bool) -> str:
        ledger = budget.BudgetLedger(
            budget.BudgetLimits(1024 * 1024, 10, 10, 8, 2, 2, 2, 2, 2),
            (budget.DatasourceCapacity(2, 2),),
        )
        generation = ledger.reserve_candidate(0, shared_bytes=10)
        ledger.publish(generation)
        token = ledger.reserve_session(generation, worker_bytes=100, parent_bytes=2 * 4096 + 524288)
        ledger.mark_live(token)
        identity = frame.ResultIdentity(
            session_id=b"S" * 16, datasource_id=b"D" * 16, generation=1, record_revision=2, job_id=3
        )
        result = receiver.ResultReceiver(
            ledger,
            token,
            lock=threading.Lock(),
            expected=identity,
            limits=frame.ResultLimits(max_rows=5, max_frame_bytes=4096),
            overhead_bytes=524288,
            deadline=deadline(),
        )
        source, worker = socket.socketpair()
        output, client = socket.socketpair()
        sockets = (source, worker, output, client)
        for sock in sockets:
            sock.settimeout(5)
        try:
            raw = packet(job=3 if valid else 4)
            worker.sendall(raw)
            if valid:
                result.receive(channel(source))
                summary = result.send_to(channel(output), deadline=deadline())
                assert (summary.columns, summary.rows, summary.truncated) == (1, 1, False)
                assert client.recv(4096) == raw[76:]
            else:
                refused = False
                try:
                    result.receive(channel(source))
                except receiver.ReceiverError:
                    refused = True
                assert refused
            assert ledger.status.entries[token._slot].output_pinned
            ledger.begin_drain(token)
            confirmation = budget.CleanupConfirmation(True, True, True, True, True)
            assert ledger.release(token, confirmation) is budget.ReleaseOutcome.HELD
            assert result.close(deadline=deadline()) is budget.OutputReleaseOutcome.CLEARED
            assert ledger.release(token, confirmation) is budget.ReleaseOutcome.RELEASED
            return "valid_body_only" if valid else "wrong_job_refused"
        finally:
            for sock in sockets:
                sock.close()

    return {
        "scenarios": [scenario(valid=True), scenario(valid=False)],
        "python": sys.version.split()[0],
        "module_hashes": {
            name: hashlib.sha256(source_path(module).read_bytes()).hexdigest()
            for name, module in modules.items()
        },
        "maskgw_outside_checkout": True,
        "dependencies": "existing interpreter, not isolated",
    }


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1]).resolve()), sort_keys=True))
