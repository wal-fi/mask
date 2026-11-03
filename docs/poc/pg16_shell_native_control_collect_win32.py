"""Win32 backend for the evidence collector policy. Import defines only.

Fake-only: the public `backend()` always returns None, so the collector stays
unavailable in production. `_load_native()` is a lazy binding of the selected
functions and is never invoked by this module; there is no fallback to it.
`_Win32Backend(api, dto)` is driven only by tests through a private api seam
(seven fixed operations) and the collector DTO namespace; neither seam is an
adversarial security boundary and class identity does not authenticate a
source. Nothing here attests native support, a physical fixed disk, atomicity
or a syscall time bound.

Custody: before every native effect the call inputs and outputs are appended
to `_retained` and, for opens, the UNKNOWN marker is published in the policy
Slot. Only a completed, known outcome removes the record; any record left
behind (pending, malformed status, raised error or control, DTO gap) blocks
every later native call, close included. Backend refusals raise OSError;
injected exceptions propagate unchanged and the public policy closes them.
"""

import ctypes
import struct

# -- explicit fixed-width types (no host `long` assumption) --

_I32 = ctypes.c_int32
_U32 = ctypes.c_uint32
_I64 = ctypes.c_int64
_U64 = ctypes.c_uint64
_U16 = ctypes.c_uint16
_U8 = ctypes.c_uint8
_PTR = ctypes.c_void_p

SUCCESS = 0
PENDING = 0x103
BUFFER_OVERFLOW = -0x7FFFFFFB  # 0x80000005
NO_MORE_FILES = -0x7FFFFFFA  # 0x80000006
INVALID_INFO_CLASS = -0x3FFFFFFD  # 0xC0000003
END_OF_FILE = -0x3FFFFFEF  # 0xC0000011
NOT_SUPPORTED = -0x3FFFFF45  # 0xC00000BB
INVALID_HANDLE_VALUE = (1 << 64) - 1
FILE_OPEN = 1
FILE_OPENED = 1
ANCHOR_NAME = "\\??\\C:\\"
# (access, share, options): FILE_OPEN only, never follow a reparse point
DIR_RIGHTS = (0x001000A1, 0x3, 0x00200021)
FILE_RIGHTS = (0x00100081, 0x1, 0x00200060)
FILE_DEVICE_DISK = 7
FILE_REMOVABLE_MEDIA = 0x1
FILE_REMOTE_DEVICE = 0x10
FS_ATTRIBUTE_CAP = 76  # fixed choice: longer names fail closed as unsupported
STREAM_PAGE = 4096
DIR_PAGE = 65536
READ_CHUNK = 4096
READ_LIMIT = 65537
MAX_HANDLES = 64
MAX_ENTRIES = 16
MAX_STREAMS = 8
STREAM_CLASS = 22
DIRECTORY_CLASS = 60  # NT FileIdExtdDirectoryInformation, not Win32 0x13/0x14
INFO_CLASSES = (0, 1, 9, 0x12)  # public Win32 classes; reserved NT class 59 unused
API_OPERATIONS = (
    "create",
    "query_info",
    "query_file",
    "query_volume",
    "query_directory",
    "read",
    "close",
)


# -- x64 layouts --


class UNICODE_STRING(ctypes.Structure):
    _fields_ = (("Length", _U16), ("MaximumLength", _U16), ("Buffer", _PTR))


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = (
        ("Length", _U32),
        ("RootDirectory", _PTR),
        ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
        ("Attributes", _U32),
        ("SecurityDescriptor", _PTR),
        ("SecurityQualityOfService", _PTR),
    )


class _StatusUnion(ctypes.Union):
    _fields_ = (("Status", _I32), ("Pointer", _PTR))


class IO_STATUS_BLOCK(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (("u", _StatusUnion), ("Information", _U64))


class FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = (
        ("CreationTime", _I64),
        ("LastAccessTime", _I64),
        ("LastWriteTime", _I64),
        ("ChangeTime", _I64),
        ("FileAttributes", _U32),
    )


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = (
        ("AllocationSize", _I64),
        ("EndOfFile", _I64),
        ("NumberOfLinks", _U32),
        ("DeletePending", _U8),
        ("Directory", _U8),
    )


class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = (("FileAttributes", _U32), ("ReparseTag", _U32))


class FILE_ID_INFO(ctypes.Structure):
    _fields_ = (("VolumeSerialNumber", _U64), ("FileId", _U8 * 16))


class FILE_FS_DEVICE_INFORMATION(ctypes.Structure):
    _fields_ = (("DeviceType", _U32), ("Characteristics", _U32))


_IOSB_P = ctypes.POINTER(IO_STATUS_BLOCK)
PROTOTYPES = {
    "NtCreateFile": (
        "ntdll",
        (
            ctypes.POINTER(_PTR),
            _U32,
            ctypes.POINTER(OBJECT_ATTRIBUTES),
            _IOSB_P,
            ctypes.POINTER(_I64),
            _U32,
            _U32,
            _U32,
            _U32,
            _PTR,
            _U32,
        ),
        _I32,
    ),
    "NtQueryInformationFile": ("ntdll", (_PTR, _IOSB_P, _PTR, _U32, _U32), _I32),
    "NtQueryVolumeInformationFile": ("ntdll", (_PTR, _IOSB_P, _PTR, _U32, _U32), _I32),
    "NtQueryDirectoryFile": (
        "ntdll",
        (
            _PTR,
            _PTR,
            _PTR,
            _PTR,
            _IOSB_P,
            _PTR,
            _U32,
            _U32,
            _U8,
            ctypes.POINTER(UNICODE_STRING),
            _U8,
        ),
        _I32,
    ),
    "NtReadFile": (
        "ntdll",
        (
            _PTR,
            _PTR,
            _PTR,
            _PTR,
            _IOSB_P,
            _PTR,
            _U32,
            ctypes.POINTER(_I64),
            ctypes.POINTER(_U32),
        ),
        _I32,
    ),
    "NtClose": ("ntdll", (_PTR,), _I32),
    "GetFileInformationByHandleEx": ("kernel32", (_PTR, _U32, _PTR, _U32), _I32),
}
_WIDTHS = (
    (_PTR, 8),
    (_I32, 4),
    (_U32, 4),
    (_I64, 8),
    (_U64, 8),
    (_U16, 2),
    (_U8, 1),
    (UNICODE_STRING, 16),
    (OBJECT_ATTRIBUTES, 48),
    (IO_STATUS_BLOCK, 16),
    (FILE_BASIC_INFO, 40),
    (FILE_STANDARD_INFO, 24),
    (FILE_ATTRIBUTE_TAG_INFO, 8),
    (FILE_ID_INFO, 24),
    (FILE_FS_DEVICE_INFORMATION, 8),
)


def _abi_ok() -> bool:
    """x64 gate: pointer, field and structure widths as documented."""
    return all(ctypes.sizeof(kind) == size for kind, size in _WIDTHS)


class _Unknown:
    """Custody marker: an open whose outcome is not known to be handle-free."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNKNOWN(<custody uncertain>)"


UNKNOWN = _Unknown()


def _refuse() -> None:
    raise OSError("win32 backend refused") from None


def _ntstatus(value: object) -> bool:
    return type(value) is int and -(1 << 31) <= value < (1 << 31)


def _is_error(status: int) -> bool:
    return (status & 0xFFFFFFFF) >> 30 == 3


def _utf16(raw: bytes) -> str:
    try:
        return raw.decode("utf-16-le")  # strict: lone surrogates are rejected
    except UnicodeDecodeError:
        _refuse()
    return ""


def _name_ok(name: object) -> bool:
    if type(name) is not str or name in (".", ".."):
        return False
    if any(char in name for char in ("\x00", "/", "\\", ":")):
        return False
    try:
        size = len(name.encode("utf-16-le"))
    except UnicodeEncodeError:
        return False
    return 2 <= size <= 510


class _Win32Backend:
    """The six collector operations over the seven-operation api seam."""

    def __init__(self, api: object, dto: object) -> None:
        if not _abi_ok() or api is None or not isinstance(dto, dict):
            _refuse()
        ops = {}
        for name in API_OPERATIONS:
            function = getattr(api, name, None)
            if not callable(function):
                _refuse()
            ops[name] = function
        kinds = tuple(dto.get(name) for name in ("Handle", "Info", "Entry", "Slot"))
        if not all(isinstance(kind, type) for kind in kinds):
            _refuse()
        self._ops = ops
        self._handle, self._info, self._entry, self._slot = kinds
        # token -> (the exact Handle object issued here, raw handle): owned and
        # closable once; only that original object is accepted, never a token.
        self._open: dict = {}
        self._next = 0
        # Outstanding native calls: inputs/outputs appended before the effect and
        # removed only after a completed, known outcome. Never freed otherwise;
        # while non-empty every later native call is refused.
        self._retained: list = []

    # -- custody --

    def _blocked(self) -> bool:
        return bool(self._retained)

    def _settle(self, record: tuple) -> None:
        self._retained[:] = [item for item in self._retained if item is not record]

    def _io(self, op: str, args: tuple, record: tuple) -> int:
        """NT call with an IOSB: pending or malformed status stays outstanding."""
        self._retained.append(record)
        status = self._ops[op](*args)
        if not _ntstatus(status) or status == PENDING:
            _refuse()
        self._settle(record)
        return status

    def _entry_of(self, handle: object) -> tuple:
        """The ownership record of exactly this issued Handle object, or ()."""
        if type(handle) is not self._handle:
            return ()
        token = handle.token
        entry = self._open.get(token) if type(token) is int else None
        if entry is None or entry[0] is not handle:
            return ()  # foreign backend object or reconstructed same-token DTO
        return entry

    def _raw(self, handle: object) -> int:
        entry = self._entry_of(handle)
        if self._blocked() or not entry:
            _refuse()
        return entry[1]

    def _ready(self, slot: object) -> None:
        if self._blocked() or type(slot) is not self._slot or slot.value is not None:
            _refuse()
        if len(self._open) >= MAX_HANDLES:
            _refuse()

    # -- opens --

    def _create(self, name: str, root: object, directory: bool, slot: object) -> int:
        encoded = name.encode("utf-16-le")
        text = ctypes.create_string_buffer(encoded, len(encoded))
        unicode = UNICODE_STRING(len(encoded), len(encoded), ctypes.addressof(text))
        attributes = OBJECT_ATTRIBUTES(48, root, ctypes.pointer(unicode), 0, None, None)
        cell, iosb = _PTR(), IO_STATUS_BLOCK()
        record = (cell, iosb, attributes, unicode, text)
        slot.value = UNKNOWN  # first: the policy quarantines anything not proven
        self._retained.append(record)  # strong retention before the effect
        access, share, options = DIR_RIGHTS if directory else FILE_RIGHTS
        status = self._ops["create"](cell, access, attributes, iosb, share, FILE_OPEN, options)
        raw = cell.value
        if _ntstatus(status) and _is_error(status) and raw is None:
            slot.value = None  # completed, known failure without a handle
            self._settle(record)
            _refuse()
        owned = any(entry[1] == raw for entry in self._open.values())
        known = raw is not None and raw != INVALID_HANDLE_VALUE and not owned
        if not (status == SUCCESS and type(status) is int and iosb.Information == FILE_OPENED):
            _refuse()
        if not known:
            _refuse()
        self._next += 1
        token = self._next
        handle = self._handle(token)  # a gap here leaves UNKNOWN and the record
        self._open[token] = (handle, raw)
        slot.value = handle
        self._settle(record)
        return raw

    def open_anchor(self, slot: object) -> None:
        self._ready(slot)
        raw = self._create(ANCHOR_NAME, None, True, slot)
        self._profile(raw)  # after publication: a failure is a closable open

    def open_child(self, parent: object, name: object, kind: object, slot: object) -> None:
        self._ready(slot)
        if type(kind) is not str or kind not in ("DIR", "FILE") or not _name_ok(name):
            _refuse()
        root = self._raw(parent)
        self._create(str(name), root, kind == "DIR", slot)

    def _profile(self, raw: int) -> None:
        """Logical local NTFS disk, not marked removable media, not remote."""
        device, iosb = FILE_FS_DEVICE_INFORMATION(), IO_STATUS_BLOCK()
        args = (raw, iosb, device, ctypes.sizeof(device), 4)
        if self._io("query_volume", args, (iosb, device)) != SUCCESS:
            _refuse()
        if iosb.Information != ctypes.sizeof(device) or device.DeviceType != FILE_DEVICE_DISK:
            _refuse()
        if device.Characteristics & (FILE_REMOVABLE_MEDIA | FILE_REMOTE_DEVICE):
            _refuse()
        buffer, iosb = ctypes.create_string_buffer(FS_ATTRIBUTE_CAP), IO_STATUS_BLOCK()
        args = (raw, iosb, buffer, FS_ATTRIBUTE_CAP, 5)
        if self._io("query_volume", args, (iosb, buffer)) != SUCCESS:
            _refuse()
        used = iosb.Information
        if not 12 <= used <= FS_ATTRIBUTE_CAP:
            _refuse()
        data = buffer.raw[:used]
        (length,) = struct.unpack_from("<I", data, 8)
        if length % 2 or 12 + length > used or _utf16(data[12 : 12 + length]) != "NTFS":
            _refuse()

    # -- metadata --

    def _fixed(self, raw: int, info_class: int, buffer: object) -> None:
        record = (buffer,)
        self._retained.append(record)
        result = self._ops["query_info"](raw, info_class, buffer, ctypes.sizeof(buffer))
        self._settle(record)  # synchronous BOOL call: completed either way
        if type(result) is not int or result == 0:
            _refuse()

    def _streams(self, raw: int, directory: bool) -> tuple:
        buffer, iosb = ctypes.create_string_buffer(STREAM_PAGE), IO_STATUS_BLOCK()
        args = (raw, iosb, buffer, STREAM_PAGE, STREAM_CLASS)
        if self._io("query_file", args, (iosb, buffer)) != SUCCESS:
            _refuse()
        used = iosb.Information
        if used > STREAM_PAGE or (used == 0) is not directory:
            _refuse()  # directories: only a completed empty success is accepted
        data, names, offset = buffer.raw[:used], [], 0
        while used:
            if len(names) >= MAX_STREAMS or offset + 24 > used:
                _refuse()
            step, length = struct.unpack_from("<II", data, offset)
            end = offset + 24 + length
            if length == 0 or length % 2 or length > 128 or end > used:
                _refuse()
            name = _utf16(data[offset + 24 : end])
            if "\x00" in name:
                _refuse()
            names.append(name)
            if step == 0:
                break
            if step % 8 or step < 24 + length or offset + step >= used:
                _refuse()
            offset += step
        return tuple(names)

    def query(self, handle: object) -> object:
        raw = self._raw(handle)
        basic, standard = FILE_BASIC_INFO(), FILE_STANDARD_INFO()
        tag, ident = FILE_ATTRIBUTE_TAG_INFO(), FILE_ID_INFO()
        for info_class, buffer in zip(INFO_CLASSES, (basic, standard, tag, ident)):
            self._fixed(raw, info_class, buffer)
        attributes = basic.FileAttributes
        directory = bool(attributes & 0x10)
        valid = (
            standard.DeletePending in (0, 1)
            and standard.Directory in (0, 1)
            and bool(standard.Directory) is directory
            and tag.FileAttributes == attributes
            and standard.EndOfFile >= 0
        )
        if not valid:
            _refuse()
        streams = self._streams(raw, directory)
        return self._info(
            reparse=bool(attributes & 0x400),
            directory=directory,
            delete_pending=bool(standard.DeletePending),
            volume=ident.VolumeSerialNumber,
            file_id=bytes(ident.FileId),
            links=standard.NumberOfLinks,
            end_of_file=standard.EndOfFile,
            change_time=basic.ChangeTime,
            streams=streams,
        )

    # -- listing --

    def _page(self, data: bytes, state: tuple, max_entries: int) -> None:
        entries, seen, dots = state
        used, offset = len(data), 0
        while True:
            if offset + 88 > used:
                _refuse()
            (step,) = struct.unpack_from("<I", data, offset)
            attributes, length = struct.unpack_from("<II", data, offset + 56)
            end = offset + 88 + length
            if length == 0 or length % 2 or length > 510 or end > used:
                _refuse()
            name = _utf16(data[offset + 88 : end])
            if step and (step % 8 or step < 88 + length or offset + step >= used):
                _refuse()
            if name in (".", ".."):
                if name in dots:
                    _refuse()
                dots.add(name)
            else:
                if not _name_ok(name) or name in seen or len(entries) >= max_entries:
                    _refuse()
                seen.add(name)
                file_id = data[offset + 72 : offset + 88]  # full 128-bit id
                directory = bool(attributes & 0x10)
                entries.append(self._entry(name=name, directory=directory, file_id=file_id))
            if step == 0:
                return
            offset += step

    def list_dir(self, handle: object, max_entries: object) -> tuple:
        raw = self._raw(handle)
        if type(max_entries) is not int or not 0 <= max_entries <= MAX_ENTRIES:
            _refuse()
        state: tuple = ([], set(), set())
        buffer = ctypes.create_string_buffer(DIR_PAGE)
        for page in range(max_entries + 3):  # one-record pages, dots, terminal
            iosb = IO_STATUS_BLOCK()
            args = (raw, iosb, buffer, DIR_PAGE, DIRECTORY_CLASS, False, page == 0)
            status = self._io("query_directory", args, (iosb, buffer))
            used = iosb.Information
            if status == NO_MORE_FILES and used == 0:
                return tuple(state[0])
            if page == 0 and status in (INVALID_INFO_CLASS, NOT_SUPPORTED):
                raise NotImplementedError("directory class unsupported") from None
            if status != SUCCESS or not 0 < used <= DIR_PAGE:
                _refuse()
            self._page(buffer.raw[:used], state, max_entries)
        _refuse()
        return ()

    # -- reads --

    def read(self, handle: object, limit: object) -> bytes:
        raw = self._raw(handle)
        if type(limit) is not int or not 0 <= limit <= READ_LIMIT:
            _refuse()
        data, turns = bytearray(), 0
        while len(data) < limit:
            turns += 1
            if turns > limit + 1:
                _refuse()
            request = min(READ_CHUNK, limit - len(data))
            buffer, iosb = ctypes.create_string_buffer(request), IO_STATUS_BLOCK()
            offset = _I64(len(data))
            args = (raw, iosb, buffer, request, offset)
            status = self._io("read", args, (iosb, buffer, offset))
            count = iosb.Information
            if status == END_OF_FILE and count == 0:
                break
            if status != SUCCESS or not 0 < count <= request:
                _refuse()
            data += buffer.raw[:count]
        return bytes(data)

    # -- close --

    def close(self, handle: object) -> bool:
        entry = self._entry_of(handle)
        if self._blocked() or not entry:
            return False  # unknown, foreign, reconstructed, already closed
        raw = entry[1]
        record = (raw,)  # raw still owned in _open here
        # Durable close ticket before ownership leaves _open: from here on the
        # raw is either in _retained (in flight / uncertain) or proven closed.
        self._retained.append(record)
        del self._open[handle.token]
        status = self._ops["close"](raw)
        if type(status) is int and status == SUCCESS:
            self._settle(record)
            return True
        return False


class _NativeApi:
    """The seven api operations over bound prototypes. Only built by
    _load_native(), which this module never calls."""

    def __init__(self, bound: dict) -> None:
        self._bound = bound

    def create(self, *args: object) -> object:
        cell, access, attributes, iosb, share, disposition, options = args
        function = self._bound["NtCreateFile"]
        return function(
            ctypes.byref(cell),
            access,
            ctypes.byref(attributes),
            ctypes.byref(iosb),
            None,
            0,
            share,
            disposition,
            options,
            None,
            0,
        )

    def query_info(self, *args: object) -> object:
        raw, info_class, buffer, size = args
        function = self._bound["GetFileInformationByHandleEx"]
        return function(raw, info_class, ctypes.byref(buffer), size)

    def query_file(self, *args: object) -> object:
        raw, iosb, buffer, length, info_class = args
        function = self._bound["NtQueryInformationFile"]
        return function(raw, ctypes.byref(iosb), ctypes.byref(buffer), length, info_class)

    def query_volume(self, *args: object) -> object:
        raw, iosb, buffer, length, fs_class = args
        function = self._bound["NtQueryVolumeInformationFile"]
        return function(raw, ctypes.byref(iosb), ctypes.byref(buffer), length, fs_class)

    def query_directory(self, *args: object) -> object:
        raw, iosb, buffer, length, info_class, single, restart = args
        function = self._bound["NtQueryDirectoryFile"]
        return function(
            raw,
            None,
            None,
            None,
            ctypes.byref(iosb),
            ctypes.byref(buffer),
            length,
            info_class,
            single,
            None,
            restart,
        )

    def read(self, *args: object) -> object:
        raw, iosb, buffer, length, offset = args
        function = self._bound["NtReadFile"]
        return function(
            raw,
            None,
            None,
            None,
            ctypes.byref(iosb),
            ctypes.byref(buffer),
            length,
            ctypes.byref(offset),
            None,
        )

    def close(self, *args: object) -> object:
        (raw,) = args
        return self._bound["NtClose"](raw)


def _load_native() -> object:
    """Lazy binding of the selected functions. Never invoked here; a real use
    needs the separate pinned loader binding, preflight and reviewed procedure."""
    if not _abi_ok():
        _refuse()
    libraries = {"ntdll": ctypes.WinDLL("ntdll"), "kernel32": ctypes.WinDLL("kernel32")}
    bound = {}
    for name, (library, argtypes, restype) in PROTOTYPES.items():
        function = getattr(libraries[library], name)
        function.argtypes, function.restype = argtypes, restype
        bound[name] = function
    return _NativeApi(bound)


def backend() -> object:
    """Public seam: no backend is available, so collection stays unavailable."""
    return None
