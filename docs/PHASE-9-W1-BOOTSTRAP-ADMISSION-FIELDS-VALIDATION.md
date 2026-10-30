# Admissão — núcleo puro de diferenças e publicação

2026-10-28, sob delegação. Desenho ADMISSION-DESIGN aceito de forma estreita,
S1/precisões incorporados antes do código. Em revisão somente leitura;
**nenhum chamador operacional ou novo Docker/PG/processo/thread do produto**.
Último Desktop Off, nenhuma repetição do main/raiz T4 consumidos.

`docs/poc/w1_bootstrap_admission_fields.py` só compara metadados. Cada campo
de Config/HostConfig/ulimits/superfície é avaliado, sem parar na primeira
diferença. Observações de Attach* separadas, Statefalse/Pidint0 separado.
Comparação original e3cf permanece inalterada; casos positivos e negativos
do teste conferem concordância. Categoria explícita deriva dos literais need
das fontes e3cf/88e2 pinadas, com igualdade de conjunto por AST no teste;
args errados, texto livre ou classe diferente viram INTERNAL.

S1 é função pura de exportação: recebe raw local, devolve só permissão,
categorias fechadas, tamanho e hash. Env exato, labels esperados com opção
única de apresentação conhecida, Cmd/Entrypoint públicos exatos; procura
recursiva de chaves proxy/auth sem distinção de caixa. Malformação, duplicata
de chave, NaN, tipo/shape errados ou recusa impedem publicação. A função não
grava arquivo nem devolve raw. O chamador/exportador ainda será implementado
e terá de cumprir esse resultado. Não alegar publicação ponta a ponta pronta.

Diff não inclui valores observados de Env/texto livre. Somente escalares
numéricos/booleanos ou valores exatamente iguais à expectativa pública são
exibidos; divergência de texto/lista/objeto vira DIFFERENT. Nenhum input privado
real foi usado, somente canários fictícios nos testes.

## Medições e limites

66passed/1,08s finais, Python nativo Windows3.11.3. Cobrem dois perfis,
26campos de perfil individualmente,19campos de superfície, divergências
simultâneas, ulimit duplicado/mounts, Statefalse versus Pidbool/int, categorias
AST, Env de proxy/auth recursivo/labels/Cmd fictícios, apresentação pública
conhecida, raw malformado/duplicata/NaN. Sem raiz/estado/comando novo.
Ruff src/tests limpo, mypy strict311/314:308arquivos sem erro; execução só3113.
Helper só lint restrito E9/F63/F7/F82 e format, sem strict helper declarado.

Primeira rodada66/66/1,01s; depois ajustes de lint do teste deixaram duas
referências antigas de variável:2failed/64pass1,49s, Ruff/mypy também falharam
nesses nomes. Corrigidos só os nomes do harness; repetição final66/66 acima.
Não ocultar essa rodada ou atribuí-la ao produto.

Pendente: revisão do núcleo, integração em variante create/inspect-only com
captura local antes de parse e guarda na exportação, categorias preservadas,
fakes de ciclo/posse/limpeza/retention, depois estado/comando revisados antes
de qualquer efeito real. T4/B-1/B-2/D-090/C1/SQL/produção continuam abertos.

## Aceite do núcleo e reforços sem efeito operacional

Claude2 aceitou72e8347f/66 como núcleo puro. Recomendações1/2 reproduzidas
com4regressões vermelhas antes do reforço:4failed/66deselected/0,45s, inspect
de CID/Name diferentes passava pelo portão e chaves auth/proxy fora de
Config/HostConfig também. Sem arquivo exportado ou credencial real.

Versão9612a46b exige CID/nome próprios como argumentos obrigatórios e compara
valores/formato exatos; varre o objeto info inteiro. Recomendação3 acrescenta
só presença/igualdade de cada chave própria, presença do label conhecido e
contagem, sem nomes/valores de chaves desconhecidas.71passed/1,13s; Ruff e
mypy src/tests308311/314 limpos. API agora exige kwargs cid/name; integrador
deve usar registro de create/intenção, nunca o Id/Name do próprio raw como
expectativa. Reforços em rerevisão antes de integrar.
