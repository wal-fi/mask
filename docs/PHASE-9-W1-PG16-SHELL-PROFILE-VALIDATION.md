# Perfil público do leitor PG16 — contrato testado com inspect sintético

2026-10-30 sob delegação. Novo pg16_shell_profile.py, somente definição de
perfil/builder/validador e fakes. Nenhum DockerCLI, raiz, start/attach, shell,
cluster, SQL, seed, worker ou alteração da imagem candidata Oracle.

## Desenho e implementação

Claude2/review98150 aceitou o desenho antes do código, com quatro precisões
incorporadas: manifesto próprio do reader, prefixo distinto, Attach* somente
observações fechadas e inserção fixa de-i com medição Windows recalculada.

Captura base fe2 e owner d671 por hash; compartilha Image/admit_image do base
e Case/reader/channel do owner. Intent congelado captura Cmd/wrapperSHA,
coreSHA separado para READY, nome por task/case e três labels próprios.
blueprint/create_args concordam para23casos. Somente o builder comum _create
é reutilizado; predicados completos de validação são explícitos. Nenhum
inspect transformado para esconder stdintrue ou Cmd diferente.

Manifesto novo867617ca inclui entrada/imagem/tmpfs/stdin/identidade do perfil
e as três fontes de owner/reader/core. Nome maskgw-ol9-pg16-reader- é distinto
da sonda. Sem relaxar RO/networknone/UID70/caps0/NNP/limites/ulimits/volume/
porta/Env/labels. OpenStdintrue/StdinOncetrue/Ttyfalse são precondições, ainda
não medidas para esse wrapper PG. AttachStdin/Stdout/Stderr retornam bool ou
null desconhecido, sem influência na aceitação.

## Regressão própria vermelha primeiro

Dois Mounts sintéticos usavam Destination lista ou dict. Antes do fix, o
teste de categoria fechada recebeu TypeError:2failed/3passed/50deselected,
0,47s. Acrescentada exigência de Destination ser str antes do lookup de
tmpfs. Nenhuma fonte base consumida mudou. Depois55passed/1,44s; rodada após
formatação55passed/1,48s. Não atribuir essa medição a execução Docker real.

## Gates medidos antes da revisão de código

- 55 testes próprios: tipos/capturas/imutabilidade,23casos,Cmd/labels/source,
  argv fechado/tamanho, stdin/TTY/Attach*, campos de segurança, OCI herdado,
  identidade alheia, perfil recusado mantendo posse e Mounts malformados.
- Maior createprocess entre23casos:4747caracteres, margem21253 para26000.
  Inclui CLI/contexto/argv completo com quoting Windows, não só script.
- Fonte8415bytes SHA-256:
  8906e846a792d7aa01bc53da000e35815ba20a9ffee4a7fb8705b19b1b630912.
- Manifesto SHA-256:
  867617ca88da9436b4645b1cacb11951b6a58737d9e60dc6a16a21ff088f730b.
- Ruff dos testes e E9/F63/F7/F82 do helper limpos; formatação somente nos
  dois novos arquivos.

## Gates relacionados concluídos

- Seleção perfil público anterior/reader/owner/perfil novo:
  **205 passed em3,76s**, nenhuma falha, skip ou deselect. Não inclui a
  unidade nativa histórica de PipeHandle; somente esses quatro arquivos.
- Ruff src/tests: limpo; format src/tests+helper novo:330 arquivos conformes.
- Mypy strict src/tests:329 arquivos limpos, alvos3.11 e3.14. Runtime apenas
  Windows3.11.3; não inferir execução Linux ou3.14.
- A primeira tentativa de iniciar a revisão de código não foi executada:
  o aprovador automático atingiu seu limite de uso. Não foi limite medido
  do Claude2 nem decisão de que a ação fosse insegura. Após retomada e novos
  gates locais, a mesma revisão somente leitura foi iniciada na sessão28829.
  Nenhuma conta/técnica alternativa ou segundo escritor utilizado.

Claude2/sessão51ea0d85/review28829 aceitou o código isolado, sem bloqueador.
O bloqueio do aprovador foi transitório e a revisão concluiu normalmente;
não houve limite do Claude2 medido nem job de retomada criado. Sem atestação
de perfil/Attach* real, sem
prova de fluxo CLI/EOF/exit42 ou leitor shell executado. Perfil não concede
create/start/cleanup; host futuro deve verificar CID e perfil antes de input.
Entrega dos negativos, watchdog/cleanup/host/entry/exporter/proposta e rodada
continuam posteriores. Gateway indisponível; gates de produção abertos.
