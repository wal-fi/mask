"""Fase 7, Etapa 9 — regressoes adversariais da rodada corretiva.

Cada teste aqui nasceu de um defeito reproduzido contra o commit da Etapa 9 antes
da correcao. Os grupos, na ordem da revisao:

1. `confirm_comment_loss` estritamente booleano — `1`/`0`/`"true"` recusados;
2. `allowed_pg_functions` presente em QUALQUER forma (inclusive `null`) e
   `IMMUTABLE_FIELD`, detectado por presenca de campo, nao por valor;
3. `PUT /config` exige `sql.denied_functions`;
4. `rules:reorder` valida o formato de cada ID no schema; lista vazia e permutacao
   valida do conjunto vazio;
5. deduplicacao SEMANTICA em `PUT /sql`, pela mesma chave da politica;
7. robustez do backup da adocao sob fault injection.

Os grupos 1-5 e 7 nao precisam de banco: exercitam schema, mutacao e filesystem
diretamente. As provas end-to-end (grupo 6) exigem PostgreSQL real e vivem em
`test_admin_http_writes_e2e.py`.
"""

from __future__ import annotations

import io
import os
import stat
import tempfile
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from maskgw.admin.errors import AdminError, AdminErrorCategory
from maskgw.admin.http import mutations
from maskgw.admin.http.schemas import (
    AdoptRequest,
    ConfigReplaceRequest,
    ConfigReplaceSql,
    RuleReorderRequest,
    SqlWriteRequest,
)
from maskgw.config.filesystem import (
    ConfigFileStore,
    ConfigWriteError,
    FilesystemHooks,
)
from maskgw.config.loader import validate_file_config
from maskgw.config.models import MaskingFileConfig

RULE_ID = "rul_" + "a" * 32
SECOND_RULE_ID = "rul_" + "c" * 32
EXCEPTION_ID = "exc_" + "b" * 32


def _adopted_document() -> MaskingFileConfig:
    return validate_file_config(
        {
            "revision": 3,
            "masking": [
                {"id": RULE_ID, "match": "cpf", "transformer": "sha256"},
                {"id": SECOND_RULE_ID, "match": "email", "transformer": "md5"},
            ],
            "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
            "database": {"statement_timeout_ms": 2000, "max_rows": 10},
            "sql": {"allowed_pg_functions": ["pg_typeof"], "denied_functions": ["dblink_exec"]},
        }
    )


# --------------------------------------------------------------------------
# 1. confirm_comment_loss estritamente booleano
# --------------------------------------------------------------------------


class TestConfirmCommentLossEstrito:
    def test_true_booleano_e_aceito(self) -> None:
        req = AdoptRequest(expected_revision=0, confirm_comment_loss=True)
        assert req.confirm_comment_loss is True

    @pytest.mark.parametrize("value", [1, 0, "true", "false", None])
    def test_valores_nao_booleanos_sao_recusados(self, value: Any) -> None:
        """O inteiro `1` era aceito porque `1 == True` em Python — a regressao.

        `1`, `0`, `"true"` e `null` devem cair no schema, todos, antes de o
        serviço ser tocado.
        """
        with pytest.raises(ValidationError):
            AdoptRequest.model_validate({"expected_revision": 0, "confirm_comment_loss": value})

    def test_false_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            AdoptRequest.model_validate({"expected_revision": 0, "confirm_comment_loss": False})

    def test_campo_ausente_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            AdoptRequest.model_validate({"expected_revision": 0})


# --------------------------------------------------------------------------
# 2. allowed_pg_functions presente (qualquer forma) e IMMUTABLE_FIELD
# --------------------------------------------------------------------------


class TestAllowedPgFunctionsPorPresenca:
    @pytest.mark.parametrize(
        "value",
        [None, [], ["pg_read_file"], "x", {"a": 1}, True, 5],
    )
    def test_put_sql_com_allowed_presente_e_immutable(self, value: Any) -> None:
        """Presenca do campo, em QUALQUER forma, e imutavel — inclusive `null`.

        A regressao: `null` passava porque a mutacao checava `is not None`, entao
        um campo explicitamente presente com `null` era tratado como ausente.
        """
        request = SqlWriteRequest.model_validate(
            {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": value}
        )
        with pytest.raises(AdminError) as raised:
            mutations.replace_sql(request)(_adopted_document())
        assert raised.value.category is AdminErrorCategory.IMMUTABLE_FIELD

    def test_put_sql_sem_allowed_prossegue(self) -> None:
        request = SqlWriteRequest.model_validate(
            {"expected_revision": 3, "denied_functions": ["nova"]}
        )
        document = mutations.replace_sql(request)(_adopted_document())
        # Preserva o allowlist atual (nao o toca).
        assert document["sql"]["allowed_pg_functions"] == ["pg_typeof"]

    @pytest.mark.parametrize("value", [None, [], ["pg_read_file"], "x", {"a": 1}, True, 5])
    def test_put_config_com_allowed_presente_e_immutable(self, value: Any) -> None:
        request = ConfigReplaceRequest.model_validate(
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": [], "allowed_pg_functions": value},
            }
        )
        with pytest.raises(AdminError) as raised:
            mutations.replace_config(request)(_adopted_document())
        assert raised.value.category is AdminErrorCategory.IMMUTABLE_FIELD

    def test_put_config_sem_allowed_preserva(self) -> None:
        request = ConfigReplaceRequest.model_validate(
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": ["nova"]},
            }
        )
        document = mutations.replace_config(request)(_adopted_document())
        assert document["sql"]["allowed_pg_functions"] == ["pg_typeof"]


class TestAllowedPgFunctionsSerializavel:
    """O campo `allowed_pg_functions` e totalmente serializavel (sem sentinela).

    A regressao: o campo era `object = object()`, entao `model_json_schema()`
    emitia `PydanticJsonSchemaWarning` e `model_dump_json()` de um request sem o
    campo lancava `PydanticSerializationError`, alem de o sentinela vazar no
    `model_dump()`. Agora e `JsonValue | None`, e a presenca continua decidida
    so por `model_fields_set`.
    """

    def _sql_absent(self) -> SqlWriteRequest:
        return SqlWriteRequest.model_validate({"expected_revision": 3, "denied_functions": []})

    def _config_absent(self) -> ConfigReplaceRequest:
        return ConfigReplaceRequest.model_validate(
            {
                "expected_revision": 3,
                "masking": [{"match": "cpf", "transformer": "md5"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                "sql": {"denied_functions": []},
            }
        )

    def test_model_json_schema_sem_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SqlWriteRequest.model_json_schema()
            ConfigReplaceRequest.model_json_schema()

    def test_dump_e_dump_json_com_campo_ausente(self) -> None:
        for request in (self._sql_absent(), self._config_absent()):
            # Nenhum dos dois levanta, e o dump nao carrega objeto arbitrario.
            request.model_dump()
            rendered = request.model_dump_json()
            assert "object object" not in rendered
            assert "<object" not in rendered

    def test_nenhum_sentinela_no_dump(self) -> None:
        dumped = self._sql_absent().model_dump()
        # `allowed_pg_functions` ausente vira `None` no dump — um valor JSON, nao
        # um sentinela. Todos os valores do dump sao tipos JSON, sem objeto cru.
        assert dumped["allowed_pg_functions"] is None
        json_types = (type(None), bool, int, float, str, list, dict)
        assert all(isinstance(v, json_types) for v in dumped.values())

    def test_presenca_ainda_por_model_fields_set(self) -> None:
        assert self._sql_absent().allowed_pg_functions_present is False
        present = SqlWriteRequest.model_validate(
            {"expected_revision": 3, "denied_functions": [], "allowed_pg_functions": None}
        )
        assert present.allowed_pg_functions_present is True


# --------------------------------------------------------------------------
# 3. PUT /config exige sql.denied_functions
# --------------------------------------------------------------------------


class TestConfigExigeDeniedFunctions:
    def test_sql_sem_denied_functions_e_schema_invalid(self) -> None:
        """`sql: {}` num `PUT /config` apagaria as negacoes em silencio.

        `denied_functions` passou a ser obrigatorio na substituicao integral.
        """
        with pytest.raises(ValidationError):
            ConfigReplaceRequest.model_validate(
                {
                    "expected_revision": 3,
                    "masking": [{"match": "cpf", "transformer": "md5"}],
                    "exceptions": [],
                    "database": {"statement_timeout_ms": 1500, "max_rows": 7},
                    "sql": {},
                }
            )

    def test_config_replace_sql_exige_denied(self) -> None:
        with pytest.raises(ValidationError):
            ConfigReplaceSql.model_validate({})

    def test_denied_functions_presente_e_aceito(self) -> None:
        model = ConfigReplaceSql.model_validate({"denied_functions": []})
        assert model.denied_functions == []


# --------------------------------------------------------------------------
# 4. rules:reorder valida o formato de cada ID no schema
# --------------------------------------------------------------------------


class TestReorderIdFormato:
    def test_id_malformado_e_schema_invalid(self) -> None:
        """ID fora do formato canonico deve cair no schema, nao virar
        `CONFIG_INVALID` mais tarde."""
        with pytest.raises(ValidationError):
            RuleReorderRequest.model_validate({"expected_revision": 3, "rule_ids": ["nao-e-um-id"]})

    def test_lista_vazia_e_aceita_pelo_schema(self) -> None:
        """Permutacao completa do conjunto vazio: valida quando ha zero regras."""
        model = RuleReorderRequest.model_validate({"expected_revision": 3, "rule_ids": []})
        assert model.rule_ids == []

    def test_ids_bem_formados_sao_aceitos(self) -> None:
        model = RuleReorderRequest.model_validate(
            {"expected_revision": 3, "rule_ids": [RULE_ID, SECOND_RULE_ID]}
        )
        assert model.rule_ids == [RULE_ID, SECOND_RULE_ID]

    def test_lista_vazia_sobre_zero_regras_e_permutacao_valida(self) -> None:
        empty_doc = validate_file_config(
            {
                "revision": 3,
                "masking": [],
                "exceptions": [{"id": EXCEPTION_ID, "match": "tipo_cpf"}],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": []},
            }
        )
        request = RuleReorderRequest.model_validate({"expected_revision": 3, "rule_ids": []})
        document = mutations.reorder_rules(request)(empty_doc)
        assert document["masking"] == []

    @pytest.mark.parametrize(
        "rule_ids",
        [
            [RULE_ID, RULE_ID],  # duplicata (mesmo com formato valido)
            [RULE_ID],  # item ausente
            [RULE_ID, SECOND_RULE_ID, "rul_" + "9" * 32],  # item desconhecido, extra
            ["rul_" + "9" * 32, "rul_" + "8" * 32],  # dois desconhecidos, mesma cardinalidade
        ],
    )
    def test_permutacao_invalida_e_config_invalid(self, rule_ids: list[str]) -> None:
        """Formato valido, mas nao e permutacao completa dos IDs atuais."""
        request = RuleReorderRequest.model_validate({"expected_revision": 3, "rule_ids": rule_ids})
        with pytest.raises(AdminError) as raised:
            mutations.reorder_rules(request)(_adopted_document())
        assert raised.value.category is AdminErrorCategory.CONFIG_INVALID


# --------------------------------------------------------------------------
# 5. deduplicacao SEMANTICA em PUT /sql
# --------------------------------------------------------------------------


class TestDeduplicacaoSemantica:
    def _denied(self, existing: MaskingFileConfig, added: list[str]) -> list[str]:
        request = SqlWriteRequest.model_validate(
            {"expected_revision": 3, "denied_functions": added}
        )
        result: list[str] = mutations.replace_sql(request)(existing)["sql"]["denied_functions"]
        return result

    def test_caixa_diferente_nao_duplica(self) -> None:
        """`Foo`, `foo`, `FOO` colapsam: a politica normaliza com strip/casefold."""
        doc = _adopted_document()  # denied atual: ["dblink_exec"]
        result = self._denied(doc, ["DBLINK_EXEC", "Foo", "foo", "FOO"])
        # `dblink_exec` ja existia (preservado); so uma grafia de "foo" entra.
        assert result == ["dblink_exec", "Foo"]

    def test_espacos_nao_duplicam(self) -> None:
        doc = _adopted_document()
        result = self._denied(doc, [" dblink_exec ", "pg_sleep", " pg_sleep"])
        assert result == ["dblink_exec", "pg_sleep"]

    def test_duplicatas_no_mesmo_request(self) -> None:
        doc = _adopted_document()
        result = self._denied(doc, ["nova", "NOVA", "nova"])
        assert result == ["dblink_exec", "nova"]

    def test_repeticao_idempotente_do_request(self) -> None:
        """Aplicar o mesmo request duas vezes nao cresce a lista."""
        doc = _adopted_document()
        first = self._denied(doc, ["pg_sleep"])
        assert first == ["dblink_exec", "pg_sleep"]
        # Reaplica sobre um documento que ja tem pg_sleep.
        doc2 = validate_file_config(
            {
                "revision": 4,
                "masking": [{"id": RULE_ID, "match": "cpf", "transformer": "sha256"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": first},
            }
        )
        second = self._denied(doc2, ["PG_SLEEP", " pg_sleep "])
        assert second == ["dblink_exec", "pg_sleep"]

    def test_preserva_primeira_grafia_persistida(self) -> None:
        """A grafia ja persistida vence; a nova, so se for chave semantica nova."""
        doc = validate_file_config(
            {
                "revision": 3,
                "masking": [{"id": RULE_ID, "match": "cpf", "transformer": "sha256"}],
                "exceptions": [],
                "database": {"statement_timeout_ms": 2000, "max_rows": 10},
                "sql": {"denied_functions": ["Existente"]},
            }
        )
        result = self._denied(doc, ["EXISTENTE", "Nova"])
        assert result == ["Existente", "Nova"]


# --------------------------------------------------------------------------
# 7. robustez do backup da adocao sob fault injection
# --------------------------------------------------------------------------


@pytest.fixture
def store_dir() -> Iterator[Path]:
    directory = Path(tempfile.mkdtemp())
    config = directory / "masking.yaml"
    config.write_bytes(b"# comentario original\nmasking: []\n")
    if os.name == "posix":
        os.chmod(config, 0o600)
    yield directory


def _open_store(directory: Path, hooks: FilesystemHooks | None = None) -> ConfigFileStore:
    return ConfigFileStore.open(directory / "masking.yaml", hooks=hooks)


class TestBackupRobustez:
    ORIGINAL = b"conteudo original a preservar"

    def test_fsync_falho_vira_write_error_e_remove_incompleto(self, store_dir: Path) -> None:
        def boom(_fd: int) -> None:
            msg = "fsync injetado"
            raise OSError(msg)

        store = _open_store(store_dir, FilesystemHooks(file_fsync=boom))
        try:
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=100)
            assert not store.backup_path(100).exists()
        finally:
            store.close()

    def test_falha_apos_criacao_remove_incompleto_e_nao_deixa_fd(self, store_dir: Path) -> None:
        """Uma falha depois do `O_EXCL`, no ponto controlado apos a criacao,
        vira `CONFIG_WRITE_ERROR`, o incompleto e removido e nenhum fd fica
        aberto (contado por diferenca de fds do processo, no POSIX)."""

        def boom(_path: str) -> None:
            msg = "falha injetada depois da criacao"
            raise OSError(msg)

        store = _open_store(store_dir, FilesystemHooks(after_backup_create=boom))
        try:
            fds_before = _open_fd_count()
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=101)
            assert not store.backup_path(101).exists()
            if fds_before is not None:
                assert _open_fd_count() == fds_before
        finally:
            store.close()

    def test_backup_preexistente_nunca_e_tocado(self, store_dir: Path) -> None:
        """Nome ocupado -> falha, e o arquivo existente fica byte a byte igual."""
        store = _open_store(store_dir)
        try:
            existing = store.backup_path(102)
            existing.write_bytes(b"backup de alguem, intocavel")
            preexisting = existing.read_bytes()
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=102)
            assert existing.read_bytes() == preexisting
        finally:
            store.close()

    def test_backup_preexistente_intacto_mesmo_com_fault_hook(self, store_dir: Path) -> None:
        """Mesmo com um hook de falha armado, a colisao nunca remove o existente.

        A colisao acontece no `O_EXCL`, antes de o hook rodar: o arquivo alvo
        nao e nosso, e nada o toca.
        """

        def boom(_path: str) -> None:  # pragma: no cover - nao deve rodar
            msg = "nao deveria alcancar o hook numa colisao"
            raise OSError(msg)

        store = _open_store(store_dir, FilesystemHooks(after_backup_create=boom))
        try:
            existing = store.backup_path(103)
            existing.write_bytes(b"intocavel")
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=103)
            assert existing.read_bytes() == b"intocavel"
        finally:
            store.close()

    def test_principal_intacto_apos_falha_de_backup(self, store_dir: Path) -> None:
        def boom(_fd: int) -> None:
            msg = "fsync injetado"
            raise OSError(msg)

        store = _open_store(store_dir, FilesystemHooks(file_fsync=boom))
        try:
            main = store_dir / "masking.yaml"
            before = main.read_bytes()
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=104)
            assert main.read_bytes() == before
        finally:
            store.close()

    # -- falhas no stream: write, flush, close, short write, non-OSError ------

    @pytest.mark.parametrize("mode", ["write", "flush", "close", "short"])
    def test_falha_no_stream_vira_write_error(self, store_dir: Path, mode: str) -> None:
        """`write`, `flush`, fechamento e short write viram `CONFIG_WRITE_ERROR`.

        O stream e substituido diretamente (patch em `os.fdopen`), sem hooks de
        producao para essas operacoes. Para cada falha: `ConfigWriteError`,
        incompleto removido, principal intacto, backup preexistente intocado e
        nenhum fd vazado.
        """
        store = _open_store(store_dir)
        try:
            main = store_dir / "masking.yaml"
            before_main = main.read_bytes()
            # Um backup preexistente com OUTRO epoch, para provar que a falha nao
            # o toca.
            other = store.backup_path(900)
            other.write_bytes(b"backup vizinho intocavel")

            fds_before = _open_fd_count()
            with _bad_fdopen(mode), pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=201)

            assert not store.backup_path(201).exists()  # incompleto removido
            assert main.read_bytes() == before_main  # principal intacto
            assert other.read_bytes() == b"backup vizinho intocavel"
            if fds_before is not None:
                assert _open_fd_count() == fds_before  # nenhum fd vazado
        finally:
            store.close()

    def test_fsync_nao_derivado_de_oserror_vira_write_error(self, store_dir: Path) -> None:
        """Um `fsync` que levanta algo que NAO e `OSError` ainda vira
        `CONFIG_WRITE_ERROR`, com o incompleto removido."""

        def boom(_fd: int) -> None:
            msg = "fsync nao-OSError"
            raise ValueError(msg)

        store = _open_store(store_dir, FilesystemHooks(file_fsync=boom))
        try:
            fds_before = _open_fd_count()
            with pytest.raises(ConfigWriteError):
                store.write_backup(self.ORIGINAL, epoch=202)
            assert not store.backup_path(202).exists()
            if fds_before is not None:
                assert _open_fd_count() == fds_before
        finally:
            store.close()

    # -- excecoes de controle: cleanup roda, mas a original SOBE intacta -------

    @pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit, GeneratorExit])
    def test_excecao_de_controle_e_relancada_apos_cleanup(
        self, store_dir: Path, exc: type[BaseException]
    ) -> None:
        """`KeyboardInterrupt`/`SystemExit`/`GeneratorExit` NAO viram
        `ConfigWriteError`: o cleanup roda (incompleto removido, principal
        intacto, sem fd vazado), mas a excecao original e relancada."""

        def boom(_path: str) -> None:
            raise exc()

        store = _open_store(store_dir, FilesystemHooks(after_backup_create=boom))
        try:
            main = store_dir / "masking.yaml"
            before_main = main.read_bytes()
            fds_before = _open_fd_count()
            with pytest.raises(exc):
                store.write_backup(self.ORIGINAL, epoch=203)
            # Cleanup rodou mesmo com a excecao de controle.
            assert not store.backup_path(203).exists()
            assert main.read_bytes() == before_main
            if fds_before is not None:
                assert _open_fd_count() == fds_before
        finally:
            store.close()

    def test_backup_bem_sucedido_permanece(self, store_dir: Path) -> None:
        """Contraparte: sem falha, o backup existe, byte a byte e com 0600."""
        store = _open_store(store_dir)
        try:
            store.write_backup(self.ORIGINAL, epoch=105)
            backup = store.backup_path(105)
            assert backup.read_bytes() == self.ORIGINAL
            if os.name == "posix":
                assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        finally:
            store.close()


class _BadStream(io.RawIOBase):
    """Stream que falha num ponto escolhido, para testar o backup sem hooks.

    `write`, `flush` e `close` levantam `OSError`; `short` devolve menos bytes do
    que os escritos. Registra se `close` foi chamado, para o teste conferir que o
    stream e sempre fechado.
    """

    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode
        self.close_called = False

    def writable(self) -> bool:
        return True

    def write(self, b: Any) -> int:
        if self._mode == "write":
            msg = "write injetado"
            raise OSError(msg)
        if self._mode == "short":
            return len(b) - 1
        return len(b)

    def flush(self) -> None:
        if self._mode == "flush":
            msg = "flush injetado"
            raise OSError(msg)

    def close(self) -> None:
        self.close_called = True
        if self._mode == "close":
            msg = "close injetado"
            raise OSError(msg)


@contextmanager
def _bad_fdopen(mode: str) -> Iterator[None]:
    """Substitui `os.fdopen` no modulo do filesystem por um `_BadStream`.

    Fecha o descritor real que `write_backup` abriu (para nao vazar) e devolve o
    stream ruim no lugar. `filesystem.py` faz `import os` e chama `os.fdopen`,
    entao o patch no proprio `os.fdopen` alcanca o modulo.
    """

    def fake_fdopen(fd: int, *_args: Any, **_kwargs: Any) -> Any:
        os.close(fd)  # o fd real e nosso; fecha para nao vazar
        return _BadStream(mode)

    with patch("os.fdopen", fake_fdopen):
        yield


def _open_fd_count() -> int | None:
    """Numero de descritores abertos do processo, no POSIX; None fora dele."""
    fd_dir = Path("/proc/self/fd")
    if not fd_dir.exists():
        return None
    return len(list(fd_dir.iterdir()))
