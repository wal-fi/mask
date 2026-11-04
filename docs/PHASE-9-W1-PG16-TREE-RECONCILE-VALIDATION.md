# Reconciliação TREE/quiescência — validação isolada com fakes

Data: 2026-11-04. Claude2 programou na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço
`medium`; o assistente principal revisou e executou os gates. Decisões
rotineiras tomadas sob a delegação geral, sem inventar aprovação individual.
Base publicada anterior: `a040f8848cea60372eafdd46aedbf3981fa87e7c`.

## Escopo e reprodução

Lote somente com dados sintéticos/kernel falso. As definições públicas do
backend `10c9058f` e do supervisor `dfcc4ed6` foram carregadas em namespaces
novos com colaboradores simulados: setup vê (1,1), depois total3/ativos0,
processo sinalizado, saída normal e EOF, membros vazios. DLL, subprocesso,
thread e sleep reais ficam proibidos nas fixtures. Não é nova execução da
tentativa operacional consumida.

Os três testes de caracterização passaram antes do módulo: o supervisor
legado chega a CLEANUP/TREE_UNPROVEN com owner RUNNING; o close independente
do MESMO owner chega a CLOSED/ledger vazio; total2 segue normalmente.
Isso demonstra um cenário lógico, **não** a causa nem as contagens da rodada
real. A política que recusa total acima de2 continua intacta.

## Histórico medido antes da implementação

| Etapa | Medição | Interpretação |
|---|---|---|
| RED40, módulo ausente/substituto legado | 40 coletados,8 pass,32 falhas;1,939s | Pós-condições novas falham por asserção;3 caracterizações passam |
| Estáticos iniciais | Ruff E501/3 ajustes de formato;mypy1teste passou | Corrigidos só em whitespace |
| RED46, seis regressões novas | 46 coletados,9 pass,37 falhas;2,043s | 34 AssertionError+3 pytest Failed;zero erros/skips |
| Congelamento | Prefixo AST dos40 idêntico;teste65696a29/15829bytes | Nenhuma asserção/caso/fallback/fixture original alterada |

RED40 e RED46 e os respectivos testes estão arquivados como dados em
`docs/poc/evidence/tree-reconcile-review-20261104/`. O módulo só foi
autorizado depois dessas medições. A retirada de error_type inútil foi
aceita pelo revisor antes da implementação.

Um pedido inicial de simular bytes após EOF em cache não é atendido pelo
backend consumido: `_peek` confia no EOF já observado. O teste final modela
bytes antes desse cache e registra a limitação, sem alterar a fonte ou
inventar proteção depois do EOF.

## Artefatos e gates anteriores à guarda de chaves (V3/V4)

Fonte V4 `docs/poc/pg16_shell_tree_reconcile.py`:
`43eaefd79c58c82120ddc0d79aa21a3fde08c762a9a5f18e5283cd20fdb72e48`, 2729bytes/69linhas.
Teste V2 `tests/test_pg16_shell_tree_reconcile.py`:
`65696a29a3b29b58cd64109fe0812f2fa20269502191fc4fcf70b35d80924f2f`,
15829bytes, congelado.

- 46/46 próprios em2,133s, sem erros/skips, sobre a candidata executável58a3.
- Correção P3 posterior só na docstring do módulo: deixa explícito que o
  delegado close pode liberar handles, mas o primitivo não retira entradas
  de registro. AST de todo código/constantes/docstrings de função idêntico;
  a candidata58a3 foi preservada como dado, não reexecutada.
- Seleção final de7arquivos: **589/589 em41,239s**, incluindo os46 sobre a
  fonte final43ea. Zero falhas/erros/skips. Backend, supervisor, adaptador,
  runner, entrada e projeção de diagnóstico legados incluídos.
- Ruff do teste e análise de erros do PoC aprovados; format de2arquivos
  aprovado após a edição final.
- Mypy strict do teste nos alvos3.11 e3.14 aprovado. O PoC não integra o alvo
  mypy; alvos de tipagem não são medições de runtime3.14.
- Venv Windows/CPython3.11.3 de referência; nenhuma versão/dependência
  instalada ou alterada neste lote. Fonte10consumidas e estado16 intactos.

## Contrato e limites

O primitivo só trata facts dict exato, CLEANUP/TREE_UNPROVEN e três flags
exatamente True. Estado inicial deve ser RUNNING exato; chama close uma vez.
Só retorno normal None mais estado final CLOSED exato dá REJECTED_CLOSED.
Exceção comum ou estado/retorno desconhecido retêm; controle propaga com a
identidade original. Os fatos e o registro não são modificados.

Casos simulados incluem ativos/membros remanescentes, processo não sinalizado,
erro de accounting, ledger parcialmente fechado, estado ilegível, retornos
malformados, tipo hostil e interrupção antes/depois do close. Não há retry,
timer, registro global ou autenticação de owner neste módulo.

Nenhum chamador operacional existe. Um chamador futuro precisa verificar
a origem do owner/método/ledger, reservar a tentativa, conservar a rejeição,
normalizar seus fatos de forma explícita e não fechar de novo o owner
comprovadamente fechado. Essa integração e seus novos pins ainda não foram
implementados nem validados. Não se alega garantia nativa a partir de fakes.

Nenhum API/DLL/job/process/control nativo real, Docker, PG, SQL, leitura
privada, runtime/config/binário explícito, nova raiz/nonce/rodada ou deploy.
A tentativa3f12dc584c29 continua FAILED_ONLY_OPERATOR_ABORT, sem reutilização
ou reclassificação. Não foram necessários PostgreSQL, browsers ou pacotes:
nenhum produto/asset/dependência ou conteúdo embarcado mudou.

Native3s **NOT_MEASURED**, entry_gate **NOT_EVALUATED**, B1/B2/D090gate2/C1,
SQL e produção continuam abertos. Gateway indisponível; destino final
Docker local com Oracle Linux9.8. Próximo: desenho/revisão de nova composição
e caller que preservem essa distinção, antes de código ou efeito operacional.

## Reforço posterior de chaves e gates finais (V7)

Revisão32708 terminou0 semP1/P2 e com P3 informativo: chaves objeto em um
dict exato podem executar igualdade estrangeira no get. Root reproduziu
uma exceção antes do close. Era fora do contrato de fatos confiáveis, sem
vulnerabilidade do produto ou causa real demonstrada; sob delegação foi
escolhido um reforço pequeno antes de integrar qualquer caller.

Três testes foram acrescentados mantendo o prefixo AST dos46. RED49 na
fonte43ea:49coletados/46pass/3falhas (1MarkerError/2AssertionError),2,580s,
zero erros/skips; só os3novos falham. Depois do RED mudou apenas _eligible
e sua docstring: exige chaves str exatas por iteração antes do get, sem
invocar hash/igualdade estrangeira. Estado, close, constantes e política
de retorno são os mesmos.

Fonte final `bb1f1984f5a144564a56e23fb5c4797dc0851651b608012ce229cc14d12a801b`,
2935bytes/74linhas. Teste final
`ad0742c02abe3544b9b4c5607df88563d1c0bf6458f278050cc0829adefe3a04`,
17763bytes, congelado. **49/49 em2,242s e592/592relacionados em48,705s**,
zero falhas/erros/skips. Ruff do teste/erros do PoC, format2 e mypy1teste
alvos3.11/3.14 aprovados; tipagem3.14 não equivale a execução3.14.
Sonda separada: NOT_APPLICABLE/zero igualdade estrangeira/zero close.
Dez fontes e estado16 intactos.

Fonte anterior43ea, RED49 e sondas antes/depois são dados preservados.
final-review.json descreve V4; final-key-review.json registra o resultado
final V7. Valores e limites históricos V3/V4 acima permanecem verdadeiros
para seus escopos. Nenhuma leitura privada ou operação nativa real.
Origem dos fatos/owner/método/ledger, reserva única e composição/pins de
um caller novo exigem integração e revisão próprias. Nenhum Gateway/SQL/
produção foi habilitado ou tentativa consumida reclassificada.
