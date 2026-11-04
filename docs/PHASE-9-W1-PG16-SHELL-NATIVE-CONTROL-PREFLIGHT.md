# Pré-checagem e proposta operacional — controles benignos e coleta (documento)

Data: 2026-11-04. Documento sob a delegação geral (trabalho rotineiro
autônomo; revisão em etapas e permissões efetivas das ferramentas antes de
efeitos continuam valendo); não é aprovação individual do usuário nem
autoriza efeito. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Nada aqui foi executado: nenhum nonce, raiz, comando materializado ou leitura
de runtime/config/binário. Usa só os dois arquivos de entrada existentes; nenhum
código novo é necessário para este lote.

Leituras do programador (fonte real): orquestrador
`docs/poc/pg16_shell_native_control.py` linhas 1–492; chamador
`docs/poc/pg16_shell_admission_host.py` linhas 1–80 e 395–490; PROCEDURE
seções 1–6 e 10–11; PENDING e CHECKPOINT (topo). Entrada `356d` e entrada da
coleta lidas em chamadas anteriores da sessão. Fatos fornecidos pelo revisor
e não relidos aqui: tamanhos das fontes (seção 2), a checagem de runtime e o
`_launcher_pin` do chamador.

## 1. Correção de tempo (revisor, conferida no código)

Minha afirmação anterior de que o lote terminaria antes do primeiro yield
estava errada. Em `_lifecycle`, um `READY` bem-sucedido só marca `ready` e
deixa `reason` nulo; depois roda `host._supervise`, que só termina quando
`now - start >= DEADLINE_SECONDS` (60,0 s) ou por outro motivo. O caso
TERMINATE aprovado exige `DEADLINE`; LAST_CLOSE fecha o INNER cedo. Um lote
nominal completo oferece, portanto, oportunidade de amostragem depois de
10 s; não é garantia absoluta de parede. Recusas e rejeições rápidas podem
terminar antes do primeiro yield.

## 2. Inventário de fontes (SHA-256 completos)

| Arquivo | SHA-256 | Bytes |
|---|---|---|
| `docs/poc/pg16_shell_native_control_entry.py` | `356d22914c21c7fefb195b9471b12591cd7120deb152524104ff3b4559fbf0c6` | 15580 |
| `docs/poc/pg16_shell_native_control.py` | `b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496` | 30055 |
| `docs/poc/pg16_shell_native_control_win32.py` | `eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407` | 15373 |
| `docs/poc/pg16_shell_admission_win32.py` | `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726` | 31948 |
| `docs/poc/pg16_shell_admission_host.py` | `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7` | 33234 |
| `docs/poc/pg16_shell_native_control_verify.py` | `b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10` | 24616 |
| `docs/poc/pg16_shell_native_control_collect.py` | `1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52` | 20571 |
| `docs/poc/pg16_shell_native_control_collect_win32.py` | `ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a` | 22315 |
| `docs/poc/pg16_shell_native_control_collect_pinned.py` | `37b098cf604099a8aa9e64c4a3569ce06c6fe389188eba9a2b46478b04a8285e` | 5373 |
| `docs/poc/pg16_shell_native_control_collect_entry.py` | `3d309771f5b33151aaf8773bdc86fbca57a1d1777ea2620848133ad1129c9e4b` | 26337 |
| launcher `.venv/Scripts/python.exe` (pin do chamador `PYTHON_SHA`) | `bfff517165ad6d1f3bf02d1782eaf7588fb7c20cd78d1c81788c4444e7bc5d82` | não lido |

Os dez tamanhos e SHA-256 das fontes Python foram medidos pelo root em
2026-11-04 por leitura exata do texto-fonte; todos os SHA-256 conferem com
esta tabela. O binário do launcher **não** foi lido agora; seu pin vem do
chamador. Commit de código base: `33b5e44`. A proposta publicada
será um commit **descendente só de documentação**; o pin `<EXPECTEDHEAD>` é
esse descendente, conferido pelo root com diff `33b5e44..<EXPECTEDHEAD>`
restrito a `docs/*.md` (nenhum `.py`). Este documento não contém o próprio
hash, para não ser autorreferente.

## 3. Pré-checagem ordenada (futura, somente leitura; nada lido agora)

1. Git: HEAD igual a `<EXPECTEDHEAD>`, sincronizado com origin, árvore
   rastreada limpa, diff desde `33b5e44` só documental.
2. Nenhum Claude CLI, print ou outro escritor ativo; tarefa histórica
   Disabled, sem próximo horário; nenhum controlador ou coleta anterior vivo.
3. SHA-256 de cada fonte da seção 2 pelos caminhos exatos, imediatamente
   antes de cada execução (controles antes do 1º exec; as três fontes da
   coleta e a entrada da coleta antes do 2º).
4. Diretórios reais, sem reparse: `C:\Users\w.filho\AppData\Local\Temp` e
   `docs\poc\evidence`. Ausentes, só estes dois caminhos derivados do nonce:
   `...\Temp\maskgw-pg16-native-control-v1-<NONCE32>` e
   `docs\poc\evidence\pg16-native-control-<NONCE12>`.
5. Runtime e launcher: **não lidos neste documento**. Guardas já internos ao
   código: o chamador fixa `PYTHON = REPO/.venv/Scripts/python.exe` e
   `PYTHON_SHA` acima, com leitura limitada a `LAUNCHER_LIMIT` (1 MiB)
   conferida pelo `_launcher_pin` antes do início de cada filho (fato do
   revisor); o perfil `win32-3.11.3-isolated-nobytecode-optimize0` e o código
   `CONTROL_RUNTIME` recusam runtime divergente (fato do revisor). O root
   pode, se quiser, conferir a versão do próprio venv numa etapa revisada à
   parte, sem ler configuração.
6. Nonce: 32 hex minúsculos, gerado só na proposta revisada; um por lote,
   consumido para qualquer desfecho a partir da criação do diretório
   privado; nunca reutilizado nem repetido.

## 4. Ações e modelos de comando (PowerShell 5.1; placeholders apenas)

Tipos de ação do lote: leituras Git/hash/diretório (pré-checagem); **um**
exec dos controles; amostras CIM somente leitura; **um** exec da coleta
(primeira chamada real de API nativa de leitura); leitura dos rótulos de
saída. Sem tty, redirecionamento, timeout, kill, `Start-Process`, arquivo de
comando ou base64. Exec em primeiro plano, `yield_time_ms` 10000, polling no
mesmo exec com esperas de no máximo 30 s. As duas chamadas exec do root usam
`login: false`, para suprimir o texto de perfil do PowerShell: o root mediu
um marcador de shell sem texto extra só com `login: false` (não é atestação
de runtime nem nativa); chamadas pelo alias do Claude mantêm o perfil.

Controles:

```powershell
$expectedHead = '<EXPECTEDHEAD>'
$controlNonce = '<NONCE32>'
if ($expectedHead -cnotmatch '^[0-9a-f]{40}$') { exit 64 }
if ($controlNonce -cnotmatch '^[0-9a-f]{32}$') { exit 64 }
if ((& git rev-parse HEAD) -cne $expectedHead) { exit 65 }
& '.\.venv\Scripts\python.exe' -I -B '.\docs\poc\pg16_shell_native_control_entry.py' $controlNonce
exit $LASTEXITCODE
```

Coleta (só para um candidato terminal da seção 6, mesmo nonce, novo exec):

```powershell
$expectedHead = '<EXPECTEDHEAD>'
$controlNonce = '<NONCE32>'
if ($expectedHead -cnotmatch '^[0-9a-f]{40}$') { exit 64 }
if ($controlNonce -cnotmatch '^[0-9a-f]{32}$') { exit 64 }
if ((& git rev-parse HEAD) -cne $expectedHead) { exit 65 }
& '.\.venv\Scripts\python.exe' -I -B '.\docs\poc\pg16_shell_native_control_collect_entry.py' $controlNonce
exit $LASTEXITCODE
```

Com placeholders literais, as guardas saem com 64 sem lançar nada. Nenhum
bloco foi executado ou parseado pelo programador; o root pode parseá-los sem
invocar. O nonce só nasce depois da proposta revisada e nunca é autoridade.

## 5. Fluxos de eventos

Controles (`MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1`): `IDENTITY`
(`nonce12`, `controller_pid`, `parent_pid`), `FINAL` (`nonce12`,
`controller_pid`, `code`, `outcome`, `refusal`), `PARKED` (`nonce12`,
`controller_pid`, `reason`, `retained`); formas sem `IDENTITY` conforme
PROCEDURE seção 4.

Coleta (`MASKGW_PG16_NATIVE_COLLECT_ENTRY_V1`): `IDENTITY` (`nonce12`,
`controller_pid`, `parent_pid`), `FINAL` (`nonce12`, `controller_pid`,
`code`, `outcome`, `reason`, `summary_sha256`, `transport_sha256`; hashes só
em 0/1), `PARKED` (`nonce12`, `controller_pid`, `reason` em `RETAINED`,
`UNKNOWN_CUSTODY`, `INTERRUPTED`, `INTERNAL`). Códigos 0 `VERIFIED_APPROVED`,
1 `VERIFIED_REJECTED`, 2 `REFUSED`, 5 `INTERRUPTED`.

Em ambos: JSON canônico ASCII, uma linha; texto agregado só para
monitoramento; `FINAL` não é veredito sem a saída terminal com o mesmo
código; linha quebrada nunca é reconstruída.

## 6. Observação CIM e matriz de aceite

Exigência original mantida para **aprovar controles**: depois de `IDENTITY`,
enquanto o exec não terminou, amostras CIM somente leitura dos dois PIDs
(`ProcessId`, `ParentProcessId`, `Name`, `CreationDate`), `CreationDate`
estável e pai igual; após a saída, instância antiga ausente ou PID
reutilizado com outra `CreationDate`. Sem essas amostras não há aprovação.

Nenhum aceite de disco é alegado antes da coleta. Ordem do aceite:

1. **Candidato terminal dos controles**: `FINAL 0` ou `1` com fluxo coerente
   (eventos inteiros e canônicos, sem texto extra), saída terminal real com o
   mesmo código e ausência pós-saída. É só candidato provisório.
2. **Uma** coleta somente leitura é permitida para esse candidato, com o mesmo
   nonce, sem retry.
3. Rótulo final, decidido só **depois** da coleta:

| Controles | Coleta | Rótulo final |
|---|---|---|
| candidato `FINAL 0` **com** amostras CIM vivas conferidas | `VERIFIED_APPROVED`, hashes públicos exatos e aprovação semântica do verificador | `CONTROLS_APPROVED_LIVE_BOUND` |
| candidato `FINAL 1` com amostras vivas | `VERIFIED_REJECTED` coerente | `CONTROLS_REJECTED_VERIFIED` (rejeição verificada, nunca aprovação) |
| candidato `FINAL 0`/`1` **sem** amostra viva, terminado com segurança | coleta diagnóstica permitida (decisão prospectiva do root sob a delegação geral do usuário, não aprovação individual) | `CONTROLS_DIAGNOSTIC_IDENTITY_UNOBSERVED`: sem aprovação dos controles, sem avanço de Native3s ou entry_gate, sem PASS de identidade, sem retry nem reuso do nonce |
| qualquer candidato | coleta `INVALID`, recusa ou rótulo divergente | sem aprovação; revisão |
| `FINAL 2` (recusa) | nenhuma coleta | lote encerrado |
| saída ausente ou malformada, texto inesperado, sessão perdida, 4, 5 ou `PARKED` | nenhuma coleta | `CONTROLS_BLOCKED` / `UNKNOWN`: só monitorar |

A coleta é escopo de **dados**, separado. Ela pode terminar antes do primeiro
yield. `FINAL 0/1` canônico, saída terminal real com o mesmo código, pins de
fonte fixos conferidos, o mesmo nonce consumido, nenhum outro escritor e
hashes públicos verificados semanticamente estabelecem
`COLLECT_DATA_VERIFIED_LIVENESS_UNOBSERVED`: verificação de dados com vida
não observada, nunca PASS de identidade do coletor nem afrouxamento de gate.
Se o root amostrar o processo da coleta vivo, registra só esse escopo medido.
Não se constrói monitor, helper ou framework para forçar essa observação.
Coleta `FINAL 2` ⇒ `COLLECT_REFUSED`, sem retry; `PARKED` ou incerteza ⇒
`COLLECT_BLOCKED`, com o processo dono mantido vivo, sem fechamento forçado,
retry ou limpeza sem revisão própria.

## 7. Ramos terminais e PARK

- Saída terminal: código igual ao `FINAL`; depois, a amostra pós-saída.
- PARK em qualquer entrada: o processo segura o namespace, os ledgers
  originais e (na coleta) handles reais; o exec não termina. O root só
  monitora por CIM esparso e lê o mesmo exec por polling; nunca mata,
  relança, envia EOF ou controle de console. Não existe método de
  recuperação no código; nenhuma recuperação é prometida. App/sessão
  encerrando, logoff ou término externo ⇒ UNKNOWN.
- A primeira leitura nativa da coleta (âncora `\??\C:\`, perfil NTFS local não
  marcado como mídia removível e não remoto, classes de informação, leitura e
  `NtClose` reais) pode recusar ou estacionar; o perfil não atesta hardware.

## 8. Dados privados

Brutos privados ficam só no Temp local; nunca vão em bruto para ferramentas,
conversa ou Git. A coleta lê apenas o inventário fixo e devolve rótulos e
hashes; só `summary.json`/`transport.json` públicos entram no Git, depois de
revisão. PIDs, caminhos, ambiente, linhas de comando e texto de exceção
nunca entram em evidência pública.

## 9. Pendente antes de qualquer efeito

Revisão deste documento; commit descendente só documental de `33b5e44` e
seu hash como `<EXPECTEDHEAD>`; nonce na proposta revisada; pré-checagem da seção 3
executada e registrada pelo root; permissões efetivas das ferramentas para
cada exec. A identidade consumida em 2026-11-02 permanece
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED. Native3s NOT_MEASURED, entry_gate
NOT_EVALUATED; B1/B2/D090/C1/SQL/produção abertos. Destino final Docker
Oracle Linux 9.8 nesta máquina.
