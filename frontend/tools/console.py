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
    {"value": "never", "text": "Nunca verificado", "tone": "neutral"},
    {"value": "passed", "text": "Aprovado", "tone": "good"},
    {"value": "failed", "text": "Reprovado", "tone": "attention"},
]
TLS_WORDS = [
    {"value": "disable", "text": "Sem TLS", "tone": "attention"},
    {"value": "require", "text": "TLS obrigatório", "tone": "neutral"},
    {"value": "verify-full", "text": "Verificação completa", "tone": "good"},
]
# Sim/nao de estado: ausencia de habilitacao/publicacao nao e erro, e neutra.
ON_WORDS = [
    {"value": "true", "text": "Sim", "tone": "good"},
    {"value": "false", "text": "Não", "tone": "neutral"},
]
# Permissoes de destino: o texto diz o efeito; nenhum dos dois estados e falha.
PERMIT_WORDS = [
    {"value": "true", "text": "Permitido", "tone": "neutral"},
    {"value": "false", "text": "Recusado", "tone": "neutral"},
]

# Textos da apresentação privada. O JS distribuído só interpreta caminhos e
# rótulos; não conhece campos, valores ou transformers da política.
RULE_WORDS = [
    {"value": "@item", "text": "Regra"},
    {"value": "@headline", "text": "match"},
    {"value": "@headline-label", "text": "Padrão da coluna"},
    {
        "value": "@hint",
        "text": "Exceções têm prioridade; depois vale a primeira regra correspondente.",
    },
    {"value": "@empty", "text": "Nenhuma regra de mascaramento cadastrada."},
    {"value": "@empty-object", "text": "Sem parâmetros adicionais."},
    {"value": "key:mode", "text": "Correspondência"},
    {"value": "key:case_sensitive", "text": "Maiúsculas/minúsculas"},
    {"value": "key:transformer", "text": "Transformação"},
    {"value": "key:config", "text": "Parâmetros"},
    {"value": "key:value", "text": "Valor substituto"},
    {"value": "key:length", "text": "Comprimento"},
    {"value": "key:pattern", "text": "Padrão da expressão"},
    {"value": "key:replacement", "text": "Texto substituto"},
    {"value": "key:strategy", "text": "Estratégia"},
    {"value": "key:preserve_length", "text": "Preservar comprimento"},
    {"value": "value:mode:contains", "text": "O nome da coluna contém o padrão"},
    {"value": "value:mode:exact", "text": "O nome da coluna é igual ao padrão"},
    {"value": "value:case_sensitive:false", "text": "Ignora diferenças"},
    {"value": "value:case_sensitive:true", "text": "Diferencia"},
    {"value": "value:transformer:fixed", "text": "Valor fixo"},
    {"value": "value:transformer:hmac_sha256", "text": "HMAC-SHA-256"},
    {"value": "value:transformer:md5", "text": "MD5"},
    {"value": "value:transformer:sha256", "text": "SHA-256"},
    {"value": "value:transformer:sha512", "text": "SHA-512"},
    {"value": "value:transformer:regex", "text": "Expressão regular"},
    {"value": "value:transformer:random", "text": "Valor aleatório"},
    {"value": "value:transformer:truncate", "text": "Truncar"},
]
EXCEPTION_WORDS = [
    {"value": "@item", "text": "Exceção"},
    {"value": "@headline", "text": "match"},
    {"value": "@headline-label", "text": "Padrão da coluna"},
    {"value": "@hint", "text": "Uma coluna coberta por exceção mantém o valor original."},
    {"value": "@empty", "text": "Nenhuma exceção cadastrada."},
    {"value": "key:mode", "text": "Correspondência"},
    {"value": "key:case_sensitive", "text": "Maiúsculas/minúsculas"},
    {"value": "value:mode:contains", "text": "O nome da coluna contém o padrão"},
    {"value": "value:mode:exact", "text": "O nome da coluna é igual ao padrão"},
    {"value": "value:case_sensitive:false", "text": "Ignora diferenças"},
    {"value": "value:case_sensitive:true", "text": "Diferencia"},
]

# Politica v1: regras e excecoes com posicao e ID, que so a v1 le. A ordem das
# chaves declaradas e a ordem de exibicao dentro de cada cartao.
V1_ITEM_WORDS = [
    # Chave de identidade: o cartao recebe as acoes do item com o MESMO ID.
    {"value": "@identity", "text": "id"},
    {"value": "key:position", "text": "Posição na avaliação"},
    {"value": "key:id", "text": "Identificador"},
    {"value": "value:id:null", "text": "Ainda sem ID: a adoção atribui"},
]
ADOPTION_WORDS = [
    {"value": "true", "text": "Adotada", "tone": "good"},
    {"value": "false", "text": "Não adotada", "tone": "neutral"},
]
ADOPTION_NOTE = (
    "“Não adotada” é o estado inicial: o Gateway aplica o arquivo normalmente; editar por "
    "esta interface exige a adoção (em Configuração), que atribui IDs e cria a revisão 1."
)
SECRET_WORDS = [
    {"value": "configured", "text": "Configurado", "tone": "good"},
    {"value": "missing", "text": "Ausente", "tone": "attention"},
]
PIPELINE_WORDS = [
    {
        "value": "DERIVED",
        "text": "Derivada: a análise do SQL provou dependência de coluna sensível → transformação",
    },
    {"value": "EXCEPTION", "text": "Exceção pelo nome autoritativo → valor original"},
    {"value": "MASKING", "text": "Regra de masking (nome de saída ou de origem) → transformação"},
    {"value": "ORIGINAL", "text": "Sem correspondência → valor original"},
]
VALIDATOR_WORDS = [
    {"value": "exactly one executable statement", "text": "Exatamente um comando executável"},
    {
        "value": "the root node must be a SELECT statement",
        "text": "O comando principal precisa ser um SELECT",
    },
    {
        "value": "no other statement node anywhere in the tree, including nested CTEs",
        "text": "Nenhum outro comando em qualquer ponto, inclusive em CTEs aninhadas",
    },
    {
        "value": "INTO and locking clauses are rejected at any depth",
        "text": "Cláusulas INTO e de bloqueio (FOR UPDATE e similares) são recusadas em qualquer nível",
    },
]


def _v1_pages(views, item):
    """Apresentacao das seis vistas v1 aprovadas, localizadas pelo rotulo selado.

    Cada pagina so arruma e nomeia os campos que as leituras `read` da vista ja
    exibiam; `protocol.py` recusa campo omitido ou campo fora dessas leituras.
    """
    by_label = {view["label"]: view["id"] for view in views}
    rule_words = [*RULE_WORDS, *V1_ITEM_WORDS]
    exception_words = [*EXCEPTION_WORDS, *V1_ITEM_WORDS]

    def section(label, entries, note=None):
        body = {"label": label, "entries": entries}
        if note is not None:
            body["note"] = note
        return body

    def adoption():
        return item("w", "Adoção", ["adopted"], "flag", ADOPTION_WORDS)

    def published():
        return item("w", "Revisão publicada", ["revision"], "count")

    return [
        {
            "view": by_label["Visão geral"],
            "sections": [
                section("Configuração em uso", [adoption(), published()], ADOPTION_NOTE),
                section(
                    "Atividade desde o início do processo",
                    [
                        item(
                            "w",
                            "Consultas recebidas",
                            ["counters", "queries_total"],
                            "count",
                            show="metric",
                        ),
                        item(
                            "w",
                            "Operações administrativas",
                            ["counters", "admin_operations_total"],
                            "count",
                            show="metric",
                        ),
                    ],
                    "Contadores em memória, zerados a cada reinício. Incluem as consultas "
                    "e as escritas ou recargas recusadas.",
                ),
                section(
                    "Runtime",
                    [
                        item("w", "Revisão em execução", ["runtime", "revision"], "count"),
                        item(
                            "w",
                            "Versões anteriores ainda abertas",
                            ["runtime", "retired_runtimes_open"],
                            "count",
                        ),
                    ],
                    "Depois de uma troca de configuração, a versão anterior fica aberta só até "
                    "terminarem as consultas que já a usavam (no máximo uma).",
                ),
                section(
                    "Segredos",
                    [
                        item(
                            "w",
                            "Token administrativo",
                            ["secrets", "admin_token"],
                            "text",
                            SECRET_WORDS,
                        ),
                        item(
                            "w",
                            "Conexão com o PostgreSQL (DSN)",
                            ["secrets", "database_dsn"],
                            "text",
                            SECRET_WORDS,
                        ),
                        item(
                            "w",
                            "Chave HMAC",
                            ["secrets", "hmac_sha256_key"],
                            "text",
                            [
                                SECRET_WORDS[0],
                                {"value": "missing", "text": "Ausente", "tone": "neutral"},
                            ],
                        ),
                    ],
                    "Só a situação é exibida; os valores nunca saem do servidor. Sem token ou "
                    "DSN o Gateway não inicia. A chave HMAC só é exigida por regras que usam "
                    "HMAC-SHA-256.",
                ),
            ],
        },
        {
            "view": by_label["Configuração"],
            "sections": [
                section(
                    "Estado",
                    [
                        adoption(),
                        published(),
                        item(
                            "w",
                            "Revisão registrada no documento",
                            ["config", "revision"],
                            "count",
                        ),
                    ],
                    "Documento declarado, somente leitura. As alterações são feitas em "
                    "Regras, Exceções, Banco e Política SQL.",
                ),
                section(
                    "Regras de masking",
                    [
                        item(
                            "w",
                            "Na ordem de avaliação",
                            ["config", "masking"],
                            "tree",
                            rule_words,
                        )
                    ],
                ),
                section(
                    "Exceções",
                    [
                        item(
                            "w",
                            "Exceções declaradas",
                            ["config", "exceptions"],
                            "tree",
                            exception_words,
                        )
                    ],
                ),
                section(
                    "Limites do banco",
                    [
                        item(
                            "w",
                            "Timeout de consulta (ms)",
                            ["config", "database", "statement_timeout_ms"],
                            "count",
                        ),
                        item("w", "Máximo de linhas", ["config", "database", "max_rows"], "count"),
                    ],
                ),
                section(
                    "SQL",
                    [
                        item(
                            "w",
                            "Funções negadas adicionalmente",
                            ["config", "sql", "denied_functions"],
                            "list",
                            [{"value": "@empty", "text": "Nenhuma função negada adicionalmente."}],
                        ),
                        item(
                            "w",
                            "Funções pg_* liberadas",
                            ["config", "sql", "allowed_pg_functions"],
                            "list",
                            [{"value": "@empty", "text": "Nenhuma função pg_* liberada."}],
                        ),
                    ],
                ),
            ],
        },
        {
            "view": by_label["Regras"],
            "sections": [
                section("Estado", [adoption(), published()]),
                section(
                    "Regras de masking",
                    [item("w", "Na ordem de avaliação", ["rules"], "tree", rule_words)],
                ),
            ],
        },
        {
            "view": by_label["Exceções"],
            "sections": [
                section("Estado", [adoption(), published()]),
                # O titulo da pagina ja e "Exceções": o grupo nao repete o nome.
                section(
                    "Exceções cadastradas",
                    [item("w", "Na ordem de avaliação", ["exceptions"], "tree", exception_words)],
                    "A exceção compara só o nome autoritativo da coluna (a origem, quando "
                    "existe); um alias na consulta não a ativa.",
                ),
            ],
        },
        {
            "view": by_label["Banco"],
            "sections": [
                section(
                    "Limites declarados",
                    [
                        item(
                            "w",
                            "Timeout de consulta (ms)",
                            ["config", "database", "statement_timeout_ms"],
                            "count",
                            show="metric",
                        ),
                        item(
                            "w",
                            "Máximo de linhas",
                            ["config", "database", "max_rows"],
                            "count",
                            show="metric",
                        ),
                    ],
                    "Aplicados pelo PostgreSQL na conexão do Gateway e conferidos depois de "
                    "conectar.",
                ),
                section("Estado", [published()]),
            ],
        },
        {
            "view": by_label["Política SQL"],
            "sections": [
                section(
                    "Como cada coluna é tratada",
                    [
                        item(
                            "w",
                            "Ordem de decisão",
                            ["pipeline"],
                            "list",
                            PIPELINE_WORDS,
                            show="ordered",
                        ),
                        item(
                            "w",
                            "Coluna sem correspondência",
                            ["unmatched_policy"],
                            "text",
                            [{"value": "allow", "text": "Passa em claro (sem masking)"}],
                        ),
                    ],
                    "A primeira etapa que se aplica decide o valor de cada coluna do resultado.",
                ),
                section(
                    "Validação do SQL",
                    [
                        item(
                            "w",
                            "Regras do validador",
                            ["validator_rules"],
                            "list",
                            VALIDATOR_WORDS,
                            show="ordered",
                        )
                    ],
                ),
                section(
                    "Funções e relações",
                    [
                        item(
                            "w",
                            "Funções pg_* por padrão",
                            ["pg_namespace_default"],
                            "text",
                            [{"value": "deny", "text": "Negadas, exceto as liberadas"}],
                        ),
                        item(
                            "w",
                            "Funções pg_* liberadas",
                            ["allowed_pg_functions"],
                            "list",
                            [{"value": "@empty", "text": "Nenhuma liberada."}],
                        ),
                        item(
                            "w",
                            "Funções negadas",
                            ["denied_functions"],
                            "list",
                            [{"value": "@empty", "text": "Nenhuma função negada."}],
                        ),
                        item(
                            "w",
                            "Prefixos negados",
                            ["denied_function_prefixes"],
                            "list",
                            [{"value": "@empty", "text": "Nenhum prefixo negado."}],
                        ),
                        item(
                            "w",
                            "Relações negadas",
                            ["denied_relations"],
                            "list",
                            [{"value": "@empty", "text": "Nenhuma relação negada."}],
                        ),
                    ],
                ),
                section(
                    "Sessão no PostgreSQL",
                    [
                        item(
                            "w",
                            "Conexão",
                            ["session", "read_only"],
                            "flag",
                            [
                                {"value": "true", "text": "Somente leitura", "tone": "good"},
                                {"value": "false", "text": "Com escrita", "tone": "attention"},
                            ],
                        ),
                        item(
                            "w",
                            "Timeout de consulta",
                            ["session", "statement_timeout_enforced_by"],
                            "text",
                            [{"value": "postgresql", "text": "Aplicado pelo PostgreSQL"}],
                        ),
                        item(
                            "w",
                            "Metadados de origem das colunas",
                            ["session", "provenance_capability_required"],
                            "flag",
                            [
                                {"value": "true", "text": "Exigidos", "tone": "good"},
                                {"value": "false", "text": "Não exigidos", "tone": "attention"},
                            ],
                        ),
                    ],
                ),
                section(
                    "Edição",
                    [
                        item(
                            "w",
                            "Estas proteções",
                            ["editable"],
                            "flag",
                            [
                                {"value": "false", "text": "Somente exibição", "tone": "neutral"},
                                {"value": "true", "text": "Editáveis", "tone": "neutral"},
                            ],
                        ),
                        published(),
                    ],
                    "A política efetiva é exibida, não editada. O formulário abaixo altera só a "
                    "lista de funções negadas do documento; funções pg_* liberadas não mudam "
                    "por esta interface.",
                ),
            ],
        },
    ]


def extend(wire, model, put, calls, views=()):
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

    def item(prefix, label, path, kind="text", wording=None, show="fact", blank=None):
        figure = {
            "id": prefix + str(next(counter)),
            "label": label,
            "path": path,
            "kind": kind,
            "wording": wording or [],
            "show": show,
        }
        if blank is not None:
            figure["blank"] = blank
        return figure

    def group(label, entries, note=None):
        """Grupo visual; devolve (grupo, itens) para compor a aba."""
        block = {"label": label, "members": [entry["id"] for entry in entries]}
        if note is not None:
            block["note"] = note
        return block, entries

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
                    {"value": "true", "text": "Catálogo disponível", "tone": "good"},
                    {"value": "false", "text": "Catálogo indisponível", "tone": "attention"},
                ],
            ),
            item(
                "f",
                "Escritas no catálogo",
                ["writes_blocked"],
                "flag",
                [
                    {"value": "false", "text": "Escritas liberadas", "tone": "good"},
                    {
                        "value": "true",
                        "text": "Escritas bloqueadas até reinício",
                        "tone": "attention",
                    },
                ],
            ),
        ],
        "notes": [
            "Somente leitura: cadastro, edição e testes de conexão dependem de uma etapa futura.",
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
            # Identidade primeiro, depois estado; em tela estreita viram pares.
            item("q", "Alias", ["alias"], show="code"),
            item("q", "Revisão", ["revision"], "count"),
            item("q", "Habilitado", ["enabled"], "flag", ON_WORDS),
            item("q", "Publicado", ["runtime", "published"], "flag", ON_WORDS),
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

    def tab(label, source, entries, blocks=()):
        """Aba; com grupos, cada item pertence a exatamente um grupo."""
        body = {"id": "a" + str(next(counter)), "label": label, "source": source}
        if blocks:
            body["groups"] = [block for block, _ in blocks]
            entries = [entry for _, members in blocks for entry in members]
        body["entries"] = entries
        body["groups"] = body.get("groups", [])
        return body

    detail = {
        "id": "d" + str(next(counter)),
        "call": ids["DatasourceResponse"],
        "extra": ids["DatasourcePolicyResponse"],
        "back": "Voltar para a lista",
        # O nome ja e o titulo do detalhe; a Visao geral nao o repete.
        "title": [*head, "display_name"],
        "tabs": [
            tab(
                "Visão geral",
                "main",
                [],
                [
                    group(
                        "Identidade",
                        [
                            item("r", "Alias", [*head, "alias"], show="code"),
                            item("r", "Revisão da configuração", [*head, "revision"], "count"),
                        ],
                        "A revisão aumenta a cada alteração salva.",
                    ),
                    group(
                        "Estado no Gateway",
                        [
                            item(
                                "r",
                                "No catálogo",
                                [*head, "enabled"],
                                "flag",
                                [
                                    {"value": "true", "text": "Habilitado", "tone": "good"},
                                    {"value": "false", "text": "Desabilitado", "tone": "neutral"},
                                ],
                            ),
                            item(
                                "r",
                                "No runtime",
                                [*head, "runtime", "published"],
                                "flag",
                                [
                                    {"value": "true", "text": "Publicado", "tone": "good"},
                                    {"value": "false", "text": "Não publicado", "tone": "neutral"},
                                ],
                            ),
                        ],
                        "Publicado: o Gateway mantém este datasource carregado em memória.",
                    ),
                    group(
                        "Atividade do runtime",
                        [
                            item(
                                "r",
                                "Geração publicada",
                                [*head, "runtime", "generation"],
                                "count",
                                show="metric",
                                blank="Nenhuma",
                            ),
                            item(
                                "r",
                                "Sessões abertas",
                                [*head, "runtime", "sessions"],
                                "count",
                                show="metric",
                            ),
                        ],
                        "Geração é a versão carregada; sessões são conexões abertas com ela.",
                    ),
                    group(
                        "Última verificação de conexão",
                        [
                            item(
                                "r",
                                "Resultado",
                                [*head, "last_test", "status"],
                                "text",
                                TEST_WORDS,
                            ),
                            item(
                                "r",
                                "Verificado em",
                                [*head, "last_test", "checked_at"],
                                blank="Sem registro",
                            ),
                        ],
                        "Testes ainda não são registrados: “Nunca verificado” não é falha nem sucesso.",
                    ),
                ],
            ),
            tab(
                "Conexão",
                "main",
                [],
                [
                    group(
                        "Destino",
                        [
                            item("r", "Host", [*head, "connection", "host"], show="code"),
                            item("r", "Porta", [*head, "connection", "port"], show="code"),
                            item("r", "Banco", [*head, "connection", "database"], show="code"),
                            item(
                                "r",
                                "Usuário técnico",
                                [*head, "connection", "username"],
                                show="code",
                            ),
                        ],
                    ),
                    group(
                        "TLS",
                        [
                            item(
                                "r",
                                "Modo",
                                [*head, "connection", "tls", "mode"],
                                "text",
                                TLS_WORDS,
                            ),
                            item(
                                "r",
                                "Nome esperado no certificado",
                                [*head, "connection", "tls", "server_name"],
                                show="code",
                            ),
                        ],
                    ),
                    group(
                        "Credencial",
                        [
                            item(
                                "r",
                                "Situação",
                                [*head, "credential", "configured"],
                                "flag",
                                [
                                    # O contrato so admite `true`: nao ha estado "sem credencial".
                                    {
                                        "value": "true",
                                        "text": "Credencial configurada",
                                        "tone": "good",
                                    },
                                ],
                            ),
                        ],
                        "O valor da credencial nunca é exibido nem enviado a esta tela.",
                    ),
                    group(
                        "Destinos aceitos",
                        [
                            item(
                                "r",
                                "Endereço público",
                                [*head, "destination_policy", "allow_public"],
                                "flag",
                                PERMIT_WORDS,
                            ),
                            item(
                                "r",
                                "Loopback",
                                [*head, "destination_policy", "allow_loopback"],
                                "flag",
                                PERMIT_WORDS,
                            ),
                            item(
                                "r",
                                "Hosts públicos autorizados",
                                [*head, "destination_policy", "allowed_hosts"],
                                "list",
                                [{"value": "@empty", "text": "Nenhum host público autorizado."}],
                            ),
                        ],
                        "Endereços de rede privada são aceitos. Loopback exige permissão; um "
                        "endereço público exige permissão e o host na lista.",
                    ),
                ],
            ),
            tab(
                "Masking",
                "extra",
                [
                    item(
                        "r",
                        "Regras, na ordem de avaliação",
                        [*rules, "masking"],
                        "tree",
                        RULE_WORDS,
                    ),
                    item("r", "Exceções", [*rules, "exceptions"], "tree", EXCEPTION_WORDS),
                ],
            ),
            tab(
                "Limites",
                "main",
                [],
                [
                    group(
                        "Aplicado às consultas",
                        [
                            item(
                                "r",
                                "Timeout efetivo (ms)",
                                [*head, "effective_limits", "statement_timeout_ms"],
                                "count",
                                show="metric",
                            ),
                            item(
                                "r",
                                "Máximo efetivo de linhas",
                                [*head, "effective_limits", "max_rows"],
                                "count",
                                show="metric",
                            ),
                        ],
                        "Valor efetivo: o menor entre o configurado no datasource e o da "
                        "política do datasource (aba SQL).",
                    ),
                    group(
                        "Configurado no datasource",
                        [
                            item(
                                "r",
                                "Timeout configurado (ms)",
                                [*head, "limits", "statement_timeout_ms"],
                                "count",
                            ),
                            item(
                                "r",
                                "Máximo de linhas configurado",
                                [*head, "limits", "max_rows"],
                                "count",
                            ),
                            item(
                                "r",
                                "Máximo de sessões",
                                [*head, "limits", "max_sessions"],
                                "count",
                            ),
                        ],
                        "Um valor configurado maior que o efetivo não é aplicado: vale o limite "
                        "menor.",
                    ),
                ],
            ),
            tab(
                "SQL",
                "extra",
                [],
                [
                    group(
                        "Funções",
                        [
                            item(
                                "r",
                                "Funções negadas adicionalmente",
                                [*rules, "sql", "denied_functions"],
                                "list",
                                [
                                    {
                                        "value": "@empty",
                                        "text": "Nenhuma função negada adicionalmente.",
                                    }
                                ],
                            ),
                            item(
                                "r",
                                "Funções PostgreSQL permitidas adicionalmente",
                                [*rules, "sql", "allowed_pg_functions"],
                                "list",
                                [
                                    {
                                        "value": "@empty",
                                        "text": (
                                            "Nenhuma função adicional; a política padrão "
                                            "continua valendo."
                                        ),
                                    }
                                ],
                            ),
                        ],
                    ),
                    group(
                        "Limites da política",
                        [
                            item(
                                "r",
                                "Timeout da política (ms)",
                                [*rules, "database", "statement_timeout_ms"],
                                "count",
                            ),
                            item(
                                "r",
                                "Máximo de linhas da política",
                                [*rules, "database", "max_rows"],
                                "count",
                            ),
                        ],
                        "Combinados com os limites configurados no datasource: vale o menor "
                        "(aba Limites).",
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
            "Resumo antes de gravar. Nesta versão não há gravação: nada foi salvo ou testado.",
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
            {"id": "p" + str(next(counter)), "label": label, "text": text} for label, text in steps
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
        "pages": _v1_pages(views, item) if views else [],
    }
