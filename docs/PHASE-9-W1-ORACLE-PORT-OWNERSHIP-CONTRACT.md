# Adendo de Desenho V4.1 — Precisões de Representação (`pipes_lost`, `plan_index` e Prazos)

Proposta de autoria sob delegação para revisão do root, sobre `PORT-DESIGN.md` (V4, `527ab514`) e `PORT-REVIEW.md`, antes da implementação de `docs/poc/oracle9_w1_port_ownership.py`. Nenhuma assinatura pública, dataclass congelada, enum, teste congelado (`e85f8b53`, 171 casos) ou contrato publicado (`5a09be1c`, `e86f8e32`, `4c155d76`) é alterado. Nenhum novo export, campo, fábrica, valor operacional ou efeito nativo é introduzido. Os módulos `oracle9_w1_port_ownership.py` e `oracle9_w1_proactor_pump.py` permanecem ausentes e todos os gates nativos/físicos e de produto permanecem **OPEN**.

---

## 1. Semântica Posicional e Domínio de `RecordView.pipes_lost`

O campo `RecordView.pipes_lost: tuple[bool | None, bool | None, bool | None]` tem comprimento fixo 3, indexado posicionalmente por descritor `(fd 0, fd 1, fd 2)`:

- **Posição `0` (`fd 0`, stdin):** aplicável apenas a `InvocationKind.SPAWN` (`stdin_pipe=True`); permanentemente `None` em `InvocationKind.CHILD` (`stdin_pipe=False`) e nos demais kinds.
- **Posição `1` (`fd 1`, stdout):** aplicável a `SPAWN` e `CHILD` após `started(handle)`.
- **Posição `2` (`fd 2`, stderr):** aplicável apenas a `CHILD` (contagem de bytes em §5.2); permanentemente `None` em `SPAWN` (que usa `DEVNULL` e não possui pipe de stderr no contrato) e nos demais kinds.

### Significado de `None`, `False` e `True` em `pipes_lost[fd]`

| Valor | Significado no modelo do owner |
|---|---|
| `None` | Pipe inexistente para o kind (`fd 2` no gateway, `fd 0` em helper, ou qualquer `fd` em `WRITE`/`WAIT`/`ACT`/`AUDIT`/`DISPOSE`), processo ainda sem `started(handle)`, ou pipe configurado ainda aberto (`Retained.PIPE_{fd}` presente em `retained`). |
| `False` | `pipe_lost(fd, False)` observado pelo owner para um `fd` configurado do processo (perda/EOF local sem flag de falha; `Retained.PIPE_{fd}` removido de `retained`). |
| `True` | `pipe_lost(fd, True)` observado pelo owner para um `fd` configurado do processo (perda local com `failed is True` reportado pelo `Pump`; `Retained.PIPE_{fd}` removido de `retained`). |

### Regras de representação e fronteira física

1. **Inicialização:** todo registro nasce com `pipes_lost = (None, None, None)`.
2. **Abertura em `started(handle)`:** `pipes_lost` permanece `(None, None, None)`; `retained` passa a incluir `(PIPE_0, PIPE_1)` em `SPAWN` e `(PIPE_1, PIPE_2)` em `CHILD`.
3. **Observação de `pipe_lost(fd, failed)`:** para `fd` configurado do processo (`{0, 1}` em `SPAWN`; `{1, 2}` em `CHILD`) e argumento `failed` de tipo exato `bool` (`failed is False` ou `failed is True`, sem coerção `bool(...)`), `pipes_lost[fd]` passa de `None` ao valor exato `failed` e `PIPE_{fd}` é removido de `retained`.
4. **Critério de todos os pipes perdidos (§7):**
   - `SPAWN`: `pipes_lost[0] is not None and pipes_lost[1] is not None` (com `pipes_lost[2] is None`);
   - `CHILD`: `pipes_lost[1] is not None and pipes_lost[2] is not None` (com `pipes_lost[0] is None`).
5. **Não inferência nativa:** `pipes_lost[fd] in (False, True)` representa exclusivamente a entrega do callback `pipe_lost` pelo `Pump`; não prova fechamento de handle no kernel, drenagem física de pipe do SO nem release de memória/processo (`NOT_PREPARED`).

---

## 2. Significado Inequívoco de `RecordView.plan_index` e `HelperRaw.index`

Os registros e relatórios nunca retêm `argv`. Toda referência à receita usa índices inteiros determinísticos derivados da ordem imutável do `CliPlan` fornecido ao construtor:

| `InvocationKind` | Valor de `RecordView.plan_index` | Origem no `CliPlan` imutável |
|---|---|---|
| `SPAWN` | `0` | Único `plan.gateway_argv` do plano. |
| `WAIT` | `0` | Espera associada ao único processo `SPAWN` (`plan_index = 0`). |
| `WRITE` | `0` | Escrita no stdin do único processo `SPAWN` (`plan_index = 0`). |
| `ACT` | `0..5` | Índice `i` (base 0) da tupla `(act_kind, helpers)` na ordem exata de `plan.acts` tal que `plan.acts[i][0] is act.kind`. |
| `AUDIT` | `0..1` | Índice `i` (base 0) da tupla `(audit_kind, helpers)` na ordem exata de `plan.audits` tal que `plan.audits[i][0] is kind`. |
| `DISPOSE` | `0` | Índice fixo `0` (em `REMOVE_GATEWAY_CONTAINER` referencia a tupla única `plan.remove_gateway`; em `CLOSE_HANDLE` e `TERMINATE_PROCESS` o alvo já é identificado por `parent = target_id`). |
| `CHILD` | `0..23` | Índice local `j` (base 0) do `HelperPlan` dentro da tupla de filhos da invocação pai (`plan.acts[p][1][j]`, `plan.audits[p][1][j]` ou `plan.remove_gateway[j]`). |

### Coerência com `HelperRaw.index` e redacção

1. **Correspondência 1:1 com `HelperRaw.index`:** para todo filho assentado de `ACT`, `AUDIT` ou `DISPOSE` (`REMOVE_GATEWAY_CONTAINER`), o `HelperRaw` entregue ao decoder interno tem `HelperRaw.index == child_record.plan_index == j` (`0 <= j < len(helpers) <= 24`), na ordem sequencial de execução `0, 1, ..., n - 1`.
2. **Não retenção de `argv`:** no momento de `schedule_start`, o owner lê `HelperPlan.argv` (ou `plan.gateway_argv`) do `CliPlan` apenas para construir o `StartRequest` enviado ao `Pump`. Nenhum `RecordView`, `HelperRaw`, `AuditReport`, `CustodyView` ou `OwnershipRefusal` armazena ou formata `argv`.

---

## 3. Invariantes de Prazo e Protocolo Preservadas (§4, §5 e §7)

1. **Prazo de startup (`SPAWN`) vs. vida da sessão (`WRITE`/`WAIT`/`ReadTake`):** `SPAWN.deadline` governa exclusivamente a conclusão do startup do gateway. Uma vez que o `SPAWN` concluiu com `SUCCEEDED` e o processo segue `OPEN`, registros posteriores de `WRITE` e `WAIT` têm `parent = spawn_record_id` e cada `ReadTake` (cujo DTO congelado público expõe apenas `take_id`, `size` e `deadline`, sem campo `parent`) permanece associado internamente ao buffer/stream desse `SPAWN`; cada operação valida o próprio `deadline`, sem reutilizar `SPAWN.deadline` vencido como teto da sessão.
2. **Encadeamento ativo de `CHILD` sob `ACT`/`AUDIT`/`DISPOSE`:** "prazo do pai" em §4 aplica-se ao despacho e `authorize` de cada `CHILD` sob seu pai `ACT`, `AUDIT` ou `DISPOSE` (`pump.now() < child.deadline` e `pump.now() < parent.deadline`, com pai não concluído), sem depender de `seal()` e sem prorrogar `parent.deadline`. Enfileirar `StartRequest` em `schedule_start` é inerte; a criação de handle depende de `authorize()` retornar `True` dentro de `run_until`.
3. **Independência da quarentena da ponte e imutabilidade do protocolo:** a quarentena/UNKNOWN da ponte é independente e nunca escreve `RecordView.protocol` (o owner nunca inspeciona slots/células da ponte nem chama `done()`/`outcome()` dos ops). Uma invocação cujo prazo expira com filho vivo permanece `PENDING` no owner (`UNKNOWN` apenas quando o próprio owner já o fixou por falha conhecida de partida, limite/capacidade, transporte ou decode), e fatos físicos posteriores atualizam somente `late`, `uncertain`, `physical`, `retained`, `pipes_lost`, `returncode` e `settled_at`, sem reabrir o protocolo.
