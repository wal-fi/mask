# W1: observação externa do MESMO job — desenho prospectivo XJ3

2026-11-15. Somente desenho, sob EXTERNAL-JOB-OBSERVATION-REVIEW EJ3 (normativa), EJ2 e EJ1. Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, claude-opus-5-5/medium. A XJ3 fecha só os quatro pontos do EJ3 sobre a XJ2 (cde09059), que fica preservada pelo root. A direção H-cria/S-adota foi aceita só como escolha prospectiva.

**O que este documento não é:** código, teste, oráculo, admissão nativa, perfil de filho, alocação de canário ou receita. Não autoriza nenhum efeito.

**Ficam fixos, sem edição nem import:** backend `10c9058f`, adaptador `eaebedd6`, qualificador `999f4a8d`, entrada C0 `43ffbf92`, host C0 `c695a68b`, os testes, `ACTIVE_PROCESS_LIMIT=2`, app124, state16 e a tentativa consumida.

As afirmações negativas valem só para essas superfícies; não são busca exaustiva.

## 1. Direção escolhida e alternativas

**Escolha prospectiva XJ-A:** H cria o job externo **J**, configura, atenua e transfere uma cópia limitada para S. S adota J no `JOB_LIST` da criação suspensa de P, ao lado do próprio OUTER.

**Motivos:** H tem proveniência desde a criação; S nunca é membro de J, então J conta só P (+ um helper), no máximo 2 durante toda a vida; o padrão de dois jobs com verificação antes do resume tem precedente no adaptador (`_expand_job_list` 273–300, `_verify_inner` 302–324), mas o adaptador NOVO de adoção não está pronto (§9).

**Alternativas:**
- **Job ancestral com S, P e helper:** fica bloqueado. São 3 processos cumulativos, acima do limite.
- **S cria e exporta o job para H:** não é impossível em princípio; é descartado aqui como ESCOLHA. Nessa direção, H só recebe o objeto depois do `setup` de S, sem proveniência própria anterior ao efeito, e S precisaria de autoridade sobre o processo de H.

## 2. Papéis, objetos e referências

| Ref | Detentor | Objeto | Origem |
|---|---|---|---|
| `F` | H | J, acesso completo de criador | criação, por H, sem nome e não herdável |
| `Q` | H | J, só QUERY e TERMINATE | duplicação atenuada de `F` dentro de H |
| `C` | S | J, só ASSIGN e QUERY | duplicação atenuada de `F` para o processo S |
| `PS` | H | processo S | a instância `Process` (padrão C0) |
| OUTER | S | job próprio de S | `Owner.setup` existente |

H nunca é membro de J, não lê pipes de P e não usa PID como identidade. P (+ helper) é criado suspenso em OUTER e em J; o helper, se houver, nasce de P. Ficam fora do escopo um job ancestral e qualquer guardião de H; não há recursão.

## 3. Identidade, proveniência e incerteza

- **Proveniência de J:** é o objeto que H criou. `Q` e `C` derivam de `F` por duplicação; nem valores de handle, nem SHA, nem PID provam identidade, e nenhum deles sai em relatório.
- **Qual referência H usa (§4):** antes de `Q` ser obtido positivamente, H conhece J só pelo `F`. Depois que `Q` é obtido positivamente, H consulta J pelo `Q`, inclusive quando o Start de S, a transferência ou a saída de S estão incertos. A identidade conhecida de J não depende da identidade, incerta, do processo S ou de `C`. S só é iniciado depois de `Q` positivo.
- **Falta de confirmação nunca prova ausência de efeito.** São estados distintos: recusa comprovadamente sem efeito (falha definida pela API de duplicação); saída desconhecida (exceção ou controle durante a duplicação, ou escrita parcial); escrita local concluída; recebimento por S, com ack; autorização de S para criar P.
- **Ack faltando ≠ "não há P".** S pode ter emitido o ack e seguido em frente sem H recebê-lo. H não fecha J nem declara ausência de P por falta de confirmação. Só a contagem de J pelo `Q`, depois da saída observada de S, fala sobre membros de J.
- **Não há retry,** nem uma segunda cópia, nem adoção depois de uma saída incerta.

## 4. Direitos, configuração e atenuação (pré-condições a MEDIR)

**Pré-condições não presumidas, nenhuma medida (a qualificação de `Process` existente não as prova):** **(R1)** o handle de `PS` obtido pelo SDK de H tem o direito de duplicar handles para dentro de S; **(R2)** a criação de J dá a `F` direitos para configurar, consultar, terminar e derivar `Q` e `C`; **(R3)** uma duplicação com direitos reduzidos não excede os de origem e produz exatamente o conjunto pedido.

**Ordem de custódia em H:**
1. **Criação de J.**
   - Criação positiva: `F` vai para a custódia imediatamente e vale `xjob=1`.
   - Criação incerta (exceção ou controle): `F` é desconhecido, nada é fechado, S não é iniciado e o registro sai com `xjob=0`, `XJOB_CREATE`, `xclose=NO_JOB`. Um eventual objeto sem membros fica como resíduo declarado até a saída de H.
2. **Configuração de J por `F`:** limite de ativos igual ao do backend, breakaway proibido, kill-on-close. Os valores exatos são de revisão, não preparados aqui.
3. **Releitura por `F`:** configuração, (total, active) = (0,0) e membros vazios → `pre=OK`.
4. **Derivação de `Q`.** Só um `Q` obtido positivamente vale como referência conhecida.
   - **Falha definida ou saída incerta de `Q`, ou `pre≠OK`:** ramo SEM início. Como S não existe e nenhuma `C` foi tentada, J não recebeu membros deste chamador. H relê por `F` a tupla completa e, só se ela for positivamente (0,0) com membros vazios, fecha `F` (`xclose=PRE_START`). Um `Q` incerto nunca é fechado nem usado; o valor dele é desconhecido e fica como resíduo até a saída de H.
   - **A tupla não é positiva:** `F` fica retido, não há registro e o host fica vivo.
5. **Com `Q` positivo:** início de S (§6) e derivação de `C` para S (§5), feita a partir de `F`.
6. **Fechamento de `F`:** só depois que a tentativa de `C` termina (com qualquer resultado) ou que o Start de S falha de forma definida antes dela, e SEMPRE com `Q` positivo retendo a mesma identidade. Falha no fechamento → `F_CLOSE_RAISED`, e `F` fica retido.

Não existe close de handle incerto.

**Usos permitidos:** `Q` consulta a qualquer momento e termina só sob a §8; `C` serve só para a adoção em S, e S nunca termina J. Observar `active > 0` não cria autoridade.

## 5. Transferência e transporte em vida de S (novo; não admitido)

- **Pipes de S:** stdin, stdout e stderr redirecionados, todos com posse de H pela instância `PS`. Este é um transporte NOVO: o C0 só lia depois da saída. Os limites pós-saída do C0 NÃO se aplicam por analogia.
- **Leitura e escrita síncronas, sem teto provado:** `Write` e `Read` podem bloquear. Prazo não é contenção. Não há thread, async nem framework.
- **Entrada H→S:** exatamente um registro ASCII `W1XT1 <ref>\n`, com `<ref>` de 1 a 16 dígitos hexadecimais minúsculos que identificam `C` dentro de S, no máximo 23 bytes. H escreve uma única vez, faz flush e fecha o stdin. S lê no máximo 24 bytes; registro extra, malformado ou ausente até o EOF leva a `REFUSED INPUT`.
- **Ack S→H:** exatamente uma linha ASCII com LF, `W1XA1 ADOPTED\n` ou `W1XA1 REFUSED <CAT>\n`, com `CAT` ∈ {`INPUT`, `HANDLE`, `CONFIG`, `NOT_EMPTY`, `QUERY`, `CONTROL`, `INTERNAL`}, no máximo 24 bytes. H lê com sentinela de 25 bytes; qualquer outra coisa é `MALFORMED` e nada recebido é `MISSING`.
- **Validação em S antes do ADOPTED:** só por `C` e pela QUERY: a configuração igual e (0,0). O ADOPTED autoriza S a criar P; não é prova para H.
- **Depois do ack:** S não escreve mais nada no stdout. H só lê o resíduo depois da saída de S, com sentinela de 1 byte. Qualquer byte é `OUT_EXTRA`; stderr segue o padrão de 1 byte do C0.
- **Estados da transferência em H:** `REFUSED_NO_EFFECT` (a API recusou a duplicação, sem efeito); `UNKNOWN` (duplicação ou escrita indeterminada); `WRITTEN` (registro escrito, flush feito, stdin fechado); `ACKED` (ack válido recebido). Se a duplicação falhar ou a escrita não for confirmada, H fecha o stdin de S sem reescrever; uma `C` eventualmente criada em S morre com S.

## 6. Ordem única por invocação

1. Preflight dos artefatos (padrão C0, streams retidos) → `F` → configuração → `pre` → `Q`.
2. `PS` alocado na custódia; `StartAttempted`; um `Start`; associação.
3. Derivação de `C` para S (R1, R3) → escrita única do registro → leitura do ack.
4. Consulta informativa de J por `Q` (`run`).
5. Espera primária pela saída de S (orçamento de decisão; no máximo um kill de reserva, §8).
6. Depois da saída observada de S: inventário de J por `Q` (`post_*`), resíduos do stdout e do stderr, término eventual (§8), fechamento de `Q`, `Dispose` de `PS`, fechamento dos artefatos.

São um J, uma `C`, um S e no máximo um P (+ helper) por invocação.

## 7. LAST_CLOSE

- **OUTER:** só S detém handle; a morte de S é o último close dele. A contagem de J depois da saída de S (`post_active=0`, membros vazios) é uma observação TEMPORAL feita de fora. Sozinha, ela NÃO prova que o último close do OUTER matou P, porque P pode ter saído antes. Concluir causalidade exigiria um fato positivo próprio (P comprovadamente ativo até a morte de S), que esta ligação não fornece e para o qual nenhum caso é alocado. O efeito em si continua premissa (§13).
- **J:** `Q` está retido, então a morte de S não é o último close de J. O kill-on-close de J só dispararia com o fechamento de `Q` ou com a morte de H, e isso é premissa sem prova.
- **Proibido:** fechar `Q` sem tupla liberável (§8) e liberar J para fabricar sucesso.
- **Não se finge que este desenho preserva o canário `close_inner` do adaptador;** o fato observado é outro (§12).

## 8. Saída de S, parada e descarte

| Saída de S | Definição |
|---|---|
| `NATURAL` | saída observada dentro do orçamento primário, sem kill |
| `FALLBACK` | o orçamento venceu, UM kill de S foi feito e a saída foi observada depois |
| `NONE` | S nunca foi iniciado (recusa antes do Start) |

**S incerto:** um Start incerto, ou uma saída nunca observada, mantém `PS`, `Q` e os artefatos. **Nenhum registro é emitido.** H pode continuar consultando J por `Q`, mas sem concluir nada e sem fechar.

**Inventário exato.** Cada leitura de J é a tupla COMPLETA (total, active, membros), com as duas consultas bem-sucedidas na mesma fatia. A tupla é válida só se:
- os três valores são inteiros exatos de 0 a 2;
- `active ≤ total`;
- membros = `active`.

Consulta parcial, valor fora do domínio ou contradição (por exemplo `total=0` com ativos ou membros) tornam a tupla inválida: nada é liberado, a custódia fica retida, não há registro e o host fica vivo.

**Tuplas liberáveis:**
- (0,0,0): J sem membros;
- (1,0,0) ou (2,0,0): membros encerrados.

Nada mais permite fechar uma referência de J.

**Depois da saída observada de S,** leituras por `Q` em fatias finitas:
1. **Tupla liberável** → observação positiva → fecha `Q` → `xclose=POST_S`. Uma tupla (0,0,0) depois de `ACKED` gera o erro `POST_EMPTY`: P não esteve em J. Isso não prova nada sobre processos fora de J.
2. **Tupla válida com `active > 0` ao fim do orçamento:**
   - UMA tentativa de término por `Q` (`xterm=RETURNED` ou `RAISED`; o retorno não é sucesso);
   - depois, novas fatias até uma tupla liberável;
   - sem ela → `Q` retido, sem registro e com o host vivo.
3. **Tupla inválida** → `Q` retido, sem registro, com o host vivo.

**Ramo sem início** (S nunca iniciado): o fechamento de `F` só pela §4, item 4, com `xclose=PRE_START`. Não há inventário por `Q` e `post_*` = null.

**Ordem de descarte:** `Q` → `PS` (`Dispose` só depois da saída observada e das leituras) → artefatos. Nada adianta etapa em incerteza. Não há prazo absoluto nem garantia de que o kill ou o término funcionem.

## 9. Adoção em S: superfície NOVA proposta (NÃO admitida)

**Arquivo:** um adaptador NOVO, específico, separado do backend `10c9058f` e do adaptador `eaebedd6`, que não são editados. É uma subclasse nova do `Owner`.

**Precedente e limites:** `NestedJobOwner` é precedente de forma, mas não está pronto para isto (ele CRIA o INNER e o guarda no ledger). O uso interno de `_call`/`_ok` e do ledger (`job`, `process`, `thread`) pela subclasse segue o MESMO padrão revisado do `eaebedd6` e precisa da revisão desta nova subclasse. O chamador (a entrada de S) nunca acessa o ledger.

**Superfície pública proposta:**

| Membro | Contrato |
|---|---|
| construtor `(request)` | igual ao `Owner`; além disso, `external = None` e `external_state = "NOT_ADOPTED"`. Sem I/O. |
| `adopt(reference) -> str` | permitido só com o Owner em `READY` (depois do `setup`) e só uma vez. Devolve `ADOPTED` ou `REFUSED_<CAT>`, mapeado 1:1 para o `<CAT>` do ack (§5). |
| `external_state` (leitura) | `NOT_ADOPTED` / `ADOPTED` / `REFUSED` |
| `start()` (herdado) | sem `ADOPTED`, a expansão do `JOB_LIST` recusa e não há efeito novo. Com `ADOPTED`: `JOB_LIST = [OUTER, C]` na criação suspensa; antes do resume, verificação do OUTER (herdada) e de `C`: pertinência, configuração, (1,1) e membros = (pid de P). |
| `close()` (herdado) | fecha só o ledger do backend. **`C` fica fora do ledger** e não é fechado nem declarado fechado por `close()`. Owner `CLOSED` não diz nada sobre `C`. |

**Pré-condições de `adopt`:**
- `reference` é um int exato de 1 a 2^64−1 (`bool` é recusado → `INPUT`);
- `reference` é diferente de todo valor do ledger e da quarentena do próprio Owner, para evitar confundir J com o OUTER ou com o stdio (→ `HANDLE`);
- uma consulta por `reference` confirma um objeto job (falha → `HANDLE` ou `QUERY`) com a configuração igual à esperada (→ `CONFIG`) e a tupla (0,0,0) (→ `NOT_EMPTY`);
- controle → `CONTROL`; qualquer outra falha → `INTERNAL`.

**Limites de `adopt`:**
- S não prova que J é o objeto de H: um job vazio e igualmente configurado seria indistinguível para S. A identidade vem da proveniência em H e da contagem pelo `Q` (`run`, `post_*`).
- **Dono de `C`:** o adaptador mantém `C` numa referência forte própria do objeto adaptador, que a entrada de S retém até a saída de S. Não existe método que feche ou termine `C`; `C` morre com o processo S. Fechar `C` não tiraria P de J.
- **S nunca termina J.** O `_interrupt` do backend só alcança o OUTER.
- **O resto de S** (park C0, close com quiescência) segue a semântica existente, que é a semântica de controle mais fraca de S.

**Ainda não admitido:** se ASSIGN e QUERY bastam para `JOB_LIST` e para as consultas; o aninhamento J/OUTER; R1–R3; os nomes exatos dos membros. Ficam para o contrato e os oráculos do adaptador, sem garantia antecipada.

## 10. Registro de H (schema próprio `W1XJ1`, não extensão do C0)

Uma linha JSON compacta, ASCII, com exatamente **21 chaves**, nesta ordem:

| # | Chave | Domínio |
|---|---|---|
| 1 | `kind` | `W1XJ1` |
| 2 | `status` | `PASS` / `FORCED` / `FAIL` / `UNKNOWN` / `REFUSED` |
| 3 | `error` | lista fechada abaixo |
| 4 | `xjob` | 0/1 |
| 5 | `pre` | `OK` / `MISMATCH` / `UNKNOWN` / `NOT_RUN` |
| 6 | `s_start` | `NONE` / `TRUE` (um Start incerto nunca gera registro) |
| 7 | `xfer` | `NOT_ATTEMPTED` / `REFUSED_NO_EFFECT` / `UNKNOWN` / `WRITTEN` / `ACKED` |
| 8 | `ack` | `NONE` / `ADOPTED` / `REFUSED` / `MALFORMED` / `MISSING` |
| 9 | `s_exit` | `NONE` / `NATURAL` / `FALLBACK` |
| 10 | `s_code` | null ou int32 |
| 11 | `fallback` | 0/1 |
| 12 | `run` | `ACTIVE` (1,1) / `ENDED` (1,0) / `EMPTY` (0,0) / `UNKNOWN` / `NOT_RUN` |
| 13 | `post_total` | null ou 0..2 |
| 14 | `post_active` | null ou 0..2 |
| 15 | `post_members` | null ou 0..2 |
| 16 | `xterm` | `NOT_REQUESTED` / `RETURNED` / `RAISED` |
| 17 | `xclose` | `NO_JOB` / `PRE_START` / `POST_S` |
| 18 | `disposed` | 0/1 |
| 19 | `assets_closed` | 0/1 |
| 20 | `descendants` | `UNKNOWN` |
| 21 | `gates` | `OPEN` |

**`error`** (no máximo 20 caracteres cada; vale só a primeira falha): `NONE`, `PARAM`, `ASSET`, `XJOB_CREATE`, `XJOB_CONFIG`, `XJOB_PRE`, `XJOB_ATTENUATE`, `F_CLOSE_RAISED`, `S_START`, `DUP_REFUSED`, `XFER_UNKNOWN`, `ACK_REFUSED`, `ACK_MALFORMED`, `ACK_MISSING`, `S_EXIT_FALLBACK`, `S_EXIT_CODE`, `POST_QUERY`, `POST_ACTIVE`, `POST_EMPTY`, `XTERM_RAISED`, `XCLOSE_RAISED`, `OUT_EXTRA`, `STDERR_PRESENT`, `DISPOSE_RAISED`, `ASSET_CLOSE_RAISED`, `CONTROL`, `INTERNAL`.

**Pior tamanho, incluindo o LF** (`"chave":valor` com os maiores valores de cada domínio):

| Entradas | Bytes |
|---|---|
| `kind` 14 + `status` 18 + `error` 30 + `xjob` 8 + `pre` 16 + `s_start` 16 + `xfer` 26 | 128 |
| `ack` 17 + `s_exit` 19 + `s_code` 20 + `fallback` 12 + `run` 15 | 83 |
| `post_total` 17 + `post_active` 18 + `post_members` 19 + `xterm` 23 | 77 |
| `xclose` 20 + `disposed` 12 + `assets_closed` 17 + `descendants` 23 + `gates` 14 | 86 |
| 20 vírgulas + 2 chaves + 1 LF | 23 |
| **Total** | **397 ≤ 512** |

**Coerência obrigatória:**
- **`xclose=NO_JOB`** ↔ `xjob=0`. Então: `pre=NOT_RUN`, `s_start=NONE`, `xfer=NOT_ATTEMPTED`, `ack=NONE`, `run=NOT_RUN`, `post_*`=null, `xterm=NOT_REQUESTED`.
- **`xclose=PRE_START`** → `xjob=1`, `s_start=NONE`, `xfer=NOT_ATTEMPTED`, `ack=NONE`, `run=NOT_RUN`, `post_*`=null, `xterm=NOT_REQUESTED`. A releitura positiva (0,0,0) por `F` imediatamente antes do fechamento é condição desse valor.
- **`xclose=POST_S`** ↔ `s_start=TRUE`. Então: `s_exit` ∈ {`NATURAL`, `FALLBACK`}, `s_code` não nulo e (`post_total`, `post_active`, `post_members`) ∈ {(0,0,0), (1,0,0), (2,0,0)}.
- **`s_start=NONE`** → `s_exit=NONE` e `s_code=null`.
- `xfer≠ACKED` → `ack≠ADOPTED`.
- `s_exit=FALLBACK` ↔ `fallback=1`.
- `post_*` são todos null ou todos inteiros; nunca há zeros fabricados para satisfazer o schema.
- `status=REFUSED` ↔ `xclose` ∈ {`NO_JOB`, `PRE_START`}.

## 11. O que existe e o que é NOVO

**Reutilizado sem mudança:** os métodos públicos do `Owner` do backend e o `_start` herdado por subclasse, como precedente do adaptador; a custódia de `Process`, o padrão de preflight e o modelo de registro fechado do host C0; o carregamento por bytes conferidos.

**NOVO, cada item com revisão explícita própria:**
- **N-H:** um host específico com ligação revisada para criar, configurar, consultar, terminar, duplicar com atenuação e fechar jobs. É uma ligação nova, não uma edição do C0, e exige revisar o contrato v2, porque o contrato C0 proíbe isso.
- **N-S:** o adaptador de adoção da §9, uma subclasse nova do `Owner` com a superfície proposta e não admitida. Não existe nada assim hoje: o `NestedJobOwner` CRIA o INNER e não recebe um job de fora.
- **N-C:** o transporte bidirecional em vida de S da §5, ainda não admitido.

Sem extração do ledger privado e sem presumir exportação ou adoção nas APIs atuais.

## 12. Predicados próprios

Todos os predicados abaixo valem só para registros emitidos. Com descarte incompleto não há registro: a custódia continua retida.

- **PASS:** a subpropriedade "inventário externo de J depois da saída NATURAL de S". É uma observação temporal, não causalidade nem limpeza física. Exige:
  - `error=NONE`, `xjob=1`, `pre=OK`, `s_start=TRUE`, `xfer=ACKED`, `ack=ADOPTED`;
  - `s_exit=NATURAL`, `s_code=0`, `fallback=0`;
  - `post_total` ∈ {1,2}, `post_active=0`, `post_members=0`;
  - `xterm=NOT_REQUESTED`, `xclose=POST_S`, `disposed=1`, `assets_closed=1`.

  `run` é informativo: `EMPTY` (P ainda não criado) e `ENDED` (P curto já encerrado) não são inconsistência e não impedem PASS. A conjunção C0 (frame `W1C0` e saída 0 do C0) NÃO faz parte.
- **FORCED:** um predicado PRÓPRIO, que não é PASS. Exige:
  - `error=S_EXIT_FALLBACK` (a primeira falha), `xjob=1`, `pre=OK`, `s_start=TRUE`, `xfer=ACKED`, `ack=ADOPTED`;
  - `s_exit=FALLBACK`, `fallback=1`, `s_code` int32 qualquer;
  - `post_total` ∈ {1,2}, `post_active=0`, `post_members=0`;
  - `xterm=NOT_REQUESTED`, `xclose=POST_S`, `disposed=1`, `assets_closed=1`.

  Significa só "depois da morte forçada de S, J não tinha membros ativos no instante da leitura". NÃO é fato causal do último close do OUTER (§7).
- **FAIL:** registro emitido com outra falha conhecida e fechada, como `POST_ACTIVE` com `xterm=RETURNED` e tupla liberável depois, `POST_EMPTY`, `S_EXIT_CODE`, `ACK_REFUSED`, `OUT_EXTRA` ou `STDERR_PRESENT`. É um achado, não sucesso.
- **UNKNOWN:** registro emitido com `xfer=UNKNOWN`, `ack` ∈ {`MISSING`, `MALFORMED`} ou `CONTROL`, sempre com `xclose=POST_S` e tupla liberável.
- **REFUSED:** S nunca foi iniciado e `xclose` ∈ {`NO_JOB`, `PRE_START`} (§4).

## 13. Premissas e fatos mensuráveis

**Premissas não medidas:** R1–R3; o aninhamento de J sob OUTER no `JOB_LIST`; o kill-on-close do OUTER alcançando P aninhado; a contagem de J não incluir detentores de handle; a morte de H e o último close de J; tetos de parede de Read, Write e chamadas do SO.

**Fatos que a XJ pode medir:** a contagem e os membros de J pelo `Q` antes de S, depois do ack e depois da saída de S; o ack; os casos `NATURAL` e `FALLBACK`; o término por `Q` e a observação posterior.

**Não medidos:** EOF de P (os pipes são de S), então **N5, N8 e o agregado não fecham por contagem**; descendentes fora de J; quitação física.

A regra B4 de P não passa para S nem para H; os controles em H têm semântica própria, e capturar um não protege contra outro. Nenhum dos 16 N é dispensado.

## 14. Escopo, gates e próximo passo

- **Escopo:** a XJ3 descreve apenas UMA ligação de custódia externa do mesmo job. Não aloca canário com filho, não muda o host C0, o backend, o adaptador nem os limites, e não admite S, G, nada nativo nem o produto.
- **Continuam OPEN:** N-H, N-S e N-C; R1–R3 e as premissas da §13; N1–N16, T5, B1, B2, D-090 gate2, C1, D119, TLS, ingressos e produção. O Gateway segue indisponível.
- **Menor próximo passo de revisão:** o root lê o delta da XJ3, recalcula o schema e decide se o próximo lote pode ser o contrato e os oráculos do adaptador N-S da §9, além do contrato v2 de N-H e do transporte N-C. Só depois vêm os oráculos congelados, com N-S primeiro (testável com fakes, sem efeito nativo), o RED, a fonte e a revisão de contenção.

Política Senff: desenho derivado de IA exige revisão humana e de segurança antes do merge.
