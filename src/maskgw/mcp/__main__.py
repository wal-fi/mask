"""Bootstrap do servidor MCP: `python -m maskgw.mcp`.

Ordem: constroi a aplicacao inteira e so entao disponibiliza o MCP. Se a
construcao falhar — configuracao invalida, chave HMAC ausente, PostgreSQL
indisponivel, capability de proveniencia ausente — o processo termina com
codigo 1 e o servidor NUNCA fica disponivel em estado parcial.

Transporte: stdio. Nenhuma porta de rede e aberta.
"""

from __future__ import annotations

import os
import sys

from maskgw.errors import MaskGatewayError
from maskgw.gateway.factory import DEFAULT_CONFIG_PATH, build_application
from maskgw.mcp.server import build_mcp_server

#: Variavel opcional para apontar outro `masking.yaml`.
CONFIG_PATH_ENV = "MASKGW_CONFIG"


def main() -> int:
    """Sobe o servidor MCP em stdio. Devolve o codigo de saida do processo."""
    config_path = os.environ.get(CONFIG_PATH_ENV, "").strip() or DEFAULT_CONFIG_PATH

    try:
        application = build_application(config_path=config_path)
    except MaskGatewayError as exc:
        # stderr, nao stdout: stdout e o canal do protocolo MCP.
        # A mensagem e nossa e ja sanitizada; nunca a do PostgreSQL.
        print(f"maskgw: falha na inicializacao: {exc}", file=sys.stderr)
        return 1

    try:
        build_mcp_server(application.gateway).run(transport="stdio")
    finally:
        application.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
