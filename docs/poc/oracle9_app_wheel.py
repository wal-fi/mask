"""Capture the declarative project and build its pure wheel twice in owned Temp."""

import contextlib
from email.parser import HeaderParser
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import stat
import sys
import time
import tomllib
import zipfile

REPO = Path(__file__).resolve().parents[2]
PROJECT_SHA = "917fe7353178849ec9e7f53627fc0ce2e0be9fb7678d6dcd2e42f79b925de8f9"
INSPECTOR = REPO / "docs/poc/oracle9_wheels_inspect.py"
INSPECTOR_SHA = "2bbcfd531f3da5f39dc4c57e5c6b5e567c2f275c3a4f3452c2435cefc340285f"
SUMMARY = REPO / "docs/poc/evidence/oracle9-wheel-inspection-summary-20261026.json"
SUMMARY_SHA = "d2f0bfcae80e8e306a95942f360e98cd8f703a3c8fb33cf1a1c52054421fd213"
BACKEND_SHA = "6f4a583e1b6bb0d5ef3af2ac0a6e9a033d06f364e4a550e3b112812674b38419"
TOOLS = {"setuptools": "84.0.0", "wheel": "0.48.0", "packaging": "26.3"}
PLUGINS = REPO / "docs/poc/evidence/oracle9-build-plugins-20261026.json"
PLUGINS_SHA = "d3da970d913ff9f75c42e56d45437a2c68aabb78fc5ca850b2f2ea71496918c9"
PLUGIN_GROUPS = (
    "setuptools.finalize_distribution_options",
    "setuptools.file_finders",
    "egg_info.writers",
    "distutils.commands",
    "distutils.setup_keywords",
)


def need(value, category):
    if not value:
        raise RuntimeError(category)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "SOURCE_FILE")


def capture(repo):
    """Read bytes without following any link; never copy the checkout root."""
    for directory in (repo, repo / "src"):
        ds = directory.lstat()
        need(
            stat.S_ISDIR(ds.st_mode)
            and not getattr(ds, "st_file_attributes", 0) & 0x400
            and not stat.S_ISLNK(ds.st_mode),
            "SOURCE_DIRECTORY",
        )
    project = repo / "pyproject.toml"
    regular(project)
    need(project.stat().st_size <= 65536, "PROJECT_SIZE")
    files = {"pyproject.toml": project.read_bytes()}
    need(sha(files["pyproject.toml"]) == PROJECT_SHA, "PROJECT_CHANGED")
    config = tomllib.loads(files["pyproject.toml"].decode())
    need(
        config["build-system"]
        == {"requires": ["setuptools>=68"], "build-backend": "setuptools.build_meta"},
        "BACKEND",
    )
    need(
        not config["project"].get("dynamic")
        and config["project"]["name"] == "maskgw"
        and config["project"]["version"] == "0.1.0",
        "PROJECT_METADATA",
    )
    pending = [repo / "src/maskgw"]
    total = len(files["pyproject.toml"])
    while pending:
        directory = pending.pop()
        ds = directory.lstat()
        need(
            stat.S_ISDIR(ds.st_mode) and not getattr(ds, "st_file_attributes", 0) & 0x400,
            "SOURCE_DIRECTORY",
        )
        for child in sorted(directory.iterdir()):
            s = child.lstat()
            need(
                not getattr(s, "st_file_attributes", 0) & 0x400 and not stat.S_ISLNK(s.st_mode),
                "SOURCE_LINK",
            )
            if stat.S_ISDIR(s.st_mode):
                if child.name != "__pycache__":
                    pending.append(child)
                continue
            need(stat.S_ISREG(s.st_mode), "SOURCE_SPECIAL")
            relative = child.relative_to(repo).as_posix()
            need(
                len(relative.encode()) <= 512 and not any(ord(c) < 32 for c in relative),
                "SOURCE_PATH",
            )
            allowed = child.suffix == ".py" or (
                child.parent == repo / "src/maskgw/admin/ui/assets"
                and child.suffix in (".html", ".js", ".css", ".json")
            )
            need(allowed and s.st_size <= 1024 * 1024, "SOURCE_ALLOWLIST")
            raw = child.read_bytes()
            need(len(raw) == s.st_size, "SOURCE_CHANGED")
            total += len(raw)
            need(total <= 16 * 1024 * 1024 and len(files) < 512, "SOURCE_BUDGET")
            files[relative] = raw
    need(len(files) >= 20, "SOURCE_INCOMPLETE")
    return dict(sorted(files.items())), config


def manifest(files):
    return [{"path": k, "bytes": len(v), "sha256": sha(v)} for k, v in files.items()]


def write_new(path, raw):
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def copy_source(destination, files):
    destination.mkdir()
    for name, raw in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_new(path, raw)
    need(all((destination / k).read_bytes() == v for k, v in files.items()), "COPY_CHANGED")


class BoundedLog(io.StringIO):
    bytes_written = 0

    def write(self, text):
        self.bytes_written += len(text.encode("utf-8"))
        need(self.bytes_written <= 1024 * 1024, "BUILD_LOG_LIMIT")
        return super().write(text)


def minimal_environment(root):
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}
    env.update(
        {
            "TEMP": str(root / "tmp"),
            "TMP": str(root / "tmp"),
            "HOME": str(root / "home"),
            "USERPROFILE": str(root / "home"),
            "PATH": str(Path(sys.executable).parent)
            + os.pathsep
            + str(Path(os.environ["SystemRoot"]) / "System32"),
            "SOURCE_DATE_EPOCH": "315532800",
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "SETUPTOOLS_USE_DISTUTILS": "local",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def plugin_inventory():
    """Read metadata only; never load an entry point during admission."""
    regular(PLUGINS)
    need(PLUGINS.stat().st_size <= 65536, "BUILD_PLUGINS_SIZE")
    raw = PLUGINS.read_bytes()
    need(sha(raw) == PLUGINS_SHA, "BUILD_PLUGINS_PIN")
    rows = []
    for group in PLUGIN_GROUPS:
        for ep in importlib.metadata.entry_points(group=group):
            need(ep.dist is not None, "BUILD_PLUGIN_OWNER")
            rows.append(
                {
                    "group": group,
                    "name": ep.name,
                    "value": ep.value,
                    "owner": ep.dist.metadata["Name"],
                    "version": ep.dist.version,
                }
            )
    rows.sort(key=lambda v: (v["group"], v["name"], v["owner"]))
    need(rows == json.loads(raw), "BUILD_PLUGIN_SET")
    return rows


def run_backend(source, output, root):
    """Public PEP517 hook of the installed, pinned backend, no frontend child."""
    output.mkdir()
    before, environment = Path.cwd(), dict(os.environ)
    log = BoundedLog()
    clean = minimal_environment(root)
    try:
        os.environ.clear()
        os.environ.update(clean)
        os.chdir(source)
        plugin_inventory()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            from setuptools.build_meta import build_wheel

            filename = build_wheel(str(output))
        need(filename == "maskgw-0.1.0-py3-none-any.whl", "WHEEL_NAME")
        need({v.name for v in output.iterdir()} == {filename}, "BUILD_OUTPUT")
        return output / filename, log.getvalue().encode("utf-8")
    finally:
        os.chdir(before)
        os.environ.clear()
        os.environ.update(environment)
        write_new(root / (source.name + "-backend.log"), log.getvalue().encode("utf-8"))


def validate_own_wheel(path, files, config, inspector):
    from packaging.requirements import Requirement

    regular(path)
    need(path.stat().st_size <= 8 * 1024 * 1024, "WHEEL_SIZE")
    raw = path.read_bytes()
    stream = io.BytesIO(raw)
    _, count = inspector["central_preflight"](stream)
    with zipfile.ZipFile(stream) as archive:
        names = archive.namelist()
        need(len(names) == count, "WHEEL_ENTRY_COUNT")
        expected = {k.removeprefix("src/") for k in files if k != "pyproject.toml"}
        need(len(names) == len(set(names)), "WHEEL_DUPLICATE")
        metadata_files = {
            "maskgw-0.1.0.dist-info/" + k for k in ("METADATA", "WHEEL", "RECORD", "top_level.txt")
        }
        need(set(names) == expected | metadata_files, "WHEEL_EXACT_MEMBERS")
        need(
            {v for v in names if not v.startswith("maskgw-0.1.0.dist-info/")} == expected,
            "WHEEL_MEMBERS",
        )
        for name in expected:
            need(archive.getinfo(name).file_size == len(files["src/" + name]), "WHEEL_SOURCE_SIZE")
            need(archive.read(name) == files["src/" + name], "WHEEL_SOURCE_BYTES")
        need(
            archive.getinfo("maskgw-0.1.0.dist-info/METADATA").file_size <= 1024 * 1024,
            "OWN_METADATA_SIZE",
        )
        meta = HeaderParser().parsestr(archive.read("maskgw-0.1.0.dist-info/METADATA").decode())
        actual_requires = meta.get_all("Requires-Dist", [])
        expected_requires = list(config["project"]["dependencies"])
        for extra, requirements in config["project"].get("optional-dependencies", {}).items():
            need(extra == "dev", "PROJECT_EXTRA")
            expected_requires.extend(r + '; extra == "dev"' for r in requirements)
        need(
            {Requirement(v) for v in actual_requires}
            == {Requirement(v) for v in expected_requires},
            "WHEEL_REQUIREMENTS",
        )
        need(meta.get_all("Provides-Extra", []) == ["dev"], "WHEEL_EXTRAS")
        need("maskgw-0.1.0.dist-info/entry_points.txt" not in names, "OWN_ENTRYPOINTS")
    entry = {
        "name": "maskgw",
        "version": "0.1.0",
        "filename": path.name,
        "sha256": sha(raw),
        "requires_python": config["project"]["requires-python"],
        "requires_dist": actual_requires,
    }
    result = inspector["inspect_wheel"](path, entry, time.monotonic() + 30)
    need(
        not result["pth_unapproved"]
        and not result["scripts"]
        and not result["entry_points"]
        and not any(v["elf"] or v["native_path"] for v in result["members"]),
        "OWN_WHEEL_SURFACE",
    )
    return result


def load_inspector():
    regular(INSPECTOR)
    source = INSPECTOR.read_bytes()
    need(sha(source) == INSPECTOR_SHA, "INSPECTOR_CHANGED")
    ns = {"__name__": "_pinned_inspector", "__file__": str(INSPECTOR)}
    exec(compile(source, str(INSPECTOR), "exec"), ns)
    return ns


def main(root):
    need(os.name == "nt" and sys.flags.isolated and not sys.flags.optimize, "RUNTIME")
    need(
        root.parent.resolve() == (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
        and root.name.startswith("maskgw-oracle9-app-wheel-"),
        "OUTPUT_ROOT",
    )
    s = root.lstat()
    need(stat.S_ISDIR(s.st_mode) and not getattr(s, "st_file_attributes", 0) & 0x400, "OUTPUT_ROOT")
    regular(root / "state.json")
    need(
        (root / "state.json").stat().st_size <= 1024 * 1024
        and {v.name for v in root.iterdir()} == {"state.json"},
        "OUTPUT_NOT_FRESH",
    )
    state = json.loads((root / "state.json").read_bytes())
    need(
        state["invoked"] is False
        and state["kind"] == "oracle9-app-wheel-v1"
        and state["program_sha256"] == sha(Path(__file__).read_bytes()),
        "STATE",
    )
    write_new(root / "invoked.json", b'{"invoked":true}\n')
    regular(SUMMARY)
    need(SUMMARY.stat().st_size <= 1024 * 1024, "SUMMARY_SIZE")
    summary = SUMMARY.read_bytes()
    need(
        sha(summary) == SUMMARY_SHA
        and json.loads(summary)["outcome"] == "WHEELS_INSPECTED_STRUCTURALLY",
        "I_NOT_READY",
    )
    inspector = load_inspector()
    native_files, _manifest, _admission = inspector["admission"](Path(state["wheelhouse"]))
    need({k: importlib.metadata.version(k) for k in TOOLS} == TOOLS, "BUILD_TOOLS")
    backend = Path(
        importlib.metadata.distribution("setuptools").locate_file("setuptools/build_meta.py")
    )
    regular(backend)
    need(sha(backend.read_bytes()) == BACKEND_SHA, "BUILD_BACKEND")
    plugins = plugin_inventory()
    write_new(root / "build-plugins.json", (json.dumps(plugins, sort_keys=True) + "\n").encode())
    files, config = capture(REPO)
    from packaging.requirements import Requirement

    need(
        {inspector["canonical"](Requirement(v).name) for v in config["project"]["dependencies"]}
        == {v["name"] for v in native_files if v["requested"]},
        "RESOLVED_ROOTS",
    )
    need(manifest(files) == state["source_manifest"], "SOURCE_CHANGED")
    write_new(
        root / "source-manifest.json", (json.dumps(manifest(files), sort_keys=True) + "\n").encode()
    )
    (root / "tmp").mkdir()
    (root / "home").mkdir()
    outputs, reports = [], []
    for index in (1, 2):
        source = root / ("source" + str(index))
        copy_source(source, files)
        path, log = run_backend(source, root / ("wheel" + str(index)), root)
        need(
            len(log) <= 1024 * 1024
            and all((source / k).read_bytes() == v for k, v in files.items()),
            "BUILD_SOURCE_CHANGED",
        )
        reports.append(validate_own_wheel(path, files, config, inspector))
        outputs.append(path)
        need(manifest(capture(REPO)[0]) == state["source_manifest"], "CHECKOUT_CHANGED")
    need(outputs[0].read_bytes() == outputs[1].read_bytes(), "NONDETERMINISTIC_WHEEL")
    result = {
        "kind": "oracle9-app-wheel-result-v1",
        "outcome": "APP_WHEEL_BUILT_VERIFIED",
        "task": state["task"],
        "program_sha256": state["program_sha256"],
        "project_sha256": PROJECT_SHA,
        "tools": TOOLS,
        "build_plugins": plugins,
        "backend_sha256": BACKEND_SHA,
        "wheel_sha256": sha(outputs[0].read_bytes()),
        "wheel_bytes": outputs[0].stat().st_size,
        "source_manifest": manifest(files),
        "inspection": reports[0],
        "two_builds_identical": True,
        "installed": False,
    }
    write_new(root / "result.json", (json.dumps(result, sort_keys=True) + "\n").encode())
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("outcome", "wheel_sha256", "wheel_bytes", "two_builds_identical")
            }
        )
    )


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({"outcome": "APP_WHEEL_REFUSED", "category": type(exc).__name__}))
        raise SystemExit(1) from None
