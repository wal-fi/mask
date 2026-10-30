"""Disposable PG16 gate only. No default run, user DB, pull or product activation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import runpy
import secrets
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER_SHA = "58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627"
CLI_SHA = "60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599"
CONFIG_SHA = "f173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a"
META_SHA = "c16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25"
FORMAT = (
    '{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},'
    '"Labels":{{json .Config.Labels}},"Running":{{json .State.Running}},'
    '"Ports":{{json .NetworkSettings.Ports}},"Bindings":{{json .HostConfig.PortBindings}},'
    '"Mounts":{{json .Mounts}},"Memory":{{json .HostConfig.Memory}},'
    '"Swap":{{json .HostConfig.MemorySwap}},"Pids":{{json .HostConfig.PidsLimit}}}'
)

EXPECTED_CASES = tuple(
    ("tests.test_db_execution_error_integration", name)
    for name in (
        "test_real_idle_success_has_exact_status_and_positive_health",
        "test_real_data_error_is_candidate_only_after_healthy_settle_same_connection",
        "test_real_cardinality_error_is_query_and_connection_remains_healthy",
        "test_real_server_timeout_keeps_querytimeout_type_and_healthy_connection",
        "test_real_terminated_owned_backend_is_never_healthy_or_recoverable",
    )
) + tuple(
    ("tests.test_db_typed_integration", name)
    for name in (
        "test_real_hmac_provenance_alias_and_authoritative_exception",
        "test_real_derived_duplicate_columns_and_nullable_types",
        "test_masked_numeric_is_text_not_preserved_numeric",
        "test_unmasked_numeric_refused_before_fetch_even_null[1]",
        "test_unmasked_numeric_refused_before_fetch_even_null[3]",
        "test_domain_metadata_measured_as_base_type_on_pg16",
        "test_random_invariants_and_row_limit_excess_not_masked",
        "test_same_connection_legacy_typed_and_read_only_defense",
        "test_server_timeout_remains_sanitized_and_session_idle",
        "test_catalog_failure_injected_after_real_query_refuses_before_fetch",
        "test_actual_pipeline_frame_is_accepted_and_sent_by_receiver",
        "test_all_eight_advertised_types_from_real_psycopg_loaders",
    )
)


def require_checks(optimize):
    if optimize != 0:
        raise SystemExit(64)


def required_cases(suite):
    checked = []
    for module, name in EXPECTED_CASES:
        matches = [
            case
            for case in suite.findall("testcase")
            if case.get("classname") == module and case.get("name") == name
        ]
        if len(matches) != 1 or any(
            matches[0].find(tag) is not None for tag in ("skipped", "failure", "error")
        ):
            raise ValueError("REQUIRED_PG_CASE_NOT_PASSED")
        checked.append(module + "::" + name)
    return checked


def owned(meta, task, name, image):
    return (
        type(meta) is dict
        and type(meta.get("Id")) is str
        and re.fullmatch("[0-9a-f]{64}", meta["Id"]) is not None
        and meta.get("Name") == "/" + name
        and meta.get("Image") == image
        and type(meta.get("Labels")) is dict
        and meta["Labels"].get("maskgw-test-owner") == task
        and type(meta.get("Running")) is bool
    )


def port(meta):
    if set(meta["Bindings"]) != {"5432/tcp"} or len(meta["Bindings"]["5432/tcp"]) != 1:
        raise ValueError("PG_BINDING")
    if meta["Bindings"]["5432/tcp"][0]["HostIp"] != "127.0.0.1":
        raise ValueError("PG_BINDING")
    published = meta["Ports"]["5432/tcp"]
    if len(published) != 1 or published[0]["HostIp"] != "127.0.0.1":
        raise ValueError("PG_BINDING")
    value = published[0]["HostPort"]
    if type(value) is not str or not value.isascii() or not value.isdecimal():
        raise ValueError("PG_BINDING")
    result = int(value)
    if not 1 <= result <= 65535:
        raise ValueError("PG_BINDING")
    return result


def sources():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for base in ("src", "tests", "docs/poc")
        for path in sorted((ROOT / base).rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def env():
    names = {
        "PATH",
        "PATHEXT",
        "COMSPEC",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "SYSTEMDRIVE",
        "OS",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in names}


async def run(root, docker):
    from psycopg import connect
    from psycopg.conninfo import make_conninfo

    helper = ROOT / "docs/poc/run_linux_as_probe.py"
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == HELPER_SHA
    assert hashlib.sha256(docker.read_bytes()).hexdigest() == CLI_SHA
    home = Path(os.environ["USERPROFILE"])
    assert hashlib.sha256((home / ".docker/config.json").read_bytes()).hexdigest() == CONFIG_SHA
    meta_file = home / (
        ".docker/contexts/meta/"
        "fe9c6bd7a66301f49ca9b6a70b217107cd1284598bfc254700c989b916da791e/meta.json"
    )
    assert hashlib.sha256(meta_file.read_bytes()).hexdigest() == META_SHA
    state_file = root / "attempt.json"
    state = json.loads(state_file.read_bytes())
    assert state["kind"] == "maskgw-worker-errors-pg16" and state["invoked"] is False
    assert state["phase"] == "APP_READY"
    task = state["task"]
    assert type(task) is str and re.fullmatch("[0-9a-f]{32}", task)
    state["invoked"] = True
    temporary = root / "attempt.tmp"
    with temporary.open("x", encoding="utf8") as stream:
        stream.write(json.dumps(state))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, state_file)
    name = "maskgw-worker-errors-" + task[:12]
    before_sources = sources()
    report = {
        "profile": "worker-errors-pg16",
        "task": task,
        "name": name,
        "outcome": "PENDING",
        "owned_cleanup": False,
        "inventory_restored": False,
        "commands": [],
        "source_unchanged": False,
    }

    def save():
        (root / "progress.json").write_text(json.dumps(report), encoding="utf8")

    save()
    bounded = runpy.run_path(str(helper))["bounded"]
    child_env = env()
    # Change only this private runpy instance's environment collaborator.
    # The frozen helper file and any other process/module remain unchanged.
    bounded.__globals__["environment"] = lambda: dict(child_env)

    async def command(label, args, *, timeout=10, limit=65536):
        assert len(report["commands"]) < 128
        rc, raw = await bounded([str(docker), *args], timeout=timeout, limit=limit)
        report["commands"].append({"name": label, "exit": rc})
        save()
        return rc, raw

    async def inspect(identifier):
        rc, raw = await command("inspect-own", ["inspect", "--format", FORMAT, identifier])
        return json.loads(raw) if rc == 0 else None

    cid = None
    image = None
    volumes = []
    password = secrets.token_hex(24)
    try:
        rc, raw = await command("version", ["version", "--format", "{{json .Server}}"], timeout=5)
        server = json.loads(raw) if rc == 0 else {}
        assert server.get("Os") == "linux" and server.get("Arch") == "amd64"
        report["engine"] = {key: server[key] for key in ("Version", "Os", "Arch")}
        rc, raw = await command("inventory-before", ["ps", "-aq", "--no-trunc"], timeout=5)
        assert rc == 0 and not raw.strip()
        rc, raw = await command(
            "image",
            ["image", "inspect", "--format", "{{json .Id}}", "postgres:16-alpine"],
            timeout=5,
        )
        image = json.loads(raw) if rc == 0 else None
        assert type(image) is str and re.fullmatch("sha256:[0-9a-f]{64}", image)
        report["image"] = image
        report["create_attempted"] = True
        save()
        child_env.update(
            POSTGRES_PASSWORD=password, POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256"
        )
        try:
            rc, raw = await command(
                "create",
                [
                    "create",
                    "--pull",
                    "never",
                    "--name",
                    name,
                    "--label",
                    "maskgw-test-owner=" + task,
                    "--log-driver",
                    "none",
                    "--memory",
                    "512m",
                    "--memory-swap",
                    "512m",
                    "--pids-limit",
                    "256",
                    "--cpus",
                    "1",
                    "--publish",
                    "127.0.0.1::5432",
                    "--env",
                    "POSTGRES_PASSWORD",
                    "--env",
                    "POSTGRES_INITDB_ARGS",
                    image,
                    "postgres",
                    "-c",
                    "timezone=UTC",
                ],
            )
        finally:
            child_env.pop("POSTGRES_PASSWORD", None)
            child_env.pop("POSTGRES_INITDB_ARGS", None)
        meta = await inspect(name)
        assert owned(meta, task, name, image)
        cid = meta["Id"]
        report["cid"] = cid
        volumes = [item["Name"] for item in meta["Mounts"] if item["Type"] == "volume"]
        assert len(meta["Mounts"]) == len(volumes) == 1
        assert meta["Memory"] == meta["Swap"] == 512 * 1024 * 1024 and meta["Pids"] == 256
        assert rc == 0 and raw.strip().decode("ascii") == cid and meta["Running"] is False
        save()
        rc, _ = await command("start", ["start", cid])
        assert rc == 0
        meta = await inspect(cid)
        assert owned(meta, task, name, image) and meta["Running"] is True
        chosen_port = port(meta)
        dsn = make_conninfo(
            host="127.0.0.1",
            port=chosen_port,
            user="postgres",
            password=password,
            dbname="postgres",
            connect_timeout=2,
        )
        ready = False
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with connect(
                    dsn, autocommit=True, options="-c statement_timeout=5000"
                ) as connection:
                    version = connection.execute(
                        "SELECT current_setting('server_version'), "
                        "current_setting('server_version_num')::int"
                    ).fetchone()
                    assert 160000 <= version[1] < 170000
                    report["postgres"] = {"version": version[0], "version_num": version[1]}
                    ready = True
                break
            except Exception:
                await asyncio.sleep(0.25)
        assert ready
        runner = root / "pytest_runner.py"
        runner.write_text(
            "import os,sys,threading\nos.dup2(1,2)\nimport pytest\n"
            "threading.stack_size(64*1024*1024)\nos.chdir(sys.argv[1])\n"
            "raise SystemExit(pytest.main(['--strict-markers','-p','no:cacheprovider',"
            "'--junitxml='+sys.argv[2]]))\n",
            encoding="utf8",
        )
        xml = root / "suite.xml"
        child_env["MASKGW_TEST_DSN"] = dsn
        report["tests_started"] = True
        save()
        print(json.dumps({"stage": "TESTS_STARTED", "root": str(root)}), flush=True)
        try:
            code, output = await bounded(
                [sys.executable, "-I", "-B", "-u", str(runner), str(ROOT), str(xml)],
                timeout=1800,
                limit=4 * 1024 * 1024,
            )
        finally:
            child_env.pop("MASKGW_TEST_DSN", None)
        report["pytest_exit"] = code
        redactions = output.count(password.encode())
        (root / "pytest.log").write_bytes(output.replace(password.encode(), b"[REDACTED]"))
        assert xml.stat().st_size <= 16 * 1024 * 1024
        xml_raw = xml.read_bytes()
        redactions += xml_raw.count(password.encode())
        if password.encode() in xml_raw:
            xml.write_bytes(xml_raw.replace(password.encode(), b"[REDACTED]"))
        report["password_redactions"] = redactions
        suite = ET.fromstring(xml.read_bytes()).find("testsuite")
        report["tests"] = {
            key: suite.attrib[key] for key in ("tests", "failures", "errors", "skipped", "time")
        }
        report["skips"] = [
            {
                "test": case.attrib["classname"] + "::" + case.attrib["name"],
                "reason": skipped.attrib.get("message", ""),
            }
            for case in suite.findall("testcase")
            for skipped in case.findall("skipped")
        ]
        assert code == 0 and redactions == 0
        assert report["tests"]["failures"] == report["tests"]["errors"] == "0"
        assert not any("MASKGW_TEST_DSN" in entry["reason"] for entry in report["skips"])
        report["required_cases_passed"] = required_cases(suite)
        report["outcome"] = "TESTS_PASSED"
    except Exception:
        report["outcome"] = "FAILED"
    finally:
        child_env.clear()
        child_env.update(env())
        try:
            meta = await inspect(cid or name) if image is not None else None
            if owned(meta, task, name, image):
                cid = meta["Id"]
                if meta["Running"]:
                    rc, _ = await command("stop-own", ["stop", "--time", "10", cid], timeout=15)
                    assert rc == 0
                    meta = await inspect(cid)
                    assert owned(meta, task, name, image) and meta["Running"] is False
                rc, _ = await command("remove-own", ["rm", "-v", cid])
                assert rc == 0
            rc, raw = await command("inventory-after", ["ps", "-aq", "--no-trunc"], timeout=5)
            report["inventory_restored"] = rc == 0 and not raw.strip()
            gone = True
            for volume in volumes:
                rc, raw = await command(
                    "volume-after",
                    ["volume", "ls", "--format", "{{.Name}}", "--filter", "name=^" + volume + "$"],
                    timeout=5,
                )
                gone = gone and rc == 0 and volume.encode() not in raw.splitlines()
            report["owned_cleanup"] = report["inventory_restored"] and gone
        except Exception:
            report["owned_cleanup"] = False
        report["source_unchanged"] = sources() == before_sources
        if not all(
            report[key] for key in ("owned_cleanup", "inventory_restored", "source_unchanged")
        ):
            report["outcome"] = "FAILED"
        report["source_hashes"] = before_sources
        save()
        (root / "result.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8"
        )
    print(
        json.dumps({key: value for key, value in report.items() if key != "source_hashes"}),
        flush=True,
    )
    return 0 if report["outcome"] == "TESTS_PASSED" else 2


def main():
    require_checks(sys.flags.optimize)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    root, docker = args.root.resolve(), args.docker.resolve()
    assert args.run and root.is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert root.name.startswith("maskgw-worker-errors-pg-20261023-")
    assert not root.is_relative_to(ROOT) and not (root / "result.json").exists()
    raise SystemExit(asyncio.run(run(root, docker)))


if __name__ == "__main__":
    main()
