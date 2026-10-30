# Watchdog do leitor PG16 — definições e fakes, sem thread real

2026-10-30 sob delegação. Variante explícita nova pg16_shell_watchdog.py;
fonte b868/emergency54cc/volumes6e38 e demais fontes consumidas intactas.
Nenhuma thread, CLI, Docker, nova raiz, seed, servidor, query ou release real.

## Revisão de código e precisão de tipo

Review21812/sessão51ea0d85 aceitou a variante d65a53a4 isolada sem bloqueador,
após121testes relacionados/9,23s e estáticos. Sua nota sobre __eq__ foi
incorporada com regressão antes do fix:1failed/32deselected em0,35s demonstrou
callback do primeiro item de command antes da validação de tipo. Ordem
corrigida para validar tuple/tamanho e todos os str exatos antes de comparar
-ec; não chamar igualdade do caller. Depois33passed/1,86s. O teste AST agora
cobre também volume_sha256 e Store.__init__/pulse/arm_b/read.

Fonte final17411bytes SHA-256:
cf6634dae741c977a1ace3ca5bc4498fd6f41d8a349524f2cf1d666b4d84bb65.
Fonte anterior17401/d65a permanece somente como medição histórica abaixo;
nenhum consumidor nativo usou qualquer das duas. Rerevisão74378 aceitou o
delta, sem bloqueador. A conferência própria por reconstrução em memória da
ordem anterior recuperou exatamente o SHA d65a: só essas linhas mudaram,
17401→17411bytes. Isso não alega diff feito pelo revisor; ele limitou sua
conferência ao bloco Snapshot e ao teste AST.

## Desenho e B1, antes do código

Claude2/review68182 apontou a possibilidade de Store substituir/apagar o CID
anterior quando houvesse vários casos. Desenho corrigido antes do código:
Store/Watchdog único por caso e CID; Store.publish monotônico fixa task/case/
Cmd/baseline, CID None→um valor, birth None→um par, sem troca/retorno/clear.
Main só cria próximo caso após prova externa completa e join; todos Stores
novos recebem mesmo Bstart global e pulse atual, sem renovar deadline600.
Esse protocolo do caller permanece posterior, não comprovado por fakes.

Precisões incorporadas: namespace/captura em __init__ na thread principal
antes de armar, parser policy.P.P.one, case para adapter96e8, _bound público
como check_snapshot antes de qualquer CLI_KILL/begin, perfil completo task/
case/wrapper capturado. Falha fica SNAPSHOT_BINDING/HELD sem invoke. PID e
FILETIME ainda dependem do handle original, não são atestados pelo binding.

## Implementação e regressão vermelha primeiro

Nova fonte deriva do b868 sem mudar o original: classes/casos próprios,
POLICY_SHA96e8, nomes/kinds próprios, Store.publish monotônico e _bound.
Case strings declaradas fechadas e comparadas ao enum capturado em teste;
Snapshot aceita somente Cmd de duas strings exatas e no máximo12000.
Sem AST/monkeypatch em runtime. Teste AST somente em tests preserva reason,
namespace, Observation e métodos de ordem/volumes/lifecycle, normalizando
apenas nomes públicos declarados. Emergência54cc e volumes6e38 inalterados.

Oito regressões B1 executadas antes do fix:8failed/0,37s. Caso/task/Cmd/
baseline/CID/clear/troca e retirada de birth eram aceitos indevidamente no
Store derivado ainda igual ao antigo. Após fix:27passed/2,94s; matriz ampliada
com callback/thread/main/nomes globais:32passed/5,15s. Nenhum recurso real.

## Gates próprios antes da revisão

- 32 testes históricos: monotonicidade e Bstart global;23casos/role antigo recusado;
  binding antes de begin/CLI; parser/policy novos sem live reread; rm-v só
  após decisão durável; preexistentes preservados; alienCID/Cmd/task recusam;
  incerteza/named/already-absent exigem reconciliação; lock e PID desconhecido;
  falha de fsync antes de rm e antes de restored; start/join de Thread fakes;
  callback único/firedHELD; nomes globais não publicados; AST equivalente.
- Fonte17401bytes SHA-256:
  d65a53a4d6b2b68358069a772efae2d42befca47c0e292c375e1dce6af263c43.
- Ruff helper E9/F63/F7/F82 limpo; imports/formato corrigidos só nos novos
  arquivos. Essa tabela preserva os números anteriores ao delta de tipo.

## Gates finais e estado observado

- Seleção watchdog público anterior/adapter reader/watchdog novo/volumes:
  **122passed/5,72s**, sem falha, skip ou deselect.
- Ruff src/tests e E9/F63/F7/F82 do helper: limpos.
- Format src/tests mais helper novo:332 conformes.
- Mypy strict src/tests:331 arquivos limpos, alvos3.11 e3.14. Runtime executado
  somente Windows3.11.3; não afirmar execução3.14/Linux.
- Review74378/sessão51ea0d85 aceitou cf6634da após21812.
- Observação externa pontual Get-Process, sem DockerCLI ou thread criada:
  DesktopOff/count0 em2026-10-30T18:05:18.9591291Z. Não é monitoramento contínuo
  nem horário exato de stop. Dependências b868/54cc/6e38/96e8/8906 inalteradas.

## Limites

_bound não autentica SO ou CID; inspect+adapter continuam antes de mutação
de container. Snapshot sem CID não autoriza cleanup, fired sempre conserva
HELD, join não implica ausência/release. Fontes Python capturadas não são
relidas depois de armado; pins externos CLI/config/meta continuam relidos
a cada invoke pelo54cc inalterado. Raw Docker e baseline globais seguem
local-only; nenhum exportador deste lote existe ainda. Host/entry/proposta/
matriz exata exigem revisão própria. Gateway indisponível e gates abertos.
