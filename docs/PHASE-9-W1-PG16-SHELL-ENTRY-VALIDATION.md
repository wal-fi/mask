# Entrada pública do leitor PG16 — código e fakes

2026-10-30, sob delegação vigente. Checkpoint inicialad322b4 sincronizado,
árvore rastreada limpa; arquivos pessoais não rastreados preservados. Desenho
ENTRY-DESIGN aceito23065, sete precisões incorporadas antes do código.

Estado inicial desta evidência: fonte nova d0cb38385b867b4890cc28ba02d431dc16eddaaf249832b5a6e38bc9ce423dbb,
23322bytes.7256 recusou um P2 de ordem da prova terminal. Corrigido com
regressões vermelhas; fonte final afaffad0/24081bytes aceita pelo Claude2
em58487, somente como código/fakes isolados. Continuação em2026-10-31.

## Escopo

Novo docs/poc/pg16_shell_run.py, import somente definições e capturas fixadas,
main próprio que só admite uma raiz nova/estado canônico. Captura Host8c41605f
sem alterar executáveis/fontes/raízes já consumidos. Não herda main/drive de
outro ensaio; nenhum listener/produto/dependência alterado.

- Estado fechado em32768bytes, task32hex, versões/imagem/fontes/medidas23 e
  plano de entrega exatos. Runtime Windows3.11.3/Proactor/-I/-B/optimize0.
  Raiz no Temp conhecido, pais sem reparse/symlink, inicialmente só attempt.
  Invoked XB/fsync precede atualização de estado; colisão não repete tentativa.
  Alvo de admissão3s mantido, ainda não medido nativamente no preparador.
- Pins finais independentes de prazo/fire: Host.pins, entrada, stdlib, fontes
  transitivas ao vivo e bytes capturados de entrega/owner/canal/reader/perfil/
  policy e cópias alcançadas por cada monitor. Hash não autentica namespace
  depois de exec: o coordenador/interpretador permanecem parte da TCB.
- Vocabulário fechado por AST dos literais need/raise nos bytes fixados.
  Classes/enums exatos, sem str/repr/traceback original. HostFault da CLI
  comum por identidade; namespaces novos somente pelos code objects/globals
  exatos de Host._bounded ou clock.sample e pela classe daquele helper.
- ForegroundA ligado a one antes de start_cycle, cujo sample já pode chamar
  processo. Journal real de12checkpoints antes e depois de B. Sucesso exige
  todos23casos e23monitores JOINED/nofire/noheld, sem erros/interrupção/prazo,
  fontes/posse/volumes/CLI/tasks/owners coletados e Desktop restaurado.
- Após falha, primeira coleta própria. Se negativa, aguarda só o monitor
  ativo: sem B e sem fire retém; com B observa até600 e join até655, sem
  renovar carimbo. Só após fired/join positivo permite uma segunda coleta
  dos mesmos records. Sem limpar paralelamente à emergência ou criar outro CID.
- Close/parada/evidência falha não implica liberar; errors sticky permanecem
  no histórico. Coleta física positiva pode permitir restauração segura e
  término NOT_PASSED; não converte um monitor disparado em passe.
- Antes da entrada em A, UNTOUCHED_PRE_A só com tasks/threads coletados e
  nenhum comando. Depois disso, estado inicial desconhecido não vira OFF.
- Driver próprio mantém o mesmo loop/Host se houver recurso pendente. Não
  usa asyncio.run operacional, não reinicia B depois de interrupção. Setup
  inválido recolhe coroutine/tasks ainda não executados e fecha loop vazio;
  setup não comprovado fica HELD, sem declarar liberação. Persistência final
  precisa terminar antes de release; falha regrava HELD/NOT_PASSED.

## Gates anteriores à revisão de código

-54testes próprios:54passed/33,94s, zero falhas/skips/deselected.
- Ruff src/tests e helper E9/F63/F7/F82 limpos; format336conformes; mypy
  strict334arquivos alvos3.11/3.14 limpos. Runtime sóWindows3.11.3.
- Fluxo completo usa Host/journal/replay reais com CLI, owners e monitores
  simulados. Prova ordem dos23casos/12checkpoints, não shell/EOF/exit42 real.
- Cobertos fire em A, falhas de B/start/send/drain/parser, coleta/retry e
  records iguais, retenção sem fire, join/owner/restore/persistência incertos,
  erro resolvido ainda histórico, namespaces HostFault próprios/estrangeiros,
  transitive/stdfile pins, captured copy do monitor, root reparse, canonicalidade/
  reuso do estado, invocation durável, admissão tardia, driver/interrupção e
  task registrada antes de falha de setup. Todos sem subprocessos de ensaio.
- Três regressões próprias falharam antes de corrigir: metadata de readiness
  escapava crua e observação tardia podia iniciar join além da janela655
  (2failed/38deselected/1,16s); loop vazio incompatível não era fechado antes
  da recusa (1failed/51deselected/0,71s). Agora readiness desconhecido=False,
  janela conferida antes/depois do join e setup recolhido antes da recusa.

Histórico de harness preservado: primeiro pre-A afirmou events vazio, mas
events também contém MONITOR_START/CLOSE fakes. Corrigida só a asserção para
ausência de CLI/commands. Depois, a igualdade do estado comparava arrays JSON
com tuplas de dataclass: passou a comparar bytes canônicos, como o contrato.
Estáticos iniciais apontaram só nomes/imports e retorno Any de stub; corrigidos.

Duas execuções terminaram pelo launcher com exit1 e sem sumário durante a
seleção de retenção; a execução verbose localizou o caso restore e mostrou
HELD depois de percorrer a matriz inteira. O teste dependia de concluir23
casos antes de sua espera de5s. Foi isolado para falhar antes da matriz nesse
teste de restore/persistência; matriz completa continua em teste separado.
Após isolamento, os quatro casos de incerteza passaram sem ampliar5s nem a
guarda independente40s. Não se atribui causa ao SO, Docker ou software do
produto.52pass/35,07s antes dos dois testes novos de setup; cinco focados de
setup/namespaces passaram1,87s, seguidos pelo54/33,94s integral acima.

O Timer40s que termina o processo de teste em caso de travamento é thread
auxiliar real; Proactor do pytest/arquivos temporários também usam o SO.
Nenhum watchdog nativo, shell/clock helper/Docker/PG foi executado. As raízes
de admissão são fixtures no Temp do pytest com HOME substituído, não raiz de
ensaio materializada no Temp operacional. HELD é cancelado só nos fakes para
encerrar o teste; loops operacionais não são desmontados dessa forma.

## Correção da prova terminal após7256

358testes relacionados/93,68s passaram sobre d0cb3838. É medição histórica
anterior ao fix, não a evidência final da fonte nova.58próprios/35,14s sobre
afaffad0, zero falhas/skips/deselected. Ruff/helper, format336 e mypy334 em
alvos3.11/3.14 aprovados; runtime somenteWindows3.11.3.

P2 reproduzido antes do fix:2failed/54deselected/1,54s. Physical_ready falso
depois do restore ou task extra fora de _host_tasks podiam deixar arquivos
VERIFIED/FINISHED quando a regravação HELD também falhava. Agora terminal_ready
exige prova física e ausência de tasks pendentes além da atual, antes de
calcular passed e antes das escritas síncronas. O fato terminal_resources_verified
é exigido por success. Sem positivo, retain precede qualquer gravação terminal;
released também volta a False ao reter ou ao driver entrar no fallback.

Os testes de regressão usam o retain real e falha de persistência posterior,
com monitoramento por callback de timer no mesmo root, sem task supervisora
acidental. Assim só a task estrangeira deliberada existe no caso extra-task.
O conjunto completo ainda prova o caminho positivo dos23casos/journal real.
Não há await entre a prova e as gravações terminais; o produtor é a TCB fixa,
sem alegar atomicidade contra mutação Python arbitrária ou falha de hardware.
O exportador futuro ainda exigirá término externo exit0, não só um arquivo.

P3 de categoria tratado: ReaderError do namespace próprio da entrega também
é reconhecido por classe/enum exatos; enum estrangeiro fica INTERNAL. Os
namespaces compilados internos de emergência/volumes/identidade dos monitores
não retêm cópia extra de raw para rehash: construtor conferiu os bytes, Host
mantém seus capturados e arquivos são relidos; isso não autentica a mutação
de código Python em memória. Limite/folga655 e admissão3s devem entrar no
diagnóstico/aritmética de orçamento antes de proposta, ainda não medidos.

## Fechamento58487

SHA final afaffad00ac2a2e9cd1666bdce5e18e6173240b4719592931b9cbda19c90c657,
24081bytes.58487 aprovou código/fakes isolados, sem P1/P2 de implementação.
Seleção final dos nove arquivos entry/host/delivery/reader/owner/profile/
policy/watch/host-público:362passed/77,86s, zero falhas/skips/deselected.
58próprios/35,14s; Ruff/check/helper, format336 e mypy334 alvos3.11/3.14
limpos. Sem alteração funcional após esses gates.

Nota residual do parecer: um callback externo à TCB, enfileirado na mesma
iteração após finish, ainda poderia criar uma task antes da checagem do
driver. A TCB própria já exige monitores joined/heartbeats terminados e não
agenda esse callback; não se reivindica garantia contra injeção de código no
interpretador. Retain conserva melhor esforço de regravação e o exportador
futuro exige término exit0. Risco registrado sob delegação vigente, sem
inventar aprovação individual do usuário nem declarar release/produção.

Bytes compilados dos watchdogs permanecem TCB; janela655 e admissão3s devem
ser medidas/orçadas antes de proposta.7256 e seu finding não são apagados.
Nenhuma revisão ativa, quota/job novo, efeito nativo ou segundo escritor.

## Limites que continuam abertos

Não há exportador/preparador/estado/proposta/comando
de rodada nova. P2 orçamento ainda exige diagnóstico público revisado somente
leitura de pinsFalse/True/transitivo-final, estimativa por23casos/margem e
conta de cleanup/restore incluindo hashes (seconds de CLI os excluem).
B300/owner12/shell8/watch600 não foram ampliados. Excesso consome tentativa
NOT_PASSED, sem retry/reinterpretação; caminho HELD não promete teto do SO.

Produto/dependências/pacotes/UI não mudaram: não repetir suíte PG/browser/
pacotes para alegar prova dessa entrada. Gateway indisponível; B1fimafim/
B2/D090gate2/C1/SQL/produção abertos. Nenhuma nova conexão a banco existente,
secret, seed privado, serviço, quota/job ou segundo escritor.
