"""Public PG16 shell reader source/vectors/parser. No native caller or effects."""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import re
import shlex

CHANNEL_SHA = "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a"
MAX_BODY = 16384
MAX_OUTPUT = 2048
GLOBAL_SECONDS = 8
SURPLUS_SECONDS = 1
DIRECTORY = "/tmp/maskgw-reader"
TRAILER_SHA = hashlib.sha256(b"SEEDEND\n").hexdigest()

# No body in variables, shell expansion, argv, environment or output. This
# function is captured verbatim by future callers, never edited in a used run.
READER_SOURCE = r"""set -efu
export LC_ALL=C
umask 077
fail() { printf 'fault=%s\n' "$1"; exit 42; }
size_of() {
    amount=$(wc -c < "$1") || fail IO
    set -- $amount
    [ "$#" -eq 1 ] || fail IO
    case "$1" in ''|*[!0-9]*) fail IO;; esac
    printf '%s' "$1"
}
hash_of() {
    digest=$(sha256sum "$1" 2>/dev/null) || fail IO
    digest=${digest%% *}
    [ "${#digest}" -eq 64 ] || fail IO
    case "$digest" in *[!0-9a-f]*) fail IO;; esac
    printf '%s' "$digest"
}
dd bs=1 count=16 of=/tmp/maskgw-reader/header 2>/dev/null || fail IO
amount=$(size_of /tmp/maskgw-reader/header) || fail IO
[ "$amount" -eq 16 ] || fail HEADER
header=$(dd if=/tmp/maskgw-reader/header bs=16 count=1 2>/dev/null) || fail IO
case "$header" in
    MGSEED01P[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) fail HEADER;;
esac
digits=${header#MGSEED01P}
printf 'MGSEED01P%s\n' "$digits" > /tmp/maskgw-reader/expected-header || fail IO
received=$(hash_of /tmp/maskgw-reader/header) || fail IO
expected=$(hash_of /tmp/maskgw-reader/expected-header) || fail IO
[ "$received" = "$expected" ] || fail HEADER
length=$digits
while [ "${length#0}" != "$length" ]; do length=${length#0}; done
[ -n "$length" ] || fail HEADER
[ "$length" -le 16384 ] || fail HEADER
dd bs=1 count="$length" of=/tmp/maskgw-reader/body 2>/dev/null || fail IO
amount=$(size_of /tmp/maskgw-reader/body) || fail IO
[ "$amount" -eq "$length" ] || fail BODY
dd bs=1 count=8 of=/tmp/maskgw-reader/trailer 2>/dev/null || fail IO
amount=$(size_of /tmp/maskgw-reader/trailer) || fail IO
[ "$amount" -eq 8 ] || fail TRAILER
received=$(hash_of /tmp/maskgw-reader/trailer) || fail IO
[ "$received" = 'TRAILER_DIGEST' ] || fail TRAILER
tail_exit=0
timeout -s KILL 1 dd bs=1 count=1 of=/tmp/maskgw-reader/extra 2>/dev/null || tail_exit=$?
amount=$(size_of /tmp/maskgw-reader/extra) || fail IO
[ "$amount" -eq 0 ] || fail SURPLUS
case "$tail_exit" in
    0) tail=EOF;;
    137) tail=QUIET;;
    *) fail IO;;
esac
printf '%s\n' "$tail" > /tmp/maskgw-reader/tail || fail IO
printf '%s\n' "$length" > /tmp/maskgw-reader/length || fail IO
""".replace("TRAILER_DIGEST", TRAILER_SHA)
CORE_SHA = hashlib.sha256(READER_SOURCE.encode("ascii")).hexdigest()


class Case(StrEnum):
    ONE = "one"
    BINARY = "binary"
    FRAGMENTED = "fragmented"
    RETAIN = "retain"
    MAGIC = "bad-magic"
    ROLE = "bad-role"
    DIGIT = "bad-digit"
    HEADER_NUL = "header-nul"
    HEADER_INNER_NUL = "header-inner-nul"
    HEADER_CR = "header-cr"
    ZERO = "zero"
    OVERSIZE = "oversize"
    SHORT_HEADER = "short-header"
    SHORT_BODY = "short-body"
    SHORT_TRAILER = "short-trailer"
    BAD_TRAILER = "bad-trailer"
    TRAILER_NUL = "trailer-nul"
    EXTRA_ASCII = "extra-ascii"
    EXTRA_NUL = "extra-nul"
    EXTRA_LF = "extra-lf"
    WAIT_HEADER = "wait-header"
    WAIT_BODY = "wait-body"
    WAIT_TRAILER = "wait-trailer"


class Code(StrEnum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    HEADER = "HEADER"
    BODY = "BODY"
    TRAILER = "TRAILER"
    SURPLUS = "SURPLUS"
    IO = "IO"
    DEADLINE = "DEADLINE"
    PRECHECK = "PRECHECK"


class ReaderError(Exception):
    def __init__(self, category):
        self.category = category if type(category) is Code else Code.INPUT
        super().__init__(self.category.value)


def need(ok, code=Code.INPUT):
    if not ok:
        raise ReaderError(code) from None


@dataclass(frozen=True)
class Vector:
    case: Case
    wire: bytes
    body: bytes
    chunks: tuple
    hold_open: bool
    fault: Code | None
    tail: str | None


def _frame(body):
    return b"MGSEED01P" + f"{len(body):06d}\n".encode("ascii") + body + b"SEEDEND\n"


def vector(case):
    """Closed public canaries only. Not an API to encode operator input."""
    need(type(case) is Case)
    body = (bytes(range(256)) * 64)[:8000] + b"SEEDEND\n"
    body += (bytes(range(256)) * 64)[: MAX_BODY - len(body)]
    if case is Case.ONE:
        body = b"\x00"
    wire = _frame(body)
    fault, tail, hold = None, "EOF", False
    if case is Case.MAGIC:
        wire, fault = b"BADSEED1" + wire[8:], Code.HEADER
    elif case is Case.ROLE:
        wire, fault = wire[:8] + b"C" + wire[9:], Code.HEADER
    elif case is Case.DIGIT:
        wire, fault = wire[:10] + b"x" + wire[11:], Code.HEADER
    elif case is Case.HEADER_NUL:
        wire, fault = wire[:15] + b"\x00" + wire[16:], Code.HEADER
    elif case is Case.HEADER_INNER_NUL:
        wire, fault = wire[:11] + b"\x00" + wire[12:], Code.HEADER
    elif case is Case.HEADER_CR:
        wire, fault = wire[:15] + b"\r" + wire[16:], Code.HEADER
    elif case is Case.ZERO:
        wire, fault = wire[:9] + b"000000" + wire[15:], Code.HEADER
    elif case is Case.OVERSIZE:
        wire, fault = wire[:9] + b"016385" + wire[15:], Code.HEADER
    elif case is Case.SHORT_HEADER:
        wire, fault = wire[:15], Code.HEADER
    elif case is Case.SHORT_BODY:
        wire, fault = wire[:17], Code.BODY
    elif case is Case.SHORT_TRAILER:
        wire, fault = wire[:-1], Code.TRAILER
    elif case is Case.BAD_TRAILER:
        wire, fault = wire[:-8] + b"BADEND!\n", Code.TRAILER
    elif case is Case.TRAILER_NUL:
        wire, fault = wire[:-1] + b"\x00", Code.TRAILER
    elif case in (Case.EXTRA_ASCII, Case.EXTRA_NUL, Case.EXTRA_LF):
        extra = {Case.EXTRA_ASCII: b"x", Case.EXTRA_NUL: b"\x00", Case.EXTRA_LF: b"\n"}[case]
        wire, fault = wire + extra, Code.SURPLUS
    elif case in (Case.WAIT_HEADER, Case.WAIT_BODY, Case.WAIT_TRAILER):
        end = {Case.WAIT_HEADER: 1, Case.WAIT_BODY: 17, Case.WAIT_TRAILER: -1}[case]
        wire, fault, hold = wire[:end], Code.DEADLINE, True
    elif case is Case.RETAIN:
        tail, hold = "QUIET", True
    if fault is not None:
        tail = None
    chunks = (wire,)
    if case is Case.FRAGMENTED:
        boundaries = (0, 1, 8, 9, 14, 15, 16, 17, 8000, 16400, len(wire))
        chunks = tuple(wire[start:end] for start, end in zip(boundaries, boundaries[1:]))
    return Vector(case, wire, body, chunks, hold, fault, tail)


def ready_line(task):
    need(type(task) is str and re.fullmatch(r"[0-9a-f]{32}", task))
    value = {
        "kind": "MASKGW_BOOTSTRAP_READY_V1",
        "pid": 1,
        "role": "P",
        "source_sha256": CORE_SHA,
        "task": task,
        "uid": 70,
    }
    return _encoded(value)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def build(task, case):
    """Public script only, not a Docker command, native caller or private seed."""
    ready = ready_line(task).decode("ascii")
    value = vector(case)
    # Public instrumentation runs INSIDE the same global deadline as reading.
    suffix = (
        "\n"
        + r"""amount=$(size_of /tmp/maskgw-reader/body) || fail IO
digest=$(hash_of /tmp/maskgw-reader/body) || fail IO
mode=$(stat -c '%u:%g:%a' /tmp/maskgw-reader/body) || fail IO
[ "$mode" = '70:70:600' ] || fail IO
tail=$(dd if=/tmp/maskgw-reader/tail bs=8 count=1 2>/dev/null) || fail IO
case "$tail" in EOF|QUIET) ;; *) fail IO;; esac
"""
    )
    # The template has only public constants and strictly validated task/case.
    pattern = (
        '{"body_bytes":%s,"body_sha256":"%s","case":"'
        + value.case.value
        + '","core_sha256":"'
        + CORE_SHA
        + '","kind":"MASKGW_PG16_SHELL_READER_V1","tail":"%s","task":"'
        + task
        + '"}\n'
    )
    suffix += "printf " + shlex.quote(pattern) + ' "$amount" "$digest" "$tail"\n'
    child = READER_SOURCE + suffix
    script = r"""set -efu
export LC_ALL=C
umask 077
exec 2>/dev/null
precheck() { printf 'fault=PRECHECK\n'; exit 42; }
[ "$$" -eq 1 ] || precheck
[ "$(id -u):$(id -g)" = '70:70' ] || precheck
[ "$(stat -f -c '%T' /tmp)" = 'tmpfs' ] || precheck
[ "$(stat -c '%u:%g:%a' /tmp)" = '70:70:700' ] || precheck
mkdir /tmp/maskgw-reader || precheck
[ "$(stat -c '%u:%g:%a' /tmp/maskgw-reader)" = '70:70:700' ] || precheck
"""
    script += "printf '%s' " + shlex.quote(ready) + "\n"
    script += "status=0\ntimeout -s KILL 8 /bin/sh -ec " + shlex.quote(child) + " || status=$?\n"
    script += r"""case "$status" in
    0) exit 0;;
    42) exit 42;;
    137) printf 'fault=DEADLINE\n'; exit 42;;
    *) printf 'fault=IO\n'; exit 42;;
esac
"""
    need(len(script.encode("ascii")) <= 12000)
    return script


def expected_report(task, case):
    """Expected public oracle, never an observed shell execution."""
    ready_line(task)
    value = vector(case)
    need(value.fault is None)
    return {
        "kind": "MASKGW_PG16_SHELL_READER_V1",
        "task": task,
        "case": case.value,
        "core_sha256": CORE_SHA,
        "body_bytes": len(value.body),
        "body_sha256": hashlib.sha256(value.body).hexdigest(),
        "tail": value.tail,
    }


def parse_report(raw, returncode, task, case):
    """Output AFTER READY stripped by admitted owner. Uses actual child exit."""
    ready_line(task)
    value = vector(case)
    need(type(raw) is bytes and 0 < len(raw) <= MAX_OUTPUT, Code.OUTPUT)
    need(type(returncode) is int, Code.OUTPUT)
    if value.fault is not None:
        need(
            returncode == 42 and raw == f"fault={value.fault.value}\n".encode("ascii"), Code.OUTPUT
        )
        return {"ok": False, "category": value.fault.value}
    need(returncode == 0, Code.OUTPUT)
    expected = expected_report(task, case)
    need(raw == _encoded(expected), Code.OUTPUT)
    return {"ok": True, **expected}
