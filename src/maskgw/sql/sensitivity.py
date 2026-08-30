"""Analise de sensitividade por AST.

Complementa a proveniencia do PostgreSQL; nunca a enfraquece.

A proveniencia (Fase 3) cobre alias, subquery, CTE, JOIN, cast no-op e view.
Ela NAO cobre os casos em que o proprio PostgreSQL declara `ftable = 0`:
expressoes, agregados, literais e UNION. Ali a origem se perde, e ate a Fase 6
o valor saia em claro (F-01 e F-02 de `docs/SECURITY-REVIEW.md`).

Este modulo fecha essa lacuna sem construir um lineage engine. A observacao que
torna a correcao pequena: **as regras de masking sao globais por nome de
coluna**. Para decidir se `substr(c.cpf, 1, 11)` e sensivel nao e preciso saber
de qual tabela `cpf` vem — basta o nome, e ele esta na propria arvore. Se a
consulta e valida, o nome referenciado e um nome de coluna real.

O que se faz, por POSICAO do result set:

1. reunir os `ColumnRef` da expressao daquela posicao, em todos os ramos de um
   UNION;
2. resolver cada nome pela ordem normal do pipeline — EXCEPTION antes de
   MASKING, porque `substr(tipo_cpf, 1, 3)` nao deve virar sensivel;
3. se exatamente uma regra for encontrada, a posicao herda essa regra;
4. se duas regras DIFERENTES aparecerem, a consulta e recusada: nao ha
   transformer unico comprovavel (D-043);
5. se a expressao serializa uma linha inteira (`row_to_json(c)`), a consulta e
   recusada: nao ha `ColumnRef` por campo para provar coisa alguma (D-044).

Ha um passo a mais, e so um: os nomes que CTEs e subqueries do FROM exportam.
Sem ele, `WITH x AS (SELECT cpf AS d FROM cliente) SELECT d FROM x` esconderia
`cpf` atras do alias `d`. O mapa e construido aplicando a MESMA analise a cada
select interno e casando os nomes de saida. Nao ha resolucao de escopo: o mapa
e por nome, como todo o resto da politica. Ver D-046.
"""

from __future__ import annotations

from typing import Final

from pglast import ast, enums
from pglast.visitors import Skip, Visitor

from maskgw.errors import QueryRejected
from maskgw.masking.rules import MaskingPolicy

#: Motivos de rejeicao. Conjunto FIXO: nenhum nome vindo da consulta entra aqui.
AMBIGUOUS_SENSITIVE_EXPRESSION: Final = "expressao depende de mais de uma regra de protecao"
WHOLE_ROW_SERIALIZATION: Final = "expressao serializa uma linha inteira"

#: Sensibilidade por posicao do result set: indice da regra, ou None.
Sensitivity = tuple[int | None, ...]


def analyze_sensitivity(statement: ast.RawStmt, policy: MaskingPolicy) -> Sensitivity | None:
    """Sensibilidade de cada posicao de saida, ou None quando nao mapeavel.

    Devolver `None` significa "a AST nao ajuda aqui" — a proveniencia do
    PostgreSQL segue sozinha, exatamente como antes. Nunca significa "seguro".
    """
    select = statement.stmt
    if not isinstance(select, ast.SelectStmt):
        return None
    return _analyze_select(select, policy)


#: Profundidade maxima de aninhamento analisada. Alem dela a analise desiste e
#: a proveniencia do PostgreSQL segue sozinha — nunca se finge que e seguro.
MAX_DEPTH: Final = 16


def _analyze_select(
    select: ast.SelectStmt, policy: MaskingPolicy, depth: int = 0
) -> Sensitivity | None:
    """Sensibilidade por posicao de um `SelectStmt`, com os ramos achatados."""
    if depth > MAX_DEPTH:
        return None
    branches = _branches(select)
    widths = {len(branch.targetList or ()) for branch in branches}
    if len(widths) != 1:
        # Ramos com contagens diferentes: o PostgreSQL nem executaria.
        return None
    width = widths.pop()
    if width == 0:
        return None

    relations = _relation_names(select)
    exported = _exported_rules(select, policy, depth)
    return tuple(
        _position_rule(branches, index, policy, relations, exported) for index in range(width)
    )


class _InnerSelectCollector(Visitor):
    """Selects de CTEs e de subqueries do FROM, SO do nivel imediato.

    Ao encontrar um, para de descer (`Skip`): os niveis mais fundos sao
    tratados pela recursao de `_analyze_select`, uma vez cada. Descer aqui
    tambem faria a analise ser quadratica na profundidade do aninhamento — e
    uma consulta com 200 subqueries aninhadas travava o processo.
    """

    def __init__(self) -> None:
        super().__init__()
        self.selects: list[ast.SelectStmt] = []

    def visit(self, ancestors: object, node: object) -> object | None:  # noqa: ARG002
        inner: object | None = None
        if isinstance(node, ast.CommonTableExpr):
            inner = node.ctequery
        elif isinstance(node, ast.RangeSubselect):
            inner = node.subquery
        if isinstance(inner, ast.SelectStmt):
            self.selects.append(inner)
            return Skip
        return None


def _output_names(select: ast.SelectStmt) -> list[str | None]:
    """Nomes que um select exporta, na ordem. Vale o primeiro ramo do UNION."""
    branches = _branches(select)
    if not branches:
        return []
    names: list[str | None] = []
    for target in branches[0].targetList or ():
        if target.name:
            names.append(target.name)
            continue
        value = target.val
        if isinstance(value, ast.ColumnRef) and value.fields:
            last = value.fields[-1]
            field = getattr(last, "sval", None)
            names.append(field if isinstance(field, str) else None)
        else:
            names.append(None)
    return names


def _exported_rules(
    select: ast.SelectStmt, policy: MaskingPolicy, depth: int = 0
) -> dict[str, int]:
    """Nome exportado por CTE ou subquery -> regra que o cobre.

    E o unico passo que atravessa niveis, e ele nao resolve escopo: casa por
    nome, como o resto da politica. Um mapeamento a mais mascara demais, nunca
    de menos. Ver D-046.
    """
    collector = _InnerSelectCollector()
    collector(select)

    exported: dict[str, int] = {}
    for inner in collector.selects:
        rules = _analyze_select(inner, policy, depth + 1)
        if rules is None:
            continue
        for name, rule in zip(_output_names(inner), rules, strict=False):
            if name and rule is not None:
                exported.setdefault(name.casefold(), rule)
    return exported


def _branches(select: ast.SelectStmt) -> list[ast.SelectStmt]:
    """Ramos de um set operation, achatados. UNION aninhado incluido."""
    if select.op == enums.SetOperation.SETOP_NONE:
        return [select]
    branches: list[ast.SelectStmt] = []
    for side in (select.larg, select.rarg):
        if isinstance(side, ast.SelectStmt):
            branches.extend(_branches(side))
    return branches


def _position_rule(
    branches: list[ast.SelectStmt],
    index: int,
    policy: MaskingPolicy,
    relations: frozenset[str],
    exported: dict[str, int],
) -> int | None:
    """Regra que cobre a posicao `index`, olhando TODOS os ramos.

    Basta um ramo ter origem sensivel comprovada para a posicao inteira ser
    sensivel: um UNION mistura as linhas dos ramos numa coluna so.
    """
    found: set[int] = set()
    for branch in branches:
        targets = branch.targetList or ()
        if index >= len(targets):
            continue
        for name in _referenced_names(targets[index], relations):
            rule = _rule_for(name, policy, exported)
            if rule is not None:
                found.add(rule)

    if len(found) > 1:
        # Duas classes sensiveis diferentes na mesma posicao: nao ha
        # transformer unico comprovavel. Recusar em vez de escolher.
        raise QueryRejected(AMBIGUOUS_SENSITIVE_EXPRESSION)
    return found.pop() if found else None


class _ColumnRefCollector(Visitor):
    """Reune os `ColumnRef` de uma expressao, inclusive dentro de subselects."""

    def __init__(self) -> None:
        super().__init__()
        self.names: list[tuple[str, ...]] = []

    def visit(self, ancestors: object, node: object) -> None:  # noqa: ARG002
        if isinstance(node, ast.ColumnRef):
            fields = tuple(
                "*" if isinstance(field, ast.A_Star) else str(getattr(field, "sval", ""))
                for field in (node.fields or ())
            )
            self.names.append(fields)


def _referenced_names(target: ast.ResTarget, relations: frozenset[str]) -> list[str]:
    """Nomes de coluna referenciados por um alvo da SELECT list.

    Um `ColumnRef` de um unico campo que casa o nome ou o alias de uma relacao
    do FROM nao e uma coluna: e a LINHA INTEIRA, como em `row_to_json(c)`.
    Nao ha como provar nada sobre ela campo a campo, entao a consulta cai.
    """
    collector = _ColumnRefCollector()
    collector(target)

    names: list[str] = []
    for fields in collector.names:
        if not fields or fields[-1] == "*":
            # `SELECT *` e `SELECT c.*`: a posicao nem sequer mapeia 1:1.
            continue
        if len(fields) == 1 and fields[0].casefold() in relations:
            raise QueryRejected(WHOLE_ROW_SERIALIZATION)
        names.append(fields[-1])
    return names


class _RelationCollector(Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def visit(self, ancestors: object, node: object) -> None:  # noqa: ARG002
        if isinstance(node, ast.RangeVar):
            if node.relname:
                self.names.add(node.relname.casefold())
            alias = node.alias
            if alias is not None and alias.aliasname:
                self.names.add(alias.aliasname.casefold())


def _relation_names(select: ast.SelectStmt) -> frozenset[str]:
    """Nomes e aliases das relacoes da consulta, para detectar linha inteira."""
    collector = _RelationCollector()
    collector(select)
    return frozenset(collector.names)


def _rule_for(name: str, policy: MaskingPolicy, exported: dict[str, int]) -> int | None:
    """Regra que cobre um nome de coluna REFERENCIADO, ou None.

    Segue a ordem do pipeline: exception antes de masking. O nome aqui vem de
    uma referencia na consulta, e uma referencia so e valida se a coluna existe
    — nao e um alias escolhido pelo atacante. Avaliar a exception sobre ele e,
    portanto, legitimo.
    """
    for exception in policy.exceptions:
        if exception.spec.matches(name):
            return None
    for rule in policy.rules:
        if rule.spec.matches(name):
            return rule.index
    return exported.get(name.casefold())
