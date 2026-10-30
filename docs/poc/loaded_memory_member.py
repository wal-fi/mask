"""Lab member pieces only. No entrypoint, parent, product caller or OS quota proof."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from functools import wraps

MIB = 1024 * 1024
STEP, TARGET, PAGE, RESERVE = 4 * MIB, 40 * MIB, 4096, 2 * MIB
AS_BYTES = 128 * MIB
STATUS_MAX, LINE_MAX = 65536, 1024


class MemberFault(Exception):
    def __init__(self):
        super().__init__("DIAGNOSTIC")


def closed(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            pass
        self.failed = True
        raise MemberFault()  # Outside except: no raw exception chain.

    return guarded


def valid_sample(vm, limits):
    if (
        type(vm) is not dict
        or any(type(key) is not str for key in vm)
        or set(vm) != {"size", "peak", "rss", "threads"}
        or any(type(value) is not int or not 0 <= value <= 1 << 50 for value in vm.values())
        or vm["threads"] != 1
        or not 0 < vm["size"] <= vm["peak"]
        or vm["rss"] > vm["size"]
        or type(limits) is not list
        or len(limits) != 2
        or any(type(value) is not int or not -1 <= value <= 1 << 50 for value in limits)
    ):
        raise MemberFault()


def parse_status(scratch, length):
    """Bounded parsing in the existing scratch; never duplicate the whole proc file."""
    if (
        type(length) is not int
        or not 1 <= length <= STATUS_MAX
        or length > len(scratch)
        or scratch[length - 1] != 10
    ):
        raise MemberFault()
    keys = (
        (b"VmSize:", "size"),
        (b"VmPeak:", "peak"),
        (b"VmRSS:", "rss"),
        (b"Threads:", "threads"),
    )
    result, start = {}, 0
    while start < length:
        end = start
        while end < length and scratch[end] != 10:
            end += 1
        for label, name in keys:
            if scratch[start : start + len(label)] != label:
                continue
            if name in result:
                raise MemberFault()
            index, number, digits = start + len(label), 0, 0
            while index < end and scratch[index] in (9, 32):
                index += 1
            while index < end and 48 <= scratch[index] <= 57:
                number, digits = number * 10 + scratch[index] - 48, digits + 1
                if digits > 16 or number > 1 << 50:
                    raise MemberFault()
                index += 1
            while index < end and scratch[index] in (9, 32):
                index += 1
            suffix = b"" if name == "threads" else b"kB"
            if not digits or scratch[index:end] != suffix:
                raise MemberFault()
            result[name] = number if name == "threads" else number * 1024
        start = end + 1
    valid_sample(result, [-1, -1])
    return result


class FixedHeld:
    """Small canonical report in a preallocated buffer, not an OOM recovery guarantee."""

    def __init__(self):
        self.buffer = bytearray(LINE_MAX)
        self.view, self.index = memoryview(self.buffer), 0

    def _raw(self, value):
        end = self.index + len(value)
        if end > len(self.buffer):
            raise MemberFault()
        self.view[self.index : end] = value
        self.index = end

    def _number(self, value):
        if type(value) is not int or not -1 <= value <= 1 << 50:
            raise MemberFault()
        if value < 0:
            self._raw(b"-")
            value = -value
        start = self.index
        while True:
            if self.index >= len(self.buffer):
                raise MemberFault()
            self.buffer[self.index] = 48 + value % 10
            self.index += 1
            value //= 10
            if not value:
                break
        left, right = start, self.index - 1
        while left < right:
            self.buffer[left], self.buffer[right] = self.buffer[right], self.buffer[left]
            left, right = left + 1, right - 1

    def encode(self, kind, limits, vm, blocks, failure, number):
        valid_sample(vm, limits)
        if (
            kind not in ("private", "shared")
            or type(blocks) is not int
            or not 0 <= blocks <= 10
            or failure not in ("NONE", "MEMORY", "ENOMEM", "OTHER")
            or (number is not None and (type(number) is not int or not 1 <= number <= 4095))
            or (failure in ("NONE", "MEMORY") and number is not None)
            or (failure == "ENOMEM" and number != 12)
            or (failure != "NONE" and blocks == 10)
        ):
            raise MemberFault()
        self.index = 0
        self._raw(b'{"phase":"held","kind":')
        self._raw(b'"private"' if kind == "private" else b'"shared"')
        self._raw(b',"limits":[')
        self._number(limits[0])
        self._raw(b",")
        self._number(limits[1])
        self._raw(b'],"vm":{')
        for label, key in (
            (b'"size":', "size"),
            (b',"peak":', "peak"),
            (b',"rss":', "rss"),
            (b',"threads":', "threads"),
        ):
            self._raw(label)
            self._number(vm[key])
        for label, value in (
            (b'},"accepted_bytes":', blocks * STEP),
            (b',"touched_pages":', blocks * (STEP // PAGE)),
            (b',"blocks":', blocks),
        ):
            self._raw(label)
            self._number(value)
        self._raw(b',"failure":')
        self._raw(
            {"NONE": b'"NONE"', "MEMORY": b'"MEMORY"', "ENOMEM": b'"ENOMEM"', "OTHER": b'"OTHER"'}[
                failure
            ]
        )
        self._raw(b',"errno":')
        if number is None:
            self._raw(b"null")
        else:
            self._number(number)
        self._raw(b"}\n")
        return self.view[: self.index]


class LinuxIO:
    """Own proc fd and nonblocking stdio; real construction only inside gated child."""

    @classmethod
    def from_linux(cls, *, deadline):
        if (
            sys.platform != "linux"
            or not sys.flags.isolated
            or not sys.flags.no_site
            or os.getpid() < 2
            or os.getppid() != 1
        ):
            raise MemberFault()
        import mmap
        import resource
        import select

        return cls._with_apis(
            deadline=deadline,
            os_api=os,
            mmap_api=mmap,
            resource_api=resource,
            select_fn=select.select,
            clock=time.monotonic,
            pid=os.getpid(),
            ppid=os.getppid(),
        )

    @classmethod
    def _with_apis(cls, *, deadline, os_api, mmap_api, resource_api, select_fn, clock, pid, ppid):
        """Trusted dependency seam for tests, never a client-selected backend."""
        self = cls.__new__(cls)
        self.os, self.mmap, self.resource = os_api, mmap_api, resource_api
        self.select, self.clock, self.deadline = select_fn, clock, deadline
        self.pid, self.ppid, self.failed = pid, ppid, False
        self.fd, self.old_flags, self.last_time = None, {}, 0
        try:
            self.scratch = bytearray(STATUS_MAX + 1)
            self.scratch_view = memoryview(self.scratch)
            self.check()
            if deadline - self.last_time > 20:
                raise MemberFault()
            self.fd = self.os.open("/proc/self/status", self.os.O_RDONLY | self.os.O_CLOEXEC)
            for fd in (0, 1):
                self.old_flags[fd] = self.os.get_blocking(fd)
                self.os.set_blocking(fd, False)
            return self
        except BaseException:
            self.close()
        raise MemberFault()

    @closed
    def check(self):
        now = self.clock()
        if (
            type(now) not in (int, float)
            or type(self.deadline) not in (int, float)
            or not math.isfinite(now)
            or not math.isfinite(self.deadline)
            or not 0 <= self.last_time <= now < self.deadline <= 1 << 50
        ):
            raise MemberFault()
        self.last_time = now
        return self.deadline - now

    def _wait(self, *, writing):
        while True:
            remaining = self.check()
            try:
                reads, writes, _errors = self.select(
                    [] if writing else [0], [1] if writing else [], [], remaining
                )
            except InterruptedError:
                continue
            if writes if writing else reads:
                self.check()
                return
            raise MemberFault()

    @closed
    def write(self, raw):
        if len(raw) > 4096 or not raw or raw[-1] != 10:
            raise MemberFault()
        view, sent = memoryview(raw), 0
        while sent < len(view):
            self._wait(writing=True)
            try:
                count = self.os.write(1, view[sent:])
            except (BlockingIOError, InterruptedError):
                continue
            if type(count) is not int or not 0 < count <= len(view) - sent:
                raise MemberFault()
            sent += count
        self.check()

    @closed
    def emit(self, event):
        self.write(
            json.dumps(event, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"
        )

    @closed
    def command(self, expected):
        if expected not in (
            b"GO_IMPORTS\n",
            b"PRESSURE_PRIVATE\n",
            b"PRESSURE_SHARED\n",
            b"RELEASE_PRIVATE\n",
            b"RELEASE_SHARED\n",
            b"FINISH\n",
        ):
            raise MemberFault()
        raw = bytearray()
        while b"\n" not in raw:
            self._wait(writing=False)
            try:
                chunk = self.os.read(0, 32 - len(raw))
            except (BlockingIOError, InterruptedError):
                continue
            if not chunk:
                raise MemberFault()
            raw.extend(chunk)
            if len(raw) >= 32:
                raise MemberFault()
        if raw != expected:
            raise MemberFault()
        self.check()

    @closed
    def sample(self):
        self.check()
        self.os.lseek(self.fd, 0, self.os.SEEK_SET)
        length = self.os.readv(self.fd, [self.scratch_view])
        vm = parse_status(self.scratch_view, length)
        limits = list(self.resource.getrlimit(self.resource.RLIMIT_AS))
        valid_sample(vm, limits)
        self.check()
        return vm, limits

    def allocate_reserve(self):
        return self.mmap.mmap(
            -1,
            RESERVE,
            flags=self.mmap.MAP_PRIVATE | self.mmap.MAP_ANONYMOUS,
            prot=self.mmap.PROT_READ | self.mmap.PROT_WRITE,
        )

    def allocate(self, kind):
        if kind == "private":
            return bytearray(STEP)
        if kind != "shared":
            raise MemberFault()
        return self.mmap.mmap(
            -1,
            STEP,
            flags=self.mmap.MAP_SHARED | self.mmap.MAP_ANONYMOUS,
            prot=self.mmap.PROT_READ | self.mmap.PROT_WRITE,
        )

    def free(self, block):
        if type(block) is not bytearray:
            block.close()

    def close(self):
        good = True
        if self.fd is not None:
            try:
                self.os.close(self.fd)
                self.fd = None
            except BaseException:
                good = False
        for fd, blocking in self.old_flags.items():
            try:
                self.os.set_blocking(fd, blocking)
            except BaseException:
                good = False
        self.old_flags.clear()
        return good


def run_member(case, io, imports):
    """Trusted callback imports; never receives the parent's inventory digest."""
    slots, reserve, code, block = None, None, 77, None
    try:
        if type(case) is not str or case not in ("control", "private", "shared"):
            raise MemberFault()
        expected = [-1, -1] if case == "control" else [AS_BYTES, AS_BYTES]
        slots = [None] * 10
        pattern, reserve_pattern, writer = (
            b"x" * (STEP // PAGE),
            b"x" * (RESERVE // PAGE),
            FixedHeld(),
        )
        io.check()
        reserve = io.allocate_reserve()
        reserve[0::PAGE] = reserve_pattern
        vm, limits = io.sample()
        valid_sample(vm, limits)
        if limits != expected:
            raise MemberFault()
        io.emit({"phase": "ready", "pid": io.pid, "ppid": io.ppid, "limits": limits, "vm": vm})
        io.command(b"GO_IMPORTS\n")
        result = imports(io)
        if io.failed or type(result) is not int or result not in (0, 72, 73, 74, 75, 76):
            raise MemberFault()
        code = result
        if result == 0:
            code = 77
            vm, limits = io.sample()
            valid_sample(vm, limits)
            if limits != expected:
                raise MemberFault()
            io.emit({"phase": "loaded", "limits": limits, "vm": vm})
            kinds = ("private", "shared") if case == "control" else (case,)
            for kind in kinds:
                io.command(b"PRESSURE_PRIVATE\n" if kind == "private" else b"PRESSURE_SHARED\n")
                _vm, limits = io.sample()
                if limits != expected:
                    raise MemberFault()
                blocks, failure, number = 0, "NONE", None
                while blocks < 10:
                    io.check()  # Clock/touch/sample exceptions are never allocator refusals.
                    try:
                        block = io.allocate(kind)
                    except MemoryError:
                        failure = "MEMORY"
                    except OSError as error:
                        number = (
                            error.errno
                            if type(error.errno) is int and 1 <= error.errno <= 4095
                            else None
                        )
                        failure = "ENOMEM" if number == 12 else "OTHER"
                    if failure != "NONE":
                        break
                    slots[blocks], block = block, None  # Own before touching.
                    slots[blocks][0::PAGE] = pattern
                    blocks += 1
                vm, limits = io.sample()  # Reserve and payload still retained here.
                valid_sample(vm, limits)
                if limits != expected:
                    raise MemberFault()
                if case != "control" and failure != "NONE":
                    io.free(reserve)
                    reserve = None
                io.write(writer.encode(kind, limits, vm, blocks, failure, number))
                io.command(b"RELEASE_PRIVATE\n" if kind == "private" else b"RELEASE_SHARED\n")
                good = True
                for index in range(10):
                    if slots[index] is not None:
                        try:
                            io.free(slots[index])
                        except BaseException:
                            good = False
                        slots[index] = None
                if not good:
                    raise MemberFault()
                io.emit({"phase": "released", "kind": kind})
            io.command(b"FINISH\n")
            io.emit({"phase": "done"})
            code = 0
    except BaseException:
        code = 77
    finally:
        block = None
        if slots is not None:
            for index in range(10):
                if slots[index] is not None:
                    try:
                        io.free(slots[index])
                    except BaseException:
                        code = 77
                    slots[index] = None
        if reserve is not None:
            try:
                io.free(reserve)
            except BaseException:
                code = 77
            reserve = None
        try:
            if io.close() is not True or io.failed:
                code = 77
        except BaseException:
            code = 77
    return code
