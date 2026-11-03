# Coletor de evidência dos controles nativos — política com fakes (desenho)

Data: 2026-11-03, America/Sao_Paulo. Sob a delegação vigente e revisão do
root; não é aprovação individual do usuário. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Desenho e testes vieram antes do módulo. Com o módulo ausente o root mediu a
baseline de recurso ausente: 136 coletados, 134 erros de fixture e 2 falhas
de chamada, todos `FileNotFoundError` (1,155 s, saída 1), sobre os testes
`720fb16a…276c` (31665 bytes); não é regressão de produto. Depois o
programador implementou `docs/poc/pg16_shell_native_control_collect.py` e
corrigiu quatro pontos de estilo dos testes sem retirar casos nem asserções
(limite exato `max_entries == 16` conferido no fake, linha longa dividida e
duas variáveis de laço substituídas por cópia local). Estado: implementado,
aguardando revisão e gates do root; nenhum teste executado pelo programador.

Fixos e não tocados: verificador puro
`b3755d492ce147596a27dd9a36bc0ecf66686efd65ef60178915ab2d1d1f7a10`
(24616 bytes) e seus testes `808869aa…` (44944 bytes); entrada, orquestrador,
adaptador, backend, chamador, estado de 16 campos e tentativas consumidas.

Nota do revisor, após retomada de03/11: política com fakes revista,467testes
relacionados (incluindo141próprios) e gates estáticos aprovados. O último
ajuste foi apenas de anotação de fixture/redação; fonte1972ec74 intacta.
Resultados e falhas anteriores em
[validação](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-VALIDATION.md).
Não existe binding/coletor real nem medição nativa deste incremento.

## 1. Escopo e perfil de confiança

Incremento **só de política com fakes**. Não há módulo de ABI nativa, ctypes,
DLL, sistema de arquivos real, processo, comando, raiz ou nonce. O backend
padrão é indisponível: `collect` devolve sempre `INVALID/COLLECT_UNAVAILABLE`
sem ler nada, portanto o caminho de produção **não pode aprovar**. A injeção
de fake é seam privado de teste, não fronteira de segurança adversarial;
coerência obtida com handles simulados não prova segurança de handles reais.

Perfil explícito: âncora de volume confiável; operador confiável com o
namespace quiescente durante a coleta. Não há garantia de atomicidade
global, de ausência de mapeamentos graváveis pré-existentes, de origem,
autenticação, ACL, estado do SO, CIM ou cleanup nativo. Processo hostil do
mesmo usuário, administrador e kernel estão fora do perfil.

Suporte documental prospectivo (consultado pelo root, não pelo programador;
suporte no Windows local NOT_MEASURED):
[`NtCreateFile`](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
(abertura relativa a `RootDirectory`, `FILE_OPEN_REPARSE_POINT`; atributos
de modo usuário zero ou `OBJ_CASE_INSENSITIVE`, sem promessa geral de
`OBJ_DONT_REPARSE`),
[`FILE_ID_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)
(volume e `FILE_ID_128`) e
[`FILE_ID_EXTD_DIR_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_extd_dir_info)
(classes 0x13/0x14, identificador de 128 bits). Os links são referências
para revisão, não atestação local. `FILE_ID_BOTH_DIR_INFO.FileId` tem 64
bits e nunca é usado como identidade. Regras do futuro parser bruto de
enumeração (deslocamento `NextEntryOffset` alinhado e dentro do buffer,
`FileNameLength` par e limitado, contagem limitada, UTF-16 válido) ficam
adiadas para o backend nativo, com revisão própria.

## 2. API (módulo futuro)

- `collect(nonce, argv0) -> (label, reason, summary_sha256, transport_sha256)`.
  `nonce` e `argv0` lidos uma vez como `str` exatos (`nonce` 32 hex
  minúsculos; `argv0` 1–1024 caracteres sem NUL), senão
  `("INVALID", "COLLECT_ARGUMENT", None, None)` antes de qualquer backend.
- Rótulos: `VERIFIED_APPROVED`, `VERIFIED_REJECTED`, `INVALID`. Motivos:
  `OK`, os motivos fechados do verificador repassados, ou do coletor:
  `COLLECT_UNAVAILABLE`, `COLLECT_POISONED`, `COLLECT_ARGUMENT`,
  `COLLECT_OPEN`, `COLLECT_REPARSE`, `COLLECT_VOLUME`, `COLLECT_TYPE`,
  `COLLECT_LISTING`, `COLLECT_EXTRA`, `COLLECT_MISSING`, `COLLECT_IDENTITY`,
  `COLLECT_LINKS`, `COLLECT_STREAMS`, `COLLECT_DELETE_PENDING`,
  `COLLECT_CAP`, `COLLECT_READ`, `COLLECT_CHANGED`, `COLLECT_UNSUPPORTED`,
  `COLLECT_BACKEND`, `COLLECT_SOURCE`, `COLLECT_CUSTODY`,
  `COLLECT_CLEANUP`, `COLLECT_INTERNAL` (`REASONS` fechado exportado).
- Hashes SHA-256 dos dois arquivos públicos só com rótulo `VERIFIED_*`;
  qualquer outro desfecho tem `None`, `None`. Nada de bytes privados,
  caminhos, tokens, PIDs, argv ou texto de exceção; sem impressão.
- Seam privado `_backend()`: produção devolve `None`. Testes substituem só a
  cópia do módulo. Não existe callback público de verificador ou captura.
- `_POISON`: lista do módulo que retém fortemente backend, ledger e slots
  incertos; não vazia ⇒ toda chamada futura devolve `COLLECT_POISONED`
  antes de tocar o backend.

## 3. Operações e DTOs fechados

Operações fixas do backend (seis): `open_anchor(slot)`,
`open_child(parent, name, kind, slot)` (`kind` `"DIR"` ou `"FILE"`),
`query(handle) -> Info`, `list_dir(handle, max_entries) -> tuple`,
`read(handle, limit) -> bytes`, `close(handle) -> bool`.

DTOs do módulo, dataclasses congeladas com `repr` fechado (sem tokens,
nomes, bytes ou ids); validados por `type(x) is` antes de qualquer método,
rejeitando subclasses e `bool` como `int`:

| DTO | Campos e limites |
|---|---|
| `Handle` | `token`: `int` exato `1 <= t < 2**64` |
| `Info` | `reparse`, `directory`, `delete_pending`: `bool`; `volume`: `int` `0..2**64-1`; `file_id`: `bytes` exatos de 16; `links`: `int` `1..2**32-1`; `end_of_file`: `int` `0..2**63-1`; `change_time`: `int` com sinal de 64 bits; `streams`: `tuple` de até 8 `str` exatos de 1–64 caracteres sem NUL |
| `Entry` | `name`: `str` exato, 1–255 unidades UTF-16, sem NUL, `/`, `\` ou `:`; `directory`: `bool`; `file_id`: `bytes` exatos de 16 |
| `Slot` | mutável, do módulo; `value` inicialmente `None`, escrito pelo backend |

Listagem: `tuple` exato de até 16 `Entry`, sem nomes repetidos. DTO
malformado ⇒ `COLLECT_BACKEND`. `list_dir` que levanta
`NotImplementedError` (classe de enumeração sem suporte) ⇒
`COLLECT_UNSUPPORTED`.

## 4. Inventário fixo e tetos

Componentes relativos fixos a partir da âncora; ancestrais nunca são
listados. No máximo 64 slots de aquisição; sem varredura de árvore.

- Fonte do verificador: `Users`, `w.filho`, `Desktop`, `codes`, `mask`,
  `docs`, `poc`, arquivo `pg16_shell_native_control_verify.py`; teto 65536.
- Público: o mesmo prefixo até `poc`, depois `evidence`,
  `pg16-native-control-<NONCE12>`; listagem exatamente `summary.json`
  (teto 16384) e `transport.json` (teto 4096).
- Privado: `Users`, `w.filho` (reusados), `AppData`, `Local`, `Temp`,
  `maskgw-pg16-native-control-v1-<NONCE32>`; listagem apenas diretórios
  `case-1`, `case-1..2` ou `case-1..3` contíguos; cada caso com
  `invocation.json`, `supervision.json` (4096), `local-stdout.bin` (1024) e,
  no caso 3, `snapshot.json` (4096) e `audit.json` (65536).
- Soma dos artefatos (público e privado) ≤ 262144; fonte com teto separado.
  Com os tetos individuais atuais a soma não é alcançável: é defensiva.
- Nonces são placeholders; nada é gerado.

## 5. Regras por objeto e ordem

1. Âncora, depois cadeia do repositório até `poc`, fonte, `evidence`,
   diretório público, listagem pública, arquivos públicos, cadeia privada,
   raiz privada, listagem, diretórios de caso, listagens, arquivos.
2. Todo diretório: não reparse (`COLLECT_REPARSE`), mesmo volume da âncora
   (`COLLECT_VOLUME`), diretório (`COLLECT_TYPE`), não pendente de exclusão
   (`COLLECT_DELETE_PENDING`), `streams == ()` (`COLLECT_STREAMS`).
3. Todo arquivo: as mesmas, mais não diretório, `links == 1`
   (`COLLECT_LINKS`), `streams == ("::$DATA",)`, `end_of_file` dentro do teto
   antes de ler (`COLLECT_CAP`); `read(handle, teto + 1)` com exatamente
   `end_of_file` bytes (`COLLECT_READ`); segundo `query` igual **ao `Info`
   inteiro** anterior (`COLLECT_CHANGED`).
4. Listagem (só dos diretórios próprios): DTO válido; tipo de cada entrada
   (`COLLECT_TYPE`); nomes extras (`COLLECT_EXTRA`) antes de faltantes
   (`COLLECT_MISSING`); casos não contíguos ou vazios (`COLLECT_LISTING`);
   `file_id` de 128 bits da entrada igual ao do handle aberto pelo nome e
   volume igual ao da âncora (`COLLECT_IDENTITY`), sem atalho de 64 bits.
5. Ao final, nova listagem de cada diretório próprio idêntica à primeira
   (`COLLECT_CHANGED`).
6. Falha de abertura ⇒ `COLLECT_OPEN`; outra falha comum do backend em
   `query` ⇒ `COLLECT_BACKEND`, em `read` ⇒ `COLLECT_READ`, em `list_dir`
   ⇒ `COLLECT_LISTING`; falha comum do próprio módulo ⇒ `COLLECT_INTERNAL`.
7. Só depois de todos os handles fechados com sucesso: SHA da fonte
   capturada igual ao pin (senão `COLLECT_SOURCE`, sem executar), execução em
   namespace novo, `Expected(nonce=…, argv0=…)` e `verify` sobre os bytes
   capturados; o resultado do verificador é repassado.

## 6. Ledger de custódia (sem framework)

- Slot reservado e retido no ledger **antes** de cada abertura; depois da
  chamada (retorno ou exceção) o valor do slot é lido uma única vez.
- Slot vazio após exceção ⇒ `COLLECT_OPEN`; vazio após retorno ⇒
  `COLLECT_BACKEND`. Handle válido e único é adotado mesmo se a abertura
  levantou (handle tardio/parcial nunca se perde).
- Valor desconhecido/malformado, ou token já possuído (alias) ⇒
  `COLLECT_CUSTODY`, envenenamento: retêm-se backend, ledger e slots; todos
  os slots daquele token ficam em quarentena e nunca são fechados; nunca se
  fecha handle arbitrário.
- Limpeza: fecha uma única vez, em ordem inversa, só handles comprovadamente
  únicos. Retorno `True` exato ⇒ fechado; `False`, tipo errado, exceção
  comum ou de controle ⇒ incerto, sem nova tentativa; incerteza ou
  quarentena retêm tudo em `_POISON`. Incerteza na limpeza ⇒
  `COLLECT_CLEANUP` (custódia prevalece), e o verificador não roda.
- Controle: a primeira interrupção (`BaseException` que não é `Exception`)
  vence; falha comum ou segunda interrupção na limpeza não a substituem.
  Interrupção surgida durante a limpeza de um desfecho comum torna-se a
  primeira: fecham-se os demais e ela propaga. Nenhuma interrupção nova é
  engolida e nenhuma posse se perde.

## 7. Testes com fakes

Backend falso com árvore em memória e handles simulados; bytes de bundle do
construtor manual dos testes do verificador; fonte do verificador lida do
arquivo pinado só no preparo. Depois do preparo os testes bloqueiam
sistema de arquivos, processos e nativo. Casos: indisponível por padrão,
argumentos, positivo APPROVED/REJECTED, repasse de INVALID do verificador,
reparse/volume/tipo/abertura/faltantes/extras/listagem, identidade incluindo
armadilha dos 64 bits baixos, links/streams/pendência (arquivos e
diretórios), tetos, leitura curta/longa/erro, alteração de cada campo do
`Info`, listagem final alterada, enumeração sem suporte, DTOs malformados,
pin da fonte, abertura parcial, alias e slot malformado, fechamento incerto,
matriz de controle, ordem de fechamento, operações permitidas, ausência de
vazamento e pureza do módulo.

## 8. Notas de implementação (política com fakes)

- Separação explícita: o módulo contém só a política, os DTOs e o ledger;
  não há ligação nativa, âncora real nem backend. A âncora confiável, a
  abertura relativa e o operador quiescente pertencem ao futuro backend e ao
  procedimento, sem garantia de atomicidade ou nativa.
- Cada `Info` é lido uma vez para uma tupla imutável validada por tipo exato
  antes de qualquer comparação; a comparação antes/depois usa essa tupla
  inteira. Listagens viram tuplas ordenadas `(nome, diretório, id)`.
- Ledger: registro e slot criados e retidos antes de chamar a abertura; o
  slot é lido uma única vez depois (retorno ou exceção). Quarentena e
  incerteza de fechamento colocam backend e estado (ledger e slots) em
  `_POISON` no mesmo instante em que ocorrem.
- Fechamento só de registros `OWNED`, uma vez, em ordem inversa; `True`
  exato é o único sucesso.
- Ordem de prioridade do desfecho sem controle: custódia, limpeza incerta,
  motivo da coleta, depois fonte e verificador.

### Achado da revisão de 1037b2d0 (regressões antes da correção)

Fonte `1037b2d08d11b744689011d6a73842025175e5a47ead15add74450248ab91eba`
(18360 bytes) e testes `30ad8821…` (31835 bytes): o root mediu 136 de 136
aprovados (5,184 s), Ruff/format limpos; base arquivada só como dados em
`docs/poc/evidence/native-collect-review-20261103`. Sondas fake
independentes reproduziram um achado de retenção de posse, em quatro
cenários: (1) handle válido cujo `token` é removido depois de preencher o
slot gera `COLLECT_INTERNAL`, 1 handle sem fechar e `_POISON` vazio;
(2) interrupção logo antes de `_cleanup` em `collect`, (3) depois de marcar
`CLOSING` e antes do `close`, e (4) em `_acquire` antes de `_adopt` após a
abertura retornar propagam a interrupção, mas deixam 31, 31 e 1 handles sem
fechar com `_POISON` vazio.

Regressões acrescentadas (casos anteriores intactos; só `import sys` novo no
topo), com fakes em memória e `sys.settrace` restaurando o rastreador
anterior: fronteira localizada uma vez no texto da fonte, disparo conferido.
Exigem a identidade da interrupção original (a primeira registrada vence,
inclusive contra uma segunda no intervalo antes da limpeza) e, para cada
cenário, ou todos os handles possuídos realmente fechados uma vez, ou
backend e todo handle não fechado retidos fortemente com chamadas futuras
recusadas antes do backend; nunca fechamento forçado ou repetido. O cenário
(1) exige `COLLECT_CUSTODY`. É injeção de falha em fakes, não medição de
sinal real do SO. Nenhum teste executado pelo programador.

Direção da correção — proposta histórica escrita antes do fix, agora
aplicada conforme o trecho "Correção aplicada" logo abaixo: um dono durável
mínimo do módulo,
registrado antes da primeira aquisição e liberado só depois de provado o
invariante terminal do ledger (todo registro fechado ou vazio); finalização
externa que retém em toda saída não provada, inclusive em intervalos fora
das chamadas ao backend. Registro reservado `NEW`/`CLOSING` não é `CLOSED`;
slot pendente nunca some. Leitura de `token` protegida: falha vira
quarentena. A garantia de controle se limita às interrupções registradas e à
retenção fechada; não há imunidade a término do processo nem a sinais fatais
repetidos.

RED medido pelo root antes da correção, com a fonte 1037b2d0 intacta: 141
coletados, 136 aprovados, 5 falhas, 0 erros (5,085 s, saída 1). Testes
vermelhos `8a3f9ebd…d7e8` (37929 bytes), com o prefixo dos 136 casos
preservado salvo `import sys`, arquivados como dados com a base e o
relatório na mesma pasta de revisão. Testes e arquivo congelados a partir
daqui.

Correção aplicada (só no módulo e neste desenho; nenhum teste executado pelo
programador, verde não alegado):

- `_ACTIVE`: lista de donos ativos do processo. O estado da coleta entra
  nela **antes da primeira aquisição** e só sai por `_release` quando o
  ledger é provadamente terminal: sem custódia nem incerteza e todo registro
  `CLOSED`, ou `EMPTY` com o slot ainda vazio. `NEW`, `CLOSING`, `OWNED`,
  `QUARANTINED`, `UNCERTAIN` ou valor tardio no slot não são terminais.
- `_POISON` continua pegajoso: recebe backend e estado (ledger, registros,
  slots e handles originais) em qualquer custódia, fechamento incerto ou
  ledger não provado. Com `_POISON` ou `_ACTIVE` não vazios, chamadas
  futuras devolvem `COLLECT_POISONED` antes do backend. Uso serializado em
  primeiro plano; sem promessa de concorrência.
- Finalização externa em `collect`: qualquer `BaseException` fora das
  chamadas protegidas (por exemplo antes de `_cleanup`, entre a marca
  `CLOSING` e o `close`, ou entre a abertura e `_adopt`) retém o dono, não
  fecha nada de novo nem repete `close`; a primeira interrupção registrada
  (`state.control`) vence; sem interrupção registrada, uma interrupção nova
  propaga e uma falha comum vira `COLLECT_INTERNAL`, ambas com retenção.
- Ledger sem prova terminal após uma limpeza que não levantou vira
  `COLLECT_CLEANUP` (custódia prevalece).
- `_adopt`: a leitura de `token` de um `Handle` conhecido é protegida; falha
  vira quarentena com o objeto original retido, nunca fechamento.
- Limites: retenção não é limpeza; fechamento simulado em fakes não é prova
  nativa; interrupções em instantes não registrados (por exemplo dentro do
  próprio tratador) ficam cobertas só pela retenção; término do processo e
  sinais fatais repetidos estão fora do alcance.

## 9. Pendências

- Backend nativo e sua posse de slots de saída ainda exigem desenho e
  revisão; suporte de `FILE_ID_INFO`/`FILE_ID_EXTD_DIR_INFO` não medido.
- Componentes do repositório fixados para esta máquina; se algum ancestral
  for reparse (por exemplo Desktop redirecionado), a coleta recusa.
- `argv0` é fornecido pelo chamador revisado; a carga da fonte capturada por
  SHA não autentica origem/importação futuras.
- Pré-checagem nativa, OS/CIM e proposta de execução seguem pendentes.
  Identidade LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED; Native 3 s NOT_MEASURED;
  entry_gate NOT_EVALUATED; destino Docker Oracle Linux 9.8 inalterado;
  gates de produção abertos.
