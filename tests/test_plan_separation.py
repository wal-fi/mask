"""Fase 7, etapas 4 e 6: separacao estrutural entre data e admin planes (§12.8).

Ate a Etapa 5 estes testes valiam por vacuidade: o pacote `admin/` nao existia.
Desde a Etapa 6 ele existe, e a separacao passa a ser verificada de fato.
"""

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


def test_the_admin_package_exists_since_stage_six() -> None:
    """Sem isto, os testes de separacao passariam por vacuidade."""
    assert python_files(ADMIN_DIR), "o pacote admin/ deveria existir desde a Etapa 6"


def test_admin_never_imports_the_mcp_plane() -> None:
    for path in python_files(ADMIN_DIR):
        assert not imports_prefix(path, "maskgw.mcp"), path


def test_admin_never_imports_the_gateway() -> None:
    """O admin troca o runtime; quem o consome e o data plane, e sao planos distintos."""
    for path in python_files(ADMIN_DIR):
        assert not imports_prefix(path, "maskgw.gateway"), path


def test_admin_has_no_http_surface_in_stage_six() -> None:
    """A Etapa 6 e a secao critica; HTTP e a Etapa 7.

    Este teste MUDA quando a Etapa 7 introduzir a aplicacao HTTP, e e por isso
    que ele existe: antecipar FastAPI, bind ou porta aqui quebra a suite em vez
    de passar despercebido.
    """
    forbidden = {"fastapi", "starlette", "uvicorn", "http", "http.server", "socket", "ssl"}
    for path in python_files(ADMIN_DIR):
        offending = sorted(name for name in imports_of(path) if name.split(".")[0] in forbidden)
        assert offending == [], f"{path.name} importa {offending}"


def test_bootstrap_really_composes_the_admin_plane() -> None:
    importers = [
        path.relative_to(SRC_ROOT).as_posix()
        for path in python_files(BOOTSTRAP_DIR)
        if imports_prefix(path, "maskgw.admin")
    ]
    assert importers == ["bootstrap/application.py"]


def test_only_bootstrap_may_import_a_plane_from_outside_that_plane() -> None:
    """Cada plano so e importado de dentro dele mesmo, ou do bootstrap.

    Ate a Etapa 5 os dois planos podiam ser varridos juntos, porque `admin/`
    estava vazio e nenhum modulo importava `maskgw.admin`. Com o pacote
    existindo, os planos precisam ser avaliados um a um: um modulo de `admin/`
    que importa `maskgw.admin.errors` esta DENTRO do proprio plano, e isso
    sempre foi permitido.
    """
    offenders: list[str] = []
    for plane_dir, prefix in ((MCP_DIR, "maskgw.mcp"), (ADMIN_DIR, "maskgw.admin")):
        for path in python_files(SRC_ROOT):
            if plane_dir in path.parents or BOOTSTRAP_DIR in path.parents:
                continue
            if imports_prefix(path, prefix):
                offenders.append(f"{path.relative_to(SRC_ROOT).as_posix()} -> {prefix}")
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
