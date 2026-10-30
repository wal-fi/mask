# W1 — payload de atualização/sonda, somente testes locais simulados

2026-10-27. Sob delegação, após desenho/revisão L1–L3 e contexto d4d4b29b
aceito. Novo deploy/oracle9_w1_update.py,29803bytes, sem chamador operacional.
Nenhum main Linux, pip, DockerCLI, imagem, app import real ou instalação
executado. Tests usam relatórios públicos/fakes e pequenos arquivos locais.

Bibliotecas em blobs comprimidos limitados/hashiados antes de compile:
origin ee2becec e context94cfa911 exatamente, com __name__ privado e __file__
profundo /opt/maskgw/lab/origin.py e context.py. Não altera suas constantes
para admitir outra contagem, não chama main/install/probe/load_inputs antigos.
Reusa verificador RECORD/projeção/delta em vez de criar parser de pacote paralelo.

Install exige runtime/perfil/PID1/root e nova atestação ausente. Umask022
explícita antes de pip. Contexto revalidado por SHA/tamanho/inventário/lock/
wheel e metadados UID/GID/tipo. Target é derivado de novo a partir da origem,
não só aceito como declaração das36deps. Original d479 precisa coincidir
com scan antes de pip; antigo verify_install executa antes/depois. Só maskgw
por nome/hash, find-links local, --no-index/no-deps/require-hashes/only-binary/
no-compile/no-cache-dir/force-reinstall. check_delta94cfa confere linhas
inteiras. Versões e .pth precisam permanecer iguais. Nenhum worker/SQL.

Sete imports/native antigos permanecem objeto comparável inalterado. Cinco
módulos W1 separados, caminho/hash/tamanho contra projeção, com contraprovas
escopadas que recusam rede/spawn/thread.start durante import. Prefixo relido
depois. Teste usa fake import_module; não afirma que esses imports ocorreram
no pacote Linux ou que contraprovas Python substituem isolamento de SO.

Nova atestação em caminho próprio, inclui origem/snapshot anterior/base/
snapshot atual/manifesto/native/versões/imports; original é preservada e
rechecada após install. Limite4MiB, gravação exclusiva+flush/fsync. Sonda só
lê a atestação nova pelo SHA fornecido, sem fallback/read da antiga; refaz
RECORD/delta/native/versões/.pth. Inputs públicos só são removidos pela lista
exata após segunda admissão completa. Falha depois da gravação mas antes do
cleanup não produz sucesso; host futuro deve recusar commit e recolher seu CID.

32testes novos aprovados no Windows3.11.3: blobs truncados/extra/hash/teto,
ABI de __file__ profundo, manifesto/owner/ROW/rewritten flag/delta, prefixo
divergente antes de pip, falhas de RECORD/dependência/import/native/cleanup
sem sucesso/atestação indevida, flags/ordem/umask, remoção exata, origem por
hash, sonda lendo só o arquivo novo e import falso de cinco módulos com bytes
conferidos. Nenhum processo pip real, cgroup/kernel ou pacote instalado novo.

Seleção7arquivos:226passed/1skip em12,99s. Skip de symlink sem privilégio
preexistente no builder. Ruff/check+format src/tests295arquivos, mypy strict
3.11/3.14 em295arquivos limpos; runtime somente3.11.3. Lint do payload só
E9/F63/F7/F82 e format, não mypy/full Ruff do laboratório sem tipos.
Primeiros22casos passaram, ajustes iniciais de lint/tipagem dos fakes foram
corrigidos antes da matriz32; não são prova nativa. Fonte de src inalterada,
wheel/contexto continuam os mesmos e não foram refeitos para esta etapa.

Pins:
- payload727c1276162cad3e6b3f0e464384a232c616919f69800b985cd0be9ec6fb2255;
- teste2bc5257549746e65a1507dfa2b4ffccc68def81d36db2c315d6fda287e0143a9.
Revisão somente leitura pendente antes de host/controles. DockerDesktopOff,
nenhum segundo escritor, quota/job, commit/push/deploy. Instalação e prefixo
3337, W1 nativo/PG16/B-1/B-2/D-090/C1/SQL/produção continuam abertos.

## Delta D1 após revisão, antes de qualquer execução

Claude2 não encontrou bloqueador de segurança/contrato, mas exigiu corrigir
diagnóstico antes de executar. Duas regressões vermelhas provaram que recusas
do origin e ContextRefusal perdiam categoria. Agora só RuntimeError exata de
um único argumento str pertencente às78categorias extraídas do need do
ee2becec, ou ContextRefusal exata do núcleo/conjunto fechado, preserva reason.
Não chama str(error)/str(objeto), não serializa mensagem desconhecida,
subclasse, grupo ou categoria adulterada. Teste verifica o conjunto contra
AST do blob original, não contra lista inventada. Campos públicos/fixos só.

Recomendações incorporadas: preloaded é capturado antes das contraprovas e
guardado separadamente de modules/hashes, sem declarar novo import de módulo
em cache. invalidate_caches logo após pip e antes das verificações/imports.
Sonda confere SHA da serialização canônica do manifesto embutido contra d4;
terceira regressão vermelha mostrou que antes disso alcançava scan com alvo
adulterado. Não muda o manifesto, a projeção ou inputs já aceitos.

37testes focados aprovados, runtimeWin3.11.3; lint/typing finais serão
conferidos após ajuste editorial de nome da subclasse de erro do fake.
Payload agora32598bytes/SHA
566c46a80675a08a45c6283e9960a8a1b7f946225d2497e42e17404472b74ea6.
727c1276 anterior fica histórico. Delta segue para rerevisão; ainda sem
host/ciclo, execução/pip/Docker ou claim de instalação/import Linux.

Rerevisão do delta D1 concluída sem bloqueador:566c46a8 congelado para host/
ciclo. Estáticos finais src/tests295arquivos limpos nos dois alvos; format
295+payload limpo, lint restrito do payload limpo. Teste final c161db83d17e91b79c8a0c04f5290e558c03925abb99455d3372dc3cf075d701.
37casos executados antes da troca editorial Derived→DerivedError no fake;
sem mudança funcional após essa medição. Próximo host medirá argv Windows
inteiro com margem, admitirá atestação só de sucesso e fará cópia do conteúdo
do contexto com dono0:0. Execução física ainda exige procedimento/artefatos/
comandos e revisão próprios, sem aval individual adicional presumido.
