"""Servidor MCP.

Adapter de I/O. Nenhuma regra de masking, nenhuma decisao de seguranca: o
handler chama o Gateway e traduz o erro. Se este arquivo sumisse, nenhuma
garantia do produto mudaria.

SDK: `mcp` v2 (`from mcp.server import MCPServer`). Transporte: **stdio
apenas**. Streamable HTTP e SSE existem no SDK e NAO sao usados aqui — nenhuma
porta de rede e aberta nesta fase. Ver D-036.

O cliente controla exclusivamente a SQL. Nao ha parametro para desabilitar
masking, escolher transformer, alterar limites, ler configuracao ou informar
credenciais — nao porque sejam recusados, mas porque nao existem.

Nao ha `resources` nem `prompts`: a superficie e uma tool.
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from maskgw.gateway.models import GatewayError, QueryResult
from maskgw.gateway.service import Gateway

SERVER_NAME = "maskgw"
SERVER_TITLE = "AI Data Masking Gateway"

#: Instrucoes gerais do servidor. Orientam o uso sem descrever o mecanismo.
SERVER_INSTRUCTIONS = (
    "Query the configured database through a read-only gateway. "
    "Results are subject to data protection policies and row limits."
)

#: Descricao da tool, endereçada ao modelo.
#:
#: O que ela deliberadamente NAO diz: quais colunas sao mascaradas, quais
#: transformers existem, quais exceptions estao configuradas, como a origem de
#: uma coluna e resolvida, ou qualquer detalhe que ajude a contornar a
#: protecao. O campo `masked` do resultado ja informa, por coluna, o que foi
#: transformado — isso basta para o modelo interpretar o dado sem receber um
#: mapa do mecanismo.
TOOL_DESCRIPTION = (
    "Execute a read-only SQL query against the configured database. "
    "Only a single SELECT statement is accepted. "
    "Results may be transformed according to data protection policies, and may "
    "be truncated when they exceed the configured row limit — check the "
    "'truncated' field. Each column reports whether it was transformed, in "
    "'columns[].masked'. Rows are positional arrays aligned with 'columns'; "
    "column names can repeat, so do not index rows by name."
)


def build_mcp_server(gateway: Gateway, *, version: str = "0.1.0") -> MCPServer:
    """Monta o servidor MCP em volta de um Gateway ja pronto.

    O Gateway chega construido: este modulo nao carrega configuracao, nao
    conecta ao banco e nao constroi o Masking Engine.
    """
    server: MCPServer = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        version=version,
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.tool(name="query_database", description=TOOL_DESCRIPTION)
    def query_database(sql: str) -> QueryResult:
        """Handler fino: chama o Gateway e traduz o erro. Nada mais."""
        try:
            return gateway.query(sql)
        except GatewayError as exc:
            category = exc.category.value
            message = str(exc)
        # Fora do handler: nem `__cause__` nem `__context__` apontam para o
        # erro interno, e o SDK nao chega a logar um traceback cru.
        raise ToolError(f"{category}: {message}")

    return server
