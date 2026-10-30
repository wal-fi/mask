"""Secretless Linux guard experiment; no effects on import or product caller."""

import base64
import ctypes
import errno
import hashlib
import importlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import types
import zlib

MIB = 1024 * 1024
GUARD_SHA = "dd10fb725b846ca097d7bef8b434fa4846f80e36216b34a3a16e658f1d15d0b4"
PYTHON = "/opt/maskgw/venv/bin/python"
MAX_LINE = 16384
CANARY = b"PUBLIC_MASKGW_GUARD_CONTROL_NOT_A_SECRET_20261026"
MODULES = ("maskgw.runtime.worker_job",)
REPORT = {"outcome": "NOT_PASSED", "phase": "START"}


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def environment():
    return {
        "PATH": "/opt/maskgw/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "MALLOC_ARENA_MAX": "1",
    }


def load_guard():
    raw = globals()["GUARD_SOURCE"]
    need(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == GUARD_SHA, "GUARD_PIN")
    module = types.ModuleType("_maskgw_guard_copied_probe")
    sys.modules[module.__name__] = module
    exec(compile(raw, "<copied-linux-guard>", "exec"), module.__dict__)
    return module


def bootstrap(guard_source, probe_source):
    need(type(guard_source) is bytes and type(probe_source) is bytes, "SOURCES")
    need(len(guard_source) < 16384 and len(probe_source) < 32768, "SOURCE_SIZE")
    guard = base64.b64encode(zlib.compress(guard_source, 9)).decode()
    probe = base64.b64encode(zlib.compress(probe_source, 9)).decode()
    command = (
        "import base64,zlib; GUARD_SOURCE=zlib.decompress(base64.b64decode("
        + repr(guard)
        + ")); PROBE_SOURCE=zlib.decompress(base64.b64decode("
        + repr(probe)
        + ")); exec(compile(PROBE_SOURCE,'<oracle9-process-probe>','exec'))"
    )
    need(len(command) < 25000, "BOOTSTRAP_SIZE")
    return command


def child_command(role, parent):
    need(role in {"control", "protected", "intermediate", "orphan", "wrong-parent"}, "ROLE")
    need(type(parent) is int and 0 < parent < (1 << 31), "PARENT")
    code = bootstrap(globals()["GUARD_SOURCE"], globals()["PROBE_SOURCE"])
    return [PYTHON, "-I", "-B", "-c", code, role, str(parent)]


def emit(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    need(len(raw) < MAX_LINE, "REPORT_SIZE")
    sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()


def read_line(stream, seconds=8):
    deadline = time.monotonic() + seconds
    data = bytearray()
    while time.monotonic() < deadline:
        ready, _, _ = select.select([stream.fileno()], [], [], max(0, deadline - time.monotonic()))
        need(ready, "READY_TIMEOUT")
        block = os.read(stream.fileno(), 4096)
        need(block, "READY_EOF")
        data.extend(block)
        need(len(data) <= MAX_LINE, "READY_SIZE")
        if b"\n" in data:
            need(data.count(b"\n") == 1 and data.endswith(b"\n"), "READY_FRAME")
            return json.loads(data)
    raise RuntimeError("READY_TIMEOUT")


def facts(guard_facts):
    return {
        "role": guard_facts.role.value,
        "pid": guard_facts.pid,
        "parent_pid": guard_facts.parent_pid,
        "as_bytes": guard_facts.address_limit_bytes,
        "observed_address_bytes": guard_facts.observed_address_bytes,
        "dumpable": guard_facts.dumpable,
        "pdeathsig": guard_facts.parent_death_signal,
        "core": list(guard_facts.core),
    }


def memory_status():
    raw = Path("/proc/self/status").read_text()
    fields = dict(line.split(":", 1) for line in raw.splitlines() if ":" in line)
    return {key: fields[key].strip() for key in ("VmPeak", "VmSize", "VmRSS", "Threads")}


def import_body():
    for name in MODULES:
        importlib.import_module(name)
    return {"imported": list(MODULES), "memory": memory_status()}


def spawn(role, parent):
    return subprocess.Popen(
        child_command(role, parent),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment(),
        close_fds=True,
    )


def reap(process, graceful=False):
    if process.poll() is None and graceful:
        try:
            os.write(process.stdin.fileno(), b"Q")
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=3)
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            stream.close()
    need(process.poll() is not None, "REAP")
    need(process.stdin.closed and process.stdout.closed, "PIPE_CLEANUP")
    return process.returncode


def runtime_profile():
    import resource

    need(sys.platform == "linux" and sys.version_info[:3] == (3, 11, 13), "RUNTIME")
    need(sys.flags.isolated and sys.flags.dont_write_bytecode and sys.executable == PYTHON, "FLAGS")
    need(os.getpid() == 1 and os.getuid() == os.getgid() == 10001, "PID1_USER")
    need(resource.getrlimit(resource.RLIMIT_CORE) == (0, 0), "CORE")
    need(resource.getrlimit(resource.RLIMIT_NOFILE) == (128, 128), "NOFILE")
    cgroup = Path("/sys/fs/cgroup")
    limits = {
        name: (cgroup / name).read_text().strip()
        for name in (
            "memory.max",
            "memory.swap.max",
            "pids.max",
            "cpu.max",
        )
    }
    need(limits["memory.max"] == "536870912" and limits["memory.swap.max"] == "0", "MEMORY")
    need(limits["pids.max"] == "32", "PIDS")
    quota, period = limits["cpu.max"].split()
    need(quota != "max" and int(quota) == int(period) > 0, "CPU")
    need({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "NETWORK")
    mounts = [line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines()]
    root = [row for row in mounts if row[4] == "/"]
    tmp = [row for row in mounts if row[4] == "/tmp"]
    need(len(root) == 1 and "ro" in root[0][5].split(","), "ROOT_RO")
    need(len(tmp) == 1 and {"noexec", "nodev", "nosuid"} <= set(tmp[0][5].split(",")), "TMP_FLAGS")
    need(Path("/tmp").stat().st_uid == Path("/tmp").stat().st_gid == 10001, "TMP_USER")
    need(Path("/tmp").stat().st_mode & 0o777 == 0o700, "TMP_MODE")
    for where, size in (("/tmp", 16 * MIB), ("/dev/shm", 8 * MIB)):
        fs = os.statvfs(where)
        need(fs.f_blocks * fs.f_frsize == size, "TMP_SIZE")
    core = Path("/proc/sys/kernel/core_pattern").read_text().strip()
    suid = Path("/proc/sys/fs/suid_dumpable").read_text().strip()
    need(suid in {"0", "1", "2"} and not (suid == "2" and core.startswith("|")), "CORE_PROFILE")
    yama = Path("/proc/sys/kernel/yama/ptrace_scope")
    return {
        "kernel": os.uname().release,
        "limits": limits,
        "core_pattern": core,
        "suid_dumpable": suid,
        "ptrace_scope": yama.read_text().strip() if yama.exists() else None,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "root_read_only": True,
    }


def child(role, expected_parent):
    guard = load_guard()
    need(dict(os.environ) == environment(), "CHILD_ENV")
    if role == "wrong-parent":
        category = None
        system = guard._LinuxSystem()
        prior_as, prior_dump = system.get_limit("as"), system.dumpable()
        actual_parent, pid = os.getppid(), os.getpid()
        wrong_parent = 1
        while wrong_parent in {actual_parent, pid}:
            wrong_parent += 1
        need(prior_dump == 1, "WRONG_PARENT_CONTROL")
        try:
            guard.protect_process(
                role=guard.ProcessRole.WORKER,
                address_limit_bytes=256 * MIB,
                expected_parent_pid=wrong_parent,
            )
        except guard.ProcessGuardError as error:
            category = error.category.value
        need(category == "PARENT", "WRONG_PARENT_ACCEPTED")
        need(
            system.get_limit("as") == prior_as and system.dumpable() == prior_dump,
            "WRONG_PARENT_MUTATED",
        )
        emit(
            {
                "refused": category,
                "ready": False,
                "pid": pid,
                "actual_parent_pid": actual_parent,
                "expected_parent_pid": wrong_parent,
                "as_unchanged": True,
                "dumpable": prior_dump,
            }
        )
        return
    result = guard.protect_process(
        role=guard.ProcessRole.WORKER,
        address_limit_bytes=256 * MIB,
        expected_parent_pid=expected_parent,
    )
    if role == "control":
        # Deliberate positive control only: all other guard/profile facts stay equal.
        guard._LinuxSystem().set_prctl(4, 1)
    dump = guard._LinuxSystem().dumpable()
    need(dump == (1 if role == "control" else 0), "DUMPABLE_CONTROL")
    if role == "intermediate":
        process = spawn("orphan", os.getpid())
        message = read_line(process.stdout)
        need(message["pid"] == process.pid and message["ready"] is True, "ORPHAN_READY")
        emit({"grandchild": process.pid, "guard": message["guard"], "ready": True})
        os._exit(0)
    body = import_body()
    buffer = ctypes.create_string_buffer(CANARY)
    emit(
        {
            "ready": True,
            "pid": os.getpid(),
            "address": ctypes.addressof(buffer),
            "bytes": len(CANARY),
            "dumpable": dump,
            "guard": facts(result),
            "body": body,
        }
    )
    if role == "orphan":
        time.sleep(30)  # Only SIGKILL/PDEATHSIG may end this test, never EOF success.
        raise RuntimeError("PARENT_DEATH_MISSED")
    ready, _, _ = select.select([sys.stdin.fileno()], [], [], 15)
    need(ready, "CHILD_IDLE")
    token = os.read(sys.stdin.fileno(), 1)
    need(token in (b"Q", b""), "CHILD_TOKEN")
    need(len(buffer) > len(CANARY), "CANARY_LIFETIME")


def permission_call(operation):
    try:
        equal = operation()
        return {"allowed": True, "equal": equal, "errno": 0}
    except OSError as error:
        need(error.errno in (errno.EACCES, errno.EPERM), "ACCESS_NOT_PERMISSION")
        return {"allowed": False, "equal": False, "errno": error.errno}


def proc_memory(pid, address):
    descriptor = os.open(f"/proc/{pid}/mem", os.O_RDONLY | os.O_CLOEXEC)
    try:
        return os.pread(descriptor, len(CANARY), address) == CANARY
    finally:
        os.close(descriptor)


class IOVec(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("length", ctypes.c_size_t)]


def vm_memory(pid, address):
    library = ctypes.CDLL(None, use_errno=True)
    function = library.process_vm_readv
    function.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(IOVec),
        ctypes.c_ulong,
        ctypes.POINTER(IOVec),
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    function.restype = ctypes.c_ssize_t
    buffer = ctypes.create_string_buffer(len(CANARY))
    local = IOVec(ctypes.addressof(buffer), len(CANARY))
    remote = IOVec(address, len(CANARY))
    count = function(pid, ctypes.byref(local), 1, ctypes.byref(remote), 1, 0)
    if count < 0:
        raise OSError(ctypes.get_errno(), "VM_DENIED")
    need(count == len(CANARY), "VM_PARTIAL")
    return buffer.raw == CANARY


def process_state(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    return raw.rsplit(") ", 1)[1].split()[0]


def ptrace_roundtrip(pid):
    function = ctypes.CDLL(None, use_errno=True).ptrace
    function.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    function.restype = ctypes.c_long
    if function(16, pid, None, None) != 0:  # PTRACE_ATTACH
        raise OSError(ctypes.get_errno(), "PTRACE_DENIED")
    deadline = time.monotonic() + 2
    stopped = False
    while time.monotonic() < deadline:
        waited, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
        if waited:
            need(os.WIFSTOPPED(status), "PTRACE_NOT_STOPPED")
            stopped = True
            break
        time.sleep(0.01)
    need(stopped, "PTRACE_STOP_TIMEOUT")
    need(function(17, pid, None, None) == 0, "PTRACE_DETACH")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if process_state(pid) not in {"T", "t"}:
            return True
        time.sleep(0.01)
    raise RuntimeError("PTRACE_RESUME_TIMEOUT")


def proc_environment(pid):
    with Path(f"/proc/{pid}/environ").open("rb") as stream:
        raw = stream.read(8193)
    need(len(raw) <= 8192, "ENV_SIZE")
    # Never return or log raw environment, even this public control environment.
    expected = {k.encode() + b"=" + v.encode() for k, v in environment().items()}
    return set(raw.rstrip(b"\0").split(b"\0")) == expected


def proc_descriptors(pid):
    return len(list(Path(f"/proc/{pid}/fd").iterdir())) >= 3


def access_case(role):
    process = spawn(role, 1)
    result = {"role": role}
    REPORT["active_access"] = result
    try:
        message = read_line(process.stdout)
        result["ready"] = message
        need(message["ready"] is True and message["pid"] == process.pid, "CHILD_IDENTITY")
        need(message["dumpable"] == (1 if role == "control" else 0), "CHILD_DUMPABLE")
        pid, address = process.pid, message["address"]
        need(process.poll() is None, "CHILD_LOST")
        result["mem"] = permission_call(lambda: proc_memory(pid, address))
        result["vm"] = permission_call(lambda: vm_memory(pid, address))
        result["ptrace"] = permission_call(lambda: ptrace_roundtrip(pid))
        result["environ"] = permission_call(lambda: proc_environment(pid))
        result["fd"] = permission_call(lambda: proc_descriptors(pid))
        code = reap(process, graceful=True)
        need(code == 0, "CONTROL_EXIT")
        result["exit_code"] = code
        return result
    finally:
        reap(process)


def parent_death_case():
    process = spawn("intermediate", 1)
    grandchild = None
    try:
        message = read_line(process.stdout)
        grandchild = message["grandchild"]
        need(type(grandchild) is int and 1 < grandchild < (1 << 31), "ORPHAN_PID")
        process.wait(timeout=3)
        need(process.returncode == 0, "INTERMEDIATE_EXIT")
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            try:
                waited, status = os.waitpid(grandchild, os.WNOHANG)
            except ChildProcessError:
                waited = 0
            if waited:
                grandchild = None
                need(
                    os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL,
                    "PDEATH_STATUS",
                )
                return {
                    "intermediate_exit": 0,
                    "grandchild_signal": 9,
                    "reaped": True,
                    "guard": message["guard"],
                }
            time.sleep(0.01)
        raise RuntimeError("PDEATH_TIMEOUT")
    finally:
        reap(process)
        if grandchild is not None:
            try:
                os.kill(grandchild, signal.SIGKILL)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 4
            collected = False
            while time.monotonic() < deadline:
                try:
                    waited, _status = os.waitpid(grandchild, os.WNOHANG)
                    if waited:
                        collected = True
                        break
                except ChildProcessError:
                    pass
                time.sleep(0.01)
            need(collected, "ORPHAN_CLEANUP")


def controller():
    REPORT["phase"] = "PROFILE"
    guard = load_guard()
    profile = runtime_profile()
    protected = guard.protect_process(
        role=guard.ProcessRole.CONTROLLER, address_limit_bytes=384 * MIB
    )
    os.environ.clear()
    os.environ.update(environment())
    REPORT.update(
        {
            "phase": "CONTROLLER_PROTECTED",
            "profile": profile,
            "controller": facts(protected),
            "controller_body": import_body(),
        }
    )
    output = REPORT
    output["phase"] = "CONTROL"
    positive = access_case("control")
    output["positive"] = positive
    output["phase"] = "PROTECTED"
    negative = access_case("protected")
    output.update(positive=positive, negative=negative)
    output["phase"] = "COMPARE"
    comparisons = {}
    for name in ("mem", "vm", "ptrace", "environ", "fd"):
        comparisons[name] = (
            positive[name]["allowed"] and positive[name]["equal"] and not negative[name]["allowed"]
        )
    output["differential"] = comparisons
    need(all(comparisons.values()), "ACCESS_NOT_DIFFERENTIAL")
    output["phase"] = "PARENT_DEATH"
    output["parent_death"] = parent_death_case()
    output["phase"] = "WRONG_PARENT"
    wrong = spawn("wrong-parent", 1)
    try:
        refusal = read_line(wrong.stdout)
        need(
            refusal["refused"] == "PARENT"
            and refusal["ready"] is False
            and refusal["pid"] == wrong.pid
            and refusal["actual_parent_pid"] == 1
            and refusal["expected_parent_pid"] not in {1, wrong.pid}
            and refusal["as_unchanged"] is True
            and refusal["dumpable"] == 1,
            "WRONG_PARENT",
        )
        wrong.wait(timeout=3)
        need(wrong.returncode == 0, "WRONG_PARENT_EXIT")
        output["wrong_parent"] = refusal
    finally:
        reap(wrong)
    output["remaining_pids"] = sorted(
        int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()
    )
    need(output["remaining_pids"] == [1], "DESCENDANT_REMAINS")
    output["outcome"] = "ORACLE9_PROCESS_GUARD_VERIFIED"
    output["phase"] = "COMPLETE"
    output["pid1_death_proved"] = False
    emit(output)


def main():
    role = sys.argv[1]
    if role == "controller":
        need(len(sys.argv) == 2, "ARGS")
        controller()
    else:
        need(len(sys.argv) == 3, "ARGS")
        need(role in {"control", "protected", "intermediate", "orphan", "wrong-parent"}, "ROLE")
        text = sys.argv[2]
        need(text.isascii() and text.isdecimal() and 0 < int(text) < (1 << 31), "PARENT")
        child(role, int(text))


if __name__ == "__main__":
    try:
        main()
    except BaseException as failure:
        REPORT.update(outcome="NOT_PASSED", failure_type=type(failure).__name__)
        emit(REPORT)
        sys.exit(1)
