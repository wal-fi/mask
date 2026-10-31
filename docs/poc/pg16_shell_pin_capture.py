"""One public pin-cost capture, no effects on import; no operational PG attempt."""

import sys

if __name__ == "__main__" and not (
    sys.platform == "win32"
    and sys.version_info[:3] == (3, 11, 3)
    and sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.optimize == 0
    and len(sys.argv) == 1
):
    try:
        sys.stdout.write(
            '{"category":"RUNTIME","kind":"MASKGW_PG16_PIN_CAPTURE_V1","outcome":"NOT_PASSED"}\n'
        )
        sys.stdout.flush()
    except BaseException:
        try:
            sys.stdout.close()
        except BaseException:
            pass
    raise SystemExit(1)

from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import stat

REPO = Path(__file__).resolve().parents[2]
TASK = "3eb3f616e3f24f3e943bd2135b0007ba"
RELATIVE = "docs/poc/evidence/pg16-pin-cost-20261031-3eb3f616e3f2"
KIND = "MASKGW_PG16_PIN_CAPTURE_V1"
RESULT_KIND = "MASKGW_PG16_PIN_COST_V1"
HELPER = "docs/poc/pg16_shell_pin_cost.py"
HELPER_SHA = "0195b1e43353167b24f8e66606450e7beeea1e7d2daddcdeec9f6d95b9b12bd8"
PUBLIC_PINS = {
    "docs/poc/pg16_shell_run.py": "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657",
    "docs/poc/pg16_shell_host.py": "8c41605f5f44f355632b05167c6348fb09752472b6d59b26961604023a613018",
    "docs/poc/pg16_shell_delivery.py": "42f7e647c548c1947be61fb7425142ec0f00b7c0fd12ca7700ecece6d2f56188",
    "docs/poc/pg16_shell_profile.py": "8906e846a792d7aa01bc53da000e35815ba20a9ffee4a7fb8705b19b1b630912",
    "docs/poc/pg16_shell_cleanup_policy.py": "96e8a4c430c55e66c95c5c8f5a6fe5c9430fdf8389f418d4c4f7888ac39923b0",
    "docs/poc/pg16_shell_watchdog.py": "cf6634dae741c977a1ace3ca5bc4498fd6f41d8a349524f2cf1d666b4d84bb65",
    "docs/poc/pg16_public_volumes.py": "6e3827affcb1a02c00c365a54ecccae5d8e768c188d8232b699efa4c6ddad128",
    "docs/poc/pg16_public_emergency.py": "54cc8f68ffa7b46e0fbb66c3076cd80fabd849ac2d9284635c2b39253be30ebc",
    "docs/poc/w1_bootstrap_identity.py": "dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d",
    "docs/poc/pg16_shell_owner.py": "d671880078d6d1f30067400ae3d3169e17458c471467027835ba2be6897b6c8f",
    "docs/poc/pg16_shell_reader.py": "efe69a79a0743e49de602067d624c075cf5af8321a2654b7c2e87d023f498a85",
    "docs/poc/w1_bootstrap_channel.py": "e6ca9e606567289fa312049b071aa777e1764579813829747cb32df05d4ee87a",
    "docs/poc/pg16_public_profile.py": "fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277",
}
EXPECTED_SOURCES = sorted(PUBLIC_PINS.values())
MAX_REPORT = 16384


class Category(StrEnum):
    RUNTIME = "RUNTIME"
    SOURCE = "SOURCE"
    ROOT = "ROOT"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    PERSISTENCE = "PERSISTENCE"
    INTERRUPTED = "INTERRUPTED"
    INTERNAL = "INTERNAL"


class CaptureError(Exception):
    def __init__(self, category):
        self.category = category if type(category) is Category else Category.INTERNAL
        super().__init__(self.category.value)


def need(value, category):
    if not value:
        raise CaptureError(category) from None


def runtime():
    need(
        sys.platform == "win32"
        and sys.version_info[:3] == (3, 11, 3)
        and sys.flags.isolated == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.optimize == 0
        and len(sys.argv) == 1,
        Category.RUNTIME,
    )


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def regular(path, maximum=65536):
    info = path.lstat()
    need(
        stat.S_ISREG(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and info.st_size <= maximum,
        Category.SOURCE,
    )
    raw = path.read_bytes()
    need(len(raw) == info.st_size, Category.SOURCE)
    return raw


def pin_sources():
    for relative, digest in {HELPER: HELPER_SHA, **PUBLIC_PINS}.items():
        need(hashlib.sha256(regular(REPO / relative)).hexdigest() == digest, Category.SOURCE)


def directory(path):
    info = path.lstat()
    need(
        stat.S_ISDIR(info.st_mode)
        and not getattr(info, "st_file_attributes", 0) & 0x400
        and not path.is_symlink(),
        Category.ROOT,
    )


def create_root():
    need(
        type(RELATIVE) is str
        and RELATIVE == "docs/poc/evidence/pg16-pin-cost-20261031-3eb3f616e3f2",
        Category.ROOT,
    )
    parent = REPO
    directory(parent)
    for part in ("docs", "poc", "evidence"):
        parent = parent / part
        directory(parent)
    root = REPO / RELATIVE
    need(
        root.parent == parent and root != REPO / ".maskgw-pg16-pin-cost-not-materialized",
        Category.ROOT,
    )
    root.mkdir(mode=0o700, exist_ok=False)
    return root


def write_new(root, name, raw):
    need(
        name in ("invoked.json", "result.json", "capture.json")
        and type(raw) is bytes
        and 0 < len(raw) <= MAX_REPORT,
        Category.PERSISTENCE,
    )
    directory(root)
    with (root / name).open("xb") as stream:
        written = stream.write(raw)
        need(type(written) is int and written == len(raw), Category.PERSISTENCE)
        stream.flush()
        # File data only: no claim of directory fsync/durability on Windows.
        os.fsync(stream.fileno())


def load_helper(raw):
    need(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == HELPER_SHA, Category.SOURCE)
    path = REPO / HELPER
    namespace = {"__name__": "_pg16_pin_cost_for_capture", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def parse_report(raw, helper):
    failed, report = False, None

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError()
            value[key] = item
        return value

    try:
        need(
            type(raw) is bytes
            and 0 < len(raw) <= MAX_REPORT
            and raw.endswith(b"\n")
            and raw.count(b"\n") == 1,
            Category.OUTPUT_INVALID,
        )
        report = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
        need(canonical(report) == raw, Category.OUTPUT_INVALID)
        helper["validate"](report)
        need(report["kind"] == RESULT_KIND, Category.OUTPUT_INVALID)
        if report["outcome"] == "MEASURED":
            need(report["source_sha256"] == EXPECTED_SOURCES, Category.OUTPUT_INVALID)
    except KeyboardInterrupt:
        raise
    except Exception:
        failed = True
    if failed:
        raise CaptureError(Category.OUTPUT_INVALID) from None
    return report


def category(error):
    if type(error) is CaptureError and type(error.category) is Category:
        return error.category.value
    if type(error) is KeyboardInterrupt:
        return Category.INTERRUPTED.value
    if type(error) in (OSError, PermissionError, FileExistsError):
        return Category.PERSISTENCE.value
    return Category.INTERNAL.value


def summary(outcome, code, artifact=None):
    return {"kind": KIND, "task": TASK, "outcome": outcome, "category": code, "artifact": artifact}


def run():
    root, program_sha, report, raw = None, None, None, None
    try:
        runtime()
        program_sha = hashlib.sha256(regular(Path(__file__))).hexdigest()
        pin_sources()
        helper_raw = regular(REPO / HELPER)
        need(hashlib.sha256(helper_raw).hexdigest() == HELPER_SHA, Category.SOURCE)
        root = create_root()
        write_new(
            root,
            "invoked.json",
            canonical(
                {
                    "kind": "MASKGW_PG16_PIN_CAPTURE_INVOKED_V1",
                    "task": TASK,
                    "helper_sha256": HELPER_SHA,
                    "program_sha256": program_sha,
                }
            ),
        )
        try:
            helper = load_helper(helper_raw)
            raw = helper["collect"]()
            report = parse_report(raw, helper)
            pin_sources()
            need(
                hashlib.sha256(regular(Path(__file__))).hexdigest() == program_sha, Category.SOURCE
            )
        except BaseException as error:
            # A caller/transport failure is not attributed to the helper.
            report = {"kind": KIND, "outcome": "NOT_PASSED", "category": category(error)}
            raw = canonical(report)
        write_new(root, "result.json", raw)
        code = None if report["outcome"] == "MEASURED" else report["category"]
        artifact = RELATIVE + "/capture.json"
        capture = {
            "kind": KIND,
            "task": TASK,
            "artifact": artifact,
            "outcome": report["outcome"],
            "category": code,
            "helper_sha256": HELPER_SHA,
            "program_sha256": program_sha,
            "source_sha256": EXPECTED_SOURCES,
            "result_sha256": hashlib.sha256(raw).hexdigest(),
            "result_bytes": len(raw),
        }
        write_new(root, "capture.json", canonical(capture))
        # Verify both artifacts before announcing completion; no async boundary.
        need(
            regular(root / "result.json", MAX_REPORT) == raw
            and regular(root / "capture.json", MAX_REPORT) == canonical(capture),
            Category.PERSISTENCE,
        )
        return summary(report["outcome"], code, artifact), 0 if report[
            "outcome"
        ] == "MEASURED" else 1
    except BaseException as error:
        return summary("NOT_PASSED", category(error)), 1


if __name__ == "__main__":
    result, status = run()
    output = canonical(result)
    try:
        written = sys.stdout.buffer.write(output)
        if type(written) is not int or written != len(output):
            raise OSError("OUTPUT")
        sys.stdout.buffer.flush()
    except BaseException:
        try:
            sys.stdout.close()
        except BaseException:
            pass
        raise SystemExit(1) from None
    raise SystemExit(status)
