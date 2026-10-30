# Etapa 8 — restauração do caminho de aceitação anterior ao guard de nome

**2026-10-21 — correção revisada; terceira rodada inconclusiva, causa nomeada.**
Plano separado: `PHASE-9-STAGE-8-LINUX-IMPORTS-NAME-PLAN.md`.
Segunda rodada permanece inconclusiva e preservada, com fontes e17f.../6a44...
em `PHASE-9-STAGE-8-LINUX-IMPORTS-OBSERVABILITY-VALIDATION.md`. Nenhuma
tentativa foi relabelada como verde. Produto e regras de origem intactos.

## Revisão, regressões e limites

Claude2 revisou somente leitura plano/evidência e depois código/testes na
sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, sem bloqueador. Permitiu uma
rodada identificada, sem mudar códigos depois da medição antes de revisá-la.
Dois testes falharam antes da correção: linha exata da stdlib com hífen e
tratamento de nomes das429 linhas antigas já aceitas. O segundo mocka
module_row para isolar apenas o novo guard, não prova origem de429 módulos.

Removida apenas a condição valid_module_name anterior a module_row; quem
decide aceitação é a mesma política de origem/owner/atribuição da primeira
rodada. A gramática de nome continua só no campo do erro; se inválido,
null/OTHER. Limitação aceita da medição: isso perde a categoria específica
do erro com nome inválido; não foi ampliada reflexão nem adicionado hash.
As regressões de erro usam arquivo fora de origem para gerar erro real,
não apenas nome diferente da gramática. Sem fallback de atribuição.

**156 passed** relacionados; Ruff src/tests e E/F/I/B/UP dos PoCs verdes;
format249 arquivos e mypy strict alvos3.11/3.14 em247 arquivos verdes.
Não é runtime3.14 medido, suíte integral PG16, pacote ou frontend.

Fontes para a terceira rodada (nunca atribuídas às duas anteriores):

- probe: `9fd5cdc6ec81e36abdfa71c2d7b82561d36c903cdbb71858b620bb3a4016a7a3`;
- observer: `6a446e5fad7752e6527f17d9a6e542fee4792293d20233b9cbe77bc956f59fa3`.

Mesma imagem, árvore preparada e limites; controle primeiro, AS32 somente se
normal, um caso de cada no máximo. Qualquer diagnóstico para sem AS32. Não
é aceitação B-1/B-2/D-090, worker/SQL ou produção. Desktop está desligado
antes da rodada; será restaurado, com cleanup próprio por ID confirmado.

## Terceira rodada identificada — resultado

Raiz `%LOCALAPPDATA%\Temp\maskgw-linux-import-run-20261021-d62jdwsm`;
container único `48b817c1bee726cceafb0f565bce37b09f967131ec733742fc886c8edd6f9aea`.
Sem novos downloads, instalação ou mudança de fontes depois do início.
Preflights aprovados: Docker29.7.2/Linux/amd64, inventário vazio, mesma
imagem oficial em cache. Controle5,422s, lote5,797s; Python exit2 medido;
container exit0. **Inconclusivo**, imports_fit_as32=false e AS32 não rodou
(limited.json ausente); não houve repetição do caso depois desse resultado.

Membro exit75, diagnostic_failure=AUDIT_ERROR, evento coletado:

```json
{"phase":"audit_error","stage":1,"module":"_openssl","category":"FILELESS_UNATTRIBUTED","has_file":false,"under_installed":false}
```

Isso identifica uma falha da auditoria em atribuir o módulo sem arquivo,
não falha do import ou de memória. Snapshot retornou antes do laço da
auditoria. Não prova a causa da primeira rodada, embora a interrupção seja
no mesmo ponto do delta após `_cffi_backend`. Nenhuma atribuição nova foi
aceita, nenhum módulo legitimado apenas pelo nome.

Inventário429 linhas (77baseline/351etapa0/1etapa1/0etapa2). Etapa0 tem
end; etapa1 start sem end, etapa2 não iniciou; sem native_check final.
O módulo da stdlib com hífen voltou à mesma linha aceita na primeira rodada.
Etapa0: VmPeak101.130.240 bytes (espaço virtual, **não RAM**), VmSize97.644.544,
VmRSS59.887.616, uma thread e fds[0,1,2], proc children disponível. Não é
pico completo dos imports nem cota aprovada. Ready do membro VmSize19.255.296/
VmPeak19.963.904; supervisor19.832.832/20.836.352. AS[-1,-1] no controle.

Pico cgroup93.392.896, events max/oom/oom_kill=0; OOMKilled=false, sem
deadline excedido ou pressão no teto externo192MiB. Inventário vivo[1,7],
final[1]/pids1. Cleanup confirmado, container removido, engine vazio
reconferido; Desktop inicialmente off foi iniciado oculto e restaurado
graciosamente (stop exit0), sem processos Desktop/backend/build/Python na
checagem posterior. Fontes/cópias, árvore e runtime.json iguais por hash.

SHA-256:

- summary.json: `dd8ce7fd1a73bf698a1d85abacec30d314737f3ac9f0783008f57168a8c4a1f0`;
- control.json: `54ccd503eb9394af8705a53cda3381d373162669287ee77c1e056d3c290b6c03`.

Bundle para revisão: `docs/poc/evidence/linux-imports-name-20261021.json`,
originais e429 linhas decodificadas pelo executor; não é nova execução.
Revisor confere leitura, não valida execução independente. Resultado deve
ser revisto antes de qualquer mudança. B-1/B-2/D-090/produção abertos.
