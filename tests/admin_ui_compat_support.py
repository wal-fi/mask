"""Pedidos deterministas da Fase 7; nenhum recurso servido da Fase 8."""

from __future__ import annotations

from typing import Any

from tests.admin_http_support import TOKEN, request


def snapshots(port: int) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for path in (
        "/admin/v1/status",
        "/admin/v1/config",
        "/admin/v1/rules",
        "/admin/v1/exceptions",
        "/admin/v1/transformers",
        "/admin/v1/protected",
        "/admin/v1/rules/rul_" + "a" * 32,
        "/admin/v1/exceptions/exc_" + "b" * 32,
    ):
        calls.extend({"method": method, "path": path} for method in ("GET", "HEAD"))
    for path in (
        "/admin/ui",
        "/admin/ui/assets/ui.js",
        "/admin/ui/assets/ui.css",
        "/admin/ui/presentation.json",
    ):
        for method in ("GET", "HEAD"):
            for token in (None, TOKEN):
                calls.append({"method": method, "path": path, "token": token})
    calls.extend(
        [
            {"token": None},
            {"token": "invalid"},
            {"headers": {"Origin": f"http://127.0.0.1:{port}"}},
            {"headers": {"Referer": f"http://127.0.0.1:{port}/admin/ui"}},
            {"host": "external.example"},
            {"method": "OPTIONS", "path": "/admin/ui"},
            {
                "method": "POST",
                "path": "/admin/ui",
                "content_type": "application/json",
                "body": b"{}",
            },
            {"method": "GET", "path": "/admin/v1/unknown"},
        ]
    )
    result = []
    for call in calls:
        reply = request(port, **call)
        result.append(
            {
                "status": reply.status,
                "headers": {key: value for key, value in reply.headers.items() if key != "date"},
                "body": reply.body.hex(),
            }
        )
    return result
