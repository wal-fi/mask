# W1 Oracle — revisão do binding T5 no main

2026-11-10, sob delegação. Lote local, base publicada5a3dec7. Claude2 é
único programador (sessão51ea0d85/claude-opus-5-5/medium); root revê e mede.
Não publicar a integração enquanto main e fixtures antigas forem incompatíveis.

## Revisão inicial de testes, antes do RED

CLI5166 recuperada0; zero escritor confirmado por metadados. Root leu todas
as807linhas de a327c801/32.597bytes. Fonte main372f342f e teste antigo5abe4582
intactos. Contrato usa System22/SLOTS10, quatro pontas antes de Popen,
RawChannel/clock/ledger reais sobre SO fake, sem efeito nativo.

Findings do harness, ainda sem medição comportamental:

- Declarações novas derivavam de SYSTEM_FIELDS/SLOTS antigos. A migração
  prevista dos helpers faria a própria sanidade exigir20campos e formar15slots.
  Corrigir com literais locais independentes, preservando contrato22/10.
- Ruff: um argumento não usado; format: três hunks; mypy: retorno Any
  declarado bytes e acesso a atributo ausente no tipo estático FakeSock.
  Registro integral em main-t5-review-20261110/initial-statics.json.
- Cobertura de prazo só tinha select bloqueado. Acrescentar retorno pronto
  mas tardio e escrita parcial tardia, sem próximo write depois do prazo.

Snapshot inicial preservado como dados, não módulo executável. Mesmo Claude2
corrige somente o novo teste antes de root ler delta e medir/congelar RED.
Nenhum pin/SDK/app124/puro/estado16/attempt foi alterado.

T5 físico/B1/B2/D090gate2/C1/ingressos/produção continuam abertos. Nenhum
Docker/PG/SQL/socket/thread/processo/guard/sinal nativo do produto, runtime,
configuração/ambiente/arquivo privado, root operacional ou deploy executado.

## RED revisto e congelado

CLI87602 recuperada0; zero escritor confirmado. Root leu o delta final.
Teste6063c0e3/34.736bytes/864linhas:41casos,2sanidades aprovadas/39falhas,
0erros/skips,12,232s. Trinta e sete TypeError por popen ausente, uma contagem
System20 versus22 e uma ausência de wrapper; RED de API, não comportamental.
AST: só sanidade de literais mudou e houve assert aditivo de tipo ProbeSock;
os dois casos aditivos têm duas variantes de atraso cada. Ruff src/tests,
format365(inclui driver), mypy364src/tests3.11/3.14 limpos. Fonte main372,
teste antigo5abe e driverb54 intactos. App124/protegidos exceto3migrações
anteriores conferidos intactos.

Próximo incremento sob delegação: somente deploy/oracle9_w1_main.py.
System22/SLOTS10, wrapper pipe2 preguiçoso, imports públicos subprocess e
ResultDeadline, pin driverb54/51913, nonce32 e ProbeChildren com facades
mínimas. Sem fonte SDK/driver/puro ou testes alterados. Root lê todo delta
antes de executar e mede41/sondas; depois migração deliberada de fixtures
antigas do main em lote separado. Não publicar integração parcial.

## Primeira fonte: verde insuficiente

CLI82502 recuperada0, zero escritor. Root leu todo delta. Fontec2eddba4/46.462bytes/1.440linhas; teste6063 congelado.
41/41 passaram em1,005s; lint restrito/format da fonte limpos. Não aprovada:
sonda independente pelo ProbeChildren público reproduziu criação de processo
fake depois de parent.close() ou writer.close() positivos. Spawn verificava
child/reader, mas não as quatro pontas possuídas antes do efeito. A raiz
continua bloqueando safe_exit, portanto não há prova de liberação indevida;
é falha concreta da pré-condição do binding. Dados em independent-preclosed.

Precisão de revisão: o oráculo AST contava qualquer atributo chamado pipe2,
inclusive System.pipe2, em vez de somente os.pipe2. Isso induziu getattr no
binding. Corrigir somente essa seleção AST para objeto Name(os), preservando
encaminhamento literal/única referência do SO e nenhum lookup no bootstrap.
Depois da precisão o binding voltará ao acesso direto root.system.pipe2.
A precisão do oráculo é correção do harness sob delegação, não enfraquecimento
do contrato preguiçoso nem evidência comportamental de uma fonte diferente.

Próximo somente teste novo: regressões aditivas para parent/writer fechados
antes do spawn, com zero Popen e slot processo EMPTY; fontec2 congelada até
root ler delta/medir RED. Nenhum outro teste, fonte ou pin alterado.

## RED comportamental43 congelado

A primeira preparação da chamada parou na guarda, sem iniciar Claude2:
o main recém-modificado faltava na lista local de deltas conhecidos. Root
conferiu Git/hash e atualizou só essa guarda, sem ampliar edição do lote.
CLI61444 recuperada0. Root leu todo delta: testeec2df911/36.224bytes/895linhas.
Somente função AST de pipe2 precisada e duas variantes de regressão aditiva;
todos os demais casos preservados.43coletados,41pass/2falhas,0erros/skips,
1,374s. Ambas DID NOT RAISE MainRefusal após close de parent/writer. Ruff/
format366/mypy364src/tests3.11/3.14 limpos. Fontec2 fixa durante RED.

Próximo somente main: exigir as quatro facades/pontas ainda possuídas pela
mesma raiz antes de reservar processo/chamar Popen. Voltar ao acesso direto
System.pipe2, agora permitido pelo oráculo correto. Testeec2 congelado.
Root lê diff e mede43 antes da migração deliberada do teste antigo5abe.

## Fonte corrigida e migração antiga pendente

CLI9697 recuperada0. Root leu delta mínimo: fonte89c99c65/46.787bytes/
1.446linhas; testeec2 fixo.43/43 passaram em0,962s; sondas independentes
recusam os dois spawns com zero processos fake. Ruff/lint restrito/format366/
mypy364src/tests3.11/3.14 limpos. Fatos exclusivamente simulados.

Baseline do teste antigo:161coletados,29pass/132falhas,0erros/skips,37,578s;
metadados antigos de driver/System/SLOTS/imports ainda não migrados. Preservado
como reprovado. A captura dessa QA omitiu o ID da sessão de execução do wrapper
no retorno ao modelo; os resultados completos foram recuperados dos JSONs/JUnit
produzidos pelo próprio wrapper, após terminar. Não houve repetição concorrente.

Próximo somente tests/test_oracle9_w1_main.py: metadados driverb54/51913,
System22/SLOTS10, dois imports públicos extras, stubs explícitos fake popen/
pipe2 que recusam se invocados no mundo legado, e assert adicional de binding
children em M06. Todos161casos e asserções anteriores preservados; helpers
T5 usam ProbeOS próprio. Fonte89/testec2/driverb54/SDK/puro fixos. Root lê
diff/AST antes dos gates conjuntos. Sem publicação parcial.

## Gate conjunto e fechamento restrito

CLI62793 recuperada0. Root leu todo delta de migração e comparou AST:
as88funções de teste antigas (161casos parametrizados) permanecem; só M06
recebe children no mapa. Teste antigo0e6e07f0/102.644bytes/2.842linhas.
Pins/System22/SLOTS10/imports e dois stubs fail-fast são as únicas mudanças
funcionais de fixture. Stub não simula sucesso nem recurso e as composições
T5 usam ProbeOS separado. Novo testeec2 permaneceu fixo.

Matriz conjunta controller/driver/session/EXPECT/main/T5:849aprovados,
0falhas/erros/skips/xfail,12,615s, WindowsCPython3.11.3. Inclui89do driverT5,
43do mainT5 e todos161antigos do main. Ruff src/tests e lint restrito dos
dois deploy limpos; format366; mypy364src/tests para3.11/3.14 limpos.
Deploy continua fora do mypy; runtime3.14 e Linux não medidos. App124 e
22de27protegidos não migrados intactos por SHA/tamanho. Os cinco deltas
protegidos são os dois deploy e três testes explicitamente migrados.

Fonte driverb54a8a94 e main89c99c65 agora coerentes; a limitação inicial de
pin/API incompatível desta revisão foi resolvida. Aceitos sob delegação
somente como integração fake do laboratório. Histórico41verde rejeitado,
RED43 e baseline161reprovado preservados. Nenhum código de produto SDK,
frontend, dependency ou configuração mudou. Sem razão para repetir gates
Node/PG/wheel por alteração restrita a laboratório e testes públicos.

Publicação deste lote pode ocorrer somente depois de Git/diff/integridade
final por ferramenta permitida. Conferir HEAD real após commit; não usar
5a3dec7 como guarda futura. Não existe job novo ou próxima chamada ativa.
Próximo incremento seguro é reconciliar o plano de readmissão nativa com
estes hashes e pré-condições, somente desenho público antes de efeitos.
O main existente não foi executado com OS real, hold ou entry operacional.
T5 físico segue BLOCK_NATIVE; B1/B2/D090gate2/C1/ingressos/produção abertos.

Preparação de evidência: auditoria inicial encontrou espaços finais em sete
logs e sete JUnit de rodadas vermelhas. Logs exibidos foram normalizados,
com cópia comprimida anterior. Nos XML, espaços finais viraram referências
XML explícitas: árvore completa parseada, textos/atributos/tails, idêntica
antes/depois. Bytes originais comprimidos preservados em junit-whitespace-
encoding.json. Console bruto e snapshots não mudaram. A primeira auditoria
parou com AssertionError ao sinalizar XMLs restantes; não foi gate de teste.

O primeiro staged diff-check recusou CRLF dos XMLs (evidence é -text pelo
repositório). O commit não ocorreu. Representação dos novos XMLs normalizada
para LF, árvore parseada idêntica, bytes anteriores comprimidos preservados
em junit-eol-normalization.json. Snapshots/código/testes intactos; gate
funcional não repetido por mudança somente de representação da evidência.

## Publicação observada

Push normal5a3dec7..861969d e fetch posterior confirmaram HEAD/origin
861969df940f7261aed1f60777bc92c34af5cf91,0/0 e rastreados limpos. Autoria/
trailers conferidos; oito arquivos finais por SHA/tamanho intactos. Sem
produto/SDK/frontend privado incluído; dados pessoais não rastreados intactos.
Fsck conectividade retornou0, com objetos dangling históricos sem erro;
nenhum objeto foi apagado. Publicação não é deploy ou prova nativa.
