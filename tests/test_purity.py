"""Criterio de aceite 15 da Fase 1 (docs/ROADMAP.md).

`masking/` e nucleo puro: nao pode depender de banco, MCP, rede ou psycopg.
Tambem nao deve depender do loader de configuracao — a dependencia e no
sentido inverso.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

MASKING_DIR = Path(__file__).resolve().parents[1] / "src" / "maskgw" / "masking"

#: Modulos que o nucleo nao pode importar, direta ou indiretamente.
FORBIDDEN_ROOTS = frozenset(
    {
        "psycopg",
        "psycopg2",
        "asyncpg",
        "sqlalchemy",
        "sqlite3",
        "pglast",
        "mcp",
        "socket",
        "ssl",
        "http",
        "urllib",
        "requests",
        "httpx",
        "yaml",
        "pydantic",
        "logging",
    }
)

#: Unicos modulos do proprio projeto que o nucleo pode importar.
ALLOWED_PROJECT_MODULES = frozenset({"maskgw.errors", "maskgw.secretsource", "maskgw.masking"})


def masking_modules() -> list[Path]:
    return sorted(MASKING_DIR.rglob("*.py"))


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module)
    return roots


def test_masking_package_is_not_empty():
    assert masking_modules(), "nenhum modulo encontrado em masking/"


@pytest.mark.parametrize("module_path", masking_modules(), ids=lambda p: p.name)
def test_no_forbidden_imports(module_path):
    for imported in imported_roots(module_path):
        root = imported.split(".")[0]
        assert root not in FORBIDDEN_ROOTS, f"{module_path.name} importa {imported!r}"


@pytest.mark.parametrize("module_path", masking_modules(), ids=lambda p: p.name)
def test_no_dependency_on_config_loader(module_path):
    for imported in imported_roots(module_path):
        if not imported.startswith("maskgw"):
            continue
        allowed = any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for prefix in ALLOWED_PROJECT_MODULES
        )
        assert allowed, f"{module_path.name} importa {imported!r}"


def test_importing_masking_does_not_load_forbidden_modules():
    """Verificacao em runtime, complementar a analise estatica.

    Roda em subprocesso: recarregar `maskgw` no interpretador do pytest
    substituiria as classes de excecao ja importadas por outros testes.
    """
    src_dir = MASKING_DIR.parents[1]
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(src_dir)!r});"
        "import maskgw.masking;"
        "print(','.join(sorted({name.split('.')[0] for name in sys.modules})))"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(result.stdout.strip().split(","))
    assert not loaded & {"psycopg", "psycopg2", "asyncpg", "pglast", "mcp", "requests", "httpx"}
    assert not loaded & {"yaml", "pydantic"}


def loaded_modules(statement: str) -> set[str]:
    """Modulos carregados por um import, medidos em subprocesso limpo."""
    src_dir = MASKING_DIR.parents[1]
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(src_dir)!r});"
        f"{statement};"
        "print(','.join(sorted(sys.modules)))"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.strip().split(","))


def test_importing_masking_does_not_load_the_db_adapter():
    """A Fase 2 adicionou `maskgw.db`. A dependencia continua num sentido so."""
    assert "maskgw.db" not in loaded_modules("import maskgw.masking")


def test_the_db_adapter_really_does_depend_on_psycopg():
    """Contraprova: sem isto, os testes de pureza passariam por vacuidade."""
    loaded = loaded_modules("import maskgw.db")
    assert "psycopg" in loaded
    assert "maskgw.masking" in loaded
