"""Politica de funcoes SQL.

Uma consulta que e um SELECT legitimo ainda pode executar funcoes com efeito
colateral: ler arquivos do servidor, abrir conexoes, alterar a sessao, derrubar
backends. O nome do nó AST nao distingue `lower(cpf)` de `pg_read_file('...')`.

## O limite de seguranca, declarado

Uma allowlist COMPLETA de funcoes seguras tornaria o Gateway inutilizavel:
`lower`, `substr`, `count`, `date_trunc`, `coalesce`, todos os operadores e
agregados teriam de ser enumerados, e qualquer omissao quebraria uma consulta
legitima. Ver docs/DECISIONS.md (D-027).

O modelo adotado inverte o default onde o risco se concentra:

- **Namespace `pg_`: deny por default.** Praticamente toda funcao perigosa do
  PostgreSQL vive nele (`pg_read_file`, `pg_ls_dir`, `pg_terminate_backend`,
  `pg_sleep`). Uma allowlist pequena e explicita libera as inofensivas.
- **Demais funcoes: allow por default, com denylist explicita** para as
  familias perigosas que nao usam o prefixo `pg_` (`dblink*`, `lo_*`,
  `query_to_xml*`, `set_config`).

Isso NAO e uma barreira completa, e o documento nao finge que seja. Uma funcao
definida pelo usuario com efeito colateral e nome comum passa. **A barreira
real e o privilegio**: role read-only, sem EXECUTE em funcoes perigosas, e sem
pertencer a `pg_read_server_files` ou `pg_execute_server_program`. Esta politica
e a primeira camada, nao a unica. Ver docs/SECURITY.md.

A politica e um dado imutavel e extensivel: `SqlPolicy` pode ser construida com
listas adicionais vindas da configuracao, sem alterar codigo.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

#: Relacoes do catalogo que carregam AMOSTRAS DOS DADOS, nao metadata.
#:
#: `pg_statistic` guarda valores reais das colunas em `stavaluesN`, e a view
#: `pg_stats` os expoe em `most_common_vals` e `histogram_bounds`. Uma unica
#: consulta devolve CPFs verdadeiros em claro: os nomes de coluna sao
#: `most_common_vals` e `histogram_bounds`, que nao casam regra nenhuma, e nao
#: ha coluna de origem a resolver. Medido na Fase 6. Ver D-039.
#:
#: Isto NAO e um bloqueio de `pg_catalog`: o resto do catalogo continua
#: acessivel, e a resolucao de proveniencia usa a conexao do Gateway, nao a SQL
#: do cliente, entao nada nela e afetado.
DENIED_RELATIONS: Final[frozenset[str]] = frozenset(
    {
        "pg_statistic",
        "pg_stats",
        "pg_stats_ext",
        "pg_stats_ext_exprs",
        "pg_statistic_ext",
        "pg_statistic_ext_data",
    }
)

#: Prefixo cujo namespace inteiro e negado por default.
PG_PREFIX: Final = "pg_"

#: Funcoes `pg_*` liberadas. Deliberadamente curta: sao operacoes de tipo e de
#: tamanho, sem acesso a arquivo, sessao, rede ou execucao de SQL.
DEFAULT_ALLOWED_PG_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "pg_typeof",
        "pg_size_pretty",
        "pg_column_size",
    }
)

#: Familias perigosas fora do namespace `pg_`, por prefixo de nome.
DEFAULT_DENIED_PREFIXES: Final[tuple[str, ...]] = (
    # Execucao de SQL remota ou arbitraria.
    "dblink",
    # Large objects: lo_import e lo_export leem e escrevem no filesystem.
    "lo_",
    # Executam SQL interno e devolvem o resultado como XML.
    "query_to_xml",
    "table_to_xml",
    "cursor_to_xml",
    "schema_to_xml",
    "database_to_xml",
)

#: Funcoes perigosas isoladas, fora do namespace `pg_`.
DEFAULT_DENIED_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        # Controle de sessao.
        "set_config",
        "setseed",
        # adminpack: escrita e remocao de arquivos no servidor.
        "lo_import",
        "lo_export",
    }
)


def canonical_function_name(name: str) -> str:
    """Chave semantica de um nome de funcao: `strip().casefold()`.

    Funcoes SQL sao case-insensitive e o parser do PostgreSQL ja normaliza o
    caixa e as aspas — `pg_read_file`, `PG_READ_FILE` e ` pg_read_file ` sao a
    MESMA funcao. Esta e a unica fonte da chave: a politica a usa para comparar,
    e a Admin API a usa para deduplicar `denied_functions` (D-059), de modo que
    duas grafias da mesma funcao nunca sejam persistidas como entradas distintas.
    """
    return name.strip().casefold()


def _normalize(names: Iterable[str]) -> frozenset[str]:
    """Nomes de funcao sao case-insensitive: o parser ja os normaliza."""
    return frozenset(canonical_function_name(name) for name in names if name.strip())


@dataclass(frozen=True, slots=True)
class SqlPolicy:
    """Politica imutavel de funcoes permitidas."""

    allowed_pg_functions: frozenset[str] = field(default=DEFAULT_ALLOWED_PG_FUNCTIONS)
    denied_functions: frozenset[str] = field(default=DEFAULT_DENIED_FUNCTIONS)
    denied_prefixes: tuple[str, ...] = field(default=DEFAULT_DENIED_PREFIXES)
    denied_relations: frozenset[str] = field(default=DENIED_RELATIONS)

    @classmethod
    def build(
        cls,
        *,
        extra_allowed_pg_functions: Iterable[str] = (),
        extra_denied_functions: Iterable[str] = (),
    ) -> SqlPolicy:
        """Politica default, estendida pela configuracao.

        A negacao vence: uma funcao presente nas duas listas fica negada.
        """
        return cls(
            allowed_pg_functions=DEFAULT_ALLOWED_PG_FUNCTIONS
            | _normalize(extra_allowed_pg_functions),
            denied_functions=DEFAULT_DENIED_FUNCTIONS | _normalize(extra_denied_functions),
        )

    def allows(self, function_name: str) -> bool:
        """Decide sobre o nome FINAL da funcao, ja sem o schema.

        O schema nao muda a decisao: `pg_catalog.pg_read_file`,
        `pg_read_file` e `PG_READ_FILE` sao a mesma funcao. O parser do
        PostgreSQL ja normaliza o caixa e as aspas.
        """
        name = function_name.casefold()

        if name in self.denied_functions:
            return False
        if any(name.startswith(prefix) for prefix in self.denied_prefixes):
            return False
        if name.startswith(PG_PREFIX):
            return name in self.allowed_pg_functions
        return True

    def allows_relation(self, relation_name: str) -> bool:
        """Decide sobre o nome da relacao, sem o schema.

        Como nas funcoes, o schema nao muda a decisao: `pg_catalog.pg_stats` e
        `pg_stats` sao a mesma relacao.
        """
        return relation_name.casefold() not in self.denied_relations


#: Politica usada quando nada e configurado.
DEFAULT_SQL_POLICY: Final = SqlPolicy()
