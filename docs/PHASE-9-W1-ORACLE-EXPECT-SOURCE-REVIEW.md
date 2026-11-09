# W1 Oracle — revisão final do gerador EXPECT

2026-11-09, sob delegação. Base publicada `9e56df4`. Este lote contém
somente definições puras, testes e evidência; nenhum SQL foi executado.

## Autoria e sequência medida

Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo
`claude-opus-5-5`, esforço `medium`, escreveu a fonte. CLI23221 retornou
exit1/API429 **depois** de gravá-la; terminal recuperado. O reset exibido
18h50 São Paulo foi interpretado como 21h50UTC, sem comprovação de reset
nem nova tentativa. Não interpretar essa chamada como ausência de edição.

Root leu as 674 linhas da fonte original `e86aad3f` e todos os oráculos do
teste congelado `ccb1f29f`. Antes da fonte, o RED119 teve 6 sanidades verdes
e 113 falhas por arquivo ausente; não demonstra comportamento do gerador.
As revisões prévias de ambiente, retenção e tipagem do teste permanecem
registradas em EXPECT-DESIGN-REVIEW e nos snapshots desta rodada.

Após autorização explícita do envio dos quatro arquivos do manifesto
`agy-handoff.json`, Antigravity executou revisão somente leitura, com
`gemini-4-argon-high`, esforço `high`, conversa
`b4ddb8b0-7f8d-4e6b-9fc0-f165b947fe62`. Terminal33083 recuperado com exit0.
Não houve finding funcional, de segurança ou contrato; apontou a formatação
pendente. As quatro cópias permaneceram intactas. Gemini não escreveu código.

A tentativa posterior de edição no Antigravity **não executou**: a revisão
automática de permissões atingiu sua própria cota e exibiu retorno em
12/11/2026 às 13h36, sem fuso estabelecido. Foi falha do serviço de revisão,
não classificação de insegurança, nem cota do Gemini. Não houve tentativa
por outra via de executar esse comando rejeitado.

Como QA local independente, root aplicou somente o formatador Ruff à fonte
de Claude2. As cinco alterações de layout deixaram a AST exatamente igual
à original; o teste congelado não mudou. Não houve autoria funcional do
root nem mudança de API, asserção, dependência ou perfil de lint.

## Resultado final local

| Verificação | Medição |
| --- | --- |
| Fonte final | `ce6ff3896d44b7e27cbfe76ca4e1c63c5da87c7982ea7e591e8ef71517a06725`, 22.114 bytes, 684 linhas |
| Teste congelado | `ccb1f29f8915a548085fc9028f4ea75a233ea859f54fb5b62275f1935e85441a`, 45.520 bytes, 1.214 linhas |
| Próprios, antes da formatação | 119 aprovados, 1,636 s |
| Relacionados, antes da formatação | 704 aprovados, 7,970 s |
| Relacionados finais, incluindo os 119 próprios | 704 aprovados, 8,160 s; zero falhas, erros ou skips |
| Ruff `src tests` e lint da fonte `E9,F63,F7,F82` | Aprovados |
| Formatação `src tests` e fonte explícita | 363 arquivos conformes |
| Mypy strict, alvos 3.11 e 3.14, com fonte explícita | 363 arquivos, ambos aprovados |
| Integridade | 27 fontes/testes protegidos e 124 insumos do pacote intactos por SHA/tamanho |

Runtime medido: Windows CPython3.11.3. Alvo mypy3.14 não significa execução
em Python3.14 ou Linux. A matriz relacionada usa somente objetos puros e
SO simulado. Não se declara suíte integral de produto nesta rodada.

`docs/poc` é excluído do perfil amplo do Ruff pelo pyproject existente.
O lint exploratório amplo da fonte original encontrou sete diagnósticos;
quatro linhas longas foram formatadas. N818, S608 e PLR0913 pertencem,
respectivamente, ao nome público fixado, à construção de SQL pela gramática
fechada e à assinatura pública de sete argumentos. Não foram adicionadas
supressões, wrappers ou relaxamentos de testes para ocultá-los. O perfil
restrito já usado no PoC passou, e esta fonte também passou mypy explícito.

## Alcance do parecer

Aceito como gerador puro de fixture, corpos mascarados e expectativas para
o laboratório futuro. As quatro funções são `seed_sql`, `result_body`,
`expected_records` e `lab_init_packet`; a última calcula os records das
mesmas entradas, sem aceitar records externos. A comparação independente
de vetores PG/HMAC e os DTOs/encoder públicos estão cobertos pelos testes.

O namespace Python é confiável: o literal `POLICY_MAPPING` continua mutável
por código que já tenha acesso direto ao módulo, como definido no contrato.
Os caminhos internos emitem somente INPUT/MODEL/ENCODE/SIZE; a classe de erro
não é uma fronteira contra construção arbitrária pelo chamador. A varredura
de retenção cobre containers builtin do namespace com limites explícitos,
não heap, closures, traceback, zeroização ou isolamento de Python hostil.
Ramos defensivos MODEL/SIZE não ganham prova por simples inspeção da fonte.

Ordem de linhas, proveniência real, OIDs e categorias dos erros são modelos
até medição no PostgreSQL. Não houve Docker, PG, SQL, processo/socket/thread
de produto, sinal, guard ou controle nativo, leitura de runtime/configuração
privada, novo root operacional, nonce, readmissão ou deployment.

T5 permanece BLOCK_NATIVE obrigatório para o laboratório completo. B1 fim
a fim, B2, D-090 gate2, C1, ingressos, IDE, MCP e produção continuam abertos;
o Gateway não foi disponibilizado por este lote. Estado16 e a tentativa
consumida não mudaram. Não há dispensa implícita de T5.

## Continuidade e publicação

**Atualização posterior:** código publicado em
`c152dc72e5c4dfb82c196e6a29617567804f136a`, por push normal. Fetch confirmou
HEAD/origin iguais e0/0, árvore rastreada limpa. Nenhum artefato funcional
mudou após os gates. A mensagem da tarefa existente foi atualizada para
o desenho T5 e relida Ready às21h55UTC, mantendo Limited/Interactive/IgnoreNew.
Dados em publication-and-resume.json. Ações distintas de Git e scheduler
passaram pelo fluxo normal de revisão; o comando AGY de edição rejeitado
não foi repetido ou desviado. O relato abaixo preserva o estado pré-commit.

Resultado ainda local. HEAD e origin/master permanecem em `9e56df4` até um
commit/push efetivamente confirmado. Não publicar por via alternativa para
contornar a falha da revisão automática. Não refazer a formatação concluída.

Últimos terminais dos agentes desta tarefa foram recuperados; nenhum novo
escritor foi iniciado depois da revisão. Get-CimInstance foi inicialmente
negado no sandbox. A chamada posterior autorizada de preparação do commit
conferiu os metadados e confirmou zero Claude2/AGY da tarefa ativos antes de
qualquer escrita no Git. Não houve nova chamada de programação.

O primeiro staged diff --check recusou os CRLF do log final de pytest.
Os bytes originais foram arquivados em formatted-log-original.json antes
da conversão do log para LF; métricas e todos os fontes permaneceram iguais.
Esse erro editorial interrompeu antes do commit/push. A nova verificação
acompanha o registro efetivo, sem repetir testes por alteração só de log.

A tarefa existente `Maskgw-Claude2-Resume-01a05804` foi previamente relida
Ready para 09/11 às 21h55UTC, uma vez, Limited/Interactive/IgnoreNew.
Não foi alterada nesta rodada. Seu texto anterior sobre formatação pendente
está superado por este registro e manda ler o checkpoint atual. Registro de
tarefa não comprova entrega ou liberação de cota; exige host/logon/app ativos.

Próximo incremento funcional: desenho mínimo da sonda T5 pelo programador
autorizado, antes de testes/RED/código. Reaproveitar o worker instalado e os
ledgers/portas existentes; sem nova camada genérica de controle. A sonda
deverá ter canal próprio, posse registrada antes do spawn e só reconhecer
EOF aprovado após saída natural0. Kill de fallback prova apenas limpeza
quando efetivamente recolhido. Qualquer mudança dos pins do driver/main
exige novo plano e evidência; este lote os deixou intactos. Sem execução
física até revisão do caminho concreto e de suas pré-condições.

Dados em `docs/poc/evidence/oracle9-w1-expect-review-20261109/` preservam os
REDs, snapshots, estáticos anteriores, revisão Gemini e resultados finais.
`raw-console-originals.json` registra os bytes recuperáveis da normalização
dos logs. A primeira saída `claude-source-tests.log` já havia sido normalizada
antes do registro do raw: seu layout original não foi preservado; métricas
JUnit e hashes da fonte/teste não foram alterados. A limitação não é omitida.
