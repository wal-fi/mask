# W1 — coordenador revisado, somente fakes/arquivos públicos

2026-10-27, sob delegação. Após aceite dos contratos R1–R5 e das precisões
do desenho, implementado `docs/poc/oracle9_w1_run_v2.py`. Nenhuma execução
de main, nova amostra Windows/CIM, Desktop, DockerCLI ou instalação neste lote.
Baseline: tentativa1 abortada e recuperação c1351f16 aceita, DesktopOff.

## Escopo fechado

Novo módulo15757bytes/SHA
a46227c96194c3171c4fdd17aa311ec636daddb4494fd3d47ccb87f94c541fef.
Usa4bc0b083 como biblioteca hashada; não chama main antigo. Exatamente cinco
métodos sobrepostos:save/cli/inspect_own/watchdog/pins. Todos os outros têm
identidade de função com a biblioteca, inclusive start_cycle/checkpoint/
perform_b/cleanup_owned/restore_desktop/create_own. Watchdog copiado difere
por AST normalizada somente no bloco que chama a posse comum.

- Posse:name/CID conhecido/image/3labels próprios como subconjunto e argv/
  entrypoint da intenção exatos. Não exige perfil de aceitação para limpar.
  Cada inspect normal exige também perfil original completo+3labels exatos;
  vale nos CIDs install e probe e em cada ponto antes/depois de efeitos.
- Watchdog usa a mesma posse, tolera label extra e bloqueia comando alheio;
  restante do método tem equivalência AST com4bc.
- cli só altera commit-own de forma exata: acrescenta --change LABEL com
  valor v2 da base validada. Lista final gravada. Demais chamadas idênticas.
  Config/camadas/4labels da imagem nova continuam com validação original.
- program_sha256 fica4bc permanentemente; entry_sha256 separado é conferido
  em cada efeito. Teste observa as duas conferências sem troca temporária.
- save cria12 registros xb encadeados (START/9OBSERVE/READY/B), sample completo
  e encode literal, SHA anterior. Regras fechadas de transição e replay puro
  exigem ACCEPT+encode idêntico. FAILED/ABORTED não entram como aceitos,
  encode repetido pós-B não duplica. Recusa ganha arquivo xb separado.
  Main novo valida os12 arquivos do disco **antes** de perform_b/create;
  corrupção no disco ou colisão de arquivo impede o corpo. Nada é reparado
  ou sobrescrito silenciosamente. Replay é lógico, não atestação externa.

## Gates medidos

31 testes novos, na seleção relacionada de12arquivos:
**384 aprovados,1 skip de symlink preexistente,45,63s**. Windows3.11.3,
somente fakes/arquivos públicos/threads watchdog sem efeito real.

Os testes reutilizam as fixtures congeladas do4bc e um adapter fake que
representa o fato observado dos3labels. Não reescrevem os testes anteriores.
Cobrem extra label e limite incorreto nos dois CIDs, aceitação recusando em
todos os inspects normais, cleanup por posse, create ambíguo, identidade
alheia preservada, watchdog com label extra/comando alheio, argv de commit,
herança/AST e journal adulterado/cadeia/ação/sample/estado/índice/colisão.

Ruff check src/tests e mypy strict3.11/3.14:299 arquivos limpos. Format
src/tests+helper novo:300 conformes. Helper:lint E9/F63/F7/F82 limpo, sem
alegação de tipagem estrita do script. Ajustes iniciais foram diagnósticos
de import/fixtures e anotação da função normalize nos testes; sem falha
funcional nova nos31 casos. Teste
cdaf21f161ff98201b93fc359ba348b744892aeef33e1fc2e25f67d437c1250e.

Fonte4bc0b083, restore9d4fa8b9, builder7540b7bf, payload566c46a8 e contexto
d4d4b29b permanecem preservados. Código segue para revisão somente leitura;
estado/comando de nova raiz ainda não foram preparados ou invocados.
Sem commit/push/job ou segundo escritor. B-1/B-2/D-090/C1/SQL/produção abertos.

## Código aceito, delta de vínculo e estado/comando novos

Claude2 aceitoua46227c9 como código sem bloqueador. Recomendações incorporadas:
replay do disco precisa ter encode idêntico ao host.cycle e head idêntico ao
SHA do último registro em memória. Dois testes de divergência exigem
JOURNAL_BINDING; mutações existentes agora exigem suas categorias exatas.
Rodada focada final33/33,12,19s; Ruff e mypy nos alvos dos testes limpos.
Fonte final16053bytes/SHA
b59388f52a38319c19c2c60b25100347d319a59c2778395cc68bea64d2bc0c37;
teste25202cb9. Nenhuma fonte histórica mudou.

Risco residual aceito para ler a próxima evidência: os labels do CID probe
ainda não foram observados. Se ele herdar um extra, aceitação recusa antes
de start, posse limpa e rollback remove tag própria. Não presumir sucesso
ou causa para eventual diferença de comportamento do Docker.

Root v2 independente preparado, ainda não invocado:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-w1-run-v2-20261027-9eb3e1f3c8d144bba31f0b4240ed4d23`.
Taskb03f575e731b4611928433cabafa7197; somente attempt.json FRESH/invokedfalse,
SHA a19394f906ec2645e49443f3f40beed92d48461dd52ff74a081eb8f69443a968.
program_sha256=4bc0b083 permanente e entry_sha256=b59388f5, seis bibliotecas
e cinco pins externos admitidos, contexto/fontes atuais relidos offline.
Medidas:24016install/23985probe, margens1984/2015. Preparação8fb8b28f.

Comando9c6b4996 no artefato oracle9-w1-v2-run-command-20261027.ps1 confere
Pythonbfff5171, fonte histórica4bc, entrada nova b593, attemptSHA e root fresco.
Exige DesktopOff antes de uma invocação -I-B e propaga exit. ParserPS5.1:
0erros; processos Docker no preparo:0. Não ancorar clock na preparação.
Delta/vínculo/estado/comando seguem para revisão antes de A; main v2 nunca
foi executado. Tentativa1 e recuperação consumidas, sem repetição.
