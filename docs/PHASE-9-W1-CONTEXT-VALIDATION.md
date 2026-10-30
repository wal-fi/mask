# W1 — preparador público e delta exato, sem materialização

2026-10-27. Implementação sob delegação após revisão do desenho em
W1-APP-UPDATE-PLAN, com L1–L3 incorporados. Novo helper laboratório
docs/poc/oracle9_w1_context.py. Nenhum main/materialização, pip, import do
app, DockerCLI ou instalação foi executado neste incremento.

Bibliotecas históricas de builder/projeção capturadas por hash sem chamar
main/sources antigos. Fonte atual deve ser igual ao manifesto W1 aceito124;
ambos wheels6b63f239 são rechecados e re-inspecionados. Projeção antiga122
deve coincidir exatamente com owner maskgw da atestação d479; nova127 ganha
cinco paths, muda apenas postgres.py/budget.py/RECORD e não colide com36deps.
Target1387 só copia os demais owners/scripts/tools, sem reinstalar nada.
Um lock por nome/hash, um wheel e manifesto formam o contexto proposto.

L1 adicional ao verificador RECORD existente: check_delta compara todas as
linhas fora do package/dist-info exatamente com installed_snapshot anterior,
inclusive RECORDs/outros metadata/modos/UID/GID/links/wrappers. Dentro: cinco
novos, três com bytes diferentes, nenhum removido; todos os demais iguais,
metadados das duas fontes e RECORD conservados, novos0644/root:root e
bytes/SHA do alvo. RECORD reescrito ainda exige seu verificador nativo próprio,
que este helper não finge executar. Prefix3332→3337 é expectativa, não medição.

34testes novos aprovados: projeção com relatórios públicos congelados,
mutação de owner/membro/delta/metadata, dependência ou link alterado,
conteúdo/modo/UID inesperados, arquivo extra, lock por nome/hash, arquivo
regular/hash/tamanho e diretório fechado. Modelo físico pequeno é explicitamente
fake, não inspeção ZIP/instalação. Fonte oversized recusada antes de leitura.
Inventário exato dos três arquivos e reparse/type são conferidos no helper.

Seleção relacionada5arquivos:157passed/1skip. Skip preexistente do builder
por privilégio de symlink indisponível neste Windows. Primeira seleção deu
148pass/1skip/1falha: teste antigo esperava que sources do contexto119 ainda
aceitasse checkout agora124. Falhou corretamente APP_SOURCE_CHANGED.
Atualizado só esse teste para contraprova explícita de recusa histórica;
programa/artefato/evidência119 permanecem intactos. Não se alterou pin antigo
para fazê-lo aceitar W1, nem se pulou o caso. Positivo124 pertence ao novo
artefato/preparador; ainda exige main materializado em rodada própria revisada.

Ruff completo no teste/src/tests e mypy strict alvos3.11/3.14 em294arquivos
limpos. Format em294arquivos+helper limpo; lint do helper sóE9/F63/F7/F82,
sem alegação de tipagem/full Ruff no helper sem tipos. Runtime3.11.3 Windows.
Não é suíte Python integral/PostgreSQL ou prova de instalação Linux.

Pins antes da revisão:
- preparador6c995cf9907c754496deca34b47e62b396f6c2e764ea8284d435422f0ab21cc2
- teste novo e14d8b7591eb1dd5efcd8a58b42408c33b3af3cc92af83c74e639d999c71b41e
- teste histórico4b7e3d1b4546f81d1e99433ed1f667b22f773cbdbbb67d4b8bf5c14d16a97f33

Revisão somente leitura do código pendente antes de preparar estado/comando
da materialização. Payload Linux/host/ciclo ainda não implementados. W1
instalado/nativo/B-1/B-2/D-090/C1/SQL/produção abertos. DesktopOff, nenhum
commit/push/deploy, quota/job novo ou segundo escritor; alterações anteriores
e artefatos26/10 preservados.

## Fechamento do código após revisão

Claude2 revisou6c995cf9 sem bloqueador para preparar raiz/comando. Três
recomendações incorporadas antes da materialização: erro próprio agora tem
categoria de conjunto fechado (ContextRefusal); mensagem de RuntimeError
estranho não é serializada. Linha do wheel antigo exige SHA9181d955 e
tamanho429231 antes de substituir; duas regressões falharam antes do fix e
passaram depois. Casos parametrizados conferem a categoria exata da recusa.
São37testes focados aprovados, sem skip. Ruff/teste e lint restrito/format
helper limpos; mypy3.11/3.14 no teste limpos. Medição294arquivos anterior
continua histórica; produto/src não mudou nesses ajustes.

Novos pins: helper94cfa9118625d175a67a398bb2c416b5ca392e7a3b458cc433dc63fa02c75d78,
teste2e4159fbc83612996e7312608f04fad87d61ef81ab65c1bf8cdca87d253a890b.
Delta final e estado/comando da raiz nova serão revisados juntos. Native
payload carregará esse helper por bytes capturados/hash e __file__ com
profundidade explícita (/opt/maskgw/lab/context.py), não um nome raso; não
duplicará check_delta sem pin. Não afirma que esse carregamento ocorreu.

## Materialização preparada, não invocada

Raiz nova
`C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-w1-context-20261027-35fdbf68fbf04dc4a849c7d4392db0b2`,
task8511960ea15a41c9b48f46b99dcfc394, somente state.json/invokedfalse,
SHA22436c2f61c894eeb37432db1d92086e213fa4eed049a03a9035b163e0ef3778.
Espelho público em oracle9-w1-context-preparation-20261027.json; não há
contexto/ready nem sentinel. Preflight conferirá hash de helper/estado e
sentinel ausente, uma invocação no cwd do projeto e conferência pós-retorno.
Comando exato proposto:
```powershell
& '.venv/Scripts/python.exe' -I -B 'docs/poc/oracle9_w1_context.py' 'C:/Users/w.filho/AppData/Local/Temp/maskgw-oracle9-w1-context-20261027-35fdbf68fbf04dc4a849c7d4392db0b2'
```
Saída/exit0+W1_CONTEXT_VERIFIED e hashes/inventário dos três arquivos serão
conferidos; falha preserva prefixo/diagnóstico e não repete na mesma raiz.
Não há DockerCLI/install/app import/DB/clock nesta execução proposta.

## Materialização concluída, após revisão do delta/estado/comando

Uma invocação do94cfa911, exit0/W1_CONTEXT_VERIFIED. Preflight conferiu
helper, estado, raiz fresca e ambos wheels; helper admitiu fontes124 e dois
wheels no começo/fim. Primeiro sources/main positivos com dados reais passaram.
Nenhum backend/build novo, instalação ou import do app foi necessário.

Contexto fechado: manifesto270278bytes/SHA
d4d4b29b302215b00d56ce249caebe6c5f76943d85725c654b8063d4940c5df8,
lock93bytes e wheel448821bytes/SHA6b63f239; soma719192bytes, três arquivos.
Rechecagem independente pós-retorno: raiz exatamente state/invoked/context/
ready; contexto e bytes/inventário relidos com check_context. Target1387 é
projeção, não arquivo instalado ou prefix medido. Main não foi repetido.

Espelhos exatos:
- oracle9-w1-context-manifest-20261027.json:270278bytes/SHA d4d4b29b acima;
- oracle9-w1-context-result-20261027.json:SHA
  5e908fa37ffeec362ae08e7c9a3244258fc3a87b248537f44ad1d1859a7e6160.
Preparação invokefalse acima é histórica; sentinel atual consumido impede
retry nessa raiz. Artefatos26/10 e produto/src inalterados. Evidência segue
para revisão somente leitura antes do payload/host. Nenhum DockerCLI,
pip/install, SQL, commit/push/deploy, quota/job ou outro escritor.

Revisão final da materialização concluída: insumo público fixo aceito para
implementar payload/host. Revisor declarou uso de buscas dirigidas/valores
do root para os hashes, não recalculou em shell. Target/prefix seguem somente
projeção; nenhum programa antigo/artefato foi regravado para fingir instalação.
