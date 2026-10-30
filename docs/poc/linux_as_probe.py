"""Synthetic Linux address-space diagnostic; not product or total-memory proof.

No workload on import/selftest. Container supervisor applies AS to itself before
creating members. Host observer, image selection and Docker lifecycle are separate.
"""

from __future__ import annotations

import json
import os
import select
import sys
import time

MIB = 1024 * 1024
AS_BYTES = 32 * MIB
HEADROOM = 4 * MIB
OUTER_BYTES = 192 * MIB
PAGE = 4096
STEP = 4 * MIB
TARGET = 40 * MIB
LINE_BYTES = 4096
CASE_SECONDS = 30
MEMBER_FIELDS = frozenset(
    {
        "phase",
        "pid",
        "ppid",
        "kind",
        "limits",
        "vm",
        "accepted_bytes",
        "touched_pages",
        "blocks",
        "failure",
        "errno",
    }
)
STOP = False


class ProbeFault(Exception):
    def __init__(self):
        super().__init__("diagnostic collection failed")


def integer(value, minimum=0, maximum=1 << 50):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProbeFault
    return value


def encode_line(value):
    data = json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode(
        "ascii"
    )
    if len(data) + 1 > LINE_BYTES:
        raise ProbeFault
    return data + b"\n"


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ProbeFault
        result[key] = value
    return result


def decode_line(data):
    if type(data) is not bytes or not 1 <= len(data) <= LINE_BYTES or not data.endswith(b"\n"):
        raise ProbeFault
    try:
        value = json.loads(data, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeFault from None
    if type(value) is not dict:
        raise ProbeFault
    return value


def parse_status(text):
    wanted = {"VmSize": "size", "VmPeak": "peak", "VmRSS": "rss", "Threads": "threads"}
    result = {}
    for line in text.splitlines():
        key, separator, rest = line.partition(":")
        if separator and key in wanted:
            fields = rest.split()
            expected = 1 if key == "Threads" else 2
            if len(fields) != expected or (expected == 2 and fields[1] != "kB"):
                raise ProbeFault
            try:
                value = int(fields[0])
            except ValueError:
                raise ProbeFault from None
            if wanted[key] in result:
                raise ProbeFault
            result[wanted[key]] = integer(value, 1) * (1 if expected == 1 else 1024)
    if set(result) != set(wanted.values()):
        raise ProbeFault
    return result


def classify_member(item, *, limited, target):
    if type(item) is not dict or set(item) != MEMBER_FIELDS or item["phase"] != "held":
        raise ProbeFault
    integer(item["pid"], 2)
    integer(item["ppid"], 1)
    if item["kind"] not in ("private", "shared", "baseline"):
        raise ProbeFault
    limits = item["limits"]
    if type(limits) is not list or len(limits) != 2 or any(type(x) is not int for x in limits):
        raise ProbeFault
    vm = item["vm"]
    if type(vm) is not dict or set(vm) != {"size", "peak", "rss", "threads"}:
        raise ProbeFault
    for value in vm.values():
        integer(value, 1)
    if vm["threads"] != 1 or vm["size"] > vm["peak"]:
        raise ProbeFault
    accepted = integer(item["accepted_bytes"], 0, TARGET)
    pages = integer(item["touched_pages"], 0, TARGET // PAGE)
    blocks = integer(item["blocks"], 0, 10)
    if accepted % PAGE or pages != accepted // PAGE or (accepted == 0) != (blocks == 0):
        raise ProbeFault
    if item["failure"] not in ("NONE", "MEMORY", "ENOMEM", "OTHER"):
        raise ProbeFault
    if item["errno"] is not None:
        integer(item["errno"], 1, 4096)
    if limited and vm["peak"] > AS_BYTES:
        return "fail"
    if limits != ([AS_BYTES, AS_BYTES] if limited else [-1, -1]):
        return "incompatible"
    if target is not None:
        if item["failure"] == "NONE" and accepted == target:
            return "normal" if limited else "control_ok"
        return "inconclusive"
    if item["failure"] == "NONE":
        return "fail" if accepted == TARGET else "inconclusive"
    if (item["failure"], item["errno"]) in (("MEMORY", None), ("ENOMEM", 12)):
        return "imposed" if accepted >= STEP and blocks >= 1 else "inconclusive"
    return "inconclusive"


def read_text(path, limit=65536):
    with open(path, "rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ProbeFault
    return raw.decode("ascii", errors="strict")


def vm_status():
    return parse_status(read_text("/proc/self/status"))


def number_file(path):
    return integer(int(read_text(path, 64).strip()))


def counters(path, keys):
    result = {}
    for line in read_text(path).splitlines():
        fields = line.split()
        if len(fields) != 2:
            raise ProbeFault
        if fields[0] in keys:
            if fields[0] in result:
                raise ProbeFault
            result[fields[0]] = integer(int(fields[1]))
    if not keys <= result.keys():
        raise ProbeFault
    return result


def cgroup_sample():
    base = "/sys/fs/cgroup/"
    return {
        "current": number_file(base + "memory.current"),
        "peak": number_file(base + "memory.peak"),
        "events": counters(base + "memory.events", {"max", "oom", "oom_kill"}),
        "stat": counters(base + "memory.stat", {"anon", "file", "shmem", "kernel", "sock"}),
        "procs": sorted({integer(int(x), 1) for x in read_text(base + "cgroup.procs").split()}),
        "pids_current": number_file(base + "pids.current"),
    }


def emit(value):
    data = encode_line(value)
    written = os.write(1, data)
    if written != len(data):
        raise ProbeFault


def command(expected):
    data = b""
    while len(data) < len(expected):
        part = os.read(0, len(expected) - len(data))
        if not part:
            raise ProbeFault
        data += part
    if data != expected:
        raise ProbeFault


def member(kind):
    import mmap
    import resource

    limits = list(resource.getrlimit(resource.RLIMIT_AS))
    start = vm_status()
    emit(
        {
            "phase": "ready",
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "kind": kind,
            "limits": limits,
            "vm": start,
        }
    )
    command(b"GO\n")
    blocks = []
    accepted = pages = 0
    failure, error_number = "NONE", None
    try:
        while accepted < (MIB if kind == "baseline" else TARGET):
            size = MIB if kind == "baseline" else STEP
            try:
                buffer = (
                    mmap.mmap(
                        -1, size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE
                    )
                    if kind == "shared"
                    else bytearray(size)
                )
            except MemoryError:
                failure = "MEMORY"
                break
            except OSError as error:
                error_number = error.errno
                failure = "ENOMEM" if error.errno == 12 else "OTHER"
                break
            for offset in range(0, size, PAGE):
                buffer[offset] = 65
                pages += 1
            blocks.append(buffer)
            del buffer
            accepted += size
        emit(
            {
                "phase": "held",
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "kind": kind,
                "limits": limits,
                "vm": vm_status(),
                "accepted_bytes": accepted,
                "touched_pages": pages,
                "blocks": len(blocks),
                "failure": failure,
                "errno": error_number,
            }
        )
        command(b"ACK\n")  # no payload freed before the supervisor samples all members
    finally:
        while blocks:
            retained = blocks.pop()
            if kind == "shared":
                retained.close()
            del retained
    emit({"phase": "released", "pid": os.getpid()})


def read_line(handle, deadline):
    data = b""
    while not STOP and time.monotonic() < deadline:
        if not select.select(
            [handle.fileno()], [], [], min(0.1, max(0, deadline - time.monotonic()))
        )[0]:
            continue
        part = os.read(handle.fileno(), LINE_BYTES + 1 - len(data))
        if not part:
            raise ProbeFault
        data += part
        if len(data) > LINE_BYTES:
            raise ProbeFault
        if b"\n" in data:
            if data.count(b"\n") != 1 or not data.endswith(b"\n"):
                raise ProbeFault
            return decode_line(data)
    raise ProbeFault


def send(process, data):
    if process.stdin.write(data) != len(data):
        raise ProbeFault


def inventory(expected):
    numeric = {int(name) for name in os.listdir("/proc") if name.isdecimal()}
    actual = set(cgroup_sample()["procs"])
    if numeric != expected or actual != expected:
        raise ProbeFault
    return sorted(actual)


def reap(processes):
    import subprocess

    clean = True
    for process in processes:
        try:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            clean = False
        finally:
            for pipe in (process.stdin, process.stdout):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        clean = False
        try:
            clean = clean and process.poll() is not None
        except OSError:
            clean = False
    return clean


def _stop(_signal, _frame):
    global STOP
    STOP = True


def supervisor(case):
    import resource
    import signal
    import subprocess

    signal.signal(signal.SIGTERM, _stop)
    deadline = time.monotonic() + CASE_SECONDS
    result = {
        "case": case,
        "outcome": "inconclusive",
        "cleanup_confirmed": False,
        "total_memory_contained": False,
        "outer_limit_exercised": False,
        "members": [],
        "kernel": os.uname().release,
        "python": sys.version.split()[0],
    }
    processes = []
    try:
        status = read_text("/proc/self/status")
        if os.getpid() != 1 or os.getuid() == 0 or os.sysconf("SC_PAGE_SIZE") != PAGE:
            raise ProbeFault
        if "NoNewPrivs:\t1" not in status or "CapEff:\t0000000000000000" not in status:
            raise ProbeFault
        if vm_status()["threads"] != 1 or read_text("/proc/self/cgroup").strip() != "0::/":
            raise ProbeFault
        if not os.path.isfile("/sys/fs/cgroup/cgroup.controllers"):
            raise ProbeFault
        for filename, expected in (
            ("memory.max", OUTER_BYTES),
            ("memory.swap.max", 0),
            ("pids.max", 16),
        ):
            if number_file("/sys/fs/cgroup/" + filename) != expected:
                raise ProbeFault
        result["startup_cgroup"] = cgroup_sample()
        result["startup_vm"] = vm_status()
        result["inherited_as"] = list(resource.getrlimit(resource.RLIMIT_AS))
        limited = case != "control"
        if limited:
            if result["startup_vm"]["size"] > AS_BYTES - HEADROOM:
                result["outcome"] = "incompatible"
                return result
            inherited_hard = result["inherited_as"][1]
            if inherited_hard != resource.RLIM_INFINITY and inherited_hard < AS_BYTES:
                result["outcome"] = "incompatible"
                return result
            resource.setrlimit(resource.RLIMIT_AS, (AS_BYTES, AS_BYTES))
        elif result["inherited_as"] != [-1, -1]:
            result["outcome"] = "incompatible"
            return result
        result["supervisor_as"] = list(resource.getrlimit(resource.RLIMIT_AS))
        if result["supervisor_as"] != ([AS_BYTES, AS_BYTES] if limited else [-1, -1]):
            raise ProbeFault
        kinds = {
            "baseline": ["baseline"],
            "control": ["private", "shared"],
            "private": ["private", "private"],
            "shared": ["shared", "shared"],
        }[case]
        for kind in kinds:
            process = subprocess.Popen(
                [sys.executable, "-I", "-B", __file__, "--member", kind],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            processes.append(process)
            ready = read_line(process.stdout, deadline)
            if set(ready) != {"phase", "pid", "ppid", "kind", "limits", "vm"}:
                raise ProbeFault
            if (ready["phase"], ready["pid"], ready["ppid"], ready["kind"]) != (
                "ready",
                process.pid,
                1,
                kind,
            ):
                raise ProbeFault
            if ready["limits"] != ([AS_BYTES, AS_BYTES] if limited else [-1, -1]):
                raise ProbeFault
            if ready["vm"]["threads"] != 1 or (
                limited and ready["vm"]["size"] > AS_BYTES - HEADROOM
            ):
                result["outcome"] = "incompatible"
                return result
        result["inventory"] = inventory({1, *(process.pid for process in processes)})
        for process in processes:
            send(process, b"GO\n")
        outcomes = []
        for process, kind in zip(processes, kinds, strict=True):
            held = read_line(process.stdout, deadline)
            if (held.get("pid"), held.get("ppid"), held.get("kind")) != (process.pid, 1, kind):
                raise ProbeFault
            outcomes.append(
                classify_member(
                    held,
                    limited=limited,
                    target=MIB if case == "baseline" else TARGET if case == "control" else None,
                )
            )
            result["members"].append(held)
        result["plateau_cgroup"] = cgroup_sample()
        result["outer_limit_exercised"] = (
            any(
                result["plateau_cgroup"]["events"][key] > result["startup_cgroup"]["events"][key]
                for key in ("max", "oom", "oom_kill")
            )
            or result["plateau_cgroup"]["peak"] > OUTER_BYTES
        )
        inventory(set(result["inventory"]))
        result["supervisor_plateau_vm"] = vm_status()
        for process in processes:
            send(process, b"ACK\n")
        for process in processes:
            if read_line(process.stdout, deadline) != {"phase": "released", "pid": process.pid}:
                raise ProbeFault
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            if process.returncode != 0:
                raise ProbeFault
        expected = (
            "normal" if case == "baseline" else "control_ok" if case == "control" else "imposed"
        )
        result["outcome"] = (
            expected
            if all(x == expected for x in outcomes)
            else "fail"
            if "fail" in outcomes
            else "inconclusive"
        )
    except Exception:
        result["outcome"] = "inconclusive"
    finally:
        result["cleanup_confirmed"] = reap(processes)
        if result["cleanup_confirmed"]:
            try:
                result["final_inventory"] = inventory({1})
                result["final_cgroup"] = cgroup_sample()
                if "startup_cgroup" in result:
                    result["outer_limit_exercised"] = (
                        result["outer_limit_exercised"]
                        or any(
                            result["final_cgroup"]["events"][key]
                            > result["startup_cgroup"]["events"][key]
                            for key in ("max", "oom", "oom_kill")
                        )
                        or result["final_cgroup"]["peak"] > OUTER_BYTES
                    )
            except Exception:
                result["cleanup_confirmed"] = False
        if not result["cleanup_confirmed"]:
            result["outcome"] = "inconclusive"
        if result["outer_limit_exercised"]:
            result["outcome"] = "inconclusive"
    return result


def selftest():
    assert decode_line(encode_line({"ok": True})) == {"ok": True}
    assert parse_status("VmSize: 1 kB\nVmPeak: 2 kB\nVmRSS: 1 kB\nThreads: 1\n")["peak"] == 2048
    return {"ok": True, "mode": "pure_selftest", "total_memory_contained": False}


def main():
    if sys.argv[1:] == ["--selftest"]:
        emit(selftest())
        return 0
    if sys.platform != "linux" or len(sys.argv) != 3:
        return 64
    option, value = sys.argv[1:]
    if option == "--member" and value in ("private", "shared", "baseline"):
        member(value)
        return 0
    if option == "--case" and value in ("baseline", "control", "private", "shared"):
        data = json.dumps(supervisor(value), sort_keys=True, separators=(",", ":")).encode("ascii")
        if len(data) > 65535 or os.write(1, data + b"\n") != len(data) + 1:
            raise ProbeFault
        return 0
    return 64


if __name__ == "__main__":
    try:
        exit_code = main()
    except BaseException:
        os.write(1, b'{"outcome":"inconclusive","collection_failed":true}\n')
        exit_code = 70
    raise SystemExit(exit_code)
