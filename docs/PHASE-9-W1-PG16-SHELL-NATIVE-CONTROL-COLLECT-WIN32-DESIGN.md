# Backend Win32 do coletor — contrato com fakes (desenho)

Data: 2026-11-03, America/Sao_Paulo. Sob a delegação vigente e revisão do
root; não é aprovação individual do usuário. Programador Claude2, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Base `dbde802`. Primeiros testes anteriores ao código: `7b5c113f`
(63332 bytes, 177 casos; baseline RED medida pelo root: 177 `FileNotFoundError`). O módulo
`docs/poc/pg16_shell_native_control_collect_win32.py` foi então implementado
(V5) só para fakes; nenhum teste foi executado pelo programador e nada nativo
foi carregado ou chamado pelo backend. Depois vieram as regressões da seção 9.
Estado atual: fonte `ccb3f74a`, testes finais `83c8f553` (189 casos),
revisados pelo assistente principal; 189 próprios e 656 relacionados
aprovados com fakes. Gates e falhas históricas em
[validação](PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-COLLECT-WIN32-VALIDATION.md).
Não é aprovação individual do usuário, atestação nativa ou liberação de produção.

Fixos: coletor `1972ec74` (20571 bytes) e testes `b6f165d1`, verificador
`b3755d49`, entrada, orquestrador, adaptador, backend, chamador e estado de
16 campos. Este laboratório Windows não é o destino final (Docker Oracle
Linux 9.8).

## 1. Escopo e fronteira

Um módulo de backend com implementação **só para fakes**: `backend()`
público devolve sempre `None` (coleta indisponível); `_load_native()` existe,
é preguiçoso e não é chamado; `_Win32Backend(api, dto)` é privado e
usado só por testes; `api` ausente ou incompleta é recusada com `OSError`,
sem recorrer ao carregador real. `api` (seis funções NT e uma Win32) e `dto`
(namespace do coletor com `Handle`, `Info`, `Entry`, `Slot`) são seams
privados, **não** fronteira de segurança hostil: identidade de classes não
autentica fonte. A ligação real por fonte pinada e o carregamento revisado
ficam para incremento próprio. Carga, aquisição e leitura reais exigem
pré-checagem e procedimento revisados. Nenhum suporte de API, sistema de
arquivos ou cliente é medido ou alegado.

## 2. ABI fixa (x64 apenas; recusa fora de ponteiro de 8 bytes)

Fontes primárias consultadas pelo revisor, não pelo programador:
[NtQueryDirectoryFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntquerydirectoryfile),
[FILE_ID_EXTD_DIR_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-file_id_extd_dir_information),
[IO_STATUS_BLOCK](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_io_status_block),
[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex),
[NtReadFile](https://learn.microsoft.com/en-us/windows/win32/devnotes/ntreadfile).
Páginas de driver descrevem modo kernel; o uso aqui é modo usuário (nomes
`Nt*`), distinção a manter na revisão.

Tipos: aliases explícitos de largura fixa (`c_int32` para `NTSTATUS`/`BOOL`,
`c_uint32` para `ULONG`/`ACCESS_MASK`/`DWORD`, `c_int64`/`c_uint64`,
`c_uint8` para `BOOLEAN`), sem supor a largura de `long` do hospedeiro;
ponteiro de 8 bytes e larguras conferidas por gates. No Windows esses aliases
são os próprios `c_long`/`c_ulong`/`c_longlong`, o que satisfaz os testes
de identidade de ponteiro existentes. Na tabela, `c_long`/`c_size_t` indicam
a largura ABI (32 com sinal / 64 sem sinal), não um requisito de nome.

Estruturas (`ctypes`, tipos LLP64 explícitos; `BOOLEAN` 1 byte, `BOOL` 4):

| Estrutura | Tamanho | Campos (offset) |
|---|---|---|
| `UNICODE_STRING` | 16 | `Length` 0, `MaximumLength` 2, `Buffer` 8 (`c_void_p`) |
| `OBJECT_ATTRIBUTES` | 48 | `Length` 0, `RootDirectory` 8 (`c_void_p`), `ObjectName` 16 (`POINTER(UNICODE_STRING)`), `Attributes` 24, `SecurityDescriptor` 32, `SecurityQualityOfService` 40 |
| `IO_STATUS_BLOCK` | 16 | união anônima `Status` (`c_long`)/`Pointer` 0, `Information` 8 (`c_size_t`) |
| `FILE_BASIC_INFO` (classe Win32 0) | 40 | `CreationTime` 0, `LastAccessTime` 8, `LastWriteTime` 16, `ChangeTime` 24, `FileAttributes` 32 |
| `FILE_STANDARD_INFO` (1) | 24 | `AllocationSize` 0, `EndOfFile` 8, `NumberOfLinks` 16, `DeletePending` 20, `Directory` 21 |
| `FILE_ATTRIBUTE_TAG_INFO` (9) | 8 | `FileAttributes` 0, `ReparseTag` 4 |
| `FILE_ID_INFO` (0x12) | 24 | `VolumeSerialNumber` 0, `FileId` 8 (16 bytes) |

Registros variáveis (bytes): `FILE_ID_EXTD_DIR_INFORMATION` (classe NT 60):
cabeçalho 88, atributos 56, `FileNameLength` 60, `ReparsePointTag` 68,
`FileId` 72, nome em 88. `FILE_STREAM_INFORMATION` (classe NT 22):
cabeçalho 24 (`NextEntryOffset`, `StreamNameLength`, tamanho, alocação),
nome em 24. `FILE_FS_ATTRIBUTE_INFORMATION` (classe de volume 5): cabeçalho
12, nome em 12. `FILE_FS_DEVICE_INFORMATION` (4): `DeviceType`,
`Characteristics` (8 bytes). As classes 0x13/0x14 são do enum Win32, não do
NT; a classe NT 59 é rotulada reservada, por isso a identidade usa a classe
Win32 pública `FileIdInfo` (0x12).

Protótipos (`PROTOTYPES`, conjunto fechado; `restype` `c_int32`):
`ntdll`: `NtCreateFile` (11 argumentos), `NtQueryInformationFile` (5),
`NtQueryVolumeInformationFile` (5), `NtQueryDirectoryFile` (11),
`NtReadFile` (9), `NtClose` (1); `kernel32`: `GetFileInformationByHandleEx`
(4). Nenhuma função de escrita, exclusão, renomeação, `Set*`, `DeviceIoControl`,
`FsControl`, cancelamento, espera, evento ou processo.

## 3. API `api` injetada (forma Python fixa da ABI)

- `create(cell, access, attributes, iosb, share, disposition, options)`:
  `NtCreateFile` com `AllocationSize` nulo, `FileAttributes` 0, sem EA.
- `query_info(raw, info_class, buffer, size)`: `GetFileInformationByHandleEx`
  (BOOL). Saída de tamanho fixo pelo contrato documentado; não se finge
  detectar escrita curta do kernel quando o retorno é verdadeiro.
- `query_file(raw, iosb, buffer, length, info_class)`: só classe 22.
- `query_volume(raw, iosb, buffer, length, fs_class)`: classes 4 e 5.
- `query_directory(raw, iosb, buffer, length, info_class, single, restart)`:
  classe 60, `single` falso, sem evento/APC/filtro de nome.
- `read(raw, iosb, buffer, length, offset)`: `offset` explícito (`c_longlong`).
- `close(raw)`: `NtClose`.

`cell` é `c_void_p`; `attributes`, `iosb` e estruturas fixas são instâncias;
buffers variáveis são `create_string_buffer`. `NTSTATUS` com sinal. Status
retornado não pendente é autoritativo; não se exige `IOSB.Status` igual.

## 4. Abertura

Âncora: nome absoluto único `\??\C:\` com `RootDirectory` nulo. Filhos: um
componente relativo (`RootDirectory` = handle bruto do pai), sem separador,
NUL, `:`, `.`, `..`, até 255 unidades UTF-16, `str` exato. `Attributes` 0
(documentação de modo usuário admite 0 ou `OBJ_CASE_INSENSITIVE`; não se
usa `OBJ_DONT_REPARSE`). `OBJECT_ATTRIBUTES.Length` 48. `FILE_OPEN` (1)
somente.

| Tipo | Acesso | Compartilhamento | Opções |
|---|---|---|---|
| diretório | `0x001000A1` (LIST, TRAVERSE, READ_ATTRIBUTES, SYNCHRONIZE) | `0x3` | `0x00200021` (DIRECTORY, SYNCHRONOUS_NONALERT, OPEN_REPARSE_POINT) |
| arquivo | `0x00100081` (READ_DATA, READ_ATTRIBUTES, SYNCHRONIZE) | `0x1` | `0x00200060` (NON_DIRECTORY, SYNCHRONOUS_NONALERT, OPEN_REPARSE_POINT) |

Sucesso exige `STATUS_SUCCESS`, `Information == FILE_OPENED` (1) e handle
bruto não nulo, diferente de `INVALID_HANDLE_VALUE`, não alias de outro
aberto. Perfil da âncora (pendente de medição real): sistema de arquivos
`NTFS`, disco local (`DeviceType` 7) não marcado como mídia removível e não
remoto. O bit `FILE_REMOVABLE_MEDIA` (0x1) significa mídia removível, não
dispositivo de hardware removível; sua ausência **não** atesta disco fixo ou
interno. `FILE_REMOTE_DEVICE` (0x10) também recusa. Fontes consultadas pelo
revisor:
[FileFsDeviceInformation (MS-FSCC)](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/616b66d5-b335-4e1c-8f87-b4a55e8d3e4a),
[FILE_FS_ATTRIBUTE_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_fs_attribute_information).
O buffer de atributos tem teto fixo escolhido; nome maior ou
`BUFFER_OVERFLOW` falha fechado (não suportado), sem alegar máximo universal
de nome de sistema de arquivos. Falha depois de publicar o handle ⇒ `OSError`
(o coletor adota e fecha). A combinação diretório + `FILE_OPEN_REPARSE_POINT`
é prospectiva, NOT_MEASURED. Compartilhamento negado não bloqueia mapeamentos
ou escritores preexistentes; sem instantâneo atômico global nem limite de
tempo de syscall; operador quiescente.

## 5. Custódia (corrigida após medição do root)

Correção: no plano anterior, um backend que retinha o registro bruto mas
deixava `Slot.value = None` e levantava controle fazia o coletor marcar
`EMPTY` e liberar o dono, com `_POISON` vazio. Contrato corrigido:

1. Validação (nome, tipo, pai aberto, `Slot` exato do coletor e vazio,
   backend não envenenado) antes de tudo; falha aqui não tem efeito e deixa
   o slot `None`.
2. Antes de qualquer efeito nativo, publicar no `Slot` o marcador distinto
   `UNKNOWN` (não `Handle`) e reter em `_retained` (lista de tuplas de
   objetos `ctypes`) célula de saída, IOSB, `OBJECT_ATTRIBUTES`,
   `UNICODE_STRING` e buffer do nome.
3. Só uma falha concluída e conhecida sem handle — status `int` de
   severidade erro (`0xC…`), célula ainda nula — limpa o marcador
   (`Slot.value = None`) e o registro retido.
4. Abertura completa e válida publica o `Handle` exato do coletor, alocado
   depois do efeito (o marcador cobre o intervalo), e só então o perfil da
   âncora é consultado.
5. Pendente, informativo/aviso, status não `int` ou fora de 32 bits, exceção
   ou controle da API, falha na alocação/publicação do DTO, célula nula ou
   `INVALID_HANDLE_VALUE` em sucesso, `Information != FILE_OPENED`, alias ou
   erro com célula não nula: marcador e registro ficam; o coletor congelado
   coloca em quarentena e retém backend, ledger e slots em `_POISON`.
6. Qualquer efeito incerto (acima; exceção ou controle de qualquer chamada;
   pendente ou NTSTATUS não `int` em chamada NT com IOSB) retém IOSB, todos os buffers,
   offset e célula, envenena o backend e recusa toda chamada nativa
   posterior; `close` passa a devolver `False` sem `NtClose`. Sem espera,
   cancelamento, evento novo ou API de processo. Falha concluída com status
   de erro ou saída malformada de chamada não pendente apenas levanta
   exceção, sem envenenar.
7. `close`: só handle conhecido e aberto, uma vez; `STATUS_SUCCESS` ⇒ `True`;
   outro status ⇒ incerto, `False`, envenena, sem nova tentativa; token
   desconhecido, fechado ou não `Handle` ⇒ `False` sem chamada; exceção ou
   controle durante `NtClose` ⇒ incerto, envenena e propaga.

Implementação: o estado incerto é derivado do próprio ledger — o backend
está bloqueado enquanto `_retained` não estiver vazio; não há flag atribuída
depois do efeito. Na abertura a ordem é marcador `UNKNOWN` no slot, registro
em `_retained`, chamada, classificação; o `Handle` é alocado, registrado e
publicado antes de o registro ser removido, então interrupção em qualquer
ponto deixa marcador ou registro. `GetFileInformationByHandleEx` é síncrona:
retorno (inclusive 0 ou não `int`) remove o registro; exceção ou controle o
deixa. `close` grava o ticket em `_retained`, depois remove o token de
`_open` e chama `NtClose`; só remove o ticket com `STATUS_SUCCESS` exato
(ordem corrigida na V7, seção 9). Teto de 64 handles abertos; buffers temporários
fixos (nome por abertura, 8/76 bytes de volume, 4096 de streams, 65536 de
página reutilizado por listagem, leitura do tamanho do pedido).

Prova nos testes: o fake guarda só endereços inteiros; a retenção é aferida
pelos endereços dos objetos vivos em `_retained`, e, pela política, por
`weakref` de um backend que só o coletor referencia.

Identidade do handle bruto do kernel (registro do backend) é separada da
alocação do DTO; o intervalo entre as duas fica coberto pelo marcador.

Exceções: toda recusa, validação, status, parser ou envenenamento do próprio
backend levanta `OSError`; só a classe sem suporte na primeira página de
listagem levanta `NotImplementedError`. Exceções injetadas pela `api` ou pelo
DTO (`Signal`, `MemoryError`, `OSError`) propagam como o objeto original, então
mensagens de exceções privadas **não** são todas saneadas. A fronteira fechada
é a política pública: `collect` devolve só tuplas fechadas, sem texto de
exceção (regressão com sentinela e `capsys`).

## 6. Parsers limitados

- Metadados fixos: classes Win32 0/1/9/0x12, retorno BOOL `int` não zero
  (0 ou não `int` ⇒ exceção, sem envenenar; a chamada é síncrona);
  `BOOLEAN` só 0/1; diretório de `FILE_STANDARD_INFO` igual ao bit 0x10 de
  `FILE_BASIC_INFO` e `FILE_ATTRIBUTE_TAG_INFO`; `EndOfFile` não negativo;
  reparse = bit 0x400.
- Streams (classe 22): buffer 4096; usado = `Information` ≤ buffer; registro
  com cabeçalho e nome dentro do usado; nome par, 2–128 bytes, UTF-16 estrito
  sem substitutos isolados; próximo 0 ou múltiplo de 8, além do fim do nome,
  dentro do usado; no máximo 8. Arquivo exige ao menos um registro completo.
  Diretório: semântica sem dados NOT_MEASURED; contrato estreito aceita só
  `SUCCESS` com `Information` 0 (streams vazios); qualquer outra coisa é
  erro, nunca normalizada para vazio. `BUFFER_OVERFLOW` é erro.
- Diretório (classe 60): página de 65536; primeira chamada de cada listagem
  com `restart` verdadeiro, depois falso; termina só em `NO_MORE_FILES` com
  `Information` 0; `SUCCESS` com 0 é falta de progresso; `BUFFER_OVERFLOW`,
  `NO_MORE_FILES` com dados e demais status são erro; sem crescer buffer nem
  fallback. Registros: cabeçalho 88 e nome dentro do registro e do usado,
  nome par 2–510 bytes, UTF-16 estrito, próximo múltiplo de 8 sem sobreposição;
  `.` e `..` no máximo uma vez cada e ignorados; nomes repetidos entre páginas
  são erro; limite de páginas `max_entries + 3` (páginas de um registro +
  pontos + terminal); `max_entries` `int` exato 0–16; mais entradas reais
  que o limite ⇒ exceção (o coletor mapeia `COLLECT_LISTING`). Status
  `STATUS_INVALID_INFO_CLASS`/`STATUS_NOT_SUPPORTED` só na primeira página ⇒
  `NotImplementedError` (prospectivo; não medido); depois, erro comum.
- Leitura: `limit` `int` exato 0–65537; pedidos ≤ 4096 com offset explícito
  crescente; aceita leituras curtas com progresso estritamente positivo;
  `END_OF_FILE` com `Information` 0 encerra; limite de voltas `limit + 1`;
  sem consumir bytes em erro.

## 7. Nomes fixados pelos testes

`backend()`, `_load_native()`, `_Win32Backend(api, dto)` (`dto` = mapeamento
com `Handle`, `Info`, `Entry`, `Slot` do coletor), `UNKNOWN`, `_retained`,
`API_OPERATIONS` (as sete operações da seção 3, nessa ordem), `PROTOTYPES`
(`nome → (dll, argtypes, restype)`) e as estruturas da seção 2 com os nomes
de campo documentados. Imports só `ctypes` e `struct`; carregadores de DLL
só dentro de `_load_native`.

## 8. Testes (primeira versão antes do módulo; regressões na seção 9)

Fakes de NT escrevem bytes sintéticos nos objetos `ctypes` recebidos, com
oráculos de layout independentes (`struct`). Cobrem: indisponível por
padrão e import sem DLL, pureza/AST, protótipos, layouts, argumentos exatos
de abertura, nomes validados antes de efeito, bundle sintético completo pela
cópia congelada da política (seam só no teste), leituras curtas e páginas
de um registro, perfil da âncora, metadados, streams e diretórios
malformados, paginação, leitura malformada e limites, faltante conhecido,
custódia antes/durante/depois da chamada e na alocação do DTO, saída
falhada não nula, alias, pendentes em cada operação, fechamento falho,
desconhecido, duplo e interrompido, ausência de vazamento e resultado público
fechado sobre mensagem injetada.

## 9. Achados de posse V6 (RED antes da correção)

O root mediu o módulo `fb453d57` (21742 bytes; 177/177 com os testes
`7b5c`) e uma revisão independente reproduziu dois achados. A fonte fica
intacta na rodada V6; 12 regressões foram acrescentadas ao fim do teste
(189 no total), medidas pelo root antes da correção conforme o registro abaixo.

- `FOREIGN_DTO_SAME_TOKEN` (10 casos): dois backends privados legítimos com
  as mesmas classes DTO da política, cada um com o primeiro `Handle.token`
  igual a 1. O backend B aceitava o handle de A e um `Handle(token)`
  reconstruído para `close`/`query`/`read`/`list_dir`/`open_child` (o `close`
  fechava o handle de B). Exigido: recusa antes de qualquer chamada do fake
  (`close` `False`, demais `OSError`, slot filho `None`), e o handle original
  de B continua utilizável e fechável. O valor do token sozinho não é custódia
  do objeto emitido. Não se alega fronteira hostil nem vulnerabilidade
  externa.
- `CLOSE_POP_BEFORE_RETAIN` (2 casos, `OSError` e `Signal`): uma interrupção
  em `record = (raw,)`, depois de `self._open.pop`, deixava o handle vivo no
  fake sem registro em `_open` nem em `_retained`. Pela política congelada
  isso dava `COLLECT_CLEANUP` com 31 criados, 30 fechados e 1 vivo. Exigido:
  todo raw vivo no fake aparece no ledger de posse do backend, sem `NtClose`
  nem nova tentativa sobre o alvo e com a coleta seguinte bloqueada. A linha é
  localizada pelo conteúdo, não pela ordem atual, e o trace é restaurado.

O root mediu RED com os testes `83c8f553` (68313 bytes): 189 coletados,
177 aprovados, 12 falhas sobre a fonte `fb453`.

Correção mínima aplicada na V7, antes da medição final do revisor:

- `_open` passa a mapear `token → (objeto Handle emitido, raw)`. Toda
  operação (`query`, `read`, `list_dir`, `open_child` como pai, `close`)
  exige `entry[0] is handle`, o objeto original exato; o valor do token ou a
  igualdade de classe não bastam. Recusa antes de qualquer chamada `api`
  (`close` → `False`, demais → `OSError`), sem afetar o handle original. A
  checagem de alias na abertura compara o raw dos registros de `_open`.
- `close`: o raw continua em `_open` até o ticket durável `(raw,)` entrar em
  `_retained`; só então o token sai de `_open` e `NtClose` é chamado. Antes
  do ticket o raw está em `_open`; depois, em `_retained` até
  `STATUS_SUCCESS` exato. Interrupção em qualquer ponto nunca deixa o raw só
  num frame local; com o ticket pendente o backend bloqueia tudo e não tenta
  de novo. A linha `record = (raw,)` foi mantida e agora roda com o raw ainda
  em posse.

Não há novo ciclo de vida, chamada nativa, carregamento ou ligação; ABI,
protótipos, operações fixas e tetos ficaram iguais.

## 10. Pendências

Medição real de suporte das classes, do perfil NTFS/disco local, de
`NtQueryInformationFile` em modo usuário (página não acessível ao revisor),
semântica de streams em diretórios e de diretório com
`FILE_OPEN_REPARSE_POINT`, status de classe sem suporte, `.`/`..`,
leitura com offset em handle síncrono, comportamento de `NtClose`; ligação
pinada ao coletor; pré-checagem e procedimento nativos. Gates de produção
abertos.
