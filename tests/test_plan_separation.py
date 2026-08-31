"""Fase 7, etapa 4: separacao estrutural entre data e admin planes (§12.8)."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "maskgw"
MCP_DIR = SRC_ROOT / "mcp"
ADMIN_DIR = SRC_ROOT / "admin"
BOOTSTRAP_DIR = SRC_ROOT / "bootstrap"
RUNTIME_DIR = SRC_ROOT / "runtime"


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            imports.add(node.module)
    return imports


def python_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py")) if path.exists() else []


def imports_prefix(path: Path, prefix: str) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for name in imports_of(path))


def test_mcp_never_imports_the_admin_plane() -> None:
    for path in python_files(MCP_DIR):
        assert not imports_prefix(path, "maskgw.admin"), path


def test_admin_never_imports_the_mcp_plane() -> None:
    """Vacuamente verdadeiro ate o pacote admin nascer numa etapa futura."""
    for path in python_files(ADMIN_DIR):
        assert not imports_prefix(path, "maskgw.mcp"), path


def test_only_bootstrap_may_import_a_plane_from_outside_that_plane() -> None:
    offenders: list[str] = []
    for path in python_files(SRC_ROOT):
        if MCP_DIR in path.parents or BOOTSTRAP_DIR in path.parents:
            continue
        if imports_prefix(path, "maskgw.mcp") or imports_prefix(path, "maskgw.admin"):
            offenders.append(path.relative_to(SRC_ROOT).as_posix())
    assert offenders == []


def test_bootstrap_really_composes_the_mcp_plane() -> None:
    importers = [
        path.relative_to(SRC_ROOT).as_posix()
        for path in python_files(BOOTSTRAP_DIR)
        if imports_prefix(path, "maskgw.mcp")
    ]
    assert importers == ["bootstrap/application.py"]


def test_runtime_imports_no_plane_or_gateway() -> None:
    forbidden = ("maskgw.admin", "maskgw.mcp", "maskgw.gateway")
    for path in python_files(RUNTIME_DIR):
        for prefix in forbidden:
            assert not imports_prefix(path, prefix), f"{path.name} importa {prefix}"


def test_admin_cannot_import_logging() -> None:
    for path in python_files(ADMIN_DIR):
        assert "logging" not in imports_of(path), path


def test_bootstrap_has_no_print_or_logging() -> None:
    for path in python_files(BOOTSTRAP_DIR):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert "logging" not in imports_of(path), path
        for node in ast.walk(tree):
            assert not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ), path
