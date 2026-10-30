# Sonda pública PG16 — rodada única e recursos restaurados

2026-10-30 sob delegação, sem initdb/servidor/consulta/conexão de banco,
seed ou credencial. Esta é prova de ferramentas/perfil/stdlib e lifecycle
no PG16 público; não é integração do Gateway com SQL nem release.

## Cadeia e execução

Preparador02d1/desenho aceitos55166; exportador95f09bbb aceito94684; entrada
a6089275 e host7275 já aceitos. Código publicado emf40d4a6;378 testes com
fakes/52,39s e estáticos326 limpos antes de efeitos. Script603/13969 recusado
em6483 foi preservado e nunca invocado. Scriptv2/9700bytes/37de40fe aceito1553,
com34pins e root/state frescos conferidos no instante da invocação.

Task `81e727564dff42578c0aa93a9a470d72`, raiz Temp
`maskgw-pg16-public-20261030-c3a916a7a7ff43f89608c6e8a1d26428`.
Materialize único: só attempt.json1935bytes, SHA721f642f idêntico à proposta,
argv igual. Intenção antes da chamada, invocação única na sessão9384.
Console terminou **FINISHED / PG16_PUBLIC_VERIFIED**, **exit0**. Nenhuma
repetição, mudança de teto, relaxamento de parser ou outra CLI concorrente.
Fontes/estado/script/raiz consumidos agora congelados; não editar/reexecutar.

## Fatos do resumo público validado

- Imagem `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`
  readmitida. PG16.15 nas quatro ferramentas; nenhum label OCI na imagem.
- Container público Alpine **3.24.1**, BusyBox **1.37.0**, UID/GID **70/70**.
  sh/base64/sha256sum/dd/wc/timeout/stat/busybox/postgres/initdb/pg_ctl/psql
  presentes; versões/tmpfs e owner/mode conferidos. initdb e postgres foram
  usados apenas com --version, sem cluster ou servidor.
- 12 checkpoints, replay positivo, boot igual, A→B **119515ms**. Head
  `a52316058610658930dd1db598431f2a48fc5f27f3d012fe813f3bfca4df98ed`.
- 34 comandos do ledger, todos exit0. Três own-inspects, todos os grupos aceitos.
  Último State: Runningfalse/Pid0/OOMKilledfalse/Deadfalse/ExitCode0. É o
  inspect do cleanup após quiesce, conforme semântica documentada do resumo.
- CID próprio `fc03f752712c2376171c55f417f108099d44d17873c32765fc08da9d7fead1b6`
  removido, ausência posterior e inventário CID restaurado. Owner **CLOSED**,
  faultnull, NOT_SENT, releasedtrue. Não houve pipe de input nem entrega de seed.
- Volumes: **17 inicialmente e17 ao final**, conjuntos/digests coerentes,
  RESTORED; uma decisão e três registros finais. Nomes globais/preexistentes
  ficaram somente no Temp. Nenhum volume de outro projeto removido.
- Watchdog: joinedtrue/firedfalse/heldfalse. Desktop iniciou Off e voltou a
  OFF_CONFIRMED. Observação independente posterior de Get-Process confirmou
  Off em **2026-10-30T14:32:51.4904199Z**. Essa observação tem essa hora; não é
  vigilância contínua nem medição do instante exato da parada.
- Sem diagnósticos de falha. Nenhum worker/SQL/ingresso do Gateway foi usado.

## Evidência publicada, nenhum bruto copiado

Exportador95f09bbb invocado **uma vez**, depois do exit real e da coleta,
reported_exit0.50 fontes/77312bytes ficaram retidas; published_source_count0.
Somente summary.json e transport.json derivados em
`docs/poc/evidence/pg16-public-run-20261030-81e727564dff/`:

- summary SHA-256:
  `f78c564757410f2da4568386ba84b6f67e6a4d3b48d33bc904ee3106b1848ef6`.
- transport SHA-256:
  `e3594e236063e58bb1fa7db23cb0d7f3e22979767dc1653c63ca37cfe57ca25e`.

Proposta/rejeição/prova de materialização/console/observação externa e recibo
estão em pg16-public-prep-20261030. O console contém só eventos públicos de
fase/count/resultado; não é cópia do raw de container. Raw e baseline completa
continuam no Temp, fora do Git. Hashes de metadado são coerência, não sigilo
de nomes previsíveis nem autenticação criptográfica do produtor.

source_unchanged do manifesto refere-se à rechecagem antes da escrita do
destino. Os dados publicados vêm do snapshot imutável validado. Não promete
que terceiros nunca escrevam depois. Nenhuma fonte foi modificada após o uso.

## Limites e próximo gate

Perfil público PG16 e fechamento de recursos passaram nesta rodada. Não
certifica Oracle/RHEL kernel, SELinux, orçamento físico total, C1, B1 fim a
fim, B2 ou D090gate2. O aplicativo Oracle9.8 candidato não mudou e permanece
sem serviço operacional. SQL PGWire continua recusada e Gateway indisponível.
Próximo: desenho do leitor shell/fixture PG privada, usando estes fatos, com
revisão antes de novos efeitos. Sem job/quota/segundo escritor. Claude2 aceitou
os fatos em2026-10-30T14:41:43.508Z, sessão51ea0d85, com duas notas menores
abaixo. O aceite não é permissão ou alegação de produção.

## Revisão factual aceita e lacunas preservadas

O revisor confrontou proposta/materialização/console, resumo, transporte e
esta validação. Aceitou os fatos como insumo para o próximo desenho, sem
fechar B1/B2/D090/C1. Com tmpfs no caminho declarado VOLUME, não houve volume
anônimo: zero Mounts de volume e inventários iguais. A decisão WITH_V não
teve volume novo para remover. A presença das ferramentas BusyBox não prova
a semântica dos flags; o leitor exato precisa de medição própria.

1. O start --attach do owner é lançado diretamente, fora dos34 comandos do
   ledger do host. O resumo atual não publica returncode/stdout_bytes do
   owner. O parser recalcula o relatório com código fixo0, enquanto o
   sucesso também é corroborado pelo ExitCode0 do inspect. No próximo
   desenho, publicar os dois campos já existentes no cases.json local e
   validar o código real. Não confundir34 comandos do ledger com todas
   as criações de processos/CLIs.
2. post_execution_state vem do inspect-cleanup, após quiesce. O escopo já
   estava descrito; próximo resumo deve publicar também esse rótulo.

Nenhum exporter, resumo, fonte ou bruto consumido foi reescrito para
eliminar retroativamente essas lacunas. Nenhum efeito nativo adicional.
