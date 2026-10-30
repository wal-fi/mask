# W1 — invariantes privadas da sessão PostgreSQL (S1)

2026-10-26, sob delegação. Hook isolado revisado pelo Claude2, sem chamador
ou consulta real. Novo db/session_state.py e método privado
PostgresAdapter._worker_session_state; connect/execute/_run legados não
mudaram. O novo import não executa SQL/ambiente/segredos em módulo.

Consulta fixa25campos de metadata, funções/operadores/tipo explicitamente
pg_catalog, CURRENT_USER/SESSION_USER intrínsecos. Identidades, search_path
e schemas efetivos, ausência pg_temp/advisory/LISTEN, parâmetros readonly,
timeout/formato/encoding/isolamento/row_security, backendPID/database e seis
parâmetros adicionais de formato recomendados na revisão. Sem SET/DISCARD,
reparo/reconexão ou retorno desses valores ao pai/clientes/logs. Mudança
legítima externa de schema também pode encerrar conservadoramente.

Baseline opt-in do worker exige readonly padrão/atual on, UTF8,
row_security/standard_conforming_strings on, sem temp/locks/canais. Registro
imutável/arrays desanexadas/repr privado/eqFalse; até64schemas/8KiB por campo/
64KiB total. O limite é de validação **depois do fetch**: AS/cgroup continuam
obrigatórios para o fetch/libpq, sem prometer limite prévio nativo.

Hook exige saúde antes/depois e exatamente uma linha, fecha cursor e zera
referência à linha antes de sair. Erros fixos lançados fora do handler, sem
cause/context/drivertext; MemoryError propaga para falha fatal de recurso.
Loop futuro deve guardar baseline antes de OPENED e conferir antes/depois
de sucesso ou erro recuperável, no mesmo prazo, sem enviar antes do S1.
Fatal já encerra, sem I/O extra para tentar recuperar.

**59testes novos;908relacionados aprovados** no Windows3.11.3. Fakes somente,
sem PostgreSQL/DSN/SQLreal. Ruff e mypy strict3.11/3.14 no escopo3arquivos
limpos. Primeira rodada47testes com19campos; recomendação adicionou6campos,
6mutações,5contraprovas de mutadores diretos no validator e uma prova de
que UDF comum continua aceita (risco D-027). Não afirmar que toda função
com efeito colateral é recusada ou que todo estado do servidor é auditado.
Preparação automática do psycopg permaneceu intacta, sem contagem genérica
de prepared statements que causaria falso positivo. PREPARE/EXECUTE/
DECLARE/SET/set_config diretos são recusados pelo validador existente.

Revisão inicial do Claude2 aceitou19campos sem bloqueador; revisão final
aceitou o delta25campos como base fixa. Obrigações do loop/owner preservadas.
Pins:
- session_state.py 5aa4d4534fd07fe5601846dba7fa558a075b9c5e1e213da7f28daab9c1fc9f2e
- postgres.py e9773331fbcdc1c90fcc25adbccf6ff3bd90db3a8cb1ae56c23011c683a4dbb
- test_worker_session_state.py ce44cb1a2fe32ab3c689cc445caaad948eb63e95a291b4f7b2410418dffbc8f4

O postgres.py recebeu apenas o import e método opt-in desde o último lote;
o pin do app instalado87871290 antecede esse método. Novo wheel e prova
PG16 terão ciclo próprio. D-120 durante A–Off manteve seus119fontes antigos
intactos; este delta posterior não reescreve aquela medição. Nenhum Docker,
DB existente, segredo, rede, alteração de dependência, commit/push/deploy
ou job novo. B-1/B-2/D-090/C1/SQL permanecem abertos; DesktopOff.
