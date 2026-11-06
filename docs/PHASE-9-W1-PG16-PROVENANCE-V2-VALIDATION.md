# Proveniência V2 — revisão e validação do componente privado

Data local: 2026-11-05. Partida HEAD/origin/master
`6a0682511cd4ffeccf28b991e6c908a1c606af66`. Claude2 foi o único programador,
sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço
`medium`. CLI94926/94652/18093/38943/24791 terminaram com exit0 e todos os
terminais foram recuperados antes da chamada seguinte. O revisor leu o teste
inicial inteiro, os deltas de testes, toda a primeira fonte e o delta final,
executou as verificações e reproduziu um finding antes da correção.
Trabalho sob delegação, sem inventar aprovação individual do usuário.

## Entrega e alcance

Componente privado `verify_v2(core, expected_v2, expected_core, evidence)`:
namespace explícito já carregado por uma cadeia confiável, política imutável
do revisor, snapshots de entradas, clone de Expected, schemas/pins/bindings,
prefixos e metadados, e chamada única ao verificador semântico congelado.
APPROVED e REJECTED continuam distintos em pares fechados V2; nenhum rótulo
autoriza produção. Não há CLI, entry, loader, collector ou publicador novo.

Guardas de identidade não autenticam um namespace inicial malicioso nem
detectam alterações de política no próprio lugar. Namespace privado/estável,
construtor e descritor do Expected continuam premissas externas. Os oito
papéis selecionados não fecham todo o código da execução. Origem, frescor,
execução real, SO, identidade viva e cleanup não são comprovados aqui.

Contrato em [CONTRACT-REVIEW](PHASE-9-W1-PG16-PROVENANCE-V2-CONTRACT-REVIEW.md),
schemas de artefatos em CASE-V2-DESIGN B2. Admission count de 11 privados
antecipa a whitelist válida sem modificar MAX_PRIVATE64 do core. Limites
individuais e agregados preservados; máximos alcançáveis 117760/124928
impedem uma testemunha isolada dos tetos agregados 262144/269312.

## Bytes finais

| Arquivo | Bytes / linhas | SHA-256 |
|---|---:|---|
| `docs/poc/pg16_shell_native_control_provenance_v2.py` |21359 /622 | `eac9709115ddbb70dc89ea1c59b734ffec556cfbf6d1ff25b0eb859116761827` |
| `tests/test_pg16_shell_native_control_provenance_v2.py` |62796 /1848 | `692b4d4ea7414e419036bf3264cc8059ec367ade2c7ad074b49327bc518f8f57` |

Teste final byte a byte igual ao RED de contagem. Source10, lifecycle/teste,
helper/teste e caller/teste: 16 arquivos conferidos por hash e tamanho,
todos intactos. Estado16 não foi editado.

## Testes antes do módulo e revisão dos oráculos

| Etapa medida | Resultado | Segundos |
|---|---|---:|
| Inicial, teste b94c8c0a/52408bytes |207 únicos;20 sanidades passaram;186 erros+1 falha, todos187 FileNotFoundError do módulo ausente |2,036 |
| Revisto, teste e3406a60/59592bytes |221 únicos;20 sanidades passaram;198 erros+3 falhas, todos201 FileNotFoundError do módulo ausente |1,965 |
| Primeira implementação565045b7 |221 passaram |5,711 |
| Regressões de contagem692b4d4e contra565045b7 |228 únicos;222 passaram/6 falharam por AssertionError |6,366 |
| Fonte final eac97091, teste congelado692b4d4e |228 passaram |5,593 |

Os dois primeiros REDs provam ausência de funcionalidade, não comportamento
de uma implementação. As 20 sanidades independentes verificaram os cinco
cenários sintéticos com o core real: aprovado e rejeitados nos prefixos
1/2/3, TREE, READY_MISSING e rejeição sem latch; verificaram também namespace,
classes, constantes, fontes e builder. AST das sanidades/fixtures preservada
na revisão dos oráculos (3c431b50).

Antes de congelar e340, o revisor corrigiu via Claude2 oráculos que mascaravam
o caminho pretendido: Collider sobrescrevia uma chave builtin existente;
nomes inválidos também ultrapassavam a contagem; retorno do parser tinha
contagem errada antes da chave estrangeira. Foram preservados os tamanhos
nos negativos, provada a presença das chaves por identidade e acrescentados
retornos aninhados, clones e controles no construtor. Não houve relaxamento
para acomodar uma implementação. Ruff/format/mypy passaram antes do módulo.

## Finding independente e correção por invariante

A fonte565045b7 passou221, mas o revisor observou pelo verify_v2 que
private12 e metadata4 entravam em _str_keys antes da recusa por contagem.
Cada chamada ainda devolvia INPUT; o problema era trabalho anterior ao teto.
_object tinha a mesma ordem, e _outcomes não limitava a contagem dos mapas
do summary pós-core. A sonda observacional registrava a entrada no scanner,
sem mudar seu predicado; não mediu tempo, alocação ou efeitos nativos.

Claude2 acrescentou seis regressões e uma sanidade da própria sonda,
preservando a AST dos221 anteriores. Os seis falharam antes do fix: mapas
externos12/4, manifest8→9, metadado8→9, summary10→11 e record13→14. Estes
últimos também explicitam a recusa de forma pós-core. O teste usa um seam
whitebox deliberado no scanner existente; depende de sua função continuar
significando varredura de chaves, não é prova geral de consumo de CPU.

Somente depois do RED, a correção passou a conferir tipo e contagem antes
da varredura em _object/_snapshot/_outcomes. Acrescentou os literais de
forma summary10/case13. Comparação AST confirmou que fora dessas três
funções e dessas duas constantes a fonte permaneceu igual. Nenhum teste
mudou após congelar692b4d4e. A sonda final voltou a INPUT, com zero chamadas
ao scanner para os mapas acima da contagem.

## Gates e escopo medido

| Gate | Resultado |
|---|---|
| Próprios |228 passed,5,593s; sem falhas/erros/skips/xfail |
| Relacionados,11 arquivos |1166 passed,48,060s; sem falhas/erros/skips/xfail |
| Ruff PoC |E9,F63,F7,F82 aprovados, política existente |
| Ruff teste |Seleção normal do repositório aprovada |
| Format |2 arquivos conformes |
| Mypy strict |1 teste, alvos3.11 e3.14 aprovados; PoC fora do mypy |
| Integridade |16 arquivos anteriores intactos; teste igual ao RED228 |
| Sonda independente |private12/metadata4 recusados sem entrar no scanner |

Execução Windows/CPython3.11.3; alvo estático3.14 não é execução em3.14.
Relacionados incluem B, core congelado, casoV2, lifecycleV2, reconciliação,
backend, host, adapter, runner, entry e projeção HELD. É uma seleção de
unidades/fakes, não a suíte integral do produto ou prova operacional.

Sem alterações de produto, frontend, dependências ou pacote; PostgreSQL,
Node, browsers e packaging não foram repetidos. Não houve DLL/job/process
control nativo, Docker, PG, SQL, leitura privada/runtime/config/binário,
root/nonce/entry/loader/CLI/comando operacional ou deploy. Os imports e
chamadas do componente foram testados com APIs de E/S selecionadas
interditadas e inspeção de corpo; isso não prova todo caminho possível de E/S.

Dados em `poc/evidence/provenance-v2-review-20261105/`: arquivos de teste
antes dos freezes, fonte pré-fix, relatórios fechados, sonda e resultado
final. Os snapshots .py.txt são dados, não entradas operacionais. Histórico
e tentativas consumidas preservados, sem reclassificação.

## Próxima integração

Revisão posterior em 2026-11-06:
[BUNDLE-V2-DESIGN-REVIEW](PHASE-9-W1-PG16-BUNDLE-V2-DESIGN-REVIEW.md)
fechou o contrato prospectivo da ponte A→B. Builder e testes ainda ausentes;
o próximo incremento é testar/medir RED antes de implementação. Este lote
documental não repetiu nem mudou os resultados acima.

O contrato revisado cobre o mapeamento do slot real de A para cada metadado B
e as obrigações do produtor/coordenador: manter posse, construir todos os bytes
antes da publicação terminal, controlar origem/frescor e executar os mesmos
bytes pinados. Loader/collector/publicador V2 e consumidor operacional não
existem; exigem incrementos próprios revistos. O próximo lote seguro é testar
o builder e medir o RED antes do módulo, sem materializar root/nonce/entrada/
comando ou repetir attempt3f12dc584c29. Não alterar source10/state16/fontes aceitas.

Gateway indisponível. Native3s NOT_MEASURED, entry_gate NOT_EVALUATED,
B1/B2/D090gate2/C1/SQL/produção continuam abertos. Identidade Nov2 e evidência
v1 não foram promovidas. Destino OracleLinux9.8 em Docker local permanece
aceito, sem nova operação neste lote.
