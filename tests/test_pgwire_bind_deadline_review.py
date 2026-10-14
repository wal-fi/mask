"""Contraprova independente: esperar o filho nao pode renovar o prazo DNS."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_dns_wait_returning_after_deadline_cannot_approve() -> None:
    """Relogio virtual no subprocesso; filho real, sem consulta DNS de rede."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    program = (
        f"import sys\nsys.path.insert(0, {source!r})\n"
        + r"""
import os
import threading
import maskgw.datasource.verify as v

watchdog = threading.Timer(8, lambda: os._exit(91))
watchdog.daemon = True
watchdog.start()
clock = [0.0]
original_time = v.time.monotonic
original_spawn = v._spawn
processes = []

def spawn(record, args, **kwargs):
    process = original_spawn(record, args, **kwargs)
    processes.append(process)
    original_wait = process.wait
    def delayed_wait(timeout=None):
        result = original_wait(timeout=timeout)
        clock[0] = 6.0
        return result
    process.wait = delayed_wait
    return process

try:
    v._BIND_DNS_CHILD_CODE = (
        'import sys; sys.stdin.buffer.read(); '
        'print("[[2, \\"127.0.0.1\\", 0]]")'
    )
    v._BIND_SLOTS = threading.BoundedSemaphore(4)
    v._BIND_LEDGER = v._Ledger(v._BIND_SLOTS)
    v._spawn = spawn
    v.time.monotonic = lambda: clock[0]
    try:
        v.resolve_bind_host_in_child('review.invalid', deadline=5.0)
    except v.BindDnsError as error:
        assert error.failure is v.BindDnsFailure.FAILED
        assert error.__cause__ is None and error.__context__ is None
    else:
        raise AssertionError('DNS approved after absolute deadline')
    assert clock[0] > 5.0
    assert not v._BIND_LEDGER.records
    assert all(process.poll() is not None for process in processes)
    assert all(process.stdin.closed and process.stdout.closed for process in processes)
    assert not any(t.name.startswith('maskgw-bind-dns-') for t in threading.enumerate())
finally:
    v.time.monotonic = original_time
    v._spawn = original_spawn
    watchdog.cancel()
    watchdog.join()
"""
    )
    result = subprocess.run(  # noqa: S603 - interpretador e programa fixos do teste
        [sys.executable, "-I", "-B", "-c", program],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_dns_answer_read_only_during_cleanup_cannot_approve() -> None:
    """O cleanup pode terminar depois do prazo, mas nao concluir a resposta."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    program = (
        f"import sys\nsys.path.insert(0, {source!r})\n"
        + r"""
import os
import threading
import maskgw.datasource.verify as v

watchdog = threading.Timer(8, lambda: os._exit(91))
watchdog.daemon = True
watchdog.start()
clock = [0.0]
release = threading.Event()
read_done = threading.Event()
original_time = v.time.monotonic
original_reader = v._pump_bind_dns_stdout
original_reap = v._ChildRecord.reap
started_at = original_time()
processes = []
original_spawn = v._spawn

def spawn(record, args, **kwargs):
    process = original_spawn(record, args, **kwargs)
    processes.append(process)
    return process

def held_reader(stream, sink):
    assert release.wait(4)
    original_reader(stream, sink)
    read_done.set()

def reap(record, deadline):
    # O filho terminou no prazo, mas o pai so recebe os bytes no cleanup.
    clock[0] = 5.5
    release.set()
    assert read_done.wait(4)
    return original_reap(record, deadline)

try:
    v._BIND_DNS_CHILD_CODE = (
        'import sys; sys.stdin.buffer.read(); '
        'print("[[2, \\"127.0.0.1\\", 0]]")'
    )
    v._pump_bind_dns_stdout = held_reader
    v._ChildRecord.reap = reap
    v._spawn = spawn
    v.time.monotonic = lambda: max(clock[0], (original_time() - started_at) * 10)
    try:
        v.resolve_bind_host_in_child('review.invalid', deadline=5.0)
    except v.BindDnsError as error:
        assert error.failure is v.BindDnsFailure.FAILED
        assert error.__cause__ is None and error.__context__ is None
    else:
        raise AssertionError('DNS approved response received only after work deadline')
    assert not v._BIND_LEDGER.records
    assert all(process.poll() is not None for process in processes)
    assert all(process.stdin.closed and process.stdout.closed for process in processes)
    assert not any(t.name.startswith('maskgw-bind-dns-') for t in threading.enumerate())
finally:
    v.time.monotonic = original_time
    v._spawn = original_spawn
    v._pump_bind_dns_stdout = original_reader
    v._ChildRecord.reap = original_reap
    watchdog.cancel()
    watchdog.join()
"""
    )
    result = subprocess.run(  # noqa: S603 - interpretador e programa fixos do teste
        [sys.executable, "-I", "-B", "-c", program],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_dns_admission_collection_cannot_follow_new_records_past_deadline() -> None:
    """Pendentes novos nao tornam a coleta de admissao uma fila sem prazo."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    program = (
        f"import sys\nsys.path.insert(0, {source!r})\n"
        + r"""
import threading
import maskgw.datasource.verify as v

clock = [0.0]
seen = []
retained = []
ledger = type(v._BIND_LEDGER)(threading.BoundedSemaphore(4))

class ReadyRecord:
    def __init__(self):
        self.in_flight = False
        self.claimer = None
        self.owner = v._BIND_OWNER
        retained.append(self)
    def reap(self, deadline):
        seen.append(deadline)
        clock[0] += 0.1
        # Simula outro build que deixa um registro pronto durante a coleta.
        if len(seen) < 80:
            with ledger.lock:
                assert ledger.slots.acquire(blocking=False)
                ledger.records.append(ReadyRecord())
        return True

assert ledger.slots.acquire(blocking=False)
ledger.records.append(ReadyRecord())
saved_time = v.time.monotonic
saved_ledger = v._BIND_LEDGER
try:
    v.time.monotonic = lambda: clock[0]
    v._BIND_LEDGER = ledger
    # Se houver admissao apos a coleta limitada, o filho nao consulta DNS.
    v._BIND_DNS_CHILD_CODE = 'import sys; sys.stdin.buffer.read(); print("[]")'
    try:
        v.resolve_bind_host_in_child('review.invalid', deadline=5.0)
    except v.BindDnsError:
        pass
    assert clock[0] <= 5.0, 'admission collection exceeded DNS work deadline'
    assert len(seen) < 80, 'collection followed all newly arriving records'
    assert any(isinstance(record, ReadyRecord) for record in ledger.records)
    assert not any(t.name.startswith('maskgw-bind-dns-') for t in threading.enumerate())
finally:
    v.time.monotonic = saved_time
    v._BIND_LEDGER = saved_ledger
"""
    )
    result = subprocess.run(  # noqa: S603 - interpretador e programa fixos do teste
        [sys.executable, "-I", "-B", "-c", program],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
