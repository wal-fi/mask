"""Fronteira de processo, sem saida nao protocolar em stdout.

O passo 1 da secao 9.2 acontece aqui: `MASKGW_ADMIN_ENABLED`,
`MASKGW_ADMIN_TOKEN`, `MASKGW_ADMIN_BIND` e `MASKGW_ADMIN_PORT` sao lidos e
validados ANTES de `build_application` tocar em arquivo, lock ou conexao. Um
token curto ou um bind fora de loopback derrubam o processo sem que nada tenha
sido aberto.

Toda a metadata emitida aqui vai para `stderr`, e e fechada: mensagens fixas
mais a revision carregada e, com a Admin API ligada, o host e a porta em que
ela escuta. `stdout` permanece exclusivamente com o protocolo MCP (secao 10.4).
O host e a porta sao parametros operacionais, nao segredos — o token nunca
aparece, nem o tamanho dele.
"""

from __future__ import annotations

import os
import sys
from typing import Final, TextIO

from maskgw.bootstrap.application import (
    CONFIG_PATH_ENV,
    DEFAULT_CONFIG_PATH,
    build_application,
    resolve_admin_settings,
)

STARTUP_FAILURE: Final = "maskgw: falha na inicializacao\n"
RUNTIME_FAILURE: Final = "maskgw: falha durante a execucao\n"
REVISION_LOADED_PREFIX: Final = "maskgw: revision carregada: "
ADMIN_LISTENING_PREFIX: Final = "maskgw: admin api escutando em "


def _write_stderr(stream: TextIO, message: str) -> None:
    """Escreve somente metadata fechada; nunca uma excecao original."""
    stream.write(message)
    stream.flush()


def main(*, stderr: TextIO | None = None) -> int:
    """Constroi, executa e encerra o processo. Devolve o codigo de saida."""
    sink = stderr if stderr is not None else sys.stderr
    config_path = os.environ.get(CONFIG_PATH_ENV, "").strip() or DEFAULT_CONFIG_PATH

    try:
        # Passo 1 da secao 9.2, antes de qualquer recurso: enable, token, bind
        # e porta. Sem admin habilitado devolve None, e o processo segue
        # exatamente como antes — nenhuma porta, nenhuma thread, nenhum lock.
        admin_http = resolve_admin_settings()
        application = build_application(config_path=config_path, admin_http=admin_http)
    except BaseException:
        # Mensagem fixa: sem DSN, secret, SQL, valor, str(exc) ou traceback.
        # Um token curto e um bind recusado saem por aqui, indistinguiveis de
        # qualquer outra falha de startup.
        _write_stderr(sink, STARTUP_FAILURE)
        return 1

    # Metadata fechada e segura em stderr. `stdout` permanece exclusivamente
    # com o protocolo MCP (§9.2 e §10.4).
    _write_stderr(sink, f"{REVISION_LOADED_PREFIX}{application.revision}\n")
    http_server = application.admin_http
    if http_server is not None:
        _write_stderr(sink, f"{ADMIN_LISTENING_PREFIX}{http_server.host}:{http_server.port}\n")

    failed = False
    try:
        application.run()
    except BaseException:
        failed = True
    finally:
        try:
            # `run` ja fecha a Application real; a segunda chamada e
            # deliberada e prova a idempotencia tambem nesta fronteira.
            application.close()
        except BaseException:
            failed = True

    if failed:
        _write_stderr(sink, RUNTIME_FAILURE)
        return 1
    return 0
