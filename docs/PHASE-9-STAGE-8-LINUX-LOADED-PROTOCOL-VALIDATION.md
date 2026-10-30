# loaded-as128 — núcleo puro, sem execução de memória

**2026-10-21 — núcleo puro local revisado sem bloqueador; sem integração/execução.**
Protocolo desenhado e revisto antes do código na sessão51ea0d85. P1–P5
incorporados (pico só nos128, hash único, controle sem comparação de hash,
leituras independentes do supervisor, ABORTED sem RELEASE/FINISH). Delegação
vigente, sem atribuir aprovação individual fictícia. AS32 continua did_not_fit.

## Entrega delimitada

Novo docs/poc/loaded_memory_protocol.py, só hashlib/json/math: digest,
parser de argv fechado, schema de held<=1KiB e máquina de estados com
deadline único, observações injetadas pelo coletor confiável. Sem produtor,
resource/mmap, I/O, processo, Docker, banco, SQL ou integração operacional.
Fatos fakes não demonstram SO ou imports realmente auditados.

Digest usa validator de inventário existente via colaborador confiável,
cap local1500/768/1MiB, rejeita nomes duplicados e usa iterencode limitado.
Bytes: domínio b"loaded-as128-v1\n" + JSON ASCII compacto de linhas ordenadas,
sem etapa; conhecido268da600...e6587. Nenhuma nova regra de origem.
Admissão só retorna True; digest do controle não sai pela API control_digest
até fim/EOF/exit0/cleanup confirmados. Sem segundo caso a partir de controle
que só completou imports. Digest não autentica código malicioso.

PRESSURE só depois da admissão e nova conferência de limites/VM. HELD só
observa resultado candidato, outcome permanece inconclusive até completar
cleanup. Release exige inventário[1,pid], fatos do supervisor e pico igual
ao relatado (com size/RSS distintos permitidos pela sequência da reserva).
Controle deve confirmar queda anon>=32MiB e VmSize<=pré+4MiB, no máximo5
amostras separadas por1s e dentro do mesmo deadline. Falha interrompe antes
de shared. ABORTED proíbe qualquer comando; kill/reap é obrigação do chamador,
nunca convertido em descarte válido. Core não coleta nem impõe esses fatos.
Exceção inesperada em operação pública também fecha ABORTED com categoria
fixa fora do except original, sem cause/context e sem retry do protocolo.

## Testes primeiro e gates medidos

Arquivo de teste criado antes do módulo: primeira coleta falhou por módulo
ausente. Não é alegação de159 regressões contra código antigo: componente
não existia. Implementação inicial passou60 testes; matriz ampliada passou
**159 focados/454 relacionados** (295 anteriores), sem skips/xfail.

Inclui vetor de hash, ordem/etapa, owner/origem/duplicado e caps; argv fechado;
três fluxos completos, controle acima de128MiB ainda válido, digest bloqueado
antes do fim;91 transições ilegais/duplicadas; schema/frames/NaN/tipos bool;
recusa do primeiro bloco,40MiB sem recusa, limite/pico independente divergente;
duas condições do descarte, cinco amostras, deadline durante validator e
saldo para espera; callback sanitizado sem cadeia; EOF/exit/cleanup incertos.

Ruff src/tests e E/F/I/B/UP dos PoCs limpos, format254 arquivos;
mypy strict alvos3.11/3.14 em251 arquivos limpo. Um RUF005 e sete diagnósticos
iniciais de helpers/anotações corrigidos sem alterar regras/configuração.
Runtime executado: .venv existente, Windows/Python3.11.3, só fakes.
Sem repetição de PG16 integral, frontend, pacotes, runtime3.14 ou pressão.

## Limites e passagem

Revisão somente leitura do código/testes pelo Claude2 antes de integrar
qualquer produtor/coletor/harness. Próximo trabalho precisa implementar e
revisar reserva mmap real, amostra antes do close, fluxo de imports e
comparação antes de PRESSURE, /proc do membro, EOF/reap, argv/inspect e
preflight. Só depois código/testes/comando revisados poderão autorizar
uma rodada própria. Nenhuma execução real autorizada por este núcleo.

Produto/src/MCP legado e fontes/artefatos das seis rodadas preservados.
Nenhuma dependência/env, segundo escritor, commit, push ou deploy.
Desktop não foi iniciado; B-1/B-2/D-090 gate2 e SQL/produção abertos.

## Revisão B1 e correção (distinta do gate B-1 do snapshot)

Primeiro parecer51ea0d85 achou bloqueador concreto: completed comparava
marker/inventory antes dos tipos dos elementos, e release fazia o mesmo.
Valor com __eq__ enganoso podia fingir done; igualdade lançando erro
escapava com estado inalterado, permitindo retry. Revisor não aprovou esse
estado inicial; ele não foi integrado ou executado com carga.

18 testes novos primeiro, **todos vermelhos**: seis combinações de igualdade
enganosa/que lança erro em marker e inventários;11 operações com exceção
inesperada injetada; assinatura inválida seguida de tentativa de retry.
Fix: tipos/comprimentos antes de igualdade, marker só chave/valor str exatos,
e wrapper closed em todas as operações públicas e construtor. ProtocolFault
mantém categoria fechada; erro inesperado fecha com SCHEMA/PROCESS, sem
cadeia, fora do except. Depois de ABORTED nenhum comando é devolvido.
Testes demonstram que __eq__ nem chega a executar e estado não volta.

Após fix e estilo dos testes: **177 focados/472 relacionados**, zero falhas/
skips/xfail; Ruff e format254 verdes, mypy strict3.11/3.14 em251 arquivos
verdes. Histórico159/454 preservado como medição anterior à revisão.
Uma correção E731 dos helpers foi feita sem relaxar gates. Rerevisão de
código/testes solicitada antes de qualquer integração. Nenhum Docker/caso
real, produtor ou recurso de memória foi iniciado nesta correção.

Rerevisão51ea0d85 confirmou B1 fechado, sem novo bloqueador/escape no wrapper
e sem overclaim no núcleo isolado. Nota de comportamento: BaseException
também converte KeyboardInterrupt/SystemExit em falha terminal; futuro
harness deve tratar interrupção fora dessas chamadas e manter watchdog.

Melhoria opcional do parecer aplicada depois com testes primeiro: duas
regressões de chave VM com hash/igualdade enganosa ou que lança erro deram
vermelho antes e verde depois. Agora facts checa chaves str exatas **antes**
de set/lookup. Resultado final **179 focados/474 relacionados** e mesmos
checks estáticos verdes. Só essa guarda e os dois testes mudaram depois
do parecer; conferência final concluiu sem bloqueador para o núcleo puro.
Continua sem produtor/execução.

## Fechamento local

Claude2 releu a guarda e os dois testes finais na sessão51ea0d85, sem
bloqueador no núcleo isolado. Não autorizou harness/integração/carga nem
executou testes: números/hashes são medições do executor. Não houve cota,
job novo ou outro escritor. Histórico da revisão bloqueante preservado.

Hashes finais:

- core384fe081261086b6437cd9b53b8afe76c72c97262855d9c6465a4488cf1c5b1c;
- teste5b81839711cb59b788d8cdc60d7f341bdb0823fb611939b3c0e1069a4689a295.

Próximo lote precisa produtor/coletor/harness e comando próprios revisados;
não há processo esperando PRESSURE. Fontes e artefatos das seis rodadas
anteriores e .venv/pyvenv.cfg permanecem iguais. Sem SQL/produção.

Auditoria final: baseline350 caminhos,354 no fechamento; seis documentos
existentes atualizados e quatro novos (protocolo, evidência, núcleo e teste),
zero ausentes e **zero src/produto alterado neste lote**. Mudanças anteriores
e arquivos pessoais preservados. git diff --check e whitespace dos novos
arquivos limpos; HEAD4a5e556 e origin/master em cache5d173ea continuam
0behind/1ahead. Sem fetch/escrita Git; zero processos Docker/Python ao fim.
Depois dos gates só documentação mudou; suítes não repetidas por isso.
