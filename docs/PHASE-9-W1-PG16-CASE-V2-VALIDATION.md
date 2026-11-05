# Caller protegido de caso V2 — revisão e validação com fakes

Data: 2026-11-05. Claude2 foi o único programador, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço
`medium`; o assistente principal revisou e executou os gates. Trabalho sob
delegação, sem inventar aprovação individual do usuário. Última chamada de
código CLI95368 terminou0 e seu terminal foi recuperado. Zero escritor
Claude2 confirmado antes da medição final; nenhum segundo escritor.

## Entrega e alcance

Componente privado com `allocate`, `prepare(slot, sources, owner, case)` e
`run(slot, artifacts)`. Slot em KEEP retém owner, case, fontes e contexto
antes de inspeções. Erro comum entregue e controle mantêm a primeira
identidade; reentrada não sobrescreve o primeiro resultado. O caller
confere originais/prova antes e depois da finalização e nunca chama limpeza
legada ou close adicional. O `_held` local apenas classifica erros.

READY_FOR_VALIDATION exige fechamento e record estruturado, mas ainda
depende da validação semântica completa e não autoriza publicar ou sair do
controlador. Os casos TREE continuam rejeitados; LAST_CLOSE conserva a
precedência do verificador congelado. O caller não cria owner, diretório,
invocation, launcher, root, nonce ou comando. Esses insumos são obrigações
do produtor futuro.

Importação só define constantes/classes/funções. Run possui efeitos
**potenciais delegados** ao lifecycle/finish; não é matematicamente puro.
Nesta entrega todos os colaboradores são falsos e não há consumidor
operacional, entrada, loader, batch ou publicação. Parte B de proveniência
continua somente desenho, com revisão própria antes de código.

## Bytes finais medidos

| Arquivo | Bytes / linhas | SHA-256 |
|---|---:|---|
| `docs/poc/pg16_shell_native_control_case_v2.py` |22627 /696 | `0fac3c7bd807e34c46e61a16c20bcda5c3a77b4ebed3c3404ff9250c4405a936` |
| `tests/test_pg16_shell_native_control_case_v2.py` |36085 /1016 | `72dde65cd0c4db08c3a864726bcb86b57af43ff1011299770a069253c30385cf` |

Testes finais byte a byte iguais ao RED72. As14 fontes/testes anteriores
foram conferidas por hash e tamanho: source10, lifecycle7bbf/test402 e
helperbb/testad. Nenhuma mudou; estado16 não foi editado.

## Testes antes da implementação e revisão dos oráculos

O arquivo foi escrito primeiro, sem módulo. O baseline inicial5c3ba504
coletou71, todos com erro de setup por FileNotFoundError,6,751s. Isso prova
ausência de funcionalidade, não uma correção comportamental. Root leu todo
o teste e corrigiu os oráculos antes de congelar:

- O negativo LAST_CLOSE com Owner simples usava prefixo case-1 e já seria
  recusado por outro motivo; agora usa case-3 antes da mutação de classe.
- O `_finish` sanitiza OSError por `_persist`/`_step`; a sonda confirmou que
  o caller recebe RunError(CONTROL_PERSISTENCE) sem cadeia. O teste observa
  e exige a identidade exata desse primeiro erro entregue, sem tentar obter
  o erro suprimido. As asserções de nenhum cleanup extra foram preservadas.
- A clonagem de tupla precisa de identidade diferente; o ajuste de lint
  usa unpack, preservando essa propriedade. Não usa tuple(valor), que pode
  devolver a própria tupla.
- A releitura de estado para o mypy preserva `is False`/`is True`.
  Comparação de tuplas aceitaria0/1; essa regressão de oráculo foi corrigida
  antes do congelamento, sem supressão ou cast.

RED71 final6d99606c/34563bytes:71 coletados únicos1..71,71 erros de setup,
6,947s. Ruff/format/mypy estrito3.11/3.14 passaram. Root arquivou o teste e
resultado antes de autorizar o módulo; nenhuma asserção foi relaxada para
acomodar uma implementação.

## Finding do código e RED72

A primeira implementação bdad4ad8 passou71/71 em7,382s. Root leu toda a
fonte e reproduziu uma falha de ordem em `_finished`: o acesso a
`case["reconcile_reserved"]` precedia a validação do domínio das chaves.

Um write_new falso apagou a chave canônica e inseriu chave estrangeira
colidente. Run devolveu RETAINED_POST_FINISH_INVALID, mas antes executou
`__eq__` estrangeiro. O owner já estava CLOSED e sem double-close; não houve
efeito nativo, mas a ordem contrariava o contrato de não chamar métodos
estrangeiros antes da recusa.

Claude2 acrescentou apenas a regressão72; a AST dos71 anteriores permaneceu
idêntica. RED72:71 passaram/1 falhou em8,132s, exatamente o caso novo.
Teste72dde65c congelado antes da correção. O fix antecipou `_intact` antes
de qualquer lookup pós-finish; as outras provas ficaram intactas. Comparação
AST confirmou que fora de `_finished` e da docstring nada mudou na fonte.
A docstring agora distingue o classificador local `_held` da limpeza legada.

Uma estatística preliminar de22422bytes era do rascunho ainda sendo escrito.
O snapshot bdad4ad8 arquivado possui22442bytes/693linhas; o metadado foi
corrigido pelos bytes preservados, com nota da correção. O snapshot não foi
alterado nem executado operacionalmente. Dados e sondas estão em
`docs/poc/evidence/case-v2-review-20261105/`.

## Gates finais

| Gate | Resultado |
|---|---|
| Teste novo |72 passed,7,222s; zero falhas/erros/skips, matriz1..72 única |
| Relacionados,9 arquivos |708 passed,39,824s; zero falhas/erros/skips |
| Ruff PoC | E9,F63,F7,F82 aprovados, política existente |
| Ruff teste | Seleção normal do repositório aprovada |
| Format |2 arquivos conformes |
| Mypy strict |1 teste, alvos3.11 e3.14 aprovados; PoC fora do mypy |
| Integridade |14 arquivos anteriores intactos, teste72 congelado |

Execução Windows/CPython3.11.3. Alvo estático3.14 não é execução em
Python3.14. A seleção inclui casoV2, lifecycleV2, helper, backend, host,
adapter, runner, entry e projeção HELD. Não é a suíte integral do produto.
Não foram repetidos PostgreSQL/Node/browsers/packaging ou integração real,
pois este incremento não altera produto, frontend ou dependências e segue
restrito aos fakes.

A sonda independente final confirmou POST_FINISH_INVALID com **zero**
hash/igualdade estrangeiros, ownerCLOSED e zero double-close. Nos positivos,
o core completo validou APPROVED dos três controles e REJECTED de TREE,
incluindo FAILED_LAST_CLOSE. Isso é semântica simulada, não atestado de
execução ou de API/ABI/NTFS/sinais reais.

## Próxima continuação e limites

O produtor/coordenador futuro ainda precisa manter owner e lista originais
antes do latch, provar a persistência da invocation e sustentar o controlador
enquanto houver posse incerta. Não há promessa absoluta de atomicidade/OOM
ou defesa contra Python privilegiado/reflexão. Originais de fontes fixadas
são precondição de confiança, não autenticação. Semântico completo continua
obrigatório; o caller não duplica `_recompute`.

Próximo lote seguro: leitura/revisão da Parte B para fechar ExpectedV2 e
cadeia externa, antes de testes/código do envelope. Nenhuma prova nativa,
procedimento/root/nonce/comando/entrada/loader/batch/publicador/collector
operacional novo neste lote. Não reutilizar ou reler privados da tentativa
3f12dc584c29 consumida como FAILED_ONLY_OPERATOR_ABORT. Identidade Nov2
continua LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED.

Gateway indisponível. Native3s NOT_MEASURED, entry_gate NOT_EVALUATED,
B1/B2/D090gate2/C1/SQL e produção abertos. Destino aceito: Docker local
Oracle Linux9.8. Sem novo Docker/PG/SQL/deploy, leitura privada/runtime/
config/binário, segundo escritor, troca de conta/modelo ou quota/reset/job.
Tarefa histórica Disabled.
