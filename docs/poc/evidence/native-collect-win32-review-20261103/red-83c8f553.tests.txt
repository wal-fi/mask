"""Fake-only tests for the Win32 backend of the evidence collector.

docs/poc/pg16_shell_native_control_collect_win32.py does not exist yet: until
it does, these tests fail at setup (feature-absent baseline, not a product
regression). Every NT and Win32 call is simulated by a fake api that reads and
writes synthetic bytes in the ctypes objects the backend itself allocated; no
DLL is loaded and no real handle, file or outside address is used. Layout and
prototype oracles are literal numbers from the documented x64 ABI, packed with
struct independently of the implementation. Integration runs through a runpy
copy of the frozen collector policy whose _backend seam is patched only here.
Consistency shown with these fakes is not native evidence.
"""

import ast
import ctypes
import gc
import hashlib
import os
import re
import runpy
import struct
import subprocess
import sys
import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
WIN32 = REPO / "docs/poc/pg16_shell_native_control_collect_win32.py"
COLLECTOR = REPO / "docs/poc/pg16_shell_native_control_collect.py"
COLLECTOR_SHA = "1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52"
VERIFY_SOURCE = REPO / "docs/poc/pg16_shell_native_control_verify.py"
VERIFY_TESTS = REPO / "tests/test_pg16_shell_native_control_verify.py"
VERIFY_SHA = "b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10"
VERIFY_NAME = "pg16_shell_native_control_verify.py"
NONCE = "0123456789abcdef0123456789abcdef"
ARGV0 = "C:\\fictitious\\lab\\venv\\Scripts\\python.exe"
PUBLIC_NAME = "pg16-native-control-" + NONCE[:12]
PRIVATE_NAME = "maskgw-pg16-native-control-v1-" + NONCE
REPO_CHAIN = ("Users", "w.filho", "Desktop", "codes", "mask", "docs", "poc")
TEMP_CHAIN = ("Users", "w.filho", "AppData", "Local", "Temp")
ANCHOR = "\\??\\C:\\"
VOLUME = 0x1234
DATA = bytes(range(256)) * 40  # 10240 fictitious bytes


def signed(code: int) -> int:
    return code - (1 << 32) if code & 0x80000000 else code


SUCCESS = 0
PENDING = 0x103
REPARSE = 0x104
BUFFER_OVERFLOW = signed(0x80000005)
NO_MORE_FILES = signed(0x80000006)
INVALID_INFO_CLASS = signed(0xC0000003)
INVALID_HANDLE = signed(0xC0000008)
END_OF_FILE = signed(0xC0000011)
ACCESS_DENIED = signed(0xC0000022)
NAME_NOT_FOUND = signed(0xC0000034)
FILE_IS_A_DIRECTORY = signed(0xC00000BA)
NOT_SUPPORTED = signed(0xC00000BB)
NOT_A_DIRECTORY = signed(0xC0000103)
INVALID_HANDLE_VALUE = (1 << 64) - 1
FILE_OPENED = 1
# (access, share, disposition, options) from the documented flag values
DIR_RIGHTS = (0x001000A1, 0x3, 1, 0x00200021)
FILE_RIGHTS = (0x00100081, 0x1, 1, 0x00200060)
INFO_SIZES = {0: 40, 1: 24, 9: 8, 0x12: 24}
DOT_ID = bytes(16)
API_OPERATIONS = (
    "create",
    "query_info",
    "query_file",
    "query_volume",
    "query_directory",
    "read",
    "close",
)

Hook = Callable[[Callable[[], Any], SimpleNamespace], Any]


class Signal(BaseException):
    """A fictitious control interruption."""


class SneakyStr(str):
    pass


COUNTER = [0]


def node_id() -> bytes:
    COUNTER[0] += 1
    return b"\x5a" * 8 + COUNTER[0].to_bytes(8, "little")


# -- synthetic records packed from the documented layouts --


def align(size: int) -> int:
    return (size + 7) & ~7


def utf16(name: str) -> bytes:
    return name.encode("utf-16-le", "surrogatepass")


def stream_raw(step: int, name_length: int, name: bytes, size: int = 0) -> bytes:
    """FILE_STREAM_INFORMATION: next, name length, size, allocation, name@24."""
    return struct.pack("<IIqq", step, name_length, size, size) + name


def stream_records(names: tuple[str, ...], size: int) -> bytes:
    out = b""
    for index, name in enumerate(names):
        encoded = utf16(name)
        last = index == len(names) - 1
        step = 0 if last else align(24 + len(encoded))
        record = stream_raw(step, len(encoded), encoded, size)
        out += record if last else record.ljust(step, b"\0")
    return out


def dir_raw(
    step: int, name_length: int, name: bytes, attrs: int = 0x20, file_id: bytes = DOT_ID
) -> bytes:
    """FILE_ID_EXTD_DIR_INFORMATION: header 88, attrs@56, length@60, id@72."""
    header = struct.pack(
        "<II6qIIII16s", step, 0, 0, 0, 0, 0, 0, 0, attrs, name_length, 0, 0, file_id
    )
    return header + name


def dir_page(entries: list[tuple[str, bool, bytes]]) -> bytes:
    out = b""
    for index, (name, directory, file_id) in enumerate(entries):
        encoded = utf16(name)
        last = index == len(entries) - 1
        step = 0 if last else align(88 + len(encoded))
        record = dir_raw(step, len(encoded), encoded, 0x10 if directory else 0x20, file_id)
        out += record if last else record.ljust(step, b"\0")
    return out


def write(target: Any, payload: bytes) -> None:
    """Copies synthetic bytes into a ctypes object the backend allocated."""
    room = ctypes.sizeof(target)
    ctypes.memmove(ctypes.addressof(target), payload[:room], min(len(payload), room))


def set_iosb(iosb: Any, status: int, information: int) -> None:
    write(iosb, struct.pack("<i4xQ", status, information))


def put_cell(cell: Any, value: int) -> None:
    write(cell, struct.pack("<Q", value))


# -- simulated NT volume --


class Node:
    def __init__(self, name: str, kind: str, data: bytes = b"") -> None:
        self.name, self.kind, self.data = name, kind, data
        self.children: dict[str, Node] = {}
        self.file_id = node_id()
        self.change = 1000
        self.volume = VOLUME
        self.links = 1
        self.pending = 0
        self.reparse = False
        self.streams: tuple[str, ...] = ("::$DATA",) if kind == "FILE" else ()

    def attributes(self) -> int:
        value = 0x10 if self.kind == "DIR" else 0x20
        return value | (0x400 if self.reparse else 0)

    def payload(self, info_class: int) -> bytes:
        if info_class == 0:
            return struct.pack("<qqqqI4x", 1, 2, 3, self.change, self.attributes())
        if info_class == 1:
            size, directory = len(self.data), int(self.kind == "DIR")
            return struct.pack("<qqIBB2x", size, size, self.links, self.pending, directory)
        if info_class == 9:
            return struct.pack("<II", self.attributes(), 0xA000000C if self.reparse else 0)
        return struct.pack("<Q16s", self.volume, self.file_id)


class FakeNt:
    """The seven fixed api operations; every call and address is recorded."""

    def __init__(self, root: Node) -> None:
        self.root = root
        self.raw = 0x400
        self.handles: dict[int, Node] = {}
        self.created: list[int] = []
        self.closed: list[int] = []
        self.calls: list[tuple[str, str]] = []
        self.seen: list[tuple[str, str, tuple[int, ...]]] = []
        self.counts: dict[tuple[str, str], int] = {}
        self.hooks: dict[tuple[Any, ...], Hook] = {}
        self.violations: list[str] = []
        self.rights: list[tuple[str, tuple[int, int, int, int]]] = []
        self.roots: list[tuple[str, int]] = []
        self.restarts: list[tuple[str, bool]] = []
        self.reads: list[tuple[str, int, int]] = []
        self.cursor: dict[int, int] = {}
        self.page_records = 64
        self.read_chunk = 4096
        self.fs_name = "NTFS"
        self.device = (7, 0)

    def api(self) -> SimpleNamespace:
        return SimpleNamespace(**{name: getattr(self, name) for name in API_OPERATIONS})

    def check(self, ok: bool, label: str) -> None:
        if not ok:
            self.violations.append(label)

    def _call(self, op: str, name: str, default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        self.calls.append((op, name))
        self.seen.append((op, name, extra.addresses))  # recorded before any effect
        key = (op, name)
        count = self.counts[key] = self.counts.get(key, 0) + 1
        hook = self.hooks.get((op, name, count), self.hooks.get(key))
        return default() if hook is None else hook(default, extra)

    def node(self, raw: Any) -> Node:
        node = self.handles.get(raw) if type(raw) is int else None
        if node is None:
            self.violations.append("stale-handle")
            return Node("<stale>", "DIR")
        return node

    def fail(self, iosb: Any, status: int) -> int:
        set_iosb(iosb, status, 0)
        return status

    def io_extra(self, iosb: Any, buffer: Any, node: Node) -> SimpleNamespace:
        addresses = (ctypes.addressof(iosb), ctypes.addressof(buffer))
        return SimpleNamespace(iosb=iosb, buffer=buffer, node=node, nt=self, addresses=addresses)

    def complete(self, iosb: Any, buffer: Any, payload: bytes) -> int:
        write(buffer, payload)
        set_iosb(iosb, SUCCESS, len(payload))
        return SUCCESS

    def create(self, *args: Any) -> Any:
        cell, access, attributes, iosb, share, disposition, options = args
        raw_attributes = bytes(attributes)
        self.check(len(raw_attributes) == 48, "attributes-size")
        self.check(ctypes.sizeof(iosb) == 16 and ctypes.sizeof(cell) == 8, "out-size")
        fields = struct.unpack("<I4xQQI4xQQ", raw_attributes.ljust(48, b"\0")[:48])
        length, root_dir, name_at, flags, descriptor, quality = fields
        self.check((length, flags, descriptor, quality) == (48, 0, 0, 0), "attributes")
        self.check(bytes(cell) == bytes(8), "cell-not-empty")
        unicode = ctypes.string_at(name_at, 16) if name_at else bytes(16)
        used, maximum = struct.unpack_from("<HH", unicode)
        text_at = struct.unpack_from("<Q", unicode, 8)[0]
        self.check(used % 2 == 0 and 0 < used <= maximum and text_at != 0, "unicode")
        text = ctypes.string_at(text_at, used) if text_at else b""
        name = text.decode("utf-16-le", "surrogatepass")
        directory = bool(options & 0x1)
        given = (access, share, disposition, options)
        self.check(given == (DIR_RIGHTS if directory else FILE_RIGHTS), "rights")
        self.rights.append((name, given))
        self.roots.append((name, root_dir))
        node: Node | None = None
        if root_dir == 0:
            self.check(name == ANCHOR, "anchor-name")
            node = self.root if name == ANCHOR else None
        else:
            parent = self.handles.get(root_dir)
            self.check(parent is not None, "parent")
            node = None if parent is None else parent.children.get(name)
        addresses = (
            ctypes.addressof(cell),
            ctypes.addressof(iosb),
            ctypes.addressof(attributes),
            name_at,
            text_at,
        )

        def default() -> int:
            found = node  # local, so the None check narrows for the type checker
            if found is None:
                return self.fail(iosb, NAME_NOT_FOUND)
            if directory != (found.kind == "DIR"):
                return self.fail(iosb, NOT_A_DIRECTORY if directory else FILE_IS_A_DIRECTORY)
            self.raw += 4
            self.handles[self.raw] = found
            self.created.append(self.raw)
            put_cell(cell, self.raw)
            set_iosb(iosb, SUCCESS, FILE_OPENED)
            return SUCCESS

        extra = SimpleNamespace(cell=cell, iosb=iosb, node=node, nt=self, addresses=addresses)
        return self._call("create", name, default, extra)

    def query_info(self, *args: Any) -> Any:
        raw, info_class, buffer, size = args
        node = self.node(raw)
        self.check(size == ctypes.sizeof(buffer) == INFO_SIZES.get(info_class), "info-args")

        def default() -> int:
            write(buffer, node.payload(info_class))
            return 1

        addresses = (ctypes.addressof(buffer),)
        extra = SimpleNamespace(buffer=buffer, node=node, nt=self, addresses=addresses)
        return self._call("info", node.name + "#" + str(info_class), default, extra)

    def query_file(self, *args: Any) -> Any:
        raw, iosb, buffer, length, info_class = args
        node = self.node(raw)
        self.check(info_class == 22 and length == 4096 == ctypes.sizeof(buffer), "stream-args")

        def default() -> int:
            return self.complete(iosb, buffer, stream_records(node.streams, len(node.data)))

        return self._call("stream", node.name, default, self.io_extra(iosb, buffer, node))

    def query_volume(self, *args: Any) -> Any:
        raw, iosb, buffer, length, fs_class = args
        node = self.node(raw)
        self.check(fs_class in (4, 5) and 0 < length <= ctypes.sizeof(buffer), "volume-args")

        def default() -> int:
            if fs_class == 4:
                payload = struct.pack("<II", *self.device)
            else:
                encoded = utf16(self.fs_name)
                payload = struct.pack("<IiI", 0x00C706FF, 255, len(encoded)) + encoded
            if len(payload) > length:
                return self.fail(iosb, BUFFER_OVERFLOW)
            return self.complete(iosb, buffer, payload)

        return self._call("volume", str(fs_class), default, self.io_extra(iosb, buffer, node))

    def query_directory(self, *args: Any) -> Any:
        raw, iosb, buffer, length, info_class, single, restart = args
        node = self.node(raw)
        self.check(info_class == 60 and length == 65536 <= ctypes.sizeof(buffer), "dir-args")
        self.check(single is False and type(restart) is bool, "dir-flags")
        self.restarts.append((node.name, restart))

        def default() -> int:
            if restart:
                self.cursor[raw] = 0
            names = [(".", True, DOT_ID), ("..", True, DOT_ID)] + [
                (name, child.kind == "DIR", child.file_id)
                for name, child in sorted(node.children.items())
            ]
            start = self.cursor.get(raw, 0)
            page = names[start : start + self.page_records]
            if not page:
                return self.fail(iosb, NO_MORE_FILES)
            self.cursor[raw] = start + len(page)
            return self.complete(iosb, buffer, dir_page(page))

        return self._call("dir", node.name, default, self.io_extra(iosb, buffer, node))

    def read(self, *args: Any) -> Any:
        raw, iosb, buffer, length, offset = args
        node = self.node(raw)
        self.check(type(offset) in (ctypes.c_longlong, ctypes.c_int64), "offset-type")
        self.check(0 < length <= 4096 and length <= ctypes.sizeof(buffer), "read-length")
        start = struct.unpack("<q", bytes(offset))[0]
        self.reads.append((node.name, start, length))

        def default() -> int:
            chunk = node.data[start : start + min(length, self.read_chunk)]
            if not chunk:
                return self.fail(iosb, END_OF_FILE)
            return self.complete(iosb, buffer, chunk)

        extra = self.io_extra(iosb, buffer, node)
        extra.addresses += (ctypes.addressof(offset),)
        return self._call("read", node.name, default, extra)

    def close(self, *args: Any) -> Any:
        (raw,) = args
        self.closed.append(raw)
        node = self.handles.get(raw) if type(raw) is int else None
        name = "<unknown>" if node is None else node.name

        def default() -> int:
            return SUCCESS if self.handles.pop(raw, None) is not None else INVALID_HANDLE

        return self._call("close", name, default, SimpleNamespace(nt=self, addresses=()))


def path(parent: Node, *names: str) -> Node:
    node = parent
    for name in names:
        node = node.children.setdefault(name, Node(name, "DIR"))
    return node


def make_tree(bundle: Any, source: bytes) -> Node:
    root = Node("<anchor>", "DIR")
    poc = path(root, *REPO_CHAIN)
    poc.children[VERIFY_NAME] = Node(VERIFY_NAME, "FILE", source)
    public = path(poc, "evidence", PUBLIC_NAME)
    public.children["summary.json"] = Node("summary.json", "FILE", bundle.summary_raw)
    public.children["transport.json"] = Node("transport.json", "FILE", bundle.transport_raw)
    private = path(root, *TEMP_CHAIN, PRIVATE_NAME)
    for name, raw in bundle.private.items():
        case, leaf = name.split("/")
        path(private, case).children[leaf] = Node(leaf, "FILE", raw)
    return root


def small_tree(data: bytes = DATA) -> Node:
    root = Node("<anchor>", "DIR")
    folder = path(root, "dir")
    folder.children["file.bin"] = Node("file.bin", "FILE", data)
    path(folder, "sub")
    return root


def named(root: Node, name: str) -> Node:
    pending = [root]
    while pending:
        node = pending.pop(0)
        if node.name == name:
            return node
        pending.extend(child for _key, child in sorted(node.children.items()))
    raise AssertionError("fixture node not found")


# -- hooks --


def raise_before(error: BaseException) -> Hook:
    def hook(_default: Callable[[], Any], _extra: SimpleNamespace) -> Any:
        raise error

    return hook


def raise_after(error: BaseException) -> Hook:
    def hook(default: Callable[[], Any], _extra: SimpleNamespace) -> Any:
        default()
        raise error

    return hook


def returns(value: Any) -> Hook:
    def hook(_default: Callable[[], Any], _extra: SimpleNamespace) -> Any:
        return value

    return hook


def returns_status(status: Any) -> Hook:
    def hook(_default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        iosb = getattr(extra, "iosb", None)
        if iosb is not None and type(status) is int:
            set_iosb(iosb, status, 0)
        return status

    return hook


def outcome(status: Any, cell: int | None = None, information: int = FILE_OPENED) -> Hook:
    """An open that completes with the given status, cell and Information."""

    def hook(_default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        in_range = type(status) is int and -(1 << 31) <= status < (1 << 31)
        set_iosb(extra.iosb, status if in_range else 0, information)
        if cell is not None:
            put_cell(extra.cell, cell)
        return status

    return hook


def alias() -> Hook:
    """A 'successful' open whose raw handle is the already open anchor."""

    def hook(_default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        put_cell(extra.cell, extra.nt.created[0])
        set_iosb(extra.iosb, SUCCESS, FILE_OPENED)
        return SUCCESS

    return hook


def filled(payload: bytes, status: int = SUCCESS, information: int | None = None) -> Hook:
    def hook(_default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        write(extra.buffer, payload)
        set_iosb(extra.iosb, status, len(payload) if information is None else information)
        return status

    return hook


def metadata(payload: bytes) -> Hook:
    def hook(_default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        write(extra.buffer, payload)
        return 1

    return hook


def break_handle(lab: Any, fake: FakeNt, name: str, error: BaseException) -> None:
    """The collector Handle allocation fails right after the open of `name`."""
    handle = lab.glob["Handle"]
    original = handle.__init__

    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        if fake.calls and fake.calls[-1] == ("create", name):
            raise error
        original(self, *args, **kwargs)

    lab.monkeypatch.setattr(handle, "__init__", init)


# -- fixture and helpers --


def forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("filesystem, process or native effect after setup")


@pytest.fixture
def lab(monkeypatch: Any) -> Any:
    win32 = runpy.run_path(str(WIN32))
    collector_bytes = COLLECTOR.read_bytes()
    collector = runpy.run_path(str(COLLECTOR))
    builder = runpy.run_path(str(VERIFY_TESTS))
    source = VERIFY_SOURCE.read_bytes()
    for owner, name in (
        (os, "open"),
        (os, "listdir"),
        (os, "scandir"),
        (os, "system"),
        (Path, "open"),
        (Path, "stat"),
        (Path, "lstat"),
        (subprocess, "Popen"),
        (ctypes, "WinDLL"),
        (ctypes, "CDLL"),
        (threading.Thread, "start"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    glob = collector["collect"].__globals__
    return SimpleNamespace(
        win32=win32,
        glob=glob,
        builder=builder,
        source=source,
        collector_sha=hashlib.sha256(collector_bytes).hexdigest(),
        monkeypatch=monkeypatch,
    )


def make(
    lab: Any, root: Node | None = None, page_records: int = 64, read_chunk: int = 4096
) -> SimpleNamespace:
    tree = small_tree() if root is None else root
    fake = FakeNt(tree)
    fake.page_records, fake.read_chunk = page_records, read_chunk
    backend = lab.win32["_Win32Backend"](fake.api(), lab.glob)
    return SimpleNamespace(nt=fake, backend=backend, root=tree)


def bundle_tree(lab: Any, scenario: str) -> tuple[Any, Node]:
    bundle = lab.builder["build"](lab.builder[scenario]())
    return bundle, make_tree(bundle, lab.source)


def prepare(
    lab: Any, scenario: str = "approved", page_records: int = 64, read_chunk: int = 4096
) -> SimpleNamespace:
    bundle, root = bundle_tree(lab, scenario)
    ctx = make(lab, root, page_records, read_chunk)
    lab.monkeypatch.setitem(lab.glob, "_backend", lambda: ctx.backend)
    ctx.bundle = bundle
    return ctx


def detached(lab: Any) -> tuple[FakeNt, Any, Node]:
    """Wires a backend that, after the first collect, only the policy holds."""
    _bundle, root = bundle_tree(lab, "approved")
    fake = FakeNt(root)
    box = [lab.win32["_Win32Backend"](fake.api(), lab.glob)]
    ref = weakref.ref(box[0])
    lab.monkeypatch.setitem(lab.glob, "_backend", box.pop)
    return fake, ref, root


def collect(lab: Any) -> Any:
    return lab.glob["collect"](NONCE, ARGV0)


def slot(lab: Any) -> Any:
    return lab.glob["Slot"]()


def anchor(lab: Any, backend: Any) -> Any:
    target = slot(lab)
    backend.open_anchor(target)
    return target.value


def child(lab: Any, backend: Any, parent: Any, name: str, kind: str = "DIR") -> Any:
    target = slot(lab)
    backend.open_child(parent, name, kind, target)
    return target.value


def opened_file(lab: Any, ctx: SimpleNamespace) -> tuple[Any, Any]:
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    return folder, child(lab, ctx.backend, folder, "file.bin", "FILE")


def retained(backend: Any) -> set[int]:
    """Addresses of the ctypes objects held by the backend's retention ledger."""
    found: set[int] = set()
    pending: list[Any] = list(backend._retained)
    while pending:
        item = pending.pop()
        if isinstance(item, (tuple, list)):
            pending.extend(item)
            continue
        if isinstance(item, dict):
            pending.extend(item.values())
            continue
        try:
            found.add(ctypes.addressof(item))
        except TypeError:
            continue
    return found


def seen(fake: FakeNt, op: str, name: str) -> set[int]:
    matches = [entry[2] for entry in fake.seen if entry[:2] == (op, name)]
    assert matches, "the effect was never reached"
    return {address for address in matches[-1] if address}


def assert_blocked(lab: Any, ctx: SimpleNamespace, handle: Any) -> None:
    """A poisoned backend refuses every later native call, close included."""
    before = list(ctx.nt.calls)
    fresh = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_anchor(fresh)
    assert fresh.value is None
    fresh = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_child(handle, "dir", "DIR", fresh)
    assert fresh.value is None
    with pytest.raises(OSError):
        ctx.backend.query(handle)
    with pytest.raises(OSError):
        ctx.backend.list_dir(handle, 16)
    with pytest.raises(OSError):
        ctx.backend.read(handle, 1)
    assert ctx.backend.close(handle) is False
    assert ctx.nt.calls == before


# -- default path, purity, pins --


def test_frozen_inputs_match_their_pins(lab: Any) -> None:
    assert lab.collector_sha == COLLECTOR_SHA
    assert hashlib.sha256(lab.source).hexdigest() == VERIFY_SHA
    assert lab.builder["NONCE"] == NONCE and lab.builder["ARGV0"] == ARGV0


def test_public_backend_is_unavailable_without_any_dll(monkeypatch: Any, capsys: Any) -> None:
    for name in ("WinDLL", "CDLL", "OleDLL", "PyDLL"):
        monkeypatch.setattr(ctypes, name, forbidden, raising=False)
    module = runpy.run_path(str(WIN32))
    monkeypatch.setitem(module["backend"].__globals__, "_load_native", forbidden)
    assert module["backend"]() is None
    assert callable(module["_load_native"])
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_the_collector_stays_unavailable_until_a_test_wires_the_seam(lab: Any) -> None:
    assert lab.glob["_backend"]() is None
    assert collect(lab) == ("INVALID", "COLLECT_UNAVAILABLE", None, None)
    assert lab.glob["_POISON"] == [] and lab.glob["_ACTIVE"] == []


BANNED_API = re.compile(
    r"NtWrite|WriteFile|NtSetInformation|SetFile|NtDelete|DeleteFile|MoveFile|"
    r"DeviceIoControl|FsControl|Cancel|WaitFor|NtWait|CreateEvent|Process|Thread|"
    r"LoadLibrary|GetProcAddress"
)
TOP_LEVEL = (
    ast.Import,
    ast.ImportFrom,
    ast.Assign,
    ast.AnnAssign,
    ast.ClassDef,
    ast.FunctionDef,
    ast.Expr,
)


def test_module_source_is_pure_lazy_and_closed() -> None:
    tree = ast.parse(WIN32.read_bytes())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"ctypes", "struct"}
    names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
    banned = {"open", "print", "input", "eval", "exec", "compile", "__import__", "globals"}
    assert not set(names) & banned
    words = names + [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
    strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    words += strings + [
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    ]
    assert not [word for word in words if BANNED_API.search(word)]
    library = re.compile(r"(?i)ntdll|kernel32|kernelbase|advapi32|user32|\w+\.dll")
    assert {text for text in strings if library.fullmatch(text)} <= {"ntdll", "kernel32"}
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not [func for func in calls if isinstance(func, ast.Name) and func.id == "_load_native"]
    loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_native"
    )
    inside = {id(node) for node in ast.walk(loader)}
    loaders = {"WinDLL", "windll", "CDLL", "cdll", "OleDLL", "PyDLL", "LibraryLoader"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in loaders:
            assert id(node) in inside
    for statement in tree.body:
        assert isinstance(statement, TOP_LEVEL)
        if isinstance(statement, ast.Expr):
            assert isinstance(statement.value, ast.Constant)
    assert not any(
        isinstance(node, ast.If) and "__main__" in ast.unparse(node.test) for node in ast.walk(tree)
    )


# -- fixed ABI oracles (literal documented x64 numbers) --


def test_x64_layouts_match_the_documented_offsets(lab: Any) -> None:
    module = lab.win32
    assert ctypes.sizeof(ctypes.c_void_p) == 8  # x64 lab precondition, not a skip
    expected: dict[str, tuple[int, dict[str, tuple[int, int]]]] = {
        "UNICODE_STRING": (16, {"Length": (0, 2), "MaximumLength": (2, 2), "Buffer": (8, 8)}),
        "OBJECT_ATTRIBUTES": (
            48,
            {
                "Length": (0, 4),
                "RootDirectory": (8, 8),
                "ObjectName": (16, 8),
                "Attributes": (24, 4),
                "SecurityDescriptor": (32, 8),
                "SecurityQualityOfService": (40, 8),
            },
        ),
        "IO_STATUS_BLOCK": (16, {"Information": (8, 8)}),
        "FILE_BASIC_INFO": (
            40,
            {
                "CreationTime": (0, 8),
                "LastAccessTime": (8, 8),
                "LastWriteTime": (16, 8),
                "ChangeTime": (24, 8),
                "FileAttributes": (32, 4),
            },
        ),
        "FILE_STANDARD_INFO": (
            24,
            {
                "AllocationSize": (0, 8),
                "EndOfFile": (8, 8),
                "NumberOfLinks": (16, 4),
                "DeletePending": (20, 1),
                "Directory": (21, 1),
            },
        ),
        "FILE_ATTRIBUTE_TAG_INFO": (8, {"FileAttributes": (0, 4), "ReparseTag": (4, 4)}),
        "FILE_ID_INFO": (24, {"VolumeSerialNumber": (0, 8), "FileId": (8, 16)}),
    }
    for name, (size, fields) in expected.items():
        layout = module[name]
        assert ctypes.sizeof(layout) == size, name
        for field, (offset, width) in fields.items():
            descriptor = getattr(layout, field)
            assert (descriptor.offset, descriptor.size) == (offset, width), (name, field)
    iosb = module["IO_STATUS_BLOCK"].from_buffer_copy(struct.pack("<i4xQ", NAME_NOT_FOUND, 7))
    assert iosb.Status == NAME_NOT_FOUND and iosb.Information == 7
    raw = struct.pack("<qqIBB2x", 5, -1, 0xFFFFFFFF, 1, 0)
    standard = module["FILE_STANDARD_INFO"].from_buffer_copy(raw)
    assert standard.EndOfFile == -1 and standard.NumberOfLinks == 0xFFFFFFFF
    assert standard.DeletePending == 1 and standard.Directory == 0
    raw = struct.pack("<qqqqI4x", 1, 2, 3, -4, 0x410)
    basic = module["FILE_BASIC_INFO"].from_buffer_copy(raw)
    assert basic.ChangeTime == -4 and basic.FileAttributes == 0x410
    raw = struct.pack("<II", 0x10, 0xA000000C)
    tag = module["FILE_ATTRIBUTE_TAG_INFO"].from_buffer_copy(raw)
    assert tag.FileAttributes == 0x10 and tag.ReparseTag == 0xA000000C
    ident_raw = struct.pack("<Q16s", (1 << 64) - 1, bytes(range(16)))
    ident = module["FILE_ID_INFO"].from_buffer_copy(ident_raw)
    assert ident.VolumeSerialNumber == (1 << 64) - 1 and bytes(ident)[8:] == bytes(range(16))


def test_prototypes_are_closed_and_llp64(lab: Any) -> None:
    module = lab.win32
    sizes = {
        "NtCreateFile": ("ntdll", (8, 4, 8, 8, 8, 4, 4, 4, 4, 8, 4)),
        "NtQueryInformationFile": ("ntdll", (8, 8, 8, 4, 4)),
        "NtQueryVolumeInformationFile": ("ntdll", (8, 8, 8, 4, 4)),
        "NtQueryDirectoryFile": ("ntdll", (8, 8, 8, 8, 8, 8, 4, 4, 1, 8, 1)),
        "NtReadFile": ("ntdll", (8, 8, 8, 8, 8, 8, 4, 8, 8)),
        "NtClose": ("ntdll", (8,)),
        "GetFileInformationByHandleEx": ("kernel32", (8, 4, 8, 4)),
    }
    prototypes = module["PROTOTYPES"]
    assert set(prototypes) == set(sizes)
    for name, (library, widths) in sizes.items():
        got_library, argtypes, restype = prototypes[name]
        assert got_library == library, name
        assert tuple(ctypes.sizeof(kind) for kind in argtypes) == widths, name
        assert ctypes.sizeof(restype) == 4 and restype(-1).value == -1, name  # NTSTATUS / BOOL
    pointer = ctypes.POINTER
    create = prototypes["NtCreateFile"][1]
    assert create[2] is pointer(module["OBJECT_ATTRIBUTES"])
    assert create[3] is pointer(module["IO_STATUS_BLOCK"])
    for name, index in (
        ("NtQueryInformationFile", 1),
        ("NtQueryVolumeInformationFile", 1),
        ("NtQueryDirectoryFile", 4),
        ("NtReadFile", 4),
    ):
        assert prototypes[name][1][index] is pointer(module["IO_STATUS_BLOCK"]), name
    assert prototypes["NtReadFile"][1][7] is pointer(ctypes.c_longlong)
    assert module["API_OPERATIONS"] == API_OPERATIONS


def test_unknown_marker_is_distinct_and_closed(lab: Any) -> None:
    marker = lab.win32["UNKNOWN"]
    assert marker is not None and type(marker) is not lab.glob["Handle"]
    assert type(marker) not in (int, str, bytes, tuple, bool)
    assert "0x" not in repr(marker)


# -- opens and the custody marker --


def test_opens_pass_exact_rights_names_and_relative_roots(lab: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    folder = child(lab, ctx.backend, root, "dir")
    leaf = child(lab, ctx.backend, folder, "file.bin", "FILE")
    handle = lab.glob["Handle"]
    assert all(type(value) is handle for value in (root, folder, leaf))
    assert len({root.token, folder.token, leaf.token}) == 3
    created = ctx.nt.created
    assert ctx.nt.roots == [(ANCHOR, 0), ("dir", created[0]), ("file.bin", created[1])]
    assert ctx.nt.rights == [(ANCHOR, DIR_RIGHTS), ("dir", DIR_RIGHTS), ("file.bin", FILE_RIGHTS)]
    assert ("volume", "4") in ctx.nt.calls and ("volume", "5") in ctx.nt.calls
    assert ctx.nt.violations == []
    assert retained(ctx.backend) == set()


def test_marker_is_published_before_the_effect_and_the_handle_before_the_profile(
    lab: Any,
) -> None:
    ctx = make(lab)
    target = slot(lab)
    observed: list[Any] = []

    def watch(default: Callable[[], Any], _extra: SimpleNamespace) -> Any:
        observed.append(target.value)
        return default()

    ctx.nt.hooks[("create", ANCHOR)] = watch
    ctx.nt.hooks[("volume", "5")] = watch
    ctx.backend.open_anchor(target)
    assert observed[0] is lab.win32["UNKNOWN"]
    assert observed[1] is target.value and type(target.value) is lab.glob["Handle"]


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("", "DIR"),
        ("a/b", "DIR"),
        ("a\\b", "DIR"),
        ("a:b", "DIR"),
        ("a\x00b", "DIR"),
        (".", "DIR"),
        ("..", "DIR"),
        ("x" * 256, "DIR"),
        ("\U0001f600" * 128, "DIR"),
        ("\ud800", "DIR"),
        (SneakyStr("dir"), "DIR"),
        (7, "DIR"),
        ("dir", "dir"),
        ("dir", SneakyStr("DIR")),
        ("dir", None),
    ],
)
def test_invalid_names_and_kinds_have_no_effect(lab: Any, name: Any, kind: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    before = list(ctx.nt.calls)
    target = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_child(root, name, kind, target)
    assert target.value is None and ctx.nt.calls == before


def test_unknown_parents_and_foreign_slots_have_no_effect(lab: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    folder = child(lab, ctx.backend, root, "dir")
    assert ctx.backend.close(folder) is True
    before = list(ctx.nt.calls)
    for parent in (lab.glob["Handle"](999999), folder, object(), None):
        target = slot(lab)
        with pytest.raises(OSError):
            ctx.backend.open_child(parent, "dir", "DIR", target)
        assert target.value is None
    occupied = slot(lab)
    occupied.value = "occupied"
    foreign = SimpleNamespace(value=None)
    for target in (occupied, foreign, None):
        with pytest.raises(OSError):
            ctx.backend.open_child(root, "dir", "DIR", target)
    assert occupied.value == "occupied" and foreign.value is None
    with pytest.raises(OSError):
        ctx.backend.open_anchor(foreign)
    assert foreign.value is None and ctx.nt.calls == before


@pytest.mark.parametrize(
    ("name", "kind", "hook"),
    [
        ("missing", "DIR", None),
        ("file.bin", "DIR", None),
        ("sub", "FILE", None),
        ("sub", "DIR", outcome(ACCESS_DENIED)),
    ],
)
def test_completed_known_failures_clear_the_marker(
    lab: Any, name: str, kind: str, hook: Any
) -> None:
    ctx = make(lab)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    if hook is not None:
        ctx.nt.hooks[("create", name)] = hook
    target = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_child(folder, name, kind, target)
    assert target.value is None
    assert retained(ctx.backend) == set()
    ctx.nt.hooks.clear()
    healthy = child(lab, ctx.backend, folder, "sub")
    assert ctx.backend.close(healthy) is True
    assert ctx.nt.closed == [ctx.nt.created[-1]]


OPEN_OUTCOMES: dict[str, Hook] = {
    "pending": outcome(PENDING),
    "pending-with-cell": outcome(PENDING, cell=0x7770),
    "informational": outcome(REPARSE),
    "warning": outcome(BUFFER_OVERFLOW),
    "failed-nonzero": outcome(ACCESS_DENIED, cell=0x7770),
    "success-null": outcome(SUCCESS),
    "success-invalid": outcome(SUCCESS, cell=INVALID_HANDLE_VALUE),
    "success-created": outcome(SUCCESS, cell=0x7770, information=2),
    "status-none": outcome(None, cell=0x7770),
    "status-bool": outcome(True),
    "status-wide": outcome(1 << 31, cell=0x7770),
    "alias": alias(),
}


@pytest.mark.parametrize("case", sorted(OPEN_OUTCOMES))
def test_uncertain_open_outcomes_keep_the_marker_and_block(lab: Any, case: str) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    ctx.nt.hooks[("create", "dir")] = OPEN_OUTCOMES[case]
    target = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_child(root, "dir", "DIR", target)
    assert target.value is lab.win32["UNKNOWN"]
    assert seen(ctx.nt, "create", "dir") <= retained(ctx.backend)
    assert ctx.nt.closed == []
    assert_blocked(lab, ctx, root)


@pytest.mark.parametrize(
    ("boundary", "error_type"),
    [
        ("before", Signal),
        ("before", OSError),
        ("after", Signal),
        ("after", OSError),
        ("dto", Signal),
        ("dto", MemoryError),
    ],
)
def test_open_boundaries_retain_custody(lab: Any, boundary: str, error_type: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    error = error_type("fictitious")
    if boundary == "before":
        ctx.nt.hooks[("create", "dir")] = raise_before(error)
    elif boundary == "after":
        ctx.nt.hooks[("create", "dir")] = raise_after(error)
    else:
        break_handle(lab, ctx.nt, "dir", error)
    target = slot(lab)
    with pytest.raises(error_type) as caught:
        ctx.backend.open_child(root, "dir", "DIR", target)
    assert caught.value is error
    assert target.value is lab.win32["UNKNOWN"]
    assert seen(ctx.nt, "create", "dir") <= retained(ctx.backend)
    assert len(ctx.nt.created) == (1 if boundary == "before" else 2)
    assert ctx.nt.closed == []
    assert_blocked(lab, ctx, root)


def spoil_profile(fake: FakeNt, case: str) -> None:
    valid = struct.pack("<IiI", 0, 255, 8) + utf16("NTFS")
    if case == "fat":
        fake.fs_name = "FAT32"
    elif case == "lowercase":
        fake.fs_name = "ntfs"
    elif case == "network":
        fake.device = (0x14, 0)
    elif case == "removable":
        fake.device = (7, 0x1)
    elif case == "remote":
        fake.device = (7, 0x10)
    elif case == "device-error":
        fake.hooks[("volume", "4")] = returns_status(ACCESS_DENIED)
    elif case == "attribute-error":
        fake.hooks[("volume", "5")] = returns_status(ACCESS_DENIED)
    elif case == "short":
        fake.hooks[("volume", "5")] = filled(valid[:8])
    elif case == "name-past-information":
        fake.hooks[("volume", "5")] = filled(valid, information=14)
    else:
        fake.hooks[("volume", "5")] = filled(valid, status=BUFFER_OVERFLOW)


PROFILE_CASES = [
    "fat",
    "lowercase",
    "network",
    "removable",
    "remote",
    "device-error",
    "attribute-error",
    "short",
    "name-past-information",
    "overflow",
]


@pytest.mark.parametrize("case", PROFILE_CASES)
def test_anchor_profile_failure_is_a_published_closable_open(lab: Any, case: str) -> None:
    ctx = make(lab)
    spoil_profile(ctx.nt, case)
    target = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_anchor(target)
    assert type(target.value) is lab.glob["Handle"]
    assert ctx.backend.close(target.value) is True
    assert len(ctx.nt.created) == 1 and ctx.nt.closed == ctx.nt.created


# -- metadata, streams --


def test_query_composes_the_info_from_the_public_classes(lab: Any) -> None:
    ctx = make(lab)
    folder, leaf = opened_file(lab, ctx)
    node = named(ctx.root, "file.bin")
    info = ctx.backend.query(leaf)
    assert type(info) is lab.glob["Info"]
    fields = (
        info.reparse,
        info.directory,
        info.delete_pending,
        info.volume,
        info.file_id,
        info.links,
        info.end_of_file,
        info.change_time,
        info.streams,
    )
    assert fields == (False, False, False, VOLUME, node.file_id, 1, len(DATA), 1000, ("::$DATA",))
    directory = ctx.backend.query(folder)
    assert directory.directory is True and directory.streams == () and directory.end_of_file == 0
    sub = named(ctx.root, "sub")
    sub.reparse, sub.pending = True, 1
    flagged = ctx.backend.query(child(lab, ctx.backend, folder, "sub"))
    assert flagged.reparse is True and flagged.delete_pending is True
    classes = {name for op, name in ctx.nt.calls if op == "info" and name.startswith("file.bin#")}
    assert classes == {"file.bin#0", "file.bin#1", "file.bin#9", "file.bin#18"}
    assert ctx.nt.calls.count(("stream", "file.bin")) == 1
    assert ctx.nt.violations == []


def test_alternate_streams_are_reported_from_complete_records(lab: Any) -> None:
    ctx = make(lab)
    named(ctx.root, "file.bin").streams = ("::$DATA", ":extra:$DATA")
    _folder, leaf = opened_file(lab, ctx)
    assert ctx.backend.query(leaf).streams == ("::$DATA", ":extra:$DATA")


METADATA_CASES: list[tuple[str, Hook]] = [
    ("file.bin#0", returns(0)),
    ("file.bin#1", returns(0)),
    ("file.bin#9", returns(0)),
    ("file.bin#18", returns(0)),
    ("file.bin#1", returns(None)),
    ("file.bin#1", returns("1")),
    ("file.bin#1", metadata(struct.pack("<qqIBB2x", 0, len(DATA), 1, 0, 2))),
    ("file.bin#1", metadata(struct.pack("<qqIBB2x", 0, len(DATA), 1, 2, 0))),
    ("file.bin#1", metadata(struct.pack("<qqIBB2x", 0, len(DATA), 1, 0, 1))),
    ("file.bin#1", metadata(struct.pack("<qqIBB2x", 0, -1, 1, 0, 0))),
    ("file.bin#9", metadata(struct.pack("<II", 0x21, 0))),
]


@pytest.mark.parametrize(("key", "hook"), METADATA_CASES)
def test_malformed_fixed_metadata_fails_without_poison(lab: Any, key: str, hook: Hook) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)
    ctx.nt.hooks[("info", key)] = hook
    with pytest.raises(OSError):
        ctx.backend.query(leaf)
    assert ctx.backend.close(leaf) is True


DATA_NAME = utf16("::$DATA")
UNALIGNED = stream_raw(39, 14, DATA_NAME).ljust(39, b"\0") + stream_raw(0, 14, DATA_NAME)
STREAM_CASES: list[tuple[str, Hook]] = [
    ("information-over-buffer", filled(stream_records(("::$DATA",), 1), information=4097)),
    ("file-without-records", filled(b"", information=0)),
    ("header-past-used", filled(b"\0" * 10)),
    ("odd-name", filled(stream_raw(0, 13, DATA_NAME))),
    ("empty-name", filled(stream_raw(0, 0, b""))),
    ("long-name", filled(stream_raw(0, 130, b"a\0" * 65))),
    ("name-past-used", filled(stream_raw(0, 14, DATA_NAME[:10]))),
    ("unaligned", filled(UNALIGNED)),
    ("overlap", filled(stream_raw(24, 14, DATA_NAME)[:24] + stream_raw(0, 14, DATA_NAME))),
    ("next-past-used", filled(stream_raw(4096, 14, DATA_NAME))),
    ("lone-surrogate", filled(stream_records(("\ud800",), 1))),
    ("too-many", filled(stream_records(tuple(":s" + str(n) + ":$DATA" for n in range(9)), 1))),
    ("overflow", filled(stream_records(("::$DATA",), 1), status=BUFFER_OVERFLOW)),
    ("denied", filled(b"", status=ACCESS_DENIED, information=0)),
]


@pytest.mark.parametrize(("case", "hook"), STREAM_CASES)
def test_malformed_file_streams_fail_without_poison(lab: Any, case: str, hook: Hook) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)
    ctx.nt.hooks[("stream", "file.bin")] = hook
    with pytest.raises(OSError):
        ctx.backend.query(leaf)
    assert ctx.backend.close(leaf) is True, case


@pytest.mark.parametrize(
    "hook",
    [
        filled(stream_records(("::$DATA",), 0)),
        filled(b"", status=ACCESS_DENIED, information=0),
        filled(b"", status=INVALID_INFO_CLASS, information=0),
        filled(b"", status=BUFFER_OVERFLOW, information=0),
        filled(b"", status=END_OF_FILE, information=0),
    ],
)
def test_directory_streams_accept_only_a_completed_empty_success(lab: Any, hook: Hook) -> None:
    ctx = make(lab)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    ctx.nt.hooks[("stream", "dir")] = hook
    with pytest.raises(OSError):
        ctx.backend.query(folder)
    assert ctx.backend.close(folder) is True


# -- listing --


@pytest.mark.parametrize("page_records", [64, 1])
def test_listing_maps_entries_filters_dots_and_restarts(lab: Any, page_records: int) -> None:
    ctx = make(lab, page_records=page_records)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    first = ctx.backend.list_dir(folder, 16)
    second = ctx.backend.list_dir(folder, 16)
    assert type(first) is tuple and first == second
    assert all(type(entry) is lab.glob["Entry"] for entry in first)
    leaf, sub = named(ctx.root, "file.bin"), named(ctx.root, "sub")
    expected = {("file.bin", False, leaf.file_id), ("sub", True, sub.file_id)}
    assert {(entry.name, entry.directory, entry.file_id) for entry in first} == expected
    flags = [flag for name, flag in ctx.nt.restarts if name == "dir"]
    one = [True] + [False] * (1 if page_records == 64 else 4)
    assert flags == one + one
    assert ctx.nt.violations == []


def test_listing_budget_admits_sixteen_one_record_pages_and_rejects_seventeen(lab: Any) -> None:
    for count, admitted in ((16, True), (17, False)):
        root = Node("<anchor>", "DIR")
        folder = path(root, "dir")
        for index in range(count):
            path(folder, "c" + str(index).zfill(2))
        ctx = make(lab, root, page_records=1)
        handle = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
        if admitted:
            assert len(ctx.backend.list_dir(handle, 16)) == 16
        else:
            with pytest.raises(OSError):
                ctx.backend.list_dir(handle, 16)
        assert ctx.nt.calls.count(("dir", "dir")) <= 16 + 3


A = utf16("a")
LISTING_CASES: list[tuple[str, Hook]] = [
    ("information-over-buffer", filled(dir_page([("a", False, DOT_ID)]), information=65537)),
    ("header-past-used", filled(b"\0" * 40)),
    ("odd-name", filled(dir_raw(0, 3, A + A))),
    ("empty-name", filled(dir_raw(0, 0, b""))),
    ("long-name", filled(dir_raw(0, 512, A * 256))),
    ("name-past-used", filled(dir_raw(0, 20, A))),
    ("unaligned", filled(dir_raw(90, 2, A).ljust(90, b"\0") + dir_raw(0, 2, utf16("b")))),
    ("overlap", filled(dir_raw(88, 2, A)[:88] + dir_raw(0, 2, utf16("b")))),
    ("next-past-used", filled(dir_raw(96, 2, A))),
    ("lone-surrogate", filled(dir_page([("\ud800", False, DOT_ID)]))),
    ("slash", filled(dir_page([("a/b", False, DOT_ID)]))),
    ("backslash", filled(dir_page([("a\\b", False, DOT_ID)]))),
    ("colon", filled(dir_page([("a:b", False, DOT_ID)]))),
    ("nul", filled(dir_page([("a\x00b", False, DOT_ID)]))),
    ("duplicate", filled(dir_page([("a", False, DOT_ID), ("a", False, DOT_ID)]))),
    ("dot-twice", filled(dir_page([(".", True, DOT_ID), (".", True, DOT_ID)]))),
    ("success-without-progress", filled(b"", information=0)),
    ("no-more-with-data", filled(dir_page([("a", False, DOT_ID)]), status=NO_MORE_FILES)),
    ("overflow", filled(dir_page([("a", False, DOT_ID)]), status=BUFFER_OVERFLOW)),
    ("denied", filled(b"", status=ACCESS_DENIED, information=0)),
]


@pytest.mark.parametrize(("case", "hook"), LISTING_CASES)
def test_malformed_pages_fail_as_listing_errors(lab: Any, case: str, hook: Hook) -> None:
    ctx = make(lab)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    ctx.nt.hooks[("dir", "dir")] = hook
    with pytest.raises(OSError) as caught:
        ctx.backend.list_dir(folder, 16)
    assert not isinstance(caught.value, NotImplementedError), case
    assert ctx.backend.close(folder) is True


def test_duplicates_are_detected_across_pages(lab: Any) -> None:
    ctx = make(lab, page_records=1)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    leaf = named(ctx.root, "file.bin")
    ctx.nt.hooks[("dir", "dir", 4)] = filled(dir_page([("file.bin", False, leaf.file_id)]))
    with pytest.raises(OSError):
        ctx.backend.list_dir(folder, 16)


@pytest.mark.parametrize("status", [INVALID_INFO_CLASS, NOT_SUPPORTED])
def test_unsupported_class_is_reported_only_on_the_first_page(lab: Any, status: int) -> None:
    ctx = make(lab, page_records=1)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    ctx.nt.hooks[("dir", "dir", 1)] = filled(b"", status=status, information=0)
    with pytest.raises(NotImplementedError):
        ctx.backend.list_dir(folder, 16)
    ctx.nt.hooks.clear()
    ctx.nt.hooks[("dir", "dir", 3)] = filled(b"", status=status, information=0)
    with pytest.raises(OSError) as caught:
        ctx.backend.list_dir(folder, 16)
    assert not isinstance(caught.value, NotImplementedError)


@pytest.mark.parametrize("max_entries", [17, -1, True, 16.0, None])
def test_listing_bound_is_an_exact_small_int(lab: Any, max_entries: Any) -> None:
    ctx = make(lab)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    with pytest.raises(OSError):
        ctx.backend.list_dir(folder, max_entries)
    assert ("dir", "dir") not in ctx.nt.calls


# -- reads --


def test_reads_use_bounded_chunks_and_explicit_offsets(lab: Any) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)
    data = ctx.backend.read(leaf, len(DATA) + 1)
    assert type(data) is bytes and data == DATA
    assert ctx.nt.reads == [
        ("file.bin", 0, 4096),
        ("file.bin", 4096, 4096),
        ("file.bin", 8192, 2049),
        ("file.bin", 10240, 1),
    ]


def test_short_reads_progress_and_the_limit_stops_reading(lab: Any) -> None:
    ctx = make(lab, small_tree(DATA[:2500]), read_chunk=1000)
    _folder, leaf = opened_file(lab, ctx)
    assert ctx.backend.read(leaf, 4097) == DATA[:2500]
    assert [(offset, length) for _name, offset, length in ctx.nt.reads] == [
        (0, 4096),
        (1000, 3097),
        (2000, 2097),
        (2500, 1597),
    ]
    ctx = make(lab, small_tree(DATA[:5000]))
    _folder, leaf = opened_file(lab, ctx)
    assert ctx.backend.read(leaf, 4097) == DATA[:4097]
    assert [(offset, length) for _name, offset, length in ctx.nt.reads] == [(0, 4096), (4096, 1)]
    ctx = make(lab, small_tree(DATA[:5]), read_chunk=1)
    _folder, leaf = opened_file(lab, ctx)
    assert ctx.backend.read(leaf, 10) == DATA[:5]
    assert len(ctx.nt.reads) == 6 <= 10 + 1


def test_the_returned_status_is_authoritative_over_iosb_status(lab: Any) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)

    def garbage(default: Callable[[], Any], extra: SimpleNamespace) -> Any:
        status = default()
        information = struct.unpack_from("<Q", bytes(extra.iosb), 8)[0]
        set_iosb(extra.iosb, 0x7777, information)
        return status

    ctx.nt.hooks[("read", "file.bin", 1)] = garbage
    assert ctx.backend.read(leaf, len(DATA) + 1) == DATA


@pytest.mark.parametrize("limit", [True, 1.0, -1, 65538, "1", None])
def test_read_limit_domain_is_checked_before_any_read(lab: Any, limit: Any) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)
    with pytest.raises(OSError):
        ctx.backend.read(leaf, limit)
    assert ctx.nt.reads == []
    assert ctx.backend.read(leaf, 0) == b"" and ctx.nt.reads == []
    assert ctx.backend.read(leaf, 65537) == DATA


def overlong(default: Callable[[], Any], extra: SimpleNamespace) -> Any:
    default()
    set_iosb(extra.iosb, SUCCESS, 4097)
    return SUCCESS


@pytest.mark.parametrize(
    "hook",
    [
        overlong,
        filled(b"", information=0),
        filled(b"abc", status=END_OF_FILE),
        returns_status(ACCESS_DENIED),
    ],
)
def test_malformed_read_results_fail_without_consuming_bytes(lab: Any, hook: Hook) -> None:
    ctx = make(lab)
    _folder, leaf = opened_file(lab, ctx)
    ctx.nt.hooks[("read", "file.bin", 2)] = hook
    with pytest.raises(OSError):
        ctx.backend.read(leaf, len(DATA) + 1)
    assert ctx.backend.close(leaf) is True


# -- effect gaps after an open --


def gap_hook(kind: str) -> tuple[Hook, Any]:
    if kind == "error":
        return raise_before(OSError("fictitious-api")), OSError
    if kind == "signal":
        return raise_after(Signal()), Signal
    if kind == "pending":
        return returns_status(PENDING), OSError
    return returns_status(None), OSError


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        (("info", "file.bin#1"), "error"),
        (("info", "file.bin#0"), "signal"),
        (("stream", "file.bin"), "pending"),
        (("stream", "file.bin"), "none"),
        (("stream", "file.bin"), "signal"),
        (("dir", "dir", 2), "pending"),
        (("dir", "dir", 1), "error"),
        (("read", "file.bin", 2), "pending"),
        (("read", "file.bin", 1), "signal"),
        (("read", "file.bin", 3), "none"),
    ],
)
def test_effect_gaps_after_the_open_poison_and_retain(lab: Any, key: Any, kind: str) -> None:
    ctx = make(lab, page_records=1)
    folder, leaf = opened_file(lab, ctx)
    hook, expected = gap_hook(kind)
    ctx.nt.hooks[key] = hook
    target = folder if key[0] == "dir" else leaf
    with pytest.raises(expected):
        if key[0] == "dir":
            ctx.backend.list_dir(folder, 16)
        elif key[0] == "read":
            ctx.backend.read(leaf, len(DATA) + 1)
        else:
            ctx.backend.query(leaf)
    assert seen(ctx.nt, key[0], key[1]) <= retained(ctx.backend)
    assert ctx.backend.close(target) is False
    assert ctx.nt.closed == []
    assert_blocked(lab, ctx, folder)


def test_profile_pending_retains_the_published_anchor(lab: Any) -> None:
    ctx = make(lab)
    ctx.nt.hooks[("volume", "5")] = returns_status(PENDING)
    target = slot(lab)
    with pytest.raises(OSError):
        ctx.backend.open_anchor(target)
    assert type(target.value) is lab.glob["Handle"]
    assert seen(ctx.nt, "volume", "5") <= retained(ctx.backend)
    assert ctx.backend.close(target.value) is False and ctx.nt.closed == []


# -- close --


def test_close_is_exact_and_once(lab: Any) -> None:
    ctx = make(lab)
    folder = child(lab, ctx.backend, anchor(lab, ctx.backend), "dir")
    for stranger in (lab.glob["Handle"](999999), object(), None):
        assert ctx.backend.close(stranger) is False
    assert ctx.nt.closed == []
    assert ctx.backend.close(folder) is True
    assert ctx.backend.close(folder) is False
    assert ctx.nt.closed == [ctx.nt.created[1]]


def test_failed_close_is_uncertain_once_and_blocks(lab: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    folder = child(lab, ctx.backend, root, "dir")
    ctx.nt.hooks[("close", "dir")] = returns(INVALID_HANDLE)
    assert ctx.backend.close(folder) is False
    assert ctx.backend.close(folder) is False
    assert ctx.nt.closed == [ctx.nt.created[1]]
    assert_blocked(lab, ctx, root)


def test_interrupted_close_propagates_and_is_never_retried(lab: Any) -> None:
    ctx = make(lab)
    root = anchor(lab, ctx.backend)
    folder = child(lab, ctx.backend, root, "dir")
    signal = Signal()
    ctx.nt.hooks[("close", "dir")] = raise_before(signal)
    with pytest.raises(Signal) as caught:
        ctx.backend.close(folder)
    assert caught.value is signal
    assert ctx.backend.close(folder) is False
    assert ctx.nt.closed == [ctx.nt.created[1]]
    assert_blocked(lab, ctx, root)


# -- through the frozen policy --


def closed_once(fake: FakeNt) -> bool:
    unique = len(set(fake.closed)) == len(fake.closed)
    return unique and sorted(fake.closed) == sorted(fake.created)


@pytest.mark.parametrize(
    ("scenario", "label", "page_records", "read_chunk"),
    [
        ("approved", "VERIFIED_APPROVED", 64, 4096),
        ("approved", "VERIFIED_APPROVED", 1, 1000),
        ("rejected_at_1", "VERIFIED_REJECTED", 64, 4096),
    ],
)
def test_synthetic_bundle_through_the_frozen_policy(
    lab: Any, scenario: str, label: str, page_records: int, read_chunk: int
) -> None:
    ctx = prepare(lab, scenario, page_records, read_chunk)
    summary = hashlib.sha256(ctx.bundle.summary_raw).hexdigest()
    transport = hashlib.sha256(ctx.bundle.transport_raw).hexdigest()
    assert collect(lab) == (label, "OK", summary, transport)
    assert ctx.nt.violations == []
    assert closed_once(ctx.nt) and ctx.nt.handles == {}
    assert lab.glob["_POISON"] == [] and lab.glob["_ACTIVE"] == []
    assert ctx.backend._retained == []
    for name in {name for name, _flag in ctx.nt.restarts}:
        flags = [flag for listed, flag in ctx.nt.restarts if listed == name]
        assert flags[0] is True and flags.count(True) == 2, name
    assert all(length <= 4096 for _name, _offset, length in ctx.nt.reads)


def spoil(ctx: SimpleNamespace, case: str) -> None:
    root, fake = ctx.root, ctx.nt
    if case == "missing":
        del named(root, "Desktop").children["codes"]
    elif case == "profile":
        fake.fs_name = "FAT32"
    elif case == "reparse":
        named(root, "codes").reparse = True
    elif case == "volume":
        named(root, "mask").volume = 0x9999
    elif case == "streams":
        named(root, "summary.json").streams = ("::$DATA", ":extra:$DATA")
    elif case == "listing":
        fake.hooks[("dir", PUBLIC_NAME)] = filled(b"", information=0)
    elif case == "unsupported":
        fake.hooks[("dir", PUBLIC_NAME)] = filled(b"", status=INVALID_INFO_CLASS, information=0)
    elif case == "read":
        fake.hooks[("read", "summary.json")] = returns_status(ACCESS_DENIED)
    else:
        changed = named(root, "summary.json")
        payload = struct.pack("<qqqqI4x", 1, 2, 3, 2000, changed.attributes())
        fake.hooks[("info", "summary.json#0", 2)] = metadata(payload)


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("missing", "COLLECT_OPEN"),
        ("profile", "COLLECT_OPEN"),
        ("reparse", "COLLECT_REPARSE"),
        ("volume", "COLLECT_VOLUME"),
        ("streams", "COLLECT_STREAMS"),
        ("listing", "COLLECT_LISTING"),
        ("unsupported", "COLLECT_UNSUPPORTED"),
        ("read", "COLLECT_READ"),
        ("changed", "COLLECT_CHANGED"),
    ],
)
def test_completed_backend_failures_map_to_policy_reasons(lab: Any, case: str, reason: str) -> None:
    ctx = prepare(lab)
    spoil(ctx, case)
    assert collect(lab) == ("INVALID", reason, None, None)
    assert closed_once(ctx.nt) and ctx.nt.handles == {}
    assert lab.glob["_POISON"] == [] and lab.glob["_ACTIVE"] == []


def test_public_policy_result_is_closed_over_an_injected_message(lab: Any, capsys: Any) -> None:
    ctx = prepare(lab)
    sentinel = "fictitious-sentinel-7f3a"
    ctx.nt.hooks[("create", ANCHOR)] = raise_before(OSError(sentinel))
    result = collect(lab)
    assert result == ("INVALID", "COLLECT_CUSTODY", None, None)
    assert sentinel not in repr(result)
    captured = capsys.readouterr()
    assert sentinel not in captured.out and sentinel not in captured.err
    assert ctx.nt.calls == [("create", ANCHOR)]
    assert ctx.nt.created == [] and ctx.nt.closed == []


def install_gap(lab: Any, fake: FakeNt, gap: str) -> BaseException | None:
    """Breaks the open of 'codes'; returns the control expected to escape."""
    key = ("create", "codes")
    if gap == "before-signal":
        signal = Signal()
        fake.hooks[key] = raise_before(signal)
        return signal
    if gap == "after-signal":
        signal = Signal()
        fake.hooks[key] = raise_after(signal)
        return signal
    if gap == "dto-signal":
        signal = Signal()
        break_handle(lab, fake, "codes", signal)
        return signal
    if gap == "after-error":
        fake.hooks[key] = raise_after(OSError("fictitious-api"))
    elif gap == "dto-memory":
        break_handle(lab, fake, "codes", MemoryError("fictitious"))
    elif gap == "pending":
        fake.hooks[key] = outcome(PENDING)
    elif gap == "alias":
        fake.hooks[key] = alias()
    else:
        fake.hooks[key] = outcome(SUCCESS, cell=0x7770, information=2)
    return None


@pytest.mark.parametrize(
    "gap",
    [
        "before-signal",
        "after-signal",
        "after-error",
        "dto-signal",
        "dto-memory",
        "pending",
        "alias",
        "created",
    ],
)
def test_policy_custody_gaps_retain_the_backend_and_block(lab: Any, gap: str) -> None:
    fake, ref, _root = detached(lab)
    expected = install_gap(lab, fake, gap)
    if expected is None:
        assert collect(lab) == ("INVALID", "COLLECT_CUSTODY", None, None)
    else:
        with pytest.raises(type(expected)) as caught:
            collect(lab)
        assert caught.value is expected
        expected.__traceback__ = None
        del caught
    gc.collect()
    backend = ref()
    assert backend is not None  # held only by the policy's retention
    assert any(item[0] is backend for item in lab.glob["_POISON"])
    record = lab.glob["_ACTIVE"][0].ledger[-1]
    assert record.status == "QUARANTINED" and record.value is lab.win32["UNKNOWN"]
    assert seen(fake, "create", "codes") <= retained(backend)
    assert fake.closed == []
    before = list(fake.calls)
    assert collect(lab) == ("INVALID", "COLLECT_POISONED", None, None)
    assert fake.calls == before


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        (("stream", "codes"), "pending"),
        (("stream", "codes"), "error"),
        (("info", "codes#0"), "error"),
        (("dir", PUBLIC_NAME), "pending"),
        (("read", "summary.json"), "pending"),
        (("read", "summary.json"), "none"),
        (("read", "transport.json"), "signal"),
        (("volume", "5"), "pending"),
    ],
)
def test_policy_effect_gaps_after_an_open_retain_and_block(lab: Any, key: Any, kind: str) -> None:
    fake, ref, _root = detached(lab)
    hook, expected = gap_hook(kind)
    fake.hooks[key] = hook
    if expected is Signal:
        with pytest.raises(Signal) as caught:
            collect(lab)
        caught.value.__traceback__ = None
        del caught
    else:
        assert collect(lab) == ("INVALID", "COLLECT_CLEANUP", None, None)
    gc.collect()
    backend = ref()
    assert backend is not None
    assert any(item[0] is backend for item in lab.glob["_POISON"])
    assert seen(fake, key[0], key[1]) <= retained(backend)
    assert fake.closed == []
    before = list(fake.calls)
    assert collect(lab) == ("INVALID", "COLLECT_POISONED", None, None)
    assert fake.calls == before


def test_policy_failed_close_is_not_retried(lab: Any) -> None:
    ctx = prepare(lab)
    ctx.nt.hooks[("close", "poc")] = returns(INVALID_HANDLE)
    assert collect(lab) == ("INVALID", "COLLECT_CLEANUP", None, None)
    assert ctx.nt.calls.count(("close", "poc")) == 1  # once, then the backend refuses
    assert len(set(ctx.nt.closed)) == len(ctx.nt.closed) < len(ctx.nt.created)
    assert lab.glob["_POISON"] != []
    assert collect(lab) == ("INVALID", "COLLECT_POISONED", None, None)


# -- ownership regressions (V6) --
#
# Exact ownership across legitimate private backend objects sharing the real
# policy DTO classes: a token value alone is not custody of the issued object.
# This is not a hostile-seam or source-authentication claim.


def foreign_call(backend: Any, handle: Any, op: str, target: Any) -> None:
    if op == "query":
        backend.query(handle)
    elif op == "read":
        backend.read(handle, 1)
    elif op == "list_dir":
        backend.list_dir(handle, 16)
    else:
        backend.open_child(handle, "dir", "DIR", target)


@pytest.mark.parametrize("op", ["close", "query", "read", "list_dir", "open_child"])
@pytest.mark.parametrize("origin", ["foreign", "reconstructed"])
def test_handles_are_owned_by_the_issuing_backend_object(lab: Any, origin: str, op: str) -> None:
    first, second = make(lab), make(lab)
    second.nt.raw = 0x900  # distinct fake raw bases: A from 0x400, B from 0x900
    a_root = anchor(lab, first.backend)
    b_root = anchor(lab, second.backend)
    handle = a_root if origin == "foreign" else lab.glob["Handle"](b_root.token)
    before_a, before_b = list(first.nt.calls), list(second.nt.calls)
    target = slot(lab)
    if op == "close":
        assert second.backend.close(handle) is False
    else:
        with pytest.raises(OSError):
            foreign_call(second.backend, handle, op, target)
    assert target.value is None
    assert first.nt.calls == before_a and second.nt.calls == before_b
    assert type(second.backend.query(b_root)) is lab.glob["Info"]
    assert second.backend.close(b_root) is True
    assert second.nt.closed == [second.nt.created[0]]
    assert first.backend.close(a_root) is True
    assert first.nt.closed == [first.nt.created[0]]


@pytest.fixture(scope="module")
def close_line() -> int:
    """Line of `record = (raw,)` in _Win32Backend.close, read from the source
    before the lab bans file access (module scope runs first)."""
    tree = ast.parse(WIN32.read_bytes())
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_Win32Backend"
    )
    close = next(
        node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "close"
    )
    lines = [
        node.lineno
        for node in ast.walk(close)
        if isinstance(node, ast.Assign) and ast.unparse(node) == "record = (raw,)"
    ]
    assert len(lines) == 1
    return lines[0]


def owned_raws(backend: Any) -> set[int]:
    """Raw ids held by the backend's own ledgers (_open and _retained) only."""
    found: set[int] = set()
    pending: list[Any] = [backend._open, backend._retained]
    budget = 100000
    while pending and budget:
        budget -= 1
        item = pending.pop()
        if type(item) is int:
            found.add(item)
        elif type(item) is ctypes.c_void_p:
            if item.value is not None:
                found.add(item.value)
        elif isinstance(item, (tuple, list)):
            pending.extend(item)
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
    assert budget, "ownership ledger walk exceeded its bound"
    return found


@pytest.mark.parametrize("error_type", [OSError, Signal])
def test_interrupted_close_keeps_the_raw_in_the_ownership_ledger(
    close_line: int, lab: Any, error_type: Any
) -> None:
    fake, ref, _root = detached(lab)
    error = error_type("fictitious-close-gap")
    code = lab.win32["_Win32Backend"].close.__code__
    fired: list[Any] = []

    def local(frame: Any, event: str, _arg: Any) -> Any:
        if event == "line" and frame.f_lineno == close_line and not fired:
            fired.append(frame.f_locals.get("raw"))
            raise error
        return local

    def tracer(frame: Any, _event: str, _arg: Any) -> Any:
        return local if frame.f_code is code else None

    previous = sys.gettrace()
    result: Any = None
    sys.settrace(tracer)
    try:
        if error_type is Signal:
            with pytest.raises(Signal) as caught:
                collect(lab)
            assert caught.value is error
            del caught
        else:
            result = collect(lab)
    finally:
        sys.settrace(previous)
    error.__traceback__ = None
    assert sys.gettrace() is previous
    assert len(fired) == 1
    target = fired[0]
    if error_type is OSError:
        assert result == ("INVALID", "COLLECT_CLEANUP", None, None)
    gc.collect()
    backend = ref()
    assert backend is not None
    assert any(item[0] is backend for item in lab.glob["_POISON"])
    assert type(target) is int and target in fake.handles
    assert target not in fake.closed  # never closed, never retried
    assert set(fake.handles) <= owned_raws(backend)
    before = list(fake.calls)
    assert collect(lab) == ("INVALID", "COLLECT_POISONED", None, None)
    assert fake.calls == before and target not in fake.closed
