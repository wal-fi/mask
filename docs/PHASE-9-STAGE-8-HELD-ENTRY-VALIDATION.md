# HELD integração I — tap e entrypoint, somente fakes

**2026-10-22 — incremento I revisado sem bloqueador, somente fakes.**
Escolha sob delegação vigente, não aval individual fictício. Nenhuma carga
nova, CLI Docker, factory Linux, SQL, worker ou fechamento B-1/B-2/D-090.
Núcleo E, dez helpers anteriores e artefatos medidos preservados byte a byte.

## I1 encontrado antes do código, corrigido no desenho

Primeiro desenho propunha E no PID1 e13 fontes no mount. Claude2 somente
leitura51ea0d85 bloqueou: E carrega host/preparador que importa packaging,
ausente sob -I -B -S no container. Não se tentou executar essa proposta.
HELD-INTEGRATION-DESIGN foi refeito antes do código: captura/transporte no
container, validação/replay por E no host. Sem instalar dependência, remover
-S, alterar sys.path do pai ou inventário/origens do membro para obter fit.

Proposta atual tem14 fontes no bundle futuro:8 no mount RO do probe (6
antigas+tap+wrapper) e6 hosts/código de validação fora do mount. II não está
implementado neste registro; não se construiu preparação/Observer real.
Dependências/custos novos ainda não foram medidos no container.

## Código entregue

-docs/poc/loaded_memory_tap.py: só stdlib, core/supervisor injetados. Tap
 limitado a2 candidatas HELD<=1024, decoder congelado, delegação explícita e
 pid dinâmico. Erro do read delegado mantém tipo/identidade/categoria; erro
 próprio marca broken terminal e fault fixo. Não cria classificador novo.
-Captura chama supervise/bounded_report congelados e emite transporte
 loaded-as128-held-transport-v1 com original exato, held candidatas e
 tap_broken. Não publica validated=true/outcome positivo; host deve salvar
 raw e validar por E. Broken mantém original negativo para diagnóstico,
 mas não permite admissão futura. Cap64KiB inclui escaping; erro/cap usa
 fallback exato inconclusivo, sem truncar ou emitir saída ilimitada.
-docs/poc/linux_held_probe.py: import só define stdlib/constantes/funções.
 Guard Linux/isolated/no_site/-B/UID65534/PID1 antes de loader. Parser
 congelado depois do load, antes da factory. Wrapper não tem --member;
 filho permanece linux_loaded_probe.py --member, sem novo módulo nele.
-Prazo20s começa antes de load/parts, relógio real inválido/regredido/atrasado
 impede factory. Factory/cleanup/write_report2s são anteriores, sem novo
 owner ou renovação da medição. Exit64 guard/argv,70 falha externa,
 0 apenas emissão, nunca aprovação semântica. Não roda E/replay no PID1.
-Loader lê<=65537, recusa>65536/SHA errado e executa somente o buffer
 verificado via compile/ModuleType, com __file__ correto. Sem segundo open
 do código depois do hash, sys.path/PYTHONPATH ou alteração de globais antigos.
 Mudança no tap/supervisor exige novo hash no wrapper e nova revisão.

## Testes e gates antes da revisão

Primeiro teste falhou na coleta porque tap ainda não existia; não é bug
antigo. Primeiro código:34 passaram, expansão46 passou. Sem erro funcional
medido nessa rodada; import/split/argumento ocioso apontados pelo Ruff foram
ajustados, sem novas exceções/configuração. Fixture nova EntryIO declara
atributos simulados de OS/writer, sem alterar RecordingIO anterior.

Fakes de OS/clock/factory/writer e IO do supervisor congelado. Três casos
completos de captura produziram transporte validável por E no host, mantendo
bytes/candidatas. Guard/argv/load/parts/factory/capture/writer, atraso e clocks
inválidos, erro delegado, broken/terceira candidata, cap/escaping, output
inválido/fallback, PID dinâmico, paridade de linhas com E.Tap testados.

Teste de dependência: AST de imports diretos só stdlib; loader/parts executados
com import hook recusando packaging/E/hosts. Carregaram apenas os cinco helpers
antigos, sem factory. **Não** é prova de execução Linux sob -S nem medição de
custo/pico. Teste de troca de arquivo durante compile confirmou buffer original
executado, não nova leitura do arquivo. Somente arquivos pequenos do pytest.

Windows3.11.3, .venv existente:

-46 novos passed em0,58s;
-849 relacionados passed em6,05s (803 anteriores+46), seleção completa
 linux_as/linux_imports/loaded_memory, -o addopts=, sem skips/xfail/deselect;
-Ruff src/tests e E/F/I/B/UP dos2 PoCs limpos;
-format259 arquivos conformes;
-mypy strict3.11 e3.14 em257 sources limpos;3.14 só análise estática.

Hashes provisórios para revisão:

-tap:aae25eb187ccd483847b725049e8932df469a5d1b9722dad786cb328436f504d;
-wrapper:3ec0b4fd4c0b061687e388ca735ee4061492a051d0fb68ba55f169720e2e56b4;
-teste:432141380018591c2059ffc1a5897c7621b1964efea698f51b3890ba07909649.

Sem suíte PG16/frontend/pacotes repetida: src/produto/dependência/recurso não
mudou, docs fora do pacote. Não atribuir a este lote gates medidos antes.
Próximo gate: revisão de código I; depois delta de desenho/revisão II e seus
fakes; III exige procedimento e comando exato próprios antes de carga.
Todos os limites de memória total/pai/nativo/concorrência continuam abertos.
Sem outra conta/escritor, tarefa nova, instalação, commit/push ou deploy.

## Revisão de código e notas obrigatórias para II

Claude2 somente leitura51ea0d85 aceitou I isolado sem bloqueador. Conferiu
I1 resolvido, imports stdlib/injeção, buffer verificado sem re-open, guard/
deadline antes de factory, ownership único/erro delegado, transporte limitado
e significado estrito de exit0. Não executou testes nem mediu Linux.
Os46/849 e hashes acima são do resultado aceito; depois só documentos mudaram.

II deve conferir todos os hashes/cópias no /probe antes de cada create: loader
do wrapper só pina tap/S; load_parts congelado não pina sozinho seus cinco
arquivos. Deve salvar raw antes do parser, validar schema fechado e tratar
tap_broken/fallback sempre como inconclusivo, sem próximo create.
Embedding/escaping pode estourar64KiB mesmo se original couber: nesse caso
transporte é fallback e original pode não chegar ao host. Não há margem de
tamanho garantida universal; parar sem truncar/elevar cap/repetir.

II precisa revisão própria do desenho/código, III do procedimento/comando
antes da rodada. O aceite I não libera nenhum deles nem o produto.
