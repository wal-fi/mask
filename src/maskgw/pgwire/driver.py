"""Driver de startup/autenticacao PGWire sobre um socket aceito (D-110, lote 2).

`run_startup_session(sock, ...)` conduz UMA conexao do primeiro byte ao
`Terminate`, na thread do chamador. Nao cria thread, nao fecha o socket (o
chamador fecha em `finally`) e nao libera vaga: a reserva de sessao e um
callback do dono futuro (o listener), que controla a contagem.

Sequencia:

1. Prazo ABSOLUTO de startup: um `Deadline` criado PELO DONO no accept e
   recebido pronto, valido ate o `ReadyForQuery`. O driver nunca cria nem
   reinicia esse prazo: atraso de agendamento da thread nao o renova, e bytes
   parciais tambem nao. Prazo ja vencido na entrada encerra sem nenhum IO.
2. Pacote inicial validado pelo framing da D-109 antes de ler o corpo.
   - `SSLRequest` (exatamente um): `S` so com contexto TLS valido; `N` so se
     TLS e opcional e nao ha contexto. Depois de `S`, o handshake roda sobre
     o mesmo socket (`TlsChannel`); se falhar, a conexao so termina, sem erro
     PostgreSQL em claro.
   - TLS obrigatorio e StartupMessage em claro: `08P01` fixo.
3. SCRAM-SHA-256 / -PLUS (D-109), com o binding do leaf do lote 1 quando ha
   TLS. O alias e consultado so por callback que le o selo (sem lease de
   registry nem upstream), e entra na MESMA decisao da prova: senha, usuario
   e alias errados dao o mesmo `28P01`. Um callback de alias que falha conta
   como alias recusado.
4. Depois da prova e ANTES do `AuthenticationOk`: `reserve_session()`.
   Recusa -> `53300`; erro do callback -> `XX000`. Ambos fixos, sem causa.
5. `SASLFinal` + `AuthenticationOk` + `ParameterStatus` fixos +
   `BackendKeyData` sintetico aleatorio + `ReadyForQuery 'I'`. A fachada
   (`server_version` 16.0) e sintetica: nao certifica IDE nem upstream.
6. Depois disso, com prazo de ociosidade ABSOLUTO (nao renovado por
   gotejamento): so `Terminate` (`X`, tamanho 4) encerra limpo; `X` com outro
   tamanho e `08P01`. Qualquer outro tipo (`Q`, `P`, `B`, `D`, `E`, `C`, `S`,
   `H`, `F`, ...) recebe `0A000` FATAL **sem** ler o corpo, sem executar nada
   e sem tocar registry ou upstream.

Nada aqui loga, e nenhuma senha, alias ou causa sai em erro.
"""

from __future__ import annotations

import secrets
import socket
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from maskgw.pgwire import framing
from maskgw.pgwire.credential import PrincipalCredential
from maskgw.pgwire.errors import PgwireErrorCategory, PgwireStartupError, error_response
from maskgw.pgwire.scram import ScramServerExchange
from maskgw.pgwire.tls import ServerTls
from maskgw.pgwire.transport import (
    Deadline,
    RawChannel,
    TlsChannel,
    TransportError,
    TransportFailure,
    TransportLimits,
)

#: Fachada sintetica enviada apos a autenticacao. Documentada na D-110.
PARAMETER_STATUS: Final[tuple[tuple[str, str], ...]] = (
    ("server_version", "16.0"),
    ("server_encoding", "UTF8"),
    ("client_encoding", "UTF8"),
    ("DateStyle", "ISO, MDY"),
    ("integer_datetimes", "on"),
    ("standard_conforming_strings", "on"),
)

_TERMINATE_LENGTH: Final = 4


class SessionOutcome(StrEnum):
    """Resultado fechado de uma sessao, para a contabilidade do dono."""

    TERMINATED = "terminated"
    AUTHENTICATION_FAILED = "authentication_failed"
    PROTOCOL_VIOLATION = "protocol_violation"
    FEATURE_NOT_SUPPORTED = "feature_not_supported"
    TOO_MANY_CONNECTIONS = "too_many_connections"
    INTERNAL_ERROR = "internal_error"
    EOF = "eof"
    TIMEOUT = "timeout"
    STOPPED = "stopped"
    IO = "io"
    TLS = "tls"
    LIMIT = "limit"


_FROM_CATEGORY: Final = {
    PgwireErrorCategory.AUTHENTICATION_FAILED: SessionOutcome.AUTHENTICATION_FAILED,
    PgwireErrorCategory.PROTOCOL_VIOLATION: SessionOutcome.PROTOCOL_VIOLATION,
    PgwireErrorCategory.FEATURE_NOT_SUPPORTED: SessionOutcome.FEATURE_NOT_SUPPORTED,
    PgwireErrorCategory.TOO_MANY_CONNECTIONS: SessionOutcome.TOO_MANY_CONNECTIONS,
    PgwireErrorCategory.INTERNAL_ERROR: SessionOutcome.INTERNAL_ERROR,
}
_FROM_FAILURE: Final = {
    TransportFailure.EOF: SessionOutcome.EOF,
    TransportFailure.TIMEOUT: SessionOutcome.TIMEOUT,
    TransportFailure.STOPPED: SessionOutcome.STOPPED,
    TransportFailure.IO: SessionOutcome.IO,
    TransportFailure.TLS: SessionOutcome.TLS,
    TransportFailure.LIMIT: SessionOutcome.LIMIT,
}


@dataclass(frozen=True, slots=True)
class DriverLimits:
    """Prazos da sessao (ms) e limites do transporte.

    `startup_deadline_ms` e usado pelo DONO para criar o `Deadline` no
    accept; o driver nao o le para criar prazo algum.
    """

    startup_deadline_ms: int
    idle_timeout_ms: int
    transport: TransportLimits = field(default_factory=TransportLimits)

    def __post_init__(self) -> None:
        for value in (self.startup_deadline_ms, self.idle_timeout_ms):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                msg = "prazo do driver pgwire invalido"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SessionResult:
    outcome: SessionOutcome
    tls_used: bool
    authenticated: bool


def _message(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("!I", len(body) + 4) + body


def _post_authentication() -> bytes:
    statuses = b"".join(
        _message(b"S", name.encode("ascii") + b"\x00" + value.encode("ascii") + b"\x00")
        for name, value in PARAMETER_STATUS
    )
    # Sintetico e aleatorio: nao ha cancelamento nesta etapa (Etapa 9).
    process_id = secrets.randbelow(2**31 - 1) + 1
    secret_key = secrets.randbits(32)
    key_data = _message(b"K", struct.pack("!II", process_id, secret_key))
    return statuses + key_data + _message(b"Z", b"I")


def _call_alias(callback: Callable[[str], bool], alias: str | None) -> bool:
    if not framing.valid_alias(alias) or alias is None:
        return False
    try:
        return callback(alias) is True
    except Exception:
        return False


def _call_reserve(callback: Callable[[], bool]) -> bool | None:
    """`True`/`False` da reserva; `None` se o callback falhou (sem causa)."""
    try:
        result = callback()
    except Exception:
        return None
    return result is True


class _Session:
    __slots__ = (
        "_alias_accepted",
        "_authenticated",
        "_channel",
        "_deadline",
        "_limits",
        "_principal",
        "_raw",
        "_reserve",
        "_tls",
        "_tls_required",
        "_tls_used",
    )

    def __init__(  # noqa: PLR0913 - colaboradores da sessao, keyword-only
        self,
        sock: socket.socket,
        *,
        principal: PrincipalCredential,
        tls: ServerTls | None,
        tls_required: bool,
        alias_accepted: Callable[[str], bool],
        reserve_session: Callable[[], bool],
        limits: DriverLimits,
        stop: Callable[[], bool],
        deadline: Deadline,
    ) -> None:
        if tls_required and tls is None:
            msg = "TLS exigido sem contexto"
            raise ValueError(msg)
        # `deadline` e keyword obrigatorio (sem default): omiti-lo e TypeError
        # do proprio Python; nao ha fallback que crie prazo novo.
        self._deadline = deadline
        self._raw = RawChannel(sock, stop=stop, limits=limits.transport)
        self._channel: RawChannel | TlsChannel = self._raw
        self._principal = principal
        self._tls = tls
        self._tls_required = tls_required
        self._alias_accepted = alias_accepted
        self._reserve = reserve_session
        self._limits = limits
        self._tls_used = False
        self._authenticated = False

    # -- leitura com framing antes do corpo --------------------------------

    def _read_initial(self) -> tuple[framing.InitialKind, bytes]:
        length = framing.initial_length(self._channel.recv_exact(4, self._deadline))
        body = self._channel.recv_exact(length - 4, self._deadline)
        return framing.classify_initial(body), body

    def _read_typed(self) -> bytes:
        size = framing.message_length(
            self._channel.recv_exact(5, self._deadline), expected_type=b"p"
        )
        return self._channel.recv_exact(size, self._deadline)

    def _send(self, data: bytes, deadline: Deadline | None = None) -> None:
        self._channel.send_all(data, deadline or self._deadline)

    # -- fases ---------------------------------------------------------------

    def _negotiate(self) -> bytes:
        kind, body = self._read_initial()
        if kind is framing.InitialKind.SSL_REQUEST:
            if self._tls is None:
                self._send(b"N")
            else:
                self._send(b"S")
                channel = TlsChannel(self._raw, self._tls.context)
                channel.handshake(self._deadline)
                self._channel = channel
                self._tls_used = True
            kind, body = self._read_initial()
            if kind is not framing.InitialKind.STARTUP:
                raise PgwireStartupError(PgwireErrorCategory.PROTOCOL_VIOLATION)
        elif self._tls_required:
            raise PgwireStartupError(PgwireErrorCategory.PROTOCOL_VIOLATION)
        return body

    def _authenticate(self, startup: framing.StartupMessage) -> bytes:
        binding = self._tls.channel_binding if self._tls_used and self._tls else None
        exchange = ScramServerExchange(
            self._principal.verifier_for(startup.user), channel_binding=binding
        )
        self._send(framing.authentication_sasl(exchange.mechanisms))
        mechanism, first = framing.parse_sasl_initial(self._read_typed())
        self._send(framing.authentication_sasl_continue(exchange.client_first(mechanism, first)))
        final = self._read_typed()
        accepted = _call_alias(self._alias_accepted, startup.database)
        return exchange.client_final(final, identity_accepted=accepted)

    def _after_ready(self) -> SessionOutcome:
        idle = Deadline(self._limits.idle_timeout_ms / 1000)
        kind = self._channel.recv_exact(1, idle)
        if kind != b"X":
            # Nenhum corpo e lido: a mensagem nao e interpretada nem executada.
            raise PgwireStartupError(PgwireErrorCategory.FEATURE_NOT_SUPPORTED)
        (length,) = struct.unpack("!I", self._channel.recv_exact(4, idle))
        if length != _TERMINATE_LENGTH:
            raise PgwireStartupError(PgwireErrorCategory.PROTOCOL_VIOLATION)
        return SessionOutcome.TERMINATED

    def _drive(self) -> SessionOutcome:
        # Prazo vencido ou parada pedida antes de qualquer IO: nada e lido.
        self._raw.check(self._deadline)
        startup = framing.parse_startup(self._negotiate())
        server_final = self._authenticate(startup)
        # O callback de alias pode ter consumido o prazo (ou a parada pode ter
        # sido pedida): nenhuma reserva nem AuthenticationOk depois disso.
        self._raw.check(self._deadline)
        reserved = _call_reserve(self._reserve)
        if reserved is None:
            raise PgwireStartupError(PgwireErrorCategory.INTERNAL_ERROR)
        if not reserved:
            raise PgwireStartupError(PgwireErrorCategory.TOO_MANY_CONNECTIONS)
        self._send(
            framing.authentication_sasl_final(server_final)
            + framing.authentication_ok()
            + _post_authentication()
        )
        self._authenticated = True
        return self._after_ready()

    def run(self) -> SessionResult:
        category: PgwireErrorCategory | None = None
        failure: TransportFailure | None = None
        outcome = SessionOutcome.TERMINATED
        try:
            outcome = self._drive()
        except PgwireStartupError as error:
            category = error.category
        except TransportError as error:
            failure = error.kind
        if category is not None:
            outcome = _FROM_CATEGORY[category]
            self._report(category)
        if failure is not None:
            outcome = _FROM_FAILURE[failure]
        return SessionResult(outcome, self._tls_used, self._authenticated)

    def _report(self, category: PgwireErrorCategory) -> None:
        """`ErrorResponse` fixo, melhor esforco, dentro do prazo da fase."""
        deadline = self._deadline
        if self._authenticated:
            deadline = Deadline(min(self._limits.idle_timeout_ms, 1000) / 1000)
        try:
            self._send(error_response(category), deadline)
        except TransportError:
            return
        # Sem isso, o close do chamador com entrada nao lida pode virar RST e
        # apagar o erro no cliente. O descarte nao interpreta nada.
        self._raw.linger()


def run_startup_session(  # noqa: PLR0913 - colaboradores da sessao, keyword-only
    sock: socket.socket,
    *,
    principal: PrincipalCredential,
    tls: ServerTls | None,
    tls_required: bool,
    alias_accepted: Callable[[str], bool],
    reserve_session: Callable[[], bool],
    limits: DriverLimits,
    stop: Callable[[], bool],
    deadline: Deadline,
) -> SessionResult:
    """Conduz uma conexao ja aceita. Nao fecha `sock` nem cria thread.

    `deadline` e OBRIGATORIO: o prazo absoluto que o dono criou no accept
    (com `limits.startup_deadline_ms`). O driver nao tem fallback que crie um
    prazo novo. Excecoes inesperadas (defeito) propagam; o chamador fecha o
    socket.
    """
    return _Session(
        sock,
        principal=principal,
        tls=tls,
        tls_required=tls_required,
        alias_accepted=alias_accepted,
        reserve_session=reserve_session,
        limits=limits,
        stop=stop,
        deadline=deadline,
    ).run()


__all__ = [
    "PARAMETER_STATUS",
    "DriverLimits",
    "SessionOutcome",
    "SessionResult",
    "run_startup_session",
]
