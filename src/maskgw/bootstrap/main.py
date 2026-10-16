"""Fronteira de processo, sem saida nao protocolar em stdout.

A flag UI bruta e a dependencia UI/Admin sao resolvidas primeiro.
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

Ativacao local do PGWire (D-110, autorizada em 2026-10-15): com
`MASKGW_PGWIRE_ENABLED` exatamente `1`, o processo compoe o listener sobre um
catalogo JA EXISTENTE (abre, nunca cria nem migra), sem Admin API e sem UI —
combinacao recusada antes de qualquer efeito, para que a v2 nao seja exposta.
O MCP em stdio, o DSN legado e o encerramento no EOF do MCP continuam iguais:
nao ha modo daemon. O listener so autentica; qualquer SQL de cliente recebe
`0A000` sem ser repassado. Com a flag desligada, nada muda e nada de
`maskgw.pgwire` ou do catalogo e importado.
"""

from __future__ import annotations

import contextlib
import os
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TextIO

from maskgw.bootstrap.application import (
    CONFIG_PATH_ENV,
    DEFAULT_CONFIG_PATH,
    Application,
    build_application,
    resolve_admin_settings,
    resolve_admin_ui_enabled,
)
from maskgw.bootstrap.settings import (
    ADMIN_UI_ENABLED_ENV,
    PGWIRE_ENABLED_ENV,
    PGWIRE_ENABLED_VALUE,
    EnvRawSettings,
    RawSettings,
    resolve_catalog_paths,
)
from maskgw.errors import ConfigError
from maskgw.secretsource import EnvSecretProvider

if TYPE_CHECKING:
    from maskgw.pgwire.listener import PgwireListener
    from maskgw.pgwire.settings import PgwireSettings

STARTUP_FAILURE: Final = "maskgw: falha na inicializacao\n"
RUNTIME_FAILURE: Final = "maskgw: falha durante a execucao\n"
REVISION_LOADED_PREFIX: Final = "maskgw: revision carregada: "
ADMIN_LISTENING_PREFIX: Final = "maskgw: admin api escutando em "
#: Bind literal confirmado: host numerico e porta.
PGWIRE_LISTENING_PREFIX: Final = "maskgw: pgwire escutando em "
#: Bind por hostname: so a porta (o literal resolvido nao e exposto aqui).
PGWIRE_LISTENING_PORT_PREFIX: Final = "maskgw: pgwire escutando na porta "


def _write_stderr(stream: TextIO, message: str) -> None:
    """Escreve somente metadata fechada; nunca uma excecao original."""
    stream.write(message)
    stream.flush()


def _require_existing_regular_file(path: Path) -> None:
    """Recusa cedo um arquivo do catalogo ausente, symlink ou nao regular.

    So uma recusa ANTECIPADA: nao e atomica nem garante ausencia de sidecars
    sob corrida. As checagens autoritativas (pais, symlink, locks, conteudo)
    continuam no `CatalogStore`. Erro fixo, sem o caminho.
    """
    try:
        info = path.lstat()
    except OSError:
        info = None
    if info is None or not stat.S_ISREG(info.st_mode):
        msg = "catalogo de datasources ausente ou inseguro"
        raise ConfigError(msg)


def _build_pgwire_application(
    raw: RawSettings, config_path: str
) -> tuple[Application, PgwireSettings]:
    """Ativacao local do PGWire: valida tudo e so entao compoe.

    Ordem: Admin/UI recusados -> settings PGWire (`pgwire.settings.resolve`)
    -> caminhos do catalogo resolvidos UMA vez -> recusa antecipada de store
    ou ancora ausente -> `build_application` (TLS, principal e o DNS limitado
    do bind antes de catalogo, config, upstream, bind e MCP). Abre o catalogo
    existente; nunca o cria, nunca migra o DSN legado, nunca escolhe alias e
    nunca cai no legado se o caminho moderno falhar.
    """
    secrets = EnvSecretProvider()
    if raw.get_raw(ADMIN_UI_ENABLED_ENV) == "1" or resolve_admin_settings(secrets) is not None:
        # A v2 so existe com catalogo e Admin HTTP juntos (D-093): recusar a
        # combinacao a mantem fora do alcance do `main`.
        msg = "pgwire: Admin API e UI nao podem ser ativadas junto com o PGWire"
        raise ConfigError(msg)
    from maskgw.pgwire.composition import PgwireComposition  # noqa: PLC0415
    from maskgw.pgwire.settings import resolve as resolve_pgwire_settings  # noqa: PLC0415
    from maskgw.runtime.datasource_service import DatasourceCatalogSettings  # noqa: PLC0415

    settings = resolve_pgwire_settings(raw, secrets)
    if settings is None:
        # A flag foi relida como desligada: falha fechada, sem cair no legado.
        msg = "pgwire: ativacao inconsistente"
        raise ConfigError(msg)
    store_path, anchor_path = resolve_catalog_paths(raw, config_path)
    _require_existing_regular_file(store_path)
    _require_existing_regular_file(anchor_path)
    application = build_application(
        config_path=config_path,
        datasource_catalog=DatasourceCatalogSettings(
            store_path=store_path, anchor_path=anchor_path
        ),
        pgwire=PgwireComposition(settings),
    )
    return application, settings


def _pgwire_listening_line(listener: PgwireListener | None, settings: PgwireSettings) -> str:
    """Metadata fechada do bind confirmado: host numerico e porta.

    Bind literal (ja validado como IP): `host:porta`, IPv6 entre colchetes.
    Bind por hostname: so a porta, porque o literal resolvido nao e publico
    fora do listener. Nenhum segredo.
    """
    if listener is None:
        msg = "pgwire: listener ausente"
        raise RuntimeError(msg)
    port = listener.port
    if settings.bind_is_hostname:
        return f"{PGWIRE_LISTENING_PORT_PREFIX}{port}\n"
    host = f"[{settings.bind}]" if ":" in settings.bind else settings.bind
    return f"{PGWIRE_LISTENING_PREFIX}{host}:{port}\n"


def _report(sink: TextIO, message: str, *, contained: bool) -> None:
    """Escreve uma mensagem fixa; `contained` = best-effort, nada escapa cru.

    Usado com `contained=True` so no caminho da ativacao PGWire; o legado
    mantem o comportamento anterior (`contained=False`).
    """
    if not contained:
        _write_stderr(sink, message)
        return
    with contextlib.suppress(BaseException):
        _write_stderr(sink, message)


def _abort_activation(sink: TextIO, application: Application) -> int:
    """Encerra uma ativacao ja composta que nao pode seguir: fecha e falha.

    Fecha a aplicacao (listener, catalogo, legado) ANTES de devolver, e nada
    escapa cru: nem a falha do `close()` nem a de escrever no stderr. O
    `STARTUP_FAILURE` fixo e tentado uma vez; um stderr quebrado nao impede o
    fechamento nem o codigo de saida 1.
    """
    with contextlib.suppress(BaseException):
        application.close()
    with contextlib.suppress(BaseException):
        _write_stderr(sink, STARTUP_FAILURE)
    return 1


def _compose(
    *, enabled: bool, raw: RawSettings, raw_settings: RawSettings | None, config_path: str
) -> tuple[Application, PgwireSettings | None]:
    """Compoe o processo: PGWire ligado, ou exatamente o caminho legado."""
    if enabled:
        # Ativacao local (2026-10-15): so esta funcao importa PGWire e
        # catalogo, e tudo e validado antes de qualquer recurso.
        return _build_pgwire_application(raw, config_path)
    # Desligado: exatamente o caminho anterior, inclusive as leituras normais
    # de UI e Admin.
    admin_ui_enabled = resolve_admin_ui_enabled(raw_settings)
    # Passo 1 da secao 9.2, antes de qualquer recurso: enable, token, bind e
    # porta. Sem admin habilitado devolve None, e o processo segue exatamente
    # como antes — nenhuma porta, nenhuma thread, nenhum lock.
    admin_http = resolve_admin_settings()
    application = build_application(
        config_path=config_path, admin_http=admin_http, admin_ui_enabled=admin_ui_enabled
    )
    return application, None


def main(*, stderr: TextIO | None = None, raw_settings: RawSettings | None = None) -> int:
    """Constroi, executa e encerra o processo. Devolve o codigo de saida."""
    sink = stderr if stderr is not None else sys.stderr
    config_path = os.environ.get(CONFIG_PATH_ENV, "").strip() or DEFAULT_CONFIG_PATH

    try:
        # D-110: a flag bruta e a primeira lida via `RawSettings` (o
        # `MASKGW_CONFIG` acima so define o caminho, sem abrir nada), sem
        # importar `maskgw.pgwire`. Falha ao le-la recusa o startup.
        raw = raw_settings if raw_settings is not None else EnvRawSettings()
        enabled = raw.get_raw(PGWIRE_ENABLED_ENV) == PGWIRE_ENABLED_VALUE
    except BaseException:
        _write_stderr(sink, STARTUP_FAILURE)
        return 1

    try:
        application, pgwire_settings = _compose(
            enabled=enabled, raw=raw, raw_settings=raw_settings, config_path=config_path
        )
    except BaseException:
        # Mensagem fixa: sem DSN, secret, SQL, valor, str(exc) ou traceback.
        # Um token curto e um bind recusado saem por aqui, indistinguiveis de
        # qualquer outra falha de startup. Na ativacao o relato e best-effort.
        _report(sink, STARTUP_FAILURE, contained=enabled)
        return 1

    # A linha do listener e calculada ANTES de qualquer metadata: se o bind
    # confirmado nao puder ser lido, a aplicacao fecha e o startup falha sem
    # saida parcial.
    pgwire_line: str | None = None
    if pgwire_settings is not None:
        try:
            pgwire_line = _pgwire_listening_line(application.pgwire_listener, pgwire_settings)
        except BaseException:
            return _abort_activation(sink, application)

    # Metadata fechada e segura em stderr. `stdout` permanece exclusivamente
    # com o protocolo MCP (§9.2 e §10.4).
    try:
        _write_stderr(sink, f"{REVISION_LOADED_PREFIX}{application.revision}\n")
        http_server = application.admin_http
        if http_server is not None:
            _write_stderr(sink, f"{ADMIN_LISTENING_PREFIX}{http_server.host}:{http_server.port}\n")
        if pgwire_line is not None:
            _write_stderr(sink, pgwire_line)
    except BaseException:
        if pgwire_settings is None:
            # Legado: comportamento anterior preservado, sem mudanca.
            raise
        # Ativacao: falha ao escrever a metadata nao deixa o listener vivo
        # nem escapa crua.
        return _abort_activation(sink, application)

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
        # Ativacao: o relato e best-effort, depois do fechamento; um stderr
        # quebrado nao escapa cru. Legado: comportamento anterior.
        _report(sink, RUNTIME_FAILURE, contained=pgwire_settings is not None)
        return 1
    return 0
