# Chamador privado da coleta — validação com fakes

2026-11-04, America/Sao_Paulo. Sob delegação geral, sem inventar aprovação
individual ou autorização de efeitos nativos. Claude2 foi o único
programador: sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5, esforço medium. O assistente principal revisou, escreveu
QA independente e registros, executou os gates e conferiu a publicação.
Base HEAD/origin36227aa,0/0, árvore rastreada limpa antes da rodada.

## Fontes finais e escopo

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| docs/poc/pg16_shell_native_control_collect_entry.py | 26337 | 3d309771f5b33151aaf8773bdc86fbca57a1d1777ea2620848133ad1129c9e4b |
| tests/test_pg16_shell_native_control_collect_entry.py | 38239 | 2e18c2b5ce22b953843115a55a2d0d33eb02925907610666969d94fab64454d2 |

Um novo chamador privado. Os três insumos pinados continuam: composição
37b098cf/5373bytes, coletor1972ec74/20571bytes e backendccb3f74a/22315bytes.
Verificadorb375, entrada dos controles356d, runnerb419, adaptadoreaeb,
backend10c9, hostdfcc, testes63/29, fontes/raízes consumidas e estado16
ficaram intactos. Nenhum src, UI ou dependência mudou.

O código define leitor limitado dos três fontes públicos e fábrica
preguiçosa que chamaria _load_native. As definições existem, mas **nunca
foram invocadas** neste incremento. O import é léxico; resolve só nos
helpers de S1, que também não foram exercitados. Não lê binário para derivar
argv0: constrói a mesma forma REPO/.venv/Scripts/python.exe do host do
runner. Seu comportamento operacional continua não medido.

As unidades positivas usam uma cópia da composição pinada com API Python
fake e bytes sintéticos. main só foi chamado nas recusas puras S0/S1 com
leitores falsos; **main positivo, _drive e _hold não foram executados**.
O driver/laço infinito foram inspecionados por AST, sem prova de vida
infinita, sinais reais, vínculo de PIDs ou sobrevivência ao encerramento do
app. Não é aplicação instalada ou serviço pronto.

## Contrato revisto

- Todas as três fontes são bytes exatos, tamanho/hash conferidos antes do
  primeiro exec. Executa os próprios bytes recebidos, não uma releitura ou
  alias de módulo mutável. Não autentica origem, runtime ou stdlib.
- Progresso e namespace são retidos antes do exec; _ATTEMPTS original é
  capturado após carga saudável, antes da única tentativa. Falha de carga
  intocada pode ser recusa pura; namespace parcial/ilegível é desconhecido.
- A fábrica registra sua entrada antes da captura, conserva registro,
  native_ns, namespace do coletor, _ACTIVE e _POISON originais antes da
  carga. A primeira operação conserva backend, _open e _retained antes de
  delegar. O construtor do adaptador de sete operações não delega nada.
- O primeiro erro privado e o primeiro controle são guardados em campos
  independentes antes de KEEP.append falível. Tracebacks permanecem
  referenciados; o teste com Token fraco confirma retenção pelo estado
  privado/erros. Não identifica uma única referência exclusiva: KEEP pode
  guardar outra referência ao mesmo erro.
- Guarda estrutural por identidade e tipos exatos dos registries antes de
  cada delegação, inclusive close. Durante a operação os ledgers podem e
  devem estar não vazios; vazio só entra na prova terminal.
- Incerteza de inspeção fica latched e não é promovida quando uma leitura
  posterior funciona. Decisões EXIT exigem forma normalizada e igualdade
  com a decisão recomputada do desfecho atual; estado incerto estaciona,
  sem retry, limpeza forçada ou recuperação.

Precisão sobre vazio: namespace e _ATTEMPTS permanecem não vazios por
projeto; a tentativa conserva um registro. A prova terminal é dos ledgers
de recursos _ACTIVE/_POISON/_open/_retained, com os objetos originais e seus
tipos. Capturar referência não prova cleanup. Um FINAL escrito antes do
return também não prova término; uma rechecagem posterior pode estacionar.

Os seams privados não são autenticação contra chamador hostil, nem as
sondas com fakes são exploração externa medida. Sinais fatais repetidos,
término externo e interrupção entre bytecodes não têm imunidade absoluta.

## Histórico medido antes das correções

Todos os terminais foram recuperados antes da chamada seguinte, mesma
sessão/modelo/esforço, sem segundo escritor. O plano só leitura47963,
iniciado03/11, terminou0; seu terminal foi recuperado04/11 antes de avançar.

1. CLI97475 escreveu só desenho/testes. Testef850633b/27130bytes:
   **81 coletados,79erros+2falhas**, todosFileNotFoundError,3,258s/saída1,
   módulo ausente, não regressão de produto. Contagem preliminar82 errada
   corrigida. Ruff/mypy do teste limpos; format reprovado em uma assinatura.
2. CLI48054 refinou contrato/testes:182ad729/31841bytes. **91 coletados,
   89erros+2falhas**, todosFileNotFoundError,0,977s/saída1. AST dos81
   originais idêntico. Uma nova assinatura ainda fora do format. Root
   reproduziu setup errado: _open é atributo de instância, portanto criar
   property na classe exige monkeypatch.setattr(...,raising=False).
3. CLI38460 corrigiu só setup e whitespace. Testec868fef7/31927bytes:
   **91 coletados,89erros+2falhas**, todosFileNotFoundError,1,005s/saída1;
   Ruff/format/mypy do teste limpos, antes de qualquer implementação.
4. CLI8846 implementou só módulo/desenho. Candidatada8992b9/22966bytes,
   lida integralmente pelo root antes dos testes: **90pass/1falha** em91,
   11,039s/saída1; estáticos limpos. A falha foi do harness, não atribuída
   ao produto: patch.setattr('sys.stdout',...) dentro do sealed fazia
   pytest resolver o nome via importlib.import_module, proibido pelo teste.
   Diagnóstico fechado localizou esse caminho antes do código de saída.
5. Três sondas independentes finitas reproduziram F1–F3 abaixo. Fonte
   rejeitada, teste, diagnósticos e métricas preservados como dados.
6. CLI71324 corrigiu o alvo para sys já importado, sem relaxar bans, e
   acrescentou regressões; fonte da899 intacta. Testee9c25833/38207bytes:
   **120 coletados,92pass/28falhas,0erros**,14,286s/saída1;
   26AssertionError e2Signal. Os91 anteriores passaram. Ruff/format limpos;
   mypy apontou apenas dois fired locais sem anotação, falha preservada.
7. CLI66039 corrigiu invariantes no módulo/desenho e somente essas duas
   anotações list[bool] no teste. AST confirmou todos os asserts e
   decorators preservados; sem remoção de caso, skip, ignore ou cast.
   RED foi medido em e9c25833 antes das anotações, sem alegar que o hash
   final2e18 foi medido vermelho. Leitores/fábrica/main/hold permaneceram
   não invocados. O root revisou o delta antes dos gates finais.

A sonda anterior do callback local mostrou um limite documentado da
composição37: ela retém o registro, mas absorve a exceção comum da fábrica,
sem conservar seu traceback. Isso motivou a retenção adicional no chamador;
não foi declarado finding no contrato anterior da composição.

## F1–F3 e sondas causais

| Sonda independente, finita | Candidata da899 | Fonte final3d309 |
|---|---|---|
| Controle na inspeção | Signal escapava; _fault e segundo settle permitiam EXIT0 sem PARK | Não escapa; primeiro controle retido e PARK persistente |
| EXIT0 com NOT_OK e hashes inválidos | Aceito por settle | PARK INTERNAL |
| _ACTIVE trocado após primeira delegação | 343delegações fake,31criados/31fechados e só depois PARK | 1delegação,1criado/0fechados e PARK UNKNOWN |

O mesmo QA foi reexecutado sobre a fonte atual, não sobre snapshots
rejeitados. A retenção do handle fake na terceira sonda é intencional:
nenhuma operação posterior, inclusive close, passa por cadeia desconhecida.
O backend e os ledgers ficam retidos; **não é prova de fechamento**.

F1: _custody/decide/_accepted protegem BaseException e conservam o primeiro
erro/controle, com inspection_unknown persistente. O controle legítimo antes
da fábrica continua EXIT5; a incerteza não é inferida de qualquer controle.

F2: tipos exatos e pares legais código/motivo/hashes, seguidos de comparação
com a decisão atual validada. Decisão antiga ou forjada estaciona sem
publicar sucesso ou sentinela. A igualdade ocorre só sobre formas já
normalizadas, não sobre valores hostis arbitrários.

F3: native_ns original explicitamente conservado, _chain compartilhado e
_guard antes de toda delegação. Trocas de _ACTIVE/_ATTEMPTS/native_ns/
_open/_retained são recusadas sem nova delegação ou cleanup forçado. A
inspeção terminal usa a mesma cadeia, exigindo os ledgers vazios ao sair.

## Gates finais

Runtime de referência Windows CPython3.11.3, mesmo .venv de testes. As metas
3.11/3.14 do mypy são estáticas; não se executou runtime3.14. PoC excluído
do mypy.

| Gate | Resultado |
|---|---|
| Próprios do chamador | **120 passed**,15,596s/saída0 |
| Relacionados,7arquivos | **868 passed**,45,992s/saída0 |
| Três sondas independentes | invariantes corrigidos, resultados na tabela |
| Ruff src/tests | aprovado |
| Lint PoC E9/F63/F7/F82 | aprovado |
| Format src/tests + novo PoC | **352 arquivos conformes** |
| mypy strict src/tests, alvo3.11 | **351 arquivos sem erros** |
| mypy strict src/tests, alvo3.14 | **351 arquivos sem erros** |

Zero falhas, erros ou skips nas suítes verdes. Os sete arquivos são os
testes de chamador da coleta, fábrica, composição pinada, backend Win32,
coletor, verificador e entrada dos controles. Depois dos gates só houve
fechamento documental e arquivamento como dados; código/testes conservaram
os hashes medidos.

Não se repetiram nem se declaram aprovados neste incremento suíte integral
de produto, PG real, Docker, browsers ou pacotes. Testes finitos e AST do
loop não provam vida infinita ou suporte nativo.

## Arquivos de revisão e coordenação

docs/poc/evidence/native-collect-entry-review-20261104 conserva baselines
81/91, candidata rejeitada, RED120, relatórios e QA em py.txt. São dados,
não fontes para reexecutar. QA inicial1915bytes,
6a56a568b9b7829d35c8e7e46c1a065896325bad79f358e5e7bf5af8f9007869;
sonda do callback766bytes,
2db9653a98ea5e7e18cd9eaf6601c9001563cd96a51c4188eb4e4bf32b4269fb.

Zero Claude2 ativo após terminal66039, reconferido antes do fechamento.
Tarefa histórica Maskgw-Claude2-Resume-01a05804 relida Disabled, sem próximo
disparo, último03/11 às16h35Z/result0. Nenhuma nova cota/reset/job,
conta/modelo ou escritor adicional. Arquivos pessoais não rastreados
preservados e excluídos do commit.

## Pendências operacionais

A fábrica preguiçosa está definida; sua **ativação** e observação real,
conversões ctypes/ABI, suporte de classes, perfil NTFS/dispositivo,
fechamento e sinais continuam não medidos. Captura operacional das fontes,
proposta concreta e comando exato ainda exigem revisão antes de efeitos.
Nenhum root/nonce/comando foi preparado ou consumido por este lote.

Sem leitura explícita de runtime/config/binário, DLL/API/job/process/control
real, instalação real de sinal, Docker/PG/SQL ou deploy. Imports normais de
Python não são promessa de ausência de DLLs ou leituras implícitas do
interpretador. Native3s NOT_MEASURED, entry_gate NOT_EVALUATED, identidade
consumida LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED; Gateway/B1/B2/D090gate2/
C1/SQL/produção abertos. Destino final Docker OracleLinux9.8 nesta máquina,
sem nova instância pronta para testes do usuário neste incremento.
