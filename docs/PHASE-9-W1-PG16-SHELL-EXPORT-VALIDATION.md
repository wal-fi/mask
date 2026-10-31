# Exportador do leitor PG16 — revisão e validação independentes

2026-10-31, sob delegação vigente. Baseline37b09f7 sincronizado e árvore
rastreada limpa no início. Programador único: Claude2. Revisão/contraprovas/
execução dos testes: assistente principal, conforme instrução atual do usuário.
Modelo do Claude2 fixado em Opus5.5/esforço medium na preferência da conta,
no atalho e nas chamadas seguintes; configuração privada não entra no Git.

## Fontes e escopo

- `docs/poc/pg16_shell_export.py`:
  ed491c013ed1a731dc47a6fdeaee412db71a902993fd6fb2b257e30e3afebba3.
- `tests/test_pg16_shell_export.py`:
  906a8caea9c5e37857741e385323d7c5d58abd045fd9c55febd1fdad271a67a1.
- Contrato/schema/limitações em SHELL-EXPORT-DESIGN. Novo módulo e testes;
  nenhum código de produto, dependência, frontend ou recurso gerado alterado.

Captura de definições públicas pinadas da entradaafaf/Host8c; não chama
admit/prepare/run/drive de laboratório. Snapshot da raiz e até23diretórios
watch-NN, nomes/tipos/links/pais/limites fechados. Leitura limitada durante
o read,1024entradas/4MiB arquivo/32MiB total/512comandos. Revalida fontes
públicas e snapshot antes de escrever em destino novo, sem overwrite/retry.
Só summary.json e transport.json derivados; todos os brutos ficam locais.

Revalida estado/pins/23blueprints/plano, ledger/replies por label/índice/
hash/tamanho/exit, relatório do leitor pelo parser original e inspect-result
do mesmo caso/CID/retorno0ou42. Não converte19negativos em positivos nem
aceita prefixo com IO como report completo. Owner SENT só do vetor público
é projetado como SENT_LOCAL_HANDOFF/NOT_APPLICABLE para seed privado.
Watchdogs NOT_STARTED distintos de JOINED. Volumes conferidos pela baseline
completa, Mounts do último inspect próprio antes do rm, eventos de decisão/
final do ledger e inventários reais capturados. Diagnóstico fechado preserva
histórico; nenhum erro original ou campo livre é publicado.

## Primeira entrega e contraprovas vermelhas

Primeira entrega a7664f37/testes4815e041, produzida pelo Claude2 sem executar
comandos:41passed/68,26s na execução do revisor. Ruff check de testes passou;
format pediu ajustes e mypy encontrou dois retornos Any em funções Path.
Nenhum commit/publicação dessa versão.

O revisor escreveu um hook de pytest em memória, sem alterar código/testes
do produto, usando a fixture de sucesso real do novo teste (entrada/host
aceitos com transportes falsos). O teste positivo passou; o hook encerrou
com1erro esperado/11,94s, listando cinco contraexemplos independentes:

1. P2 UNBOUNDED_GROWING_READ: lstat tamanho1/read_bytes retornando xx;
   houve chamada de leitura sem limite antes da recusa.
2. P2 REPARSE_ANCESTOR_ACCEPTED: somente o pai Temp marcado reparse0x400;
   exportação ainda era aceita.
3. P2 DECISION_AFTER_CASE_FINAL_ACCEPTED: trocar posições/nomes da primeira
   decisão e do primeiro final, mantendo bytes canônicos/ordem gapless;
   project aceitava a decisão tardia.
4. P3 INTEGER_AS_BOOLEAN_PLAN_ACCEPTED: hold_open False trocado por0;
   igualdade de dict aceitava prova mal tipada.
5. P2 FAILURE_AFTER_COMPLETION_MARKER: erro de leitura do transport.json
   posterior ao rename fazia export falhar com marcador já visível.

Claude2 corrigiu por Edits e acrescentou13regressões formais, sem rodar
testes por conta própria. A revisão verificou read(limit+1), cadeia completa
de diretórios, eventos de volume ordenados ligados ao rm/último inspect,
comparação JSON canônica tipada e rename como última operação antes do retorno.
Escrita curta e falha do readback pendente ficam sem marcador completo.
Nenhuma fonte congelada foi editada para fazer os testes passarem.

## Gates finais medidos pelo revisor

-54passed/110,51s no arquivo do exportador, nenhuma falha/skip/deselected.
- Mesmo hook independente repetido sobre o resultado final:
  INDEPENDENT_REVIEW=CLEAN;1passed/18,21s, exit0, nenhum erro.
- Ruff src/tests e lint restrito E9/F63/F7/F82 do helper aprovados.
- Ruff format:341arquivos do escopo src/tests+pin_cost+pin_capture+export
  conformes. Não inclui PoCs históricas de SCRAM já documentadas como fora
  do padrão atual; fontes consumidas não foram renormalizadas.
- Mypy strict:338arquivos, alvos3.11 e3.14, sem erros. Runtime executado
  somente Windows/Python3.11.3; nenhum runtime3.14 afirmado.
- Seleção relacionada13arquivos:481passed/213,91s, nenhuma falha/erro/skip/
  deselected, exit0. Código/testes congelados nos SHA acima durante os gates.

Os testes escrevem somente seus diretórios temporários próprios e usam os
transportes falsos já existentes; não leem os executáveis/configurações Docker
fixados, não executam shell no container nem conectam a banco. Há loop asyncio
do teste e timer auxiliar real de40s no harness antigo, não watchdog nativo de
laboratório. Esses tempos são duração dos testes, não latência de PG/owner.
Nenhum PostgreSQL, browser, build de frontend ou pacote foi necessário:
somente docs/poc/testes mudaram e não há novo recurso embarcado/dependência.

## Limites e próximos passos

Recusa lotes com fire/evidência de emergência ou supervisão incerta; não
projeta esse caso como recurso liberado. Brutos/baseline permanecem locais;
hash é coerência de metadado, não sigilo de nomes previsíveis. Exportação
não é autoridade de cleanup nem atestação criptográfica da execução.

commands.seconds começa depois dos pins. Host8c não persiste tempo por owner
ou fsync: o ensaio futuro mede conclusão/prazo e os tempos de CLI disponíveis,
não O/w individualmente sem instrumentação própria. Envelope47012 continua
condicional. Nenhuma exportação de raiz operacional foi feita neste lote.

## Parecer final do revisor

Aprovado no escopo isolado do exportador/fakes, sem P1/P2 remanescentes.
Os cinco contraexemplos originais não se reproduzem no resultado final e
as13regressões formais passam. Depois dos gates só relatórios/estado foram
editados; nenhum código/teste foi reescrito pelo revisor. Não é aprovação
individual do usuário nem release de Gateway. Publicação técnica autorizada
pela delegação vigente, com coautoria do programador Claude Opus5.5.

Próximo: preparar estado≤32768/admissão3s e
proposta/comando revisados antes de uma rodada pública. Artefatos da task3eb3
continuam consumidos/intactos. Nenhum Docker/PG/worker/SQL/serviço ou observação
nova do Desktop. Sem segundo escritor, quota ou job novo. Gateway indisponível;
B1/B2/D090gate2/C1/SQL/produção continuam abertos.
