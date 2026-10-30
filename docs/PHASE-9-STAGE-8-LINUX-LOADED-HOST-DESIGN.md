# loaded-as128 — observador externo, desenho antes do código

**2026-10-22 — proposta sob delegação; este lote só código/testes com fakes.**
Supervisor59/669 revisado sem bloqueador, ainda não executado. AS32 e seis
rodadas preservados. Não haverá CLI Docker, workload, download/instalação,
alteração do Desktop, banco, SQL ou liberação de produção neste incremento.

## Reuso explícito, não transformação silenciosa de outro fluxo

Novo docs/poc/run_linux_loaded.py e tests/test_loaded_memory_host.py.
Carregar run_linux_imports.py por seu loader já existente, que verifica os
dois helpers congelados. Herdar preparação/cópia/manifesto do seu __init__,
readiness/preflight e métodos baixos cli/inspect/save/identity/cleanup.
Override explícito de init/check/case/run: **nunca** chamar o case/run antigo,
alterar seu Cmd em memória ou usar classify_limited/fits_as32.

Init antigo só prepara arquivos e objetos sem iniciar thread/CLI. Na nova
raiz temporária própria, adicionar quatro fontes de membro (protocolo,
produtor, coletor e supervisor) ao probe RO e cópia do observador novo fora
do mount. Dez fontes no total; conferir originais/cópias antes de cada caso
e ao fim. Hash de identidade será SHA-256 do mapa canônico nome->hash das
dez fontes, explícito como bundle, não o hash primário antigo. Task/nome/
owner/profile/raiz são próprios loaded-as128. Preparação parcial existente,
owners/versions/generated, árvore e pins permanecem iguais e não são escritos.

CLI pública só --run <docker.exe existente> <prepared_root>. Sem modo
diagnose, digest externo, image variável, download ou retry de lote/caso.
Constructor/run podem operar uma vez por instância. Recurso de ambiente que
não pertence a este lote não é removido ou parado. Permissões efetivas valem.

## Perfil real, argv e preflight

Imagem BASE já pinada, dois mounts bind RO /probe e /installed, UID65534,
rootfs RO, rede none, IPC/cgroup privados, sem namespaces host/devices/ports/
extra binds/init/volumes anônimos/restart/healthcheck/log. CapDropALL e NNP,
memory192MiB/swap0,CPU1,pids16,shm1MiB,nofile64/core0. Env idêntico ao da
imagem pinada, sem -e. Validate_profile próprio confere **diretamente** os
campos reais, sem reescrever info para passar pelo validador antigo.

Entrypoint[python], Cmd exato[-I,-B,-S,/probe/linux_loaded_probe.py,--case,
control|private|shared,--expected,-|digest]. Control exige '-',128 exige
hex64 minúsculo igual ao digest admitido do controle deste lote. Conferir
inspect antes de start e depois de exit, com mesmo CID/task/bundle/nome.

Reusar preflight obrigatório: até3 version de5s/16KiB sob20s, só timeout ou
nonzero admitem retry predeclarado,1s entre tentativas quando cabe. JSON/schema/
cleanup inválido aborta; ps global deve estar vazio; inspect imagem Linux/
amd64 sem volumes e env fechado. preflight_passed só no fim; caso exige flag.
Procedimento externo com cada exit conferido e comando exato ainda terá revisão
separada antes da rodada. Watchdogs30s/caso e120s/lote são independentes.

## Admissão, uma tentativa e stop

Run uma vez, sequência control/private/shared. Case exige run ativo, caso
exatamente esperado e não tentado, e expected derivado da admissão anterior.
Registrar tentativa antes de timer/create; nunca reexecutar após falha.
Sem PRESSURE ou container128 a partir de controle que só completou imports.

Cada case: conferir fontes/cópias/runtime/tree antes de create; gravar pending
durável antes da chamada; create com pull never e argv explícito; CID hex64
validado, pending atualizado antes de inspect; só depois da identidade/perfil
conferidos entregar CID aos watchdogs. Start attach limitado a64KiB e saldo
de30s; inspect final exige CLI0, container parado/ExitCode0/OOMKilledFalse.
Artefato bruto do supervisor é preservado separadamente<=64KiB com fsync/
replace; case.json contém metadados e referência/hash, não duplica o JSON
grande dentro de outra linha64KiB. Artefatos cumulativos<=1MiB.

Validação do relatório: JSON único/ASCII/sem NaN/chaves duplicadas, perfil/
case/outcome/total_memory_containedFalse fechados. Sucesso exige sem failure,
cleanupTrue, returncode0 int exato, final_inventory[1] int exato, startup/
observações/cgroup válidos e limits esperados, sem pressão externa/counters
regressivos, inventário de módulos pelo codec antigo/digest único do core.
Não reimplementar classificador de held nem afirmar replay do protocolo: o
supervisor fonte conferida é a origem confiável dessas medições; o host
confere envelope, consistência e lifecycle, não mede /proc por Docker exec.

Controle deve ser control_ok e conter digest igual ao calculado pelo host
das linhas auditadas; só depois de cleanup/container rm e verificações de
integridade positivas esse digest é admitido para128.128 só vale imposed e
mesmo digest das suas linhas, sem campo inventory_digest publicado. O Cmd
de ambos contém o controle admitido. Qualquer fail/incompatible/inconclusive/
host failure/cleanup/integridade/tempo interrompe antes do próximo caso.

Cleanup só por CID próprio validado; create incerto recupera por nome exato
e confere labels/hash/CID antes de limpar, nunca toca coincidência estrangeira.
Recuperação não converte criação incerta em sucesso. Cancel/erro inesperado
fecha inconclusive com categorias fixas, sem mensagem original. Fechar ambos
watchdogs e confirmar ausência por ID; registro pending fica se incerto.
Nenhum sweep/rm global. Inventário global final deve estar vazio, como antes.

## Resultado final e provas deste lote

Summary tem profile loaded-as128, complete apenas se três tentativas executadas,
not_executed explícito, expected outcomes control_ok/imposed/imposed.
diagnostic_success exige também todos cleanup, fontes/cópias/runtime/tree
iguais, inventory_restored, watchdog_closed e sem deadline/host_failure.
Não significa contenção total/plataforma certificada; sempre
total_memory_containedFalse. Só três resultados válidos dão exit0; demais2,
argv inválido64. Não usar flag imports_fit_as32 ou promover produção.

Testes primeiro: fakes de CLI/inspect/watchdog/clock/preparação/filesystem
pequeno, sem criar CLI/processo real ou ler árvore preparada73MiB. Contraprovas
de todos campos relevantes de perfil e argv/digest/extra flags; controle
forjado/exit/cleanup/bool/NaN/cap/report grande; mismatch bloqueando casos128;
preflight falhando sem create, ordem e uma tentativa; timeout/criação incerta,
identidade estrangeira, perfil divergente próprio, limpeza confirmada/falha,
snapshot alterado, watchdog disparando, stop e resumo/not_executed.

Revisar desenho, código/testes, depois procedimento/comando real. Neste lote
nenhum construtor real sobre a preparação existente nem workload. B-1/B-2/
D-090 gate2/SQL/produção continuam abertos; sem commit/push ou segundo escritor.

## Refinamentos da revisão, antes do código

Claude2, sessão51ea0d85: sem bloqueador condicionado a H1–H4, incorporadas.

- H1: sucesso tem chaves exatas do supervise: profile/case/outcome/
  total_memory_contained/observations/cleanup_confirmed/startup/module_inventory/
  member_returncode/final_inventory/final_cgroup, mais inventory_digest **só**
  no controle. Negativo tem base+failure fechada e apenas campos opcionais
  alcançáveis do supervise, todos tipados, sem digest. Fallback exato de
  bounded_report sem case é REPORT_LIMIT/inconclusive. Exit70 sem dados é
  REPORT_MISSING;64 é argv inválido; demais nonzero/OOM são inconclusive.
- H2: conservar30s/caso e120s/lote; não há promessa de completar o pior caso.
  Fontes/cópias/runtime/tree antes e depois de cada caso ficam fora do timer
  do caso, **dentro** do watchdog120s. Se qualquer soma exceder prazo, parar
  inconclusive, sem elevar limites/repetir. Orçamento declarado:

  | Passo | Teto individual |
  |---|---|
  | readiness |20s, até3 chamadas5s e intervalos predeclarados |
  | ps inicial / inspect imagem |5s cada |
  | fontes/tree antes/depois |saldo do lote120s, sem subprocesso |
  | create / inspect pré-start |5s cada, consumindo caso30s |
  | start attach |saldo restante do caso30s |
  | supervisor |20s medição + até2s reap +2s relatório, sem ampliar caso |
  | inspect pós-start |5s, ainda contado no caso |
  | cleanup |inspect/kill/inspect/rm/ps até5s cada; atraso invalida o caso |
  | fechar watchdog |até7s do helper; atraso/erro invalida |

  Limpeza ainda é tentada depois de timeout; não se promete teto absoluto
  para SO/engine. A soma de máximos é maior que30/120 e **não** é autorização
  para estender: apenas execuções efetivamente dentro dos dois prazos valem.
- H3: em vez de herdar classe com algoritmos antigos, expor só métodos baixos
  selecionados por composição/atribuição e chamar explicitamente seu init de
  preparação (sem CLI/thread iniciada). case/run/check são novos e não há
  algoritmo antigo no MRO. Task loaded-as128 e hash bundle substituem campos
  antigos antes de qualquer pending/label/create/identity/cleanup. Assinaturas
  e guards novos recusam chamadas fora do fluxo autorizado antes de create.
- H4: raw imutável por nome de caso,<=65536 incluindo newline, fsync/replace
  e débito no1MiB antes de validar. case.json registra nome, SHA e tamanho;
  validação só depois da gravação. Cap excedido é OUTPUT_LIMIT, sem truncar.
  Integridade inclui também raws já validados antes de próxima admissão e fim.

Admissão explícita: unpack_inventory antigo -> inventory_digest único ->
igual ao controle reportado -> cleanup/rm/integridade -> grant próximo caso.
Cada128 precisa reproduzir esse digest. Nunca usar classificação AS32.
Código, perfis, fakes e comando terão revisão própria; nada real aprovado.

## Revisão do código: qualificação de negativos fortes

B1: fail/incompatible não podem ser aceitos só pelo envelope, mesmo que o
lote pare e nunca publique sucesso. São afirmações fortes de evidência.
Seis regressões primeiro demonstraram a lacuna (cleanup falso, FAIL sem
testemunha, código/stage errados, incompatible no controle e pressão externa).

Host agora exige startup/observações/AS128/CG coerentes, cleanup confirmado,
inventário final[1] e ausência de pressão externa/counter regressivo. FAIL
exige category OBSERVED_FAIL, rc=-9 ou0..255 (não sinal espontâneo), e a
última observação independente confirma pico>128 ou, em HELD, size>=pré+40.
Pré-pressão é índice5 dos casos128, não ready antes dos imports. O host não
mede o sinal: confia no supervisor hashado para distinguir kill próprio;
não classifica um sinal como recusa. Incompatible só nos128, stage imports,
MEMORY/IMPORT e código natural72/73 correspondente. Sem exigir digest de
módulos para falha antes do término dos imports.

Qualquer divergência desses negativos fortes vira inconclusive com
REPORT_LIFECYCLE no case/summary; raw original permanece imutável para revisão.
Testes mantêm fail/incompatible válidos gerados pelo supervisor fake e
verificam o downgrade dos forjados sem alterar os bytes de origem.
