# Verificador privado de evidências — núcleo puro revisado

Data: 2026-11-03, America/Sao_Paulo. Base002c6a49d61571630335845f97bb88c5297746ca,
HEAD/origin confirmados por fetch; árvore rastreada limpa antes do lote.
PENDING e CHECKPOINT lidos primeiro; zero chamada da sessão/print antes de
cada chamada. Claude2 único programador, sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5/esforço medium. Root revisa, executa gates e registra fatos.
Decisões sob delegação vigente; nenhuma aprovação individual inventada.

## 1. Contrato aceito e limite

CLI25013 terminou0, só leitura, propondo núcleo puro. Leitura de arquivos
fica fora deste incremento; não se promete eliminar a corrida de lstat/open.
O núcleo confere bytes fornecidos e coerência semântica; não atesta origem
do disco, execução nativa, CIM ou cleanup. Coletor confiável e proposta de
execução/preflight continuam pendentes. Identity mantém o rótulo histórico
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED, sem replay.

Expected com dois campos nonce/argv0, sem revelar argv0 em repr/str; pins,
limites e ambiente fixos. API devolve só dois rótulos fechados. Arquivos JSON
com LF único e esquema/caps/tipos fechados; whitelist11, prefixos3/6/11,
hashes e semântica recomputada, incluindo os seis campos do snapshot.
inner_closed continua autodeclaração do summary, sem prova independente.

## 2. Testes escritos antes do módulo e baseline ausente

CLI33591 terminou0, escrevendo só VERIFY-DESIGN e o teste, sem executar nada.
Root leu integralmente ambos. Módulo conferido ausente antes de medir:
204 coletados;203 erros de setup e1 falha no teste de fonte; todos204 por
FileNotFoundError;exit1. É ausência da funcionalidade nova, não regressão
de produto. Nenhum teste aprovado nesta baseline.

SHA-256 dos arquivos antes da implementação:
- teste: ab35babf8b2e88c9b49c0a6a8d00774f7338fe02c437fb911ea4c8993a5062a6;
- desenho: f64384ff62dd86cf36d757106d3995dbe04ddc83818aa98c90781ec635c73b68.

A saída normal ficou truncada; a mesma baseline foi repetida só com relatório
fechado de contagens/tipos, sem mudar fontes ou fixtures. A primeira tentativa
desse relatório teve exit4 porque no:terminal removia a opção -q; corrigido
somente o roteiro efêmero do revisor, limpando addopts e retirando -q. A
repetição concluída produziu as contagens acima, sem traceback ou payload.

Ruff inicial:5 erros (duas funções de fixture com argumentos demais, lambda
redundante e dois comentários longos); format recusou1arquivo. Correção de
estilo solicitada ao programador preservando casos e assertivas, sem ignores.

## 3. Histórico da implementação inicial

Zero escritor confirmado antes de CLI94056, mesma sessão/modelo/esforço.
Escrita só no novo núcleo, teste e desenho. Root também exigiu captura local
única dos campos Expected e do dict privado limitado a11entradas, evitando
releitura de entradas mutáveis do chamador. Testes determinísticos de mutação
devem ser anexados antes do código; sem threads reais ou efeitos nativos.

Ainda sem parecer final ou gates verdes deste incremento. Runtime confirmado
por metadados: Windows/CPython3.11.3. Tarefa histórica relida Disabled, sem
próximo horário; último run01/11 às21h24m15Z/result0. Nenhuma quota/reset,
tarefa nova, conta/modelo/escritor alternativo. Fontes aceitas/estado16 fixos.
Sem rodada real, DLL/job/processo nativo ou leitura explícita de configuração/binário do runtime,
root/nonce/comando operacional, Docker/PG/SQL/serviço/deployment.
Native3s NOT_MEASURED/entry_gate NOT_EVALUATED; Gateway/B1/B2/D090gate2/C1/
SQL/produção abertos. Destino DockerOracle9.8 nesta máquina preservado.

## 4. Candidato inicial rejeitado — um P2 de domínio numérico

CLI94056 terminou0. Root leu o módulo inteiro e as alterações do teste.
Fonte inicialc833e4c86109f49275b88471bf4b40b88ab0f7ba28af46bb7ffba3547df7e69d
(24292bytes), testes4fe9fb0730992bd310c85d268960949a71c9ff26a420dd27e9a5ad65cd630058
(41511bytes). Próprios208casos concluíram exit0, sem falhas/skips visíveis;
este terminal não emitiu linha de resumo. Ruffsrc/tests e lint restrito do
novo PoC passaram; format recusou só a quebra da assinatura verify.

Cinco contraprovas finitas independentes: trêsCLEAN (colchetes em string
JSON e rejeições coerentes antes do lançamento nos casos1/3); duas receberam
VERIFIED_APPROVED indevido com LAST_CLOSE.exit_code=-1 ou2**32, summary e
supervision concordantes e hashes recalculados. Mais oito contraprovas
aceitaram VERIFIED_REJECTED para total_processes ou snapshot.total/active/
members fora de faixa (-1/2**32). Todos os insumos eram sintéticos.

O backend fixo usa DWORD para exit_code e Accounting.Total/ActiveProcesses;
members é comprimento não negativo de lista limitada. Root consultou a
[assinatura GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess),
que recebe LPDWORD; não chamou a API ou DLL. Domínio de campo é separado da
gramática numérica JSON: esses campos exigem0<=int<2**32, sem bool; null
continua permitido quando representa ausência de leitura.

Um P2 reproduzido, candidato não aprovado/não publicado. Bytes do módulo e
teste preservados como dados em native-verify-review-20261103, com tamanho/
SHA e marca do_not_execute. Zero escritor antes de CLI30082, agora limitada
a anexar regressões e notas, sem editar módulo. Root medirá RED antes de
autorizar o fix; nenhuma rodada nativa, collector ou produto foi tocado.

## 5. RED formal do P2 antes de liberar a correção

CLI30082 terminou0, só anexos no teste e notas no desenho. Fontec833
reconferida intacta; prefixo exato dos208casos anteriores preservado nos
bytes do teste. Medição:230coletados,13failed/217passed,zero erros/skips,
2,853s,exit1. As13 falhas AssertionError são exatamente os casos fora do
domínio unsigned32; nove controles novos de fronteira/nullable passaram.

Teste vermelho808869aac6429d6738d6ee3976e63bdd1f8fdaf491f14385d529c4b173a6c14c
(44944bytes), preservado em red-tests.b64/red-manifest.json na mesma pasta.
Relatório fechado do revisor registra só tipo, nodeid e contagens; nenhuma
asserção/fixture foi desativada e nenhum traceback/payload foi emitido.

Zero escritor antes de CLI66272; agora permitida só a correção de campo
unsigned32 e a assinatura formatada no módulo, mais notas de desenho. Testes
não estão no escopo de escrita dessa chamada. Ainda sem resultado final.

## 6. Correção e gates do núcleo puro

CLI66272 terminou0; só módulo e notas de desenho. Teste808869aa reconferido
intacto após o fix. Root comparou o diff completo contra a fonte rejeitada:
constante UINT32_LIMIT, helper nullable exactint/bool-rejected, sete usos nos
campos de summary/supervision/snapshot e assinatura verify formatada. Sem
mudança de produtor, limites, ambiente, pins ou estado16.

Fonteb3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10
(24616bytes). Medido depois da correção:
- próprios230passed/3,529s/exit0,zero falhas/erros/skips;
- cinco probes independentes CLEAN,exit0, e oito probes de contadores agora
  INVALID/SCHEMA,exit0; mesmos insumos e expectativas do vermelho;
- Ruff em src/tests e lint PoC restrito E9/F63/F7/F82 aprovados;
- format em src/tests+novoPoC:347arquivos conformes;
- mypy strict em src/tests,346arquivos, alvo3.11 e alvo3.14 sem erros.

Mypy cobre src/tests, não o PoC; alvo3.14 é só estático. Execução do lote é
Windows/CPython3.11.3. As duas métricas de probes não são execução nativa.
VERIFIED_APPROVED valida os bytes fornecidos; não é assinatura/autenticação
do produtor nem prova de origem do filesystem, execução, CIM ou cleanup.

Matriz relacionada22arquivos, sessão56643 terminada0:1301coletados e1301passed,
384,25s,zero falhas/erros/skips. Nenhum writerClaude2 ativo; não houve quota/
reset. As13contraprovas independentes foram repetidas sobre o código corrigido
e passaram; os230 próprios também estão contidos nesta matriz final.

## 7. Parecer e escopo da entrega

Núcleo puro aprovado pelo root no escopo de bytes fornecidos, sem P1/P2
remanescente identificado nesta revisão. Um P2 corrigido com regressões
medidas antes do fix, sem remover ou enfraquecer testes. Fontes fixas de
entrada/runner/adapter/backend/host reconferidas; hashes e tamanhos dos três
snapshots de revisão decodificados conferem. Os cinco arquivos de revisão
são dados, marcados do_not_execute, nunca inputs de uma rodada operacional.

Depois dos gates só documentação mudou; não se repetiram testes por edição
editorial. Produto/src, dependências, UI, recursos e fontes aceitas anteriores
não mudaram. Sem Node/browser, wheel/sdist, PostgreSQL ou suíte integral do
produto neste lote. Gates registrados têm o escopo explícito das seções
anteriores; não se reaproveita contagem antiga como medição nova.

No fechamento, diff-check identificou CRLF dos dois manifestos de revisão
sob a regra -text. Só as terminações desses metadados foram normalizadas
para LF; objetos JSON e bytes/SHA dos snapshots decodificados reconferidos
iguais. Código e testes não mudaram.

Coletor confiável não implementado; bytes de disco e origem real ainda não
atestados. Antes de executar controles continuam necessários contrato/testes/
revisão do coletor, binding das amostras CIM e saída terminal, fonte/runtime
pins, nonce e proposta/preflight próprios. Nenhum root ou comando operacional
foi preparado. Native3s NOT_MEASURED/entry_gate NOT_EVALUATED; Gateway/B1/B2/
D090gate2/C1/SQL/produção abertos. Não houve tarefa nova nem troca de conta/
modelo; tarefa histórica Disabled, sem próximo horário. Destino preservado.
