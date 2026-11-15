# N-S: contrato consolidado para primeiros oráculos com SDK falso

2026-11-15. Fechamento pelo revisor após ler integralmente a proposta45475, o suplemento parcial75101 e os suplementos completos33580/88linhas e67827/62linhas. Os dois últimos terminaram0/service success/is_errorFalse, sem denials, recuperados; marcadores END_ABC_RECEIVED e END_D1_D2_RECEIVED confirmam recebimento integral. XJ3 e TODO EJ1–EJ6 continuam normativos. Este texto prevalece sobre propostas anteriores nos pontos que fecha.

## 1. Escopo e sequência

- Único fonte futuro: docs/poc/oracle9_w1_external_job_adoption.py. Único primeiro teste: tests/test_oracle9_w1_external_job_adoption.py.
- Ambos AUSENTES neste fechamento. Primeiro C2 escreve somente o teste, com Read/Edit/Write restrito, sem comandos. Root lê TODOS os oráculos, mede RED e só então congela o teste antes de qualquer fonte.
- Não é admissão de N-H/N-C, direitos reais, runtime, transferência ou efeito de job. Nenhum perfil com filho ou execução nativa alocado. Nenhum framework/Owner genérico/guardião novo.
- Backend10c9058f, adaptadoreaebedd6, C0c695a68b/43ffbf92, qualificador999f4a8d, fontes/testes/pins/app124/state16/tentativa anteriores permanecem fixos. Estado16 e tentativa não são lidos.
- Claude2 único programador, sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5/medium; root revisa e executa QA. Zero escritores antes de chamar; ativo só monitorar.

## 2. Módulo, loader e fronteira do cache

Import e construção só definem dados/funções/classes: nenhum resolve/lstat/open/compile/exec, DLL, processo, thread ou loop. Resolver o caminho somente na chamada explícita definitions. Não importar o adaptador/qualificador, registrar instâncias globais ou procurar módulos vivos.

Constantes: BACKEND_RELATIVE docs/poc/pg16_shell_admission_win32.py; BACKEND_SHA10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726; SOURCE_LIMIT65536. Reusar o contrato de leitura limitada: fonte regular, sem reparse final, tamanho do lstat igual aos bytes capturados, teto aplicado, SHA exato e AST de despacho conferidos ANTES de executar os MESMOS bytes. AST confirma o caminho herdado de UpdateProcThreadAttribute via self._ok e de ResumeThread/CreateProcessW via self._call. Código privado novo, sem alterar backend publicado.

definitions devolve exatamente quatro chaves: backend, Request, Win32Error, ExternalJobOwner. Request/Win32Error e a classe-base de ExternalJobOwner vêm desse MESMO namespace privado. Chamada posterior no mesmo namespace devolve o mesmo dicionário completo. Outro namespace novo tem cache próprio; nenhum cache de owners/handles vivos.

Cache inicial None. Construir namespace, classe e dicionário completo LOCALMENTE, e publicar com UMA atribuição. Declaração global deve preceder o primeiro uso, conforme sintaxe Python. Nunca update parcial de cache compartilhado. Antes dessa fronteira, falha comum deixa cache None e levanta AdoptionError com args exatos(ADOPT_SOURCE), fora do except, sem mensagem/cause/context originais. Controle não é engolido e deixa None se anterior à publicação. Controle DEPOIS da publicação pode deixar cache COMPLETO mesmo antes do return: não prometer transação que abranja todo bytecode. Nova chamada após falha pré-publicação pode tentar o carregamento novamente; isso não autoriza retry de efeitos nativos.

AdoptionError e ADOPT_SOURCE são nomes fechados escolhidos. Seu construtor nunca inclui argumento opaco ou diagnóstico bruto. Não há promessa de concorrência/reentrância de definitions: é o carregamento explícito do chamador único de S, não outro serviço de registro.

## 3. Classe e propriedades

ExternalJobOwner é subclasse específica do Owner capturado. Construtor(request) chama o construtor puro herdado. Propriedades públicas sem setter/deleter: external, external_state, adopt_attempted, adopt_control. Inicialmente None, NOT_ADOPTED, False, None. Prefixo privado _xj_ para backing fields e retenção da lista de jobs. Atribuição/deleção pelos nomes públicos deve levantar AttributeError. Não é barreira contra alteração arbitrária de campos privados por código privilegiado.

external_state tem apenas NOT_ADOPTED/ADOPTED/REFUSED. Nenhum método próprio fecha/termina C. O backend pode fechar sua posse genuína; não confundir candidato recusado por alias com empréstimo externo distinto.

## 4. adopt: prioridade, consumo e custódia

1. Exigir Owner READY. Fora disso, Win32Error WIN32_HELD se HELD, senão WIN32_STATE, sem consumo/consulta. Em READY, tentativa já consumida recebe WIN32_STATE, sem nova operação.
2. Consumir a tentativa ANTES da validação. Nenhum retry/rebind ou segundo candidato, mesmo após INPUT inválido.
3. Aceitar somente int built-in exato,1..2^64−2, seguindo _handle; bool/subclasse/int fora do domínio ou qualquer outro objeto recebe REFUSED_INPUT. Não bool/str/repr/eq/conversão de opacos; external permanece None.
4. Conferir formas internas com tipos built-in exatos: ledger dict, chaves str e valores de handle válidos; quarantine list plana de handles válidos. Não invocar igualdade/conversão de entradas opacas. Forma inválida recebe REFUSED_INTERNAL sem consulta. Fechamento normativo de segurança: nesse caso o Owner fica HELD/WIN32_INTERNAL, por atribuições puras, para close posterior não encaminhar dados corrompidos ao SDK. Nenhum campo anterior do ledger/quarentena é corrigido ou descartado.
5. Comparar só ints exatos para alias de ledger/quarentena: REFUSED_HANDLE, external None, Owner READY e posse anterior intacta. close herdado pode fechar normalmente o genuíno handle do ledger; nunca afirmar proibição baseada só na igualdade numérica do candidato recusado.
6. Candidato distinto vai para external ANTES da primeira consulta. A referência fica retida em todo desfecho posterior, inclusive QUERY/CONFIG/NOT_EMPTY/INTERNAL/CONTROL; não fechar nem terminar esse C.
7. Consultas próprias no molde do adaptador por super()._call: configuração estendida, contabilidade e membros. Falha de API/comprimento/estrutura inválida recebe REFUSED_QUERY; configuração válida mas divergente recebe REFUSED_CONFIG; contabilidade/membros válidos não vazios recebem REFUSED_NOT_EMPTY. Ordem: configuração, contabilidade, membros. Tupla vazia positivamente observada só se as três conferências passarem. TOO_MANY/membros malformados são QUERY. Não tratar consultas separadas como snapshot atômico.
8. Tudo positivo: ADOPTED e external_state ADOPTED. Recusa comum: external_state REFUSED; Owner READY, salvo a forma interna corrompida definida acima. Qualquer Exception inesperada na lógica da adoção recebe REFUSED_INTERNAL, sem diagnóstico ou cadeia original. Nenhuma recusa autoriza iniciar P.

Retornos exatos: ADOPTED, REFUSED_INPUT, REFUSED_HANDLE, REFUSED_QUERY, REFUSED_CONFIG, REFUSED_NOT_EMPTY, REFUSED_INTERNAL, REFUSED_CONTROL. Não acrescentar outra enumeração ou superfície administrativa.

## 5. Primeiro controle de adopt

Após consumo, capturar BaseException não-Exception no corpo de adoção. Guardar PRIMEIRO objeto exato em adopt_control; external_state REFUSED; Owner HELD e held_reason WIN32_INTERRUPTED, apenas com atribuições puras; devolver REFUSED_CONTROL. Não chamar _interrupt, re-raise, bool/str/repr, relógio, log, close, terminate ou outro SDK após essa captura. Não atribuir __traceback__/__context__; tampouco prometer que a propagação original feita pelo Python nunca acrescentou frames.

Depois disso start/close/adopt recusam por WIN32_HELD sem SDK; ledger/C ficam retidos. Controles fora das fronteiras capturadas ou segundo controle assíncrono permanecem resíduo explícito; isso não estabelece B4 global. Um controle no start/pré-resume segue a semântica mais fraca herdada (_guarded/_interrupt/OUTER), não a garantia restrita ao adopt.

## 6. start, despacho e referência emprestada

Override público mínimo de start: primeiro exigir READY, depois ADOPTED, antes de delegar. Sem adoção positiva, WIN32_STATE, READY preservado e ZERO SDK/atributos. Em HELD, WIN32_HELD tem prioridade. _start herdado permanece sem edição.

No despacho de UpdateProcThreadAttribute, validar a aridade7 antes de delegar. Para JOB_LIST, conferir o buffer de UM handle OUTER, tamanho/flags/None e identidade do ledger conforme o padrão do adaptador. Delegar par [OUTER,C] retido em _keep até o caminho herdado terminar. Sem re-adoção/segundo par. Outras chamadas válidas herdadas mantêm o caminho existente.

Antes de delegar ResumeThread, conferir argumento e posse, pertinência de P a C, configuração de C, contabilidade(1,1) e membros exatamente(pid de P). Nenhum ResumeThread real se isso falhar. O abort de posse/estado/erro segue o backend congelado; não inventar um único estado para todos os aborts.

**Guarda de saídas de CreateProcessW, fechada após revisão D2:**
- Capturar C antes da delegação. Acesso interno somente de leitura ao ProcessInformation _pending da cópia pinada é admitido nessa subclasse específica, nunca pelo chamador. Conferir forma/tipo exatos; não consultar atributo ou converter saída opaca.
- Antes de devolver os resultados ao _start, comparar os campos de handle normalizados só por _handle com C, usando ints exatos. Se hProcess OU hThread aliasar C, sinalizar (raised=True,value=None), independentemente de retorno nativo verdadeiro/falso/Exception. Não adotar saída em ledger.
- O caminho herdado lê/quarentena as saídas, limpa os atributos conforme o backend, contém só o OUTER e fica HELD/WIN32_CREATE. Nenhum wait, membership como processo, resume, terminateProcess ou close sobre C. Um controle segue o caminho herdado WIN32_INTERRUPTED; não prometer WIN32_CREATE em todo controle.
- Sem conflito, preservar resultado e comportamento herdados. Não modificar backend, buffers de saída nem inventar marcador público de conflito. Estado/reason e rastros do SDK falso bastam.

Asserções precisam ser POR PAPEL DO ARGUMENTO: QueryInformationJobObject(C) e IsProcessInJob(P,C) são usos legítimos do C como JOB. Proibido C como processo/thread, CloseHandle(C), TerminateProcess(C) ou TerminateJobObject(C). Um teste C ausente de todo touched seria incorreto e recusaria o caso positivo.

close herdado libera só o ledger do backend; C distinto fica fora dele, retido no adaptador até a saída de S. Owner CLOSED não declara C fechado nem liberação global de J. Não pressupor que fake/kernel sempre produzem handles disjuntos: forçar as colisões de saída no oráculo.

## 7. Primeiros oráculos e fakes

Reusar o Kernel falso e o modelo do laboratório tests/test_pg16_shell_native_control_win32.py, estendendo só o teste novo, sem editar referência. Injetar _load_api/sys SOMENTE no namespace privado recém-executado; nunca alterar funções/módulos vivos de produto. Armadilhas stdlib para WinDLL/Popen/os.system/Thread.start impedem efeitos reais. Nenhuma leitura de venv/configuração/ambiente/binário/estado16/tentativa.

Fake registra operações e argumentos por papel, inclusive consultas legítimas sobre C, criação e fechamento. Deve modelar outro job vazio e planos determinísticos: retorno verdadeiro/falso/Exception e controle, outputs C como processo ou thread, faults de consulta/comprimento/membros e guarda de no-resume. Não imitar o adaptador no fake.

Cobrir: pureza/import/construtor; loader/pin/cache/identidades; readonly; fora de estado e repetição; inválidos e opacos sem sondas; alias genuíno versus C distinto; forma interna malformada HELD; consultas determinísticas; controle exato e zero efeitos posteriores; start sem adoção; positivo de dois jobs/pré-resume; falha pré-resume; seis colisões de saída e controles; close de posse genuína versus retenção de C. Sem skip/xfail/cast/ignore/noqa ou assert enfraquecido.

Helpers/fakes podem ter sanidades próprias, identificadas como tal. Falta do fonte deve gerar falha explícita dentro do teste, não skip/sucesso nem erro de collection/fixture. Root lê TODO teste e mede todos os motivos do RED; só depois congela. Nenhum fonte antes disso. As futuras provas reais N-H/N-C/rights/transferência/EOF permanecem separadas e OPEN.
