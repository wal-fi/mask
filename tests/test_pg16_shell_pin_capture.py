"""Capture/publication boundary fakes. No actual binary/config timing or processes."""

import builtins
import hashlib
import io
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_shell_pin_capture.py"))


def measured(module: Any) -> Any:
    modes = ("NORMAL", "CLEANUP", "FINAL0", "FINAL23")
    return {
        "kind": module["RESULT_KIND"],
        "outcome": "MEASURED",
        "cycles": 5,
        "sample_count": 20,
        "samples": [
            {"cycle": cycle, "mode": mode, "ns": 1} for cycle in range(5) for mode in modes
        ],
        "stats": {mode: {"observed_max_ns": 1, "median_ns": 1} for mode in modes},
        "construction": {
            "builder_ns": 1,
            "host_context0_ns": 1,
            "host_context23_ns": 1,
            "monitors23_ns": 1,
        },
        "source_sha256": list(module["EXPECTED_SOURCES"]),
        "host_counts": [0, 23],
    }


@pytest.fixture
def helper(module: Any) -> Any:
    real = runpy.run_path(str(REPO / module["HELPER"]))
    return {"validate": real["validate"]}


@pytest.fixture
def fake(module: Any, helper: Any, tmp_path: Any, monkeypatch: Any) -> Any:
    parent = tmp_path / "docs/poc/evidence"
    parent.mkdir(parents=True)
    (tmp_path / module["HELPER"]).write_bytes((REPO / module["HELPER"]).read_bytes())
    state = SimpleNamespace(
        payload=module["canonical"](measured(module)), calls=[], fail_collect=None
    )

    def collect() -> bytes:
        state.calls.append("collect")
        root = tmp_path / module["RELATIVE"]
        assert (root / "invoked.json").is_file()
        assert not (root / "result.json").exists()
        if state.fail_collect is not None:
            raise state.fail_collect
        assert type(state.payload) is bytes
        return state.payload

    def pins() -> None:
        state.calls.append("pins")

    monkeypatch.setitem(module["run"].__globals__, "REPO", tmp_path)
    monkeypatch.setitem(module["run"].__globals__, "runtime", lambda: None)
    monkeypatch.setitem(module["run"].__globals__, "pin_sources", pins)
    monkeypatch.setitem(
        module["run"].__globals__, "load_helper", lambda _raw: {**helper, "collect": collect}
    )
    return state


def test_complete_capture_only_after_invoked_and_reparsed_public_report(
    module: Any, fake: Any
) -> None:
    result, status = module["run"]()
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    assert status == 0 and result["outcome"] == "MEASURED"
    assert fake.calls == ["pins", "collect", "pins"]
    assert {path.name for path in root.iterdir()} == {"invoked.json", "result.json", "capture.json"}
    raw = (root / "result.json").read_bytes()
    capture = json.loads((root / "capture.json").read_bytes())
    assert raw == fake.payload and capture["result_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (
        capture["result_bytes"] == len(raw)
        and capture["source_sha256"] == module["EXPECTED_SOURCES"]
    )
    assert capture["artifact"] == result["artifact"] == module["RELATIVE"] + "/capture.json"
    assert str(root).encode() not in (root / "capture.json").read_bytes()


def test_same_directory_refused_without_second_measurement_or_overwrite(
    module: Any, fake: Any
) -> None:
    assert module["run"]()[1] == 0
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    result, status = module["run"]()
    assert status == 1 and result["artifact"] is None
    assert fake.calls.count("collect") == 1
    assert before == {path.name: path.read_bytes() for path in root.iterdir()}


@pytest.mark.parametrize(
    "bad",
    [
        "duplicate",
        "nan",
        "infinity",
        "noncanonical",
        "unknown",
        "wrong-sha",
        "private-sha",
        "nonascii",
        "multiline",
        "oversize",
    ],
)
def test_invalid_payload_never_written_or_hashed_as_evidence(
    module: Any, fake: Any, bad: str
) -> None:
    report = measured(module)
    if bad == "duplicate":
        raw = b'{"kind":"PRIVATE_TOKEN","kind":"MASKGW_PG16_PIN_COST_V1"}\n'
    elif bad in ("nan", "infinity"):
        raw = b'{"private":' + (b"NaN" if bad == "nan" else b"Infinity") + b"}\n"
    elif bad == "noncanonical":
        raw = json.dumps(report).encode() + b"\n"
    elif bad == "unknown":
        report["private"] = "PRIVATE_TOKEN"
        raw = module["canonical"](report)
    elif bad in ("wrong-sha", "private-sha"):
        report["source_sha256"] = sorted(
            ["f" * 64] if bad == "private-sha" else report["source_sha256"][:-1]
        )
        raw = module["canonical"](report)
    elif bad == "nonascii":
        raw = b"\xffPRIVATE_TOKEN\n"
    elif bad == "multiline":
        raw = fake.payload + b"\n"
    else:
        raw = b"PRIVATE_TOKEN" * 2000 + b"\n"
    fake.payload = raw
    result, status = module["run"]()
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    contents = b"".join(path.read_bytes() for path in root.iterdir())
    assert status == 1 and result["category"] == "OUTPUT_INVALID"
    assert b"PRIVATE_TOKEN" not in contents
    stored = json.loads((root / "result.json").read_bytes())
    assert stored == {"kind": module["KIND"], "outcome": "NOT_PASSED", "category": "OUTPUT_INVALID"}
    assert b"MEASURED" not in (root / "result.json").read_bytes()


def test_helper_closed_failure_preserved_without_partial_statistics(module: Any, fake: Any) -> None:
    fake.payload = module["canonical"](
        {"kind": module["RESULT_KIND"], "outcome": "NOT_PASSED", "category": "PIN"}
    )
    result, status = module["run"]()
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    assert status == 1 and result["category"] == "PIN"
    assert (root / "result.json").read_bytes() == fake.payload
    assert fake.calls == ["pins", "collect", "pins"]


def test_interrupt_is_recorded_without_retry(module: Any, fake: Any) -> None:
    fake.fail_collect = KeyboardInterrupt()
    result, status = module["run"]()
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    assert status == 1 and result["category"] == "INTERRUPTED"
    assert json.loads((root / "result.json").read_bytes())["category"] == "INTERRUPTED"
    assert fake.calls.count("collect") == 1


def test_post_source_change_discards_completed_samples(
    module: Any, fake: Any, monkeypatch: Any
) -> None:
    assert fake.calls == []
    count = 0

    def pins() -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise module["CaptureError"](module["Category"].SOURCE)

    monkeypatch.setitem(module["run"].__globals__, "pin_sources", pins)
    result, status = module["run"]()
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    assert status == 1 and result["category"] == "SOURCE"
    assert "samples" not in json.loads((root / "result.json").read_bytes())


@pytest.mark.parametrize("name", ["invoked.json", "result.json", "capture.json"])
def test_persistence_failure_never_announces_complete_capture(
    module: Any, fake: Any, monkeypatch: Any, name: str
) -> None:
    original = module["write_new"]

    def fail(root: Any, selected: str, raw: bytes) -> None:
        if selected == name:
            raise OSError("PRIVATE_STORAGE_PATH")
        original(root, selected, raw)

    monkeypatch.setitem(module["run"].__globals__, "write_new", fail)
    result, status = module["run"]()
    assert status == 1 and result["artifact"] is None
    assert "PRIVATE" not in module["canonical"](result).decode()
    assert fake.calls.count("collect") == (0 if name == "invoked.json" else 1)


def test_loader_uses_real_helper_file_name_and_no_main_or_capture(module: Any) -> None:
    raw = (REPO / module["HELPER"]).read_bytes()
    helper = module["load_helper"](raw)
    assert helper["__name__"] != "__main__"
    assert Path(helper["__file__"]) == REPO / module["HELPER"]
    assert helper["REPO"] == REPO
    assert helper["validate"] and helper["collect"]
    assert "H" not in helper and "output" not in helper


def test_source_pin_matches_exact_helper_and_thirteen_public_files(module: Any) -> None:
    assert len(module["PUBLIC_PINS"]) == len(module["EXPECTED_SOURCES"]) == 13
    assert len(set(module["EXPECTED_SOURCES"])) == 13
    module["pin_sources"]()  # public repo sources only, no binaries/configuration


def test_reparse_parent_or_logical_root_refused(module: Any, fake: Any, monkeypatch: Any) -> None:
    path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=0o040700, st_file_attributes=0x400),
        is_symlink=lambda: False,
    )
    with pytest.raises(module["CaptureError"], match="ROOT"):
        module["directory"](path)
    monkeypatch.setitem(
        module["run"].__globals__, "RELATIVE", ".maskgw-pg16-pin-cost-not-materialized"
    )
    result, status = module["run"]()
    assert status == 1 and result["category"] == "ROOT" and not fake.calls.count("collect")


def test_duplicate_parser_error_has_no_original_exception_context(module: Any, helper: Any) -> None:
    with pytest.raises(module["CaptureError"], match="OUTPUT_INVALID") as caught:
        module["parse_report"](b'{"private":"PRIVATE_TOKEN","private":2}\n', helper)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("bad", ["platform", "version", "isolated", "bytecode", "optimize", "argv"])
def test_runtime_refusal_before_any_nonbuiltin_import(module: Any, bad: str) -> None:
    output = io.StringIO()
    fake_sys = SimpleNamespace(
        platform="win32",
        version_info=(3, 11, 3),
        flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0),
        argv=["PUBLIC_SCRIPT"],
        stdout=output,
    )
    if bad == "platform":
        fake_sys.platform = "linux"
    elif bad == "version":
        fake_sys.version_info = (3, 11, 4)
    elif bad == "argv":
        fake_sys.argv.append("PRIVATE_ARGUMENT")
    else:
        setattr(
            fake_sys.flags,
            "dont_write_bytecode" if bad == "bytecode" else bad,
            1 if bad == "optimize" else 0,
        )
    imports: list[str] = []

    def imported(name: str, *_args: Any, **_kwargs: Any) -> Any:
        imports.append(name)
        assert name == "sys"
        return fake_sys

    namespace = {
        "__name__": "__main__",
        "__file__": module["__file__"],
        "__builtins__": vars(builtins) | {"__import__": imported},
    }
    with pytest.raises(SystemExit) as caught:
        exec(compile(Path(module["__file__"]).read_bytes(), module["__file__"], "exec"), namespace)  # noqa: S102 - fixed source, fake sys; later imports refused
    assert caught.value.code == 1 and imports == ["sys"]
    assert json.loads(output.getvalue())["category"] == "RUNTIME"
    assert "PRIVATE" not in output.getvalue()


@pytest.mark.parametrize("failure", ["write", "short", "flush"])
def test_main_output_failure_after_complete_artifact_exits_one_without_retry(
    module: Any, fake: Any, monkeypatch: Any, failure: str
) -> None:
    class Output:
        def __init__(self) -> None:
            self.buffer = self
            self.closed = False

        def write(self, raw: bytes) -> int:
            if failure == "write":
                raise OSError("PRIVATE_PIPE")
            return len(raw) - 1 if failure == "short" else len(raw)

        def flush(self) -> None:
            if failure == "flush":
                raise OSError("PRIVATE_PIPE")

        def close(self) -> None:
            self.closed = True

    # Execute the exact main body with the real run(), faking only stdout.
    source = Path(module["__file__"]).read_text(encoding="utf-8")
    tail = source[source.rindex('if __name__ == "__main__":') :]
    output = Output()
    monkeypatch.setitem(module, "sys", SimpleNamespace(stdout=output))
    namespace = module | {"__name__": "__main__"}
    with pytest.raises(SystemExit) as caught:
        exec(compile(tail, module["__file__"], "exec"), namespace)  # noqa: S102 - exact main body, fake stdout; no real pins
    assert caught.value.code == 1 and output.closed
    assert fake.calls.count("collect") == 1
    root = module["run"].__globals__["REPO"] / module["RELATIVE"]
    assert json.loads((root / "capture.json").read_bytes())["outcome"] == "MEASURED"


def test_artifact_tampered_after_write_is_not_announced(
    module: Any, fake: Any, monkeypatch: Any
) -> None:
    assert not fake.calls
    original = module["write_new"]

    def tamper(root: Any, name: str, raw: bytes) -> None:
        original(root, name, raw)
        if name == "capture.json":
            (root / "result.json").write_bytes(b"PRIVATE_UNTRUSTED\n")

    monkeypatch.setitem(module["run"].__globals__, "write_new", tamper)
    result, status = module["run"]()
    assert status == 1 and result["artifact"] is None and result["category"] == "PERSISTENCE"
    assert "PRIVATE" not in module["canonical"](result).decode()


def test_exclusive_write_rejects_existing_file_and_short_write(
    module: Any, tmp_path: Any, monkeypatch: Any
) -> None:
    target = tmp_path / "result.json"
    target.write_bytes(b"PREEXISTING")
    with pytest.raises(FileExistsError):
        module["write_new"](tmp_path, "result.json", b"NEW\n")
    assert target.read_bytes() == b"PREEXISTING"

    class ShortStream:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def write(self, raw: bytes) -> int:
            return len(raw) - 1

    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: ShortStream())
    with pytest.raises(module["CaptureError"], match="PERSISTENCE"):
        module["write_new"](tmp_path, "invoked.json", b"NEW\n")


def test_import_creates_no_loop_thread_process_or_artifact(monkeypatch: Any) -> None:
    source_path = REPO / "docs/poc/pg16_shell_pin_capture.py"
    source = source_path.read_bytes()
    original_import = builtins.__import__
    original_open = Path.open
    imports: list[str] = []

    def imported(name: str, *args: Any, **kwargs: Any) -> Any:
        imports.append(name)
        assert name not in {"asyncio", "threading", "subprocess", "multiprocessing"}
        return original_import(name, *args, **kwargs)

    def readonly(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        assert not any(marker in mode for marker in ("w", "x", "a", "+"))
        assert path.is_relative_to(REPO)
        return original_open(path, mode, *args, **kwargs)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("IMPORT_EFFECT")

    monkeypatch.setattr(Path, "open", readonly)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    namespace: Any = {
        "__name__": "_import_only_capture",
        "__file__": str(source_path),
        "__builtins__": vars(builtins) | {"__import__": imported},
    }
    exec(compile(source, str(source_path), "exec"), namespace)  # noqa: S102 - reviewed source, imports monitored, writes forbidden
    assert imports == ["sys", "enum", "hashlib", "json", "os", "pathlib", "stat"]
    assert "result" not in namespace and "root" not in namespace
