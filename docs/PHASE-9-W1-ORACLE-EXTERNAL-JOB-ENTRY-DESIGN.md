# W1: entrada S para adoção externa e seu lado do N-C — desenho prospectivo XE2

2026-11-16. Somente desenho, sob EXTERNAL-JOB-ENTRY-REVIEW ER2 e ER1 (normativas), XJ3 e EJ1–EJ6. Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, claude-opus-5-5/medium. A XE2 substitui a XE1 (`ec2eff71`), que fica preservada pelo root.

**O que este documento não é:** código, teste, oráculo, admissão do `main`, perfil de P, argv, caminho, valor operacional ou efeito nativo. Nenhuma autorização nova.

**Ficam fixos:** N-S `465ae906`/teste `37a757ad` (publicados em `28677e2`, só com SDK falso), backend `10c9058f`, adaptador `eaebedd6`, C0 `c695a68b`/`43ffbf92`, qualificador `999f4a8d`, todos os testes, pins, app124, state16 e a tentativa. O C0 é precedente de custódia e de leitura limitada, NÃO é entrada de adoção nem transporte vivo; seu argv, perfil e fluxo setup/close não são herdados.

## 1. Fronteira, carga e confiança

- **Módulo futuro único:** `docs/poc/oracle9_w1_external_job_entry.py`. O import só define; não registra nada em `sys.modules`.
- **`load_adoption() -> AdoptionLoad`:** lê o irmão fixo `oracle9_w1_external_job_adoption.py` exatamente como os loaders pinados existentes.
  - Exige arquivo regular, sem reparse point final, tamanho do `lstat` igual aos bytes capturados e limite de 65.536 bytes.
  - SHA-256 completo `465ae9067e0f24fe656259e3757f45e8a5788f55ed177db2ab82160d5b6ba5ae` (15.836 bytes).
  - Executa os MESMOS bytes num namespace privado, com `compile(..., dont_inherit=True)` e `__file__` igual ao caminho real (o loader pinado do próprio N-S acha o backend).
  - Depois chama `definitions()` desse namespace.
  - Falha comum → `EntryLoadError` fechado, sem cadeia; controle → propaga, porque ainda não existe custódia nem efeito.
- **Fronteira de confiança:** `AdoptionLoad` é uma classe congelada própria da entrada, com repr redigido, criada SÓ por `load_adoption()`. Guarda o dicionário de quatro chaves e captura uma vez `backend`, `Request`, `ExternalJobOwner` e `Win32Error`.
  - `run_entry` exige `type(adoption) is AdoptionLoad` e reconfere as identidades: `Request is backend["Request"]`, `Win32Error is backend["Win32Error"]`, `ExternalJobOwner` subclasse direta de `backend["Owner"]`.
  - Um dicionário arbitrário com os quatro nomes NÃO é aceito. Isso é contrato de API, não defesa contra código privilegiado que fabrique a instância.
- **API testável:** `run_entry(adoption, request, reader, writer, budget, custody) -> str`, que devolve a categoria da §7 e nunca estaciona.
  - `request`: `type(request) is adoption.Request` exato, construído pelo chamador.
  - `reader`/`writer`: só `read(n)`, `write(b)` e `flush()`, no papel de stdin/stdout binários.
  - `budget`: int built-in exato de 1 a 400, o mesmo teto `MAX_TURNS` do qualificador. Não há valor operacional aqui.
  - Constantes vindas do backend capturado: `MAX_WAIT_MS` (espera por turno) e `MAX_READ` (bytes por leitura). Nada de ambiente ou runtime é lido.
- **NÃO admitido neste lote:** o `main` real e seu argv; a construção do `Request` de P; o valor do orçamento; a ligação de stdin/stdout do processo; e o park do `main` (§6). A entrada testada com fakes NÃO é o produto final.

## 2. Custódia concreta: `EntryCustody`

Dataclass mutável com `slots`, repr redigido e criada vazia pelo chamador. Não é `QualCustody`.

| Campo | Tipo e default | Escrito quando |
|---|---|---|
| `claimed` | bool = False | primeiro passo depois das checagens pré-aquisição |
| `adoption` | `AdoptionLoad` ou None = None | no claim |
| `request` | `Request` ou None = None | no claim |
| `owner` | `ExternalJobOwner` ou None = None | logo depois da construção, ANTES do `setup` |
| `reference` | int ou None = None | logo depois do parse válido, ANTES do `adopt` |
| `adopt_result` | str ou None = None | retorno exato do `adopt` |
| `ack` | `"NOT_ATTEMPTED"` (default) / `"DELIVERED_LOCAL"` / `"WRITE_FAILED"` / `"FLUSH_FAILED"` | §4 |
| `output_bytes` | int = 0 | contador dos bytes de P lidos e descartados; nunca o conteúdo |
| `first_error` | Exception ou None = None | primeira exceção comum OBSERVADA pela entrada |
| `first_control` | BaseException ou None = None | primeiro controle, por identidade |
| `stage` | enum `EntryStage` = `NEW` | a cada transição |

**`EntryStage`:** `NEW`, `CLAIMED`, `OWNER`, `SETUP`, `INPUT`, `ADOPT`, `ACK`, `START`, `SUPERVISE`, `DRAIN`, `CLOSE`, `DONE`.

**Recusa pré-aquisição (`REJECTED`):** custódia não vazia, de outro tipo ou já reclamada; `adoption` fora da fronteira; `request` de outro tipo; `budget` fora do domínio. Nesse caso nada é escrito na custódia, não há Owner, ack nem efeito. É distinta de `REFUSED`, que é uma recusa depois da aquisição, com ack e close.

A referência emprestada C fica em `custody.reference` e dentro do Owner (`external`). A entrada NUNCA fecha nem termina C e não usa C fora do `adopt`. Uma exceção comum interna ao N-S só é visível pelo resultado do `adopt`; a entrada não inventa um original escondido.

## 3. Entrada: um registro limitado até o EOF

- **Gramática da XJ3 §5:** `W1XT1 ` + 1 a 16 dígitos hexadecimais minúsculos + `\n`, com no máximo 23 bytes. Zeros à esquerda são ACEITOS: `000000000000ab` representa ab. Não aceita CR, espaço extra nem segundo registro.
- **Leitura:** acumula até ter 24 bytes ou até `read` devolver `b""`, que é o EOF.
  - Cada `read(n)` pede só o que falta para 24.
  - Se o resultado não é `bytes` exato, ou tem mais que `n` → falha de entrada.
  - Leitura curta NÃO é EOF.
  - Chegar a 24 bytes → excesso: para de ler e recusa.
  - Uma leitura pode bloquear; não há teto de parede.
- **Domínio numérico:** 1..2^64−2. Zero e 2^64−1 → recusa INPUT sem `adopt`.

## 4. Ack: um único, entrega LOCAL

- **Mapeamento:** `ADOPTED` → `W1XA1 ADOPTED\n`; `REFUSED_<CAT>` → `W1XA1 REFUSED <CAT>\n`, com `CAT` ∈ {`INPUT`, `HANDLE`, `CONFIG`, `NOT_EMPTY`, `QUERY`, `CONTROL`, `INTERNAL`}. São no máximo 24 bytes.
- **Escrita:** UMA tentativa, sem retry.
  - Entregue só se `write` devolver um int exato (não `bool`) igual ao comprimento e o `flush` vier depois sem exceção.
  - Qualquer outro retorno → `WRITE_FAILED`, sem flush.
  - Exceção no `flush` → `FLUSH_FAILED`.
- **Depois do ack:** NENHUM byte a mais em stdout e nada em stderr. Não há frame final nem diagnóstico.
- **Entrega local ≠ prova:** não prova que H recebeu, nem cria ou termina P. Ack faltando não prova que P não existe em toda falha assíncrona.

## 5. Transições

Todo `close` exige retorno None e estado público exatamente `"CLOSED"`. Se falhar, o resultado é `RETAIN`.

1. **`CLAIMED`:** checagens pré-aquisição; claim; `adoption` e `request` retidos.
2. **`OWNER`:** `owner = ExternalJobOwner(request)`, retido ANTES do `setup`.
3. **`SETUP`:** `setup()` deve retornar None e o estado deve ser `READY`.
   - Senão: ack `REFUSED INTERNAL` SEM ler a entrada. O registro pode ficar não consumido; isso não prova nada sobre o transporte vivo em H.
   - Depois: estado `SETUP_FAILED` → `close` → `SETUP_REFUSED` (ack entregue) ou `ACK_FAILED`; HELD ou outro → `RETAIN`.
4. **`INPUT`:** leitura da §3. Recusa → ack `REFUSED INPUT`, sem `adopt`.
5. **`ADOPT`:** `owner.adopt(reference)` uma vez.
6. **`ACK`:** a §4.
7. **Sem P:**
   - Owner READY → `close` → `REFUSED` (ack entregue) ou `ACK_FAILED`.
   - Owner HELD (forma interna corrompida, ou `REFUSED_CONTROL`) → `RETAIN`.
8. **`START`:** só com `ADOPTED` E `DELIVERED_LOCAL`. `start()` deve retornar None com estado `RUNNING`; senão → `RETAIN`.
9. **`SUPERVISE`/`DRAIN`:** um ÚNICO orçamento de turnos compartilhado. Um turno é um `wait(MAX_WAIT_MS)`, e há no máximo um `read` por turno.
   - **Domínios exatos:** `wait` → `bool`; `available` → None ou int de 0 a 2^32−1; `read` → `bytes` com até `MAX_READ` (vazio permitido, mas não é EOF); `exit_code` → int de 0 a 2^32−1; `accounting` → exatamente `(1, 0)`; `members` → exatamente `()`.
   - **Em cada turno:** `wait`, depois `available`, e se for positivo um `read`. Os bytes são contados em `output_bytes` e descartados.
   - **Depois de `wait` True:** `exit_code`, `accounting` e `members`, nessa ordem e com inventário positivo.
   - **Drenagem:** `available()` → None fresco = EOF; positivo → `read` (se ainda não houve read neste turno), senão novo turno; zero → novo turno. Isso vale para saída de P maior que um bloco, até o orçamento acabar.
   - **Fim:** `close` → `DONE` se o código for 0, ou `DONE_NONZERO`.
   - **Orçamento esgotado, valor fora do domínio, Win32Error ou estado incoerente** → `RETAIN`, sem `terminate` (a parada é de H) e sem `close`.
   - EOF de P nunca é inferido por inventário, nem término físico por retorno de `terminate`.

## 6. Controles, retenção e park do `main`

- **Pontos de captura** (cada um com seu `except BaseException`): construção, `setup`, cada `read`, `adopt`, `write`/`flush`, `start`, cada chamada de supervisão e drenagem, e cada `close`.
- **Primeiro controle:** vai para `first_control` por identidade, sem `bool`/`str`/`repr`, sem re-raise e sem atribuir traceback ou contexto. Depois disso não há escrita, flush nem chamada nova da entrada, e o resultado é `RETAIN`.
- **ÚNICA exceção a essa regra:** quando o `adopt` RETORNA `REFUSED_CONTROL`, a entrada copia `owner.adopt_control` (o objeto exato) para `first_control`, se ainda vazio, e faz UMA tentativa do ack `W1XA1 REFUSED CONTROL\n`. Não há SDK depois. Um controle no `write`/`flush` desse ack não substitui o primeiro nem autoriza retry. O resultado é sempre `RETAIN`.
- **Escopo:** a garantia de zero SDK depois do controle é só a do `adopt` (N-S). Efeitos internos do backend (`_guarded`/`_interrupt`, que podem terminar o OUTER) e controles entre bytecodes ficam fora, como resíduo explícito. HELD nunca é fabricado: só se lê o estado público.
- **Observabilidade determinística:** `run_entry` NÃO estaciona. Devolve `RETAIN` com a custódia forte do chamador ainda populada. Os oráculos observam o retorno e a custódia, sem laço infinito, thread, processo nem substituição de produto.
- **Obrigação do `main` futuro (não admitido):** reter a custódia até o fim de S; em `RETAIN`, entrar num park específico que só dorme e engole controles posteriores sem substituir o primeiro, nunca fecha, termina nem sai. Esse park pertence só ao `main` e será revisto junto com ele.

## 7. Categorias (código do processo depois do mapeamento do `main`; nada em stdout)

| Categoria | Situação |
|---|---|
| `DONE` | ADOPTED, ack local, P iniciado, quiescência e EOF positivos, close None+CLOSED, P com código 0 |
| `DONE_NONZERO` | idem, com código ≠ 0 |
| `REFUSED` | ack de recusa entregue, sem P, close None+CLOSED |
| `SETUP_REFUSED` | setup recusado de forma limpa, ack entregue, close None+CLOSED |
| `ACK_FAILED` | ack não entregue (em qualquer ramo sem P), close None+CLOSED |
| `REJECTED` | recusa pré-aquisição: sem custódia escrita, sem Owner, sem ack |
| `RETAIN` | qualquer incerteza ou controle; o chamador retém tudo |

A numeração fica para a admissão do `main`. A saída de S e seu código são observações de H separadas do ack.

## 8. Oráculos falsos antes da fonte (teste novo; RED pela ausência)

Reusa o `Kernel` de referência e o `AdoptKernel` do teste de N-S, com `reader`/`writer` concretos e pequenos de bytes. Só os seams da cópia privada do backend; sem processo, thread, DLL ou patch de produto vivo.

1. **Carga:** pin completo, ausente, adulterado ou grande demais → recusa sem executar; `AdoptionLoad` forjada, dicionário arbitrário ou identidade trocada → `REJECTED`.
2. **Custódia:** defaults exatos; reuso ou tipo estranho → `REJECTED` sem escrita; Owner retido antes do `setup` e `reference` antes do `adopt`; `budget` com `bool`, 0 ou 401 → `REJECTED`.
3. **Entrada:** leituras fragmentadas aceitas; zeros à esquerda aceitos; extra, longa, CR, maiúsculas, 0, 2^64−1, sem LF, ausente até o EOF, `read` não-bytes ou acima do pedido → `REFUSED INPUT` sem `adopt`.
4. **Ack:** um único com os bytes exatos para cada resultado; retorno do `write` curto, zero, None, `bool` ou opaco → `WRITE_FAILED` sem flush; falha no flush → `FLUSH_FAILED`; nada depois do ack; stderr vazio.
5. **`setup`:** recusa limpa → `SETUP_REFUSED` com o registro não lido; HELD → `RETAIN`.
6. **Ciclo de P:** positivo → `DONE`; saída em vários blocos drenada dentro do orçamento; EOF só por `available` None depois do inventário; código diferente de zero → `DONE_NONZERO`; domínios inválidos, orçamento esgotado ou close falho → `RETAIN` sem `terminate`.
7. **Controles:** em cada ponto → primeiro objeto retido, nenhum efeito novo da entrada, `RETAIN`; `REFUSED_CONTROL` → `first_control is owner.adopt_control`, exatamente um ack `CONTROL`, nenhum SDK depois; controle no `write` desse ack → o primeiro preservado.
8. **Uso de C:** nenhum `CloseHandle`/`TerminateJobObject`/uso como processo de C em nenhum caminho.
9. **AST:** sem `subprocess`, threads, sockets, `time` nem acesso a ledger em `run_entry`.

## 9. Continua aberto

O `main`, o park, o `Request` de P e o valor do orçamento; N-H (job e direitos do lado H, também testável com fakes em contrato próprio); o transporte vivo real; R1–R3; aninhamento e kill-on-close; N1–N16 e todos os gates de produto. O Gateway segue indisponível. Próximo passo: o root lê todo o delta antes de decidir sobre os primeiros oráculos.

Política Senff: desenho derivado de IA exige revisão humana e de segurança antes do merge.
