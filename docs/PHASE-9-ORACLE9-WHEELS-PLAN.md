# Oracle9 — download fechado e inspeção de36wheels

Proposta sob delegação, antes de código/rede; sem aprovação individual
inventada. Revisão34268 aceitou o relatório nativo como entradas candidatas,
não lock instalado. Fonte imutável `oracle9-dependencies-attempt2-20261025.json`
SHA8b737f8fe07f6ec42d8984fec013bf43bdf483e3629a04cf3390b3b9f4807113 e
resumo3866fb9f. Fonte compartilhada de validação011ba374. Docker desligado.

## Identidade de projetos consultada em fontes primárias

Não inferir legitimidade só da aparência do nome. Cruzados URLs oficiais
do METADATA nativo e páginas de projeto/repos oficiais em2026-10-25:

- MCP2.1.1: https://pypi.org/project/mcp/2.1.1/ e pyproject do tag oficial
  https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v2.1.1/pyproject.toml
  declaram httpx2>=2.5.0 e mcp-types da mesma versão. Sem extras cli/dev.
- HTTPX2/HTTPCore2: https://pypi.org/project/httpx2/2.16.0/ e
  https://pypi.org/project/httpcore2/2.16.0/ apontam para
  https://github.com/pydantic/httpx2 . O repo oficial Pydantic declara
  membros src/httpx2 e src/httpcore2 e dependência de truststore. Não são
  tratados como o pacote antigo encode/httpx nem renomeados no lock.
  Conteúdo de main confirma identidade do projeto; não é prova de que o
  wheel corresponda bit a bit a um commit. Tags sem v retornaram404 e não
  são usados como prova de release. SHA do arquivo PyPI continua obrigatório.
- Truststore0.10.5: https://pypi.org/project/truststore/0.10.5/ e
  https://github.com/sethmlarson/truststore . Usa truststore do SO, relevante
  ao TLS dos clientes HTTP do SDK na revisão futura. Não altera o MCP do
  projeto para HTTP; stdio continua exclusivo e nada é instalado aqui.
- Annotated-doc0.0.5: https://pypi.org/project/annotated-doc/0.0.5/ e
  https://github.com/fastapi/annotated-doc , coincidentes com metadata.
- MCP-types2.1.1: https://pypi.org/project/mcp-types/2.1.1/ e workspace
  src/mcp-types no tag oficial do SDK acima, mesma versão e repositório.
- SSE-starlette3.6.0: metadata nativo aponta para https://github.com/sysid/sse-starlette ;
  página geral https://pypi.org/project/sse-starlette/ e repo confirmam
  projeto; página versionada no navegador retornou cache miss, não é prova
  nova dessa versão. A versão/hash selecionada vem do relatório PyPI nativo.

Isso é conferência de identidade/procedência declarada, não auditoria
completa de código ou garantia de ausência de vulnerabilidades.

## Incremento proposto

1. Um script host novo, no escopo de preparação pública, somente Windows
nativo existente, stdlib/curl do sistema pinado73d24149. Raiz Temp própria
nova e tentativa consumida uma vez antes da primeira rede. Sem Docker,
pipinstall, extração/import de wheel ou alteração da .venv/produto. Hashes
do programa, do validador011ba374 e das evidências conferidos. Revalidar
pacote original/compressão/projeção e36URLs em vez de confiar só no resumo.
Pyproject/seed devem continuar iguais aos usados no relatório.
2. Baixar **exatamente**36filenames/URLs/SHA256 do relatório. Filenames
seguros, únicos, regulares e sem reparse; .curlrc/proxy/netrc/clientcert
não usados. curl-q como primeiro argumento, HTTPSsomente/sem redirect,
sem retry, connect10s/max30s/maxfilesize32MiB e restante do teto total128MiB,
process timeout35s com reap. Uma transferência por arquivo, HTTP200 e URL
efetiva exatos, hash obrigatório antes de ZIP. Total de subprocessos<=36,
sequenciais, consumo global limitado e resultado registrado. Memórias e
arquivos parciais não viram entradas prontas. Falha aborta sem retry ou
ignorar arquivo, sem ampliar limites. Não copiar credencial/env do host.
3. Fechamento de wheelhouse com manifesto: exatamente36wheels e arquivos
auxiliares próprios declarados, sem desconhecidos/symlinks/reparse ou
arquivos preexistentes. lock **candidato** de dependências com cada
name==version e SHA256; ainda sem wheel do projeto ou prova de instalação.
Registrar tamanhos individuais e soma medidos. Tetos conservadores, não
estimativa de tamanho exato:32MiB/arquivo e128MiB total; inspeção de ZIP
abaixo não extrai nada no host e tem seus próprios tetos de expansão.
4. Inspeção ZIP após hash:<=10.000entradas,<=128MiB expandidos por wheel e
<=512MiB expandidos na soma; teto por member64MiB; streaming limitado,
sem confiar só no size declarado. Rejeitar nomes duplicados/absolutos/
traversal/drive/backslash/NUL, symlinks/special/encryption e bits de
privilégio. Diretórios e nomes UTF8 seguros podem existir; não interpretar
código. METADATA<=1MiB, WHEEL<=64KiB e RECORD<=2MiB.
5. Uma dist-info coerente com nome/version e WHEELmajor1. METADATA Name e
Version correspondentes à entrada. RECORDCSV estrito e coerente com os
membros, sem duplicados ou hashes fracos: SHA256/384/512 e tamanho por
arquivo verificados em streaming; somente RECORD sem hash próprio, e
assinaturas legadas RECORD.jws/p7s apartadas/inventariadas conformePyPA.
Nenhum arquivo extra sem hash, exceto os casos previstos no formato.
Regras de formato baseadas em fonte primária:
https://packaging.python.org/en/latest/specifications/binary-distribution-format/ .
6. Inventariar .pth (conteúdo/sha/tamanho limitado), entry_points incluindo
console_scripts e .data/scripts, além de libs nativas (.so/ELFpaths/hashes).
Inventário não executa entrypoint e não aprova .pth: qualquer .pth exigirá
escolha técnica explícita e revisada antes da instalação, sem apagá-lo para
silenciar. PyPA permite scripts e metadata próprios; não deduzir segurança
apenas do nome. A inspeção é estrutural/integridade, não scanner DLP.
7. Bibliotecas empacotadas têm ciclo de patch independente dos RPMs:
psycopg-binary inclui libpq/OpenSSL, cryptography inclui OpenSSL estático,
pydantic-core/rpds-py/pglast/cffi contêm extensões nativas. Inventariar o que
vier neste conjunto; versões efetivas só serão medidas no Linux depois
de instalação. Atualizar OpenSSL RPM não prova correção das cópias do wheel.
Nenhuma garantia FIPS/kernel/ausência global de CVE é afirmada aqui.
8. Código/testes, nova raiz/manifesto e comando exato serão revistos antes
da rede. Sem outro escritor/job/quota; fontes congeladas durante a ação.
Depois de revisão de resultados, próximo lote separado construirá wheel
próprio fora do checkout e instalará offline com hashes/only-binary/
no-index/networknone. Evitar resolver URLs indiretas de metadata: instalar
conjunto fechado com --no-deps e exigir pipcheck e testes/imports depois,
ou solução equivalente revisada. Ainda não há pacote final nem Gateway
ativo. B-1/B-2/D-090 gate2, SQL e produção seguem abertos.


## Precisões incorporadas da revisão60190 antes de código

Separar D (download/hash/manifesto, uma chamada de rede por arquivo) de I
(inspeção offline, política hashada própria). Ajustar I sob revisão não
redownload/retry de D e não muda nenhum byte da wheelhouse. D não declara
ZIP/instalação aprovados. I só usa manifestos/arquivos revalidados por hash.

D: limite global1500s além dos tempos por processo/requisição, sem sleep
ou retry; stdout curl<=4KiB/HTTP200/URL exata, cwdSystem32, ambiente mínimo
reconstruído. SHA conferido após fsync e novamente ao fechar manifesto:
antivírus pode remover/bloquear, isso recusa sem criar exceção ao antivírus.
Não reutilizar curl_args do módulo RPM: ele restringe URLs ao Oracle e
seria inadequado. Novo argv fechado é específico das36URLs validadas.
Lock candidato sóLinux x86_64/CPython3.11, sem markers, sha256 por linha.

I: métodos stored/deflated somente, sem prefixo/trailingdata e comentário
<=4KiB; EOCD/CD preflight antes de ZipFile (CD<=2MiB e<=10.000entradas).
ZIP64 global/multidisk recusados neste conjunto pequeno; variantes locais
se existentes precisam respeitar comprimentos/ranges medidos. Conferir
cabeçalhos locais/nomes e faixas sem sobreposição, compressed/expanded
contados; não confiar só em tamanhos declarados. .dist-info/.data só da
distribuição correta; WHEELTags iguais ao conjunto expandido do filename,
RootIsPurelib coerente com tags. METADATARequiresDist/RequiresPython
coerentes com a projeção nativa, com normalização semântica/regras de
fold explícitas revisadas. RECORDsha256/384/512 por conteúdo e tamanhos.
Correção de precisão à redação genérica de membros do revisor: PyPA permite
RECORD.jws/p7s **fora** do RECORD, não se exigirá entrada CSV dessas duas
assinaturas legadas; serão inventariadas sem alegar verificação de assinatura.
Nenhum outro membro regular sem RECORD. .pth/entrypoints/todos os grupos/
.data/scripts e bibliotecas empacotadas inventariados, não executados.

Evidência de I terá teto declarado (16MiB bruto/2MiB envelope comprimido
ou equivalente revisado), mantendo inventário completo e resumo. Campos
License/LicenseExpression já no METADATA poderão ser registrados como
fatos, sem introduzir fluxo de governance ou aprovação jurídica fora de
escopo. Na instalação futura: conjunto instalado exatamente o lock mais
ferramentas da base explicitamente decididas, .pth/entrypoints revisados,
networknone/nodeps/hashonlybinary/noindex e pipcheck obrigatório.


## D implementado localmente, aguardando revisão antes de rede

Novo `docs/poc/oracle9_wheels_download.py`, sem Docker nem ZipFile. Valida
hash da evidência completa8b737f8f e usa os bytes pinados do validador
011ba374 para revalidar bruto/projeção; pyproject/seed atuais devem ser os
mesmos.36entradas, .lock candidato e manifesto exatos. curl tem argv novo
PyPI, q primeiro/semredirect/proxy/clientcert/retry; binário73d24149 é
rehashado antes de cada subprocesso e no fim. --maxfilesize=min(32MiB,
resto128MiB), connect10/max30/process35, deadlineglobal1500s, cwdSystem32,
env mínimo. Arquivos exclusivos, fsync em r+b (Windows) e SHA depois e no
fechamento; nenhum byte é interpretado como ZIP/importado. Fonte/inputs
congelados durante D; parcial não vira ready se qualquer falha ocorrer.
19 testes novos puros/fakes passaram (inclui bytes deliberadamente nãoZIP
aceitos só por D, manifestos/lock alterados recusados, URL/limites/env/curl),
Ruff/mypy do teste, formatdos2 e E9/F63/F7/F82 do script verdes. Não é
prova de ZIP/instalação ou lint completo do script; I não implementado.

Nova raiz `C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-wheels-20261025-8ca7de53`,
task0db814cd7c2844bca53f54a1bcca0726, invokedfalse/wheelhouse_readyfalse.
Snapshot `docs/poc/evidence/oracle9-wheels-procedure-v1-20261025.json`, SHA
4565ce25e4a2b692dd8fd8171bad966689a0ab7f43c8edb4ff3d57a564122a60.
Programae3c243cc714123e15589e70442d439ed37d68c0c58618e5e93bfbae0bead50b1.
Policy011ba374/evidência8b737f8f/pyproject917fe735/seedfd77310a e curl73d24149
serão conferidos completos, com estado/root reais antes de executar.

Depois de revisão, uma única D, sem A/B/C Docker, comando separado com
exit conferido (não executar antes dos pins/estado):
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_wheels_download.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-wheels-20261025-8ca7de53'
exit $LASTEXITCODE
```
Esperado36exitsCurl0/HTTP200/URLshaexatos e WHEELS_DOWNLOADED_VERIFIED,
mas não declarar isso antes de medir. Qualquer falha encerra sem retry ou
instalarparcial; conservar tentativa/arquivos, nenhuma limpeza recursiva.
Após D, conferir dataset/hash novamente e registrar/revisar evidência
antes de Ioffline. Fontes não serão editadas durante D. Nenhuma rede/
Docker/download real foi feita neste incremento ainda.

D concluído e revisto por5047; evidênciaWHEELS-VALIDATION. Próximo I usará
somente stdlib e acesso rb; packaging26.3 do host foi apenas identificado
para avaliar alternativas, **não será dependência de I**. METADATA será
comparado como campos normalizados/unfolded pelo mesmo formato JSON do
pip22.3.1, sem resolver dependências ou avaliar código. Fonte primária
PEP566 orienta a normalização. A base do pip22.3.1 remete a _json.py,
mas as tentativas de ler esse arquivo pela web falharam; não se afirma
que seu conteúdo foi consultado. I usa HeaderParser/compat32 e somente
unfold RFC de continuação + strip; compara conjuntos Requires-Dist e
Requires-Python exato assim normalizado, sem reordenar specifiers nem
alterar espaços dentro de strings de markers. É comparação conservadora
de campos, não implementação de equivalência semântica PEP508. Qualquer
diferença recusa I para diagnóstico offline, sem resolver/baixar de novo.
Fonte lida: https://peps.python.org/pep-0566/#json-compatible-metadata . CSVRECORD
assinaturasjws/p7s são exceções explícitas da especificação, fora do CSV.
Nenhum fluxo jurídico/governance novo será criado.

## I implementado, revisão antes de abrir os ZIP reais

Novo docs/poc/oracle9_wheels_inspect.py, stdlib, rb para entradas, sem
rede/subprocesso/extract/import dos wheels. Compõe somente a admissão do
D capturado/hashado e3c243cc (sem executar seu main), incluindo revalidação
da projeção nativa e de todos os36hashes antes do primeiro ZipFile.
EOCD/CD limitados antes da alocação ZipFile; ZIP64 global e extras locais
recusados explicitamente nesta política pequena. Faixas locais contíguas,
descritor medido com/sem assinatura, nome/CRC/tamanhos/flags coerentes;
somente stored/deflate, descompressão própria em blocos64KiB, CRC/tamanho
e EOF sem cauda obrigatórios. Hash final do wheel e novamente do conjunto.

Política de output: até16MiB JSON bruto com todos os membros/hashes,
envelope zlib/base64<=2MiB e hash/tamanho bruto. Prazo lógico120s durante
stream, não garantia absoluta sobre bloqueio de I/O do SO. Cada raiz I é
consumida por invoked.json exclusivo; fontes congeladas na execução.
Falha preserva categoria/arquivo e resultados anteriores, não instala nada.
Se recusar formato legítimo, ajuste offline revisado em outra raiz, sem
alterar bytes/D/lock ou baixar novamente.

51 testes novos sintéticos e133 relacionados passaram. Ruff completo do
teste, mypy strict do teste, format2 e E9/F63/F7/F82 do script passaram;
não se declara Ruff/mypy completos desse script laboratorial. Uma falha
inicial foi erro na fixture (modo octal maior que16bits, struct.error
antes da chamada ao inspetor); corrigida a fixture. Nenhum ZIP real aberto.

Raiz I: C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261025-ff2e25c4,
task022e0c16dbb242dcb1a6962d936e4fde, invokedfalse. Programa
7e0e31fced7b3e4ee21187793cd6b05fee7c37178998ef5a01dd37888fbfcff4,
estado cdfc8648cd41b14dbd4157243592e77b5a91e383e1d9c2db32971e3ef56af4b1,
snapshot oracle9-wheel-inspection-procedure-v1-20261025.json SHA
4e525f63503d0eb69b9593c60cb0a263f821f6c501fadf6e32b3361abdd000ed.
Entrada D8ca7de53/manifesto1d16b3e1/locke24ec23e preservados.

Depois de revisão, conferir todos esses pins completos e ausência do
invoked.json antes da chamada única (não executar antes da revisão):
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_wheels_inspect.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-wheels-20261025-8ca7de53' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261025-ff2e25c4'
exit $LASTEXITCODE
```
Sem Docker, instalação, carga, banco, outro escritor, commit/push/deploy.

### Rerevisão I — 2026-10-26

A revisão pré-ação encontrou I1: saída deflate pode continuar pendente
quando a entrada acaba. Sete regressões com blocos de saída1–7bytes
falharam primeiro com DEFLATE_TRUNCATED. Corrigido por drain de
decompress(b"",65536) com teto/tamanho/CRC/prazo a cada bloco; não se usou
flush() sem teto, que alocaria antes de validar expansão.62novos e144
relacionados verdes. Ruff/mypy do teste e estáticos nos escopos acima verdes.

Também incorporadas as recomendações: um único dist-info e até um data
de primeiro nível, identidade canonicalizada e versão exata; nomes reais
usados na leitura, sufixos internos .data/dist-info não confundidos com
raiz. Needed-version local<=45, ainda sem ZIP64; extras locais/centrais
limitados e inventariados por tipo/tamanho/hash. A regra anterior recusa
o **extra ZIP64 local**, não todos os extras locais. Disk-start por membro
deve ser0. Parser inesperado gera UNEXPECTED com relatório parcial, nunca
sucesso; teste prova persistência e consumo exclusivo da tentativa.

A raiz ff2e25c4/v1 não foi executada e está preservada. Nova raiz/comando
substituem somente a proposta de execução de I, nunca os bytes do D:
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261026-8b7bf71a,
taskc59eb4545cfd4cdf97405e16b1775750, invokedfalse. Programa
2381710a8bdcaf117d903cb8f0876a027230cf89896f9eb39cfed7db006e19cc;
estado a59c80cda03845367ede908966b25f4b4295df610809176db7db2fdd372bfdba;
snapshot oracle9-wheel-inspection-procedure-v2-20261026.json SHA
a3eaf0b0004c468dd9b302e727a7057cc072de70742e0fbb547624733da48326.
Conferir também D e3c243cc, manifesto1d16b3e1, locke24ec23e e ausência
do invoked.json. Não abrir ZIP real até a rerevisão deste delta/comando:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_wheels_inspect.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-wheels-20261025-8ca7de53' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261026-8b7bf71a'
exit $LASTEXITCODE
```

### I2 e execução final prevista

Rerevisão confirmou as correções e encontrou I2: o campo mode do relatório
usava o valor do último membro do primeiro laço, embora as checagens de
segurança já fossem individuais. Delta de produção laboratorial de uma
linha: mode vem de info.external_attr de cada membro no inventário. Novo
teste com modos0644/0755 distintos prova correspondência.63novos e145
relacionados verdes; Ruff/mypy do teste e format2 verdes. O Claude2 aceitou
a execução offline única após essa linha/teste e novos pins, sem exigir
outra revisão desse delta estrito. Nenhum ZIP real ainda foi aberto.

v1 e v2 não invocadas, preservadas. Raiz final v3
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261026-9b5033d4,
task6a0953a58b5549dc8e03d68b1d2d94dd. Programa
2bbcfd531f3da5f39dc4c57e5c6b5e567c2f275c3a4f3452c2435cefc340285f;
estado77e92d0fad3187d6ce01134650a4ea8e7a98070eb71fc5b2b2bdf6727fe83d94;
snapshot oracle9-wheel-inspection-procedure-v3-20261026.json SHA
bd6943256e8b620720401eded9e91edec294b1d6a4fd1af5ed9e558527bea6d4.
Antes da chamada conferir esses hashes, D/manifesto/lock originais e a
ausência de invoked.json. Programa congelado até fechamento da tentativa.
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_wheels_inspect.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-wheels-20261025-8ca7de53' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-inspect-20261026-9b5033d4'
exit $LASTEXITCODE
```
