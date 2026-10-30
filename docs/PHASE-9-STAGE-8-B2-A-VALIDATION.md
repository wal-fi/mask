# Fase 9 — Etapa 8 — B2-A: diagnóstico temporário Windows

**Estado (2026-10-19): diagnóstico executado e revisado tecnicamente;
registro aprovado explicitamente pelo usuário em 2026-10-19.
Seis controles e 36 casos concluídos, limpeza confirmada. O pico excedeu o
teto nos 12 casos job-only; não é gate de contenção aprovado. Não fecha B-2,
B-1 fim a fim ou D-090 gate 2. Sem produto, SQL, commit/push ou produção.**

## 1. Autorização e checkpoint

O usuário autorizou criar o harness temporário e executar somente B2-A após
revisão do Claude2, conforme §4 de
[PHASE-9-STAGE-8-B2-PLAN.md](PHASE-9-STAGE-8-B2-PLAN.md).
HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`; referência local
`origin/master` em `5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0
behind. Sem fetch, commit, emenda ou push. Freeze próprio: **439 arquivos**,
distinto dos freezes das etapas anteriores; alterações preexistentes preservadas.

Raiz temporária nova, fora do checkout:
`%LOCALAPPDATA%\Temp\maskgw-b2a-20261019-311a869add584820b5298206798d3a6c\`.
Ambiente existente: Windows nativo, CPython **3.11.3**, pywin32 já instalado;
sem instalação ou alteração da `.venv`. Probes sem `maskgw`, PostgreSQL,
Docker, rede ou dados/chaves reais. Os parâmetros são experimentais, não
defaults do produto.

## 2. Revisões anteriores à execução

Claude2 revisou somente leitura os scripts `harness.py`, `native.py` e a
cópia privada do helper `winjob.py`. Um bloqueador de evidência foi corrigido
**antes** dos testes: estouro de relatório poderia impedir a contabilidade
de caso incompleto e dos restantes não executados.

O teto não foi elevado: o relatório agora compacta campos numéricos por
tabelas explícitas. Se ainda exceder o teto, mantém prefixo marcado como
parcial, registra a perda e encerra a matriz. Selftest verifica igualdade
exata após compactar/expandir e recusa com evidência truncada para uma
fixture sintética de 128 amostras. **Selftest: exit 0**, sem criar job ou filho.
Não é um codec de resultado do gateway.

Também foram tratados, somente no harness: ambos os contadores da lista de
PIDs, retorno/código da tentativa de `TerminateJobObject` e distinção entre
liberação ao alocador Python e `MEM_RELEASE`. O fechamento explícito do
`subprocess.Handle` foi conferido no `subprocess.py` do CPython instalado:
`Close()` é idempotente e marca o objeto antes de fechar o handle do SO.
Claude2 retirou a observação de fechamento duplo após essa conferência.

## 3. Preparações incompletas, sem pressão

Todos os caminhos abaixo são relativos à raiz temporária. Cada sumário
registra os hashes dos scripts daquela revisão. Não houve aumento de cota,
reclassificação como aprovado ou execução de casos de pressão nessas rodadas.

| Rodada | Resultado | Limpeza |
|---|---|---|
| `run-c74c3cc7a2244c13b4c3f414a8c63150` | Job vazio completo; controle normal de 4 MiB incompleto por `PermissionError` 13; 40 casos restantes não executados | Confirmada |
| `run-f02f63a15b4f41d4a51f47962dd1618c` | Job vazio e normal completos; recusa incompleta por `TypeError`; restante não executado | Confirmada |
| `run-d0b00d84f9a4481780867fded8432e48` | Job vazio e normal completos; recusa incompleta por `PermissionError` 13 na abertura de `launch.json`; restante não executado | Confirmada |

O `TypeError` era do próprio harness: handle ctypes da contraprova de acesso
reduzido passado para `os`/`subprocess`, que exigem inteiro. Corrigido com
`.value`, sem dar mais acesso ao handle, alterar o negativo ou enfraquecer
a verificação de identidade/associação.

A instrumentação posterior registra só nomes de arquivo/função e linhas,
sem mensagem original, argumentos, fonte ou variáveis locais. Ela localizou
o erro de abertura em `pathlib.read_bytes` do metadado de startup. **Não foi
comprovada causa externa** (antivírus, compartilhamento, rename ou outra).
O primeiro erro, sem esse rastreio, não recebe atribuição retroativa.

O canal de startup foi trocado, somente no harness, por registro numérico
fixo no offset 128 do mapeamento de 4 KiB já usado; os checkpoints do filho
continuam no offset 0. Evento exclusivo publica o registro antes de o
guardião conferir identidade/associação e autorizar retomada. Claude2 revisou
essa alteração somente leitura, sem apontar bloqueador, **antes** da execução
final. Nenhum caso de pressão foi executado nas preparações incompletas.

## 4. Matriz final medida

Rodada `run-37592d48051e4e099afb870ddffbd9aa`, Windows build **26200**,
processos de 64 bits, estrutura de limites estendidos com **144 bytes**.
CPython 3.11.3; mesmos parâmetros aprovados. Selftest novamente exit 0 antes
do lote. Execução: **42/42 casos completos**, **23,156 s**, exit 0 do harness.
O código de saída significa diagnóstico completo, **não** aprovação de teto.

Seis controles concluídos antes da pressão: job vazio, normal de 4 MiB,
recusa de handle sem direito de atribuição (código 5, nenhum filho), morte
do launcher antes de criar, após criar suspenso e após retomar. Nos dois
últimos casos, o guardião encontrou o membro por conta própria e confirmou
o término após fechar o último handle do job.

As 36 pressões foram **uma execução da matriz** de três perfis × dois
alocadores × dois passos × três repetições, não tentativas até obter verde.
Payload pedido de até 40 MiB, um filho por vez. Cota ativa: **33.554.432 bytes
(32 MiB)**. Não se subtrai baseline nem se acrescenta tolerância ao pico.

| Perfil | Casos | Menor pico do job (bytes) | Maior pico do job (bytes) | Observação estrita |
|---|---:|---:|---:|---|
| Só limite de job | 12 | 33.648.640 | 36.487.168 | **12/12 excederam** o cap do job; limite individual desligado |
| Só limite individual | 12 | 31.707.136 | 33.509.376 | 12/12 picos individuais dentro de 32 MiB; job sem cap |
| Ambos os limites | 12 | 31.670.272 | 33.382.400 | 12/12 dentro dos dois caps, somente neste perfil medido |

Neste ensaio de um membro, os picos reportados de processo/job nas consultas
de job coincidiram. Não se usa soma de picos individuais para provar agregado.
Os 18 casos Python registraram falha no `except MemoryError`; os 18 nativos
registraram retorno nulo de `VirtualAlloc` e código **1455**. Recusa de
alocação, por si só, não é aprovação da contenção.

## 5. Sequência observada, sem conclusão causal universal

Nos 12 casos job-only, o primeiro checkpoint arquivado com pico acima do cap
foi `after` de uma tentativa marcada como recusada. Exemplo nativo de passo
4 MiB, `job_only-native-4-1`:

| Marco | Payload confirmado | Commit privado atual (`PrivateUsage`, PSAPI) | Pico do job (`PeakJobMemoryUsed`) | Pico de commit (`PeakPagefileUsage`, PSAPI) |
|---|---:|---:|---:|---:|
| Antes da quinta tentativa | 16.777.216 | 32.206.848 | 32.206.848 | 32.206.848 |
| Depois da tentativa recusada, código 1455 | 16.777.216 | 32.206.848 | 36.401.152 | 36.401.152 |

O `PeakProcessMemoryUsed` consultado no job também coincidiu nesse exemplo,
mas a flag de limite individual estava **desligada**: existência do contador
não significa cota individual ativa. A consulta PSAPI distinta corrobora os
valores observados, não prova uma explicação causal independente.

O payload e commit **nos dois marcos** permaneceram iguais; o pico reportado
subiu 4.194.304 bytes. Isso estreita a observação, mas **não** prova qual
mecanismo interno gerou o pico nem exclui estados transitórios dentro da
chamada. Não se declara contador inválido, bug de Windows ou inexistência de
excesso real em todo instante. A asserção histórica continua **FAIL**.

O resultado torna a cota individual candidata a estudo separado; não é
contrato alternativo aprovado, certificação de múltiplos workers ou solução
da memória do pai. `host_job_inherited=true`: o guardião já pertencia a um
job do host; suas restrições não foram identificadas nem alteradas. Não se
forçou breakaway e não se atribui o resultado exclusivamente a uma cota.

## 6. Limpeza, limites de evidência e rastreabilidade

Auditoria pós-lote somente leitura: **zero processos Python vivos desta raiz**;
39 identidades de filhos registradas, todas com término confirmado. São os
36 probes de pressão mais o controle normal e os dois controles de morte
com filho; vazio, recusa e morte antes de criar não geraram filho.

- **42 casos com cleanup confirmado**, zero notas de erro, zero evidências
  truncadas e zero amostras com divergência de binding/configuração.
- Máximo de **44 amostras** e **19.712 bytes de artefatos por caso**, abaixo
  de 128 amostras/64 KiB. Total do lote, incluindo fontes: **644.814 bytes**,
  abaixo de 4 MiB.
- Menores preflights **arquivados por caso**: 16.940.007.424 bytes de física
  disponível e 13.239.619.584 de commit disponível. Não são mínimos contínuos
  do host; o monitor amostrado não é contenção física universal.
- Os três scripts da rodada final foram copiados para `sources/` antes dos
  casos; hashes dos fontes continuaram iguais até o fim. As três preparações
  falhas guardam hashes e artefatos, mas suas revisões de fontes anteriores
  não foram arquivadas como cópias completas: limitação de rastreabilidade,
  não apresentada como prova reproduzível de produto.

SHA-256 da rodada final:

- `summary.json`: `f5fdef25d1f4a35999685c8aaed2a98cbc2cd5d65e5e0dd5d678c91b75507bab`;
- `sources/harness.py`: `0a0a79fd543102a5b6227baa04c5e61fdaab2aac31f4999b0863e1b4fcb41b61`;
- `sources/native.py`: `92f8b3158eaa178972fbb7da3c694966a48ea1ac5647c35b333dc482fd97f797`;
- `sources/winjob.py`: `b7183f44a630c7ccf65cb49922cd37d86760d6ec367cd3f168b283dc7d2de24c`.

## 7. Revisão final e exclusões

Claude2 concluiu revisão somente leitura dos resultados e desta evidência,
sem bloqueador para registrar o diagnóstico. Conferiu integralmente o caso
nativo da §5 e amostrou o restante; não executou testes nem refez toda a
agregação. As contagens completas foram conferidas pelo implementador.
O FAIL agregado histórico de 384 MiB permanece intacto e não foi reexecutado.
Todas as medições se limitam aos processos sintéticos, não ao produto.

Nenhuma suíte integral, pacote, browser, PostgreSQL real, CPython 3.14 ou
POSIX foi executado neste incremento. Não há memória do pai real, decoder,
ledger global, fetch, transação, proveniência ou worker integrado comprovados.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos; SQL continua `0A000`.

Fechamento exclusivamente documental após os testes e auditoria. Contra o
freeze de **439 arquivos deste lote**, mudaram seis documentos existentes e
esta evidência foi adicionada; nenhum arquivo removido. `src`, `tests`,
dependências e `.venv/pyvenv.cfg` continuaram com os mesmos hashes, inclusive
as alterações preexistentes. Os fontes temporários medidos e arquivados e
o relatório antigo também permaneceram iguais. UTF-8 estrito, whitespace e
`git diff --check` conferidos; nenhuma suíte foi repetida por essas edições.

## 8. Aprovação do registro

Em 2026-10-19, o usuário respondeu **"aprovo"** à apresentação do diagnóstico
revisado. O aval é do registro desta evidência, não da contenção de produção
nem de um contrato alternativo de memória. Resultados, falhas, limites e
conclusões das seções anteriores permanecem inalterados.

B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos. Não foram autorizados
novos lotes, implementação de produto, worker integrado, SQL de cliente,
commit, push ou produção. O registro desta aprovação alterou somente os
documentos de estado e esta evidência; nenhuma suíte foi repetida.
