# W1 instalado na candidata Oracle9.8 — rodada v2

Execução em2026-10-27; captura/rechecagem de artefatos em2026-10-28.
Sob delegação. Código b59388f5, estadoa19394f9 e comando9c6b4996 revisados
pelo Claude2 antes de uma invocação. Não repetir a raiz consumida. A tentativa1
NOT_PASSED e sua recuperação c1351f16 permanecem como histórico íntegro.

## Resultado observado

Exit0/ORACLE9_W1_CANDIDATE_VERIFIED, instalação8,75s e sonda4,641s. Nova imagem
local, mantida sem push e ainda sem uso fora da sonda:

`sha256:621cc7f702ec34d7014809411fda7fc89ab6b95f6dc7d16315274d4a7006ef0b`

Tag `maskgw-oracle9-w1-candidate:b03f575e731b4611928433cabafa7197`.
Oracle Linux9.8/Python3.11.13, origem87871290+um layer
d399fb14a284e2521af70760de97ba618673e09cf8a1d076220a913d374b766e.
Config inteiro e4labels conformes; label público de apresentação foi declarado
no commit. Ambos CIDs medidos têm exatamente os3labels próprios, inclusive
o probe: o risco residual de herdar um label extra não se materializou.

W1 veio do wheel6b63f239 (448821bytes), contexto d4d4b29b e payload566c46a8,
sem copiar checkout ou fontes avulsas. Atualização offline somente do app:
prefix3332→3337,5paths novos/0removidos/3alterados; outros owners/bytes/modos/
UID/GID e base.pth iguais.39versões preservadas (37wheels+2tools vendor),
RECORD/pip-check e5assets verificados no Linux. L3 real:155linhas,149C/6A,
sem D; não foi necessário relaxar o validador para nova forma.

Importação dos5módulos W1 via Python-I-B no pacote instalado fora do checkout
passou na instalação e na sonda. session_state já estava carregado pelos
imports antigos e consta em preloaded; não inventar prova de import fresco
desse módulo sob os guards. Nenhuma query/conexão upstream ou worker iniciado.
Sonda UID/GID10001, read-only/networknone/caps0/NNP/seccomp,512MiB/swap0,
pids32/CPU1/nofile128/core0/tmp16MiB/shm8MiB, diff vazio. Installer root0,
perfil correspondente de preparação/tmp64MiB. Não é perfil de consulta.

## Ciclo e cleanup

12checkpoints xb completos,124656ms A→B, mesmo boot134372287595000000.
Replay independente no host em28/10 refez START/9OBSERVE/READY/B usando
o core congelado e comparou encodes/ordem/cadeia; bate com cycle.json.
Head d1b2e7f6d765b566a868baccf44d8a091b03898124e07862b0dcebbd77b97a8e.
Resultado journal_verifiedtrue e12checkpoints. Diferentemente da tentativa1,
todos os intervalos intermediários estão preservados, sem reconstrução fictícia.

50comandos registrados, todos exit0:35DockerCLI e15chamadas do controlador
PowerShell (o sampler tem chamadas próprias). Dois CIDs próprios removidos:

- install3e867ec57b852d173df6f61fd06c04d6977d4bb373438d43a519b1e9e5df92f0;
- probe2c76729ab99c6e1d2ac82716d7b5fe0b99d0f7258017ccebda9f05d81cb3cc23.

Ausência por CID e inventário global vazio exit0. Desktop iniciado pelo lote,
PID8896/FILETIME134375857978266391, foi revalidado antes do stop13,375s/exit0;
ausência de processos confirmada. owned_cleanup/inventory_restored/
desktop_restored/inputs_unchangedtrue, watchdogfalse, OFF_CONFIRMED.
Em28/10, nova leitura de processos confirmou0, sem DockerCLI adicional.

## Transporte e rechecagem

36arquivos/2236940bytes copiados sem transformação para
`docs/poc/evidence/oracle9-w1-v2-run-20261027/`. Manifesto de transporte SHA
e257a5361db7bd70ea6041b9b159dfa192b190ffdc693f888d614c43342b5545.
Atestação instalada1965244bytes/SHA
f0c3cd547d333fd6c7783800e868c5fc85a96eabf1e4897647154d591f4ad863.
ResultSHA a5e16d5bddc94cc24a0502baf549794a178dcbab241f6efc8988ccd4c0283969.

Rechecagem host somente leitura confirmou atestação/origem/projeção W1/L1,
Config/camadas/labels de imagem e155linhas L3 com os mesmos validadores
congelados. Atestação/manifesto são evidência do payload executado; o replay
lógico não cria autenticidade externa nem mede novamente o SO.

## Limites e próximo gate

Não libera worker/SQL/IDE/MCP/Admin operacionais, B-1 fim a fim, B-2,
D-090 gate2 ou C1. Ainda não há serviço disponível. Esta candidata é insumo
de integração; patches/minimalização de dependências permanecem gate antes
de release (OpenSSL sistema3.5.8/crypto4.0.2/psycopg3.5.4, pip/setuptools/.pth).
Sem DB existente/credencial antiga, porta externa, commit/push/deploy ou job.

Resultado segue para revisão somente leitura antes de usar a candidata em
prova W1 com PostgreSQL16 descartável/isolado, dados sintéticos e plano próprio.
Não repetir preparação, instalar de novo ou iniciar outro escritor.

Revisão final em28/10: Claude2 aceitou fatos e candidata621cc7f7 como insumo
fixo para o desenho da prova W1/PG16, sem certificar worker/consulta/gates.
O revisor conferiu coerência de manifesto/artefatos, sem recalcular SHAs em
shell. Recomendações externas não criam aprovações individuais ou política
corporativa nova; os gates técnicos já registrados permanecem vigentes.
