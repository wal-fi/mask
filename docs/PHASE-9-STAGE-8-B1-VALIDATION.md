# Fase 9 — Etapa 8 — núcleo B-1: snapshot e equivalência local

**Estado (2026-10-19): núcleo implementado e validado localmente no runtime
3.11.3; revisão técnica concluída e lote aprovado explicitamente pelo usuário.
Sem commit/push. Não fecha B-1 fim a fim, B-2 ou D-090 gate 2.**

## 1. Autorização e checkpoint

Depois da aprovação do desenho em 2026-10-18, o usuário autorizou em
2026-10-19 somente snapshot e testes de equivalência do masking, com revisão
pelo Claude2, sem worker integrado, SQL de cliente, commit ou push.
Decisão: [D-111](DECISIONS.md).

Checkpoint: `master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`,
referência local `origin/master` em
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind. Nenhum fetch
foi feito. A árvore já continha alterações da tipagem e documentação da etapa
anterior, o desenho aprovado e arquivos pessoais não rastreados; foram
preservados. As mudanças deste lote foram conferidas contra o freeze tomado
antes da implementação, não contra uma árvore supostamente limpa.

## 2. Entrega estritamente interna

- `src/maskgw/runtime/snapshot.py`: template destacado e imutável, captura
  dos segredos usados na mesma compilação, vínculo explícito de identidade,
  parser fechado/canônico e recompilação pelo loader/engine existentes.
- `src/maskgw/runtime/candidate.py`: opção interna
  `capture_snapshot=False` e campo opcional no `PreparedRuntime`. Somente a
  opção explícita `True` captura; nenhum chamador operacional a habilita.
- `tests/test_runtime_snapshot.py`: **201 casos** sem banco real.
- Documentos de estado, desenho e D-111: autorização, implementação parcial
  e pendências, sem antecipar aceite do isolamento ou de SQL.

JSON v1 é formato **privado de entradas**, não RFC 8785 nem codec de
resultados. Usa ASCII com escapes, ordenação de chaves, separadores sem
espaços, recusa de valores não finitos, duplicatas e formas não canônicas.
O envelope tem teto de 64 KiB, o template reserva 512 bytes para identidade
e há guarda de profundidade 32 antes do parser. Isso não é garantia de
memória agregada; B-2 continua separado.

O recorder só admite `MASKGW_HMAC_KEY`, cacheia a primeira leitura por nome
e preserva exatamente o valor devolvido pelo provider original. A recompilação
nunca relê ambiente: usa provider fechado e exige igualdade de nomes
fornecidos/consumidos. A chave-mestra do catálogo não é capturada.

Os bytes carregam senha upstream e HMAC; somente extrações explícitas para
código confiável os devolvem. Objetos e erros são redigidos. A identidade
esperada é conferida com inteiros estritos; isso **não autentica** remetente,
payload ou processo. Não há nonce, tag, pipe, subprocesso ou handshake.

## 3. Provas unitárias medidas

Windows nativo, CPython **3.11.3** existente; `.venv` não recriada nem
modificada por instalação. Todos os valores, chaves e destinos são sintéticos.

| Grupo | Evidência |
|---|---|
| Determinísticos | 135 combinações: nove configurações de transformers × 15 valores/tipos, com igualdade de decisão, tipo, valor e bytes UTF-8 quando string. Inclui hashes, HMAC, fixed, truncate e regex com fallback. |
| Matching | Exceptions pelo nome autoritativo, aliases, prioridade de derivados, default ALLOW, ordem, case sensitivity, modos e aridade. |
| AST real | Quatro SELECTs analisados sem executar SQL, com os mesmos índices de regra e resultado de masking após recompilação. |
| Random | Cinco configurações: parâmetros e invariantes de alfabeto/comprimento, NULL, e comparação com entropia controlada só no contexto de teste, restaurada ao sair. Sem seed/hook de produto. |
| Identidade/configuração | Limites efetivos mais restritivos, política SQL, conninfo com `hostaddr` fixado, IDs/revision administrativos distintos da identidade de geração e bytes canônicos estáveis. |
| Rotação/mutabilidade | Uma leitura HMAC por compilação; reconstrução antiga usa a chave capturada após mudança do ambiente e criação de outro candidato. Mutar o `file_config` não altera o template. |
| Recusa/sigilo | Campos e segredos desconhecidos/ausentes/não usados, identidade bool/float ou divergente, duplicatas, tamanho/profundidade, texto inválido, truncamento e representação alternativa. Erros fixos sem causa/contexto original, representações redigidas e JSON genérico recusado. |
| Compatibilidade default | Candidato operacional sem captura aceita política maior que o novo teto; a captura explícita recusa, sem reduzir silenciosamente a proteção nem cair para o ambiente. |
| Falha simulada | Provider lança erro com canário; exceções de recurso simuladas durante recompilação recebem categoria interna fixa, sem cadeia. Não é teste de pressão real de memória. |

Rodada focada final: **201 passed, zero falhas/erros/skips**, 0,55 s.
Comando: `.venv\Scripts\python.exe -I -B -m pytest -o addopts=--strict-markers
-q -p no:cacheprovider --tb=short tests/test_runtime_snapshot.py`.

## 4. Regressão e gates

- Ruff check `src tests`: aprovado; format check: **227 arquivos conformes**.
- Mypy strict `src tests`: aprovado nos alvos **3.11 e 3.14**,
  **227 arquivos** cada, executado pelo interpretador 3.11.3. Não é medição
  de execução no CPython 3.14.
- Regressão Python integral: **5.530 coletados, 4.930 aprovados, zero falhas,
  zero erros e 600 skips**, sem deselect/xfail. Exit 0, 532,41 s no resumo
  pytest; XML registra 531,826 s no escopo da suíte. Pilha temporária de
  64 MiB, `-I -B`, sem cache do pytest e `MASKGW_TEST_DSN` removido somente
  do ambiente do processo, sem mudar as configurações do usuário.
  - **583 skips por DSN ausente** (580 com uma mensagem e três com outra);
  - **17 de plataforma:** nove bits de modo POSIX, seis symlinks
    indisponíveis e dois `fsync` de diretório POSIX;
  - um warning já existente sobre `pytest.raises(match="")` em teste
    administrativo; não foi alterado nem tratado como finding corrigido.
- PostgreSQL real: **não executado neste lote**; nenhum banco do usuário
  consultado. Docker não foi iniciado. Testes que dependem de DSN não são
  apresentados como integração aprovada quando pulados.
- Frontend/browser: não repetidos; não houve mudança em UI, contratos
  públicos, recursos gerados ou dependências.
- `git diff --check`, UTF-8 e whitespace dos arquivos novos: aprovados.

Rodadas intermediárias tiveram falhas de tipagem e de harness dos testes
novos, corrigidas sem skip/xfail: IDs explícitos para payloads grandes e um
`NameError` ao reorganizar um teste. Uma seleção inicial abortou antes de
rodar por nome de arquivo incorreto. Essas rodadas não são gates aprovados;
os números acima são da repetição final sobre os arquivos corrigidos.

## 5. Pacotes — verificação limitada, não o gate instalado completo

Wheel e sdist foram construídos de cópia dos fontes fora do checkout,
com o `build` existente e `--no-isolation`, sem instalar dependências.
`snapshot.py` e `candidate.py` têm bytes idênticos aos fontes nos dois
arquivos. O módulo foi importado diretamente do wheel por processo isolado
`-I -B`, e todos os módulos `maskgw.*` carregados vieram do wheel, sem
fallback para fonte do checkout.

**Limitação explícita:** as dependências da `.venv` existente foram
reutilizadas; não foi repetido o gate completo de instalações independentes
de wheel/sdist, aplicação ou browsers fora do checkout.

SHA-256:

- wheel: `8967c7142c89c1ed9749c5e3825c829337c83e33e67ba9197cdb350a57f1fca7`;
- sdist: `86fdeb5919287674be77ea485a7343f6f18aa178cfbb14907c3e20aad68fb032`.

Evidência local temporária:
`%LOCALAPPDATA%\Temp\maskgw-b1-validation-6ad306c78cb3420d879937b6988e596e\`.
Contém runner, XML da regressão e pacotes. Caminho temporário não é artefato
embarcado nem substituto de reprodução dos testes do repositório.
SHA-256 de `pytest-full.xml`:
`be79898032ad1ddd981dd5b68252a9999ef2b20a497ea6004651039a2be1c9bb`.

Fontes funcionais medidos (SHA-256):

- `runtime/snapshot.py`: `75b43e79a23fee01492fd86a881930e3807d5e98b9b754a4ddaf9971d98aa7b2`;
- `runtime/candidate.py`: `09a0ff4df176a4cd74aef622c5463187125d23e589d5651fe4107ae30c404186`;
- `tests/test_runtime_snapshot.py`: `fb38c35c2d0ceecca80a1c9ebe7e9c0a1aa249f26e8adf21785b28185f541bca`.

## 6. Revisão, limites e próximo gate

Claude2 fez revisão somente leitura do desenho de implementação e do código,
sem editar ou executar comandos. Nenhum bloqueador foi apontado no escopo
restrito; comentários sobre sigilo, conjuntos de leituras, imutabilidade,
random e categorias foram conferidos pelo implementador. A conclusão não é
aprovação do usuário nem prova de isolamento. A revisão final de código e
documentação também não apontou bloqueador. Ela ocorreu enquanto a regressão
integral terminava; só depois o implementador registrou os números reais
acima, conferidos no XML. As últimas alterações foram exclusivamente
documentais; os três hashes funcionais continuaram iguais aos medidos.

B-1 **fim a fim permanece aberto**: a identidade foi fornecida explicitamente
pelo teste, não capturada no ingresso de uma lease real; não há worker,
ambiente de filho, transporte, handshake ou equivalência em outro processo.
CPython 3.14 e POSIX não foram executados neste lote.

B-2 e D-090 gate 2 continuam abertos. Não há mudança de cursor, contenção de
memória do pai, admissão de workers, lifecycle de processos ou codec de
resultado. A falha agregada de memória anterior continua reprovada, sem
reclassificação. Nenhum SQL de cliente foi liberado; PGWire segue em `0A000`.
Sem integração em bootstrap/registry/lease, novas dependências/settings,
Admin/UI, MCP multi-datasource, commit, push, deploy ou produção.

## 7. Aprovação do lote

Em 2026-10-19, depois do relatório dos resultados e limites acima, o usuário
respondeu **"aprovado"**. A aprovação abrange o núcleo B-1 entregue e a
D-111, não o fechamento de B-1 fim a fim, B-2 ou D-090 gate 2. Não autoriza
worker, integração, SQL de cliente, commit, push ou produção.

O registro dessa aprovação alterou somente documentos. Os resultados e
limitações medidos foram preservados, e os três hashes funcionais da §5
continuaram iguais. As suítes não foram repetidas para esse ajuste editorial.

## 8. Incremento posterior autorizado: prova em outro processo

Em 2026-10-19, depois dessa aprovação, o usuário autorizou separadamente a
prova de equivalência em processo isolado, sem SQL de cliente ou integração
operacional, localmente, com revisão pelo Claude2 e sem commit/push. Há
somente dois arquivos novos de testes e atualizações de documentos; o núcleo
de produto e os hashes da §5 não mudaram. A evidência própria está em
`PHASE-9-STAGE-8-B1-PROCESS-VALIDATION.md`.

Esse incremento posterior foi aprovado explicitamente pelo usuário em
2026-10-19, sem ampliar a autorização nem autorizar commit/push.

As medições e exclusões das seções anteriores descrevem o lote original.
A prova posterior não fecha B-1 fim a fim, B-2 ou D-090 gate 2, não entrega
transporte operacional/handshake e não autoriza worker ou SQL.
