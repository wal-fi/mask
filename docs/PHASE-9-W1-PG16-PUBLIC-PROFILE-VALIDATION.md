# PG16 público — perfil e parser puros

2026-10-29, sob delegação. Desenho60182/P1 confirmado22157, núcleo de volumes
6e3827af aceito78090. Este incremento não tem chamador operacional, raiz,
DockerCLI, banco, shell executado ou seed. T4v2 consumida permanece intacta.

## Primeira versão — posteriormente recusada na revisão36874

`docs/poc/pg16_public_profile.py`, SHA-256
`78e815a583df0e44f5e8b8efc7b7e9222bf02720bc153924ef9daa0b7d66f919`.

- Readmissão candidata por IDcf78/Linux/amd64 e Config.Volumes/ExposedPorts
  fechados. ENV só chaves públicas/valores delimitados; desconhecido/duplicado
  recusa antes do Intent. Não é medição nova do inventário real da imagem.
- Intent imutável captura comando shell público, task, fonteSHA, labels,
  manifesto e ENV da imagem antes do create. Nenhuma fonte ou script privado
  no stdin. Comando de create medido≤26000chars, sem publish/bind/-i/envsenha.
- Perfil proposto UID70/RO512MiB/rede none/caps0/NNP/IPCprivado/core0/256pids,
  dois tmpfs exatos, stdinfalse, healthnone/lognone, sem restart/mountvolume/bind.
  ExposedPorts5432 herdado só metadata; publicação e rede continuam proibidas.
- Cleanup identity separada de aceitação: Id/nome/imagem/argv/entry/labels
  próprios continuam conferidos se ENV/limites/mounts/fonte viva mudarem.
- Fonte só usa versões, id/os-release e stat/tipos/modos, sem initdb/server/
  SQL. A presença das ferramentas será medida, não garantida. Integridade
  pelo host/Cmd antes de start, não por sha256sum que a fonte ainda medirá.
- Parser≤8192bytes/32linhas ASCII em ordem e chaves fechadas, versões só
  semver/PG16 coerente com a imagem admitida, UID70/tmpfs0700. Erros fechados,
  sem prefixo de saída aceito como sucesso. Parser não recebe output do DB.
- Publicação de raw de CID exige Env/labels/argv/ID/nome/imagem capturados,
  scan auth/proxy em todo JSON; profundidade64/nós65536, sem recursão própria.
  Retorna só decisão/categorias/hash/tamanho, não raw. Não é exportador de
  imagem nem filtro de resultados ou segredos. Logger/coordenador não existem.

## Medições e regressões

Windows nativo3.11.3:63 testes novos +33volumes, **96passed em0,79s**.
Só fixtures sintéticas em memória, sem Bash/BusyBox/PG/Docker real. Fonte shell
não foi executada; sem certificação de seus comandos/flags ou tempos reais.
Ruff src/tests limpo; format320 conforme; mypy strict311/314 em318arquivos
limpos, runtime somente3113. Helper com lint restrito, não mypy strict.

Regressões antes dos fixes: fixture com ExposedPorts herdado5432 falhouCONFIG;
perfil corrigido para aceitar a declaração fechada sem permitir bind/rede.
JSON de600níveis estourou recursão no scanner; teste falhou antes do walker
iterativo limitado e passa depois. Não houve nova execução de fonte consumida.
Renomeação de canário no teste deixou3referências inválidas, detectadas por
Ruff/mypy e corrigidas antes do gate final; não se registra aquela rodada
como aprovada. Nenhuma adaptação de produto ou teste escondendo falha.

## Limites

Código em revisão somente leitura pelo Claude2. Integração CLI fake (volumes
do create, rm falhando/named remanescente/HELD), readmissão real da imagem,
orçamento/supervisor/estado/comando novos e exportador próprio ainda faltam.
Não reusar os mains/loggers públicos com segredo. Shell reader exato precisa
de outro lote público medido antes do fixture privado/TLS/worker/consultas.
Sem dependência/instalação/commit/push/job/outro writer ou banco existente.
Gateway indisponível, B1/B2/D090/C1/SQL/produção continuam abertos.

## Delta B1/B2 após revisão36874

Primeira versão78e815a5 recusada por ordem de ulimits presumida e lista de
ENV completa não medida. Dois testes novos falharam primeiro (PROFILE na
ordem invertida, IMAGE_ENV no metadado público de build). Corrigidos:
mapa Name→(Soft,Hard)+len2/chaves/tipos exatos recusa duplicata/bool/campoextra;
ENV opção(b) do revisor, nomes uppercase limitados/sem palavras sensíveis e
valores públicos limitados, obrigatórios PATH/PG_MAJOR/PG_VERSION/PGDATA.
Demais variáveis públicas de build são capturadas imutáveis; ambiente do CID
e S1 continuam exigindo igualdade exata com o capturado da imagem. Não é DLP.

Fonte atual `c1ac6428dbc5df4cff975996e17d5c3dd9cefbad85f37ef6c04d8a6671787280`.
75perfil+33volumes: **108passed em0,90s**, Ruff src/tests e mypy strict311/314
em318arquivos limpos, runtime só3113. Sem novos efeitos nativos. Precisão de
rawantesvalidação e categorias fechadas para labels consta no desenho futuro.
Delta em rerevisão; não declara perfil/image/BusyBox efetivamente medidos.

## Precisão TAB e comando exato antes de A

Revisão17859 confirmou B1/B2 e pediu aceitar TAB só no valor de variável
opcional de build. Teste falhouIMAGE_ENV antes do fix. Agora TAB é preservado,
sem normalizar; LF/CR/NUL/nome comTAB/campo obrigatório comTAB recusados. CID
e S1 ainda exigem os mesmos bytes. Não afirma que o Env real da cf78 foi lido.

`blueprint(task)` calcula argv/medição exatos sem imagem nem I/O; não admite
imagem ou autoriza create. CLI manda só os três labels próprios; labels da
imagem não são reenviados nem afetam o tamanho do comando. Intent e validação
continuam capturando/verificando labels herdados da imagem admitida. Criar
exige no futuro igualdade create_args(intent_real)==blueprint da proposta.
Sem imagem falsa, pré-inspect extra ou comando dependente de dados desconhecidos.

Fonte atual `fe2f8ba8bfabc5572fe7aeb85c31c54de38ceaa23c1a6c34dd631425371d9277`.
87perfil+33volumes: **120passed em0,91s**, Ruff/mypy311/314 em318arquivos limpos,
runtime só3113. Nenhum novo efeito nativo. Delta em revisão; histórico de
medidas anteriores preservado, sem chamar perfil/template como fato do Docker.

Revisão6796: perfilfe2f8ba8 aceito isoladamente; direção do host aceita para
owner/fakes com P1–P4 incorporados no desenho antes do código. Sem medição
real nova da imagem/ENV/labels/BusyBox ou autorização de release.
