"""Fase 7, etapas 4, 6 e 7: separacao estrutural entre os planos (§12.8).

Ate a Etapa 5 estes testes valiam por vacuidade: o pacote `admin/` nao existia.
Desde a Etapa 6 ele existe, e a separacao passa a ser verificada de fato.

A Etapa 7 introduziu a fronteira HTTP, e com ela **muda uma regra**: FastAPI,
starlette, uvicorn e socket passam a ser permitidos — mas apenas dentro de
`admin/http/`. A secao critica administrativa continua sem HTTP, e importar
`maskgw.admin` continua nao carregando FastAPI. Isso nao afrouxa a separacao:
troca "nenhum HTTP em `admin/`" por "HTTP confinado ao subpacote da fronteira",
que e o que a arquitetura pede, e acrescenta a verificacao de que o
confinamento vale em tempo de import, e nao so no texto.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "maskgw"
MCP_DIR = SRC_ROOT / "mcp"
ADMIN_DIR = SRC_ROOT / "admin"
ADMIN_HTTP_DIR = ADMIN_DIR / "http"
BOOTSTRAP_DIR = SRC_ROOT / "bootstrap"
RUNTIME_DIR = SRC_ROOT / "runtime"
GATEWAY_DIR = SRC_ROOT / "gateway"

#: Pacotes de rede/HTTP. Permitidos SO em `admin/http/`.
HTTP_PACKAGES = {"fastapi", "starlette", "uvicorn", "http", "socket", "ssl"}


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


def test_http_is_confined_to_the_admin_http_subpackage() -> None:
    """A fronteira HTTP existe, e mora num so lugar.

    Substitui o teste da Etapa 6, que proibia HTTP em `admin/` inteiro. A regra
    mudou de fato: a Etapa 7 introduziu a aplicacao. O que continua valendo, e
    o que este teste passa a proteger, e o confinamento — a secao critica
    administrativa nao pode adquirir dependencia de rede.
    """
    for path in python_files(ADMIN_DIR):
        if ADMIN_HTTP_DIR in path.parents:
            continue
        offending = sorted(name for name in imports_of(path) if name.split(".")[0] in HTTP_PACKAGES)
        assert offending == [], f"{path.name} importa {offending}"


def test_the_admin_http_subpackage_exists_since_stage_seven() -> None:
    """Sem isto, o teste de confinamento passaria por vacuidade."""
    assert python_files(ADMIN_HTTP_DIR), "admin/http/ deveria existir desde a Etapa 7"


def test_no_other_plane_acquires_a_network_dependency() -> None:
    """Somente `admin/http/` fala HTTP. O MCP continua stdio only (D-036)."""
    for directory in (MCP_DIR, GATEWAY_DIR, RUNTIME_DIR):
        for path in python_files(directory):
            offending = sorted(
                name for name in imports_of(path) if name.split(".")[0] in HTTP_PACKAGES
            )
            assert offending == [], f"{path.name} importa {offending}"


def test_importing_the_admin_plane_does_not_load_fastapi() -> None:
    """A secao critica e utilizavel — e testavel — sem servidor.

    Medido em subprocesso, no estilo de `test_purity.py`: importar
    `maskgw.admin` nao pode arrastar FastAPI, uvicorn nem starlette. Se
    `admin/__init__.py` reexportasse a aplicacao HTTP, isso deixaria de valer
    sem que nenhum outro teste percebesse.
    """
    src_dir = SRC_ROOT.parent
    program = (
        "import sys;"
        f"sys.path.insert(0, {str(src_dir)!r});"
        "import maskgw.admin;"
        "print(','.join(sorted({name.split('.')[0] for name in sys.modules})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(result.stdout.strip().split(","))

    assert not loaded & {"fastapi", "uvicorn", "starlette"}
    assert "maskgw" in loaded


def test_the_contraproof_admin_http_really_does_load_fastapi() -> None:
    """Sem esta contraprova, o teste acima passaria se nada carregasse FastAPI.

    O mesmo padrao de `test_purity.py`: afirmar a ausencia so tem valor depois
    de provar que a presenca seria detectada.
    """
    src_dir = SRC_ROOT.parent
    program = (
        "import sys;"
        f"sys.path.insert(0, {str(src_dir)!r});"
        "import maskgw.admin.http;"
        "print(','.join(sorted({name.split('.')[0] for name in sys.modules})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(result.stdout.strip().split(","))

    assert {"fastapi", "uvicorn", "starlette"} <= loaded


def test_the_http_boundary_still_ignores_the_data_plane() -> None:
    """`admin/http/` nao conhece `mcp/` nem `gateway/`, como o resto de `admin/`."""
    for path in python_files(ADMIN_HTTP_DIR):
        assert not imports_prefix(path, "maskgw.mcp"), path
        assert not imports_prefix(path, "maskgw.gateway"), path


def test_admin_has_no_print() -> None:
    """Secao 10.4: nenhum `print` em `admin/`, porque `stdout` e do MCP."""
    for path in python_files(ADMIN_DIR):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            assert not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ), path


def test_no_module_writes_to_stdout_directly() -> None:
    """`sys.stdout` nao e escrito por `admin/` nem por `bootstrap/`.

    `bootstrap/main.py` escreve metadata, e escreve em `stderr` — o parametro
    da funcao, nunca `sys.stdout`.
    """
    for directory in (ADMIN_DIR, BOOTSTRAP_DIR):
        for path in python_files(directory):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "stdout":
                    raise AssertionError(f"{path.name} referencia sys.stdout")


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
