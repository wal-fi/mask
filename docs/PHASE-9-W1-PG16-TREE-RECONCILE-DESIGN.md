# Reconciliação TREE/quietude — desenho (testes escritos antes do módulo)

Data: 2026-11-04. Sob a delegação geral vigente (AGENTS.md), sem aprovação
individual inventada; Claude2 programa, o root revisa e mede. Sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço
`medium`. Lote **só com fakes**: nas etapas de teste existiam só este
desenho e `tests/test_pg16_shell_tree_reconcile.py`; o módulo
`docs/poc/pg16_shell_tree_reconcile.py` foi implementado na V3 (seção
3.1.1), posteriormente revisto e medido pelo root (seção 5). Nenhum teste executado pelo
programador. A tentativa `3f12dc584c29` está consumida como
`FAILED_ONLY_OPERATOR_ABORT`; nada dela é reutilizado ou relido. As dez fontes
consumidas e o estado16 ficam fixos.

## 1. Defeito lógico (código, não causa real comprovada)

`Owner.accounting()` (backend `10c9058f`) levanta `WIN32_TREE` quando
`active > total` ou `total > ACTIVE_PROCESS_LIMIT`; `TotalProcesses` é
cumulativo, o limite é de processos ativos. `_supervise` (chamador
`dfcc4ed6`) trata `TREE` como `TREE_UNPROVEN`, termina o job uma vez e volta
ao mesmo `accounting`, que continua levantando: o laço só sai por
`held = CLEANUP`, e o orquestrador estaciona o owner (`CONTROL_HELD`). Já
`Owner.close()` prova quietude por outro caminho (contagem bruta de ativos
`== 0`, membros vazios, espera sinalizada, EOF) e não olha o total. Uma
árvore que já teve total maior que 2, mas está quieta, vira retenção
permanente em vez de rejeição com owner `CLOSED`.

Os testes reproduzem isso com o `Owner` real e o `Kernel` falso existente de
`tests/test_pg16_shell_admission_win32.py` (carregados por `runpy`, sem DLL,
processo, thread, sleep ou leitura de runtime/config/binário): setup vê
`(1, 1)`; depois do resume falso, total 3 e ativos 0, launcher sinalizado,
saída normal e EOF, sem membros. O `_supervise` real termina em `CLEANUP`
com `TREE_UNPROVEN`, e o `close` real do mesmo owner fecha com ledger vazio.
Controle negativo: total 2 supervisiona e fecha normalmente. Isso caracteriza
o comportamento antigo inalterado; não prova as contagens nem a causa da
rodada real.

## 2. Primitivo futuro e contrato menor

Proposta do root: `reconcile(owner, error_type, facts)`. **Ajuste proposto
antes de implementar:** retirar `error_type`. Toda exceção comum é tratada
igual (retém, sem mensagem) e o controle propaga, então o tipo do erro do
backend não decide nada; mantê-lo só aumentaria a superfície. Os testes
fixam `reconcile(owner, facts) -> str` e `VERDICTS = ("REJECTED_CLOSED",
"RETAIN", "NOT_APPLICABLE")`. Se o root preferir os três argumentos, basta
acrescentar o parâmetro ignorado nos testes e no módulo antes do RED.

Regras (`docs/poc/pg16_shell_tree_reconcile.py`, menos de 100 linhas, sem
imports, sem chamador operacional, CLI, sistema de arquivos, nativo,
controle ou recuperação de processo antigo; atributos tocados só `close`,
`state` e `get`):

1. `facts` precisa ser `dict` exato, com todas as chaves `str` exatas (V7, §6),
   e `held` e `reason` `str` exatos iguais
   a `CLEANUP` e `TREE_UNPROVEN`, e `terminated`, `signaled`, `eof`
   exatamente `True`; senão `NOT_APPLICABLE`, sem chamada.
2. `owner.state` precisa ser `str` exato `RUNNING` (leitura sob `try`);
   senão `RETAIN`, sem chamada.
3. Uma única chamada `owner.close()`. `Exception` ⇒ `RETAIN`, sem ler
   mensagem nem atributos. `BaseException` de controle propaga inalterada.
4. `REJECTED_CLOSED` só se o retorno for exatamente `None` **e**
   `owner.state` for `str` exato `CLOSED`; qualquer outra combinação ⇒
   `RETAIN`.

Nunca muta `facts` nem o registro; nunca aprova política ou runtime, não
mexe em limites, não muda a aceitação do `accounting` (a rejeição
`TREE_UNPROVEN` continua) e não libera registro. Um chamador futuro revisado
teria de preservar a rejeição, reservar a tentativa antes do efeito, liberar
só o owner provado `CLOSED` e nunca fechar duas vezes; nenhuma integração com
coordenador agora.

## 3. Testes e base de comparação

Enquanto o módulo não existe, os testes usam `legacy_reconcile`, substituto
transparente e congelado do comportamento atual: nenhuma reconciliação, o
owner fica retido (`RETAIN`). Assim a pós-condição desejada falha por
asserção, não por módulo ausente. Pela minha contagem (a medir pelo root),
40 casos: passam já os 3 de caracterização/negativo e os 5 de estado de owner
desconhecido; falham os demais (fechamento do TREE quieto, fechamento único,
fatos inelegíveis ou malformados, close que não prova quietude, retornos
malformados, exceção hostil, identidade do controle e o teste estático do
módulo). Depois do RED, nenhuma asserção muda; sem skip/xfail.

Casos: caracterização (CLEANUP/TREE_UNPROVEN/terminado/sinalizado/EOF, owner
`RUNNING`, `accounting` levanta `WIN32_TREE`, um `TerminateJobObject`, sem
fechamento duplo); close independente fecha; total 2 normal; reconciliação
fecha com fatos intactos (inclusive identidade do `bytearray`) e chamada
única; segunda chamada não fecha de novo; 12 fatos inelegíveis por valor ou
tipo e 4 malformados ⇒ `NOT_APPLICABLE` sem chamada; 5 estados de owner ⇒
`RETAIN` sem chamada; 5 casos reais de não quietude (ativo extra, membro
extra, não sinalizado, `accounting` falho, ledger parcial) ⇒ `RETAIN` com
ledger não vazio; 6 retornos malformados ⇒ `RETAIN`; exceção hostil
redigida; controle com identidade; módulo pequeno, sem imports, CLI ou
efeitos de import (não é alegação de pureza matemática).

## 3.1 Refinamento V2 (testes antes do módulo)

RED medido pelo root com o módulo ausente: 40 coletados, 8 aprovados, 32
falhas (31 `AssertionError` + 1 `pytest.fail`), sem erros nem skips, 1,939 s;
os 3 de caracterização, inclusive o close direto no mesmo owner falso,
passaram (não é prova da causa real). Fonte e teste arquivados como
`red40.tests.txt`/`red40.json` em `tree-reconcile-review-20261104`. A
retirada de `error_type` foi aceita pelo root como escolha rotineira sob
delegação: assinatura `reconcile(owner, facts)`.

(Correção: os artefatos `red40` são o teste e o relatório, não uma cópia de
fonte do backend.)

V2 muda os 40 casos só em espaços (uma linha longa de `setitem` quebrada e
duas assinaturas unidas, conforme o Ruff) e acrescenta seis regressões:
`dict` exato exigido (subclasse com `get`/`__getitem__` espiões nunca lida,
`NOT_APPLICABLE`, sem close); leitura inicial de `state` com exceção comum
hostil ⇒ `RETAIN` sem close e sem inspecionar texto ou args; a mesma leitura
com controle ⇒ propaga com identidade, sem close; `close` com retorno `None`
e leitura final de `state` com exceção comum ⇒ `RETAIN`, close uma vez; a
mesma leitura final com controle ⇒ propaga, close uma vez; `Owner` real com
bytes tardios no pipe ⇒ `RETAIN`, ledger não vazio, sem fechamento duplo.
(Correção: só os quatro casos de propriedade hostil usam o owner falso
pequeno; o caso da subclasse de `dict` usa o `Owner` real, como o sexto.)

**Limitação encontrada no backend consumido (não alterada):** depois que o
`Owner` observa EOF e grava `eof = True`, `_peek` devolve logo `(None, True)`
e `close()` não relê o pipe. Bytes injetados depois do EOF em cache não são
detectados, e um teste exigindo `RETAIN` nesse caso nunca passaria sem mudar
a fonte consumida. O sexto caso modela bytes tardios vistos **antes** desse
cache (zera `eof` no owner de teste), quando o `close` real relê o pipe e
recusa. Com o escritor fechado, bytes novos depois do EOF não deveriam ocorrer
na prática, mas isso não foi medido.

O root aceitou, como escolha rotineira sob delegação, essa adaptação do
caso de EOF (bytes antes do EOF em cache) e a assinatura de dois argumentos.
Depois do EOF em cache o backend não reconsulta o pipe; nenhuma proteção
contra isso é alegada.

## 3.1.1 RED46 e implementação (V3)

RED medido pelo root com o módulo ausente e o substituto `legacy_reconcile`:
46 coletados, 9 aprovados, 37 falhas (34 `AssertionError` + 3
`pytest.fail`), sem erros nem skips, 2,043 s. O prefixo AST dos 40 casos
originais ficou exatamente igual depois das mudanças de espaços; Ruff,
format e mypy do teste aprovados. Teste
`65696a29a3b29b58cd64109fe0812f2fa20269502191fc4fcf70b35d80924f2f` (15829
bytes) arquivado como `red46.tests.txt`/`red46.json` e **congelado**.

Implementado `docs/poc/pg16_shell_tree_reconcile.py` (V3), sem mudar o
teste nem as fontes consumidas. Contrato atual, exatamente:

- `VERDICTS = ("REJECTED_CLOSED", "RETAIN", "NOT_APPLICABLE")`;
  `reconcile(owner, facts) -> str`; sem imports, CLI, sistema de arquivos,
  processo, thread, sinal ou preparação nativa; sem chamador operacional nem
  recuperação de processo antigo.
- `_eligible`: `type(facts) is dict`; `held`/`reason` `str` exatos iguais a
  `CLEANUP`/`TREE_UNPROVEN`; `terminated`, `signaled`, `eof` `is True`.
  Inelegível ⇒ `NOT_APPLICABLE` antes de qualquer acesso ao owner.
- `_state_is`: uma leitura protegida de `owner.state`; `Exception` conta
  como desconhecido; exige `str` exato.
- `reconcile`: estado inicial exato `RUNNING`, senão `RETAIN`; um único
  `owner.close()`; `Exception` ⇒ `RETAIN` sem inspecionar texto, args ou
  contexto; retorno diferente de `None` ⇒ `RETAIN`; leitura final protegida
  exata `CLOSED` ⇒ `REJECTED_CLOSED`, senão `RETAIN`. Nenhum `except
  BaseException`: o controle propaga com a mesma identidade.
- Nunca muta fatos ou registro; sem timer, retry, registro global, framework
  ou mudança de limite. Não copia o supervisor nem se liga a hook,
  coordenador ou entrada.

O programador não executou testes nem gates estáticos.

**Medido pelo root na V3:** fonte
`58a3fd5f2be9a895a36ff2ff060b8a4fcbb02bfd8c96c1c9eccaf1ea79d9a81d` (2573
bytes, 67 linhas); **46/46** próprios em 2,133 s, sem erros nem skips; Ruff
do teste e erros de PoC, format (2 arquivos) e mypy do teste nos alvos 3.11 e
3.14 aprovados; teste `65696a29` congelado e as dez fontes aceitas
inalteradas. Na medição V3 a seleção relacionada ainda não estava executada;
o resultado posterior está na seção 5.

**V4, só editorial:** o root apontou um único P3 na docstring do módulo: a
frase "nothing is released" era falsa sem qualificação, porque o
`owner.close` delegado libera handles do próprio owner. A docstring do módulo
agora diz que o primitivo nunca remove ele mesmo uma entrada de registro,
que o `close` delegado **pode** liberar handles do owner, que não há garantia
de pureza matemática nem nativa e que não há chamador operacional atual.
Nenhum código executável, constante, docstring de função ou teste mudou; a
fonte `58a3` foi arquivada pelo root como dado (`pre-editorial58a3.source.txt`) para
comparação de AST ignorando só a docstring do módulo.

## 3.2 Obrigações de um chamador futuro

O helper não é validador de autenticidade nem motor genérico de
recuperação: não libera o registro, não muta fatos e só transforma um
retorno `None` com estado exato `CLOSED` em `REJECTED_CLOSED`, que é
rejeição com fechamento, nunca aprovação. Um chamador futuro revisado teria
de reter o `Owner` original vindo das fontes pinadas, o método ligado e a
proveniência do ledger, reservar uma única tentativa **antes** de chamar
`reconcile`, preservar a rejeição `TREE_UNPROVEN`, liberar só o owner
provado `CLOSED` e nunca fechar duas vezes. `owner.close` é um efeito nativo
**adiado**, que só aconteceria se esse chamador existisse: o módulo é
isolado e privado e só é exercitado com fakes, não é matematicamente puro, e
não há chamador operacional agora.

## 3.3 Semântica das contagens (fontes do root)

Páginas primárias consultadas pelo root, não pelo programador:
[JOBOBJECT_BASIC_ACCOUNTING_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)
e
[JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
Pelo relato do root: `TotalProcesses` inclui todo processo que já foi
associado ao job, inclusive os encerrados e as associações que falharam por
causa do limite; o limite de processos ativos é concorrente. Isso sustenta
que as duas grandezas são distintas; **não** autoriza aceitar total maior que
2 nem explica a causa da rodada real. O limite de total do código antigo
continua sendo política estrita. As referências da documentação sobre
`ActiveProcesses` indicam fatores que podem afetar a contabilidade, mas não
são causa medida nem garantia ampla da API.

## 4. Lacunas

Causa real, contagens do job e quietude da rodada real continuam não
comprovadas. Nenhuma variante do chamador/orquestrador/entrada nem pins
operacionais novos neste lote. Limites, orçamentos, leitura estrita e política de fio
inalterados. Native3s NOT_MEASURED, entry_gate NOT_EVALUATED;
B1/B2/D090gate2/C1/SQL e produção abertos. Sem Docker/PG/SQL/deploy, outro
escritor, conta, modelo ou contorno de cota.

## 5. Validação final isolada

Fonte final43eaefd7 (2729bytes/69linhas), teste65696a29 congelado.
AST de constantes, código e docstrings de função igual à candidata58a3;
só a docstring do módulo mudou. Seleção final:589/589em41,239s, incluindo
os46 sobre a fonte final, zero falhas/erros/skips. Ruff do teste e análise
de erros do PoC, format2 e mypy1teste alvos3.11/3.14 aprovados. O PoC fica
fora do alvo mypy; não há medição de runtime3.14. Dez fontes consumidas e
estado16 intactos. Evidências, hashes completos, RED40/46 e limites em
TREE-RECONCILE-VALIDATION e tree-reconcile-review-20261104/final-review.json.

Nenhum chamador operacional foi implementado. Rejeição da política permanece;
CLOSED nos fakes não é prova nativa nem ativa Gateway/produção. Próxima etapa
exige nova composição e pins operacionais revisados, sem repetir a tentativa
consumida ou editar suas fontes.

Os gates desta seção (46/46 e 589/589) são históricos, anteriores ao guarda
de chaves da seção 6.

## 6. Domínio das chaves — testes antes do endurecimento (V6)

O root reproduziu o P3 informativo da revisão final: um `dict` exato com uma
chave não-`str` cujo `__hash__` colide com `hash("held")` e cujo `__eq__`
levanta uma exceção comum faz `dict.get` invocar esse `__eq__`, e a exceção
sai de `reconcile` antes de qualquer acesso ao owner (close não chamado).
Isso está **fora** do contrato atual de chaves confiáveis (os fatos vêm do
`_new_facts` do próprio chamador); não é vulnerabilidade demonstrada do
produto nem causa da rodada real. Sob a delegação, o root escolheu endurecer
o tipo das chaves agora, em vez de só documentar o risco, sem framework nem
fronteira pública nova.

A fonte `43eaefd7` continua **byte a byte igual** até o RED, arquivada pelo
root como `pre-keys43ea.source.txt`. O prefixo dos 46 casos (teste
`65696a29`: asserções, helpers, fixtures, substituto) não muda; foram
acrescentados só três testes e helpers privados mínimos (`MarkerError`,
`CollidingKey`, `keyed`), sem imports novos:

1. `dict` exato com chave não-`str` que colide com `held` e cuja igualdade
   levanta exceção comum ⇒ `NOT_APPLICABLE`, igualdade nunca invocada,
   `state` e `close` do owner intocados;
2. a mesma colisão com igualdade permissiva (responderia `True` e deixaria
   passar `CLEANUP`) ⇒ nunca comparada, sem close, `NOT_APPLICABLE`;
3. fatos elegíveis com uma chave não-`str` extra (`7`) ⇒ `NOT_APPLICABLE`,
   sem acesso ao owner nem close.

Correção mínima proposta, a aplicar só depois do RED e de nova autorização
do root: logo depois de `type(facts) is dict` e **antes** de qualquer `.get`
ou comparação, percorrer as chaves do `dict` e exigir `type(key) is str` em
todas, recusando sem chamar hash, igualdade, `str`, `repr` ou `bool` de chave
estrangeira. Sem limite de tamanho, framework, import ou método novo. Os
fatos privados de `_new_facts` continuam válidos (só chaves `str`), a
rejeição TREE continua, e as obrigações do chamador futuro (origem do owner,
método e ledger) não mudam. Os testes novos não foram executados pelo
programador; a contagem real fica com o root.

**RED49 medido pelo root**, com a fonte `43ea` byte a byte intacta: 49
coletados, 46 aprovados, 3 falhas (1 `MarkerError` + 2 `AssertionError`),
só nos três testes novos, sem erros nem skips, 2,580 s. Prefixo AST dos 46
casos exatamente preservado; Ruff, format e mypy do teste aprovados. Teste
`ad0742c02abe3544b9b4c5607df88563d1c0bf6458f278050cc0829adefe3a04` (17763
bytes) **congelado**, arquivado como `red49.tests.txt`/`red49.json`.

**Guarda implementado (V7)**, só em `_eligible`: logo depois de
`type(facts) is dict` e antes de qualquer `.get`, um laço direto sobre o
`dict` (`for key in facts`) exige `type(key) is str` para todas as chaves e
devolve `False` na primeira que não for. A iteração de um `dict` exato não
chama hash nem igualdade das chaves, e o guarda não chama `bool`, `str` ou
`repr` delas. Mudou só esse trecho e a docstring de `_eligible`; nenhuma
constante, função, import, cache, limite de tamanho ou política de retorno
foi acrescentada ou alterada. Propagação do controle, `close` único, estado
`str` exato, pós-condição `None` + `CLOSED` e imutabilidade dos fatos e do
registro ficam iguais. Os fatos do `_new_facts` do chamador continuam
válidos; não há alegação de autenticidade nem superfície pública nova. O
root aceitou esse endurecimento sob a delegação, mesmo fora do contrato de
confiança anterior, sem aprovação individual nova do usuário. Os gates
históricos 46/46 e 589/589 da seção 5 continuam válidos para o escopo
anterior; testes e gates sobre a fonte com o guarda não foram executados pelo
programador.

## 7. Validação final da guarda de chaves (V7)

Após RED49, Claude2 alterou só _eligible e sua docstring. Iteração de chaves
str exatas precede qualquer get. Constantes, docstring do módulo, _state_is
e reconcile mantiveram AST idêntico. Teste49 ad0742c0/17763bytes congelado.
Fonte final `bb1f1984f5a144564a56e23fb5c4797dc0851651b608012ce229cc14d12a801b`,
2935bytes/74linhas.

Root leu o código completo:49/49 em2,242s e592/592relacionados em48,705s,
zero falhas/erros/skips. Ruff do teste e análise de erros do PoC, format2 e
mypy1teste alvos3.11/3.14 aprovados. A sonda separada confirmou
NOT_APPLICABLE/zero comparações estrangeiras/zero close na chave colidente.
Dez fontes aceitas/estado16 intactos; nenhuma integração ou efeito nativo.
Evidências finais em TREE-RECONCILE-VALIDATION e final-key-review.json;
final-review.json conserva a medição histórica anterior à guarda.

Não há caller operacional novo nem gate de produto liberado.
