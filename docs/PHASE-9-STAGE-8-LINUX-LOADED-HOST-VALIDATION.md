# loaded-as128 — observador externo, testes simulados

**2026-10-22 — código isolado revisado sem bloqueador; sem execução real.**
Sob delegação vigente, não aprovação individual fictícia. AS32 e seis rodadas
anteriores preservados. B-1 fim a fim/B-2/D-090 gate2/SQL/produção abertos.

## Entrega e limites

Novo docs/poc/run_linux_loaded.py, com tests/test_loaded_memory_host.py.
Reusa funções selecionadas do observador anterior: preparação inicial,
readiness/preflight, CLI limitada, inspect/save/identity/cleanup. Não herda
classe com case/run/check antigos, não transforma Cmd ou usa classificador
AS32. Fluxos e perfis próprios loaded-as128. Nenhum comando Docker é emitido
ao importar o arquivo; as classes de teste não iniciam watchdog real.

Preparação nova copia seis fontes para probe RO e quatro hosts fora dele,
usa bundle SHA256 do mapa canônico das dez fontes antes de labels/pending/
identity/cleanup e preserva árvore/pins/runtime existente. No teste dessa
composição, o init de preparação foi substituído por fixture minúscula:
não se construiu o Observer real sobre a árvore preparada73MiB.

Perfil/argv conferidos diretamente por inspect, sem reescrever um perfil
para passar noutro: imagem pinada, dois mounts RO, UID65534/NNP/caps/rede/
namespaces/limites/env, Cmd com --case e --expected explícitos. Um único grant
por caso, uma tentativa por instância/lote, interrupção no primeiro resultado
inválido. Controle control_ok só admite128 após digest recalculado, remoção
própria confirmada e integridade; privado imposto é gate do compartilhado.

Raw do supervisor é salvo **antes** da validação,<=64KiB, fsync/replace,
contado no1MiB e imutável por nome. case.json guarda referência/hash/bytes,
sem envolver outro JSON grande dentro do mesmo teto. Raw/todas fontes/cópias/
manifesto/árvore são reconferidos antes da próxima admissão e no final.
Criação incerta recupera apenas por nome exato e identidade completa; label
de import antigo é estrangeiro e não é removido. Recuperação não torna a
tentativa positiva. Nenhuma limpeza global ou Docker exec.

30s/caso e120s/lote preservados; integridade antes/depois fica dentro do lote
e fora do timer do caso. Tabela no desenho declara que a soma dos piores
casos **não** cabe necessariamente: exceder prazo é inconclusive/stop, sem
ampliar quota ou repetir. Cleanup ainda é tentado, não há teto absoluto do SO.

## Desenho, testes primeiro e correção do prazo

PHASE-9-STAGE-8-LINUX-LOADED-HOST-DESIGN.md foi revisado pelo Claude2 na sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f antes do código. H1–H4 incorporadas:
schemas exatos/fallback, tabela de orçamento, identidade substituída antes
de uso e accounting/raw imutável. Aval só para testes primeiro com fakes.

Primeira coleta de testes falhou por módulo novo ausente; não são regressões
contra código inexistente. Matriz inicial de parsing/perfil passou44, depois
59 com ciclo de CLI completo simulado e65 com integridade/prazo/preparação.
Parâmetro de65KiB recebeu ID curto após dois erros de setup com nome gigante;
não se atribui causa adicional não medida. O fake do supervisor anterior
omitira detalhes do pai: normalizados **só nos novos testes** inherited_as e
procs/pids de startup/final, para corresponder ao backend real. Não se mudou
o teste anterior nem relaxou o parser para aceitar metadados impossíveis.

Regressão vermelha mostrou que watchdog atrasado, ainda não marcado fired,
podia permitir create após120s. Corrigido com relógio explícito antes de grant,
create/start e attach limitado ao menor saldo caso/lote. O mesmo teste passou
depois sem raise de limites. Fixtures foram divididas e anotadas para os gates
de estilo/tipagem, sem novas exceções na configuração.

## Revisão bloqueante: negativos fortes também precisam de evidência

Primeira revisão de código encontrou B1: fail/incompatible eram tipados, mas
não se verificava a base forte dessas afirmações. Não admitiam caso seguinte
nem sucesso, porém podiam poluir o registro com uma conclusão sem fundamento.

Seis regressões primeiro falharam: cleanup falso, FAIL sem testemunha, código
de import errado, stage errado, incompatible no controle e cgroup com OOM.
Correção exige startup/cleanup/final[1], limites128, observações coerentes e
progressão/cap externo de cgroup para essas duas classificações também.
FAIL aceita só OBSERVED_FAIL e última observação independente confirmando
pico>128 ou size>=pré+40 no HELD; pré é índice5, **não** ready antes dos
imports. Isto depende da ordem fixa do supervisor: mudança futura exige
revisão coordenada. Código de saída permitido é-9 ou0..255; o host confia no
supervisor hashado para distinguir kill próprio, não mede sinal por conta
própria nem o classifica como recusa.

Incompatible só em128, stage imports, MEMORY72/IMPORT73 natural correspondente.
Sem digest exigido para import interrompido. Falha dessas condições produz
REPORT_LIFECYCLE e outcome inconclusive no case/summary; raw negativo original
permanece intacto. Testes preservam fail/incompatible válidos do supervisor
fake e comprovam downgrade dos inválidos no lote inteiro. Oito novos casos
passaram após o fix e dois extras conferem persistência/downgrade do raw.

Rerevisão confirmou B1 fechado, sem bloqueador residual no código com fakes.
Revisor não executou testes; números e hashes são medições deste executor.
Não aprovou procedimento, comando ou execução real. Nenhuma cota observada,
job novo ou outro escritor iniciado.

## Gates finais medidos

Windows, .venv existente Python3.11.3. Fakes de CLI/inspect/clock/watchdog e
arquivos pequenos nos diretórios temporários do pytest; fsync/replace foram
exercidos nesses artefatos próprios. Não houve processo/thread do laboratório,
DockerCLI, conexão, consulta, workload ou leitura da preparação real neste lote.

- **75 testes novos passed em1,41s**, sem skips/xfail.
- **744 relacionados passed em5,34s**,669 anteriores+75; seleção completa
  linux_as/linux_imports/loaded_memory, -o addopts=, sem deselect.
- Ruff src/tests e E/F/I/B/UP do novo PoC limpos.
- Format check **256 arquivos**, src/tests+novo PoC, todos conformes.
- mypy strict3.11 e3.14 **255 source files**, ambos limpos.3.14 somente
  análise estática, não runtime executado.
- Diff check e whitespace dos novos limpos; avisos LF/CRLF conhecidos.

Sem suíte integral PG16/frontend/pacotes repetidos: nenhum código src, recurso,
dependência ou configuração de produto mudou. MANIFEST.in continua prunando
docs; estes helpers não são superfície distribuída do produto.

Hashes finais:

- run_linux_loaded.py:d95cdfe231ab273fba96c4ecd808ce829327caea466992ee90c98c9d27a0e821;
- test_loaded_memory_host.py:cc8ab88a536f6d43e0ac74e9d942510f8deaeb994bf401ca5946381ed1c1d0e9.

## Próximo gate, sem execução por este fechamento

Procedimento externo deve registrar estado do Desktop, um version externo
limitado com cada exit conferido, abort durável sem nova tentativa e condição
de restauração apenas se o próprio lote iniciou o Desktop. Depois revisar o
comando exato e confirmar os hashes das fontes antes da rodada única.
Leitura real /proc/<pid>/fd/readlink do filho continua não comprovada e deve
falhar fechado. Não há certificação de128MiB/192MiB ou produção.

Desktop e recursos de outros trabalhos não foram iniciados, parados ou limpos.
Sem fetch, commit/push, deploy ou alteração do ambiente. Próximo incremento
continua sujeito a revisão técnica, não a novo aval individual por lote.

## Auditoria do fechamento

Baseline novo do início deste lote:364 caminhos, final368, zero ausentes.
Somente seis documentos de estado existentes mudaram, mais quatro novos:
desenho/evidência, observador e teste. Zero src alterado neste lote; fontes
congeladas, core/produtor/coletor/supervisor e .venv/pyvenv.cfg iguais ao
baseline. Arquivos pessoais e diferenças anteriores preservados.
HEAD4a5e556, origin/master em cache5d173ea,0behind/1ahead; sem fetch/escrita Git.
Diff e whitespace dos novos limpos. Depois dos gates só documentação mudou,
por isso as suítes não foram repetidas. Nenhum processo de laboratório ficou
esperando comando e nenhuma tarefa de retomada foi necessária neste lote.
