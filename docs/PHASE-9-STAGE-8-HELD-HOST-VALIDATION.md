# HELD integração II — observador e artefatos, somente fakes

**2026-10-22 — II revisado sem bloqueador, somente fakes.**
Sob delegação vigente, não aval individual fictício. I aceito só em fakes;
III/procedimento/comando/rodada real não iniciado. B-1/B-2/D-090/SQL e
produção abertos. Sem alteração de src, dependência, configuração ou produto.

## Desenho e fluxo novo

HELD-HOST-DESIGN revisado antes do código, sessão51ea0d85. R1 argv completo
-I/-B/-S; R2 pins cruzados; R3 parse/E só depois de remoção, fora30s/dentro120s;
R4 tabela de exits/ausência/OOM. Incorporados antes de implementar II.

Novo docs/poc/run_linux_held.py. Fluxo superior derivado mecanicamente do
contrato do observador congelado, revisado como código novo. Não herda
case/run/check nem diagnostic_success, não altera inspect/resultado para
encaixar no perfil antigo nem monkeypatch em globais. Seleciona apenas
primitivas baixas/prepare/readiness/preflight anteriores. H/E/T/W e13 hashes
congelados conferidos no load; E somente no host, não no container.

Init14 fontes,8 probe RO e6 hosts fora, source_hash do mapa canônico14 e
task held-as128 próprios antes de label/pending/CID. runtime/árvore separados.
Pins cruzados do wrapper para S/T e E para H, fontes/cópias/artefatos antes
de cada create e fim. Teste de init usou preparação minúscula injetada, não
árvore real73MiB. Preserva todos os arquivos/classes/medições anteriores.

Case só lifecycle: pending, criação/inspect/identidade, bounded attach,
**transport raw salvo imutável antes de parse**, inspect pós-exit e cleanup
de identidade própria. Timer30 termina antes da avaliação E. Exit64=ARGV,
70=EXECUTION, outro/OOM=CONTAINER_EXIT, exit0 sem raw=MISSING; nenhum deles
gera envelope. Raw vazio também é preservado como artefato de0 bytes.

Somente depois da remoção/cleanup: decoder fechado do transporte, E.encode,
envelope salvo como segundo artefato imutável, E.decode e revalidação do
original para digest. Processamento fora do caso30s, dentro do lote120s.
Expirar lote durante E torna caso inconclusivo mesmo com envelope salvo.
Metadados referenciam ambos por SHA/bytes;1MiB inclui os dois e regravações.
Sem raw completo duplicado em case.json.

Transport fallback ou E fallback interrompe; tap_broken sempre inconclusivo.
Original positivo com broken produz E.FALLBACK, nunca envelope positivo;
negativo pode ser preservado exatamente em envelope negativo sem HELD.
Fail/incompatible só após validação congelada, não aceitos por marcador.
Controle validado/cleanup/integridade admite privado128 com digest próprio;
imposed privado admite shared. Sumário/perfil próprios, sucesso requer3
resultados esperados, E validado, dois artefatos, pins, cleanup/integridade/
prazo/inventário. total_memory_contained=false em qualquer resultado.

## Testes primeiro, falhas e correções preservadas

Primeira coleta falhou por módulo novo ausente. Testes assíncronos iniciais
usaram marca/plugin não instalado:21 falharam antes de executar e6 passaram.
Sem instalar plugin: passaram a funções síncronas com asyncio.run, padrão
existente. Depois14 falhas eram de fixture de image inspect: comparava o
digest pinado com o IMAGE falso do teste e tratava imagem como container.
Fixture corrigida, sem mudar requisito de produção ou helpers antigos.

Quatro falhas restantes mostraram tratamento incorreto do newline no novo
decode_transport (literal backslash+n em vez de newline); corrigido só no
código novo. Os27 casos passaram. Matriz extra de8 casos encontrou quatro
regressões vermelhas:64/70 sem raw perdiam categoria, bytearray de fallback
era aceito antes da conferência de tipo, e sumário não exigia explicitamente
pins_consistent no final. Correções: prioridade dos exits, tipo bytes antes
de igualdade e requisito de pin final.35 passaram. Mais contraprovas de
negativo forte/broken, erro de envelope, parser fechado, raw adulterado após
remoção e relógio tardio sem watchdog levaram a45 verdes.

Fakes só reaproveitam mecânica da fixture antiga: instância nova da classe
II e CLI/inspect simulados. Nenhum case/run da classe antiga é executado.
Cmd da fixture é construído para o wrapper; não representa reescrita de
inspect real. Pins da fixture de ciclo são declarados true; teste de init
separado confere os14 arquivos reais do código e cópias pequenas, inclusive
troca do tap causando falha. Remoções são callbacks, não Docker.

Teste R3: E consumindo35s lógicos por caso completa em105s do lote, sem
atribuir35s aos casos; E consumindo121s no controle impede outro create.
Não é medição de performance. Preflight inválido não cria; incerteza continua
negativa; estrangeiro não removido. Corpo do parser exige schema exato,
ASCII/sem NaN/duplicata/overflow, tipo antes de igualdade e duas evidências.
R1 prova perfil válido antes de retirar cada flag para evitar falso positivo
por outra inconformidade do fake.

## Gates medidos antes da revisão

Windows3.11.3, .venv existente; nenhuma factory Linux/proc/CLI/carga.

-45 novos passed em1,65s, sem skips/xfail;
-894 relacionados passed em8,97s (849 anteriores+45), seleção completa
 linux_as/linux_imports/loaded_memory, -o addopts=, sem deselect;
-Ruff src/tests e E/F/I/B/UP do PoC limpos;
-format261 arquivos conformes;
-mypy strict3.11/3.14 em258 sources limpos;3.14 somente estático.

Imports/atribuição tipada do seam pytest ajustados sem ignorar regras ou
configuração. Hashes provisórios para revisão:

-observador:d8e97e2ee97f43d4e9116f16f9ed3bc3510f346acb35cc7f4313cb7ed5279ae1;
-teste:fb4420d845396035b476a21c224ddd0d39645fae2287d8efbd649691226760ef.

Nada prova import/factory reais do wrapper sob Linux -S, custo do PID1,
conteúdo nativo sob falha, memória total/pai/saída/concorrência ou runtime3.14.
Escaping pode estourar cap mesmo com original<64KiB, causando fallback e
perda do original antes do host: inconclusivo, sem truncar/elevar/repetir.
Plano da rodada anterior consumido, evidência Q1 original não reescrita.

Sem PG16/frontend/pacotes repetidos, porque produto/recursos/deps não mudaram;
sem alegar seus resultados antigos como novos. Próximo: revisão de código II;
III requer procedimento externo/hashes/estado/contexto/comando e rodada única
revisados separadamente. Nenhum Docker/start/stop Desktop, build/install,
outro escritor, commit/push ou deploy neste lote.

## Revisão inicial e regressão adicional do prazo final

Primeiro parecer II51ea0d85 não encontrou bloqueador e aceitou somente fakes,
sem III. Duas notas preservadas: load do host tem intervalo entre hash e
IMPORTS.load (aceito no single-writer com integrity antes dos casos); envelope
negativo junto de TAP_BROKEN não é conclusão forte do caso, que é inconclusivo.

Durante a revisão, o executor encontrou e reproduziu outra falha no código
II derivado: timestamp/deadline eram calculados antes da integrity final.
Novo teste, primeiro vermelho, fez essa conferência terminar em121s e ainda
obteve diagnostic_success=true. Corrigido **só no novo II**: integrity final
antes de fechar watchdog e colher timestamp/deadline. Campo elapsed_scope
declara o checkpoint: até integrity final e fechamento do watchdog, **antes
da escrita final de summary.json**. Não é teto absoluto de fsync/SO nem tempo
total de startup/preparação. Não se infere quebra real na rodada anterior
ou se reescreve sua evidência; helpers congelados continuam iguais.

46 novos passaram em1,98s após o fix; Ruff/format e mypy3.11/3.14 limpos.
Gates finais relacionados/hashes e rerevisão ainda pendentes neste registro.

## Fechamento revisado

Rerevisão somente leitura51ea0d85 confirmou correção do prazo final sem
bloqueador: integrity -> watchdog.close -> timestamp/deadline -> classificação
e escrita do summary. Flag que dispara durante integrity também invalida.
Tempo não inclui escrita final/fsync nem startup/preparação anterior ao run,
conforme elapsed_scope; não reinterpretar nenhuma rodada anterior.

Aceite só de código/fakes II; revisor não executou testes. Notas de gap
hash/import no host e TAP_BROKEN inconclusivo continuam obrigatórias. III
precisa plano, estado Desktop/contexto,14 hashes/cópias, version externo com
exits conferidos, comando exato/cwd e rodada única revistos antes de carga.

Gates finais sobre o resultado corrigido:

-46 novos passed em1,98s, total I+II92 novos;
-895 relacionados passed em9,17s (803 anteriores+92), sem skips/xfail/deselect;
-Ruff src/tests e PoCs limpos; format261 arquivos conformes;
-mypy strict3.11 e3.14 em258 sources limpos; runtime só Windows3.11.3.

Hashes finais:

-run_linux_held.py:02d2774a4c7af48a8e2f3b1491bc4384872806231d8e2dbfee5c210736f2a0b0;
-test_loaded_memory_held_host.py:d264bc9537025c42ef3bb5a4e2d9196cab26cc23bf1ea7f4a9b5f42a84e4f091.

I permanece igual aos hashes e46/849 registrados em ENTRY-VALIDATION;
seus testes também executaram no total895. Depois dos gates só documentos
mudaram, sem repetir nem apresentar suítes PG/frontend/pacotes antigas como novas.

Baseline375 caminhos; final384 com9 novos (4 documentos,3 helpers e2 testes),
zero ausentes. Somente seis documentos de estado existentes mudaram.
Novos: INTEGRATION-DESIGN, HOST-DESIGN, ENTRY-VALIDATION, HOST-VALIDATION,
tap, wrapper, observador e seus2 testes. Zero src ou helper/teste/artefato
anterior alterado; .venv/pyvenv.cfg e arquivos pessoais preservados.
GitHEAD4a5e556, origin em cache5d173ea,0behind/1ahead; sem fetch/escrita Git.
Diff/whitespace limpos. Sem CLI Docker/processo de laboratório, proc/Linux,
pressão/banco/SQL, start/stop Desktop, instalação, segundo escritor, cota/job
novo, commit/push ou deploy. B-1/B-2/D-090/produção continuam abertos.
