# Caller protegido V2 — revisão do desenho

Data: 2026-11-05. Entrega exclusivamente documental, sob a delegação
vigente. Claude2 escreveu o desenho na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço
`medium`. O assistente principal revisou o contrato e conferiu as referências.
Nenhuma aprovação individual do usuário é inventada.

## Parecer e próximo incremento

Parte A revista para escrever os testes e medir/congelar o RED antes de
implementar o módulo. API mínima: allocate de um slot enraizado,
prepare(slot, sources, owner, case) e run(slot, artifacts). A matriz contém
71 casos **previstos**, não testes implementados ou aprovados.

O componente recebe owner/case já preparados. A construção, invocation,
registro original, diretório e retenção inicial continuam sendo obrigações
explícitas do produtor futuro. Não há código novo de caller, teste novo,
loader, CLI, root, nonce, comando ou publicação.

Parte B permanece desenho prospectivo, com envelope externo e reutilização
do verificador semântico congelado. Antes de escrever B, revisar sua forma
exata de ExpectedV2 e a cadeia externa de confiança; não tratar os oito
papéis selecionados como inventário completo da execução. Não há atestado
de execução real ou garantia de SO.

## Findings fechados no contrato

| Ponto revisado | Resultado |
|---|---|
| API e fontes | Slot pré-alocado; fontes em tupla exata, namespaces reais; host vem do case, sem parâmetro ausente ou cópia de globals |
| Captura inicial | Owner/case/sources crus guardados antes de validar/desempacotar, dentro da proteção; produtor mantém referências até observar o latch |
| Reentrada | Resultado terminal gravado uma vez; recusa de reentrada não sobrescreve primeiro erro, controle ou record; reserva exige False exato |
| Limites | MAX_READ4096 e AUDIT_LIMIT512 confirmados nas fontes; floats finitos e tipos exatos antes de comparações |
| Contexto | Retorno cru guardado em slot.ctx antes de inspeção; vínculos com owner/case/registro/ledger originais verificados antes de lifecycle |
| Finalização | Referências transitivas capturadas e conferidas; sem _case/_contain/close de fallback; prova antes e depois de finish |
| Schema externo | Launcher é campo explícito; latch e flag de reconcile coerentes; limites e prefixo executado fechados |
| Confiança | Expected do revisor sem auto-hash; declaração de digest não é evidência de execução; loader/publicador/collector futuros têm revisão própria |
| Falhas | Injeções de teste não são OOM/nativo medidos; controles retêm identidade e contexto; não há promessa de atribuição atômica |
| Harness | Slots válidos e registros efetivamente capturados são distinguidos de argumentos inválidos e recusas anteriores à captura |

CLI61137 foi somente leitura. CLI63082 escreveu a primeira proposta,
bb3ff468/29082bytes; root leu o documento inteiro e pediu oito correções.
CLI28389 terminou a revisão V3; root releu toda a versão e pediu os dois
últimos pontos de latch. CLI17499 terminou0 e seu terminal foi recuperado.
Zero Claude2 ativo foi confirmado na revisão final. Nenhum segundo escritor.

O revisor fez somente clarificações documentais de fechamento: testes antes
do RED e módulo depois; regra do harness compatível com recusa anterior à
captura; sonda de reuso distinguida dos testes do caller inexistente. Não
mudou API, código ou testes congelados. A primeira proposta e os findings
estão arquivados como dados em `evidence/case-v2-design-review-20261105`.

## Conferências realizadas

- As14 fontes/testes congelados foram conferidos por SHA-256 e tamanho:
  source10, lifecycle7bbf/test402 e helperbb/testad. Nenhum mudou. Os sete
  papéis de fonte já existentes na tabela do desenho batem com os bytes;
  o caller futuro continua placeholder inválido como medição.
- A numeração da matriz foi conferida:1 a71, sem lacunas ou duplicações.
  Isso valida apenas a consistência da proposta.
- A sonda de reuso executou os três casos simulados **existentes** com
  `runpy`, `lab.__wrapped__` e os mesmos kernels falsos. Gerou11 artefatos
  em memória, owners fechados sem double-close e core
  VERIFIED_APPROVED/OK. WinDLL, Popen, os.system, Thread.start e sleep
  estavam proibidos pelo fixture. Não mede o caller novo.
- Git diff check e conferência do índice fazem parte do fechamento. Não
  houve motivo para repetir pytest integral, PostgreSQL, Node, browsers,
  packaging, Ruff ou mypy: nenhum código, teste, recurso ou dependência mudou.
  Os44/636 testes do lote anterior permanecem históricos, não nova medição.

Os limites numéricos/canônicos citados foram comparados com `_integer`,
`_real`, `_parse` e `_capture` do core congelado: total interno262144,
manifest4096 e no máximo3 metadados de1024, total269312. Nenhuma fonte,
configuração ou binário de runtime foi lido para preencher o tamanho do
launcher; o schema mantém apenas sua referência SHA.

## Limites mantidos

Tentativa3f12dc584c29 consumida como FAILED_ONLY_OPERATOR_ABORT; identidade
Nov2 LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED. Não foram reexecutadas,
reutilizadas, relidas em privado ou reclassificadas. Estado16 não foi
alterado. Sem operação nativa de DLL/job/process/control, Docker, PG, SQL,
deployment, root/nonce/comando operacional ou leitura privada/runtime/config/
binário. Não houve quota/reset/job novo ou troca de conta/modelo; tarefa
histórica Disabled.

Gateway continua indisponível. Native3s NOT_MEASURED, entry_gate
NOT_EVALUATED, B1/B2/D090gate2/C1/SQL e produção abertos. Destino já aceito:
Docker local Oracle Linux9.8. Próximo lote seguro: Claude2 escreve somente
os testes de A; root mede o RED e revisa antes do módulo, mesma sessão e
sem segundo escritor.
