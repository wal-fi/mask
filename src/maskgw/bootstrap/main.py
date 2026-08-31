"""Fronteira de processo, sem saida nao protocolar em stdout."""

from __future__ import annotations

import os
import sys
from typing import Final, TextIO

from maskgw.bootstrap.application import CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH, build_application

STARTUP_FAILURE: Final = "maskgw: falha na inicializacao\n"
RUNTIME_FAILURE: Final = "maskgw: falha durante a execucao\n"
REVISION_LOADED_PREFIX: Final = "maskgw: revision carregada: "


def _write_stderr(stream: TextIO, message: str) -> None:
    """Escreve somente metadata fechada; nunca uma excecao original."""
    stream.write(message)
    stream.flush()


def main(*, stderr: TextIO | None = None) -> int:
    """Constroi, executa e encerra o processo. Devolve o codigo de saida."""
    sink = stderr if stderr is not None else sys.stderr
    config_path = os.environ.get(CONFIG_PATH_ENV, "").strip() or DEFAULT_CONFIG_PATH

    try:
        application = build_application(config_path=config_path)
    except BaseException:
        # Mensagem fixa: sem DSN, secret, SQL, valor, str(exc) ou traceback.
        _write_stderr(sink, STARTUP_FAILURE)
        return 1

    # Metadata fechada e segura em stderr. `stdout` permanece exclusivamente
    # com o protocolo MCP (§9.2 e §10.4).
    _write_stderr(sink, f"{REVISION_LOADED_PREFIX}{application.revision}\n")

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
