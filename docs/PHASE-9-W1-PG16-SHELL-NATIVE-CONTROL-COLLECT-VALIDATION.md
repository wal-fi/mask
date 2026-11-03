# Coletor de evidências — validação da política com fakes

Data: 2026-11-03, America/Sao_Paulo. Incremento privado sob a delegação
vigente; não é aprovação individual do usuário nem liberação de produção.
Claude2 programou; o assistente principal revisou, executou os gates e
registrou esta evidência. Base publicada: `ef465b7ef8bacccdc84ecb6567894489e30fce6c`.

## Estado atual

**Política com fakes revista e gates finais aprovados; pronta para publicação.**
Estado anterior de tipagem pendente e cota preservado nas seções históricas.
Módulo `docs/poc/pg16_shell_native_control_collect.py`:
20571 bytes, SHA-256
`1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52`.
Teste `tests/test_pg16_shell_native_control_collect.py`:
37978 bytes, SHA-256
`b6f165d19e85fe419b3d82b9eac6441a92146dec212daaaa4fadc4af8636f0c7`.
O teste vermelho/pré-ajuste `8a3f9ebd` (37929 bytes) está preservado como
dado de revisão, sem reescrita.

[Desenho](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-DESIGN.md).
Backend padrão `None`: `collect` recusa como indisponível; não existe
leitor real ou binding nativo. Seam privado só para fakes, sem fronteira
adversarial. A política confere inventário, bytes e metadados simulados,
identidade de 128 bits, limites e retenção de posse. O verificador puro
capturado só executa depois de seu SHA exato e do fechamento simulado
comprovado. Isso não autentica produtor, disco, SO, CIM, execução ou cleanup.

## Cronologia medida

- CLI96874, somente leitura, terminou 0 com contrato revisto. Corrigida no
  desenho a mistura de FileId64 com FileId128; binding e suporte Windows
  continuam não medidos. Fontes primárias Microsoft foram consultadas pelo
  revisor, não pelo programador.
- CLI37722 terminou 0, só desenho e testes. Fonte ainda ausente:
  **136 coletados, 134 erros de preparação e 2 falhas**, 1,155 s, saída 1,
  todas as 136 exceções `FileNotFoundError`. Ausência de recurso novo,
  não regressão de produto. Teste inicial `720fb16a`, 31665 bytes.
- CLI67443 terminou 0 com fonte `1037b2d0`, 18360 bytes, e teste
  `30ad8821`, 31835 bytes. Corrigiu quatro apontamentos de estilo sem
  remover casos. **136/136 passaram**, 5,184 s; Ruff/format limpos.
- Revisão independente reproduziu retenção de posse ausente em quatro
  cenários descritos abaixo. Fonte/teste rejeitados arquivados como dados.
- CLI80031 terminou 0, somente regressões/notas; fonte rejeitada intacta.
  **141 coletados, 136 passaram e 5 falharam**, 0 erros, 5,085 s, saída 1.
  Prefixo dos 136 testes preservado salvo novo `import sys`.
- CLI79484 terminou 0, corrigindo somente módulo/desenho; testes RED
  `8a3f9ebd` intactos. **141/141 passaram**, 9,133 s.
- Rerevisão: as quatro sondas independentes agora encontram retenção e
  bloqueio em vez de perda de posse; a interrupção observada é a mesma.
  Uma primeira invocação do roteiro do revisor terminou em `StopIteration`
  ao procurar a indentação antiga da fonte. Ajustado apenas o localizador
  do roteiro para comparar o texto sem indentação; a repetição terminou 0.
  Esse erro de harness não foi contado como resultado do módulo.
- Matriz de integração privada: **467/467 passaram**, 12,304 s, zero
  falhas/erros/skips. Não houve alteração funcional depois desses gates.

## Finding: retenção de posse

Na candidata rejeitada, todos os cenários abaixo eram só fakes em memória:

| Cenário | Resultado anterior | Recursos simulados sem close e sem registro persistente |
|---|---|---|
| Open preenche Handle e perde o campo token | INVALID/COLLECT_INTERNAL | 1 |
| Interrupção entre gather e cleanup | mesma interrupção propagada | 31 |
| Interrupção depois de CLOSING, antes de close | mesma interrupção propagada | 31 |
| Interrupção após open, antes de adopt | mesma interrupção propagada | 1 |

As cinco regressões também cobrem primeira interrupção registrada seguida
de outra no intervalo da limpeza. Trace restaura o rastreador anterior e
confere o disparo; não mede sinais reais do SO. Exige fechar cada handle
uma vez **ou** reter backend/ledger/slots/handles originais e recusar nova
coleta, sem repetir fechamento incerto ou fechar token desconhecido.

Correção: `_ACTIVE` registra o proprietário antes da primeira aquisição;
só libera com ledger terminal. `_POISON` retém estado incerto; qualquer
registro NEW/CLOSING/OWNED/quarentenado/incerto impede liberação. Leitura
inválida do token vai para custódia. Finalização externa conserva o dono
nos intervalos fora das chamadas do backend; primeira interrupção
registrada vence. **Retenção não é limpeza.** Interrupções em instantes
não registrados e durante a própria finalização têm só retenção; não há
garantia contra morte do processo ou sinais fatais repetidos. Uso
serializado em primeiro plano, sem promessa de thread safety.

Baseline rejeitada, testes e RED:
`docs/poc/evidence/native-collect-review-20261103/`.
São dados de revisão, nunca módulos para carregar ou executar.

## Gates antes da retomada (histórico preservado)

Ambiente: Python nativo do Windows, CPython 3.11.3. Os alvos de mypy não são
medições de runtime Python 3.14.

| Gate | Resultado |
|---|---|
| Novos testes, após fix | 141 passed / 9,133 s / saída 0 |
| Coletor + verificador puro + entrada privada | 467 passed / 12,304 s / saída 0 |
| Sondas independentes dos quatro cenários | retenção/bloqueio conferidos; mesma interrupção / saída 0 |
| Ruff src/tests | aprovado |
| Ruff PoC novo, E9/F63/F7/F82 | aprovado |
| Format src/tests + PoC novo | 348 arquivos conformes |
| mypy strict src/tests, alvo 3.11 | reprovado: 1 erro em 347 arquivos |
| mypy strict src/tests, alvo 3.14 | reprovado: o mesmo erro em 347 arquivos |

Pendência medida antes da retomada: `tests/test_pg16_shell_native_control_collect.py:718`,
`Unpacked dict entry 1 has incompatible type object; expected SupportsKeysAndGetItem[str, Any]`.
Era o mapa heterogêneo de `changes` em `_bad_info`; precisava de anotação
precisa do mapa aninhado, sem ignore/cast/skip ou mudança de asserções.
A frase histórica “Direção da correção (ainda não aplicada)” no desenho
também precisava ser marcada como proposta pré-fix. Ambos resolvidos na
retomada abaixo; resultados reprovados não foram apagados.

A matriz relacionada usa somente:
`test_pg16_shell_native_control_collect.py`,
`test_pg16_shell_native_control_verify.py` e
`test_pg16_shell_native_control_entry.py`. O mypy cobre src/tests,
não os PoCs. A suíte integral de produto, PG, frontend e pacotes **não foi
repetida nem declarada aprovada neste incremento**. Nenhum src/produto/UI/
dependência mudou; fontes antigas foram reconferidas por SHA.

## Cota e agendamento (registro anterior à retomada)

A tentativa seguinte, somente para anotação de fixture e redação histórica,
retornou **API429/exit1 antes de editar**: reset informado pelo Claude2
“1:30pm (America/Sao_Paulo)”, em 03/11/2026. Não houve nova tentativa,
troca de sessão/conta/modelo ou segundo escritor; pós-cota conferiu zero
chamada ativa. Mesma sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
sempre `claude-opus-5-5`, esforço `medium`.

Reutilizada a tarefa existente `Maskgw-Claude2-Resume-01a05804`, sem
execução manual. Registro relido em 03/11 às 13h56m39Z: **Ready**, um único
disparo `2026-11-03T13:35:00-03:00` / próximo UTC **16h35**,
`IgnoreNew`, `Limited`, ação exata `codex queue` para esta conversa
`01a05804-2c07-71f2-bfef-7e3c90c06476`, com instrução de inspecionar
escritor ativo antes de retomar. O resultado 0 da última execução em
01/11 às 21h24m15Z é histórico; não comprova a próxima execução.
O agendamento dependia da máquina e da sessão local disponíveis. A execução
efetiva seguinte foi medida e registrada abaixo.

## Retomada e gates finais

Mensagem agendada recebida às16h35Z em03/11. O revisor leu primeiro PENDING
e CHECKPOINT, conferiu HEAD/origin ef465b7, alterações locais esperadas e
hashes1972ec74/8a3f9ebd. CIM confirmou zero chamada Claude2 ativa; Scheduler
registrou execução em03/11 às16h35Z, resultado0 e próximo horário nulo.
O reset16h30Z observado já havia passado, sem tentativa intermediária.

CLI43588 terminou0 na mesma sessão/conta/modelo/esforço. Editou somente o
teste (mapa `by_kind: dict[str, dict[str, Any]]`, depois seleção por `kind`)
e a frase histórica do desenho. Sem ignore/cast/skip ou redução de testes.
Revisão AST independente confirmou todas as asserções, funções/decoradores
e valores do mapa idênticos; diff de teste só anotação/seleção. Fonte20571/
1972ec74 e arquivos antigos intactos. Nenhuma alteração funcional nova.

| Gate final após ajuste | Resultado |
|---|---|
| Coletor + core + entrada, incluindo141próprios | **467 passed / 14,958 s / saída0**, zero falhas/erros/skips |
| Ruff src/tests | aprovado |
| Ruff PoC novo, E9/F63/F7/F82 | aprovado |
| Format src/tests + PoC novo | **348 arquivos conformes** |
| mypy strict src/tests, alvo3.11 | **347 arquivos sem erros** |
| mypy strict src/tests, alvo3.14 | **347 arquivos sem erros** |

PoC não incluído no mypy; runtime apenas Windows3.11.3. Demais gates de
produto/PG/frontend/pacotes não repetidos. `rereview.json` conserva o estado
PENDING anterior ao ajuste; não é a evidência final desta retomada.

Tarefa única consumida desabilitada após conferência: **Disabled**, último
disparo03/11 às16h35Z/result0, próximo horário nulo. Zero escritor Claude2
ativo na conferência posterior. Não se criou outra tarefa ou chamada.

## Fronteiras preservadas

Core b3755d49, testes808869aa, entrada356d2291, runnerb4198fe1,
adaptadoreaebedd6, backend10c9058f, hostdfcc4ed6 e estado16 fixos.
Sem coletor real, binding/API nativa, nova sonda de processo, Docker/PG/SQL,
runtime/config/binário, raiz/nonce/comando operacional ou deployment.
Preflight e execução nativos seguem posteriores a revisão própria;
nenhum PASS nativo derivado destes fakes. Identity conserva
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED, Native3s NOT_MEASURED e
entry_gate NOT_EVALUATED. Gateway/B1/B2/D090gate2/C1/SQL/produção abertos.
Destino final segue Docker Oracle Linux 9.8 nesta máquina.
