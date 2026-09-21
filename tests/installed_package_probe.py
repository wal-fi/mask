"""Run explicitly with isolated installed Python; never included in the package."""

from __future__ import annotations

import io
import os
import secrets
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

import maskgw.bootstrap.main as process
from maskgw.admin.ui import resources
from tests.admin_http_support import free_port, request
from tests.installed_support import verify_environment
from tests.test_admin_ui_startup import block_operational_effects


def startup_barrier(config: Path, *, rejected: bool) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MASKGW_ADMIN_ENABLED", "1")
        patch.setenv("MASKGW_ADMIN_UI_ENABLED", "1")
        patch.setenv("MASKGW_ADMIN_TOKEN", secrets.token_hex(32))
        patch.setenv("MASKGW_ADMIN_BIND", "127.0.0.1")
        patch.setenv("MASKGW_ADMIN_PORT", "8765")
        patch.setenv("MASKGW_CONFIG", str(config))
        events = block_operational_effects(patch, config)
        stderr, stdout = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout):
            result = process.main(stderr=stderr)
        assert result == 1 and stderr.getvalue() == "maskgw: falha na inicializacao\n"
        assert stdout.getvalue() == ""
        # A valid installation must reach the deliberately blocked config step.
        # Otherwise the corruption tests could pass due to unrelated settings.
        assert events == ([] if rejected else ["forbidden"])


def corrupted_installation() -> None:
    """Mutate real installed files, not a mocked resource provider; restore exactly."""
    asset_root = Path(resources.__file__).parent / "assets"
    expected = resources.load_resources()
    with TemporaryDirectory(prefix="maskgw-installed-fail-") as directory:
        config = Path(directory) / "masking.yaml"
        config.write_bytes(b"masking: []\nexceptions: []\n")
        for name in (*expected, "manifest.json"):
            asset = asset_root / name
            original = asset.read_bytes()
            startup_barrier(config, rejected=False)
            for absent in (False, True):
                try:
                    if absent:
                        asset.unlink()
                    else:
                        asset.write_bytes(original + b"\xff")
                    startup_barrier(config, rejected=True)
                finally:
                    asset.write_bytes(original)
            assert resources.load_resources() == expected
            startup_barrier(config, rejected=False)


async def stdio_and_http() -> None:
    """Real installed CLI, no harness in the child; stdout stays MCP protocol."""
    token = secrets.token_hex(32)
    with TemporaryDirectory(prefix="maskgw-installed-stdio-") as directory:
        path = Path(directory)
        config = path / "masking.yaml"
        original = (
            b"masking:\n- match: protected_value\n  transformer: fixed\n  config: {value: masked}\n"
        )
        config.write_bytes(original)
        port = free_port()
        env = dict(os.environ)
        env.update(
            MASKGW_CONFIG=str(config),
            MASKGW_DATABASE_DSN=os.environ["MASKGW_TEST_DSN"],
            MASKGW_ADMIN_ENABLED="1",
            MASKGW_ADMIN_UI_ENABLED="1",
            MASKGW_ADMIN_TOKEN=token,
            MASKGW_ADMIN_BIND="127.0.0.1",
            MASKGW_ADMIN_PORT=str(port),
        )
        parameters = StdioServerParameters(
            command=sys.executable, args=["-I", "-u", "-m", "maskgw"], env=env, cwd=directory
        )
        errpath = path / "stderr.txt"
        with errpath.open("w", encoding="utf-8") as errlog:
            async with (
                stdio_client(parameters, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == ["query_database"]
                for _ in range(3):
                    result = await session.call_tool(
                        "query_database", {"sql": "SELECT 'original'::text AS protected_value"}
                    )
                    assert not result.is_error
                    assert result.structured_content is not None
                    assert result.structured_content["rows"] == [["masked"]]
                    response = request(port, path="/admin/ui", token=None)
                    assert response.status == 200
                    response = request(port, path="/admin/v1/status", token=token)
                    assert response.status == 200
        errors = errpath.read_text(encoding="utf-8")
        assert token not in errors and os.environ["MASKGW_TEST_DSN"] not in errors
        assert "Traceback" not in errors and config.read_bytes() == original
        # A normal restart on the same config/port proves lock and socket release.
        with errpath.open("w", encoding="utf-8") as errlog:
            async with (
                stdio_client(parameters, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                assert request(port, path="/admin/v1/status", token=token).status == 200
        assert config.read_bytes() == original


def main() -> None:
    verify_environment()
    corrupted_installation()
    anyio.run(stdio_and_http)
    verify_environment()
    print("Installed integrity: ten refusals before effects; stdio/HTTP and restart: passed.")


if __name__ == "__main__":
    main()
