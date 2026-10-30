"""Prepare a partial Linux import lab; never import Linux/product code on host.

Metadata is a separate action. Network downloads/install require code review.
All writes are new artifacts below the explicit, freshly-created temp directory.
"""

from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

MIB = 1024 * 1024
COMPRESSED_CAP = 100 * MIB
ZIP_CAP = 240 * MIB
TREE_CAP = 250 * MIB
PRODUCT_HASH = "de45edb1c8ea30bbccd9ef73cb9533c7d705fd1ade76cdb926f90a60c4b45449"
PINS = {
    "pglast": "8.4",
    "psycopg": "3.3.4",
    "psycopg-binary": "3.3.4",
    "pydantic": "2.13.5",
    "pydantic-core": "2.46.5",
    "pyyaml": "6.0.3",
    "cryptography": "50.0.1",
    "cffi": "2.1.1",
    "pycparser": "3.0",
    "typing-extensions": "4.16.0",
    "annotated-types": "0.8.0",
    "typing-inspection": "0.4.4",
    "maskgw": "0.1.0",
}
EXCLUDED_PRODUCT_DEPS = {"mcp", "fastapi", "uvicorn", "scramp", "asn1crypto"}
PLATFORMS = [f"manylinux_2_{n}_x86_64" for n in range(36, 16, -1)] + ["manylinux2014_x86_64"]
TAGS = list(cpython_tags((3, 11), abis=["cp311"], platforms=PLATFORMS)) + list(
    compatible_tags((3, 11), interpreter="cp311", platforms=PLATFORMS)
)
RANK = {tag: index for index, tag in enumerate(TAGS)}
HEX = re.compile(r"[0-9a-f]{64}\Z")


class PreparationError(Exception):
    def __init__(self, category="INVALID"):
        self.category = category
        super().__init__(category)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise PreparationError("REDIRECT")


def network_opener():
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )


def url_allowed(url, host):
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise PreparationError("ORIGIN")


def hashed(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save(path, value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(data) > MIB:
        raise PreparationError("REPORT_LIMIT")
    temporary = path.with_suffix(".new")
    with temporary.open("wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def choose_wheel(metadata, name, version):
    if (
        canonicalize_name(metadata["info"]["name"]) != name
        or metadata["info"]["version"] != version
    ):
        raise PreparationError("METADATA_IDENTITY")
    choices = []
    for item in metadata["urls"]:
        if item.get("packagetype") != "bdist_wheel" or item.get("yanked") is not False:
            continue
        filename = item["filename"]
        dist, wheel_version, _build, tags = parse_wheel_filename(filename)
        if dist != name or wheel_version != Version(version) or not tags <= RANK.keys():
            continue
        url_allowed(item["url"], "files.pythonhosted.org")
        sha = item["digests"]["sha256"]
        size = item["size"]
        if not HEX.fullmatch(sha) or type(size) is not int or not 0 < size <= COMPRESSED_CAP:
            raise PreparationError("METADATA_SIZE_HASH")
        choices.append(
            (
                min(RANK[tag] for tag in tags),
                filename,
                {
                    "name": name,
                    "version": version,
                    "filename": filename,
                    "url": item["url"],
                    "sha256": sha,
                    "size": size,
                    "tags": sorted(map(str, tags)),
                },
            )
        )
    if not choices:
        raise PreparationError("NO_COMPATIBLE_WHEEL")
    return min(choices, key=lambda item: (item[0], item[1]))[2]


def product_matches(wheel, checkout):
    if hashed(wheel) != PRODUCT_HASH:
        raise PreparationError("PRODUCT_HASH")
    checked = 0
    with zipfile.ZipFile(wheel) as archive:
        packaged = {
            name
            for name in archive.namelist()
            if name.startswith("maskgw/") and not name.endswith("/")
        }
        expected = {
            path.relative_to(checkout / "src").as_posix()
            for path in (checkout / "src/maskgw").rglob("*.py")
            if "__pycache__" not in path.parts
        }
        expected.update(
            path.relative_to(checkout / "src").as_posix()
            for path in (checkout / "src/maskgw/admin/ui/assets").glob("*")
            if path.suffix in {".html", ".js", ".css", ".json"}
        )
        if packaged != expected:
            raise PreparationError("PRODUCT_INVENTORY")
        for name in archive.namelist():
            if name.startswith("maskgw/") and not name.endswith("/"):
                source = checkout / "src" / name
                if not source.is_file() or source.read_bytes() != archive.read(name):
                    raise PreparationError("PRODUCT_SOURCE_CHANGED")
                checked += 1
    if checked != 115:
        raise PreparationError("PRODUCT_INVENTORY")
    return checked


def check_placement(root, checkout):
    resolved, repository = root.resolve(), checkout.resolve()
    if (
        not resolved.name.startswith("maskgw-linux-imports-")
        or resolved.is_relative_to(repository)
        or repository.is_relative_to(resolved)
    ):
        raise PreparationError("ROOT")


def metadata_only(root, product):
    check_placement(root, Path(__file__).resolve().parents[2])
    if root.exists() or not root.name.startswith("maskgw-linux-imports-"):
        raise PreparationError("ROOT")
    if shutil.disk_usage(root.parent).free < 500 * MIB:
        raise PreparationError("DISK_SPACE")
    for name, version in PINS.items():
        if importlib.metadata.version(name) != version:
            raise PreparationError("HOST_VERSION_CHANGED")
    checked = product_matches(product, Path(__file__).resolve().parents[2])
    root.mkdir()
    save(root / "owner.json", {"kind": "maskgw-linux-imports", "root": str(root)})
    opener = network_opener()
    wheels = []
    deadline = time.monotonic() + 180
    for name, version in PINS.items():
        if name == "maskgw":
            continue
        if time.monotonic() >= deadline:
            raise PreparationError("PREPARATION_DEADLINE")
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        url_allowed(url, "pypi.org")
        with opener.open(url, timeout=10) as response:
            url_allowed(response.geturl(), "pypi.org")
            raw = response.read(4 * MIB + 1)
        if len(raw) > 4 * MIB:
            raise PreparationError("METADATA_LIMIT")
        wheels.append(choose_wheel(json.loads(raw), name, version))
    total = sum(item["size"] for item in wheels) + product.stat().st_size
    if total > COMPRESSED_CAP:
        raise PreparationError("COMPRESSED_LIMIT")
    save(
        root / "metadata.json",
        {
            "wheels": wheels,
            "compressed_bytes": total,
            "product": str(product),
            "product_sha256": PRODUCT_HASH,
            "product_files_checked": checked,
            "packaging_version": importlib.metadata.version("packaging"),
            "tls_and_pypi_hash_only": True,
            "independent_attestation": False,
        },
    )
    print(
        json.dumps(
            {
                "root": str(root),
                "metadata_wheels": len(wheels),
                "compressed_bytes": total,
                "downloaded_wheels": 0,
            }
        )
    )


def download_one(opener, item, target, deadline):
    url_allowed(item["url"], "files.pythonhosted.org")
    temporary = target.with_suffix(".part")
    size = 0
    sha = hashlib.sha256()
    with opener.open(item["url"], timeout=10) as source, temporary.open("xb") as output:
        url_allowed(source.geturl(), "files.pythonhosted.org")
        while block := source.read(65536):
            size += len(block)
            if size > item["size"] or time.monotonic() >= deadline:
                raise PreparationError("DOWNLOAD_LIMIT")
            sha.update(block)
            output.write(block)
    if size != item["size"] or sha.hexdigest() != item["sha256"]:
        raise PreparationError("DOWNLOAD_INTEGRITY")
    os.replace(temporary, target)


def safe_member(name):
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or path.is_absolute()
        or ".." in path.parts
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise PreparationError("ZIP_PATH")
    if any(part.casefold().endswith((".pth", ".pyc")) for part in path.parts):
        raise PreparationError("ZIP_EXECUTION")


def wheel_details(path):
    distribution, version, _build, tags = parse_wheel_filename(path.name)
    names = set()
    declared = 0
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 10000:
            raise PreparationError("ZIP_MEMBERS")
        for item in archive.infolist():
            safe_member(item.orig_filename)  # ZipInfo normalizes backslashes on Windows
            safe_member(item.filename)
            folded = item.filename.casefold()
            if folded in names or stat.S_ISLNK(item.external_attr >> 16):
                raise PreparationError("ZIP_COLLISION_LINK")
            names.add(folded)
            if item.file_size > ZIP_CAP or item.file_size > max(item.compress_size, 1) * 2000:
                raise PreparationError("ZIP_RATIO_SIZE")
            declared += item.file_size
        if declared > ZIP_CAP:
            raise PreparationError("ZIP_SIZE")
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise PreparationError("WHEEL_IDENTITY")
        prefix = metadata_names[0][: -len("METADATA")]
        meta = BytesParser().parsebytes(archive.read(prefix + "METADATA"))
        wheel = BytesParser().parsebytes(archive.read(prefix + "WHEEL"))
        if canonicalize_name(meta["Name"]) != distribution or meta["Version"] != str(version):
            raise PreparationError("WHEEL_IDENTITY")
        if set(wheel.get_all("Tag", [])) != set(map(str, tags)):
            raise PreparationError("WHEEL_TAGS")
        entrypoints = []
        if prefix + "entry_points.txt" in archive.namelist():
            parser = configparser.ConfigParser()
            parser.read_string(archive.read(prefix + "entry_points.txt").decode())
            for group in ("console_scripts", "gui_scripts"):
                if parser.has_section(group):
                    for script in parser[group]:
                        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", script):
                            raise PreparationError("ENTRYPOINT")
                        entrypoints.append(script)
        return {
            "name": distribution,
            "version": str(version),
            "declared_bytes": declared,
            "requires": meta.get_all("Requires-Dist", []),
            "entrypoints": entrypoints,
            "members": [item.filename for item in archive.infolist() if not item.is_dir()],
        }


def check_dependencies(details):
    versions = {item["name"]: item["version"] for item in details}
    extras = {name: {""} for name in versions}
    env = default_environment()
    env.update(
        os_name="posix",
        sys_platform="linux",
        platform_system="Linux",
        platform_machine="x86_64",
        python_version="3.11",
        python_full_version="3.11.17",
        implementation_name="cpython",
        implementation_version="3.11.17",
        platform_python_implementation="CPython",
        platform_release="",
        platform_version="",
    )
    excluded = set()
    for _ in range(len(details) + 1):
        changed = False
        for item in details:
            for line in item["requires"]:
                req = Requirement(line)
                if req.marker is not None and not any(
                    req.marker.evaluate({**env, "extra": extra}) for extra in extras[item["name"]]
                ):
                    continue
                name = canonicalize_name(req.name)
                if item["name"] == "maskgw" and name in EXCLUDED_PRODUCT_DEPS:
                    excluded.add(name)
                    continue
                if name not in versions or Version(versions[name]) not in req.specifier or req.url:
                    raise PreparationError("DEPENDENCY_CLOSURE")
                if not req.extras <= extras[name]:
                    extras[name].update(req.extras)
                    changed = True
        if not changed:
            return sorted(excluded)
    raise PreparationError("DEPENDENCY_CLOSURE")


def verify_tree(target, launchers):
    files = {}
    for path in target.rglob("*"):
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_symlink() or attributes & 0x400:
            raise PreparationError("TREE_LINK")
        if path.is_file():
            relative = path.relative_to(target).as_posix()
            safe_member(relative)
            if relative.casefold() in {name.casefold() for name in files}:
                raise PreparationError("TREE_COLLISION")
            files[relative] = path
    total = sum(path.stat().st_size for path in files.values())
    if total > TREE_CAP:
        raise PreparationError("TREE_SIZE")
    recorded = set()
    for record in target.glob("*.dist-info/RECORD"):
        for relative, fingerprint, size in csv.reader(
            io.StringIO(record.read_text(encoding="utf-8"))
        ):
            if relative not in files:
                # pip target relocates launchers; never resolve '..' outside this root.
                candidates = [name for name in launchers if relative.endswith("/" + name)]
                if len(candidates) != 1 or candidates[0] not in files:
                    raise PreparationError("RECORD_PATH")
                relative = candidates[0]
            path = files[relative]
            if not fingerprint:
                if path != record or size:
                    raise PreparationError("RECORD_UNHASHED")
            else:
                if not fingerprint.startswith("sha256=") or size != str(path.stat().st_size):
                    raise PreparationError("RECORD_INTEGRITY")
                expected = (
                    base64.urlsafe_b64encode(bytes.fromhex(hashed(path))).decode().rstrip("=")
                )
                if fingerprint != "sha256=" + expected:
                    raise PreparationError("RECORD_INTEGRITY")
            recorded.add(relative)
    if recorded != files.keys():
        raise PreparationError("RECORD_MISSING")
    return {
        "file_count": len(files),
        "file_bytes": total,
        "files": [
            [name, path.stat().st_size, hashed(path)] for name, path in sorted(files.items())
        ],
    }


def prepare(root):
    check_placement(root, Path(__file__).resolve().parents[2])
    owner = json.loads((root / "owner.json").read_bytes())
    if owner != {"kind": "maskgw-linux-imports", "root": str(root)}:
        raise PreparationError("ROOT")
    metadata = json.loads((root / "metadata.json").read_bytes())
    if (
        not root.name.startswith("maskgw-linux-imports-")
        or shutil.disk_usage(root).free < 500 * MIB
    ):
        raise PreparationError("ROOT_OR_DISK_SPACE")
    seen = set()
    for item in metadata["wheels"]:
        name = item["name"]
        if name == "maskgw" or name in seen or PINS.get(name) != item["version"]:
            raise PreparationError("MANIFEST_IDENTITY")
        seen.add(name)
        filename = item["filename"]
        safe_member(filename)
        dist, version, _build, tags = parse_wheel_filename(filename)
        if (
            "/" in filename
            or dist != name
            or str(version) != item["version"]
            or not tags <= RANK.keys()
        ):
            raise PreparationError("MANIFEST_TAGS")
        url_allowed(item["url"], "files.pythonhosted.org")
        if not HEX.fullmatch(item["sha256"]) or type(item["size"]) is not int or item["size"] <= 0:
            raise PreparationError("MANIFEST_SIZE_HASH")
    if seen != PINS.keys() - {"maskgw"}:
        raise PreparationError("MANIFEST_IDENTITY")
    product = Path(metadata["product"])
    total = sum(item["size"] for item in metadata["wheels"]) + product.stat().st_size
    if total != metadata["compressed_bytes"] or total > COMPRESSED_CAP:
        raise PreparationError("COMPRESSED_LIMIT")
    wheelhouse, target = root / "wheels", root / "installed"
    wheelhouse.mkdir()
    target.mkdir()
    checked = product_matches(product, Path(__file__).resolve().parents[2])
    opener = network_opener()
    deadline = time.monotonic() + 180
    for item in metadata["wheels"]:
        download_one(opener, item, wheelhouse / item["filename"], deadline)
    shutil.copyfile(product, wheelhouse / product.name)
    details = [wheel_details(path) for path in sorted(wheelhouse.glob("*.whl"))]
    validate_wheelhouse(details)
    excluded = check_dependencies(details)
    lines = [
        f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}"
        for item in metadata["wheels"]
    ]
    lines.append(f"maskgw==0.1.0 --hash=sha256:{PRODUCT_HASH}")
    (root / "requirements.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    args = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "install",
        "--no-index",
        "--no-deps",
        "--require-hashes",
        "--only-binary=:all:",
        "--no-compile",
        "--find-links",
        str(wheelhouse),
        "--target",
        str(target),
        "--python-version",
        "3.11",
        "--implementation",
        "cp",
        "--abi",
        "cp311",
        "--abi",
        "abi3",
        "--abi",
        "none",
        "-r",
        str(root / "requirements.txt"),
    ]
    for platform in PLATFORMS:
        args.extend(["--platform", platform])
    env = {
        key: os.environ[key]
        for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
        if key in os.environ
    }
    completed = subprocess.run(
        args,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if completed.returncode:
        raise PreparationError("INSTALLATION")
    launchers = {
        f"{directory}/{script}{suffix}"
        for item in details
        for script in item["entrypoints"]
        for directory in ("bin", "Scripts")
        for suffix in ("", ".exe", "-script.py")
    }
    inventory = verify_tree(target, launchers)
    save(root / "tree.json", inventory)
    save(
        root / "prepared.json",
        {
            "details": details,
            "excluded_product_deps": excluded,
            "product_files_checked": checked,
            "installed_files": inventory["file_count"],
            "installed_bytes": inventory["file_bytes"],
            "tree_sha256": hashed(root / "tree.json"),
            "launchers_allowlist": sorted(launchers),
            "partial_installation_only": True,
            "runtime_imports_executed": False,
            "ssl_cert_file_present": "SSL_CERT_FILE" in os.environ,
            "ssl_cert_dir_present": "SSL_CERT_DIR" in os.environ,
        },
    )
    print(
        json.dumps(
            {
                "prepared": True,
                "root": str(root),
                "installed_bytes": inventory["file_bytes"],
                "installed_files": inventory["file_count"],
                "runtime_imports_executed": False,
            }
        )
    )


def validate_wheelhouse(details):
    if len(details) != len(PINS) or {item["name"]: item["version"] for item in details} != PINS:
        raise PreparationError("WHEELHOUSE_IDENTITY")
    if sum(item["declared_bytes"] for item in details) > ZIP_CAP:
        raise PreparationError("ZIP_SIZE")
    folded_members = set()
    for item in details:
        for member in item["members"]:
            folded = member.casefold()
            if folded in folded_members:
                raise PreparationError("CROSS_WHEEL_COLLISION")
            folded_members.add(folded)


def main():
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "metadata":
            metadata_only(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        elif len(sys.argv) == 3 and sys.argv[1] == "prepare":
            prepare(Path(sys.argv[2]).resolve())
        else:
            return 64
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "preparation_success": False,
                    "category": error.category
                    if isinstance(error, PreparationError)
                    else "COLLECTION",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
