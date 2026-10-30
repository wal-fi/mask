# Admissão — exportação S1 das evidências

2026-10-28: implementada e em revisão somente leitura. Não executada sobre
uma raiz real do diagnóstico (ela ainda não existe), nenhum Docker/PG/seed
ou subprocesso/thread do produto novo. Desktop Off, fontes/raiz T4 consumidas
preservadas. Runner7c113617/20 e núcleo9612/71 aceitos antes deste exportador.

`docs/poc/w1_bootstrap_admission_export.py` importa apenas definições do
runner pinado. Root admission exata, somente terminal FINISHED/ABORTED e
invokedtrue, estado canônico/pins/medidas exatos, exit relatado consistente,
limpeza/inventário/Desktop/thread provados nos registros. Esses registros
não são um atestado independente do SO; exit é informado pelo procedimento
externo, que precisa conferir a sessão real. Destino restrito ao evidence
com taskprefix, diretório novo, sem sobrescrita ou exclusão.

Snapshot limitado256arquivos/4MiBporarquivo/64MiBtotal, somente nomes
fechados/regulares/não-reparse. Todos classificados e conferidos antes de
mkdir. Raw de admission-inspectNN, inspect-before herdado e cleanup passam
novamente pelo núcleo com CID/nome do registry/Intent; não confiar no bool
publicado pelo produtor. Alias herdado precisa ter hash/tamanho do raw de
admissão. Raw não registrado fica retido por padrão. Metadata de imagem só
sai se bytes iguais à projeção canônica do registro histórico pinado.

Qualquer raw negado não ganha arquivo no destino: manifesto contém apenas
nome fechado, hash/tamanho, publishedfalse e categorias do portão. Fonte
permanece intacta em Temp. Todas as cópias de raw são verificadas, não só o
nome principal. Demais documentos foram gerados pelo runner/núcleo pinados
em schema público: relatórios de Env/texto livres só igualdade/diferença,
comandos/digests públicos e categorias fechadas. Não reutilizar em container
de PG/entrada privada. A guarda não identifica credenciais em valores
arbitrários fora de seus campos, conforme o limite do núcleo já aceito.

Releitura da lista/bytes fonte antes e depois da escrita. Manifesto completo
só após verificar tudo; se fonte muda durante escrita, destino parcial
público é preservado sem transport.json, não declarado completo. Sem retry.

## Medições

14passed/9,44s, Windows3.11.3, controller/CLI/monitor/clock simulados. Testes
rodam o ciclo/journal/diagnóstico falso aceito, depois exportam seus arquivos:
quatro aliases públicos, proxy fictício nega duas cópias e nenhum valor
aparece em qualquer arquivo exportado; flagallowed forjada ignorada;
cleanup com Auth fictício negado; raw desconhecido retido; hashes/alias/
imagem/estado/resultado/arquivoextra inválidos abortam antes do destino;
exit incoerente, destino existente e fonte alterada durante escrita.
Ruff src/tests limpo, mypy310arquivos311/314 limpos, runtime só3113;
helper só lint restrito e format, não strict helper.

Primeira execução14erros de fixture: o harness criava subdiretório dentro
do conjunto que depois tentava copiar como arquivos. Corrigido para tirar
snapshot da lista antes de criar o destino de teste, sem alterar o helper.
Repetição final14/14 acima; imports/assinatura de fixture/anotação de lista
também corrigidos nos checks estáticos. Não atribuir esses erros ao produto.

Pendente: revisão do exportador, preparador/estado/comando próprios antes
de qualquer diagnóstico real. Nenhum transporte com raw real novo foi feito.
Não fecha T4, B-1/B-2/D-090/C1, SQL, PG ou produção.

## Aceite e reforço dos metadados

02bf49d2/14 aceito pelo Claude2 como componente. Recomendação de defesa em
profundidade reproduzida antes do delta: version.json com HTTPProxy e
admission-reports com Auth inesperado eram copiados,2failed/14deselected/1,91s.
Versãobeeb85d6 aplica scan recursivo proxy/auth também a cada JSON de
metadata, com rejeição de duplicatas/NaN/shape escalar. Negado fica apenas
no manifesto por nome/tamanho/hash/categoria, nunca arquivo com valor.
16passed/10,91s, Ruff/mypy311/314311 limpos. Reforço em rerevisão, sem uso real.

Limites: HELD não é exportável por este helper; precisa de caminho específico
e revisado com recuperação, sem afrouxar fase/provas. Destino sem transport.json
é incompleto, não evidência para citar ou commitar. Não é atestado independente
do SO nem scanner de valores arbitrários/credenciais; scope só lab público.
