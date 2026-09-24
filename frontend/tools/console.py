"""Autoria privada do console v2 somente leitura (Fase 9, Etapa 5, D-097).

Chamado por `presentation.py` DEPOIS de toda a autoria da v1, para que IDs de
modelos, chamadas, views, editores, ligacoes e mensagens da v1 continuem os
mesmos. Nenhuma ligacao de papel (versao, identidade, ordem) e criada para os
modelos v2: a lista v2 tem uma revision por item, e o leitor da v1 exige uma
unica versao por resposta.

Tudo aqui e privado: rotulos, caminhos e textos chegam ao navegador somente
depois da entrada explicita, dentro de `presentation.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from maskgw.admin.http.v2.errors import DatasourceErrorCategory
from maskgw.admin.http.v2.routes import V2_READ_PATHS

PRIVATE = Path(__file__).resolve().parents[2] / "frontend/private"

#: Categorias que uma leitura v2 pode devolver (fronteira + v2).
V2_READ_ERRORS = (
    "UNAUTHORIZED",
    "HOST_NOT_ALLOWED",
    "CROSS_ORIGIN_REJECTED",
    "METHOD_NOT_ALLOWED",
    "NOT_FOUND",
    "INTERNAL_ERROR",
    DatasourceErrorCategory.CATALOG_BLOCKED.value,
    DatasourceErrorCategory.DATASOURCE_SERVICE_UNAVAILABLE.value,
)

TEST_WORDS = [
    {"value": "never", "text": "Nunca verificado"},
    {"value": "passed", "text": "Aprovado"},
    {"value": "failed", "text": "Reprovado"},
]
TLS_WORDS = [
    {"value": "disable", "text": "Sem TLS"},
    {"value": "require", "text": "TLS obrigatório"},
    {"value": "verify-full", "text": "TLS com verificação completa"},
]


def extend(wire, model, put, calls):
    """Acrescenta modelos, quatro leituras v2 e devolve a secao `console`."""
    extra = json.loads((PRIVATE / "wire-schemas-v2.json").read_text(encoding="utf-8"))
    for key, value in extra.items():
        if key in wire and wire[key] != value:
            raise ValueError("Conflicting definition")
        wire[key] = value
    variants = []
    for category in V2_READ_ERRORS:
        props = {
            "error": {"const": category},
            "detail": {"type": "string"},
            "current_revision": {"type": "integer", "minimum": 0},
        }
        variants.append(
            {
                "value": category,
                "ref": model(
                    "ReadError" + category,
                    {"type": "object", "properties": props, "required": ["error", "detail"]},
                ),
            }
        )
    error = put("ReadErrorEnvelope", {"type": "union", "tag": "error", "variants": variants})
    outputs = dict(
        zip(
            V2_READ_PATHS,
            (
                "V2StatusResponse",
                "DatasourceListResponse",
                "DatasourceResponse",
                "DatasourcePolicyResponse",
            ),
            strict=True,
        )
    )
    ids = {}
    for path, output in outputs.items():
        key = "c" + str(len(calls))
        identity = path.split("{")[1].split("}")[0] if "{" in path else None
        calls.append(
            {
                "id": key,
                "method": "GET",
                "path": path,
                "input": None,
                "output": model(output),
                "operation": "read",
                "identity": identity,
                "error": error,
            }
        )
        ids[output] = key
    counter = iter(range(10_000))

    def item(prefix, label, path, kind="text", wording=None):
        return {
            "id": prefix + str(next(counter)),
            "label": label,
            "path": path,
            "kind": kind,
            "wording": wording or [],
        }

    counts = ["datasources"]
    registry = ["registry"]
    summary = {
        "id": "s" + str(next(counter)),
        "label": "Painel",
        "call": ids["V2StatusResponse"],
        # Ordem = prioridade visual: as tres primeiras contagens sao as
        # metricas principais; as demais contagens sao detalhes; indicadores
        # sim/nao viram sinais de saude com texto proprio para cada estado.
        "figures": [
            item("f", "Datasources cadastrados", [*counts, "total"], "count"),
            item("f", "Publicados no runtime", [*counts, "published"], "count"),
            item("f", "Sessões abertas", [*registry, "sessions"], "count"),
            item("f", "Habilitados", [*counts, "enabled"], "count"),
            item("f", "Limite global de sessões", ["limits", "max_sessions"], "count"),
            item("f", "Gerações em drenagem", [*registry, "retired_open"], "count"),
            item("f", "Revisão do catálogo", ["catalog_revision"], "count"),
            item(
                "f",
                "Catálogo",
                ["catalog_available"],
                "flag",
                [
                    {"value": "true", "text": "Catálogo disponível"},
                    {"value": "false", "text": "Catálogo indisponível"},
                ],
            ),
            item(
                "f",
                "Escritas no catálogo",
                ["writes_blocked"],
                "flag",
                [
                    {"value": "false", "text": "Escritas liberadas"},
                    {"value": "true", "text": "Escritas bloqueadas até reinício"},
                ],
            ),
        ],
        "notes": [
            "Somente leitura: cadastro, edição e testes de conexão chegam na próxima etapa.",
            "Consultas por IDE (PGWire) e a ativação pelo operador ainda não existem.",
        ],
        "absent": (
            "O catálogo de datasources não está habilitado nesta execução. A política do "
            "Gateway continua disponível no grupo Política v1."
        ),
    }
    collection = {
        "id": "l" + str(next(counter)),
        "label": "Datasources",
        "call": ids["DatasourceListResponse"],
        "items": ["datasources"],
        "key": ["id"],
        "title": ["display_name"],
        "columns": [
            item("q", "Nome", ["display_name"]),
            item("q", "Alias", ["alias"]),
            item("q", "Habilitado", ["enabled"], "flag"),
            item("q", "Publicado", ["runtime", "published"], "flag"),
            item("q", "Revisão", ["revision"], "count"),
            item("q", "Última verificação", ["last_test", "status"], "text", TEST_WORDS),
        ],
        "search": "Buscar por nome ou alias",
        "searchable": [["display_name"], ["alias"]],
        "empty": (
            "Nenhum datasource cadastrado. O cadastro chega em uma próxima etapa; o "
            "protótipo de navegação está em Novo datasource."
        ),
        "nothing": "Nenhum datasource corresponde à busca.",
        "open": "Ver detalhes",
    }
    head = ["datasource"]
    rules = ["policy"]

    def tab(label, source, entries):
        return {"id": "a" + str(next(counter)), "label": label, "source": source, "entries": entries}

    detail = {
        "id": "d" + str(next(counter)),
        "call": ids["DatasourceResponse"],
        "extra": ids["DatasourcePolicyResponse"],
        "back": "Voltar para a lista",
        "tabs": [
            tab(
                "Visão geral",
                "main",
                [
                    item("r", "Nome", [*head, "display_name"]),
                    item("r", "Alias", [*head, "alias"]),
                    item("r", "Habilitado", [*head, "enabled"], "flag"),
                    item("r", "Publicado no runtime", [*head, "runtime", "published"], "flag"),
                    item("r", "Geração publicada", [*head, "runtime", "generation"], "count"),
                    item("r", "Sessões abertas", [*head, "runtime", "sessions"], "count"),
                    item("r", "Revisão", [*head, "revision"], "count"),
                    item(
                        "r", "Última verificação", [*head, "last_test", "status"], "text",
                        TEST_WORDS,
                    ),
                    item("r", "Verificado em", [*head, "last_test", "checked_at"]),
                ],
            ),
            tab(
                "Conexão",
                "main",
                [
                    item("r", "Host", [*head, "connection", "host"]),
                    item("r", "Porta", [*head, "connection", "port"]),
                    item("r", "Banco", [*head, "connection", "database"]),
                    item("r", "Usuário técnico", [*head, "connection", "username"]),
                    item(
                        "r", "TLS", [*head, "connection", "tls", "mode"], "text", TLS_WORDS
                    ),
                    item("r", "Nome TLS", [*head, "connection", "tls", "server_name"]),
                    item(
                        "r",
                        "Credencial configurada (o valor nunca é exibido)",
                        [*head, "credential", "configured"],
                        "flag",
                    ),
                    item(
                        "r", "Destino público permitido",
                        [*head, "destination_policy", "allow_public"], "flag",
                    ),
                    item(
                        "r", "Loopback permitido",
                        [*head, "destination_policy", "allow_loopback"], "flag",
                    ),
                    item(
                        "r", "Hosts autorizados",
                        [*head, "destination_policy", "allowed_hosts"], "list",
                    ),
                ],
            ),
            tab(
                "Masking",
                "extra",
                [
                    item("r", "Regras, na ordem de avaliação", [*rules, "masking"], "tree"),
                    item("r", "Exceções", [*rules, "exceptions"], "tree"),
                ],
            ),
            tab(
                "Limites",
                "main",
                [
                    item(
                        "r", "Timeout efetivo (ms)",
                        [*head, "effective_limits", "statement_timeout_ms"], "count",
                    ),
                    item(
                        "r", "Máximo efetivo de linhas",
                        [*head, "effective_limits", "max_rows"], "count",
                    ),
                    item(
                        "r", "Timeout configurado no datasource (ms)",
                        [*head, "limits", "statement_timeout_ms"], "count",
                    ),
                    item(
                        "r", "Máximo de linhas configurado",
                        [*head, "limits", "max_rows"], "count",
                    ),
                    item(
                        "r", "Máximo de sessões", [*head, "limits", "max_sessions"], "count"
                    ),
                ],
            ),
            tab(
                "SQL",
                "extra",
                [
                    item(
                        "r", "Funções negadas pela política",
                        [*rules, "sql", "denied_functions"], "list",
                    ),
                    item(
                        "r", "Funções permitidas (somente leitura)",
                        [*rules, "sql", "allowed_pg_functions"], "list",
                    ),
                    item(
                        "r", "Timeout da política (ms)",
                        [*rules, "database", "statement_timeout_ms"], "count",
                    ),
                    item(
                        "r", "Máximo de linhas da política",
                        [*rules, "database", "max_rows"], "count",
                    ),
                ],
            ),
        ],
        "gone": "Este datasource não existe mais. Volte para a lista e releia.",
    }
    steps = [
        ("Identificação", "Nome de apresentação e alias usado como dbname pelas IDEs."),
        ("Destino", "Host, porta e banco do PostgreSQL real, validados contra SSRF."),
        (
            "Credencial",
            "A senha técnica será pedida somente no envio real, nunca exibida depois. "
            "Neste protótipo nenhuma senha é solicitada.",
        ),
        ("TLS", "Modo TLS e nome esperado no certificado."),
        ("Política", "Regras de masking, exceções e limites deste datasource."),
        (
            "Teste",
            "O teste de conexão existe na API, mas não é executado neste protótipo. "
            "Nenhuma conexão é aberta.",
        ),
        (
            "Revisão",
            "Resumo antes de gravar. Nesta versão não há gravação: nada foi salvo ou "
            "testado.",
        ),
    ]
    guide = {
        "id": "g" + str(next(counter)),
        "label": "Novo datasource",
        "banner": (
            "Protótipo de navegação. Nada é salvo, nenhuma conexão é testada e nenhuma "
            "senha é solicitada nesta versão."
        ),
        "steps": [
            {"id": "p" + str(next(counter)), "label": label, "text": text}
            for label, text in steps
        ],
    }
    return {
        "brand": "Mask Gateway",
        "tagline": "Administração local",
        "main": "Datasources",
        "legacy": "Política v1",
        "yes": "Sim",
        "no": "Não",
        "blank": "Não informado",
        "failure": "Não foi possível ler agora. Tente novamente.",
        "unavailable": (
            "O catálogo está indisponível ou bloqueado, por exemplo depois de uma falha "
            "de gravação. É necessário reiniciar o Gateway."
        ),
        "summary": summary,
        "collection": collection,
        "detail": detail,
        "guide": guide,
    }
