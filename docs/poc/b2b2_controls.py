"""B2-B2a shared-section diagnostic, NOT product or containment certification.

Copy beside the archived B2-A native.py/winjob.py into a new temporary root.
Only --controls spawns; --selftest does not import native helpers or spawn.
No database, network, gateway imports, secrets, installation or global kills.
Control subset only: no guardian-death, escape or private-pressure matrix.
Review this revision before --controls; a complete diagnostic is not a PASS
for total memory. Shared sections are anonymous, fixed size and never exported.
"""

import ctypes
import hashlib
import json
import mmap
import os
import shutil
import struct
import sys
import threading
import time
import uuid
from pathlib import Path

MIB = 1024 * 1024
CAP = 32 * MIB
RECORD = struct.Struct("<16q")
ROOT = Path(__file__).resolve().parent
SPECS = (
    ("empty", 0, "none", 0, CAP),
    ("normal", 2, "python", MIB, CAP),
    ("uncapped", 2, "python", 40 * MIB, None),
    ("shared_commit", 2, "commit", 40 * MIB, CAP),
    ("shared_reserve", 2, "reserve", 40 * MIB, CAP),
)
HELPER_HASHES = {
    "native.py": "92f8b3158eaa178972fbb7da3c694966a48ea1ac5647c35b333dc482fd97f797",
    "winjob.py": "b7183f44a630c7ccf65cb49922cd37d86760d6ec367cd3f168b283dc7d2de24c",
}


def verified_sources(directory=ROOT):
    hashes = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in (Path(__file__).name, *HELPER_HASHES)
    }
    if any(hashes[name] != expected for name, expected in HELPER_HASHES.items()):
        raise ValueError("historical helper hash mismatch")
    return hashes


def encoded(value, limit=64 * 1024):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(raw) > limit:
        raise ValueError("evidence size exceeded")
    return raw


def save(path, value, limit=64 * 1024):
    raw = encoded(value, limit)
    temporary = path.with_suffix(".pending")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def publish_record(state, values):
    RECORD.pack_into(state, 0, *values)


def helpers():
    verified_sources()  # before importing any copied helper, including in each child
    # Explicit, archived, trusted helpers; -I does not add the script folder.
    sys.path.insert(0, str(ROOT))
    import native
    import winjob

    if (
        Path(native.__file__).resolve() != ROOT / "native.py"
        or Path(winjob.__file__).resolve() != ROOT / "winjob.py"
    ):
        raise ValueError("unexpected helper module location")
    w = winjob.w
    winjob._sig(
        native.k.CreateFileMappingW,
        [w.HANDLE, ctypes.c_void_p, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR],
        w.HANDLE,
    )
    winjob._sig(
        native.k.MapViewOfFile,
        [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_size_t],
        ctypes.c_void_p,
    )
    winjob._sig(native.k.UnmapViewOfFile, [ctypes.c_void_p], w.BOOL)

    class Performance(ctypes.Structure):
        _fields_ = (
            [("cb", w.DWORD)]
            + [
                (name, ctypes.c_size_t)
                for name in (
                    "CommitTotal",
                    "CommitLimit",
                    "CommitPeak",
                    "PhysicalTotal",
                    "PhysicalAvailable",
                    "SystemCache",
                    "KernelTotal",
                    "KernelPaged",
                    "KernelNonpaged",
                    "PageSize",
                )
            ]
            + [(name, w.DWORD) for name in ("HandleCount", "ProcessCount", "ThreadCount")]
        )

    winjob._sig(winjob.psapi.GetPerformanceInfo, [ctypes.POINTER(Performance), w.DWORD], w.BOOL)

    def system_commit():
        info = Performance()
        info.cb = ctypes.sizeof(info)
        winjob._check(
            winjob.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb), "GetPerformanceInfo"
        )
        return {
            "bytes": info.CommitTotal * info.PageSize,
            "page_size": info.PageSize,
            "structure_bytes": info.cb,
        }

    native.system_commit = system_commit
    return native, winjob


def environment(directory):
    return {
        "SystemRoot": os.environ["SystemRoot"],
        "WINDIR": os.environ["SystemRoot"],
        "TEMP": str(directory),
        "TMP": str(directory),
    }


def child(tag, kind, amount):
    n, j = helpers()
    if kind not in {"python", "commit", "reserve"} or amount not in {MIB, 40 * MIB}:
        return 64
    state = mmap.mmap(-1, 4096, tagname=tag, access=mmap.ACCESS_WRITE)
    ready, ack = n.event(tag + "-ready"), n.event(tag + "-ack")
    reserve = bytearray(2 * MIB)
    held = None
    section = view = None
    failed = error = failure_kind = 0
    created = mapped = committed = touched = phase = 0
    in_any_job = int(n.in_job(n.k.GetCurrentProcess(), None))

    def checkpoint(stage):
        publish_record(
            state,
            (
                stage,
                amount,
                int(held is not None),
                failed,
                error,
                failure_kind,
                int(reserve is not None),
                time.monotonic_ns(),
                created,
                mapped,
                committed,
                touched,
                phase,
                in_any_job,
                0,
                stage,
            ),
        )
        n.signal(ready)
        if not j.wait(ack, 15000):
            os._exit(96)

    try:
        checkpoint(1)
        try:
            if kind == "python":
                phase = 1
                held = bytearray(amount)
            else:
                phase = 2
                flags = 0x08000000 if kind == "commit" else 0x04000000
                section = n.k.CreateFileMappingW(j.w.HANDLE(-1), None, 4 | flags, 0, amount, None)
                j._check(section, "CreateFileMappingW")
                created = 1
                phase = 3
                view = n.k.MapViewOfFile(section, 2, 0, 0, amount)  # FILE_MAP_WRITE
                j._check(view, "MapViewOfFile")
                mapped = 1
                if kind == "reserve":
                    phase = 4
                    j._check(n.k.VirtualAlloc(view, amount, 0x1000, 4), "commit section")
                committed = 1
                phase = 5
                for offset in range(0, amount, 4096):
                    ctypes.c_ubyte.from_address(view + offset).value = 1
                    touched += 1
                held = True  # all pages touched; retain section/view until parent ACK
        except (MemoryError, OSError) as exc:
            failed = 1
            failure_kind = 1 if isinstance(exc, MemoryError) else 2
            error = int(getattr(exc, "winerror", 0) or getattr(exc, "errno", 0) or 0)
            reserve = None  # bounded reporting headroom; peak remains measured
        checkpoint(2)
        return 0
    finally:
        if view:
            j._check(n.k.UnmapViewOfFile(view), "UnmapViewOfFile")
        if section:
            j.close(section)
        held = reserve = None
        state.close()
        j.close(ready)
        j.close(ack)


def fault(exc):
    # Numeric/category evidence only, no messages, arguments, environment or locals.
    return {
        "category": type(exc).__name__,
        "code": int(getattr(exc, "winerror", 0) or getattr(exc, "errno", 0) or 0),
    }


def run_case(spec, directory, base, n, j, live_jobs, ownership):
    name, count, kind, amount, cap = spec
    report = {"name": name, "members": count, "cap": cap, "complete": False}
    jobs, members = [], []
    deadline = time.monotonic() + 30

    def new_job():
        job = j.create_job(process_limit=cap, job_limit=None, active_processes=1)
        with ownership:
            live_jobs.append(job)
        jobs.append(job)
        return job

    def remaining_ms():
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError("case deadline")
        return remaining

    def checkpoint(stage):
        samples = []
        # Every child remains blocked until all samples have been collected.
        for member in members:
            if not j.wait(member["ready"], remaining_ms()):
                raise TimeoutError("checkpoint deadline")
            info, job = member["process"], member["job"]
            record = RECORD.unpack_from(member["map"], 0)
            if record[0] != stage or record[1] != amount or j.wait(info.hProcess, 0):
                raise ValueError("missing live checkpoint")
            listed = j.job_members(job)
            accounting = j.query_accounting(job)
            if len(listed) != 1 or listed[0]["pid"] != info.dwProcessId:
                raise ValueError("member inventory mismatch")
            if accounting.ActiveProcesses != 1 or not n.in_job(info.hProcess, job):
                raise ValueError("membership mismatch")
            extended = j.query_extended(job)
            wanted = j.LIMIT_ACTIVE_PROCESS | j.LIMIT_KILL_ON_JOB_CLOSE
            if cap is not None:
                wanted |= j.LIMIT_PROCESS_MEMORY
            flags = extended.BasicLimitInformation.LimitFlags
            if (
                flags & wanted != wanted
                or flags & (j.BREAKAWAY_FLAGS | j.LIMIT_JOB_MEMORY)
                or extended.BasicLimitInformation.ActiveProcessLimit != 1
                or (cap is not None and extended.ProcessMemoryLimit != cap)
                or (cap is None and flags & j.LIMIT_PROCESS_MEMORY)
            ):
                raise ValueError("effective config mismatch")
            samples.append(
                {
                    "pid": info.dwProcessId,
                    "created": member["created"],
                    "state": record,
                    "memory": n.memory(info.hProcess),
                    "job_peak": extended.PeakJobMemoryUsed,
                    "process_peak": extended.PeakProcessMemoryUsed,
                    "flags": flags,
                }
            )
        return samples

    try:
        if name == "empty":
            job = new_job()
            if j.job_members(job) or j.query_accounting(job).ActiveProcesses:
                raise ValueError("empty control has member")
            report["assertions"] = True
        else:
            for _ in range(count):
                job = new_job()
                tag = "Local\\maskgw-b2b2-" + uuid.uuid4().hex
                member = {"job": job}
                members.append(member)  # cleanup owns every partially created resource
                member["map"] = mmap.mmap(-1, 4096, tagname=tag, access=mmap.ACCESS_WRITE)
                member["ready"] = n.event(tag + "-ready", create=True)
                member["ack"] = n.event(tag + "-ack", create=True)
                process = n.start_in_job(
                    job,
                    [
                        base,
                        "-I",
                        "-S",
                        "-B",
                        str(Path(__file__).resolve()),
                        "--child",
                        tag,
                        kind,
                        str(amount),
                    ],
                    str(directory),
                    environment(directory),
                )
                member["process"] = process
                member["created"] = j.creation_time(process.hProcess)
                if os.path.normcase(n.image(process.hProcess)) != os.path.normcase(base):
                    raise ValueError("unexpected image")
                j._check(n.k.ResumeThread(process.hThread) == 1, "ResumeThread")
            report["baseline"] = checkpoint(1)
            report["system_commit_baseline_noisy"] = n.system_commit()
            for member in members:
                n.signal(member["ack"])
            report["held"] = checkpoint(2)
            report["system_commit_held_noisy"] = n.system_commit()
            report["sum_private_held"] = sum(x["memory"]["private"] for x in report["held"])
            report["sum_individual_peaks_not_simultaneous"] = sum(
                x["memory"]["peak_commit"] for x in report["held"]
            )
            report["individual_peaks_within_cap"] = cap is None or all(
                max(x["memory"]["peak_commit"], x["process_peak"]) <= cap for x in report["held"]
            )
            if kind in {"commit", "reserve"}:
                report["shared_mapping_succeeded"] = sum(x["state"][2] for x in report["held"])
                coverage = []
                for sample in report["held"]:
                    record = sample["state"]
                    if (
                        record[2] == 1
                        and record[3] == 0
                        and record[8:11] == (1, 1, 1)
                        and record[11] == amount // 4096
                        and cap < amount
                    ):
                        outcome = "gap_observed"
                    elif record[3] == 1 and record[5] in {1, 2} and record[12] in {2, 3, 4, 5}:
                        outcome = "refused_observed_cause_not_attributed"
                    else:
                        outcome = "inconclusive"
                    coverage.append(
                        {
                            "pid": sample["pid"],
                            "coverage": outcome,
                            "phase": record[12],
                            "code": record[4],
                        }
                    )
                report["coverage"] = coverage
                report["total_memory_contained"] = False  # never certify from this diagnostic
                report["assertions"] = report["individual_peaks_within_cap"] and all(
                    item["coverage"] != "inconclusive" for item in coverage
                )
                report["total_memory_claim"] = "not_proved_by_this_control"
            else:
                report["assertions"] = (
                    all(x["state"][2] == 1 and x["state"][3] == 0 for x in report["held"])
                    and report["individual_peaks_within_cap"]
                )
            for member in members:
                n.signal(member["ack"])
            for member in members:
                if not j.wait(member["process"].hProcess, remaining_ms()):
                    raise TimeoutError("normal exit deadline")
                code = j.w.DWORD()
                j._check(
                    n.k.GetExitCodeProcess(
                        member["process"].hProcess,
                        ctypes.byref(code),
                    ),
                    "GetExitCodeProcess",
                )
                member["exit_code"] = int(code.value)
                if code.value != 0:
                    raise ValueError("unexpected child exit")
            report["exit_codes"] = [member["exit_code"] for member in members]
        report["complete"] = True
    except Exception as exc:
        report["failure"] = fault(exc)
    finally:
        errors = []

        def cleanup(label, operation):
            try:
                operation()
            except Exception as exc:
                errors.append({"at": label, **fault(exc)})

        for job in jobs:
            cleanup(
                "terminate", lambda job=job: j._check(n.k.TerminateJobObject(job, 97), "terminate")
            )
        for member in members:
            process = member.get("process")
            if process:
                cleanup(
                    "wait", lambda process=process: j._check(j.wait(process.hProcess, 3000), "wait")
                )
                cleanup("thread_handle", lambda process=process: j.close(process.hThread))
                cleanup("process_handle", lambda process=process: j.close(process.hProcess))
            for key in ("ready", "ack"):
                if key in member:
                    cleanup(key, lambda member=member, key=key: j.close(member[key]))
            if "map" in member:
                cleanup("map", member["map"].close)
        for job in jobs:
            cleanup(
                "empty",
                lambda job=job: j._check(
                    not j.job_members(job) and j.query_accounting(job).ActiveProcesses == 0,
                    "job empty",
                ),
            )
            # Watchdog and main cannot close/kill a recycled handle concurrently.
            with ownership:
                cleanup("job_handle", lambda job=job: j.close(job))
                live_jobs.remove(job)
        report["cleanup"] = {"confirmed": not errors, "errors": errors}
    return report


def controls():
    hashes = verified_sources()
    n, j = helpers()
    if (
        sys.version_info[:3] != (3, 11, 3)
        or ctypes.sizeof(ctypes.c_void_p) != 8
        or ctypes.sizeof(j.EXTENDED_LIMIT) != 144
        or n.system_info()["page_size"] != 4096
    ):
        raise RuntimeError("unsupported diagnostic profile")
    status = j.memory_status()
    if status["avail_phys"] < 2 * 1024 * MIB or status["avail_commit"] < 4 * 1024 * MIB:
        raise RuntimeError("preflight insufficient")
    batch = ROOT / ("controls-" + uuid.uuid4().hex)
    batch.mkdir()
    sources = batch / "sources"
    sources.mkdir()
    for name in (Path(__file__).name, "native.py", "winjob.py"):
        source = ROOT / name
        shutil.copyfile(source, sources / name)
    if verified_sources(sources) != hashes:
        raise ValueError("archived source mismatch before cases")
    summary = {
        "profile": "B2-B2a_shared_section_diagnostic_only",
        "python": sys.version.split()[0],
        "windows": sys.getwindowsversion().build,
        "preflight": status,
        "host_job_inherited": n.in_job(n.k.GetCurrentProcess(), None),
        "source_hashes": hashes,
        "state_fields": [
            "stage",
            "amount",
            "held",
            "failed",
            "error",
            "failure_kind",
            "emergency_held",
            "time_ns",
            "created",
            "mapped",
            "committed",
            "pages_touched",
            "phase",
            "in_any_job",
            "reserved2",
            "sequence",
        ],
        "control_map_bytes_per_member": 4096,
        "planned": [x[0] for x in SPECS],
        "cases": [],
        "complete": False,
        "production_gate_passed": False,
    }
    save(batch / "summary.json", summary)
    jobs, ownership = [], threading.Lock()

    def emergency():
        with ownership:
            for job in jobs:
                n.k.TerminateJobObject(job, 98)
        os._exit(98)  # closing own last job handles is the emergency fallback

    timer = threading.Timer(120, emergency)
    timer.start()
    try:
        for spec in SPECS:
            report = run_case(spec, batch, sys._base_executable, n, j, jobs, ownership)
            save(batch / (spec[0] + ".json"), report)
            summary["cases"].append(report)
            save(batch / "summary.json", summary)
            if (
                not report["complete"]
                or not report["cleanup"]["confirmed"]
                or report.get("assertions") is False
            ):
                break
        summary["complete"] = len(summary["cases"]) == len(SPECS) and all(
            x["complete"] and x["cleanup"]["confirmed"] and x.get("assertions") is not False
            for x in summary["cases"]
        )
        summary["source_integrity_after"] = (
            verified_sources() == hashes and verified_sources(sources) == hashes
        )
        summary["complete"] = summary["complete"] and summary["source_integrity_after"]
        save(batch / "summary.json", summary)
    finally:
        timer.cancel()
        timer.join()
    print(
        json.dumps(
            {"batch": str(batch), "complete": summary["complete"], "production_gate_passed": False}
        ),
        flush=True,
    )
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        assert RECORD.size == 128
        assert len(SPECS) == 5
        buffer = bytearray(4096)
        values = (2, 40 * MIB, 0, 1, 1455, 2, 0, 123, 1, 1, 0, 0, 4, 1, 0, 2)
        publish_record(buffer, values)
        assert RECORD.unpack_from(buffer, 0) == values
        assert buffer[RECORD.size :] == bytes(4096 - RECORD.size)
        assert len(encoded({"complete": False})) < 4096
        try:
            encoded({"too_large": "x" * 20}, 8)
        except ValueError:
            pass
        else:
            raise AssertionError("evidence bound not enforced")
        print("selftest: PASS (no native helpers, jobs, children or files)")
    elif len(sys.argv) == 5 and sys.argv[1] == "--child":
        raise SystemExit(child(sys.argv[2], sys.argv[3], int(sys.argv[4])))
    elif sys.argv[1:] == ["--controls"]:
        raise SystemExit(controls())
    else:
        raise SystemExit(64)
