# Adaptador privado de jobs aninhados — validação com fakes

Data: 2026-11-01, America/Sao_Paulo. Incremento sob delegação vigente,
iniciado sobre `66dcaa6a352a98000972f66424c578ae7f7e8384`. Claude2 foi o único
programador, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo
`claude-opus-5-5`, esforço `medium`; o assistente principal revisou, executou
os checks e escreveu este registro. Não se inventa aprovação individual.

## 1. Escopo e autoria

Entregues apenas `docs/poc/pg16_shell_native_control_win32.py`,
`tests/test_pg16_shell_native_control_win32.py`, desenho e registros de revisão.
O módulo expõe definições carregadas explicitamente, sem CLI, `__main__`,
consumidor ou orquestrador `pg16_shell_native_control.py`.

CLI93312 terminou com plano de leitura; não realizou leitura nova naquela
chamada. CLI41852 leu as fontes aceitas e escreveu o desenho. CLI5462 corrigiu
três pontos pedidos pelo revisor: reuso de `_start` por despacho virtual,
quiescência antes do fechamento ordinário de INNER e auditoria finita com
integridade explícita. CLI3480 implementou o adaptador e testes. Todas
terminaram exit0 antes de iniciar a chamada seguinte.

CLI35435 corrigiu os dois P2 após escrever regressões, terminando exit0. A
primeira tentativa de enviar essa tarefa falhou no parser do PowerShell,
antes de chamar Claude2; o reenvio escapou os apóstrofos. O programador não
executou ferramentas de runtime: recebeu apenas Read/Edit/Write com escopos
explícitos. Não houve segunda conta, modelo, escritor, nova quota ou tarefa.

## 2. Contrato conferido

- O backend aceito é carregado por SHA em namespace privado; seu `_start` é
  herdado como o mesmo objeto, sem copiar lifecycle, assinatura ou globais.
- OUTER permanece o job do ledger original, observador e fallback. INNER é
  outro handle próprio, não herdável, com os mesmos flags/cap2/sem breakaway.
- O ponto de extensão é `_call`: a lista validada `[outer]` vira
  `[outer, inner]` antes de criar o processo suspenso; a configuração,
  membership, accounting e lista de INNER são verificadas antes do resume.
- `close()` ordinário comprova sinal/zero ativos/lista vazia/EOF antes de
  soltar INNER. Recusa de árvore viva não fecha INNER. `close_inner()` é a
  única operação deliberada de fechar INNER vivo, sob guarda herdada.
- O proxy de auditoria cobre chamadas posteriores ao setup de OUTER,
  inclusive o terminate direto da interrupção herdada. Até512 entradas,
  snapshots imutáveis, perda/overflow invalidam permanentemente a auditoria.
  Uma `Exception` no registro não impede cleanup; `BaseException` propaga
  antes da operação real, sem retomar lançamento após interrupção.
- O desenho futuro exige auditoria íntegra e nenhum terminate para aprovar
  LAST_CLOSE. Nenhum dos três controles nativos foi executado aqui.

## 3. Revisão e baselines reprovadas

Versão inicial: fonte `e7ccc7597bb49e4fa4b691e2cbfc71a07505cc7fd61453e6a66d19a111b816c2`
(14.772 bytes), testes
`12d5926023c1e17a9703233aa69b4c31ab318f312dfdbf6fecd64e024db49280`
(23.044 bytes). Seus26 testes passaram em0,75s, mas o hook independente
reproduziu dois P2 (1passed/1error/0,34s):

1. `UpdateProcThreadAttribute` com JOB_LIST e8 argumentos ainda alcançava
   o backend. Agora aridade diferente de7 é recusada antes da delegação.
2. Interrupção na auditoria do fechamento ordinário de INNER escapava com
   estado RUNNING. Agora a transição extra inteira usa `_guarded`, conservando
   INNER e HELD em exceção inesperada ou interrupção; recusa conhecida de
   quiescência continua sem efeito destrutivo.

Antes da correção, os bytes da fonte e dos testes foram preservados como
base64 em `docs/poc/evidence/native-adapter-review-20261101/`, com manifesto
de tamanho e SHA dos bytes decodificados. São dados de revisão rejeitada,
nunca um controle nativo para executar.

Depois da correção, as sete regressões selecionadas dos testes finais foram
executadas contra a fonte rejeitada, carregada somente em memória com kernel
fake: **5failed/2passed/26deselected,0,54s,exit1**. As cinco falhas cobrem
aridade6/8/9, interrupção de controle e MemoryError. Os dois casos de erro ou
FALSE no CloseHandle já passavam. Esta é medição retrospectiva da baseline;
não se declara que esses testes formais foram executados antes do fix.
O hook independente já havia reproduzido os dois problemas antes dele.

## 4. Gates sobre os bytes finais

Ambiente executado: Windows, CPython3.11.3 da `.venv`; apenas kernels/owners
simulados. APIs nativas, Popen, os.system e Thread.start são recusados pelo
fixture do adaptador. O runtime não foi executado em Python3.14: esse alvo
foi somente análise estática.

| Gate | Resultado |
|---|---|
| Próprios do adaptador | 33passed/0,93s,exit0 |
| Hook independente repetido, mesmas duas contraprovas | CLEAN,1passed/0,17s,exit0 |
| Relacionados,19 arquivos | 892passed/273,79s,exit0;zero falhas/skips |
| Ruff em src/tests | Aprovado |
| PoC,lint restrito E9/F63/F7/F82 | Aprovado |
| Format em src/tests e8PoCs explícitos | 351 arquivos conformes |
| Mypy alvo3.11 em src/tests | 343 arquivos,sem erros |
| Mypy alvo3.14 em src/tests | 343 arquivos,sem erros |

O PoC permanece fora do escopo mypy geral já existente. Não se alterou
configuração para alargar ou suprimir gates. Removeu-se apenas o noqa:C901
desnecessário; N802 fica nos nomes ABI do kernel fake. Nenhum skip/xfail novo.

Não houve mudança de produto/src/frontend/dependências nem empacotamento
deste PoC. PostgreSQL, browsers, Docker, pacotes e suíte integral de produto
não foram executados neste incremento; os gates acima verificam este escopo.

## 5. Pins finais e insumos congelados

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| `docs/poc/pg16_shell_native_control_win32.py` | 15373 | `eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407` |
| `tests/test_pg16_shell_native_control_win32.py` | 25708 | `46a82a6eebabb4ce4582117bc211a7bd78c7cc52ec74674acab663011dbdeeb6` |
| backend aceito | 31948 | `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726` |
| chamador aceito | 33234 | `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7` |

Preparador8d0bf39e, sonda738ee1e3, entradaafaffad0 e exportadored491c01
reconferidos intactos. Estado aceito de16campos e fontes/raízes consumidas
continuam congelados. Não há proposta, raiz, nonce ou comando operacional novo.

## 6. Limitações e próximo incremento

Revisão aprova apenas o adaptador privado simulado após os gates finais.
Jobs aninhados, atribuição atômica e morte por último handle continuam
**não medidos nativamente**. O desenho separa o job observado do fechado;
não mantém INNER aberto ao dizer que o fecha. Nenhum OpenProcess por PID foi
introduzido. Atribuição causal da morte continua inferência de amostra benigna,
não prova universal contra duplicação externa de handles.

Após liberar INNER, `super().close()` mantém o comportamento aceito do
backend; não há promessa nova de guarda de interrupções nessa parte herdada.
Uma segunda interrupção no terminate herdado pode substituir a primeira.
Chamadas síncronas do SO não têm prazo absoluto. Um futuro CPython nativo
lerá implicitamente configuração/site/DLLs/stdlib; não há promessa de startup
livre dessas leituras. Nenhum desses arquivos foi lido explicitamente agora.

Próximo: orquestrador privado dos três controles, com fakes e revisão antes
de qualquer CLI/proposta/raiz/comando/efeito nativo. Native3s NOT_MEASURED,
entry_gate NOT_EVALUATED. Gateway indisponível; B1/B2/D090gate2/C1/SQL e
produção permanecem abertos. Nenhum novo job ou workaround de quota.
