# Composição pinada do coletor — desenho

Data: 2026-11-03. Sob a delegação geral vigente e revisão do root; não é
aprovação individual do usuário nem ativação nativa. Programador Claude2,
sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço
`medium`. Base `2ef95a2`. Testes congelados `a3ebf78b` (21009 bytes, 63
casos; RED medido pelo root: 63 `FileNotFoundError`, 0,907 s). O módulo
`docs/poc/pg16_shell_native_control_collect_pinned.py` foi implementado na
V4. Fonte109ab960/4291bytes: o root mediu63 próprios e719 relacionados
aprovados sem falhas/erros/skips, com duas sondas independentes. Gates e
limites em [validação](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-PINNED-VALIDATION.md).
Nenhum teste foi executado pelo
programador. O uso do seam de teste vale só neste laboratório, sob a
delegação geral; não é aprovação individual nem ativação nativa.

Pins exatos:

- coletor `1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52`,
  20571 bytes;
- backend Win32 `ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a`,
  22315 bytes.

Também fixos: verificador `b3755d49`, entrada, orquestrador, adaptador,
backend, chamador e estado de 16 campos. Destino final segue Docker Oracle
Linux 9.8.

Histórico: o primeiro teste (`515b7243`, 18629 bytes) deu, medido pelo root,
52 coletados, 51 erros + 1 falha, todos `FileNotFoundError`, 0,926 s; o
relato do programador de 41 casos estava errado. Ruff apontou 3 erros (dois
E501 e um PLR0911 em `tampered`), format 1 arquivo fora do padrão; mypy do
teste limpo. Havia ainda uma contradição: o AST proibia o atributo/string
`backend`, mas o contrato exige `record.backend`. V3 corrige: a proibição
fica só em função/classe chamada `backend` (além de nada público), o
`tampered` usa um mapeamento, linhas longas foram quebradas e entraram casos
novos (seção 4).

## 1. Escopo

Laboratório só com fakes. O root aceita, apenas aqui, o uso privado do seam
de teste `_backend` numa cópia executada do coletor. `_backend()` do coletor e
`backend()` do Win32 nos arquivos congelados seguem `None`. Sem CLI/`main`,
sem backend público disponível, sem leitura de arquivo, DLL, processo ou
import de módulos do checkout; `_load_native` não é referenciado.

## 2. Contrato

Módulo importa só `hashlib`. Constantes `COLLECTOR_SHA`, `COLLECTOR_SIZE`,
`BACKEND_SHA`, `BACKEND_SIZE` (os pins exatos acima); `_ATTEMPTS = []`
(lista pegajosa, por namespace do módulo); registro `_Attempt` com atributos
`collector`, `native` (dicts de namespace), `api` e `backend`, e `repr`
fechado.

`_collect_pinned(collector_src, backend_src, api, nonce, argv0) -> tuple`:

1. As duas fontes: `type(...) is bytes`, tamanho e SHA iguais aos pins, ambas
   conferidas antes de qualquer `compile`/`exec`. Falha ⇒
   `("INVALID", "COLLECT_SOURCE", None, None)` sem consumir a tentativa.
2. `api is None` ⇒ `COLLECT_UNAVAILABLE`, sem `exec` nem recurso a carregador
   nativo, sem consumir.
3. `_ATTEMPTS` não vazio ⇒ `COLLECT_POISONED`, sem `exec` nem chamada `api`.
4. Antes do primeiro `exec`, publica em `_ATTEMPTS` um `_Attempt` que
   referencia os dois dicts (vazios, só com `__name__`) e a `api`. Esse
   registro original fica retido para sempre: retorno limpo, exceção,
   controle ou montagem parcial. É retenção durável do modelo, não limpeza
   nem imunidade de tempo de vida do processo.
5. `exec(compile(collector_src, ...))` e depois o backend, compilando os
   próprios objetos `bytes` recebidos (nunca relidos); constrói
   `_Win32Backend(api, ns_collector)` com os DTOs originais da cópia,
   grava-o em `record.backend`, troca só `ns_collector["_backend"]` e chama
   `collect(nonce, argv0)` uma vez. Não limpa nem substitui `_ACTIVE`/
   `_POISON` da cópia; não instala nada em `sys.modules`.
6. `Exception` na montagem ou na política ⇒ `COLLECT_INTERNAL`, sem texto.
   `BaseException` de controle propaga com a mesma identidade, sem perder o
   registro.
7. Saída revalidada: `type(result) is tuple` com 4 itens; label, motivo e
   hashes `type(...) is str` (sem subclasse, `bool` ou `int`);
   `VERIFIED_APPROVED`/`VERIFIED_REJECTED` + `"OK"` + dois hex minúsculos de
   64 (os dois conferidos); ou `"INVALID"` + motivo do `REASONS`
   (`frozenset`) da cópia executada, diferente de `"OK"`, + `None, None`.
   Qualquer outra coisa ⇒ `COLLECT_INTERNAL`.

## 3. Limites de confiança

O pin prova o conteúdo dos bytes recebidos, não a origem da captura, nem a
stdlib importada pelas fontes (`dataclasses`, `hashlib`, `re`, `ctypes`,
`struct`), nem a `api` injetada: os seams privados não são fronteira de
autenticação hostil. Os testes de forma de saída trocam os pins por uma fonte
falsa; isso exercita só a revalidação, não prova nada sobre a confiança do
coletor real. Uma tentativa por namespace do módulo: falha de montagem
inutiliza a composição até um novo namespace.

## 4. Testes (antes do módulo)

Setup lê as fontes e carrega por `runpy` os ajudantes `FakeNt`/árvore dos
testes Win32 e o construtor de bundle; durante o exercício `open`, `os`,
`Path`, processo, thread, `runpy`, `importlib` e DLL ficam proibidos por
`monkeypatch.context()` (restaurado antes do relatório). Cobrem: pins; pureza
AST; todo tipo/tamanho/SHA adulterado nas duas fontes sem `exec`;
indisponível sem consumo; bundles aprovado/rejeitado com identidade dos DTOs,
dos ledgers e dos `bytes` compilados; argumento julgado pela política uma vez;
controle durante cada `compile` e antes da publicação do backend; falha de
montagem; fechamento incerto e controle na coleta sem fechamento forçado ou
repetido; sentinela fora da tupla, `repr` e saída; `sys.modules` e cópias
originais intactos; revalidação da forma de saída. V3 acrescenta 10 casos
de tipo exato (subclasse de `str` no label, motivo, `"OK"` ou hash; subclasse
de `tuple`; motivo `bool`/`int`; segundo hash maiúsculo, curto ou não hex) e
1 interrupção no primeiro `exec`, que confere que os dicts originais vazios e
a `api` já estavam retidos no registro. Total: 63 casos (RED medido pelo
root antes do módulo; histórico preservado: 52 na V2, 63 na V3).

Implementação (V4): uma função `_collect_pinned` e dois auxiliares de
validação (`_pinned`, `_closed`), um registro `_Attempt` com `__slots__` e
`repr` fechado, e um provedor que devolve `record.backend` para o seam
copiado. Ordem: pins das duas fontes, `api`, tentativa consumida, publicação
do registro, `compile`/`exec` do coletor, `compile`/`exec` do backend,
construtor, troca do seam, `collect`, revalidação. `except Exception` devolve
`COLLECT_INTERNAL`; não há limpeza, nova tentativa, remoção ou reset.

## 5. Lacunas antes de qualquer efeito nativo

Procedimento revisado de captura dos bytes; conversões do `_NativeApi` e gate
ABI no CPython alvo; perfil da âncora (NTFS local, não marcado como mídia
removível, não remoto; a ausência do bit não atesta hardware fixo nem
removível);
suporte das classes, diretório com `FILE_OPEN_REPARSE_POINT`, streams de
diretório e `NtClose` reais; pré-checagem de SO/escritor único; procedimento do
operador (root/nonce/invocação não criados aqui); ativação exigiria chamador
revisado ou mudança de fonte congelada. Native3s NOT_MEASURED, entry_gate
NOT_EVALUATED, identidade LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED; gates de
produção abertos.
