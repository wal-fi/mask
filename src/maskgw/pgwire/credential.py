"""Credencial SCRAM-SHA-256 do principal unico e o verifier simulado (D-109).

A senha so atravessa `prepare_principal`, no startup: `make_auth_info` (API
publica da `scramp`, SASLprep + PBKDF2) e chamada duas vezes — para a senha
configurada e para o controle da senha vazia sob o mesmo salt. Nenhum PBKDF2
ocorre por tentativa de autenticacao. Depois disso o objeto guarda so salt,
iteracoes, StoredKey e ServerKey.

Usuario desconhecido recebe um verifier SIMULADO com o material publico
IDENTICO ao do principal — o mesmo salt e as mesmas iteracoes —, de modo que o
server-first nao distingue usuario existente de inexistente. So as chaves
privadas diferem: derivadas por HMAC de uma chave aleatoria do processo, nunca
autenticam (`real` e falso e entra na decisao final da troca).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

from scramp import ScramException, ScramMechanism  # type: ignore[import-untyped]

from maskgw.errors import ConfigError

SCRAM_MECHANISM: Final = "SCRAM-SHA-256"
#: O padrao do PostgreSQL (`scram_iterations`). Igual para real e simulado.
SCRAM_ITERATIONS: Final = 4096
SALT_BYTES: Final = 16
KEY_BYTES: Final = 32
MAX_USERNAME_BYTES: Final = 63

_INVALID_USERNAME: Final = "pgwire: usuario do principal invalido"
_REFUSED_CREDENTIAL_TEXT: Final = "pgwire: senha do principal recusada pelo SASLprep ou vazia"


class ScramVerifier:
    """Material publico e chaves de verificacao. Nunca a senha."""

    __slots__ = ("iterations", "real", "salt", "server_key", "stored_key")

    def __init__(
        self,
        *,
        salt: bytes,
        iterations: int,
        stored_key: bytes,
        server_key: bytes,
        real: bool,
    ) -> None:
        self.salt = salt
        self.iterations = iterations
        self.stored_key = stored_key
        self.server_key = server_key
        self.real = real

    def __repr__(self) -> str:
        return "ScramVerifier(<redigido>)"


class PrincipalCredential:
    """O principal unico do listener (§4.2) e o caminho simulado."""

    __slots__ = ("_mock_key", "_username", "_verifier")

    def __init__(self, username: str, verifier: ScramVerifier) -> None:
        self._username = username.encode("utf-8")
        self._verifier = verifier
        self._mock_key = secrets.token_bytes(KEY_BYTES)

    def __repr__(self) -> str:
        return "PrincipalCredential(<redigido>)"

    def verifier_for(self, startup_user: str) -> ScramVerifier:
        """Verifier do `user` do StartupMessage; simulado se nao for o principal.

        As duas derivacoes simuladas sao calculadas ANTES da selecao, nos dois
        caminhos: o trabalho de HMAC e o mesmo para usuario certo e errado.
        Isso iguala o custo local, e nao e promessa de tempo constante na rede.
        """
        candidate = startup_user.encode("utf-8")
        mock = ScramVerifier(
            salt=self._verifier.salt,
            iterations=self._verifier.iterations,
            stored_key=self._derive(b"stored", candidate),
            server_key=self._derive(b"server", candidate),
            real=False,
        )
        if hmac.compare_digest(candidate, self._username):
            return self._verifier
        return mock

    def _derive(self, label: bytes, user: bytes) -> bytes:
        return hmac.new(self._mock_key, label + b"\x00" + user, hashlib.sha256).digest()


def _valid_username(username: object) -> bool:
    if not isinstance(username, str) or not username or "\x00" in username:
        return False
    try:
        size = len(username.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return size <= MAX_USERNAME_BYTES


def _derive_real(password: str, salt: bytes) -> tuple[bytes, bytes] | None:
    """StoredKey e ServerKey pela `scramp`; `None` se o SASLprep recusar."""
    mechanism = ScramMechanism(SCRAM_MECHANISM)
    try:
        _, stored, server, _ = mechanism.make_auth_info(
            password, iteration_count=SCRAM_ITERATIONS, salt=salt
        )
    except ScramException:
        return None
    return bytes(stored), bytes(server)


def prepare_principal(username: str, password: str) -> PrincipalCredential:
    """Deriva a credencial do principal. Falha FECHADA, sem citar a entrada.

    Recusa: usuario vazio, com NUL ou acima de 63 bytes; senha vazia, recusada
    pelo SASLprep ou que normaliza para vazia (comparada com a derivacao da
    senha vazia sob o mesmo salt). Nao ha fallback para a senha crua.
    """
    if not _valid_username(username):
        raise ConfigError(_INVALID_USERNAME)
    if not isinstance(password, str) or not password:
        raise ConfigError(_REFUSED_CREDENTIAL_TEXT)
    salt = secrets.token_bytes(SALT_BYTES)
    real = _derive_real(password, salt)
    empty = _derive_real("", salt)
    if real is None or empty is None or hmac.compare_digest(real[0], empty[0]):
        raise ConfigError(_REFUSED_CREDENTIAL_TEXT)
    verifier = ScramVerifier(
        salt=salt,
        iterations=SCRAM_ITERATIONS,
        stored_key=real[0],
        server_key=real[1],
        real=True,
    )
    return PrincipalCredential(username, verifier)


__all__ = [
    "SCRAM_ITERATIONS",
    "PrincipalCredential",
    "ScramVerifier",
    "prepare_principal",
]
