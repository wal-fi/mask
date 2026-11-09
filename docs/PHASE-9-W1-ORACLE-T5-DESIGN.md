# W1 Oracle — desenho mínimo da sonda EOF (T5, caso 24), v3

2026-11-09. Somente desenho, Claude2 (sessão 51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5, esforço medium), sob a delegação vigente. É uma proposta para
revisão do root, não aprovação individual. Base HEAD 9748d2b.

A v1 (1ccdaa2d) e sua revisão lógica ficam como dados arquivados pelo root. A v2
(d505daed) corrigiu os achados F1 a F4. Esta v3 acrescenta só as precisões R2-1 a
R2-3. Nada foi executado: nenhum teste, processo, socket, thread, sinal, guard,
Docker, PG ou SQL. Nenhum fato nativo foi medido. Todos os testes citados aqui são
**planejados**, não medidos; nenhum comportamento novo está provado por fakes.

Fixos neste lote:
- main 372f342f/teste 5abe4582;
- driver 39a68904/teste 585540af;
- puro 4c155d76/teste 084d62cd;
- EXPECT ce6ff389/teste ccb1f29f;
- protegidos 27, app124, estado16 e tentativa consumida.

T5 continua BLOCK_NATIVE obrigatório para o laboratório completo. Hoje o driver
emite `RESULT{24, FAIL, PENDING, T5_PENDING}` e **não** sonda EOF.

## 1. Fatos lidos que fixam o desenho

- `WorkerSession` (público) não fecha por EOF.
  - `close()` em READY envia `CLOSE`.
  - `_reap` usa `wait(1 s)` e depois `kill`.
  - A sonda precisa de canal próprio e não usa campos privados da sessão.
- `worker_process` instalado:
  - `main` exige argv de 4 números e `protect_process(WORKER, expected_parent_pid)`;
  - exige env igual ao público `child_environment()`, socket AF_UNIX/STREAM conectado e stdin FIFO;
  - `_read_init` precisa do INIT inteiro **e** de EOF no stdin;
  - em seguida o filho conecta, envia OPENED (`hmac(nonce, snapshot)`) e entra em `_loop`;
  - `_next` devolve `None` em EOF **e** em expiração do idle; `_loop` devolve **0** nos dois casos e também em `CLOSE`;
  - toda recusa, exceção ou falha de abertura dá **1**.
- Consequência: **exit 0 sozinho não distingue EOF de idle.**
  - `CLOSE` está excluído porque o binding revisto do pai não envia nada pelo socket (§3).
  - Para excluir o idle, usa-se uma cerca temporal (§4.1).
- Codecs públicos de `worker_protocol`: `HEADER_BYTES`, `parse_header`, `Kind`, `decode_guard`, `decode_opened`, `encode_init`, `SecretInit`.
- Ledger público:
  - `reserve_session` e `adopt_session` sob o lock comum;
  - `begin_drain` + `release(token, CleanupConfirmation)`, que dá HELD se faltar fato;
  - `retain`.
- Main: `System` já tem `socketpair`, `select`, `set_blocking`, `os_write`, `close` e `monotonic`. Faltam a criação de processo e um pipe explícito.

## 2. Lacunas exatas (mudanças prospectivas mínimas)

| # | Onde | Mudança |
|---|---|---|
| L1 | driver `Ports` | 9º campo `children` (§3) |
| L2 | driver porta `ids` | `nonce() -> bytes` de 32 bytes |
| L3 | driver `t5()` | sonda §4 no lugar do PENDING |
| L4 | main `System` | 21º campo `popen` (`subprocess.Popen`) e 22º campo `pipe2` (wrapper de módulo `_pipe2`, §3) |
| L5 | main `SLOTS` | +5: `probe_parent`, `probe_child`, `probe_stdin_r`, `probe_stdin_w`, `probe_process` |
| L6 | main | binding `ProbeChildren(root)` e `SessionIds.nonce` |
| L7 | main pins | `DRIVER_SHA`/`DRIVER_BYTES` do driver emendado |

- O main ganha import de `subprocess`.
- Ficam inalterados: SDK, `WorkerSession`, núcleo puro, EXPECT, wire host↔controlador, 50 frames e 56 linhas.
- O formato do resultado e do SUMMARY muda conforme §6.

## 3. Porta `children` (contrato confiável, não sandbox)

```text
children.pair()  -> (parent, child)        # socketpair AF_UNIX/STREAM
  parent.recv_exact(n, *, deadline: float) -> bytes ; parent.close() -> bool
  child.fd: int ; child.close() -> bool
children.stdin() -> (reader, writer)       # pipe explícito, criado ANTES do Popen
  reader.fd: int ; reader.close() -> bool
  writer.write_all(packet: bytes, *, deadline: float) -> bool ; writer.close() -> bool
children.spawn(child, reader, *, parent_pid, address_bytes, idle_ms) -> proc
  proc.pid: int ; proc.wait(*, deadline: float) -> int | None ; proc.kill() -> bool
```

**F4: o que a interface garante.**
- `parent` não expõe send, write nem shutdown. Isso é contrato do binding revisto e confiável, não impossibilidade física: Python arbitrário e hostil no mesmo processo poderia escrever no fd.
- Não há sandbox. O namespace do controlador é confiável, como em todo o laboratório.

**Binding no main (L6), mesma forma do `WorkerSession._open`, sem mudar o SDK:**
- **`pair`:**
  - `socketpair(1, SOCK_STREAM)`, as duas pontas não herdáveis;
  - `recv_exact` via `RawChannel` público com `ResultDeadline(expires_at=deadline, clock=System.monotonic)`.
- **`stdin`:**
  - `System.pipe2(O_CLOEXEC)` com o literal Linux x86-64 `0o2000000`, no mesmo padrão de `SOURCE_FLAGS`;
  - depois `set_blocking(write_fd, False)`.
  - **R2-3, construção sem efeito e independente de plataforma:** `real_system()` liga `pipe2` a um wrapper estreito do módulo, `_pipe2(flags)`, no mesmo padrão de `_pause` e `_set_blocking`.
    - Só o corpo do wrapper procura e chama `os.pipe2`, que é exclusivo do Linux, e só quando o wrapper é invocado num lote nativo posterior.
    - Import e `real_system()` não consultam `os.pipe2`. No Windows de referência o atributo está ausente, observado pelo root só como atributo, sem chamada.
    - A ligação e o encaminhamento do wrapper são conferidos por fonte/AST. Todo teste com efeito usa `System.pipe2` fake.
    - O valor de `O_CLOEXEC` e os argumentos/env reais do `Popen` continuam exigindo prova nativa; o documento não os afirma como fato.
  - Assim as duas pontas nascem close-on-exec, e só a escrita do pai fica não bloqueante. O filho torna seu fd 0 não bloqueante por conta própria.
- **`spawn`:** `popen` com:
  - argv literal `[sys.executable, "-I", "-B", "-m", "maskgw.runtime.worker_process", child_fd, parent_pid, address_bytes, idle_ms]`;
  - `stdin=reader.fd` (o fd já possuído; nenhum pipe criado pelo Popen), `stdout/stderr=DEVNULL`;
  - env literal igual a `child_environment()`;
  - `close_fds=True`, `pass_fds=(child_fd,)`, `bufsize=0`.
- **Fds no filho:**
  - fd 0 é um dup do leitor (o dup2 do Popen limpa o close-on-exec só nessa cópia);
  - `child_fd` é herdado por `pass_fds`;
  - stdout/stderr apontam para devnull.
  - O escritor do pai é close-on-exec e não aparece em `pass_fds`, então nunca chega ao filho.
- **Resíduos não possuídos:** o Popen abre internamente o seu errpipe e o `/dev/null`. São do stdlib, close-on-exec e fechados pelo próprio Popen; não são fds do owner. O documento declara isso, sem alegar posse.
- **`write_all`:** escrita não bloqueante com `select`/`os_write` e prazo absoluto. Nada é escrito depois do prazo. Devolve `True` só com todos os bytes escritos.
- **`wait`:** `Popen.wait(timeout)` limitado. `TimeoutExpired` ou `OSError` dão `None`.
- **Metadado vs. ação física:** ler `sys.executable` e as constantes do perfil é metadado. `pipe2`, `popen`, `close`, `write`, `wait` e `kill` são ações físicas.
- **Sem import de `worker_process`:** o main não o importa. A igualdade do env é pinada em teste, e o filho recusa divergência com exit 1.

## 4. Fluxo do caso 24 (G2, após T4 fechado RELEASED)

### 4.0 Posse e regras gerais

O Owner não ganha campos novos. A tabela mostra onde cada recurso fica:

| Recurso | Owner do driver | Slot do main |
|---|---|---|
| token | `_session_token` | — |
| pontas do socket | `_endpoints` | `probe_parent`, `probe_child` |
| pontas do stdin | `_endpoints` | `probe_stdin_r`, `probe_stdin_w` |
| processo | `_handles` | `probe_process` |
| criação incerta | `_unknown` (`probe_pair`, `probe_stdin`, `probe_process`) | slot UNKNOWN |

- **R2-2, contagem exata:** são **quatro pontas**: as duas do socket (pai e filho) e as duas do stdin (leitor e escritor). O processo é o quinto **slot**, não uma ponta. Não há outro tipo de recurso.
- **Saída do owner:** uma ponta só sai do owner com fechamento confirmado (`close() is True`). Fechamento `False`, exceção ou desconhecido nunca conta.
  - "Owner retém tudo" significa: retém os recursos originais ainda **não resolvidos**. Uma ponta já fechada com sucesso não volta ao owner.
  - Processo e token ficam até o reap verificado e o `release` RELEASED.
- **Antes de alocar:** cada slot é reservado UNKNOWN; depois do retorno vira OWNED. Interrupção entre o retorno e a atribuição deixa UNKNOWN, sem limpeza fingida.
- **Relógio:** valores exatamente `int`/`float` e finitos. Qualquer outro valor é falha fechada.
- **Fase de abertura:** `t_open = clock`, `open_end = t_open + 12 s`.
  - Toda chamada da fase confere `clock < open_end` **antes** e **depois** do retorno.
  - Vencido em qualquer ponto: não há próximo I/O nem INIT; segue a limpeza §5.
  - Prazo não interrompe chamada bloqueada no kernel: o binding só limita esperas com `select`/`RawChannel`/`wait(timeout)`. Uma chamada presa fica coberta pela posse e pelo hold do main.

### 4.1 Cerca de discriminação EOF/idle (F1)

- **Base:** `t_pre = clock` lido **imediatamente antes** de chamar `writer.write_all`.
- **Desigualdade:** o filho só começa o idle depois de:
  1. receber o INIT inteiro;
  2. ver EOF no stdin, o que exige o `writer.close()` do pai, posterior a `t_pre`;
  3. conectar e enviar OPENED.

  Logo `inicio_idle > t_pre` e `fim_idle > t_pre + idle_s`, no mesmo CLOCK_MONOTONIC.
- **Cerca:** `fence = t_pre + idle_s − IDLE_MARGIN_S`, sempre abaixo do fim do idle.
- **Por que a v1 errava:** qualquer instante pós-retorno é só limite **superior** do fechamento real. Um retorno atrasado empurraria a cerca para depois do idle. A cerca é capturada uma vez e nunca é recalculada ou estendida.
- **Premissa nativa não provada:** pai e filho compartilham o CLOCK_MONOTONIC (mesmo container, mesma premissa do código atual).

### 4.2 Passos

0. **Chave da sonda (R2-1), antes de qualquer efeito físico:** reutiliza a construção fechada que o driver já usa em `open_session`, sem campo ou fonte nova.
   - `session_id = ids.session_id()` precisa ser `bytes` exatos de 16 bytes, ausente do mesmo conjunto `self.ids` do driver. Ele é inserido nesse conjunto antes de seguir; repetição ou tipo errado dá ABORT SESSION.
   - `key_G2 = SessionKey(session_id, bytes.fromhex(pure.DATASOURCE_ID[4:]), 2, pure.RECORD_REVISION)`. A validação do próprio `SessionKey` ocorre na construção.
   - Nenhuma chave ou sessão antiga é reutilizada.
   - O `nonce` do passo 7 é outro valor, vindo de `ids.nonce()`, com exatamente 32 bytes.
1. **Reserva, posse e adoção:**
   - `token = reserve_session(G2, W, P)` sob `ledger_call`, usando o ledger e o lock originais, já enraizados no owner desde `open_ledger`.
   - O token é atribuído a `owner._session_token` logo após o retorno da reserva e **antes** do `adopt`.
   - Depois, `adopt_session(token)` sob `ledger_call`.
   - Falha na reserva: ABORT LEDGER.
   - Interrupção durante a reserva ou a atribuição: o estado da reserva e do ledger fica incerto e retido, sem `release` inventado.
   - Falha na adoção: `retain(token)` e ABORT retido, sem efeito físico.
2. **Socket:** `pair()` e registro das duas pontas.
3. **Stdin:** `stdin()` e registro de leitor e escritor.
4. **Processo:** marca `probe_process`, depois `spawn(child, reader, parent_pid=guard.pid, address_bytes=W, idle_ms=30000)`, depois registro do processo.
   - Exceção: marca mantida, ABORT retido, sem kill.
5. **Fechar as cópias do pai:** `child.close()` e `reader.close()`. Cada um só sai do owner com `True`.
6. **GUARD_READY:** cabeçalho com kind `GUARD_READY` e tamanho ≤ 256 antes do corpo.
   - Exige `decode_guard == (proc.pid, guard.pid, W)`.
   - Senão: limpeza, sem INIT.
7. **Preparar o INIT:** `nonce = ids.nonce()` (exatamente 32 bytes); `expected = hmac(nonce, snapshots[2])`.
   - Pacote: `encode_init(SecretInit(key_G2, ResultLimits(1000, F), open_end, nonce, snapshots[2]))`, com o `key_G2` do passo 0.
8. **Enviar o INIT:** `t_pre = clock`, depois `writer.write_all(pacote, deadline=open_end)`, depois `writer.close()`.
   - Exige `True` nos dois e `clock < open_end` depois.
   - Senão: limpeza, sem ler OPENED.
   - `pacote` e `nonce` são apagados.
   - `fence` é calculada conforme §4.1.
9. **OPENED:** permite `{OPENED, ERROR}` com tamanho ≤ 256.
   - Exige `OPENED` e `compare_digest(decode_opened, expected)` dentro de `open_end`.
10. **READY e GO:** `ready(24)` e depois `accept(GO_CAP_S, fence)`. GO tardio dá IDLE_WINDOW, limpeza e ABORT.
11. **EOF:** `parent.close()`. Com `True`: `t_eof = clock`. Senão: limpeza §5.
    - Antes de esperar, captura-se uma vez `wait_end = min(t_eof + EOF_WAIT_S, fence)`.
    - Se `t_eof ≥ fence`: EXIT_LATE sem espera de EOF; o processo vai ao fallback §5.
12. **Espera:** `rc = proc.wait(deadline=wait_end)`, depois `t_ret = clock`.
    - Só `type(rc) is int`, nunca bool ou subclasse, conta como reap. Outro tipo vale como `None`.
    - Com rc int, `t_ret < wait_end` **e** `t_ret < fence`:
      - `rc == 0` → PASS;
      - senão → FAIL EXIT_NONZERO.
    - Com rc int, `t_ret ≥ fence` → FAIL EXIT_LATE (atraso em relação ao idle).
    - Com rc int, `wait_end ≤ t_ret < fence` → FAIL WAIT_LATE (atraso de fase, ainda antes da cerca).
    - rc `None` → fallback §5 → FAIL NO_EXIT, mesmo que o rc pós-kill seja 0.
13. **Liberação:** `release(token, CleanupConfirmation(...))` com fatos reais:
    - `processes` = rc int;
    - `pipes` e `handles` = todas as **quatro** pontas fechadas com `True`;
    - `threads` e `output` = `True`, porque a sonda não cria thread nem receiver.

    HELD dá ABORT retido. RELEASED limpa token, `_handles` e `_endpoints`.
14. **Resultado:** `RESULT{24}` (§6), depois ACK com `ACK_CAP_S` e sem janela.

Constantes lógicas novas: `OPEN_CAP_S = 12.0`, `EOF_WAIT_S = 10.0`, `KILL_REAP_S = 0.75`.

Reuso: W 256 MiB, P 33 MiB, idle 30000 ms, `IDLE_MARGIN_S`, `LOCK_S`, ledger do DRIVER-DESIGN §4.

Nenhuma cerca ou prazo é movido depois de uma falha para obter verde.

## 5. Limpeza de fallback, controles e hold

- **Ordem com processo existente e sem rc:**
  1. `proc.kill()`;
  2. `rc2 = proc.wait(deadline=clock + KILL_REAP_S)`;
  3. aceitar `rc2` só se `type(rc2) is int` e `clock` depois do retorno estiver antes desse prazo;
  4. então fechar todas as pontas ainda possuídas (escritor, leitor, filho, pai) e chamar `release` com fatos.
- `rc2` inválido ou tardio dá ABORT retido: o owner e os slots ficam com o token, o processo e as pontas ainda não fechadas com sucesso.
- **Kill nunca gera PASS,** nem EXIT_NONZERO, EXIT_LATE ou WAIT_LATE. Gera NO_EXIT ou o ABORT da fase.
- **Nada sai do owner sem fato positivo:** só `close() is True` ou rc int válido. Prazo vencido, `False` ou poll presumido nunca liberam.
- **Controles** (KeyboardInterrupt, MainSignal):
  - o driver não os captura; `run` deixa escapar com o owner do chamador intacto;
  - o main registra o controle e retém a raiz.
  - O predicado de `safe_exit` já exige todos os slots EMPTY. Os cinco slots novos entram nele sem exceção, então qualquer slot OWNED ou UNKNOWN leva ao hold e nunca à saída.
- **Falhas antes de READY:**
  - limpeza comprovada: `ABORT{24, CASE, SESSION, retained:false}`;
  - incerteza: `retained:true`.
  - Nenhum RESULT é emitido.

## 6. Eventos e resultado (mudança prospectiva explícita)

- Caso 24: `RESULT{case:24, kind:"EOF", verdict, reason, release:"RELEASED"}`.
  - `reason` é `null` no PASS, ou `EXIT_NONZERO`, `EXIT_LATE`, `WAIT_LATE` ou `NO_EXIT`.
  - Os demais campos ficam `null`.
  - Saem `PENDING` e `T5_PENDING`; nenhum campo novo; mesmo `next_seq`, frames e linhas.
- `SUMMARY.failed` deixa de conter sempre 24. `global_pass` continua `false`.
- ABORT reutiliza `SESSION`, `IDLE_WINDOW` e `LEDGER`.
- `DriverResult` não muda.

## 7. Plano de testes com fakes (RED primeiro; todos planejados, nenhum medido)

**Arquivos futuros:**
- `tests/test_oracle9_w1_driver_t5.py`: ledger real, codecs públicos, `children` fake roteirizado com log e relógio fake.
- `tests/test_oracle9_w1_main_t5.py`: `System` fake com `popen` e `pipe2` fakes.

**Driver:**
- **D5-1:** caminho positivo.
  - Ordem exata do log: reserve, adopt, pair, stdin, spawn, `child.close`, `reader.close`, GUARD, `t_pre`, `write_all`, `writer.close`, OPENED, READY, GO, `parent.close`, `wait`, release.
  - Zero kill e zero escrita no socket.
  - O pacote decodifica via `decode_init` com key G2, `snapshots[2]`, nonce de 32 bytes e `expires_at = open_end`.
  - O ledger volta a ter capacidade para T6.
- **D5-2:** composição até `T6_UNKILLED`, com SUMMARY sem 24 e 50 frames.
- **D5-F1 (oráculo independente do falso positivo da v1).** Roteiro com relógio fake:

  | Evento | Instante |
  |---|---|
  | `t_pre` | 1,0 |
  | retorno de `write_all`/`close` | 11,0 |
  | OPENED | 11,1 |
  | GO | 30,9 |
  | `parent.close` | 31,1 |
  | `wait` devolve rc 0 | 31,2 |

  Com `idle_s = 30` e margem 2, `fence = 29`. Esperado: GO depois da cerca → IDLE_WINDOW e ABORT. Uma variante com GO até 28 e `wait` em 31,2 → EXIT_LATE. **Nunca PASS.** O cálculo pós-retorno da v1 (`fence = 39`) faria esse roteiro passar, por isso ele é o RED.
- **D5-3:** rc 1 ou rc −9 sem kill → EXIT_NONZERO.
- **D5-4:** rc 0 com `t_ret ≥ fence` → EXIT_LATE.
- **D5-4b:** rc 0 com `wait_end ≤ t_ret < fence` (atraso de fase, antes da cerca) → WAIT_LATE.
- **D5-5:** wait `None`, kill, rc2 = 0 → NO_EXIT.
- **D5-6:** rc2 `None`, tardio ou exceção → RETAINED. O owner mantém, por identidade, o token, o processo e só as pontas cujo fechamento não foi confirmado.
- **D5-7:** rc `True`, ou subclasse de int → tratado como `None`, nunca PASS.
- **D5-8:** `pair`, `stdin` ou `spawn` levanta → UNKNOWN, RETAINED, sem kill nem release.
- **D5-9:** handshake:
  - GUARD com pid, ppid ou AS errado: nenhum INIT;
  - cabeçalho grande ou de outro kind: nenhum corpo lido;
  - OPENED com HMAC errado ou `ERROR`;
  - `write_all` ou `close` False.

  Em todos: limpeza, ABORT SESSION, `retained` conforme os fatos.
- **D5-10:** cada chamada da abertura com retorno após `open_end` (pair, stdin, spawn, closes, GUARD, nonce, `write_all`, OPENED) → nenhum próximo I/O, nenhum INIT depois de vencido.
- **D5-11:** `parent.close` False → fallback, ponta retida.
- **D5-12:** falha em `adopt` → `retain` sem efeitos físicos; `release` HELD → ABORT retido; T6 não roda.
- **D5-13:** KeyboardInterrupt no `wait` fake escapa. O owner do chamador mantém por identidade o token, o processo e as pontas ainda não fechadas com sucesso.
- **D5-14:** relógio devolve NaN, bool ou objeto → falha fechada.
- **D5-15:** RESULT com chaves e enum exatos, sem segredo nem canário.
- **D5-16 (R2-1), chave da sonda:**
  - O INIT decodificado traz `SessionKey` com `session_id` novo de 16 bytes, já inserido em `self.ids`, `datasource_id` igual a `bytes.fromhex(DATASOURCE_ID[4:])`, `generation` 2 e `record_revision` igual a `RECORD_REVISION`.
  - `ids.session_id` repetido de uma sessão anterior, com 15 ou 17 bytes, ou do tipo `bytearray` → ABORT SESSION antes de qualquer reserva ou efeito físico.
  - `ids.nonce` com 31 ou 33 bytes ou de tipo errado → nenhum INIT.
- **D5-17 (R2-1), posse do token antes da adoção:** um `adopt_session` fake que inspeciona o owner encontra `owner._session_token is token`. Interrupção no `adopt` → owner com token, sem `release`.

**Main:**
- **M5-1:** `real_system().popen is subprocess.Popen` e `real_system().pipe2 is _pipe2`, sem chamar.
  - AST: o `os.pipe2` aparece só dentro do corpo de `_pipe2`, que encaminha `flags` sem alterá-las.
  - Sem monkeypatch global, skip ou chamada nativa no Windows.
- **M5-2:** `pipe2` é chamado com `0o2000000` exato; as duas pontas são reservadas UNKNOWN antes e possuídas depois; só a escrita fica não bloqueante.
- **M5-3:** dentro do `popen` fake:
  - os slots `probe_parent`, `probe_child`, `probe_stdin_r` e `probe_stdin_w` já estão OWNED, e `probe_process` está UNKNOWN;
  - `stdin` é exatamente o fd do leitor;
  - `pass_fds == (child_fd,)` e `close_fds` é `True`;
  - o fd do escritor não aparece em nenhum argumento passado ao filho;
  - argv e env são exatos (env igual a `child_environment()`).
- **M5-4:** `popen` levanta, ou ocorre controle logo após o retorno → slot UNKNOWN, `safe_exit` falso, hold.
- **M5-5:** `write_all` com escrita parcial, EAGAIN e prazo; nada escrito depois do prazo.
- **M5-6:** `wait`: `TimeoutExpired` ou `OSError` dão `None`.
- **M5-7:** `pair` usa AF_UNIX literal 1 e pontas não herdáveis. `SessionIds.nonce` devolve 32 bytes.

**Migração deliberada (única mudança de oráculos antigos):**
- `T5_PENDING` é substituído pelo roteiro D5-1, injetado explicitamente no mundo D1; "SUMMARY ⊇ {24}" passa a depender do roteiro.
- `Ports` passa a ter 9 campos e `ids.nonce` entra nos fakes.
- `SYSTEM_FIELDS` vai de 20 para 22; `SLOTS` vai de 5 para 10; os imports do main ganham `subprocess`; os fakes de `System` ganham `popen`/`pipe2`.
- `DRIVER_SHA`/`BYTES` mudam no main e no teste do main.
- Nenhuma outra asserção é afrouxada.

**Sequência:**
1. Lote A, só testes do driver: RED medido e congelado pelo root.
2. Emenda do driver.
3. Lote B, só testes do main com o novo SHA: RED.
4. Emenda do main.

## 8. O que fakes provam e o que fica para o Oracle nativo

- **Depois de medidos, os testes planejados só poderão mostrar,** sob fakes: ordem, posse antes do efeito, cercas e prazos fechados, recusa de kill como PASS, retenção, eventos e codecs públicos.
- **Não poderão mostrar:**
  - entrega de EOF e EOF no stdin pelo kernel;
  - herança real de fds e close-on-exec;
  - aceitação de env e guard pelo filho instalado;
  - returncode e waitpid reais;
  - relógio monotônico comum;
  - fechamento dos backends no PG. O host deve conferir zero backends do papel em janela finita (NativePlan §12).

## 9. Pendências e riscos declarados

- A premissa de CLOCK_MONOTONIC comum entre pai e filho não foi medida.
- Exit 0 por EOF depois da cerca é FAIL conservador (EXIT_LATE).
- Os fds internos do Popen (errpipe, `/dev/null`) não são do owner. A herança dos fds depende do stdlib e do kernel.
- A sonda repete só a abertura pública do `WorkerSession`. A divergência é pinada em teste por argv e env literais.
- Sem execução física até a revisão desta proposta, dos testes/RED e das pré-condições nativas.
- B1, B2, D-090 gate 2, C1, ingressos, IDE, MCP e produção continuam abertos.
