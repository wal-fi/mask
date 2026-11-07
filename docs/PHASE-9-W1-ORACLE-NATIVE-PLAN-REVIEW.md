# W1 Oracle nativo — revisão do plano, 2026-11-06

Decisões sob a delegação vigente, sem atribuir aprovação individual ao
usuário. Claude2 escreveu somente o plano, na sessão51ea0d85, modelo
claude-opus-5-5, esforço medium. O assistente principal reviu as versões,
fontes pertinentes e as verificações descritas abaixo.

## Parecer e escopo

A v4 de W1-ORACLE-NATIVE-PLAN, SHA-256
5db1c1f4b4693cf0794cb8b3882a26f61f6f90dda8a741f17051a96d628c975d,
é aceita como direção prospectiva **somente para o primeiro incremento de
testes puros**, com as precisões deste registro. Não autoriza invocar Docker,
PostgreSQL, consultas, controle nativo ou deployment. T5 e os demais gates
BLOCK_NATIVE continuam obrigatórios antes da execução correspondente.

O próximo arquivo é `tests/test_oracle9_w1_controller.py`, antes de
`deploy/oracle9_w1_controller.py`. O módulo continua ausente durante a
revisão/RED. Somente depois de conferir oráculos e congelar os testes o
Claude2 implementará as definições puras; sem main, spawn ou sockets nesse
primeiro incremento. Não há código desse incremento entregue aqui.

## Caminho crítico e reaproveitamento

O laboratório Windows PG16 shell e a admissão Native3s permanecem abertos;
não são declarados aprovados ou dispensados. O caminho escolhido para W1 é
uma prova própria no destino Oracle Linux9.8 aceito, com PostgreSQL16
descartável próprio, não um novo coordenador genérico com fakes no Windows.

O registro UPDATE-V2-RUN aceita a candidata instalada621cc7f7, wheel6b63f239
e contexto d4d4b29b. A disponibilidade atual não foi inspecionada no Docker.
Root comparou os124 insumos públicos do manifesto com o checkout:123 paths
do pacote e pyproject, todos iguais por tamanho/SHA-256. Isso evita rebuild
ou reinstalação de fontes inalteradas; não substitui readmissão da imagem,
perfil, pacote instalado, kernel e ferramentas na futura rodada.

As propostas iniciais se apoiavam em registros mais antigos e ficaram
preservadas, não aprovadas. Imports Linux e guard já tinham medições reais;
elas não fecharam B1 fim a fim/B2/D-090 nem demonstram consulta pelo worker.

## Captura pública: verificação própria, não API nova

Root leu `_compile` e os helpers de snapshot. O caminho puro usa o loader
público, o mesmo RecordingSecrets, effective_database_settings,
GatewayConfig, build_conninfo e capture_template. Não cria PreparedRuntime
nem chama build_candidate/verify_prepared; não injeta verifier nulo no
controlador nem conecta no pai.

Quatro combinações (política padrão/HMAC, limites padrão/restritivos)
produziram bytes bind idênticos ao controle D111 congelado, com connect e
getaddrinfo reais interceptados como proibidos. O controle de comparação
usa a fixture fake já existente; ela não é o caminho do controlador.
Resultado/script e duas correções do harness estão em
pure-capture-public-composition-review.json. Não são testes de DB ou prova
de geração operacional; eliminam o suposto bloqueio por API ausente.

## Intenção SQL: verificação própria

Root extraiu as19 linhas SQL do plano e passou pelo validate_select padrão:
17 Selects admitidos, DELETE/job14 e pg_read_file/job15 recusados por
QueryRejected. Nenhuma conexão ou consulta foi executada. Isso só prova a
intenção sintática/política: proveniência real, OIDs, categorias QUERY/TYPE/
TIMEOUT e efeitos continuam exigindo o PostgreSQL e a rodada nativa.

## Precisões do primeiro contrato puro

LAB_INIT/LAB_CONTROL são protocolos de laboratório, distintos de MGW2 e
do estado16 antigo. As definições da v4 são mantidas com estes detalhes:

- LAB_INIT.kind é exatamente MASKGW_W1_LAB_INIT_V1; version é int exato1,
  nunca bool. Corpo é JSON ASCII canônico, sort_keys/separadores compactos,
  sem LF adicional; comprimento inclui exatamente esses bytes. Cabeçalho
  >4sI com MGI1, corpo1..65536, sem sobra depois do corpo.
- target é dict de quatro chaves. ip é IPv4 privada canônica; port é int
  exato1..65535; database/username são ASCII com padrão
  `[a-z][a-z0-9_]{0,62}`. A igualdade ao alvo próprio preparado será
  conferida antes de qualquer uso; validação de schema não autoriza conectar.
- Senha48hex e chave HMAC64hex são str exatas em hex minúsculos. A chave é
  texto UTF-8, sem conversão hex. Nenhuma releitura de ambiente.
- raw_canaries é list exata1..16, strings ASCII sem controles1..128. Não
  podem alterar a sintaxe dos SQLs fixos: o gerador deve restringir/escapar
  dados antes da substituição; nunca interpolar texto arbitrário como SQL.
- expected é list exata19, jobs int exatos1..19 na ordem, seis chaves por
  item. kind é RESULT ou ERROR. Os únicos ERRORs são11LIMIT,13QUERY,
  14QUERY,15QUERY,16TIMEOUT,18TYPE. Os demais são RESULT. Resultado tem rows
  int exato0..1000, bytes int exato1..F, sha256 lowerhex64, reason None;
  ERROR tem rows/bytes/sha256 None e o reason exato da tabela.
- Números são int exatos: bool/float/subclasses/coerções recusados. Chaves
  duplicadas, campos extras, faltas, corpo não canônico/NaN e conteúdo
  excedente são recusados em erro fechado, sem conteúdo/causa/contexto.
- DTOs que contêm credenciais, canários, snapshots ou expectativas não
  expõem esses valores em repr/logs. Não prometer zeroização da memória.
- LAB_CONTROL mantém >4sBBHII/MGL1/version1 e50 frames máximos. O seq é por
  frame aceito. Leitor exclusivo, handoff de T4 e avanço só pela principal
  após join; ABORT não reabre estado nem aceita retry/replay.
- SUMMARY anterior a T6 é só resumo de prefixo, nunca PASS global. Resultado
  global exige T6, todos os critérios aplicáveis, inventários e cleanup reais.

## Segurança da futura rodada

O SRF de2bilhões foi removido como finding de desenho; não houve teste
nativo desse risco. O novo SQL tem entradas finitas e continua hipótese
de timeout, nunca resultado medido. PGDATA/tmp/temp_file_limit também são
finitos no desenho; tmpfs cobra memória do cgroup e pode causar OOM.
Nenhum limite será aumentado depois da rodada para transformá-la em verde.
Referências primárias estão no plano; elas não certificam a imagem local.

T5 não é dispensado por compartilhar ramo com idle. O driver direto deverá
reservar/adotar e reter dono/fds antes do spawn. Só saída natural0 comprova
EOF; kill de fallback só comprova limpeza, se efetivamente recolhido. O
desenho detalhado do driver ainda será revisto antes do código desse caso.

A pressão/concorrência/herança cruzada/INIT máximo/cliente lento/gerações
e os demais itens fora da matriz atual continuam no ledger de pendências.
Após a rodada, uma auditoria requisito→evidência precede qualquer fechamento
de etapa. D-119/C1 novo perfil, B2, D-090gate2, ingressos/TLS/IDE/MCP/Admin,
patches/minimalização e produção seguem abertos. Nenhum serviço disponível.

## Sequência e limites preservados

CLI3083/52597/75890 foram somente Read e recuperadas antes da próxima chamada.
CLI25630/57391/2704/75815 escreveram somente o plano, todas terminaram0 e
foram recuperadas. Um Claude2 de cada vez; nenhum job/reset/quota novo.
Root reviu todas as versões ou seus deltas completos, preservando os dados.

Source20, estado16 e a tentativa consumida não foram modificados. Nenhum
banco existente, credencial antiga, container ou configuração do usuário
foi tocado. Os testes1352 do incremento publicado9ba0d2b são históricos
para esta revisão documental; não foram repetidos sem mudança de código.
