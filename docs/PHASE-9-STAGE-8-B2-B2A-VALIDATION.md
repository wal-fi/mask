# Fase 9 — Etapa 8 — B2-B2a: lacuna de seções compartilhadas

**Estado (2026-10-20): cinco controles executados uma vez, completos, cleanup
confirmado. Os quatro membros dos casos de seção mantiveram 40 MiB cada sob
cota privada de 32 MiB: `gap_observed`. Contenção de memória total NÃO provada.
Evidência revisada pelo Claude2, sem reivindicação acima do medido;
B-2, B-1 fim a fim e D-090 gate 2 abertos.
Nenhum SQL, worker operacional, commit, push ou deploy.**

## 1. Autoridade, revisão e escopo

Executado sob a delegação de 2026-10-20, conforme §7 de
`PHASE-9-STAGE-8-B2-B2-PLAN.md`. Não altera a reprovação histórica de 384 MiB,
os 12 excessos job-only do B2-A ou os critérios de produto. Não executou a
matriz de 16 pressões, controles de escape/breakaway ou morte do guardião.

Claude2 revisou plano, código e helpers somente leitura na sessão
`747e03db-22b5-4fbf-a719-de254e1e261c`, sem editar/executar. A primeira revisão
do código não conseguia ler os helpers externos; a rerevisão recebeu acesso
somente leitura à pasta exata com `--add-dir` e conferiu JOB_LIST, criação
suspensa, ausência de fallback/handles herdados, eventos auto-reset, ABI e
retornos. Foram corrigidos antes da execução: `ResumeThread == 1`, hashes
antes dos imports e nas cópias, classificação explícita de cobertura e registro
numérico publicado no offset zero. A rerevisão não encontrou bloqueador para
**somente os cinco casos**, não aprovou produto ou contenção.

Checkpoint preservado: `master`, HEAD
`4a5e5560abb495898c9e1b8ca44ac2d155681015`, referência local `origin/master`
em `5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind, sem fetch.
Lotes anteriores e arquivos pessoais não rastreados preservados.

## 2. Ambiente e execução

Windows build **26200**, CPython **3.11.3 x64** existente, páginas de 4 KiB,
estrutura de limites estendidos de 144 bytes. Sem recriar `.venv`, instalação,
banco, Docker, rede ou secrets. Guardião fora dos jobs próprios; job herdado
do host presente, cadeia de restrições não identificada nem contornada.

Raiz da execução: `%LOCALAPPDATA%\Temp\maskgw-b2b2a-20261020-482dd302\`.
Rodada única: `controls-7a32bd2e2784466bab67d58fb24d3265`.
Comando: Python existente com `-I -B`, script da raiz temporária, `--controls`.
Os três fontes foram arquivados antes dos casos; hash conferido antes de
importar, nas cópias e ao final. Sem `__pycache__` na raiz preparada.

Preflight observado: **18.553.745.408 bytes físicos** e
**20.181.417.984 bytes de commit** disponíveis. Limiares predeclarados:
2 GiB físicos/4 GiB commit. Até dois filhos por caso, payload intencional de
até 80 MiB coexistindo; 30 s por caso e watchdog independente de 120 s para
o lote. Não são cotas de produto nem mínimo contínuo do host.

## 3. Resultado completo

O código de saída foi **0**; `complete=true` significa diagnóstico completo,
não contenção aprovada. O próprio sumário registra
`production_gate_passed=false`; casos de seção registram também
`total_memory_contained=false` e `coverage=gap_observed` por membro.

| Caso | Membros | Observação | Cleanup |
|---|---:|---|---|
| job vazio | 0 | criado/configurado e vazio ao fim | confirmado |
| normal | 2 | ambos mantiveram `bytearray` de 1 MiB sob cota privada de 32 MiB | confirmado |
| sem cota privada | 2 | ambos mantiveram `bytearray` de 40 MiB; pico privado de 56.160.256 e 56.479.744 bytes | confirmado |
| SEC_COMMIT | 2 | ambos criaram/mapearam/tocaram 40 MiB de seção anônima sob cota privada de 32 MiB | confirmado |
| SEC_RESERVE + MEM_COMMIT | 2 | ambos criaram/mapearam/commitaram/tocaram 40 MiB sob a mesma cota | confirmado |

Nos quatro membros das seções: retorno válido de criação e map, commit
concluído, **10.240 páginas tocadas por membro**, nenhuma falha de alocação,
payload mantido até o ACK posterior à amostragem dos dois. Nenhuma view ou
handle de payload foi exportado a outro processo.

| Seção / membro | Privado no platô | Pico privado PSAPI = pico individual do job | Working set no platô |
|---|---:|---:|---:|
| SEC_COMMIT / 1 | 14.589.952 | 14.589.952 | 63.328.256 |
| SEC_COMMIT / 2 | 14.184.448 | 14.184.448 | 63.365.120 |
| SEC_RESERVE / 1 | 14.467.072 | 14.467.072 | 63.336.448 |
| SEC_RESERVE / 2 | 13.942.784 | 13.942.784 | 63.164.416 |

Todos os picos privados permanecem menores que **33.554.432 bytes**, apesar
das seções de **41.943.040 bytes por membro**. Isso demonstra neste perfil
que o limite privado sozinho não cobre esse vetor; não é prova de limite
físico/commit total. Working set não é rebatizado como commit privado.

O commit global observado por `GetPerformanceInfo` aumentou 83.886.080 bytes
entre os dois checkpoints de cada caso de seção. É dado complementar/ruidoso
do sistema; a coincidência com 80 MiB não atribui causalidade universal nem
substitui os retornos e checkpoints dos filhos. Não há contador agregado único
dos dois jobs, e a soma dos picos individuais não é pico simultâneo medido.
No controle sem cota, o aumento global foi 83.226.624 bytes, também ruidoso;
não se presume que deva coincidir exatamente com o payload.

## 4. Limpeza e integridade

**5/5 cleanups confirmados**, oito filhos, todos com exit code 0. Por caso:
espera pelos handles de processo, jobs vazios, eventos/mapas/handles fechados.
Auditoria pós-rodada: nenhum dos oito PIDs existia mais. Nenhum processo alheio
foi encerrado ou enumerado para exclusão. Sem cache de bytecode remanescente.
Não exercitou morte deliberada do guardião, `before_register` ou launcher.

Nove arquivos no lote (cinco casos, sumário e três fontes), **59.212 bytes**,
abaixo dos tetos de 64 KiB por caso e 4 MiB por lote. Fontes e sumário:

- `b2b2_controls.py`: `41c80c101becc1055ab28e5357f17b917c380c12a4101aeede1a19742d40fe67`;
- `native.py`: `92f8b3158eaa178972fbb7da3c694966a48ea1ac5647c35b333dc482fd97f797`;
- `winjob.py`: `b7183f44a630c7ccf65cb49922cd37d86760d6ec367cd3f168b283dc7d2de24c`;
- `summary.json`: `633ac755ded1c94f233e1b36938bec16188748e300635d9599fed821f9d4c0ad`.

Uma raiz preparatória anterior, `maskgw-b2b2a-20261020-a6ecb410`, guardou só
cópias de rascunho e executou apenas o selftest sem helpers/jobs/filhos.
Não foi rodada nativa falha nem é fonte da medição acima; foi preservada.

## 5. Gates proporcionais e interpretação

- Selftest puro do harness (inclusive registro de falha e teto de evidência):
  aprovado, sem import nativo/jobs/filhos/arquivos nesse modo.
- Ruff `E,F,I,B,UP` e format do harness: aprovados antes da execução.
- Regressões existentes de orçamento/snapshot/pureza/separação:
  **623 passed em 6,98 s**, zero falhas/skips; processo terminou com exit 0.
- Nenhuma suíte Python integral, PostgreSQL, frontend, browser, pacote,
  CPython 3.14 ou POSIX executado neste diagnóstico.

A matriz privada maior foi adiada: não resolve a lacuna de memória
compartilhada por si só. Antes da integração, escolher um contrato que cubra
alocações privadas **e** compartilhadas/nativas do caminho protegido, mais
custos proporcionais no pai. Não generalizar a partir de um único perfil nem
assumir que cota individual limita todo tipo de memória.

O resultado orienta a próxima arquitetura, não corrige um finding de worker
de produto (que ainda não existe). B-2, B-1 fim a fim e D-090 gate 2 seguem
abertos; SQL PGWire continua recusada com `0A000`. Sem commit/push/deploy.

## 6. Revisão dos resultados e fechamento deste diagnóstico

Claude2 leu o sumário completo e listou os artefatos, na mesma sessão citada
na §1, somente leitura. Conferiu cinco casos, oito PIDs distintos/exit zero,
flags, configurações, cobertura por membro, valores das tabelas e integridade
registrada. Não leu os cinco JSONs separadamente (estão embutidos no sumário),
não recalculou hashes/59.212 bytes nem refez a auditoria de PIDs; essas
verificações foram do executor. Concluiu que não há reivindicação acima do
medido. A observação de commit global do controle sem cota foi incorporada.

Fechamento do registro sob delegação, não aprovação individual inventada nem
certificação de memória total. A revisão recomenda o próximo lote puro e
multiplataforma: representação/validação limitada de resultados em bytes no
pai, com decisão explícita de formato, custo e ownership antes do código.
Cobertura compartilhada/nativa do worker continua como gate separado.
