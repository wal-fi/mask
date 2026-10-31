"""Shell-reader exporter fakes over realistic fake-transport roots.

Roots are produced by the accepted entry/host with the existing fake transports
only: no Docker, PowerShell, shell, native watchdog, real configuration or real
executable read. Adapters add the exact public metadata keys of the real owner
(e6ca channel) and watchdog (cf66) objects; production code is unchanged.
"""

import hashlib
import json
import runpy
import stat
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self

import pytest

from tests.test_pg16_shell_host import Monitor, Owner, run
from tests.test_pg16_shell_host import bound as host_fixture
from tests.test_pg16_shell_run import context as context_fixture
from tests.test_pg16_shell_run import entry as entry_fixture

bound, entry, context = host_fixture, entry_fixture, context_fixture
REPO = Path(__file__).resolve().parents[1]
ROOT_NAME = "maskgw-pg16-shell-reader-v1-" + "d" * 32
OTHER = "third_party_project_data"
_PRODUCED: dict[str, Any] = {}


class RealisticOwner(Owner):
    """Fake transport exposing the exact e6ca ManagedBootstrap.metadata keys."""

    def __init__(self, engine: Any, task: str, cid: str, case: str) -> None:
        super().__init__(engine, task, cid, case)
        self.sent, self.total, self.retained = False, 0, 0

    async def send_vector(self) -> None:
        await super().send_vector()
        self.sent = True

    async def drain(self) -> Any:
        observed = await super().drain()
        self.total, self.retained = observed.stdout_bytes, observed.report_bytes
        return observed

    def metadata(self) -> Any:
        return {
            "phase": "CLOSED" if self.released else "ACTIVE",
            "role": "P",
            "cid": self.target.cid,
            "fault": None,
            "seed_delivery": "SENT" if self.sent else "NOT_SENT",
            "stdout_bytes": self.total,
            "retained_stdout_bytes": self.retained,
            "released": self.released,
        }


class RealisticMonitor(Monitor):
    """Fake thread lifecycle exposing the exact cf66 Watchdog.metadata keys."""

    def metadata(self) -> Any:
        base = super().metadata()
        return {
            "fired": base["fired"],
            "held": base["held"] or base["fired"],
            "category": "HEARTBEAT" if base["fired"] else None,
            "cid_absent": False,
            "released": False,
            "volumes_restored": False,
            "volume_uncertain": False,
            "thread_joined": base["thread_joined"],
        }


@pytest.fixture
def producer(entry: Any, context: Any, monkeypatch: Any) -> Any:
    value, host, engine, _ = context
    monkeypatch.setitem(
        host.pg["delivery"], "PublicDeliveryOwner", lambda *args: RealisticOwner(engine, *args)
    )

    def watchdog(root: Any, store: Any, _lock: Any, callback: Any, *_rest: Any) -> Any:
        return RealisticMonitor(engine, root, store, callback)

    monkeypatch.setitem(host.pg["watch"], "Watchdog", watchdog)
    entry_sha = hashlib.sha256(Path(entry["__file__"]).read_bytes()).hexdigest()
    # Same complete schema that entry.admit accepts, then the prepare transition.
    host.state.update(
        kind="maskgw-pg16-shell-reader-v1",
        phase="INVOKED",
        invoked=True,
        program_sha256=entry["H"]["V2"]["ORIGINAL_SHA"],
        v2_sha256=entry["H"]["P"]["V2_SHA"],
        parent_sha256=entry["H"]["PARENT_SHA"],
        entry_sha256=entry_sha,
        pg_pins=dict(entry["H"]["SOURCES"].values()),
        transitive_pins=dict(entry["TRANSITIVE_PINS"]),
        stdlib_pins=dict(entry["C"]["STDLIB_PINS"]),
        image=entry["IMAGE"],
    )
    host.write_new(
        "invoked.json",
        entry["R"]["json_bytes"](
            {
                "kind": "MASKGW_PG16_SHELL_INVOKED_V1",
                "task": host.state["task"],
                "host_sha256": entry["HOST_SHA"],
                "entry_sha256": entry_sha,
            }
        ),
    )

    def produce(kind: str) -> Any:
        if kind not in _PRODUCED:
            if kind == "abort-start":
                engine.fail_start = True
            elif kind == "abort-drain":
                engine.fail_drain = True
            elif kind == "pre-a":
                original = host.start_supervision

                async def broken() -> None:
                    await original()
                    raise RuntimeError("SUPERVISION_HELD")

                monkeypatch.setattr(host, "start_supervision", broken)
            status = run(entry["run"](value))
            files: dict[str, bytes] = {}
            dirs: list[str] = []
            for path in sorted(host.root.iterdir()):
                if path.is_dir():
                    dirs.append(path.name)
                    for child in sorted(path.iterdir()):
                        files[path.name + "/" + child.name] = child.read_bytes()
                else:
                    files[path.name] = path.read_bytes()
            _PRODUCED[kind] = (status, files, tuple(dirs))
        return _PRODUCED[kind]

    return produce


@pytest.fixture
def lab(tmp_path_factory: Any, monkeypatch: Any) -> Any:
    module = runpy.run_path(str(REPO / "docs/poc/pg16_shell_export.py"))
    base = tmp_path_factory.mktemp("shell-export")
    # "public" is an ancestor of the destination only, never of the source root.
    temp, parent = base / "Temp", base / "public" / "evidence"
    temp.mkdir()
    parent.mkdir(parents=True)
    namespace = module["export"].__globals__
    monkeypatch.setitem(namespace, "TEMP_ROOT", temp)
    monkeypatch.setitem(namespace, "OUTPUT_PARENT", parent)
    return SimpleNamespace(module=module, namespace=namespace, temp=temp, parent=parent)


def materialize(lab: Any, produced: Any) -> Path:
    _, files, dirs = produced
    root: Path = lab.temp / ROOT_NAME
    root.mkdir()
    for name in dirs:
        (root / name).mkdir()
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return root


def target(lab: Any) -> Path:
    path: Path = lab.parent / ("pg16-shell-reader-run-" + "a" * 12)
    return path


def refused(lab: Any, root: Path, reported_exit: int, code: str) -> Any:
    with pytest.raises(lab.module["ExportError"]) as caught:
        lab.module["export"](root, target(lab), reported_exit)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught


def canonical(item: Any) -> bytes:
    return (json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def rewrite(root: Path, name: str, change: Callable[[Any], Any]) -> None:
    path = root / name
    item = json.loads(path.read_bytes())
    change(item)
    path.write_bytes(canonical(item))


def published(lab: Any) -> tuple[Any, bytes, bytes]:
    summary_raw = (target(lab) / "summary.json").read_bytes()
    transport_raw = (target(lab) / "transport.json").read_bytes()
    return json.loads(summary_raw), summary_raw, transport_raw


def confidential(*blobs: bytes) -> None:
    for blob in blobs:
        assert OTHER.encode() not in blob and b"private-marker" not in blob
        assert b"fault=" not in blob and b"pytest-of" not in blob
        assert b"ProxyPassword" not in blob and b"MASKGW_PG16_SHELL_READER_V1" not in blob


def test_success_23_cases_exports_projection_only(producer: Any, lab: Any) -> None:
    produced = producer("success")
    assert produced[0] == 0
    root = materialize(lab, produced)
    before = {name: (root / name).read_bytes() for name in produced[1]}
    manifest = lab.module["export"](root, target(lab), 0)
    written = sorted(path.name for path in target(lab).iterdir())
    assert written == ["summary.json", "transport.json"]
    summary, summary_raw, transport_raw = published(lab)
    assert summary["outcome"] == "PG16_SHELL_READER_VERIFIED" and summary["phase"] == "FINISHED"
    assert summary["counts"] == {
        "cases_total": 23,
        "records": 23,
        "complete": 23,
        "monitors_started": 23,
        "positive": 4,
        "negative": 19,
    }
    definitions = lab.module["definitions"]()
    reader = definitions["reader"]
    assert [row["case"] for row in summary["cases"]] == list(definitions["cases"])
    for row in summary["cases"]:
        vector = reader["vector"](reader["Case"](row["case"]))
        assert row["status"] == "COMPLETE" and row["monitor"] == "JOINED"
        assert row["returncode"] == (0 if vector.fault is None else 42)
        assert row["report"]["category"] == (None if vector.fault is None else vector.fault.value)
        assert row["inspect_result"]["state"]["ExitCode"] == row["returncode"]
        assert row["owner"]["vector_delivery"] == "SENT_LOCAL_HANDOFF"
        assert row["owner"]["private_seed"] == "NOT_APPLICABLE"
    modes = [row["delivery"]["mode"] for row in summary["cases"]]
    assert modes.count("HEADER_PREFIX") == 9 and modes.count("EXACT_VECTOR") == 14
    assert all(row["status"] == "JOINED" and not row["fired"] for row in summary["watchdogs"])
    assert summary["volumes"]["status"] == "RESTORED"
    assert len(summary["volumes"]["finals"]) == 25 and summary["volumes"]["finals"][-1]["restored"]
    assert summary["cycle"]["checkpoint_count"] == 12 and summary["cycle"]["head"]
    assert summary["diagnostics"]["history"] == []
    assert manifest == json.loads(transport_raw)
    assert manifest["published_source_count"] == 0 and len(manifest["source_directories"]) == 23
    assert {row["name"] for row in manifest["files"]} == set(produced[1])
    assert all(row["published"] is False for row in manifest["files"])
    assert manifest["derived_artifacts"] == [
        {
            "name": "summary.json",
            "bytes": len(summary_raw),
            "sha256": hashlib.sha256(summary_raw).hexdigest(),
        }
    ]
    confidential(summary_raw, transport_raw)
    assert {name: (root / name).read_bytes() for name in produced[1]} == before


def test_reported_exit_must_match_terminal_phase(producer: Any, lab: Any) -> None:
    root = materialize(lab, producer("success"))
    refused(lab, root, 1, "EXPORT_TERMINAL")
    assert not target(lab).exists()


def test_abort_prefix_after_failed_start_keeps_history(producer: Any, lab: Any) -> None:
    produced = producer("abort-start")
    assert produced[0] == 1
    root = materialize(lab, produced)
    refused(lab, root, 0, "EXPORT_TERMINAL")
    lab.module["export"](root, target(lab), 1)
    summary, summary_raw, transport_raw = published(lab)
    assert summary["outcome"] == "NOT_PASSED" and summary["phase"] == "ABORTED"
    assert summary["counts"]["complete"] == 0 and summary["counts"]["records"] == 1
    case = summary["cases"][0]
    assert case["status"] == "INCOMPLETE" and case["removed"] is True and case["report"] is None
    assert summary["diagnostics"]["history"][0]["phase"] == "failure"
    statuses = [row["status"] for row in summary["watchdogs"]]
    assert statuses[0] == "JOINED" and set(statuses[1:]) == {"NOT_STARTED"}
    assert summary["volumes"]["finals"][-1]["restored"] is True
    assert summary["resources"]["pg16_reader_verified"] is None
    confidential(summary_raw, transport_raw)


def test_io_after_prefix_never_becomes_a_report(producer: Any, lab: Any) -> None:
    produced = producer("abort-drain")
    assert produced[0] == 1
    root = materialize(lab, produced)
    lab.module["export"](root, target(lab), 1)
    summary, _, _ = published(lab)
    case = summary["cases"][0]
    assert case["status"] == "INCOMPLETE" and case["report"] is None
    assert case["output_withheld"] is False
    assert summary["counts"]["positive"] == summary["counts"]["negative"] == 0


def test_pre_a_abort_is_untouched_without_commands(producer: Any, lab: Any) -> None:
    produced = producer("pre-a")
    assert produced[0] == 1
    root = materialize(lab, produced)
    lab.module["export"](root, target(lab), 1)
    summary, _, _ = published(lab)
    assert summary["a_entered"] is False and summary["commands"] == []
    assert summary["desktop"] == {"state": "UNTOUCHED_PRE_A", "initial_active": None}
    assert summary["volumes"]["status"] == "NOT_ADMITTED" and summary["cases"] == []
    assert summary["watchdogs"][0]["status"] == "JOINED"
    assert summary["diagnostics"]["history"][0]["category"] == "SUPERVISION_HELD"


def swap_cases(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[0], rows[1] = rows[1], rows[0]

    rewrite(root, "cases.json", change)


def swap_cids(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[0]["cid"], rows[1]["cid"] = rows[1]["cid"], rows[0]["cid"]

    rewrite(root, "ownership.json", change)


def duplicate_reply(root: Path) -> None:
    rewrite(root, "public-cli-manifest.json", lambda rows: rows.append(dict(rows[-1])))


def swap_label(root: Path) -> None:
    def change(rows: Any) -> None:
        row = next(row for row in rows if row["label"] == "inspect-result-one")
        row["label"] = "inspect-result-binary"

    rewrite(root, "public-cli-manifest.json", change)


def tamper_output(root: Path) -> None:
    path = root / "local-case-05-bad-magic-output.bin"
    path.write_bytes(path.read_bytes() + b"x")


def collapse_negative(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[4].update(returncode=0, report_ok=True, report_category=None)

    rewrite(root, "cases.json", change)


def inspect_exit(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[0]["inspect_exit_code"] = 1

    rewrite(root, "cases.json", change)


def owner_delivery(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[0]["owner"]["seed_delivery"] = "NOT_SENT"

    rewrite(root, "cases.json", change)


def delivery_plan(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[4]["delivery"]["mode"] = "EXACT_VECTOR"

    rewrite(root, "cases.json", change)


def fired_monitor(root: Path) -> None:
    def change(item: Any) -> None:
        item["watchdogs"]["one"]["metadata"].update(fired=True, held=True)

    rewrite(root, "result.json", change)


def unproven_resources(root: Path) -> None:
    def change(item: Any) -> None:
        item["terminal_resources_verified"] = False

    rewrite(root, "result.json", change)


def success_history(root: Path) -> None:
    history = [{"phase": "failure", "category": "INTERNAL", "origin": "INTERNAL"}]
    rewrite(root, "result.json", lambda item: item.update(error_history=history))


def volume_final(root: Path) -> None:
    name = min(path.name for path in root.glob("volume-final-*.json"))
    rewrite(root, name, lambda item: item.update(restored=False))


def baseline(root: Path) -> None:
    def change(item: Any) -> None:
        item["names"] = sorted([*item["names"], "zzz-extra"])

    rewrite(root, "local-volume-baseline.json", change)


def unknown_file(root: Path) -> None:
    (root / "notes.txt").write_bytes(b"public")


def watch_evidence(root: Path) -> None:
    (root / "watch-01" / "emergency-00.json").write_bytes(b"{}\n")


def watch_unknown(root: Path) -> None:
    (root / "watch-02" / "raw.bin").write_bytes(b"x")


def held_phase(root: Path) -> None:
    rewrite(root, "attempt.json", lambda item: item.update(phase="HELD"))


def state_pin(root: Path) -> None:
    def change(item: Any) -> None:
        item["stdlib_pins"][sorted(item["stdlib_pins"])[0]] = "0" * 64

    rewrite(root, "attempt.json", change)


def invoked_task(root: Path) -> None:
    rewrite(root, "invoked.json", lambda item: item.update(task="b" * 32))


def monitor_evidence(root: Path) -> None:
    name = max(path.name for path in root.glob("monitor-case-01-one-*.json"))
    rewrite(root, name, lambda item: item.update(status="NOT_STARTED"))


def journal(root: Path) -> None:
    path = root / "checkpoint-05.json"
    path.write_bytes(path.read_bytes() + b" ")


def reply_bytes(root: Path) -> None:
    path = root / min(path.name for path in root.glob("local-cli-*.bin"))
    path.write_bytes(path.read_bytes() + b"x")


def swap_volume_chronology(root: Path) -> None:
    # Reviewer counterexample 3: canonical bytes and a gapless global metadata
    # sequence are kept, only the decision/final chronological slots swap.
    decision = min(root.glob("volume-decision-*.json"))
    final = min(root.glob("volume-final-*.json"))
    decision_number, final_number = decision.name[-8:-5], final.name[-8:-5]
    decision_raw, final_raw = decision.read_bytes(), final.read_bytes()
    decision.unlink()
    final.unlink()
    (root / ("volume-final-" + decision_number + ".json")).write_bytes(final_raw)
    (root / ("volume-decision-" + final_number + ".json")).write_bytes(decision_raw)


def duplicate_decision(root: Path) -> None:
    numbers = [
        int(path.name[-8:-5])
        for pattern in ("volume-*-*.json", "monitor-case-*.json")
        for path in root.glob(pattern)
    ]
    decision = min(root.glob("volume-decision-*.json"))
    name = "volume-decision-" + str(max(numbers) + 1).zfill(3) + ".json"
    (root / name).write_bytes(decision.read_bytes())


def hold_open_integer(root: Path) -> None:
    # Reviewer counterexample 4: False -> 0 still compared equal with ==.
    def change(rows: Any) -> None:
        assert rows[0]["delivery"]["hold_open"] is False
        rows[0]["delivery"]["hold_open"] = 0

    rewrite(root, "cases.json", change)


def inspect_exit_boolean(root: Path) -> None:
    def change(rows: Any) -> None:
        assert rows[0]["inspect_exit_code"] == 0
        rows[0]["inspect_exit_code"] = False

    rewrite(root, "cases.json", change)


def monitor_integer(root: Path) -> None:
    def change(rows: Any) -> None:
        rows[0]["monitor"]["thread_joined"] = 1

    rewrite(root, "cases.json", change)


MUTATIONS: dict[str, tuple[Callable[[Path], None], str]] = {
    "volume-chronology": (swap_volume_chronology, "EXPORT_VOLUME"),
    "duplicate-decision": (duplicate_decision, "EXPORT_VOLUME"),
    "hold-open-integer": (hold_open_integer, "EXPORT_CASE"),
    "inspect-exit-boolean": (inspect_exit_boolean, "EXPORT_INSPECT"),
    "monitor-integer": (monitor_integer, "EXPORT_WATCHDOG"),
    "case-order": (swap_cases, "EXPORT_CASE"),
    "cid-swap": (swap_cids, "EXPORT_RECORD"),
    "duplicate-reply": (duplicate_reply, "EXPORT_CAPTURE"),
    "label-swap": (swap_label, "EXPORT_CAPTURE"),
    "output": (tamper_output, "EXPORT_REPORT"),
    "negative-collapsed": (collapse_negative, "EXPORT_REPORT"),
    "inspect-exit": (inspect_exit, "EXPORT_INSPECT"),
    "owner-delivery": (owner_delivery, "EXPORT_OWNER"),
    "delivery-plan": (delivery_plan, "EXPORT_CASE"),
    "fired": (fired_monitor, "EXPORT_WATCHDOG"),
    "resources": (unproven_resources, "EXPORT_RESOURCE"),
    "success-history": (success_history, "EXPORT_RESOURCE"),
    "volume-final": (volume_final, "EXPORT_VOLUME"),
    "baseline": (baseline, "EXPORT_VOLUME"),
    "unknown-file": (unknown_file, "EXPORT_ARTIFACT"),
    "watch-evidence": (watch_evidence, "EXPORT_WATCHDOG"),
    "watch-unknown": (watch_unknown, "EXPORT_ARTIFACT"),
    "held-phase": (held_phase, "EXPORT_TERMINAL"),
    "state-pin": (state_pin, "EXPORT_STATE"),
    "invoked": (invoked_task, "EXPORT_STATE"),
    "monitor-evidence": (monitor_evidence, "EXPORT_WATCHDOG"),
    "journal": (journal, "EXPORT_JOURNAL"),
    "reply-bytes": (reply_bytes, "EXPORT_CAPTURE"),
}


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_mutated_success_root_is_refused_without_destination(
    producer: Any, lab: Any, mutation: str
) -> None:
    root = materialize(lab, producer("success"))
    change, code = MUTATIONS[mutation]
    change(root)
    refused(lab, root, 0, code)
    assert not target(lab).exists()


def test_abort_history_outside_closed_vocabulary_refused(producer: Any, lab: Any) -> None:
    root = materialize(lab, producer("abort-start"))

    def change(item: Any) -> None:
        item["error_history"].append(
            {"phase": "failure", "category": "PASSWORD_IN_MESSAGE", "origin": "RUNTIME"}
        )

    rewrite(root, "result.json", change)
    caught = refused(lab, root, 1, "EXPORT_DIAGNOSTIC")
    assert "PASSWORD" not in str(caught.value)


@pytest.mark.parametrize(
    "limit",
    [
        ("MAX_FILES", 10, "EXPORT_SIZE"),
        ("MAX_FILE_BYTES", 64, "EXPORT_SIZE"),
        ("MAX_TOTAL_BYTES", 4096, "EXPORT_SIZE"),
        ("MAX_COMMANDS", 8, "EXPORT_LEDGER"),
    ],
)
def test_explicit_caps_refuse_before_any_write(
    producer: Any, lab: Any, monkeypatch: Any, limit: tuple[str, int, str]
) -> None:
    root = materialize(lab, producer("success"))
    name, cap, code = limit
    monkeypatch.setitem(lab.namespace, name, cap)
    refused(lab, root, 0, code)
    assert not target(lab).exists()


def test_reparse_source_is_refused_without_following(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    root = materialize(lab, producer("success"))
    original = Path.lstat

    def lstat(self: Path) -> Any:
        info = original(self)
        if self.name == "cases.json":
            return SimpleNamespace(
                st_mode=info.st_mode, st_size=info.st_size, st_file_attributes=0x400
            )
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    refused(lab, root, 0, "EXPORT_ARTIFACT")


def test_source_change_after_projection_refused_before_destination(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    root = materialize(lab, producer("success"))
    original = lab.namespace["project"]

    def project(*args: Any) -> Any:
        projected = original(*args)
        path = root / "cases.json"
        path.write_bytes(path.read_bytes() + b" ")
        return projected

    monkeypatch.setitem(lab.namespace, "project", project)
    refused(lab, root, 0, "EXPORT_CHANGED")
    assert not target(lab).exists()


def test_changed_entry_pin_refuses_definitions(producer: Any, lab: Any, monkeypatch: Any) -> None:
    root = materialize(lab, producer("success"))
    monkeypatch.setitem(lab.namespace, "ENTRY_SHA", "0" * 64)
    refused(lab, root, 0, "EXPORT_SOURCE")


@pytest.mark.parametrize("failure", ["fsync", "rename"])
def test_persistence_failure_never_announces_completion(
    producer: Any, lab: Any, monkeypatch: Any, failure: str
) -> None:
    root = materialize(lab, producer("success"))
    real = lab.namespace["os"]

    def broken(*_args: Any) -> None:
        raise OSError("private-detail")

    fake = SimpleNamespace(
        fsync=broken if failure == "fsync" else real.fsync,
        rename=broken if failure == "rename" else real.rename,
    )
    monkeypatch.setitem(lab.namespace, "os", fake)
    caught = refused(lab, root, 0, "EXPORT_IO")
    assert "private-detail" not in str(caught.value)
    assert target(lab).is_dir() and not (target(lab) / "transport.json").exists()


def test_existing_or_misnamed_destination_is_never_overwritten(producer: Any, lab: Any) -> None:
    root = materialize(lab, producer("success"))
    target(lab).mkdir()
    (target(lab) / "summary.json").write_bytes(b"earlier")
    refused(lab, root, 0, "EXPORT_DESTINATION")
    assert (target(lab) / "summary.json").read_bytes() == b"earlier"
    with pytest.raises(lab.module["ExportError"]) as caught:
        lab.module["export"](root, lab.parent / "pg16-shell-reader-run-other", 0)
    assert caught.value.args == ("EXPORT_DESTINATION",)


def test_root_outside_expected_parent_or_name_is_refused(lab: Any) -> None:
    other = lab.temp / ("maskgw-pg16-public-20261030-" + "e" * 32)
    other.mkdir()
    refused(lab, other, 0, "EXPORT_ROOT")
    nested = lab.parent / ROOT_NAME
    nested.mkdir()
    refused(lab, nested, 0, "EXPORT_ROOT")


def test_import_defines_only_and_exporter_pins_accepted_entry(lab: Any) -> None:
    accepted = "afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657"
    digest = hashlib.sha256((REPO / "docs/poc/pg16_shell_run.py").read_bytes()).hexdigest()
    assert lab.module["ENTRY_SHA"] == accepted == digest
    assert "main" not in lab.module and not list(lab.parent.iterdir())


class Stream:
    """Fake open() stream recording every requested read size."""

    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.requested: list[int] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, size: int) -> bytes:
        self.requested.append(size)
        return self.raw[:size]


def fake_file(size: int, raw: bytes) -> tuple[Any, Stream]:
    stream = Stream(raw)

    def unbounded() -> bytes:
        raise AssertionError("unbounded read_bytes")

    path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=size),
        open=lambda _mode: stream,
        read_bytes=unbounded,
    )
    return path, stream


def test_grown_source_is_changed_without_unbounded_read(lab: Any) -> None:
    # Reviewer counterexample 1: lstat size 1, content grew to two bytes.
    path, stream = fake_file(1, b"xx")
    with pytest.raises(lab.module["ExportError"]) as caught:
        lab.module["regular"](path)
    assert caught.value.args == ("EXPORT_CHANGED",)
    assert stream.requested == [lab.module["MAX_FILE_BYTES"] + 1]


def test_oversized_growth_reads_at_most_limit_plus_one(lab: Any) -> None:
    path, stream = fake_file(4, b"x" * 4096)
    with pytest.raises(lab.module["ExportError"]) as caught:
        lab.module["regular"](path, 4)
    assert caught.value.args == ("EXPORT_SIZE",)
    assert stream.requested == [5]


def reparse_directory(monkeypatch: Any, selected: Path, mode: int) -> None:
    original = Path.lstat

    def lstat(self: Path) -> Any:
        info = original(self)
        if self == selected:
            return SimpleNamespace(st_mode=mode, st_size=0, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)


def test_source_ancestor_reparse_point_is_refused(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    # Reviewer counterexample 2: only the Temp ancestor is a directory reparse point.
    root = materialize(lab, producer("success"))
    reparse_directory(monkeypatch, lab.temp, stat.S_IFDIR | 0o700)
    refused(lab, root, 0, "EXPORT_ROOT")
    assert not target(lab).exists()


def test_destination_ancestor_reparse_point_is_refused(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    root = materialize(lab, producer("success"))
    reparse_directory(monkeypatch, lab.parent.parent, stat.S_IFDIR | 0o700)
    refused(lab, root, 0, "EXPORT_DESTINATION")
    assert not target(lab).exists()


def test_symlinked_source_root_is_refused(producer: Any, lab: Any, monkeypatch: Any) -> None:
    root = materialize(lab, producer("success"))
    original = Path.lstat

    def lstat(self: Path) -> Any:
        info = original(self)
        if self == root:
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_size=0)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    refused(lab, root, 0, "EXPORT_ROOT")
    assert not target(lab).exists()


def test_short_write_never_announces_completion(producer: Any, lab: Any, monkeypatch: Any) -> None:
    root = materialize(lab, producer("success"))
    original = Path.open

    class Short:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> Self:
            self.stream.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self.stream.__exit__(*args)

        def write(self, raw: bytes) -> int:
            self.stream.write(raw[:-1])
            return len(raw) - 1

        def flush(self) -> None:
            self.stream.flush()

        def fileno(self) -> int:
            return int(self.stream.fileno())

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original(self, mode, *args, **kwargs)
        return Short(stream) if self.name == "summary.json" and mode == "xb" else stream

    monkeypatch.setattr(Path, "open", opener)
    refused(lab, root, 0, "EXPORT_IO")
    assert not (target(lab) / "transport.json").exists()
    assert not (target(lab) / "transport.json.next").exists()


def test_completion_marker_is_last_and_never_read_back_after_rename(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    # Reviewer counterexample 5: a failure after the rename left a visible
    # marker. Every fallible read now precedes the rename.
    root = materialize(lab, producer("success"))
    original = lab.namespace["regular"]

    def regular(path: Any, maximum: Any = None) -> bytes:
        if path.name == "transport.json":
            raise OSError("after-marker")
        return bytes(original(path, maximum))

    monkeypatch.setitem(lab.namespace, "regular", regular)
    manifest = lab.module["export"](root, target(lab), 0)
    assert (target(lab) / "transport.json").read_bytes() == canonical(manifest)
    assert not (target(lab) / "transport.json.next").exists()


def test_pending_readback_failure_leaves_no_completion_marker(
    producer: Any, lab: Any, monkeypatch: Any
) -> None:
    root = materialize(lab, producer("success"))
    original = lab.namespace["regular"]

    def regular(path: Any, maximum: Any = None) -> bytes:
        if path.name == "transport.json.next":
            raise OSError("readback")
        return bytes(original(path, maximum))

    monkeypatch.setitem(lab.namespace, "regular", regular)
    refused(lab, root, 0, "EXPORT_IO")
    assert not (target(lab) / "transport.json").exists()
    assert (target(lab) / "transport.json.next").is_file()
