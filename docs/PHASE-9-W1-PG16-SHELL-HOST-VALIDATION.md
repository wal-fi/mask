# Coordenador público do leitor PG16 — código e fakes

Data: 2026-10-30. Escolha sob a delegação vigente, sem atribuir aprovação
individual nova ao usuário. Estado inicial: HEAD/origin42ff4ab sincronizados;
nenhuma mudança rastreada, arquivos pessoais não rastreados preservados.

## Escopo e fontes

Novo `docs/poc/pg16_shell_host.py`, só definições, sem main/entrada operacional.
Subclasse explícita do host7275c8ae, inicialização direta das definições V2b593
e journal4bc preservado; não inicializa nem executa o coordenador single-case.
Pin próprio do host no estado, mais delivery42f7/profile8906/policy96e8/watchcf66/
volumes6e38/emergency54cc/identitydc248, capturados por SHA. Não altera fontes,
raízes ou artefatos consumidos por rodadas anteriores.

Desenho em SHELL-HOST-DESIGN, revisão2192 e suas oito precisões. Revisão29625
recusou o primeiro hostd65fccc5 com três P2 de código e um gate de orçamento.
Correções abaixo.59784 recusou um P2 restante de categoria; corrigido com
regressão vermelha.61196 aprovou as definições/fakes isolados, sem P1/P2 de
código. Gate de orçamento pré-native permanece aberto.

- Lista fechada dos23casos, sem seletor do operador. Createprocess medido por
  caso e delivery_plan completos comparados por bytes JSON canônicos ao estado.
- Cada record possui case/Intent/owner/birth próprios. Owner da entrega usa seu
  próprio C/Target/Absent; perfil e parser usam seu próprio Case/Image. Cruzam
  só primitivos, SHA, bytes e campos do descritor. Wrapper/Target/descritor são
  conferidos antes de start; registro do owner precede spawn e Birth é capturado
  em finally. Nenhuma credencial/Seed privado nesta matriz pública.
-23Stores/Watchdogs construídos antes de A em watch-01/…/watch-23/, sem iniciar
  threads no constructor. Só o primeiro inicia antes de A; mesmo Bstart armado
  uma vez em todos. Snapshot nunca volta a None. Heartbeat local por Store.
- Passagem entre casos exige CID ausente, volumes iguais após prova durável,
  owner liberado, monitor close/join positivo, heartbeat aguardado e metadata
  persistida/nofire/noheld. Callback fechado sobre case só cancela o foreground
  daquele case e dá ack ao próprio monitor. Todos monitores ficam registrados.
- CLI fechado por blueprint/record/CID, tokens kill/rm de uso único consumidos
  antes do await. CID removido só admite consulta de ausência. Invoke exige
  token interno exato; PowerShell só aceita os dois comandos fixados de4bc.
  Nenhum run/exec/cp/install/commit genérico. Esses guardas estreitam a API
  interna; não são sandbox contra mutação Python arbitrária do coordenador.
- Intents/reports em case-NN-<case>-*.json e saída local-case-NN-<case>-output.bin.
  Raw de inspect/volume é somente local; version/info crus são descartados,
  com projeções validadas. Exportador ainda não existe: não publicar esses
  arquivos nem reutilizar exportador95f0 flat no layout novo.
- Reaproveitados por identidade de objeto: journal/save V2, _metadata,
  _inventory_volumes, _task, foreground, _removal, record_intents, _volume_final
  e os três guardas que recusam hooks antigos. Evidência de volumes mantém
  os schemas genéricos MASKGW_PG16_PUBLIC_VOLUME_*; não promete esquema reader.

## Resultados medidos até a revisão

Windows3.11.3, testes contra CLI/owners/monitores simulados. Comandos sem
Docker/PowerShell/shell real, PostgreSQL, initdb, servidor, SQL ou worker.
O guardTimer independente de40s do pytest é uma thread auxiliar real, termina
o processo de teste se houver travamento; não é watchdog nativo do ensaio.

- Seleção própria final antes da revisão:38passed/26,04s, zero falhas/skips.
  Todos23casos percorrem o coordenador fake, incluindo19faults/exit42 e nove
  HEADER_PREFIX. Contagens de stdout/report ligadas ao READY e State exigido
  parado/Pid0/semOOM/semDead/ExitCode exatamente igual ao returncode real
  fornecido pelo fake. Parser original recusa relatório diferente/prefixo+IO.
- Três regressões próprias falharam antes do fix (3failed/35deselected/1,69s):
  exceção de close interrompia coleta dos heartbeats; set de joins sobrepunha
  metadata negativa; expirar B durante pins ainda permitia owner.start.
  Agora close desconhecido conserva HELD e para heartbeat; _all_joined consulta
  metadata; há checagem de prazo adicional imediatamente antes de owner.start.
- Fakes cobrem ambiguidade de create sem retry/adotar por nome, CID retirado,
  token de remoção consumido em falha, cancelamento/envio/IO/start/report/exit,
  falta de ticket/ownerrelease, persistência de intent e volume-final, coleta
  do record antigo com case selecionado diferente, callback obsoleto, fired
  durante join, prazo expirado depois do join, join desconhecido, troca de
  wrapper, projeção de configuração hostil e restauração segura após fired.
- Ruff src/tests e helper E9/F63/F7/F82 limpos. Format334arquivos conformes;
  mypy strict333arquivos, alvos3.11/3.14 limpos. Runtime somente3.11.3, não3.14.

Desenvolvimento preservado: a primeira seleção usou encoder fake importado
que já embrulhava uma lista e resultou em JSON duplamente embrulhado; corrigido
o stub. Na seleção seguinte de38,37passaram e um mock de restore recusou a
listagem de volumes obrigatória. Mock corrigido, sem mudar produto para fazer
passar. A repetição integral própria38/26,04s acima passou. Nenhuma medição
shell/Linux/Proactor/EOF real é inferida desses fakes.

## Correções após a revisão29625

Fonte atual3624327f93aecb445c6042caf709fca1614c6ecafa9c6512002f25bdb1afb309,
39979bytes.50próprios/34,08s aprovados, Ruff/format334/mypy333 limpos nos dois
alvos. A seleção de49 anterior passou45,91s antes de acrescentar a checagem
de prazo após pins do CLI. Runtime somente Windows3.11.3.

Cinco regressões P2 falharam antes do fix:5failed/38deselected/4,29s. São as
duas conferências finais de fontes depois de prazo expirado/fire, as duas
falhas de metadata/heartbeat que interrompiam o shutdown e a ausência de
evidência de inspect pós-execução na linha do caso. Agora:

1. `pins()` confere só fontes/pins/endpoint, também relê o original4bc, sem
   misturar inputs_unchanged com estado de execução. `_gate()` separado faz
   deadline/fired nos controles e em perform_b. O invoke novo preserva tokens,
   conferência de fontes e log de comandos, mas revalida `_gate` depois dos
   hashes e antes do backend privado `_bounded`. Assim um pins que consuma o
   tempo restante não inicia outro CLI. `_bounded` mantém a distinção4bc de
   ambiente para public_clock/app_start, capturando a mesma fonte fixada; não
   aceita ambiente do operador. O mock passa a substituir esse backend, sem
   saltar o controle de tokens/estado do invoke novo.
2. Close, parada/await do heartbeat, leitura de metadata e persistência têm
   blocos independentes. Falha marca erros fechados/HELD; stop_supervision
   tenta todos os monitores e só ao final levanta SUPERVISION_HELD sem cadeia
   original. Resultado usa metadata coletada em cache, sem segunda leitura
   crua que pudesse interromper o fechamento. Join físico positivo permite
   restauração segura; falha de evidência nunca autoriza próximo caso nem
   converte o ensaio em passe. Metadata negativa não é anulada por set de joins.
3. Cada caso inclui inspect_exit_code/oom_killed/dead/report_ok/report_category
   e inspect_label/inspect_cli_index/inspect_artifact ligados ao inspect feito
   depois do retorno do owner (inspect-result-<case>). O manifesto local liga
   label/índice/hash/bytes ao raw; futuro exportador deve verificar essa ligação
   antes de projetar somente fatos fechados, sem liberar o raw.

Notas P3 tratadas neste código: tokens kill/rm limpos no finally de coleta;
create_invoked registra intenção conservadora antes da chamada. Se o create
nunca foi submetido, cleanup pode registrar create_not_invoked e provar os
inventários globais sem inventar CID/ausência/remoção. Isso não conta como
caso concluído. Submissão ambígua continua HELD, sem retry/adotar por nome.
Regressão dessa distinção falhou primeiro:1failed/48deselected/2,30s.

Ampliados os fakes: override real de checkpoint(B) arma todos23Stores uma vez
e persiste/replay12checkpoints; asyncio.timeout real com B encurtado só no
teste para0,5s cancela drain ou collect e ainda recolhe depois; constructors
reais dos23Watchdogs e check_snapshot, com apenas start/thread simulados;
owner real em NEW quiesce/close sem spawn. Nenhuma thread de watchdog/CLI foi
iniciada nessa prova dos constructors. Timer de guarda40s permanece auxiliar
real. Não se afirma teste de shell, EOF/exit42 nativo ou prazo do Windows.

O P2 de orçamento é gate **antes da proposta/rodada nativa**, não encerrado
por estes testes. Os seconds de4bc (e do invoke variante) começam depois de
pins; não incluem hashes síncronos de docker.exe/Desktop.exe/powershell.exe.
A composição de23casos faz centenas dessas leituras, além dos pins explícitos
por caso e das releituras do original. Antes da execução medir custo por
chamada e somar ao custo total projetado, ou revisar redução de frequência
separadamente. Não justificar B300 somente pelos tempos anteriores de CLI.
Nenhum cache/relaxamento de pin nem prazo de produto alterado nesta correção.

Nota para a entrada futura: se emergência estiver com o mutex, a primeira
coleta pode falhar em1s. Depois de join comprovado, tentar novamente a coleta
dos mesmos records antes de declarar HELD definitivo; nunca criar outro CID.

## Fechamento da revisão61196

Fonte8c41605f5f44f355632b05167c6348fb09752472b6d59b26961604023a613018,
40791bytes, aprovada pelo Claude2 em61196.52testes próprios aprovados/49,90s.
Seleção final dos oito arquivos host/delivery/reader/owner/profile/policy/watch/
host-público:304passed/59,10s, nenhuma falha/skip/deselected; todos fakes.
Ruff src/tests/helper, format334 e mypy333 alvos3.11/3.14 limpos; runtime só
Windows3.11.3. A seleção relacionada302/56,67s pertence ao3624327f; não é
apresentada como medição da fonte final; a medição final é304/59,10s acima.

59784 apontou report_category nula nos19negativos: o parser devolve category,
não fault. A matriz completa falhou antes do fix (1failed/49deselected/5,93s).
Agora cada categoria é comparada à do Vector original: noveHEADER e três
DEADLINE, demais BODY/TRAILER/SURPLUS e quatro positivos sem categoria.
Inspect_reply exige label exato, exit0 e artifact str antes de gerar a linha.

Heartbeat já cancelado com stop definido pode ser comprovadamente coletado
num teardown posterior; a regressão falhou primeiro (1failed/50deselected/
2,32s). Só se aceita isso quando a task filha está done/cancelled e a task
atual tem cancelling()==0. Cancelamento do próprio foreground continua HELD/
erro fechado e não avança caso; teste adicional cobre a distinção. Erros de
supervisão podem ser removidos em nova tentativa quando todos estágios forem
positivos. Isso não remove fired: a entrada futura deve consultar o campo
separado dos watchdogs, mesmo após erro de evidência resolvido.

## Limites e próxima composição

B300global é meta fail-closed; owner12s/shell8s e watchdog600s não mudam.
Não cabe a soma dos piores casos emB300. Justificar/recalibrar antes de uma
rodada nativa e preservar NOT_PASSED se exceder, sem ampliar após falha.
Margem aritmética534<600 do desenho inclui join bloqueante; não é garantia
de prazo absoluto do SO/filesystem. Normal CLI e owner.start rechecados por
monotonic, sem depender só do callback de asyncio.timeout.

Faltam entrada com HELD, exportador por projeção/recursive
sem symlink/reparse, preparador/estado/proposta/script e revisão antes de uma
única execução nativa. A entrada deve tratar falha de preparo antes de A sem
inventar baseline/estado inicial nem acionar daemon que não foi tocado, e
manter o loop vivo se houver owner/CLI/thread pendente. Um monitor não iniciado
é NOT_STARTED, nunca prova de join; um monitor disparado sempre reprova o lote,
mesmo quando recursos forem recolhidos e Desktop restaurado com segurança.

Nenhum container/DB/secret/raiz operacional criado. Gateway indisponível;
B1fimafim/B2/D090gate2/C1/SQL/produção continuam abertos. Sem job ou segundo
escritor. Não houve teste de aplicação/empacotamento/browser neste incremento
isolado em docs/poc; produto e dependências não foram alterados.
