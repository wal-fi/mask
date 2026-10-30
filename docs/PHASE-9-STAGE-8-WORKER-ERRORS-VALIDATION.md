# Worker — erros tipados e saúde da conexão

**2026-10-23 — implementado sob delegação; código e evidência final revistos
pelo Claude2 sem bloqueador.** D-117 é escolha técnica delegada, não
aprovação individual. Nenhum worker/IPC operacional foi ligado. B-1 fim a fim,
B-2 e D-090 gate2 continuam abertos; SQL PGWire continua recusada.

## Escopo e fontes

HEAD4a5e5560abb495898c9e1b8ca44ac2d155681015, origin/master em cache
5d173ea938eb12db33bc880bf67a2e81a208fd5e,0behind/1ahead, sem fetch/escrita
em .git. Baseline618 arquivos versionáveis incluindo capturas e
.venv/pyvenv.cfg; alterações anteriores preservadas. Windows nativo,
Python3.11.3 da .venv existente; runtime3.14/POSIX não executados.

Produto novo: db/execution_error.py. Único delta de produção em arquivo
anterior: db/postgres.py importa o classificador, escolhe-o apenas quando
typed=True e oferece _typed_connection_healthy, sem I/O. Auditoria reversa
removeu exatamente esses três trechos e recuperou os bytes anteriores do
adapter, SHA170dafb9c792f113b8892a52b3a0c6603c98010004dac40983d729f6d1ca6081.
Nenhum chamador operacional usa execução tipada ou esse teste de saúde.

| Fonte final | SHA256 |
| --- | --- |
| db/execution_error.py |a1cffd9ed5a4c8e1b4c03cac4dbe37cb5ee7349d969e5b749b07fbba180c55e1|
| db/postgres.py |461e544fb185b6a3984e451d839034d8233c0a866b0bb46cb5ed0e68e284cd63|
| docs/poc/worker_errors_pg.py |1ec9d0071feaa1dd8706c6d8b252a5fe9270c5c65491cb79cc140616d60f2470|

## Contrato e limites

Enum privado QUERY/TIMEOUT/RESOURCE/CONNECTION/INTERNAL; erros novos retêm
somente categoria e mensagem fixa. Subclasses de DatabaseError e, para
TIMEOUT, QueryTimeout. Classificador lê somente sqlstate: str exata5
caracteres ASCII A-Z/0-9. Sem str/repr/diag, SQL ou erro original retido.
O levantamento continua depois do except, sem cause/context original.

- 57014 é cancelamento do servidor; mantém tipo QueryTimeout por
  compatibilidade, mas não comprova statement_timeout.
- 0A/21/22/23/40/42/54 e somente25006 são QUERY; demais25xxx fatais.
- 53 é RESOURCE fatal, sem atribuir OOM local; 08 ou None é CONNECTION
  fatal, incluindo falhas locais/driver sem SQLSTATE.
- Outros, malformados ou falha de introspecção são INTERNAL fatal.
- Candidato a continuar é só QUERY/TIMEOUT, **não autorização suficiente**.
  Depois de _settle, sob dono exclusivo, saúde exige closed/broken False,
  ConnStatus.OK e TransactionStatus.IDLE por identidade exata. Campo ausente
  ou leitura falhando resulta False. Não conecta/cancela/consulta/fecha.

Saúde é somente observação local libpq; não atesta rede viva, read-only ou
sucesso futuro. Servidor pode ter fechado sem libpq saber; próxima falha é
fatal, sem retry/reconexão/fallback. Worker futuro ainda precisa combinar
saúde com categoria e integridade/ownership. MemoryError nativa fora de
psycopg.Error não foi convertida; deverá encerrar worker. Erro genérico na
fronteira do cursor também continua genérico/fatal para chamador futuro.
Connect/D-107, legado, validator, proveniência, masking e settle não mudaram.
Mensagens tipadas são privadas e diferem das strings legadas preservadas.

## Revisões, regressões e testes locais

Plano WORKER-ERRORS-PLAN revisto antes de código por Claude2, sessão51ea0d85:
W1 estreitou25 a25006, W2 esclareceu cancelamento57014, W3 incluiu
ConnStatus.OK/pós-settle/limite de rede, W4 incluiu cardinalidade21.
Código revisto sem bloqueador; notas exigiram saúde positiva com enums
reais, distinção CONNECTION local e mensagens distintas do legado.

Testes de contrato vieram antes do módulo (coleta falhou por API ausente).
Primeira execução:67 passaram/2 fixtures falharam. Uma fixture de erro com
getter hostil agora evita que o construtor psycopg leia esse getter;
FakeCursor usa executed, não queries. Corrigidos só os testes novos. Uma
seleção citou test_db_adapter.py inexistente e não executou testes; repetida
com os arquivos reais. Estilo/tipagem novos corrigidos antes dos gates.

| Gate local | Resultado |
| --- | --- |
| Contrato/classificador/saúde/legado com fakes |69 passed|
| Helper PG, guards/ownership/env/JUnit com fakes |26 passed|
| Integrações novas, executadas na suíte PG abaixo |5 passed|
| Seleção relacionada adapter/typed/encoder/security/purity/plan |392 passed/69,94s|
| Ruff e format src/tests |aprovados,265 arquivos|
| mypy strict alvos3.11 e3.14 src/tests |265 arquivos, ambos sem erro|
| Helper POC |Ruff E/F/I/B/UP e format aprovados|

São100 casos novos no total; as seleções relacionadas se sobrepõem e não
devem ser somadas. Runtime medido somente Windows3.11.3. Casos53 sintéticos
não são pressão nativa nem prova B-2. Nenhum browser/frontend alterado.

## PG16 descartável — procedimento revisado e execução única

WORKER-ERRORS-PG-PLAN está consumido; não repetir A/B/C. Antes de executar,
Claude2 leu helper e scripts externos completos. Corrigidos P1 (asserts
sob otimização: main agora recusa -O antes de I/O), P2 (17 identidades de
testes obrigatórias, não só ausência de uma frase de skip), N1 (sem cache)
e N2 (senha efêmera visível em Config.Env do container até remoção).
26 testes de guard após oito novas regressões. Rerevisão sem bloqueador
condicionada a APP_READY atômico e PID/FileTime exatos antes de parar.

Raiz própria %LOCALAPPDATA%/Temp/maskgw-worker-errors-pg-20261023-3ce74efa,
task df9b8229bd5e4956a63406e0c410cb77. O Desktop estava off. Uma execução do
start hidden registrou PID27284/FileTime134372505506341375. Nove observações
verdadeiras em intervalos comandados10s; três comandos30s tiveram intervalos
de orquestração, portanto o setup durou **mais que90s**, sem observação
contínua prometida. APP_READY só depois de confirmar a mesma identidade.
FileTime é maior que2^53; cópia conserva JSON UTF8 exato, sem conversão JS.

Uma invocação B, sessão3200 terminal/exit0. Engine29.7.2 linux/amd64,
imagem local postgres16 ID
sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685,
--pull=never. Container próprio, SCRAM, loopback/porta aleatória,512MiB,
pids256/CPU1,log-driver=none. PG16.15/160015 real. Sem DSN herdado, banco do
usuário ou produção. Senha aleatória só ambiente; redactions medidos0.
DSN só no runner filho. Não há segredo em argv/repositório/artefatos.
Não se afirma que Config.Env protege de administrador Docker local.

Runner -I -B, stderr unido ao stdout, pilha temporária64MiB, sem alterações
na .venv. Suíte inteira sem deselect/cache; JUnit e stdout persistidos.

| Gate PG16 integral | Resultado |
| --- | --- |
| Coletados/executados |7.523|
| Passaram |7.503|
| Falhas/erros/deselect/skip por DSN |0/0/0/0|
| Skips de plataforma |20:5 fsync POSIX,6 symlink,9 bits POSIX|
| Tempo JUnit / resumo pytest |916,188s /916,62s|
| Casos obrigatórios |17/17, exatamente uma vez e sem skip|

Cinco novos provam: IDLE/saúde positiva após sucesso; erro de dados e
cardinalidade com mesma conexão saudável/uso posterior; cancelamento com
QueryTimeout e saúde positiva; backend próprio terminado nunca saudável
nem recuperável. Doze D-115 existentes provam tipos/masking/proveniência,
read-only, timeout, recusa antes de fetch e encoder/receptor reais.
Nomes exatos e nós XML estão na cópia de evidência; não se afirma que toda
classe SQLSTATE tenha sido provocada no PG. Um PytestWarning em teste
antigo test_admin_http_implica_a_secao_critica: match vazio sempre passa;
não foi convertido em falha nem atribuída causa nova.

Helper confirmou source_unchanged,13 comandos CLI exit0 (lista commands
do result.json preservada na cópia; medição do executor), stop/rm-v do
próprio CID, inventário global vazio e ausência do volume próprio. Nome do
volume não foi persistido no resultado: conclusão se apoia no helper
hashado/revisto e seus exits/flags, não em inventário recalculado pelo
revisor. Antes de C, root reconferiu PID/FileTime/cleanup. Uma execução de
restore, sessão10092 terminal/exit0: ps vazio e desktop stop/exit0. Em
2026-10-23T18:02:16.5272131Z, observação de processos encontrou0 Docker.
attempt final COMPLETE_PG16_DESKTOP_OFF; imagens preservadas. Não houve
force, WSL shutdown, retry ou segundo escritor. Cleanup não é promessa
de recuperação após toda falha do SO/descendentes arbitrários.

Cópia imutável docs/poc/evidence/worker-errors-pg-run-20261023.json:
56.171bytes/SHA1a29a59d01e64af5e9a3f204ecdb615fcaedfefcf747ac869789c5fe93e16673.
Preserva result/attempt/observations/restore/runner com UTF8/hash/tamanho;
JUnit completo e log ficam na raiz externa com hashes/tamanhos, e17 nós
obrigatórios/20 skips/aviso/resumo foram copiados. O revisor leu só os nós
copiados; não reexecutou nem recontou o XML integral. Scripts/comandos
pré-execução estão em worker-errors-pg-procedure-20261023.json.

## Pacotes — sonda limitada

Raiz própria %LOCALAPPDATA%/Temp/maskgw-errors-package-20261023-6f3b1056.
Wheel/sdist novos, sem isolamento/rede; wheel reconstruído do sdist fora
do checkout. Extrator valida caminhos/tipos/contagens/tamanho antes de
extrair147 membros, sem link/traversal/drive/pessoal/docs/testes/frontend.
Wheel121 entradas; **todos** os .py maskgw em ambos wheels comparados byte
a byte com src, inclusive o módulo novo. Build inicial exit0 (chamada
db717c) precedeu o checker, por isso não está em commands do result.json.

Instalações separadas --no-index --no-deps --no-compile, ambiente allowlist,
-I -B/cwd externo. Dependências do interpretador existente, não isoladas.
Sonda C1 copiada, acrescida de RESOURCE53 fatal,57014 QueryTimeout e
QUERY22 candidata. Uma referência de import no programa externo foi
corrigida para maskgw.errors **antes da primeira sonda**, sem execução
reprovada ou mudança no produto.40 módulos carregados vindos de cada
target e idênticos aos fontes; C1 continua com dois NOT_READY. Contraprovas
stale/checkout exit1 esperado; demais comandos exit0. Não comprova app
instalada completa, PG em pacote ou contenção de SO.

| Artefato | SHA256 |
| --- | --- |
| wheel |ffd27ee51243cc2570236da0e62f7d3c31fc75805fbb7116341210c4c47ad1ac|
| sdist |3ac71576afb39752f92efe06a7cdbf181da0dd8e0862f36b79f4e3264bcfa8c4|
| wheel reconstruído |f6dbd00d12e1e83316979dc6ecda4aaa47fb1085bed26b7082a8c8070939d1f7|
| result.json original |e3920e5b70dbb8b45004bb85ab199cf0d528108487ae87bb5dc9cfb109e7d12a|

Cópia docs/poc/evidence/worker-errors-package-20261023.json:
18.206bytes/SHA71a4ea3016da8ceb85203e0143017023cce089e444ea23b4bab06b4e8431497b,
sete arquivos externos UTF8/hash/tamanho (result,checker,probe,quatro logs).
Asserções desse checker externo executadas sem -O, sob -I que ignora
PYTHONOPTIMIZE. Nenhuma alteração de recurso/selo da UI ou dependência.

## Fechamento

Claude2 sessão51ea0d85, handle42134 terminal: revisão final somente leitura
de código/evidência/D-117 sem bloqueador para fechar o incremento isolado.
As duas notas documentais sobre XML integral e origem da contagem CLI
foram incorporadas acima, sem reexecução ou alteração funcional.
Auditoria final dos618 arquivos confirmou somente os oito deltas esperados
entre arquivos anteriores: sete documentos de estado e db/postgres.py.
Manifesto src/tests/POC da execução PG ainda idêntico; raw das duas cópias
coincide byte a byte com os externos e seus hashes/tamanhos. Capturas
anteriores e .venv/pyvenv.cfg intactos. Baseline/auditoria preservados em
docs/poc/evidence/worker-errors-source-{baseline,audit}-20261023.json.
Audit SHA2ad91b7b0fcce1bd721f43aee4b2bef7883307803316c5683124ed704e0bbaba.
git diff --check limpo, só avisos LF/CRLF; HEAD inalterado,0behind/1ahead
contra origin/master em cache. Após gates funcionais, só documentos novos
ou de estado foram editados; suítes não repetidas.
Não há chamada operacional nem fechamento de B-1/B-2/D-090. Próximos
incrementos devem integrar protocolo/worker sob domínio físico comprovado,
sem transformar um perfil C1 NOT_READY em permissão para SQL. Destino de
produção ainda não informado; não presumir servidor/OS/credencial.
Sem commit/push/deploy; não declarar aplicação pronta em produção.
