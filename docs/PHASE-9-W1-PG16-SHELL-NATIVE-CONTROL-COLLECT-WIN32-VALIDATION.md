# Backend Win32 do coletor — validação com fakes

Data: 2026-11-03, America/Sao_Paulo. Base publicada:
`dbde802f3f8a686d13e8a1289ade591d373b6386`. Sob delegação vigente, sem
inventar aprovação individual do usuário. Claude2 foi o único programador
(sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`,
`claude-opus-5-5`, esforço `medium`); o assistente principal fez a
revisão e executou os gates. Não se alega revisão humana independente.

## Estado final do incremento

Backend privado revisto **somente com fakes**. Módulo:
`docs/poc/pg16_shell_native_control_collect_win32.py`, 22315 bytes,
SHA-256 `ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a`.
Testes: `tests/test_pg16_shell_native_control_collect_win32.py`,
68313 bytes, SHA-256
`83c8f5533a2f820d7ebc16e0c78104169ffb5c243830e50c920c895a8dcf9d92`.

[Desenho](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-WIN32-DESIGN.md).
Ponto público `backend()` retorna `None`; a fábrica do coletor anterior
também continua indisponível. Nenhum chamador real foi ligado.
`_load_native` permanece sem chamada. Os testes simulam as sete operações
da API usando buffers `ctypes` próprios; nenhuma API selecionada do Windows
foi realmente invocada, nem DLL explicitamente carregada pelo módulo.
Isso não afirma ausência de DLLs do próprio interpretador ou das ferramentas.

O backend implementa seis operações da política, tipos/ABI x64,
protótipos, páginas e leituras limitadas, metadados, streams e preservação de
posse. Exige o objeto Handle original, não só seu token. Retém buffers antes
de efeitos simulados e mantém posse antes de removê-la no fechamento.
Se a posse fica incerta, a política bloqueia nova coleta. **Retenção não é
cleanup**; não há prova de cleanup nativo, atomicidade, origem, ACL, CIM,
hardware fixo ou prazo absoluto de syscall.

## Cronologia e baselines preservadas

- CLI49713 terminou0, só plano. O revisor demonstrou a lacuna do plano:
  raw fake retido apenas pelo backend, slot ainda None e controle levantado
  fazem o coletor congelado marcar EMPTY e liberar ACTIVE/POISON. O contrato
  foi corrigido antes do código: marcador UNKNOWN no slot antes da chamada,
  com célula e buffers fortemente retidos.
- CLI38011 terminou0 com desenho e testes. Primeiro teste `15fe2480`,
  62740 bytes: **176 coletados, 174 erros de preparação e 2 falhas**,
  todas as 176 exceções FileNotFoundError; 1,238s/saída1. Mypy do teste
  passou; Ruff apontou21B017 e format1 pendente. Ausência do recurso novo,
  não regressão de produto.
- CLI70718 terminou0, mas repetiu V2 por erro do revisor: substituição
  de prompt multilinha não encontrou o trecho; V3 não foi enviado. Houve
  só ajuste local da fixture (captura de Node opcional). Não se atribuiu
  falta de cumprimento ao Claude2. O teste `8b82e751`, 62825 bytes,
  foi preservado antes do reenvio.
- Reenvio V4 foi montado do template original, com prompt em uma linha,
  marcador e escopo conferidos. CLI55798 terminou0: exceções esperadas
  estreitadas para OSError, sem reduzir asserções; uma regressão de saída
  pública com sentinela e notas de perfil/ABI.
- Teste `7b5c113f`, 63332 bytes: **177 coletados, 175 erros de preparação
  e 2 falhas**, todas as 177 exceções FileNotFoundError, 1,341s/saída1.
  Ruff/format/mypy do teste aprovados. AST conferiu asserções/decoradores
  anteriores preservados; uma nova função de teste, sem supressões.
- CLI38950 terminou0: candidata `fb453d57`, 21742 bytes. O revisor leu
  integralmente os629linhas antes de importar; ABI/pureza/default4pass
  em1,279s; **177/177 passaram**,9,129s. Lint restrito e format aprovados.
  A revisão independente reproduziu os dois findings abaixo.
- CLI48667 terminou0 só com regressões e notas. Teste `83c8f553`,
  68313 bytes: prefixo177preservado salvo novo import sys.
  **189 coletados,177 aprovados,12 falhas,0 erros**,11,623s/saída1,
  na candidata rejeitada intacta. Ruff/format/mypy do teste limpos.
- CLI12120 terminou0, corrigindo somente módulo/desenho. Os189 testes
  permaneceram byte a byte congelados. Sem medição pelo programador.
  O revisor verificou o diff e os gates finais abaixo.

Candidata, baselines e RED preservados como dados em
`docs/poc/evidence/native-collect-win32-review-20261103/`.
Os arquivos `.tests.txt` e `.source.txt` nunca devem ser carregados como
módulos ou executados. Nenhuma raiz operacional foi consumida neste lote.

## Findings reproduzidos e correções

### DTO estrangeiro ou reconstruído com token igual

Dois backends privados legítimos compartilham as classes da política, mas
têm raws diferentes. Ambos emitiam token1. Na candidata, B aceitava o DTO
de A ou um DTO reconstruído de mesmo token; close fechava o recurso de B.
Não se alega vulnerabilidade externa ou fronteira hostil: o problema é
posse exata entre objetos privados. Dez regressões cobrem as duas origens
e cinco operações: close/query/read/list_dir/open_child.

Correção: `_open[token] = (Handle original, raw)`;
`entry[0] is handle` é obrigatório antes de qualquer chamada simulada.
As operações recusam o estrangeiro sem afetar o original. Alias de raw
continua recusado. Não se introduziu outro framework de capacidade.

### Remoção da posse antes do ticket no fechamento

Interrupção na linha que cria o ticket, após pop, deixava o raw só no frame.
Pela política congelada:31criados,30fechados,1vivo no fake, mas banco do
backend vazio e retenção vazia, apesar de a política estar poisoned.
Duas regressões injetam OSError e Signal por sys.settrace, conferem disparo,
restauram o trace e eliminam traceback como prova de retenção. O walker
limitado olha apenas os ledgers do backend, não a tabela do driver fake.

Correção: raw permanece em `_open` até o ticket entrar em `_retained`;
só então é removido e NtClose simulado é tentado. Não há fechamento forçado
ou repetido. A sonda final mantém31criados/30fechados/1vivo, agora com
**1registro próprio de posse**, e a política impede nova coleta.
Isso comprova retenção no modelo, não fechamento real.

Se a interrupção precede o ticket, nenhum NtClose foi tentado: o backend
privado pode ainda conhecer o raw, enquanto a política o marca incerto e
não tenta novamente. Após o ticket pendente, o backend bloqueia outras
chamadas. Não há promessa de imunidade à morte do processo ou sinais fatais
repetidos.

## Gates finais medidos pelo revisor

Ambiente de execução: Windows CPython3.11.3. Os alvos3.11/3.14 do mypy não
são medições de runtime3.14. Nenhuma alteração funcional depois dos gates.

| Gate | Resultado |
|---|---|
| Testes próprios congelados | **189 passed**,10,052s/saída0 |
| Backend + coletor + core + entrada privada | **656 passed**,22,701s/saída0 |
| Sondas independentes de posse | 2 conferidas; estrangeiro recusado e raw retido |
| Delegação de argumentos em _NativeApi | 7 funções Python simuladas conferidas |
| Ruff src/tests | aprovado |
| Lint PoC novo, E9/F63/F7/F82 | aprovado |
| Format src/tests + PoC novo | **349 arquivos conformes** |
| mypy strict src/tests, alvo3.11 | **348 arquivos sem erros** |
| mypy strict src/tests, alvo3.14 | **348 arquivos sem erros** |

Zero falhas, erros e skips nas suítes verdes. Matriz relacionada:
`test_pg16_shell_native_control_collect_win32.py`,
`test_pg16_shell_native_control_collect.py`,
`test_pg16_shell_native_control_verify.py` e
`test_pg16_shell_native_control_entry.py`.
PoC não incluído no mypy. As sete delegações conferem quantidade, ordem,
nulos e referências byref somente contra funções Python; **não exercitam
conversão ctypes para função nativa, convenção de chamada, loader real ou
suporte do kernel**. Tais gates seguem não medidos.

Suíte integral de produto, PG, frontend, build de pacotes e Docker não foram
repetidos nem declarados aprovados neste incremento. Nenhum src/produto/UI/
dependência mudou. Depois dos gates só houve fechamento documental.

## Estado de coordenação e fronteiras

Zero Claude2 ativo na conferência posterior, Git/fetch com HEAD e origin
em dbde802 antes da publicação. Tarefa histórica
`Maskgw-Claude2-Resume-01a05804` relida Disabled, sem próximo horário,
último disparo03/11 às16h35Z/result0. Nenhuma cota/reset/tarefa nova
ou segundo escritor. Arquivos pessoais não rastreados preservados.

Coletor1972/testsb6f, coreb375/testes8088, entrada356d, runnerb419,
adaptereaeb, backend10c9, hostdfcc e estado16 fixos. Ligação por fontes
pinadas, pré-checagem e procedimento real continuam posteriores a revisão.
Sem runtime/config/binário, DLL/controle real, Docker/PG/SQL, root/nonce/
comando operacional ou deploy. Native3s NOT_MEASURED,
entry_gate NOT_EVALUATED, identity LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED;
Gateway/B1/B2/D090gate2/C1/SQL/produção abertos. Destino final continua
Docker Oracle Linux9.8 nesta máquina; este laboratório é Windows.
