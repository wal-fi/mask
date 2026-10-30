# Fase 9 — Etapa 8 — B2-B2: múltiplos membros Windows

**Estado (2026-10-20): preparação sob delegação do usuário; revisão inicial
do plano concluída, com lacunas para os controles completos. Primeiro
diagnóstico estreitado para B2-B2a (§7), executado após rerevisão do código:
cinco casos completos, lacuna compartilhada observada, cleanup confirmado.
Evidência em `PHASE-9-STAGE-8-B2-B2A-VALIDATION.md`, revisada. Não fecha
B-2, B-1 fim a fim ou D-090 gate 2; SQL PGWire segue recusada.**

## 1. Contrato candidato e limites

Estudar a soma de cotas **individuais impostas**, com número de membros
também imposto, em vez de reutilizar o teto agregado que falhou. A escolha é
nova, sob a delegação de 2026-10-20, não uma aprovação retroativa do B2-A.
Antes de integrar o produto, revisar o argumento de cobertura de todos os
processos/auxiliares, incluindo seus próprios limites e os custos do pai.

Um job próprio por membro: `PROCESS_MEMORY` de **32 MiB por processo**,
`ACTIVE_PROCESS` de 1, `KILL_ON_JOB_CLOSE`, sem breakaway e **sem** cota
agregada de job. Controlador conhece somente N em {2, 4}, sem launcher
auxiliar nesta versão; não é integração da admissão global operacional.
Criação com `PROC_THREAD_ATTRIBUTE_JOB_LIST`, suspensa,
conferência de associação e identidade antes de retomar; sem Assign posterior
ou fallback. As cotas não são elevadas após falha.

O argumento limitado é: se cada um dos no máximo N membros está sujeito à
cota individual C, o commit privado desses membros tem orçamento N × C.
Não inclui supervisor/guardião externo, memória compartilhada/kernel ou pai
do gateway. A conclusão depende do inventário e do contrato do SO, não da
soma de picos individuais observados em instantes diferentes.

Registrar os picos individuais e sua soma como limite superior calculado
(não pico simultâneo), sem tolerância,
subtração de baseline ou descarte de excessos. Contador que exceder o limite
reivindicado reprova essa asserção; não pode ser explicado como falso só
porque a alocação retornou erro. O FAIL histórico de 384 MiB e os 12 excessos
job-only do B2-A continuam intactos.

## 2. Experimento sintético limitado

Sem gateway, worker operacional, SQL, PostgreSQL, Docker, rede, secrets ou
instalação. Fontes novos e cópias privadas de helpers em diretório temporário
novo, fora do checkout, arquivados antes da execução. Não alterar o B2-A.
Runtime inicial: CPython 3.11.3 nativo existente. Não extrapolar para 3.14 ou
POSIX; job herdado do host registrado, sem breakaway ou alteração.

- Preflight: pelo menos 2 GiB de memória física e 4 GiB de commit disponíveis.
- Pressão máxima pretendida: 4 membros × 32 MiB; supervisor fora da soma.
- Payload pedido por membro até 40 MiB, reserva de emergência de 2 MiB já
  incluída no baseline sujeito à cota, passos de 1 ou 4 MiB.
- Dois alocadores: `bytearray` Python e `VirtualAlloc`/`VirtualFree` nativos.
- Sincronizar todos os membros em checkpoints: ninguém libera o payload
  enquanto outro satura. Registrar uma amostra conjunta estável com todos
  parados após falha de alocação, além dos picos.
- Teto de 64 amostras/64 KiB por caso e 4 MiB por lote. Relatório incompleto
  impede aprovação; nenhuma evidência descartada para caber.
- Prazos: 30 s por caso, 300 s por lote e watchdog independente do fluxo
  principal; cleanup só de jobs/handles deste lote. Falha de cleanup impede
  próximo caso e exige diagnóstico, nunca varredura destrutiva por nome.

Controles antes da pressão: job vazio; dois membros normais; handle sem
direito de atribuição recusado sem filho; membro excedente e breakaway
recusados com os admitidos preservados; sem cotas de memória, quatro membros
conseguem manter 40 MiB cada. Este último distingue a recusa sob cota de uma
limitação anterior do host neste perfil, não prova ausência de toda restrição
herdada. Reconfirmar configuração efetiva e inventário completo.

Contraprova separada: dois membros tentam seção compartilhada pagefile-backed
de 40 MiB e tocam as páginas. Registrar se a cota privada a contém, sem exigir
recusa para transformar resultado em verde. Se não contiver, o contrato de
memória total não está provado: inventariar e limitar esse vetor antes do
produto. Memória privada não pode ser rebatizada como toda memória do host.
Primeiro incremento executável: somente estes controles de segurança; revisar
fontes e resultados antes da matriz de pressão. Acrescentar controle de morte
do guardião com vários membros e confirmação externa antes da pressão.
Não confundir esses controles com prova universal de falha durante cada
instrução nativa de criação; limites dessa prova permanecem explícitos.

Matriz predeclarada: N em {2, 4} × alocador em {Python, nativo} × passo em
{1, 4 MiB} × duas repetições = **16 casos de pressão**, depois dos controles.
Cada execução registra todos os casos previstos, não executados e falhos.
Falha no próprio harness é corrigida e revista antes de uma nova rodada,
preservando artefatos e causa somente quando demonstrada.

## 3. Asserções por caso

1. Configuração relida exata, membros conhecidos, associação confirmada antes
   de retomar, imagem e identidade conferidas; nenhum membro extra.
2. Todos os membros chegam ao baseline e pressionam; não aprovar caso em
   que um morre antes de disputar memória ou não alcança recusa observável.
3. Cada pico individual de PSAPI e de job dentro de C, independentemente da
   soma; amostra conjunta dentro de N × C e payloads coexistindo no checkpoint
   final. Sem job compartilhado não há contador agregado único do SO. Somar
   picos individuais fornece um limite superior calculado, não medição do
   pico agregado simultâneo.
4. `MemoryError` ou `VirtualAlloc == NULL` são observações de recusa, não
   prova isolada de contenção. Ausência de erro não é sucesso se não houve
   saturação.
5. Fim de todos confirmado por handles/identidades e job vazio; handles,
   mapas e eventos fechados. Sem liberação lógica de crédito por mera
   sinalização do filho, EOF ou pedido de kill.

## 4. O que permanece aberto

Mesmo uma matriz verde certifica apenas este perfil sintético. Não impõe
limite ao pai, ao verificador D-107, TLS, codec, gerações ou bookkeeping;
não integra o ledger nem prova isolamento do pipeline. B-2 e D-090 continuam
abertos. Antes do codec, escolher e revisar representação que não amplifique
dados arbitrários no pai ou um domínio de processo realmente limitado.

As duas alternativas em análise são buffers de bytes fixos com validação
incremental sem objetos de linhas no pai, e plano de dados por sessão
contido incluindo socket/TLS. Nenhuma está implementada ou declarada aprovada
por este plano. Mudança arquitetural deve registrar tradeoffs, segurança,
compatibilidade e novas provas; não rebatizar uma restrição ausente.

## 5. Referências

- [Microsoft — limites estendidos](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).
- [Microsoft — número de processos e flags](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
- [Microsoft — associação na criação](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

São contratos documentados, não medições locais. Resultado e revisão próprios
serão registrados em evidência separada, sem modificar relatórios anteriores.

## 6. Revisão da preparação e rascunho

Claude2 revisou somente leitura na sessão
`747e03db-22b5-4fbf-a719-de254e1e261c`, sem executar ou aprovar código.
Aceitou a governança sob delegação; apontou seis lacunas técnicas para os
controles: separação controlador/guardião e ownership dos handles; distinção
entre picos individuais e simultâneos; controles distintos de contagem e
breakaway; observador externo da morte do guardião; dimensionamento do
relatório conjunto; e variantes SEC_COMMIT/SEC_RESERVE de memória compartilhada.

O primeiro rascunho `docs/poc/b2b2_controls.py`, antes do estreitamento da §7,
não tinha SEC_RESERVE nem observador externo e confundia breakaway com
contagem. Nunca foi executado com processos. A versão posterior B2-B2a
substitui esse rascunho, implementa SEC_COMMIT/SEC_RESERVE e **não** executa
os testes de escape ou morte. O observador e os controles completos continuam
pendentes para a matriz maior. Só o selftest sem jobs foi executado até este
checkpoint; revisar a versão B2-B2a antes de `--controls`.

A próxima iteração dos controles completos deve fechar estes pontos sem ampliar as cotas ou esconder
falhas. Caso a seção compartilhada escape da cota privada, esse resultado
deve orientar a arquitetura antes da matriz de pressão, não ser declarado
contenção de toda memória. O destino/SO foi perguntado ao usuário de forma
não bloqueante; a resposta pode mudar a prioridade Windows/POSIX.

## 7. B2-B2a — contraprova preliminar de seções compartilhadas

Sob a mesma delegação, executar **primeiro** a contraprova de cobertura de
memória, depois de revisar os fontes específicos. Ela pode invalidar a
estratégia antes do investimento na matriz maior. Não executa a matriz de
16 pressões, escape, breakaway ou morte deliberada do guardião, nem se
apresenta como prova de lifecycle em crashes. Os seis requisitos da revisão
continuam necessários para os controles completos, não são dados como feitos.

Perfil predeclarado: Windows nativo, CPython 3.11.3 x64 existente, páginas de
4 KiB, estrutura de limite estendido de 144 bytes. Recusar perfil diferente.
Um guardião direto com watchdog independente do laço principal; até dois
membros, job próprio por membro, `ActiveProcessLimit=1`, `PROCESS_MEMORY`
de 32 MiB (exceto o controle positivo sem cota), sem breakaway, associação
JOB_LIST na criação e nenhum handle herdado. O guardião é o único dono dos
handles de job; o canal numérico de checkpoint usa um mapeamento de 4 KiB
por membro e dois eventos exclusivos. Esse mapeamento é custo compartilhado
do harness, não memória privada inventada no orçamento.

Cinco casos, uma execução completa, sem repetição até verde:

| Caso | Membros | Tentativa por membro | Cota privada | Conclusão possível |
|---|---:|---|---:|---|
| vazio | 0 | nenhuma | 32 MiB | criação/configuração e cleanup |
| normal | 2 | `bytearray` de 1 MiB | 32 MiB | controle positivo pequeno |
| sem cota | 2 | `bytearray` de 40 MiB | desligada | capacidade neste host, não ausência de toda restrição herdada |
| SEC_COMMIT | 2 | seção anônima pagefile-backed de 40 MiB, mapear e tocar todas as páginas | 32 MiB | observar cobertura/lacuna, sem forçar recusa como resultado desejado |
| SEC_RESERVE | 2 | seção anônima de 40 MiB, mapear, `VirtualAlloc(MEM_COMMIT)` na view e tocar páginas | 32 MiB | observar separadamente criação, map, commit e toque |

As seções de payload são sem nome, sem exportar handles; só o checkpoint
possui nome exclusivo. O guardião amostra os dois membros enquanto ambos
retêm os payloads e esperam ACK. Registrar retorno/fase/código de cada API,
páginas tocadas, commit privado/pico PSAPI e os dois picos do job de cada
membro. `GetPerformanceInfo.CommitTotal × PageSize` no baseline e no
platô é apenas evidência global complementar e ruidosa, sem atribuição causal
exata ao harness. Não existe contador agregado único dos dois jobs.

Máximo de payload intencional coexistente: **80 MiB**, mais baselines e
pequenos checkpoints; preflight de 2 GiB físicos e 4 GiB de commit livres.
Não há pedido proporcional a entrada externa, arquivos de dados ou banco.
Prazo de 30 s por caso, 120 s do watchdog do lote; casos não alcançados por
prazo/erro ficam não executados no sumário (não aprovados). Artefatos de até
64 KiB por caso e 4 MiB por lote, com os três fontes arquivados antes dos
casos. Término por handles, exit code, job vazio e fechamento conferido para
cleanup; falha de cleanup interrompe o lote e nunca autoriza release.

Completar esse diagnóstico não fecha contenção, mesmo se as seções falharem.
Se alocarem 40 MiB sob cota privada de 32 MiB, registrar precisamente essa
lacuna; não aumentar cotas, descartar os mapas ou declarar memória total
contida. Sem produto/SQL/worker, alteração da `.venv`, instalação, commit ou
push neste diagnóstico. Código em `docs/poc/b2b2_controls.py`; cópias privadas
e execução somente em diretório temporário novo fora do checkout.

Referências adicionais: [CreateFileMapping](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createfilemappinga),
[MapViewOfFile](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile)
e [PERFORMANCE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information).

Na primeira revisão do código estreitado, Claude2 aceitou o envelope de
segurança do diagnóstico, mas não conseguiu ler helpers fora do checkout.
Exigiu conferir os helpers, exigir `ResumeThread == 1`, garantir eventos
auto-reset, verificar hashes antes do import/na cópia arquivada/no fim e
registrar `coverage=gap_observed/refused/inconclusive` explicitamente por
membro. As correções estão no rascunho em rerevisão; nenhum processo foi
criado nesse intervalo. A rerevisão recebe leitura somente do diretório
histórico dos helpers via `--add-dir`, sem ferramentas de escrita/execução.
