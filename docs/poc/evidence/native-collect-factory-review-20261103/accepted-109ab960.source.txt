"""Source-pinned composition of the collector policy and its Win32 backend.

Private, fake-only lab composition used under the general delegation; it is
not native activation nor an individual user approval. Both sources are
received as exact bytes, checked against fixed sizes and SHA-256 pins before
either is compiled, and the received bytes themselves are executed into fresh
private namespaces; nothing is read, imported from the checkout or installed
in the module table. The copied collector seam is replaced only inside the
private copy; the frozen files keep their unavailable defaults.

The pins prove the content of the received bytes, not the origin of the
capture, the standard library they import, or the injected api: the private
seams are not an authentication boundary. One attempt per module namespace:
the record is published before the first exec and retained forever, which is
durable model retention, not cleanup. Ordinary failures become a closed
tuple; control interruptions propagate unchanged.
"""

import hashlib

COLLECTOR_SHA = "1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52"
COLLECTOR_SIZE = 20571
BACKEND_SHA = "ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a"
BACKEND_SIZE = 22315
_VERIFIED = ("VERIFIED_APPROVED", "VERIFIED_REJECTED")
_HEX = frozenset("0123456789abcdef")
_SOURCE = ("INVALID", "COLLECT_SOURCE", None, None)
_UNAVAILABLE = ("INVALID", "COLLECT_UNAVAILABLE", None, None)
_POISONED = ("INVALID", "COLLECT_POISONED", None, None)
_INTERNAL = ("INVALID", "COLLECT_INTERNAL", None, None)
# Sticky: the single attempt of this namespace, never removed or reset.
_ATTEMPTS = []


class _Attempt:
    """Durable record: both private namespaces, the api and the backend."""

    __slots__ = ("collector", "native", "api", "backend")

    def __init__(self, api: object) -> None:
        self.collector = {"__name__": "_pg16_pinned_collector"}
        self.native = {"__name__": "_pg16_pinned_win32"}
        self.api = api
        self.backend = None

    def __repr__(self) -> str:
        return "Attempt(<hidden>)"


def _pinned(raw: object, size: int, digest: str) -> bool:
    return type(raw) is bytes and len(raw) == size and hashlib.sha256(raw).hexdigest() == digest


def _hash_ok(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= _HEX


def _closed(result: object, namespace: dict) -> tuple:
    """Exact four-tuple with a lawful label/reason/hash combination only."""
    reasons = namespace.get("REASONS")
    if type(result) is not tuple or len(result) != 4 or type(reasons) is not frozenset:
        return _INTERNAL
    label, reason, summary, transport = result
    if type(label) is not str or type(reason) is not str:
        return _INTERNAL
    if label in _VERIFIED and reason == "OK" and _hash_ok(summary) and _hash_ok(transport):
        return (label, reason, summary, transport)
    lawful = reason != "OK" and reason in reasons and summary is None and transport is None
    if label == "INVALID" and lawful:
        return ("INVALID", reason, None, None)
    return _INTERNAL


def _provider(record: _Attempt) -> object:
    def provide() -> object:
        return record.backend

    return provide


def _collect_pinned(
    collector_src: object, backend_src: object, api: object, nonce: object, argv0: object
) -> tuple:
    """Closed (label, reason, summary_sha256, transport_sha256)."""
    if not (
        _pinned(collector_src, COLLECTOR_SIZE, COLLECTOR_SHA)
        and _pinned(backend_src, BACKEND_SIZE, BACKEND_SHA)
    ):
        return _SOURCE
    if api is None:
        return _UNAVAILABLE  # no fallback to any native loader
    if _ATTEMPTS:
        return _POISONED
    record = _Attempt(api)
    _ATTEMPTS.append(record)  # published before the first exec, kept forever
    try:
        exec(compile(collector_src, "<pinned-collector>", "exec"), record.collector)
        exec(compile(backend_src, "<pinned-win32>", "exec"), record.native)
        record.backend = record.native["_Win32Backend"](api, record.collector)
        record.collector["_backend"] = _provider(record)  # private copy only
        return _closed(record.collector["collect"](nonce, argv0), record.collector)
    except Exception:
        return _INTERNAL
