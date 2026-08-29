"""Interface MCP. Somente entrada e saida."""

from __future__ import annotations

from maskgw.mcp.server import (
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    TOOL_DESCRIPTION,
    build_mcp_server,
)

__all__ = [
    "SERVER_INSTRUCTIONS",
    "SERVER_NAME",
    "TOOL_DESCRIPTION",
    "build_mcp_server",
]
