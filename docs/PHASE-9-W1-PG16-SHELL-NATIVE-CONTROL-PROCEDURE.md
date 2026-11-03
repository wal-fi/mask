# Controles nativos benignos — procedimento prospectivo (não executado)

Data: 2026-11-02, America/Sao_Paulo. Documento sob a delegação geral vigente e
revisão do root; não é aprovação individual do usuário nem concede permissão
nova. Programador Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
`claude-opus-5-5`, esforço `medium`. Nada aqui foi executado: nenhum nonce,
raiz, comando materializado, script, efeito nativo ou resultado.

Fontes relidas nesta etapa (texto apenas): entrada
`docs/poc/pg16_shell_native_control_entry.py`, orquestrador
`docs/poc/pg16_shell_native_control.py` (trechos de persistência, publicação
e `_run`), constantes do chamador `docs/poc/pg16_shell_admission_host.py`,
PENDING, CHECKPOINT, proposta e validação da identidade. ENTRY-DESIGN,
ENTRY-VALIDATION, CONTROL-DESIGN, CONTROL-VALIDATION, adaptador e backend
foram lidos em chamadas anteriores desta mesma sessão. Nenhum `.venv`,
configuração, binário ou segredo foi lido.

## 1. Tentativa de identidade e emenda proposta

Histórico preservado: a sonda de identidade foi executada uma única vez pelo
root (`PHASE-9-W1-PG16-SHELL-NATIVE-IDENTITY-VALIDATION.md`). Rótulo final da
tentativa consumida: **LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED**. Vida e
parentesco amostrais e saída natural 0 foram conferidos; o PASS_SAMPLED
estrito da proposta continua **não comprovado**, porque o tool entrega texto
agregado, sem bytes brutos do pipe nem stderr separado. Pela regra da
proposta, esse rótulo aborta avanço nativo. Não há rerun nem wrapper.

**Emenda prospectiva aceita pelo root sob delegação:** para o lote futuro
dos controles, os eventos vistos no texto agregado servem só para
monitoramento. Não se alega pipe bruto nem stderr independente. Qualquer
texto visível inesperado, extra ou não canônico desqualifica aprovação; se a
posse estiver desconhecida nesse momento, a situação é só monitorada. A
aprovação dos controles vem exclusivamente dos critérios de disco e de saída
da seção 6. A emenda não muda o rótulo da tentativa anterior, não cria nova
sonda e, sozinha, não fecha gate nativo nem de produção.

**Decisão prospectiva do root, sob delegação (registrada em
PROCEDURE_FIXES_V2):** eventos agregados apenas para monitoramento são
aceitáveis para este procedimento futuro de controles. Não é PASS retroativo
da tentativa de identidade consumida, cujo rótulo segue
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED, e não é aprovação individual do
usuário. A revisão documental final está registrada na seção 9; as
pré-condições de execução continuam pendentes.

## 2. Pré-checagem necessária (futura, somente leitura)

1. HEAD igual ao commit revisado, sincronizado com origin, árvore rastreada
   limpa; nenhum Claude CLI, print ou outro escritor ativo; tarefa histórica
   Disabled sem próximo horário.
2. SHA-256 completos, conferidos pelo root imediatamente antes:
   - entrada `docs/poc/pg16_shell_native_control_entry.py`:
     `356d22914c21c7fefb195b9471b12591cd7120deb152524104ff3b4559fbf0c6`;
   - orquestrador `docs/poc/pg16_shell_native_control.py`:
     `b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496`;
   - adaptador `docs/poc/pg16_shell_native_control_win32.py`:
     `eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407`;
   - backend `docs/poc/pg16_shell_admission_win32.py`:
     `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726`;
   - chamador `docs/poc/pg16_shell_admission_host.py`:
     `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7`.
   A entrada fixa o orquestrador; o orquestrador fixa chamador e adaptador; o
   adaptador fixa o backend. Estado de 16 campos e fontes consumidas fixos.
3. Pré-requisitos futuros, **não lidos nem medidos nesta etapa**: runtime
   Windows/CPython 3.11.3 `-I -B`, e pin do launcher
   `bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82`, que o
   orquestrador confere a cada caso pelo `_launcher_pin` do chamador (leitura
   limitada do binário durante a execução, não antes).
4. `<NONCE32>`: 32 hexadecimais minúsculos, nascido só numa proposta de
   execução revisada; não concede permissão. Nomes esperados, conferidos
   ausentes pelo root (somente esses dois caminhos, sem enumeração ampla):
   - privado: `C:\Users\w.filho\AppData\Local\Temp\maskgw-pg16-native-control-v1-<NONCE32>`
     (constantes `TEMP` e `PRIVATE_PREFIX` do orquestrador);
   - público: `docs\poc\evidence\pg16-native-control-<NONCE12>`, com
     `<NONCE12>` os 12 primeiros caracteres (`PUBLIC_PREFIX`).
   `TEMP` e `docs\poc\evidence` existentes como diretórios reais.
5. Nenhum controlador vivo, owner retido ou raiz consumida anterior deste
   lote (o root confere pelos próprios registros; a entrada nunca foi
   invocada de verdade até aqui).

Vínculo de consumo: a partir do momento em que o orquestrador cria o
diretório privado, o nonce está consumido para qualquer desfecho; nunca é
reutilizado, apagado ou repetido. Recusas da entrada anteriores a isso não
criam diretório, mas o nonce também não é reaproveitado: uma nova tentativa
exige nova proposta revisada. A tentativa de identidade é outra execução já
consumida e não serve a este lote.

## 3. Modelo de invocação (PowerShell 5.1, não invocado)

O diretório de trabalho do exec é o repositório. Sem `Set-Location`, base64,
arquivo de comando, `Start-Process`, redirecionamento, tty, timeout ou kill.

```powershell
$controlNonce = '<NONCE32>'
if ($controlNonce -cnotmatch '^[0-9a-f]{32}$') { exit 64 }
& '.\.venv\Scripts\python.exe' -I -B '.\docs\poc\pg16_shell_native_control_entry.py' $controlNonce
exit $LASTEXITCODE
```

- Com o placeholder literal, a guarda sai com 64 sem lançar nada. Só a
  substituição revisada por um nonce válido permite o lançamento.
- Exec em primeiro plano, mesmo harness, stdout como pipe, sem tty,
  `yield_time_ms` 10000; esperas posteriores de polling no mesmo processo de
  exec, cada uma de no máximo 30 s; código de saída preservado por
  `exit $LASTEXITCODE`. Nenhum retry, nenhum segundo lançamento.
- O root analisou este bloco com ParseInput: 0 erros, sem execução. O
  programador não o executou nem parseou; o parse não é resultado nativo.

## 4. Eventos, observação e monitoramento

Esquema da entrada (código relido): cada evento é JSON canônico
(`sort_keys`, separadores `,`/`:`), ASCII, uma linha, `kind =
MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1`:

| Evento | Chaves exatas |
|---|---|
| `IDENTITY` | `kind`, `event`, `nonce12`, `controller_pid`, `parent_pid` |
| `FINAL` | `kind`, `event`, `nonce12`, `controller_pid`, `code`, `outcome`, `refusal` |
| `PARKED` | `kind`, `event`, `nonce12`, `controller_pid`, `reason`, `retained` |

Ordem esperada no caso normal: `IDENTITY` e depois exatamente um de
`FINAL`/`PARKED`. Exceções válidas pelo código da entrada, sem `IDENTITY`:

- `FINAL` código 2 em S0 (`ENTRY_ARGV`, com `nonce12` nulo — único caso de
  nonce nulo) ou S1 (`ENTRY_SOURCE`);
- `FINAL` código 2 em S2 (`ENTRY_LOAD`, `ENTRY_INTERRUPTED`) ou S3
  (`ENTRY_ARM`), emitido só com a lista original confiável e vazia;
- `PARKED` antes de S3 (por exemplo `UNKNOWN_REGISTRY` na carga).

Nesses casos `controller_pid` nulo é válido (o PID só é atribuído após o par
validado em S3; se a escrita de `IDENTITY` falhar depois disso, `FINAL` pode
trazer `controller_pid` sem `IDENTITY` visível). Conferir `nonce12` igual ao
nonce revisado quando não nulo; PIDs inteiros exatos (não `bool`),
`0 < v < 2**32`, distintos; `code`/`outcome`/`refusal`/`reason`/`retained`
em conjuntos e tipos fechados. Linha quebrada ou incompleta nunca é
completada nem reconstruída: só formas observadas inteiras e canônicas
contam; o resto é texto inesperado (seção 1).

Ordem do observador:

1. Anotar `T0`; lançar; ler o texto agregado a cada yield.
2. Após `IDENTITY`, amostras CIM somente leitura dos dois PIDs, com
   `ProcessId`, `ParentProcessId`, `Name`, `CreationDate` (mesmo filtro da
   proposta de identidade): `controller_pid` vivo, `CreationDate` estável,
   pai igual a `parent_pid`. Nomes são forma, não proveniência.
3. `FINAL` não é veredito: a entrada pode emitir `FINAL` antes de uma
   rechecagem que estacione. Só a saída terminal do exec, com código igual
   ao `FINAL`, encerra a observação do processo.
4. `PARKED`, ausência de evento, pipe quebrado, texto inesperado, app ou
   sessão encerrando: monitorar apenas, por amostras CIM esparsas. Nunca
   encerrar o controlador para obter resultado do exec, nunca lançar outro,
   nunca enviar EOF ou controle de console, sem timeout.
5. Após a saída: amostra pelos mesmos PIDs; instância antiga ausente ou PID
   reutilizado com outra `CreationDate`.

PIDs, caminhos, valores de ambiente, linhas de comando e texto de exceção
nunca entram em evidência pública, Git ou resumo; PIDs ficam só locais. As
linhas de evento não provam cleanup.

## 5. Desfechos e códigos

Fixos e em ordem: `NORMAL`, `TERMINATE`, `LAST_CLOSE` (todos efeitos
nativos futuros, não executados). Códigos da entrada:

| Código | Rótulo | Significado |
|---|---|---|
| 0 | `APPROVED` | `run` retornou descritor com lote `APPROVED`; registro original vazio |
| 1 | `REJECTED` | descritor com lote `REJECTED` (primeiro caso reprovado encerra; demais `NOT_RUN`) |
| 2 | `REFUSED` | recusa fechada `ENTRY_*` ou `CONTROL_*`; com diretório privado criado, nonce consumido |
| 4 | `COMMIT_INDETERMINATE` | posse resolvida; rename final indeterminado |
| 5 | `INTERRUPTED` | interrupção com owners provados `CLOSED`; publicação desconhecida |
| — | `PARKED` (`HELD`, `INTERRUPTED`, `UNKNOWN_REGISTRY`, `INTERNAL`) | posse retida/incerta; sem saída |
| — | `UNKNOWN` | término externo, encerramento do app/sessão, logoff, reboot ou falha fatal |

`PARKED` mantém namespace e lista original; só observação. Não existe
interface de recuperação. Orçamentos de prazo do orquestrador (60/10 s,
1200/200 turnos, READY 10 s/200 turnos) são decisões entre chamadas, não
limites absolutos de chamadas do SO, desligamento ou runtime.

## 6. Aceitação (contrato real do orquestrador)

Pré-condições: saída terminal observada com código igual ao `FINAL`;
eventos inteiros e canônicos conforme a seção 4, sem texto extra visível;
amostras CIM ligando `controller_pid`/`parent_pid` enquanto vivo. Eventos e
hashes conferidos sozinhos não estabelecem a semântica aninhada nem cleanup.

Esquemas fechados, fixados antes de qualquer leitura futura (do código do
orquestrador):

- Público: diretório com exatamente `summary.json` e `transport.json`.
- `transport.json`: JSON canônico, ASCII, exatamente 5 chaves `kind`,
  `nonce`, `outcome`, `summary`, `private`; `kind =
  MASKGW_PG16_NATIVE_CONTROL_TRANSPORT_V1`; `summary` exatamente
  `name = summary.json`, `bytes`, `sha256`; `private` lista ordenada por
  nome, cada item exatamente `name`, `bytes`, `sha256`.
- `summary.json`: exatamente 10 chaves `kind`, `nonce`, `outcome`, `scope`,
  `admission_3s`, `cases`, `host_sha256`, `adapter_sha256`,
  `backend_sha256`, `launcher_sha256`; `cases` com 3 itens, cada um com
  exatamente as 13 `CASE_KEYS` (`case`, `outcome`, `rejection`,
  `exit_code`, `framing`, `total_processes`, `terminated`, `ready`,
  `inner_closed`, `audit_integral`, `audit_entries`, `terminate_calls`,
  `seconds`).
- Em todos: hashes hexadecimais minúsculos de 64 caracteres, inteiros `int`
  exatos e nunca `bool`, sem chaves duplicadas, NaN/Infinity ou extras.
- Nomes privados permitidos (lista branca), relativos ao diretório privado:
  `APPROVED` exige exatamente 11 —
  `case-1/`, `case-2/` e `case-3/` cada um com `invocation.json`,
  `supervision.json` e `local-stdout.bin`, mais `case-3/snapshot.json` e
  `case-3/audit.json`. `REJECTED` usa o prefixo realmente executado: 3
  (só caso 1), 6 (casos 1–2) ou 11 (casos 1–3) arquivos; nunca é aprovação.
- Nunca concatenar nomes arbitrários da tabela, seguir links, reparse
  points ou ADS, aceitar `..`, separadores inesperados ou caminhos
  absolutos, nem ler conteúdo desconhecido. Toda leitura é limitada.

**Escolha do root:** verificador privado pequeno, com testes fake e
adversariais e revisão própria **antes** da execução nativa; não lista manual
improvisada. Nenhum código de verificador existe ou é escrito agora. Contrato
futuro mínimo do verificador, somente leitura:

1. esquemas e listas brancas acima, conjunto exato de arquivos, tamanho e
   SHA de cada arquivo privado e do summary;
2. `invocation.json` de cada caso: nonce, argv fixo do caso, pins e limites
   iguais aos do orquestrador;
3. `supervision.json`: `owner_state = CLOSED` e fatos coerentes com o caso;
4. `local-stdout.bin`: bytes e framing exatos das linhas fixas
   (`MASKGW-NATIVE-CONTROL-NORMAL`/`MASKGW-NATIVE-CONTROL-READY`) conforme o
   caso;
5. caso 3: `snapshot.json` e `audit.json` coerentes com o summary
   (`inner_closed`, integridade, contagem de entradas, zero terminate);
6. pins de fonte congelados nos campos do summary.

`host.strict` do chamador verifica só sintaxe JSON estrita; não substitui
esse contrato. Mesmo com o verificador, a aceitação exige saída terminal,
vínculo CIM e estes fatos; nenhum gate de produto é afrouxado.

Código 1 com projeção conferida é resultado REJECTED válido, mas não aprova
os controles. Códigos 2/4/5: só verificação somente leitura do que existir,
sem retry. Sem mutação posterior: nada é editado, apagado ou reescrito após a
execução; diretório parcial ou `.next` em falha fica consumido.

Privacidade: brutos privados ficam só no próprio Temp desta máquina e nunca
são emitidos em bruto para ferramentas, conversa ou Git; só a projeção
pública aprovada (summary/transport) pode entrar no Git, após revisão.
Revisar parser ou verificador não é resultado nativo.

## 7. Risco do launcher da venv (fonte, não medido)

O root consultou o código-fonte do CPython v3.11.3
(https://raw.githubusercontent.com/python/cpython/v3.11.3/PC/launcher.c,
variante `VENV_REDIRECT` e `run_child`): o launcher cria e configura um Job
Object com KILL_ON_JOB_CLOSE e SILENT_BREAKAWAY_OK, inicia o filho e tenta
`AssignProcessToJobObject`, sem que o retorno ignorado seja evidência de
associação local. Minha afirmação anterior de que ele "coloca" o filho no job
foi forte demais e fica corrigida: não está provado.

Se, localmente, a associação ocorrer e o fechamento do último handle se
aplicar, a perda do launcher pode afetar o controlador; isso é condicional e
não medido, e cairia em UNKNOWN. A interação de SILENT_BREAKAWAY_OK com a
herança e com OUTER/INNER dos processos filhos é não medida. Nenhuma limpeza
é alegada. Win32_Process
(https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-process)
continua valendo para amostras: `ParentProcessId` pode ser de processo
terminado/reutilizado, por isso `CreationDate`.

## 8. Gates antes da primeira execução nativa e pontos abertos

Estado dos gates:

1. Emenda da seção 1 e procedimento: revisão documental concluída pelo root
   (seção 9), somente como contrato prospectivo, sem liberação de execução.
2. Bloco da seção 3: ParseInput com 0 erros **medido pelo root**, sem
   execução; o programador não o executou nem parseou.
3. Verificador privado da seção 6: escolhido pelo root; **não implementado
   nem revisado**.
4. Proposta de execução com nonce exato, registro da pré-checagem e pins de
   runtime/launcher: **não preparados nem medidos**.
5. Nenhum efeito nativo é autorizado por este documento; risco de job do
   launcher é apenas inferência condicional de código-fonte (seção 7), sem
   afirmar associação real.

Abertos: comportamento nativo de jobs aninhados, KILL_ON_JOB_CLOSE, morte por
último handle, entrega de sinais, sobrevivência a encerramento do app,
proveniência do binário, teto 512 da auditoria (`AUDIT_INVALID` possível),
pin do launcher não atômico, leituras implícitas do runtime, segunda
interrupção herdada do backend, `FINAL` anterior a estacionamento.

Autoridade: nenhuma aprovação individual por lote é necessária sob a
delegação vigente, e este documento não concede permissão nova.

Ambiente: este é o laboratório de controle nativo Windows desta máquina (o
orquestrador fixa `TEMP` em `C:\Users\w.filho\AppData\Local\Temp`). Ele é
distinto do destino final do produto já aceito pelo usuário — Docker com
Oracle Linux 9.8 nesta mesma máquina —, que não muda e não é reperguntado.
Este procedimento não infere mudança de destino; outro ambiente ou usuário
para o laboratório exigiria novo contrato. Native 3 s NOT_MEASURED, entry_gate
NOT_EVALUATED; Gateway indisponível e B1/B2/D090/C1/SQL/produção abertos.

## 9. Revisão final documental — root, 2026-11-02

CLI72698 entregou a primeira redação. Root encontrou lacunas nas formas de
eventos antes de S3, schemas/nomes privados e conferência de evidências.
CLI87209 repetiu a solicitação anterior por erro do revisor ao substituir
um prompt multilinha: só fontes citadas e uma frase de privacidade mudaram.
Não se atribui essa repetição ao programador. O envio corrigido usou um
marcador único conferido e um template com prompt em uma linha.

CLI4685 terminou0; releu PENDING/CHECKPOINT e corrigiu os seis itens pedidos,
somente neste documento. Root confrontou o resultado com as fontes fixas e
repetiu ParseInput: um bloco, zero erros, nunca executado. Sem P1/P2
documental remanescente nesta revisão; contrato aceito apenas para o trabalho
prospectivo, sob delegação, sem inventar voto individual do usuário.

Próximo incremento seguro: desenho detalhado e implementação revisada do
verificador privado, com fixtures e adversários, antes da proposta/rodada
nativa. Este documento não substitui esses gates nem autoriza lê-los como
fechados. Nenhum programa, fonte consumida ou estado de16campos mudou.

## 10. Estágios da coleta posterior — prospectivo, 2026-11-03

Acréscimo documental (as seções 1–9 ficam como estão). Sob a delegação geral:
ela cobre o trabalho rotineiro autônomo, mas as proibições explícitas e as
permissões efetivas das ferramentas continuam valendo; não há aprovação
individual inventada, e procedimento e comando nativos exatos exigem revisão
posterior antes de qualquer efeito. Nenhuma raiz, nonce ou comando foi
criado.

Correção de um plano anterior do programador (CLI98605), que dizia que a
sonda de identidade não fora feita: ela **foi executada uma vez em
2026-11-02 e está consumida**, com rótulo final estrito
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED (seção 1 e CHECKPOINT). Sem rerun nem
promoção posterior do rótulo.

Inventário pinado conhecido, além da seção 2: verificador `b3755d49…`
(`docs/poc/pg16_shell_native_control_verify.py`); coletor
`1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52` (20571
bytes); backend de coleta
`ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a` (22315
bytes); composição pinada anterior `109ab960…` (4291 bytes), preservada
como dado e no Git. Revisão aditiva atual:5373bytes,
`37b098cf604099a8aa9e64c4a3569ce06c6fe389188eba9a2b46478b04a8285e`.
Fábrica privada revista pelo root somente com fakes:29próprios e
748relacionados aprovados; evidência em COLLECT-FACTORY-VALIDATION.
Isso não cria nem chama uma fábrica nativa.

Ordem, cada estágio com recusa ou PARK:

1. **Autoridade e pré-checagem (seção 2)**, mais os pins acima conferidos
   pelo root imediatamente antes. Falta ou divergência: nada roda.
2. **Controles (seções 3–6)**: uma execução da entrada por nonce. `FINAL` 0 ou
   1 com saída terminal e aceitação da seção 6 seguem; 2 encerra o lote; 4, 5,
   `PARKED` ou UNKNOWN bloqueiam até revisão, sem coleta.
3. **Captura das fontes da coleta**: leitura limitada, `lstat` regular sem
   reparse, de composição, coletor e backend; cada um vira um único `bytes`,
   o mesmo objeto do SHA e do `exec`, sem releitura nem import do checkout.
   Divergência: recusa pura, antes de qualquer namespace.
4. **Coleta**: um processo, uma chamada à composição, sem retry. A `api` real
   viria de uma fábrica sobre o namespace pinado já executado; a chamada de
   `_load_native` por ela é ativação nativa e exige revisão própria.
5. **Decisão de saída**: só com quiescência comprovada sobre os **objetos
   originais**, capturados por identidade: o `_ATTEMPTS` original com seu
   único registro; `_ACTIVE` e `_POISON` originais vazios; `_retained` e
   `_open` originais do backend vazios. Contêineres vazios substituídos, ou
   igualdade `==` com um vazio, não provam nada. Qualquer outro estado: PARK
   em primeiro plano, pegajoso, retendo esses objetos; sem limpeza, retry ou
   saída.
6. **Conferência**: rótulo e hashes da coleta confrontados com o `FINAL` e a
   aceitação da seção 6; nada promove produção.

O `_LIVE` da entrada cobre só os owners do orquestrador; **não** cobre os
handles da coleta. O futuro chamador da coleta precisa da sua própria
retenção pegajosa em primeiro plano dos objetos do item 5; nenhum código de
chamador é escrito neste lote.

Lacunas: chamador da coleta e uma fábrica nativa real (não criada);
revisão privada com fakes não fecha os gates nativos; conversões do
`_NativeApi` e ABI no CPython alvo; perfil da âncora (NTFS local, não marcado
como mídia removível, não remoto, sem atestar hardware); suporte das classes
e `NtClose` reais; janelas de console e término externo herdadas. Runtime
atual só Windows CPython 3.11.3; destino final Docker Oracle Linux 9.8.
Native 3 s NOT_MEASURED, entry_gate NOT_EVALUATED; gates de produção abertos.
