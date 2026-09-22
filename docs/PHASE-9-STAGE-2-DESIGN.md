# Fase 9 — desenho fechado da Etapa 2

**Data:** 2026-09-22
**Estado:** barreira de projeto fechada antes do código; implementação autorizada somente dentro deste contrato.

Este documento fecha as escolhas de implementação exigidas por D-069 sem
reabrir ou reduzir D-065–D-076. A Etapa 2 não cria registry, Admin API v2, UI
v2, listener PGWire ou mudança no MCP.

## 1. Biblioteca e dependência

Será usada `cryptography==50.0.1`, com `cryptography.hazmat.primitives.ciphers.aead.AESGCM`,
`HMAC` e `HKDF` da própria biblioteca. A dependência é pinada exatamente no
projeto e nos artefatos; não há criptografia própria, fallback de algoritmo ou
chave derivada de senha humana.

- segredo upstream: AES-256-GCM;
- autenticação do payload do catálogo: HMAC-SHA-256 com subchave HKDF distinta;
- nonce: 12 bytes de CSPRNG por cifragem;
- chave-mestra: exatamente 32 bytes, recebidos como 64 dígitos hexadecimais
  ASCII por `MASKGW_DATASOURCE_MASTER_KEY`/`SecretProvider`;
- erro de chave, tag, formato ou AAD: falha fechada sem detalhe criptográfico.

## 2. Representação canônica

O payload autenticado é um objeto JSON UTF-8 sem BOM, com `sort_keys=True`,
separators `(',', ':')`, `ensure_ascii=False` e sem espaços. O conjunto de
chaves é fechado, números são inteiros dentro dos limites dos modelos, e listas
de datasources são ordenadas pelo ID opaco. O payload autenticado exclui apenas
o campo `auth`, que contém o algoritmo e a tag HMAC; todos os demais campos,
inclusive alias, destino, política, revisions e ciphertext, entram no HMAC.

O digest SHA-256 usado pela âncora é calculado sobre esses bytes canônicos. O
digest não é segredo e nunca substitui o HMAC.

## 3. Envelope versionado

O arquivo `datasources.store` tem exatamente estas chaves de topo:

```json
{"auth":{"algorithm":"HMAC-SHA256","tag":"<hex>"},"catalog_revision":1,"datasources":[],"format":1,"schema_version":1}
```

Cada datasource tem schema fechado e inclui `id`, `alias`, `display_name`,
`enabled`, `host`, `port`, `database`, `username`, `tls`, `policy`, `limits`,
`resolved_addresses`, `revision`, `last_test` e `upstream_secret`. O campo
`upstream_secret` tem `algorithm=AES-256-GCM`, `version=1`, `nonce` base64url e
`ciphertext` base64url; o tag GCM está no ciphertext retornado pela biblioteca.

AAD é o JSON canônico de `{datasource_id, field, schema_version, revision}`.
O `field` é exatamente `upstream_secret`. O plaintext nunca é serializado,
retornado por snapshot, incluído em `repr`, erro, log, auditoria ou resposta.

## 4. Âncora monotônica e trust boundary

O store substituível e a âncora não compartilham o diretório. A âncora fica em
um diretório separado, operador-gerenciado, privado e não symlinkado; no
default, `config/.maskgw-anchor/datasources.anchor`, enquanto o store fica em
`config/datasources.store`. Pode ser configurada explicitamente por
`MASKGW_DATASOURCE_ANCHOR` para um diretório protegido por proprietário/ACL
distinto do diretório do store.

O processo exige diretório da âncora privado (`0700`) e arquivo/lock privados
(`0600`) no POSIX, arquivos regulares não symlinkados e pais estáveis. No
Windows a implementação exige regularidade, não-symlink e criação exclusiva;
ACLs são responsabilidade do diretório operador-gerenciado e a documentação
não trata bits POSIX como prova de ACL.

A âncora contém somente `format`, `catalog_revision` e `catalog_digest`. Ela é
um contador monotônico confiável sob esse trust boundary, não um arquivo comum
ao lado do catálogo. Um atacante que consiga substituir também o diretório da
âncora está fora da garantia desta etapa; nesse caso não existe detector local
de replay integral sem um serviço/TPM externo, e o deployment deve falhar na
validação de confiança.

## 5. Protocolo de commit e recuperação

Cada instância serializa, pelo lock de lifecycle, as leituras de estado, a
checagem de revision e cada transação de persistência como uma única operação.
`close()` aguarda a operação em andamento antes de liberar os sidecars; chamadas
que obtenham o lock depois do fechamento falham. Os locks sidecar são adquiridos
em ordem determinística: store primeiro, âncora depois. Locks não são removidos
no close; o descritor é liberado e o arquivo continua regular e privado.

Uma escrita segue este protocolo:

1. validar o par store/âncora e capturar `(old_revision, old_digest)`;
2. construir e autenticar o payload novo com `new_revision=old+1`;
3. gravar journal autenticado na âncora com old/new revision e digest, fsync do
   arquivo e do diretório;
4. criar backup cifrado do store anterior com `O_EXCL`, fsync e modo privado;
5. gravar o store temporário, fsync, `replace` no mesmo diretório e fsync do
   diretório quando suportado;
6. gravar a âncora nova, fsync, `replace` no diretório protegido e fsync;
7. somente numa rotação de master key, depois do ponto de commit (§6.1):
   remover todos os backups gerenciados, fsync do diretório no POSIX e nova
   varredura confirmando que nenhum restou;
8. remover o journal e limpar somente temporários/backups gerenciados antigos,
   sem tocar em symlinks ou nomes desconhecidos.

"Backup gerenciado" é exclusivamente um arquivo regular cujo nome casa com
`datasources.store.bak.<revision>`, com revision decimal sem zero à esquerda.
Symlinks, diretórios e nomes parecidos (`.bak.01`, `.bak.2.orig`) nunca são
tocados. Escritas que não trocam a chave mantêm a retenção dos três backups
mais recentes.

Na abertura, um journal pendente é recuperado somente se os estados forem
coerentes: old/old descarta a intenção; new/old conclui a âncora; new/new limpa
o journal. Há uma exceção delimitada para a inicialização vazia: somente
`old_revision=0`, store exatamente em `new` e âncora ausente permite criar a
âncora nova. Qualquer outra combinação incompleta falha fechada. Ausência,
truncamento, conteúdo não UTF-8, revision regressiva, digest divergente ou
journal inválido não recebe autocorreção.

A recuperação é decidida inteiramente antes de qualquer escrita: o journal é
autenticado pela chave fornecida, o store é autenticado por HMAC com essa mesma
chave (não existe leitura não autenticada do store em nenhum caminho) e a âncora
precisa coincidir com um dos estados `(revision, digest)` do journal. Só depois
dessa reconciliação a âncora pode avançar e o journal pode ser removido. Uma
tentativa de abertura que terminaria em erro de chave nunca consome o journal,
nunca avança a âncora e nunca executa a limpeza seletiva. A âncora não carrega
tag própria (D-080): ela é validada por igualdade com o estado que o journal e o
store autenticados comprometem.

Falhas antes da tentativa de replace do store preservam o par antigo e mantêm a
categoria `CatalogWriteError`. A partir da tentativa de replace do store o
resultado é **incerto**: o store pode já estar no estado novo, e a falha pode
ter ocorrido depois da âncora ou da remoção do journal. Toda falha a partir
desse ponto vira `CatalogOutcomeUncertainError` (subclasse de
`CatalogWriteError`), com texto fixo e sem `__cause__`/`__context__`. O
chamador não pode inferir o estado pelo erro. O objeto que sofreu a falha fica
bloqueado até ser fechado e reaberto, impedindo novas mutações com memória
potencialmente divergente do disco. A âncora só avança depois da durabilidade
do store; o journal só é removido depois da durabilidade da âncora, e sua
remoção é estrita (falha de `unlink`/`fsync` do diretório é erro, não é
silenciosa).

Para escritas com a mesma chave, reabrir com essa chave conclui a recuperação
acima. Rotação de master key tem o contrato explícito da §6.

## 6. Rotação de master key

Rotação é explícita e executada enquanto o catálogo ainda está aberto com a
chave antiga: descriptografa cada segredo somente em memória, cifra novamente
com a nova chave e nonce, incrementa a revision e usa o mesmo journal. O journal
de rotação carrega duas tags: a do papel antigo, calculada com a chave antiga, e
a do papel novo, calculada com a chave nova. A chave externa só deve ser trocada
no ambiente depois do retorno bem-sucedido da operação. Não há fallback
silencioso, rollback automático do store nem aceitação de duas chaves depois da
determinação.

### 6.1. Ponto de commit e resultado incerto

O ponto de commit da rotação é a âncora nova durável. Até ele, os backups
gerenciados são preservados: se a rotação não se confirmar, eles continuam
cifrados com a chave que segue válida. Depois dele, todo backup gerenciado é
anterior à rotação e está cifrado com uma chave anterior; por isso é removido,
com verificação, antes do journal. Enquanto o journal existir, a limpeza é
parte da conclusão da rotação; o journal só desaparece depois que nenhum
backup gerenciado resta. Estados possíveis depois de uma interrupção:

| limite da interrupção | store / âncora | backups da chave anterior | journal | erro devolvido | chave confirmada |
|---|---|---|---|---|---|
| antes do replace do store | old / old | preservados | sim | `CatalogWriteError` | antiga |
| após replace/fsync do store | new / old | preservados | sim | `CatalogOutcomeUncertainError` | nova |
| após replace/fsync da âncora | new / new | preservados | sim | `CatalogOutcomeUncertainError` | nova |
| durante a remoção dos backups (falha ou interrupção) | new / new | parcialmente removidos | sim | `CatalogOutcomeUncertainError` | nova |
| após a remoção verificada dos backups | new / new | nenhum | sim | `CatalogOutcomeUncertainError` | nova |
| após limpeza do journal | new / new | nenhum | não | `CatalogOutcomeUncertainError` | nova |

A remoção conta como falha quando uma remoção levanta erro, quando o `fsync` do
diretório falha ou quando a varredura final ainda encontra um backup gerenciado
(inclusive se a remoção retornou sem efeito).

Um erro depois do replace **não significa que a rotação falhou**. Ele significa
que o chamador não sabe qual chave vale.

### 6.2. Abertura com uma única chave

`CatalogStore.open` só conclui um journal de rotação quando o resultado já não
é incerto e a chave autentica o estado do store:

- old/old aberto com a chave antiga: o store nunca foi substituído; a intenção é
  descartada e nenhum byte do store é restaurado (não é rollback);
- new/new aberto com a chave nova: a âncora já confirmou o commit; restam a
  remoção verificada dos backups da chave anterior e a do journal, nessa ordem.
  Se a remoção dos backups falhar, a abertura falha e o journal permanece.

Qualquer outra combinação — new/old com qualquer chave, ou uma chave que não
autentica o store — falha com `CatalogRotationPendingError` sem nenhuma
escrita. Chave que não autentica nenhum papel do journal falha com
`CatalogKeyError`, também sem escrita. Sem journal, a chave que não autentica o
store falha com `CatalogKeyError` como em qualquer abertura.

### 6.3. Determinação e recuperação explícitas

- `CatalogStore.inspect_master_key_rotation(store, anchor_path=..., old_master_key=..., new_master_key=...)`
  é somente leitura e devolve `MasterKeyRotationStatus(confirmed_key, catalog_revision, journal_pending)`.
- `CatalogStore.recover_master_key_rotation(...)` faz a mesma determinação e só
  então aplica a conclusão já fixada pelos arquivos: descarta a intenção
  (old/old, com os backups preservados, porque continuam cifrados com a chave
  válida) ou, quando a chave nova é a confirmada, avança a âncora se preciso,
  remove com verificação os backups da chave anterior e só então remove o
  journal.

Ambas exigem as duas chaves, distintas e no formato canônico, e adquirem os locks
sidecar (store e depois âncora); portanto falham fechadas enquanto outra
instância mantém o catálogo aberto. O journal só é aceito se a chave antiga
autenticar o papel antigo **e** a nova autenticar o papel novo; o store precisa
ser autenticado pela chave do estado que representa; a âncora precisa coincidir
com o estado antigo ou o novo do journal; store antigo com âncora nova é
regressão e falha fechada; todos os segredos precisam abrir, em memória, com a
chave confirmada. Chaves trocadas, iguais, malformadas ou erradas falham sem
escrita. Repetir a recuperação devolve o mesmo resultado sem alterar arquivos;
uma recuperação interrompida pode ser repetida e converge ao mesmo estado. Sem
journal, a determinação indica qual das duas chaves autentica o par coerente.
O status não contém chave, segredo, ciphertext, nonce, digest ou destino.

### 6.4. Procedimento operacional

1. Guarde a chave nova fora do ambiente antes de chamar `rotate_master_key`.
   Não troque `MASKGW_DATASOURCE_MASTER_KEY` ainda.
2. Se a chamada retornar com sucesso, troque a variável para a chave nova. O
   sucesso só é devolvido depois que os backups gerenciados cifrados com a
   chave antiga foram removidos do diretório do catálogo e o journal foi
   limpo; a chave antiga deixa de abrir qualquer arquivo gerenciado ali.
3. Se a chamada falhar com `CatalogWriteError` que não seja
   `CatalogOutcomeUncertainError`, o par antigo foi preservado e a chave antiga
   continua sendo a configurada. Reabrir com ela descarta a intenção.
4. Se a chamada falhar com `CatalogOutcomeUncertainError`, ou se o processo
   terminar durante a rotação, o resultado é incerto: **preserve as duas
   chaves**, não troque a variável e não descarte nenhuma delas. Feche a
   instância bloqueada.
5. Execute `inspect_master_key_rotation` com as duas chaves para saber qual foi
   confirmada, e `recover_master_key_rotation` para concluir. Repita se for
   interrompido; o resultado é o mesmo.
6. Configure somente a chave indicada em `confirmed_key` e abra o catálogo
   normalmente. Descarte a outra chave apenas depois dessa abertura
   bem-sucedida.
7. `CatalogRotationPendingError` numa abertura significa que o passo 5 ainda não
   foi executado. `CatalogKeyError` na recuperação significa que o par de chaves
   fornecido não é o da rotação interrompida: não tente chaves alternativas no
   ambiente de produção nem apague journal, âncora ou backups à mão — a
   remoção dos backups da chave anterior é feita pela própria conclusão.
8. **Suspeita de comprometimento da chave-mestra exige também trocar as
   credenciais upstream.** Rotacionar a chave-mestra muda a chave que protege
   as senhas, não as senhas. Remover os backups locais não revoga cópias já
   obtidas por terceiros: um atacante que tenha a chave antiga e tenha lido o
   store, um backup, um snapshot do disco ou um backup externo do host (fora do
   alcance deste protocolo) continua capaz de decifrar a senha que estava ali.
   Nesse caso, troque a senha de cada usuário técnico no PostgreSQL de destino
   e grave a nova com `rotate_secret` em cada datasource, depois da rotação da
   chave. Só então as cópias antigas deixam de ter valor.

## 7. Destino e SSRF

O destino é armazenado como host/porta/database/usuário separados, nunca DSN.
Host não aceita URL, barra, controle, credencial ou porta embutida. A resolução
captura todas as respostas ordenadas e recusa loopback, unspecified, link-local,
multicast, IPv4-mapped IPv6 perigoso e endpoints de metadata cloud. IPs privados
são permitidos; endereços globais exigem allowlist exata no modelo.

Na criação/migração, `resolved_addresses` é gravado. Antes de qualquer uso
futuro, a resolução deve produzir exatamente o mesmo conjunto; mudança,
resposta vazia ou resposta múltipla divergente falha fechadamente. Não há
cache DNS permissivo nem re-resolução sem comparação.

## 8. Estados de ausência e migração

- feature desligada: nenhum store, âncora ou chave é carregado; o modo legado
  permanece byte a byte;
- inicialização explícita: cria par vazio somente quando solicitada pela API
  interna da Etapa 2;
- store sem âncora, âncora sem store, chave ausente/incorreta ou qualquer
  corrupção: falha fechada, exceto pela recuperação delimitada do journal de
  inicialização descrita na §5;
- migração legada: operação interna explícita, lê `MASKGW_DATABASE_DSN` apenas
  em memória, separa seus campos, cifra a senha e cria um datasource; nunca
  apaga, reescreve ou altera `masking.yaml` e nunca ativa registry/runtime;
- não existe fallback automático do catálogo para o DSN legado.

## 9. Decisões novas

As decisões D-077–D-086 em `docs/DECISIONS.md` registram este desenho e sua
rastreabilidade. A evidência executável será criada em
`docs/PHASE-9-STAGE-2-VALIDATION.md` depois dos testes e gates da implementação.
