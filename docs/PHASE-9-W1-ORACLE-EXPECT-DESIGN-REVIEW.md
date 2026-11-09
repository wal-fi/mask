# W1 Oracle — revisão do contrato EXPECT

2026-11-09, sob delegação, não aprovação individual. Base9e56df4.
CLI7447/6327 encerraram0 e foram recuperadas; zero escritor. Root leu
todas239linhas da v1 f9bd9c48/13450bytes e APIs públicas pertinentes.
Aceito só para testes puros/RED antes da fonte, com as precisões abaixo.

## Decisões e precisões do revisor

1. Local: docs/poc/oracle9_w1_expect.py, sem main/CLI; teste em
   tests/test_oracle9_w1_expect.py. Ambos ainda ausentes. Fonte nova também
   deve passar mypy strict3.11/3.14 explicitamente, além de lint/format;
   deploy não ganha cobertura mypy automaticamente neste repositório.
2. **Remover records de lab_init_packet.** A função recebe só ip,port,
   database,username,readonly_password,hmac_key,canaries e calcula
   expected_records internamente com essa mesma chave/canários. Evita
   misturar expectativas válidas de outra entrada. Quatro funções públicas
   permanecem; expected_records e result_body continuam acessores puros.
3. **Contrato imutável fechado:** ExpectRecord valida os seis campos e
   coerência entre job/kind/rows/bytes/sha/reason no construtor. Tipos exatos
   antes de igualdade/hash/regex; valores estrangeiros não ganham callbacks.
   Erros INPUT (entrada), MODEL (tabela/decisões divergentes), ENCODE (falha
   de compilação/masking/encoder), SIZE (limites), sem cadeia ou segredo,
   inclusive com handler do chamador ativo. Fixtures/modelo fechados não
   ganham API de injeção dinâmica só para cobrir ramo.
4. Política: literal local espelhado, sem alterar fonte pinada. Comparar no
   teste o mapping normalizado por DatasourcePolicy.from_mapping(...).
   to_mapping() com PURE['_lab_policy'](1).to_mapping(); só esse helper
   lógico estático conhecido do módulo pinado como oráculo de teste, nunca
   import privado de runtime/dados ou dependência operacional do gerador.
   Publicar o literal como POLICY_MAPPING no namespace do módulo para esse
   teste. Não declarar sandbox contra Python hostil/reflexão.
5. OID confirmado por leitura do adapter postgres.py:314–341, MASK→25 e
   demais decisões usam type_code validado na whitelist. Descriptors sem
   origem têm schema/table None e provenance DERIVED; DIRECT usa origem
   maskgw_lab.t. Job4 primeira coluna derivada0; job5 derivada0. Modelar
   job6 origem cpf conforme tabela, registrando hipótese nativa.
6. Vetores independentes já calculados pelo root SEM importar maskgw em
   oracle9-w1-expect-review-20261109/independent-vectors.json. SELECT1:
   60bytes/sha aa19842a612ea62536e94011790cd8c6a8b7e8c0d5c9bb1557daf2a5ecd99420.
   Job2:204bytes/sha169b93d9914e1987d390d8181efe154a02d0086bcc68a2a7ffa1f42f8bc704f0.
   Chave ASCII UTF8 de64chars, não hex-decoded. H(C0)=
   a9745149ad94f4460daff322d00912444b9e506bef7d63d1f2843399b3f5e695.
   Manual PG T/D/C conferido por montagem struct independente; modelo não
   foi executado. Job10:27+15*(1048576+11)+15=15728847bytes de corpo.
7. result_body devolve só bytes do corpo; expected_records calcula len/sha
   desse retorno, sem acessar frame local inexistente. Processar um job por
   vez; sem cache global de corpos/chaves/canários. Não alegar teto físico
   provado. records cabem sem13corpos simultâneos.
8. Seed: o novo teste fixa um literal completo e revisável com uma instrução
   por linha, begin/create schema/create domain/create table/insert/commit,
   um INSERT das3linhas na ordem9colunas da tabela, ASCII/LF/finalLF.
   Essa escolha de espaços é contrato do teste antes da fonte, não cópia da
   implementação futura. Nenhum papel/GRANT/senha/chave na saída.
9. Segredos no LAB_INIT são verificados por caminhos do JSON, não count
   bruto de substrings que pode colidir entre senha e chave válidas.
   Canários entram em raw_canaries e seed como planejado; nunca em corpos.
   Não ler ambiente real nem perfil/config/runtime. Guardas sem I/O usam
   seams locais/namespaces do módulo e fonte/AST; não patch global da stdlib,
   de sinais/streams reais ou algoritmos do SDK. RandomTransformer.transform
   pode ser spy/tripwire temporário para provar que não foi aplicado.
10. Incluir uma sanidade independente de encoder com17linhas×1MiB gerando
    EncodeFailure.LIMIT, sem chamar gerador ou PG. Demonstra preflight, não
    prova o job11 do PostgreSQL. Tabelas ERROR13/16/18 e ordens5/6/7 são
    hipóteses até prova nativa. Compartilhar engine/encoder mede consistência,
    não segurança independente ou fato do PG.

## Fronteira e próximo lote

T5 continua BLOCK_NATIVE para o laboratório completo; rejeitada a sugestão
anterior de dispensa implícita. Nenhum efeito físico ou diagnóstico limitado
autorizado por este documento. Ponte/fixture/frescor/readmissão, B1/B2/D090/
C1, TLS/ingressos/IDE/MCP/produção continuam abertos.

Próximo lote somente o novo teste pelo mesmo Claude2; fonte EXPECT ausente
até root ler todos os oráculos, medir e congelar RED. Fonte27/app124/estado16/
attempt consumido e os testes aceitos permanecem fixos. Mesma sessão/modelo/
medium, guardzero e terminal recuperado antes da próxima chamada.

## Revisão do primeiro teste EXPECT (antes de pytest)

CLI68256 encerrou0 e foi recuperada, zero escritor. Root leu1097linhas
86d852ab/40511bytes. Não executou pytest: o caso environment usava setenv/
delenv reais, em desacordo com a precisão9. Ruff limpo; format dois hunks;
mypy311/314 reprovaram __contains__(str) por override de Container(object).
Dados/snapshot preservados em expect-review-20261109/initial-test-*.

Antes do RED: mesmo Claude2 altera apenas esse teste:
- substituir setenv/delenv por spy no nome MappingSecretProvider do namespace
  do gerador, delegando à classe pública verdadeira, com chaves explícitas
  KEY/KEY2. Nada de ler/mutar ambiente global, módulos stdlib ou SDK;
- guard de retenção cobre recursivamente só containers builtin exatos
  dict/list/tuple/set/frozenset, com limite explícito de profundidade/nós,
  ciclos por identidade, nunca __dict__/getattr de objeto estrangeiro.
  Inspecionar globals próprios, excluindo metadados/imports/defs; detectar
  corpo grande e chave/canários em str/bytes/bytearray também aninhados.
  Sanidade independente sem gerador confirma detecção de cache aninhado.
  Declarar que não prova heap, closures ou zeroização;
- __contains__ recebe object (protocolo), delega a str só após refinar tipo,
  sem cast/ignore nem remover o contador; aplicar manualmente dois hunks
  de format (VECTORS_FILE e parametrize).
Restante dos oráculos preservado; fonte EXPECT ausente até revisão/RED.

## Oráculos EXPECT revistos e RED119 congelado

Root leu o teste inicial86d852ab/40511bytes/1097linhas e todo delta R1.
CLI90343 recuperada0; helper de retenção só containers builtin exatos com
limites/ciclos, sem heap/closures/zeroização. Spy local de MappingSecretProvider
substituiu setenv/delenv sem ler/mutar ambiente. CLI5610 recuperada0 mudou
só hostile:dict[str,object]; root confirmou igualdade byte a byte após essa
única inserção, preservando initializer/asserts/semântica.

Teste finalccb1f29f/45520bytes/1214linhas. RED119:6sanidades passam,113falhas
apenas FileNotFoundError do gerador,0erros/skips/xfail,9,842s; ausência não
prova comportamento. Ruff/format/mypy1teste3.11/3.14 limpos. Estáticos
reprovados anteriores preservados; runtimeWindows3.11.3, não runtime3.14.

Aceito só para nova fonte docs/poc/oracle9_w1_expect.py pelo mesmo Claude2;
teste/vetores/fonte27/app124/estado16/attempt fixos. Source ainda ausente
antes do próximo lote. Nenhuma prova nativa/SQL/Oracle/produção fechada.
