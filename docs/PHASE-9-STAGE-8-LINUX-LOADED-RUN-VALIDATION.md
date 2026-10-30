# loaded-as128 — rodada real com imports completos

**2026-10-22 — executada uma vez; registro revisado sem bloqueador.**
Sob delegação vigente, não aprovação individual fictícia. Não fecha B-1 fim
a fim, B-2 ou D-090 gate2 e não libera SQL/produção. AS32 e seis rodadas
anteriores preservados, sem reclassificação ou ampliação retroativa de cotas.

## Procedimento e execução

Código/protocolo e plano LOADED-RUN-PLAN revisados pelo Claude2, sessão
51ea0d85. A1 impediu executar -c frágil do PowerShell5.1: antes de qualquer
DockerCLI, programa gravado por apply_patch fora do checkout, hash conferido,
helper absoluto/hash interno e comandos exatos. Rerevisão fechou A1/R-A2/R-A3,
condições C1/cwd próprio e C2/hash do programa cumpridas. Revisor não executou
os comandos. Oito simulações finais passaram; falhas anteriores do harness
e causa medida de aspas estão preservadas no plano, sem tentar version real.

Desktop já ativo desde09:26, processos UI/backend iguais antes/depois; não
iniciado nem parado por este lote. CLI/config/contexto/endpoint named-pipe
local/10 fontes/programa/tree reconferidos antes de A e B. Sem download,
instalação, build, Docker exec ou alteração de ambiente/configuração.

A: uma chamada externa version5s/16KiB, READY, exit0,0,437s, engine29.7.2
linux/amd64. Registro lido e validado em outra chamada **antes** de B.
external.json.observer_invoked=false é o snapshot pré-invocação, não o
resultado global: B foi posteriormente executado exatamente uma vez.

B: .venv existente/Python Windows3.11.3, -I -B e --run, cwd próprio.
Preflight interno obrigatório também passou:1 poll READY, cleanupCLI=true,
ps global vazio e imagem pinada inspecionada antes de create. Árvore parcial
e fontes verificadas pelo Observer, depois a cada admissão e ao final.
Mesmos limites revisados:30s/caso,120s/lote,20s internos, AS128 para privado/
shared; defesa externa192MiB/swap0/CPU1/pids16/shm1MiB/nofile64/core0,
UID65534/NNP/capdropALL/rede none/mounts RO. Sem banco/conexão/SQL/policy.

## Resultados, sem inferir memória total

| Campo | Controle | Privado128 | Compartilhado128 |
| --- | --- | --- | --- |
| Outcome | control_ok | imposed | imposed |
| Tempo externo do caso |5,532s|5,187s|5,172s|
| AS do supervisor/membro |ilimitado|134.217.728|134.217.728|
| Inventário completo |467 linhas|467 linhas|467 linhas|
| Observações independentes |12|9|9|
| VmSize pré-pressão |112.058.368|112.058.368|112.058.368|
| VmPeak no platô |154.042.368|133.050.368|133.029.888|
| VmSize no platô observado |154.042.368|130.953.216|130.932.736|
| Pico cgroup |141.041.664|96.358.400|95.805.440|
| Eventos max/oom/oom_kill |0/0/0|0/0/0|0/0/0|
| Membro/container exit |0/0|0/0|0/0|
| Inventário final do supervisor |[1]|[1]|[1]|
| Cleanup membro/container |true/true|true/true|true/true|

Sumário: complete=true, diagnostic_success=true, total_memory_contained=false,
not_executed=[], elapsed25,671s, deadline_exceeded=false, watchdog_closed=true,
inventory_restored=true; exit do observador **0** conferido. Sem retry/segunda
invocação ou caso extra. Todos sources/tree/runtime/raw_unchanged=true.

Os três inventários foram descomprimidos pelo decoder limitado e comparados
linha a linha; iguais,467 cada, com digest único recalculado:
`1d25ea3c8b9b85388ac7482f28a4f1feae6641ea484406756052ac5047d48c74`.
O digest do controle deste lote foi admitido **antes** da pressão de cada128
pelo protocolo hashado. Não se reaproveitou o inventário465 da rodada AS32.
Imports cumulativos db.postgres/runtime.snapshot/pgwire.result_encoder,
auditoria de origem/efeitos e native_check completos, não execução de query.

Controle:40MiB privado retido, descartado antes do compartilhado. VmSize
154.042.368→112.058.368; anon do cgroup100.220.928→58.236.928, queda
41.984.000>=32MiB. Cumpriu descarte sem relaxar critério/teto ou malloc_trim.
Depois compartilhado40MiB: VmSize154.001.408, shmem41.943.040→0 após liberar.
Nos128, o supervisor classificou imposed somente após validar a resposta
fechada de recusa/ao menos um bloco retido e confirmar pico independente,
limite e lifecycle. **O raw final não persiste a linha HELD nem categoria/
errno/número exato de blocos do membro**; não apresentar tais detalhes como
recalculados diretamente destes JSONs. A conclusão depende também do código
hashado/revisado que validou essa linha, não só do marcador outcome do raw.
Observação compartilhada128: shmem20.971.520 no platô e0 após liberar; não
chamar isso sozinho de prova de recusa no alocador. VmPeak não é RAM.

Leitura real dos fds/readlinks do filho nos pontos estáveis foi possível
neste perfil: [0,1,2,3], fd3 do sampler próprio, proc_children_available=true.
Observações transitórias entre imports têm fds=null conforme desenho S1,
não uma coleta estável inventada. Não se adicionou CAP_SYS_PTRACE ou fallback.

Não houve saturação deliberada dos192MiB; seus picos/eventos não certificam
imposição externa. Não testa falha nativa interna de libpq/pglast/Rust/TLS,
consultas/AST/masking reais, concorrência, gerações, saída ou custo do pai.
Não certifica Windows/Jobs nem Linux de produção;128MiB não é default.

## Artefatos e integridade

Originais fora do checkout, preservados sem edição:

- rodada: `%LOCALAPPDATA%\Temp\maskgw-loaded-as128-20261022-phrueydi`;
- externo: `%LOCALAPPDATA%\Temp\maskgw-loaded-external-20261022-s2f890fv`;
- programa: `%LOCALAPPDATA%\Temp\maskgw-loaded-command-20261022-1b49c2ad`.

O processo imprimiu os mesmos caminhos via alias8.3 WA2E4~1.FIL; o caminho
longo w.filho foi usado nas leituras seguintes. Rodada reteve20 arquivos/
266.355 bytes (não é a soma contabilizada das regravações). Cada raw<64KiB,
cap de1MiB aplicado pelo observador; nenhum truncamento para aprovar parser.
task=loaded-as128-70fce744e6dd4a3fa75d1687fe8e7da6, bundle das10 fontes:
`32b8ac751d6b0b0f697c60ec83e60e88a4eb7e79fdc06d1a7bf1f0cf58fce7f0`.

| Original | SHA256 |
| --- | --- |
| summary.json |30545f1a6c6bf1aa94d0daa346aaba839be17eb25dc75ed3cd42d81dfcc8ec29|
| external.json |c84ad0dcc6f215cde003259722a025e16340afa9d5d7fe6e105105effa830037|
| runtime.json |dc5f7e5ab500a708dd67bda6164bd02b26a00e2d4481da7e9e57ac7f4b1dc5d1|
| control-diagnostic.json |acc9e36ab912a324ba0bac30b130ddf393615cb8992ea4c88382eafe028700ee|
| private-diagnostic.json |1ba307897f059b2afb266af70ce0ed1b3b58fc2f783cccf3b588de661ab45714|
| shared-diagnostic.json |4dda2dfa8a32959a844e691d9038de4f21bc9c078eb388f2f0a38af800e07a3f|

Cópia de revisão `docs/poc/evidence/linux-loaded-as128-20261022.json`,
12 arquivos parseados com SHA/tamanho original e três inventários completos
descomprimidos.271.579 bytes,<1MiB; não é um raw de caso nem artefato sujeito
ao teto64KiB do canal. SHA:
`c9c45157c7bac80efaf6806c3f56c42d84a65a019a3673ad528f6b4cff3dfeb3`.
Hashes e bytes atestados pelo executor contra originais; revisor só terá
cópia no checkout, não se atribui a ele recomputação que não executou.

Containers próprios removidos pelo lifecycle, identidade task/bundle/ID:

- control:7f42cdf958074ac844950137f2d90157ffe21921a58e3cb32bfe872d1862a18b;
- private:918321788b4bad9bee094992bfc840e97811bde85df89b2b9821aea0b6fb4aae;
- shared:3e78d9a1320ace273cf8a21b012c763734ff89c16ac55dd3dad63c142811d492.

pending final phase=removed do último ID; ps final global vazio pelo host.
Não houve limpeza de recurso alheio, start/stop do Desktop ou Docker exec.
Código/testes/produto congelados; neste lote só plano/evidência/cópia de
revisão e documentos de estado. Não repetir suítes PG16/frontend/pacotes
sem mudança funcional; resultados anteriores não rotulados como novos.
Sem fetch/commit/push/deploy ou outro escritor. Próximo gate: revisão desta
evidência antes de decidir incremento posterior de contenção.

## Revisão final e qualificações obrigatórias

Claude2, sessão51ea0d85, somente leitura da cópia no checkout: sem bloqueador
para registrar diagnóstico por processo após imports. Não executou código
nem atestou hashes/bytes dos originais. Conferiu consistência do sumário,
casos, preflight, aritmética de descarte/reserva, sequência e limites.

- Q1: imposed depende da validação pelo supervisor hashado; a linha HELD não
  está no raw. **Próximo desenho deve persistir a linha HELD validada<=1KiB**
  no raw para rechecagem independente, sem alterar retrospectivamente esta
  rodada. Não inventar categoria/errno/blocos a partir de VmSize/shmem.
- Q2: uma imagem/kernel e árvore parcial, somente imports; não trabalho
  nativo sob falha, consultas, pai, saída, concorrência, gerações ou domínio
  externo saturado. Não certifica Windows/Jobs nem Linux de produção.
- Q3: fd/readlink reais funcionaram neste perfil, não prova portabilidade.
  Outro perfil pode negar acesso e deve falhar fechado, sem relaxamento.

Nenhum gate B-1/B-2/D-090 fechado, nem SQL/produção liberados. Plano consumido;
qualquer novo ensaio exige desenho/comando/revisão próprios sob a delegação.
Sem nova cota observada ou retomada necessária. Revisor encerrado, não há
segundo escritor ou tarefa armada por este lote.

## Auditoria do fechamento

Baseline368 caminhos; somente seis documentos de estado existentes mudaram,
mais três novos: plano, esta evidência e a cópia JSON. Zero src/teste/helper
alterado, fontes congeladas/core/produtor/coletor/supervisor/host e
.venv/pyvenv.cfg iguais ao baseline. Nada anterior ou pessoal removido.
Programa externo1923bytes/hashbbceb94b..., criado via apply_patch e testado
com fakes antes da tentativa; diretório temporário próprio preservado.
GitHEAD4a5e556, origin em cache5d173ea,0behind/1ahead; sem fetch/escrita Git.
Diff e whitespace dos novos limpos. Depois da rodada/revisão só documentação
mudou; nenhum gate antigo foi reapresentado como execução desta rodada.
