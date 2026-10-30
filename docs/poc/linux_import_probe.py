"""Import-only lab, two cases; no SQL, services, network or production caller."""

from __future__ import annotations

import base64
import importlib
import importlib.util
import json
import os
import sys
import time
import zlib
from pathlib import Path
from types import ModuleType

ROOTS = ("maskgw.db.postgres", "maskgw.runtime.snapshot", "maskgw.pgwire.result_encoder")
FORBIDDEN = (
    "mcp",
    "fastapi",
    "starlette",
    "uvicorn",
    "anyio",
    "scramp",
    "asn1crypto",
    "maskgw.admin",
    "maskgw.bootstrap",
    "maskgw.mcp",
)
MAX_ROWS = 1500
MAX_RAW = 1024 * 1024
MAX_COMPRESSED = 32 * 1024
MAX_PROBE = 56 * 1024
METADATA_LIMIT = 8000
MAX_BATCH_DETAILS = 8
BATCH_KINDS = ("NON_MODULE", "MODULE_EXACT", "ABSENT")
BATCH_TOTALS = ("non_module_total", "module_exact_total", "absent_total")
AUDIT_CATEGORIES = ("FORBIDDEN", "OUTSIDE_ORIGIN", "UNOWNED_TOP", "FILELESS_UNATTRIBUTED", "OTHER")
AUDIT_EXIT = 75
CHECK_EXIT = 76
NATIVE_ROOTS = ("pglast", "pydantic_core", "cryptography", "yaml")
CHECK_CATEGORIES = (
    "SOCKET_FD",
    "CHILD",
    "FD_SET_CHANGED",
    "THREADS",
    "PSYCOPG_IMPL",
    "NATIVE_MISSING",
    "OTHER",
)
IDENTITY_LINK = (
    "_openssl",
    "cryptography.hazmat.bindings._rust",
    "cryptography/hazmat/bindings/_rust.abi3.so",
    "cryptography",
)
IDENTITY_SLOT = ("_openssl.lib", "lib")


class ImportFault(Exception):
    pass


class AuditFault(ImportFault):
    def __init__(self, category):
        super().__init__()
        self.category = category


class CheckFault(ImportFault):
    def __init__(self, category, root=None):
        super().__init__()
        self.category, self.root = category, root


def check_failure(lab, stage, error):
    category = error.category if isinstance(error, CheckFault) else "OTHER"
    root = error.root if isinstance(error, CheckFault) else None
    if category not in CHECK_CATEGORIES or (root is not None and root not in NATIVE_ROOTS):
        category, root = "OTHER", None
    event = {"phase": "check_error", "stage": stage, "category": category, "root": root}
    try:
        lab.emit(event)
    except BaseException:
        pass
    return CHECK_EXIT


def valid_check_error(event, stage):
    return (
        type(event) is dict
        and set(event) == {"phase", "stage", "category", "root"}
        and event["phase"] == "check_error"
        and type(event["stage"]) is int
        and event["stage"] == stage
        and stage in (-1, 0, 1, 2, 3)
        and event["category"] in CHECK_CATEGORIES
        and (
            event["root"] in NATIVE_ROOTS
            if event["category"] == "NATIVE_MISSING"
            else event["root"] is None
        )
    )


def valid_module_name(name):
    return (
        type(name) is str
        and 1 <= len(name) <= 200
        and all(
            character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_."
            for character in name
        )
    )


def audit_context(module, name=None):
    if name == IDENTITY_SLOT[0]:
        return None, None  # Opaque slot: deliberately unmeasured, even on failure.
    has_file = False
    try:
        if name == IDENTITY_LINK[0]:
            if type(module) is not ModuleType:
                return False, False
            filename = module.__dict__.get("__file__")
        else:
            filename = getattr(module, "__file__", None)
        has_file = bool(filename)
        return has_file, has_file and Path(filename).resolve().is_relative_to("/installed")
    except BaseException:
        return has_file, False


def audit_module(lab, stage, name, module, owners, generated, *, batch=None):
    """One row or a closed error; False always stops the member (exit 75)."""
    try:
        row = module_row(name, module, owners, generated)
        event = (
            {"phase": "baseline", "row": row}
            if stage == -1
            else {"phase": "module", "stage": stage, "row": row}
        )
        lab.emit(event)
        return True
    except BaseException as error:
        category = (
            error.category if isinstance(error, AuditFault) and valid_module_name(name) else "OTHER"
        )
    has_file, under_installed = audit_context(module, name)
    event = {
        "phase": "audit_error",
        "stage": stage,
        "module": name if valid_module_name(name) else None,
        "category": category if category in AUDIT_CATEGORIES else "OTHER",
        "has_file": has_file,
        "under_installed": under_installed,
    }
    try:
        lab.emit(event)
    except BaseException:
        return False  # EOF/exit 75 still refuses the diagnostic.
    if batch is not None and stage in (0, 1, 2) and event["category"] == "FILELESS_UNATTRIBUTED":
        try:
            delta, accepted, deadline = batch
            details, terminal = batch_candidates(
                stage, delta, accepted, owners, generated, deadline
            )
            for item in [*details, terminal]:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                lab.emit(item)
        except BaseException:
            pass  # Missing batch_end is PROTOCOL, not a partial success.
    return False


def valid_audit_error(event, stage):
    return (
        type(event) is dict
        and set(event) == {"phase", "stage", "module", "category", "has_file", "under_installed"}
        and event["phase"] == "audit_error"
        and type(event["stage"]) is int
        and event["stage"] == stage
        and stage in (-1, 0, 1, 2)
        and (event["module"] is None or valid_module_name(event["module"]))
        and event["category"] in AUDIT_CATEGORIES
        and (
            event["has_file"] is None and event["under_installed"] is None
            if event["module"] == IDENTITY_SLOT[0]
            else (
                type(event["has_file"]) is bool
                and type(event["under_installed"]) is bool
                and (not event["under_installed"] or event["has_file"])
            )
        )
    )


def collect_returncode(result, process, deadline):
    import subprocess

    try:
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
        result["member_returncode"] = process.returncode
    except subprocess.TimeoutExpired:
        result["member_wait"] = "TIMEOUT"
    except BaseException:
        result["member_wait"] = "DIAGNOSTIC"


def batch_anchor(owners, generated, *, strict=False):
    """Recheck only the closed exact-module anchor; never inspect a candidate."""
    try:
        child_name, provider_name, relative, owner = IDENTITY_LINK
        child, provider = sys.modules.get(child_name), sys.modules.get(provider_name)
        if type(child) is not ModuleType or type(provider) is not ModuleType:
            return None
        attributes, provider_attributes = child.__dict__, provider.__dict__
        if type(attributes) is not dict or type(provider_attributes) is not dict:
            return None
        filename = attributes.get("__file__")
        if filename is not None and (type(filename) is not str or filename):
            return None
        if (
            provider_attributes.get(child_name) is not child
            or type(provider_attributes.get("__file__")) is not str
            or not provider_attributes["__file__"]
        ):
            return None
        row = module_row(provider_name, provider, owners, generated)
        if row != [provider_name, owner, "installed/" + relative]:
            return None
        return attributes
    except AuditFault:
        return None
    except BaseException:
        if strict:
            raise  # Own slot audit categorizes unexpected failures as OTHER.
        return None


def batch_candidates(stage, delta, accepted, owners, generated, deadline):
    """Candidate facts only, bounded storage; no candidate origin verdict."""
    if type(stage) is not int or stage not in (0, 1, 2):
        raise ImportFault
    if time.monotonic() >= deadline:
        raise TimeoutError
    anchor = batch_anchor(owners, generated)
    sentinel = object()
    groups = {kind: [] for kind in BATCH_KINDS}
    totals = dict.fromkeys(BATCH_KINDS, 0)
    examined = 0
    for name in delta:
        if examined == MAX_ROWS:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError
        examined += 1
        if name in accepted:
            continue
        candidate = sys.modules.get(name, sentinel)
        dict_file = None
        if candidate is sentinel:
            kind = "ABSENT"
        elif type(candidate) is ModuleType:
            attributes = candidate.__dict__
            if type(attributes) is dict:
                filename = attributes.get("__file__")
                if type(filename) is str and filename:
                    continue
                dict_file = False
            kind = "MODULE_EXACT"
        else:
            kind = "NON_MODULE"
        slot = "NONE"
        if anchor is not None and candidate is not sentinel and candidate is not None:
            lib = "lib" in anchor and anchor["lib"] is not None and anchor["lib"] is candidate
            ffi = "ffi" in anchor and anchor["ffi"] is not None and anchor["ffi"] is candidate
            slot = "BOTH" if lib and ffi else "LIB" if lib else "FFI" if ffi else "NONE"
        totals[kind] += 1
        if len(groups[kind]) < MAX_BATCH_DETAILS:
            groups[kind].append(
                {
                    "phase": "batch_detail",
                    "stage": stage,
                    "module": name if valid_module_name(name) else None,
                    "kind": kind,
                    "dict_file": dict_file,
                    "identity_slot": slot,
                }
            )
    details = [row for kind in BATCH_KINDS for row in groups[kind]][:MAX_BATCH_DETAILS]
    terminal = {
        "phase": "batch_end",
        "stage": stage,
        "examined": examined,
        "details": len(details),
        **{key: totals[kind] for key, kind in zip(BATCH_TOTALS, BATCH_KINDS, strict=True)},
        "incomplete": examined >= MAX_ROWS or sum(totals.values()) > MAX_BATCH_DETAILS,
        "anchor": "ANCHORED" if anchor is not None else "UNANCHORED",
    }
    return details, terminal


def valid_batch_detail(event, stage):
    return (
        type(event) is dict
        and set(event) == {"phase", "stage", "module", "kind", "dict_file", "identity_slot"}
        and event["phase"] == "batch_detail"
        and type(event["stage"]) is int
        and event["stage"] == stage
        and (event["module"] is None or valid_module_name(event["module"]))
        and event["kind"] in BATCH_KINDS
        and (
            event["dict_file"] is None
            or (event["kind"] == "MODULE_EXACT" and event["dict_file"] is False)
        )
        and event["identity_slot"] in ("LIB", "FFI", "BOTH", "NONE")
        and (event["kind"] != "ABSENT" or event["identity_slot"] == "NONE")
    )


def valid_batch_end(event, stage, details):
    if (
        type(event) is not dict
        or set(event)
        != {"phase", "stage", "examined", "details", *BATCH_TOTALS, "incomplete", "anchor"}
        or event["phase"] != "batch_end"
        or type(event["stage"]) is not int
        or event["stage"] != stage
        or type(event["incomplete"]) is not bool
        or event["anchor"] not in ("ANCHORED", "UNANCHORED")
    ):
        return False
    for key in ("examined", "details", *BATCH_TOTALS):
        if type(event[key]) is not int or not 0 <= event[key] <= MAX_ROWS:
            return False
    total = sum(event[key] for key in BATCH_TOTALS)
    if (
        event["details"] != len(details)
        or len(details) > MAX_BATCH_DETAILS
        or not len(details) <= total <= event["examined"]
        or (not event["incomplete"] and (total != len(details) or event["examined"] == MAX_ROWS))
    ):
        return False
    if event["anchor"] == "UNANCHORED" and any(item["identity_slot"] != "NONE" for item in details):
        return False
    return all(
        sum(item["kind"] == kind for item in details) <= event[key]
        for key, kind in zip(BATCH_TOTALS, BATCH_KINDS, strict=True)
    )


def consume_batch(result, reader, process, deadline, stage):
    """A closed terminal diagnostic, never accepted rows or a normal outcome."""
    batch = {"details": [], "incomplete": True}
    result["batch"] = batch
    try:
        while True:
            if len(json.dumps(result)) > METADATA_LIMIT:
                raise ImportFault
            event = reader.read(deadline)
            if event.get("phase") == "batch_detail":
                if len(batch["details"]) >= MAX_BATCH_DETAILS or not valid_batch_detail(
                    event, stage
                ):
                    raise ImportFault
                batch["details"].append(event)
            elif valid_batch_end(event, stage, batch["details"]):
                batch["end"] = event
                break
            else:
                raise ImportFault
        if len(json.dumps(result)) > METADATA_LIMIT:
            raise ImportFault
        try:
            reader.read(deadline)
        except EOFError:
            pass
        else:
            raise ImportFault
        collect_returncode(result, process, deadline)
        if result.get("member_wait") or result.get("member_returncode") != AUDIT_EXIT:
            raise ImportFault
        if len(json.dumps(result)) > METADATA_LIMIT:
            raise ImportFault
        batch["incomplete"] = event["incomplete"]
    except BaseException:
        result["diagnostic_failure"] = "PROTOCOL"
        batch["incomplete"] = True
        if "member_returncode" not in result:
            collect_returncode(result, process, deadline)


def validate_inventory(rows):
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ImportFault
    for entry in rows:
        if (
            type(entry) is not list
            or len(entry) != 2
            or type(entry[0]) is not int
            or entry[0] not in (-1, 0, 1, 2)
        ):
            raise ImportFault
        row = entry[1]
        if (
            type(row) is not list
            or len(row) != 3
            or any(type(value) is not str or len(value) > 768 for value in row)
        ):
            raise ImportFault


def pack_inventory(rows):
    validate_inventory(rows)
    raw = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(raw) > MAX_RAW:
        raise ImportFault
    compressed = zlib.compress(raw, 6)
    if len(compressed) > MAX_COMPRESSED:
        raise ImportFault
    return {
        "codec": "zlib-base64",
        "raw_bytes": len(raw),
        "payload": base64.b64encode(compressed).decode("ascii"),
    }


def unpack_inventory(blob):
    try:
        if type(blob) is not dict or set(blob) != {"codec", "raw_bytes", "payload"}:
            raise ImportFault
        if (
            blob["codec"] != "zlib-base64"
            or type(blob["raw_bytes"]) is not int
            or not 0 <= blob["raw_bytes"] <= MAX_RAW
        ):
            raise ImportFault
        if type(blob["payload"]) is not str or len(blob["payload"]) > 4 * (
            (MAX_COMPRESSED + 2) // 3
        ):
            raise ImportFault
        compressed = base64.b64decode(blob["payload"], validate=True)
        if len(compressed) > MAX_COMPRESSED:
            raise ImportFault
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, MAX_RAW + 1)
        if (
            len(raw) > MAX_RAW
            or not inflater.eof
            or inflater.unused_data
            or inflater.unconsumed_tail
            or len(raw) != blob["raw_bytes"]
        ):
            raise ImportFault
        rows = json.loads(raw)
        validate_inventory(rows)
        return rows
    except Exception:
        raise ImportFault from None


def bounded_report(result):
    raw = json.dumps(result, separators=(",", ":"), sort_keys=True).encode("ascii")
    if len(raw) <= MAX_PROBE:
        return raw
    return json.dumps(
        {
            "case": result["case"],
            "outcome": "inconclusive",
            "report_limit": True,
            "total_memory_contained": False,
            "imports_fit_as32": False,
            "cleanup_confirmed": result["cleanup_confirmed"],
            "final_inventory": result.get("final_inventory", []),
        },
        separators=(",", ":"),
    ).encode("ascii")


class LineReader:
    """Bounded incremental lines; multiple emits may share one pipe read."""

    def __init__(self, handle, lab):
        self.handle, self.lab, self.buffer = handle, lab, b""

    def read(self, deadline):
        import select

        while not self.lab.STOP and time.monotonic() < deadline:
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    return self.lab.decode_line(line + b"\n")
                except Exception:
                    raise ImportFault from None
            if len(self.buffer) > self.lab.LINE_BYTES:
                raise ImportFault
            if not select.select([self.handle.fileno()], [], [], 0.05)[0]:
                continue
            block = os.read(self.handle.fileno(), self.lab.LINE_BYTES)
            if not block:
                if self.buffer:
                    raise ImportFault  # A partial trailing line is not a clean EOF.
                raise EOFError
            self.buffer += block
            if len(self.buffer) > 2 * self.lab.LINE_BYTES:
                raise ImportFault
        raise TimeoutError


def support():
    spec = importlib.util.spec_from_file_location(
        "_lab_support", Path(__file__).with_name("linux_as_probe.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def effects():
    fds = []
    for name in sorted(os.listdir("/proc/self/fd")):
        try:
            target = os.readlink("/proc/self/fd/" + name)
        except FileNotFoundError:
            continue  # directory listing's own already-closed descriptor
        if target.startswith("socket:"):
            raise CheckFault("SOCKET_FD")
        fds.append(int(name))
    try:
        children = Path(f"/proc/self/task/{os.getpid()}/children").read_text()
    except FileNotFoundError:
        children = None  # optional kernel interface; supervisor still inventories all /proc+cgroup
    if children is not None and children.strip():
        raise CheckFault("CHILD")
    return {"fds": fds, "proc_children_available": children is not None}


def module_row(name, module, owners, generated=None):
    if any(name == item or name.startswith(item + ".") for item in FORBIDDEN):
        raise AuditFault("FORBIDDEN")
    if name == IDENTITY_SLOT[0]:
        # No reads, equality, hashing, type metadata or fallback on the opaque object.
        if module is None or sys.modules.get(name) is not module:
            raise AuditFault("FILELESS_UNATTRIBUTED")
        anchor = batch_anchor(owners, generated, strict=True)
        slot = IDENTITY_SLOT[1]
        if (
            anchor is None
            or slot not in anchor
            or anchor[slot] is None
            or anchor[slot] is not module
        ):
            raise AuditFault("FILELESS_UNATTRIBUTED")
        return [
            name,
            IDENTITY_LINK[3],
            "attached-by-identity-slot/" + slot + "/installed/" + IDENTITY_LINK[2],
        ]
    if name == IDENTITY_LINK[0]:
        if type(module) is not ModuleType:
            raise AuditFault("FILELESS_UNATTRIBUTED")
        filename = module.__dict__.get("__file__")
    else:
        filename = getattr(module, "__file__", None)
    if filename:
        path = Path(filename).resolve()
        if path.is_relative_to("/installed"):
            relative = path.relative_to("/installed").as_posix()
            owner = owners.get(relative.split("/")[0])
            if owner is None:
                raise AuditFault("UNOWNED_TOP")
            return [name, owner, "installed/" + relative]
        if path.is_relative_to("/usr/local/lib/python3.11") and "site-packages" not in path.parts:
            return [
                name,
                "stdlib",
                "stdlib/" + path.relative_to("/usr/local/lib/python3.11").as_posix(),
            ]
        if name == "__main__" and path == Path(__file__).resolve():
            return [name, "harness", "probe/linux_import_probe.py"]
        if (
            name == "_lab_support"
            and path == Path(__file__).with_name("linux_as_probe.py").resolve()
        ):
            return [name, "harness", "probe/linux_as_probe.py"]
        raise AuditFault("OUTSIDE_ORIGIN")
    if module is None:
        return [name, "cache-none", "no-code"]
    root = name.split(".")[0]
    if root in sys.stdlib_module_names or name in ("builtins", "sys", "__main__"):
        return [name, "stdlib", "builtin-or-frozen"]
    if name == IDENTITY_LINK[0]:
        child_name, provider_name, relative, owner = IDENTITY_LINK
        provider = sys.modules.get(provider_name)
        if type(provider) is not ModuleType or sys.modules.get(child_name) is not module:
            raise AuditFault("FILELESS_UNATTRIBUTED")
        attributes = provider.__dict__
        if (
            type(attributes) is not dict
            or attributes.get(child_name) is not module
            or type(attributes.get("__file__")) is not str
            or not attributes["__file__"]
        ):
            raise AuditFault("FILELESS_UNATTRIBUTED")
        row = module_row(provider_name, provider, owners, generated)
        if row[1:] != [owner, "installed/" + relative]:
            raise AuditFault("FILELESS_UNATTRIBUTED")
        return [name, owner, "attached-by-identity/" + row[2]]
    # PyO3 creates fileless submodules; attribute to the verified parent .so,
    # never invent an actual __file__ for them.
    parent = name
    while "." in parent:
        parent = parent.rsplit(".", 1)[0]
        ancestor_file = getattr(sys.modules.get(parent), "__file__", None)
        if ancestor_file and ancestor_file.endswith(".so"):
            row = module_row(parent, sys.modules[parent], owners, generated)
            return [name, row[1], "generated-by/" + row[2]]
    for relative in (generated or {}).get(name, []):
        for native_name, native in sys.modules.items():
            if getattr(native, "__file__", None) == "/installed/" + relative:
                row = module_row(native_name, native, owners, generated)
                return [name, row[1], "generated-cython/" + row[2]]
    raise AuditFault("FILELESS_UNATTRIBUTED")


def native_check():
    if getattr(getattr(sys.modules.get("psycopg"), "pq", None), "__impl__", None) != "binary":
        raise CheckFault("PSYCOPG_IMPL")
    native = {}
    for root in NATIVE_ROOTS:
        names = [
            name
            for name, module in sys.modules.items()
            if (name == root or name.startswith(root + "."))
            and str(getattr(module, "__file__", "")).startswith("/installed/")
            and str(getattr(module, "__file__", "")).endswith(".so")
        ]
        if not names:
            raise CheckFault("NATIVE_MISSING", root)
        native[root] = sorted(names)
    return native


def member():
    import resource

    deadline = time.monotonic() + 20
    lab = support()
    lab.emit(
        {
            "phase": "ready",
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "limits": list(resource.getrlimit(resource.RLIMIT_AS)),
            "vm": lab.vm_status(),
        }
    )
    lab.command(b"GO\n")
    sys.path.insert(0, "/installed")  # explicit trusted tree, no site/PYTHONPATH
    manifest = json.loads(Path(__file__).with_name("runtime.json").read_bytes())
    owners = manifest["owners"]
    try:
        initial_fds = effects()
    except BaseException as error:
        return check_failure(lab, -1, error)
    previous = set(sys.modules)
    for name in sorted(previous):
        if not audit_module(lab, -1, name, sys.modules[name], owners, manifest["generated"]):
            return AUDIT_EXIT
    for number, target in enumerate(ROOTS):
        lab.emit({"phase": "start", "stage": number})
        try:
            importlib.import_module(target)
        except MemoryError:
            lab.emit({"phase": "error", "stage": number, "category": "MEMORY"})
            return 72
        except ImportError:
            lab.emit({"phase": "error", "stage": number, "category": "IMPORT"})
            return 73
        except BaseException:
            lab.emit({"phase": "error", "stage": number, "category": "OTHER"})
            return 74
        names = set(sys.modules)
        delta = sorted(names - previous)
        accepted = set()
        for name in delta:
            if not audit_module(
                lab,
                number,
                name,
                sys.modules[name],
                owners,
                manifest["generated"],
                batch=(delta, accepted, deadline),
            ):
                return AUDIT_EXIT
            accepted.add(name)
        previous = names
        try:
            vm = lab.vm_status()
            if effects() != initial_fds:
                raise CheckFault("FD_SET_CHANGED")
            if vm["threads"] != 1:
                raise CheckFault("THREADS")
        except BaseException as error:
            return check_failure(lab, number, error)
        lab.emit({"phase": "end", "stage": number, "vm": vm, "fds": initial_fds})
    try:
        native = native_check()
    except BaseException as error:
        return check_failure(lab, 3, error)
    lab.emit({"phase": "verified", "native": native, "psycopg_impl": "binary"})
    lab.command(b"ACK\n")
    return 0


def supervisor(case):
    import resource
    import signal
    import subprocess

    lab = support()
    signal.signal(signal.SIGTERM, lab._stop)
    deadline = time.monotonic() + 20
    result = {
        "case": case,
        "outcome": "inconclusive",
        "total_memory_contained": False,
        "imports_fit_as32": False,
        "events": [],
        "cleanup_confirmed": False,
        "kernel": os.uname().release,
        "python": sys.version.split()[0],
        "glibc": os.confstr("CS_GNU_LIBC_VERSION"),
        "environment_names": sorted(os.environ),
    }
    processes = []
    module_rows = []
    try:
        if (
            os.getpid() != 1
            or os.getuid() != 65534
            or not sys.flags.no_site
            or not sys.flags.isolated
        ):
            raise ImportFault
        status = lab.read_text("/proc/self/status")
        if "NoNewPrivs:\t1" not in status or "CapEff:\t0000000000000000" not in status:
            raise ImportFault
        if lab.read_text("/proc/self/cgroup").strip() != "0::/" or lab.vm_status()["threads"] != 1:
            raise ImportFault
        for name, value in (
            ("memory.max", 192 * lab.MIB),
            ("memory.swap.max", 0),
            ("pids.max", 16),
        ):
            if lab.number_file("/sys/fs/cgroup/" + name) != value:
                raise ImportFault
        if result["glibc"] != "glibc 2.36":
            raise ImportFault
        result["startup_cgroup"] = lab.cgroup_sample()
        result["startup_vm"] = lab.vm_status()
        limited = case == "limited"
        if limited:
            if result["startup_vm"]["size"] > 28 * lab.MIB:
                result["outcome"] = "incompatible"
                return result
            resource.setrlimit(resource.RLIMIT_AS, (lab.AS_BYTES, lab.AS_BYTES))
        elif resource.getrlimit(resource.RLIMIT_AS) != (-1, -1):
            raise ImportFault
        result["supervisor_as"] = list(resource.getrlimit(resource.RLIMIT_AS))
        if result["supervisor_as"] != ([lab.AS_BYTES] * 2 if limited else [-1, -1]):
            raise ImportFault
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-S", __file__, "--member"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        processes.append(process)
        reader = LineReader(process.stdout, lab)
        ready = reader.read(deadline)
        result["ready"] = ready
        if (
            ready["phase"],
            ready["pid"],
            ready["ppid"],
            ready["limits"],
            ready["vm"]["threads"],
        ) != ("ready", process.pid, 1, result["supervisor_as"], 1):
            raise ImportFault
        if limited and ready["vm"]["size"] > 28 * lab.MIB:
            result["outcome"] = "incompatible"
            return result
        result["inventory"] = lab.inventory({1, process.pid})
        lab.send(process, b"GO\n")
        next_start = 0
        active = None
        verified = False
        while not verified:
            try:
                event = reader.read(deadline)
            except EOFError:
                collect_returncode(result, process, deadline)
                if (
                    active is not None
                    and type(process.returncode) is int
                    and process.returncode < 0
                ):
                    result["failure"] = "SIGNAL"
                    result["failure_stage"] = active
                else:
                    result["diagnostic_failure"] = "EOF"
                return result
            except TimeoutError:
                result["diagnostic_failure"] = (
                    "STOPPED" if getattr(lab, "STOP", False) else "TIMEOUT"
                )
                return result
            except ImportFault:
                result["diagnostic_failure"] = "PROTOCOL"
                collect_returncode(result, process, deadline)
                return result
            except BaseException:
                result["diagnostic_failure"] = "DIAGNOSTIC"
                collect_returncode(result, process, deadline)
                return result
            phase = event.get("phase")
            if phase == "baseline" and active is None and next_start == 0:
                row = event.get("row")
                validate_inventory([[-1, row]])
                module_rows.append([-1, row])
            elif (
                phase == "start"
                and active is None
                and event == {"phase": "start", "stage": next_start}
            ):
                active = next_start
            elif phase == "module" and active is not None and event.get("stage") == active:
                row = event.get("row")
                if type(row) is not list or len(row) != 3 or any(type(x) is not str for x in row):
                    raise ImportFault
                module_rows.append([active, row])
            elif phase == "end" and active is not None and event.get("stage") == active:
                if event["vm"]["threads"] != 1 or (limited and event["vm"]["peak"] > lab.AS_BYTES):
                    raise ImportFault
                lab.inventory({1, process.pid})
                active = None
                next_start += 1
            elif phase == "verified" and next_start == 3 and active is None:
                if event.get("psycopg_impl") != "binary":
                    raise ImportFault
                verified = True
            elif phase == "audit_error":
                expected_stage = active if active is not None else -1 if next_start == 0 else None
                if not valid_audit_error(event, expected_stage):
                    result["diagnostic_failure"] = "PROTOCOL"
                else:
                    result["diagnostic_failure"] = "AUDIT_ERROR"
                    result["audit_error"] = event
                    result["events"].append(event)
                    if active is not None and event["category"] == "FILELESS_UNATTRIBUTED":
                        consume_batch(result, reader, process, deadline, active)
                        return result
                collect_returncode(result, process, deadline)
                return result
            elif phase == "check_error":
                expected_stage = (
                    active
                    if active is not None
                    else -1
                    if next_start == 0
                    else 3
                    if next_start == 3
                    else None
                )
                if not valid_check_error(event, expected_stage):
                    result["diagnostic_failure"] = "PROTOCOL"
                else:
                    result["diagnostic_failure"] = "CHECK_ERROR"
                    result["check_error"] = event
                    result["events"].append(event)
                collect_returncode(result, process, deadline)
                return result
            elif phase == "error" and active is not None and event.get("stage") == active:
                category = event.get("category")
                if (
                    set(event) != {"phase", "stage", "category"}
                    or type(event["stage"]) is not int
                    or category not in ("MEMORY", "IMPORT", "OTHER")
                ):
                    result["diagnostic_failure"] = "PROTOCOL"
                else:
                    result["failure"] = category
                    result["failure_stage"] = active
                    result["events"].append(event)
                collect_returncode(result, process, deadline)
                if (
                    "failure" in result
                    and result.get("member_returncode")
                    != {"MEMORY": 72, "IMPORT": 73, "OTHER": 74}[category]
                ):
                    result["diagnostic_failure"] = "PROTOCOL"
                return result
            else:
                result["diagnostic_failure"] = (
                    "COLLECTION_FAILED"
                    if event == {"outcome": "inconclusive", "collection_failed": True}
                    else "PROTOCOL"
                )
                collect_returncode(result, process, deadline)
                return result
            if phase not in ("module", "baseline"):
                result["events"].append(event)
            if len(json.dumps(result)) > METADATA_LIMIT or len(module_rows) > MAX_ROWS:
                raise ImportFault
        result["plateau_cgroup"] = lab.cgroup_sample()
        lab.send(process, b"ACK\n")
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
        result["member_returncode"] = process.returncode
        if process.returncode != 0:
            raise ImportFault
        result["outcome"] = "normal"
        result["imports_fit_as32"] = limited
    except BaseException:
        result["outcome"] = "inconclusive"
        result.setdefault("diagnostic_failure", "DIAGNOSTIC")
    finally:
        result["cleanup_confirmed"] = lab.reap(processes)
        if processes and "member_returncode" not in result and type(processes[0].returncode) is int:
            result["member_returncode"] = processes[0].returncode
            result["member_returncode_after_cleanup"] = True
        if result["cleanup_confirmed"]:
            try:
                result["final_inventory"] = lab.inventory({1})
                result["final_cgroup"] = lab.cgroup_sample()
                if "startup_cgroup" in result and any(
                    result["final_cgroup"]["events"][key] > result["startup_cgroup"]["events"][key]
                    for key in ("max", "oom", "oom_kill")
                ):
                    result["outcome"] = "inconclusive"
                    result["outer_pressure"] = True
            except Exception:
                result["cleanup_confirmed"] = False
        if not result["cleanup_confirmed"]:
            result["outcome"] = "inconclusive"
        if result["outcome"] != "normal":
            result["imports_fit_as32"] = False
        try:
            result["module_inventory"] = pack_inventory(module_rows)
        except Exception:
            result["outcome"] = "inconclusive"
            result["imports_fit_as32"] = False
            result["inventory_failure"] = True
    return result


def main():
    if sys.platform != "linux":
        return 64
    if sys.argv[1:] == ["--member"]:
        return member()
    if len(sys.argv) == 3 and sys.argv[1] == "--case" and sys.argv[2] in ("control", "limited"):
        raw = bounded_report(supervisor(sys.argv[2]))
        if os.write(1, raw + b"\n") != len(raw) + 1:
            raise ImportFault
        return 0
    return 64


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        os.write(1, b'{"outcome":"inconclusive","collection_failed":true}\n')
        code = 70
    raise SystemExit(code)
