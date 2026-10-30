# Diagnóstico público de admissão — depois da T4 reprovada

Proposta sob delegação,2026-10-28; **sem implementação ou efeitos novos**.
Baseline reprovada0566dd40 e restauração aceitas. Não reexecutar/editar fontes
consumidas88e2/835c/c789 nem raiz86e5417c. Não é repetição da matriz T4:
escopo novo somente create/inspect de dois perfis, sem start/attach/seed.

## Objetivo, limites e insumos

Identificar todas as divergências entre perfil proposto e o que o Docker
retorna para normalUID10001 e retainUID70, ambos criados mas nunca iniciados.
Usar imagem621 exata e create_args/Intent e3cf congelados, task/root novos,
rede none/rootRO/capsNone/pids8/mem128 e nenhum mount/porta/privateinput.
Dois CIDs sequenciais: criar, observar, limpar/liberar, só depois o segundo.
Não relaxar aceitação de transporte para fazer o diagnóstico terminar.

O cliente medido foi29.7.2/a7dcaa6. A [fonte oficial dessa versão](https://raw.githubusercontent.com/docker/cli/v29.7.2/cli/command/container/opts.go)
liga interactive a AttachStdin e OpenStdin+AttachStdin a StdinOnce=true.
Isso é hipótese de divergência, **não campo medido do CID nem causa provada**.
Não alterar o valor esperado até observar. Labels imagem4/CID3 medidos no
baseline anterior continuam preservados, sem supor causa no Desktop.

## Código novo específico, reuso auditável

Novo `docs/poc/w1_bootstrap_admission_run.py`, variante explícita do entrypoint
835c congelado, sem alterar o original. Copiar sua estrutura de admissão,
posse, ciclo/journal, join/retention, restauração, driver; teste AST permite
somente alterações fechadas: kind/root específicos de admission, Host do
diagnóstico, condição/contador/outcome de **captura diagnóstica**, sem parecer
T4 completa. Não criar backend/DSL/argv arbitrários nem usar transformações
dinâmicas da AST em produção. Binding88e2 é carregado por hash, só definições.

Classe de diagnóstico herda Host88e2. Overrides declarados antes do código:
__init__ (estado/contadores privados), inspect_own (captura+avaliação),
perform_b (somente dois creates sequenciais) e _case (sempre recusa, para
eliminar caminho herdado de attach). Sem ManagedBootstrap/owner/seed; teste
sentinela recusa qualquer tentativa de construir transporte. run_own,
check_attestation/watchdog antigos já recusam e continuam os mesmos objetos.
create_own herdado mantém intenção xb/snapshot/registro antes do efeito.

Diferença deliberada: **somente neste diagnóstico**, inspect_own retorna
info de posse comprovada mesmo que o perfil não seja aceito; registra
divergências, não declara aceitação. O perform_b não chama _case nem usa esse
info para start. Malformação, erro CLI, posse ausente ou falha de captura
abortam; não retornar info não identificado. Nenhum consumidor operacional
recebe essa exceção de contrato. Conclusão diagnóstica não libera T4/canal.

## Captura antes de validar

Logo depois de inspect exit0, gravar stdout exato limitado2MiB em xb único,
**antes** de json.loads/identity/validate_container. Um contador de inspeções
evita sobrescrita, com label/role e hash/tamanho públicos em manifesto. A
posse e o perfil serão avaliados depois de salvar. Cleanup também preserva
suas observações quando passar por esse override. Para coleta inicial que
usa cli direto no Host88, o raw do primeiro inspect é o mesmo já capturado
na admissão; não alegar que uma observação posterior foi persistida se não foi.

Justificativa de sigilo para esta captura restrita: nenhum segredo é entrada
deste experimento; Cmd/labels são públicos fixos do canário, imagem/config
exatos e Env conhecidos. Antes de A, confirmar config Docker pinada sem
proxies (leitura atual tem keys auths/credsStore/currentContext/features/plugins,
sem proxies; valores não exibidos). Não passar auth/envfile/mount/seed. Não
reutilizar logger raw em PG/produção ou container com input privado futuro.
Se precondição pública falhar, abortar antes de create, sem capturar privado.

## Diffs e categorias fechados

Núcleo puro novo recebe o inspect público e a intenção capturada, avalia
**cada predicado** de validate_container separadamente, sem parar no primeiro:
Config Labels/User/WorkingDir/Env/Tty/OpenStdin/StdinOnce/Volumes/ExposedPorts/
Healthcheck, perfil HostConfig, ulimits/isolamento e itens de superfície.
Registrar campo, expectativa e observado em schema fechado; valores de
presença usam booleano quando o contrato só exige vazio. Campos extras não
viram categoria/texto livre. Também observar AttachStdin/AttachStdout/
AttachStderr e State.Running/Pid (esses dois obrigatoriamente false/0).

Rodar depois o validador e3cf inalterado para obter categoria do grupo,
whitelist explícita de RuntimeError.args[0] exato: CONFIG/PROFILE/ISOLATION/
SURFACE/OWNERSHIP/CID_CHANGED/INSPECT_SHAPE e SOURCE/PIN conhecidos conforme
o código. Qualquer outro texto vira INTERNAL, sem mensagem/cadeia. Não
devolver str(error) genérico nem perder categoria fechada em FAILED.
Diff por campo mais resultado do validador ficam juntos; não alegar que
um diff isolado explica toda a falha se há outros. Perfil aceito só quando
todos os predicados e o validador original concordarem.

## Sucesso, posse e prazos

Resultado novo `ORACLE9_ADMISSION_CAPTURED` só exige duas capturas/diffs
completas, inspeções Statecreated/Pid0, journal íntegro, recursos removidos,
inventário vazio, thread joined, Desktop/inputs restaurados, sem disparo ou
falha operacional. **Não exige perfil aprovado**: é medição, não liberação.
Não usar t4_verified ou números de sete casos para indicar sucesso.

Preservar gate A→noveOBSERVE→READY→B/journal, o mesmo boot e limites. Até dois
casos de create5+inspect3+captura/avaliação3+cleanup22+margem3=36s cada;
matriz80s/pendência28/restore93/join50 =251<600 pós-B, sem novos tetos maiores.
Nenhum owner/spawn/CLI de attach; erro de create desconhecido fica HELD,
nenhuma inferência por ausência transitória. Cleanup por posse/subconjunto e
comando capturado, rm semforce, nova ausência; sem prune/force/retry de create.
Watchdog existente recebe snapshots de CID, sem PID de attach; registra CLI
desconhecido sem adivinhar, pode remover CID próprio, não emite release.
No diagnóstico não existe CLI de attach a recolher, então a ausência de PID
desse tipo não é uma pendência; os subprocessos CLI públicos continuam sob
o executor aceito e exitNone mantém HELD. Não alterar watchdog consumido.

## Gates

Fakes do núcleo com cada campo falhando, múltiplas divergências, categorias
privadas sanitizadas, raw salvo antes de falha/malformação, colisão xb sem
overwrite, posse estranha sem mutação, create incerto, shape inválido, State
running, dois perfis, fluxo inteiro/replay/restauração e sentinela zeroattach.
AST/reuso por identidade e caps verificados, Ruff/format/mypy. Revisão de
código depois desses testes; então raiz/estado/comando próprios antes de
execução única. Rodada reprovada original permanece intacta. Nenhum PG,
seed/SQL/produção, ajuste de perfil ou nova T4 completa neste diagnóstico.

## S1 e precisões da revisão, antes do código

Desenho aceito de forma estreita; S1 é obrigatório. Captura raw em xb fica
**somente na raiz Temp local**, antes de parse/validação. Exportação para
checkout/evidência é outra operação, após conferência pura fechada: Env exato,
nenhuma chave proxy/auth em Config/HostConfig (case-insensitive, recursivo)
e labels só os próprios esperados e eventual apresentação v2 já conhecida.
Se recusar, bruto não sai de Temp; relatório público contém só hash/tamanho,
nomes fechados de campos divergentes e categorias. Testes incluem proxy
fictício negado e Env exato permitido. Não publicar valores de Env/texto livre
nos diffs, mesmo com perfil divergente; só igualdade/nome fechado do campo.

Whitelist de categorias será comparada em teste ao AST dos need com literais
nas fontes e3cf/88e2; fora do conjunto, INTERNAL. Gravação herdada de
inspect-before continua segunda cópia dos mesmos bytes, testada. State vivo
aborta, _collect por cli direto continua observação não capturada, e isso
consta no resultado. Admission e T4 recusam kind/root uma da outra.
Critério novo exige duas capturas/diffs completos e Statecreated/Pid0,
além dos gates de posse/journal/restauração; profile_accepted só por perfil,
com todos os predicados e o validador concordando, nunca uma liberação global.

O comentário corporativo do parecer não é tratado como uma instrução do
usuário ou política comprovada neste repositório. Nenhuma credencial real
foi observada, não há incidente declarado nem autorização de comunicação
externa inferida. Aplicar somente o controle técnico de sigilo acima.

## Precisões de integração antes do código operacional

São **cinco** overrides da classe, acrescentando pins aos quatro declarados:
o novo núcleo puro e o próprio entrypoint precisam de captura/hashes em
memória sempre, e leitura dos arquivos vivos fora de cleanup. Sem esse
override, os pins herdados só conhecem as cinco fontes T4 e host88, não o
comparador/guarda novo. Estado fechado ganha diagnostic_pins com somente
esse núcleo; cleanup usa sua captura admitida, não arquivo mutável. Confirmar
config Docker sem proxies em pins normais, com valores jamais registrados.

A variante é arquivo novo baseado no entry835c congelado; diffs AST devem
permitir só import/constantes/captura do núcleo, DiagnosticHost, kind/root
distintos, pin adicional fechado e condição/counter/outcome de diagnóstico.
prepare chama DiagnosticHost explicitamente, sem rebind oculto em namespaces
ou transformação AST em runtime. Os demais passos/handlers/driver continuam
textualmente iguais salvo preservação das categorias pelo núcleo capturado.

Exportador futuro aplica a guarda a **cada cópia** de raw, incluindo o
inspect-before herdado e qualquer inspeção de cleanup arquivada; nenhum
alias escapa pelo nome. Manifesto de captura registra fase, nome, hash/
tamanho e permissão, sem valores privados. Capturas de cleanup não contam
como uma das duas admissões. Inspect direto inicial do cleanup herdado não
é arquivado e não deve ser alegado como capturado. Nenhum transporte contendo
raw será preparado sem esse gate e sua revisão/testes próprios.
