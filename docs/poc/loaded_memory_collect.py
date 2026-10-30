"""Lab import producer and closed event collector, not an executable supervisor."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from types import ModuleType

HARNESS = {
    "__main__": "linux_loaded_probe.py",
    "_lab_loaded_protocol": "loaded_memory_protocol.py",
    "_lab_loaded_member": "loaded_memory_member.py",
    "_lab_loaded_collect": "loaded_memory_collect.py",
    "_lab_import_probe": "linux_import_probe.py",
    "_lab_support": "linux_as_probe.py",
}


class CollectFault(Exception):
    def __init__(self):
        super().__init__("PROTOCOL")


def resolve_path(value):
    return Path(value).resolve().as_posix()


def audit_one(io, probe, stage, name, module, owners, generated, *, resolve=resolve_path):
    """Intercept only the closed harness names, before the unchanged origin rules."""
    if name not in HARNESS:
        return probe.audit_module(io, stage, name, module, owners, generated, batch=None)
    good, has_file = False, False
    try:
        if type(module) is ModuleType:
            filename = module.__dict__.get("__file__")
            has_file = type(filename) is str and bool(filename)
            good = has_file and resolve(filename) == "/probe/" + HARNESS[name]
    except BaseException:
        pass
    if not good:
        io.emit(
            {
                "phase": "audit_error",
                "stage": stage,
                "module": name,
                "category": "OUTSIDE_ORIGIN",
                "has_file": has_file,
                "under_installed": False,
            }
        )
        return False
    row = [name, "harness", "probe/" + HARNESS[name]]
    io.emit(
        {"phase": "baseline", "row": row}
        if stage == -1
        else {"phase": "module", "stage": stage, "row": row}
    )
    return True


def valid_vm(vm):
    if (
        type(vm) is not dict
        or any(type(key) is not str for key in vm)
        or set(vm) != {"size", "peak", "rss", "threads"}
        or any(type(value) is not int or not 0 <= value <= 1 << 50 for value in vm.values())
        or vm["threads"] != 1
        or not 0 < vm["size"] <= vm["peak"]
        or vm["rss"] > vm["size"]
    ):
        raise CollectFault()


def valid_effects(value):
    if (
        type(value) is not dict
        or set(value) != {"fds", "proc_children_available"}
        or type(value["proc_children_available"]) is not bool
        or type(value["fds"]) is not list
        or len(value["fds"]) != 4
        or any(type(fd) is not int or not 0 <= fd <= 63 for fd in value["fds"])
        or value["fds"][:3] != [0, 1, 2]
        or value["fds"][3] < 3
    ):
        raise CollectFault()


def collect_imports(
    io, probe, owners, generated, *, modules, importer, effects_fn, native_fn, resolve=resolve_path
):
    """Trusted dependencies only; all output goes through io's sole deadline writer."""
    try:
        initial = effects_fn()
        valid_effects(initial)
    except BaseException as error:
        return probe.check_failure(io, -1, error)
    previous = set(modules)
    for name in sorted(previous):
        io.check()
        if not audit_one(io, probe, -1, name, modules[name], owners, generated, resolve=resolve):
            return 75
    for stage, target in enumerate(probe.ROOTS):
        io.check()
        io.emit({"phase": "start", "stage": stage})
        failure, code = None, 0
        try:
            importer(target)
        except MemoryError:
            failure, code = "MEMORY", 72
        except ImportError:
            failure, code = "IMPORT", 73
        except BaseException:
            failure, code = "OTHER", 74
        if failure is not None:
            io.emit({"phase": "error", "stage": stage, "category": failure})
            return code
        current = set(modules)
        for name in sorted(current - previous):
            io.check()
            if not audit_one(
                io, probe, stage, name, modules[name], owners, generated, resolve=resolve
            ):
                return 75
        previous = current
        try:
            vm, _limits = io.sample()
            valid_vm(vm)
            if effects_fn() != initial:
                raise probe.CheckFault("FD_SET_CHANGED")
        except BaseException as error:
            return probe.check_failure(io, stage, error)
        io.emit({"phase": "end", "stage": stage, "vm": vm, "fds": initial})
    try:
        native = native_fn()
    except BaseException as error:
        return probe.check_failure(io, 3, error)
    io.emit({"phase": "verified", "native": native, "psycopg_impl": "binary"})
    return 0


def _envelope(event, phase):
    fields = {"phase", "vm", "limits"} | ({"pid", "ppid"} if phase == "ready" else set())
    if (
        phase not in ("ready", "loaded")
        or type(event) is not dict
        or any(type(key) is not str for key in event)
        or set(event) != fields
        or type(event["phase"]) is not str
        or event["phase"] != phase
    ):
        raise CollectFault()
    valid_vm(event["vm"])
    limits = event["limits"]
    if (
        type(limits) is not list
        or len(limits) != 2
        or any(type(value) is not int or not -1 <= value <= 1 << 50 for value in limits)
    ):
        raise CollectFault()
    if phase == "ready" and (
        type(event["pid"]) is not int
        or not 2 <= event["pid"] <= 1 << 30
        or type(event["ppid"]) is not int
        or event["ppid"] != 1
    ):
        raise CollectFault()
    return {**event, "vm": dict(event["vm"]), "limits": list(limits)}


def envelope(event, phase):
    try:
        return _envelope(event, phase)
    except BaseException:
        pass
    raise CollectFault()


def parse_limits(raw):
    try:
        return _parse_limits(raw)
    except BaseException:
        pass
    raise CollectFault()


def _parse_limits(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= 65536 or not raw.endswith(b"\n"):
        raise CollectFault()
    result = None
    for line in raw.splitlines():
        parts = line.split()
        if parts[:3] != [b"Max", b"address", b"space"]:
            continue
        if result is not None or len(parts) != 6 or parts[-1] != b"bytes":
            raise CollectFault()
        result = []
        for token in parts[3:5]:
            if token == b"unlimited":
                result.append(-1)
            elif not token or len(token) > 16 or any(not 48 <= char <= 57 for char in token):
                raise CollectFault()
            else:
                value = int(token)
                if value > 1 << 50:
                    raise CollectFault()
                result.append(value)
    if result is None:
        raise CollectFault()
    return result


def closed(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            pass
        if self.state != "FAILED":
            self.failure, self.expected_exit = "PROTOCOL", 77
        self.state = "FAILED"
        self._rows.clear()
        raise CollectFault()

    return guarded


class ImportCollector:
    """No I/O or commands. Trusts the frozen origin validator, never a success marker alone."""

    def __init__(self, probe):
        self.probe = probe
        self.state, self.stage, self.active = "COLLECTING", 0, None
        self._rows, self._names, self._fds = [], set(), None
        self.failure, self.expected_exit = None, None

    def _keys(self, event, expected):
        if set(event) != expected:
            raise CollectFault()

    def _row(self, stage, row):
        entry = [stage, row]
        self.probe.validate_inventory([entry])
        if row[0] in self._names or len(self._rows) >= self.probe.MAX_ROWS:
            raise CollectFault()
        self._names.add(row[0])
        self._rows.append([stage, list(row)])

    def _failure(self, event, phase):
        stage = self.active if self.active is not None else (-1 if self.stage == 0 else 3)
        if phase == "error":
            self._keys(event, {"phase", "stage", "category"})
            if (
                self.active is None
                or type(event["stage"]) is not int
                or event["stage"] != self.active
                or type(event["category"]) is not str
                or event["category"] not in ("MEMORY", "IMPORT", "OTHER")
            ):
                raise CollectFault()
            self.failure = event["category"]
            self.expected_exit = {"MEMORY": 72, "IMPORT": 73, "OTHER": 74}[self.failure]
        elif phase == "audit_error" and self.probe.valid_audit_error(event, stage):
            self.failure, self.expected_exit = "AUDIT_ERROR", 75
        elif phase == "check_error" and self.probe.valid_check_error(event, stage):
            self.failure, self.expected_exit = "CHECK_ERROR", 76
        else:
            raise CollectFault()
        self.state = "FAILED"
        raise CollectFault()

    @closed
    def feed(self, event):
        if (
            self.state != "COLLECTING"
            or type(event) is not dict
            or any(type(key) is not str for key in event)
            or type(event.get("phase")) is not str
        ):
            raise CollectFault()
        phase = event["phase"]
        if phase in ("error", "audit_error", "check_error"):
            self._failure(event, phase)
        elif phase == "baseline" and self.active is None and self.stage == 0:
            self._keys(event, {"phase", "row"})
            self._row(-1, event["row"])
        elif phase == "start" and self.active is None and self.stage < 3 and self._rows:
            self._keys(event, {"phase", "stage"})
            if type(event["stage"]) is not int or event["stage"] != self.stage:
                raise CollectFault()
            self.active = self.stage
        elif phase == "module" and self.active is not None:
            self._keys(event, {"phase", "stage", "row"})
            if type(event["stage"]) is not int or event["stage"] != self.active:
                raise CollectFault()
            self._row(self.active, event["row"])
        elif phase == "end" and self.active is not None:
            self._keys(event, {"phase", "stage", "vm", "fds"})
            if type(event["stage"]) is not int or event["stage"] != self.active:
                raise CollectFault()
            valid_vm(event["vm"])
            valid_effects(event["fds"])
            if self._fds is not None and event["fds"] != self._fds:
                raise CollectFault()
            self._fds = {
                "fds": list(event["fds"]["fds"]),
                "proc_children_available": event["fds"]["proc_children_available"],
            }
            self.stage, self.active = self.stage + 1, None
        elif phase == "verified" and self.stage == 3 and self.active is None:
            self._keys(event, {"phase", "native", "psycopg_impl"})
            native = event["native"]
            if (
                type(event["psycopg_impl"]) is not str
                or event["psycopg_impl"] != "binary"
                or type(native) is not dict
                or any(type(key) is not str for key in native)
                or set(native) != set(self.probe.NATIVE_ROOTS)
            ):
                raise CollectFault()
            audited = {row[0]: row for _stage, row in self._rows}
            for root, names in native.items():
                if (
                    type(names) is not list
                    or not names
                    or len(names) > self.probe.MAX_ROWS
                    or any(type(name) is not str for name in names)
                    or len(set(names)) != len(names)
                ):
                    raise CollectFault()
                for name in names:
                    row = audited.get(name)
                    if (
                        not (name == root or name.startswith(root + "."))
                        or row is None
                        or not row[2].startswith("installed/")
                        or not row[2].endswith(".so")
                    ):
                        raise CollectFault()
            self.state, self.expected_exit = "VERIFIED", 0
        else:
            raise CollectFault()
        return self.state == "VERIFIED"

    @closed
    def snapshot(self):
        if self.state != "VERIFIED":
            raise CollectFault()
        return [[stage, list(row)] for stage, row in self._rows]

    def match_exit(self, code):
        return type(code) is int and self.expected_exit is not None and code == self.expected_exit
