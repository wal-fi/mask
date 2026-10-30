# T4 v2 — perfil medido, sem mudar o protocolo

Proposta sob delegação,2026-10-28, antes de implementação/efeito novo.
Diagnóstico4f771777 aceito: dois perfis criados, não iniciados, única diferença
Config.StdinOncetrue; fonte são os dois brutos/relatórios publicados sob
`oracle9-admission-run-20261028-34346ce8ed18/`. T4 antiga0566 continua
NOT_PASSED sem atribuição retroativa; consumidos88e2/835c/c789/7c11/9612/
1b06/beeb e raízes86e5/2dd9 permanecem intactos.

## Mudança única de predicado, identidade/protocolo inalterados

Novo módulo `docs/poc/w1_bootstrap_transport_profile_v2.py`, carregando por
hash somente definições e3cf/9612/e6ca. validate_container será cópia explícita
do e3cf com **apenas StdinOnce is False → is True**; teste AST permite só
essa mudança, nenhum outro predicado. Não normalizar/reescrever o inspect
para fazê-lo passar. Posse usa identity e3cf original. create_args, Intent,
labels3/manifesto, imagem621, Sourcecanário9dd1 e canal e6ca permanecem iguais.
Nome de profile no manifesto e3cf não muda o protocolo; o estado/resultado
novo prende explicitamente o validador v2 por hash.

Publicação copia a função9612 com uma mudança fechada de regex: nomes dos
sete casos e3cf em vez de só normal/retain. Mesmos CID/nome do registro,
Cmd/ENTRY do Intent, ENV/labels da policy, scan recursivo/sem dados livres.
Teste de AST prova o resto igual. Categorias incluem literais já derivados
de e3cf/88e2 e valores públicos da enum Fault e6ca, sem texto livre. Cópias
e dependências pinadas em memória; livefiles fora de cleanup. Sem factory,
backend/argv arbitrários, nova lib ou instalação na imagem.

## Um attach e EOF

StdinOncetrue fecha stdin do container quando esse cliente desconecta;
continua só um attach por CID. Isso não é garantia de instante de EOF da
camada Docker. Leitor exato e6ca aceita EOF depois do frame e recusa byte
extra visível; não depende de EOF para delimitar. eof_observed continua
informativo, true/false permitidos. Retain deve continuar vivo após CLI
recolhido mesmo recebendo EOF, pois PID1 dorme. Blackhole/cancel não leem,
flood não depende de ausência de EOF. Fakes com EOF verdadeiro e falso.
Futuro shell/PG T1 deve também aceitar EOF após seed sem depender dele;
nenhum PG/segredo é entregue neste lote.

## Variante de entrypoint e quatro hooks

Novo `docs/poc/w1_bootstrap_t4_v2_run.py`, variante explícita de835c:
kind/rootT4-v2, transport_pins fechado do novo módulo, classe T4V2Host,
category fechado e resultado específico. Driver/join/HELD/ciclo/journal/
restore e condição de sete casos iguais ao835c, com teste AST. Não há
transformação AST em runtime ou rebind oculto. Base é Host88 congelado.

Overrides da classe: __init__, pins, inspect_own e _owned_inspect. Os demais
create_own/_case/perform_b/_collect/cleanup_owned são mesmos objetos88, com
todos os oráculos corrigidos e caps56/414/28/93/50 (585<600) preservados.
_owned_inspect seleciona diretamente o validador v2 na aceitação e identity
original na limpeza; não modifica namespace e3cf nem objeto medido.

Raw local xb antes de parse/validação, contador/t4-captures.json e portãoS1
recalculado. Aceitação exige publicationallowed e perfil estritotrue antes
de permitir start do canário público. Cleanup não é impedido por recusa de
publicação: usa posse e conserva raw local para filtro posterior. Em erro,
categoria fechada é registrada antes de propagar; nada vira FAILED genérico.
Pins chamam88 primeiro e acrescentam módulo/dependências/entrypoint capturados;
livefiles só fora da limpeza. Dockerconfigpinado semproxies antes de A.

## Exportação de todas as cópias

Novo exportador específico v2, variante de beeb pinada com teste de deltas:
root/kind/pins/outcome/rolecount7, nomes dos sete casos e nova função de
publicação; metadados continuam scan estrito de chaves privadas. Registry
com todos os próprios CIDs removidos, result/exit/recursos coerentes, fontes
regulares e limites/releitura/freshdest iguais. Nada de exportar HELD ou
citar destino sem transport.json. Cada alias é filtrado, nunca confiar no
allowed do produtor, sem ler raw em ferramenta antes do filtro.

Além de admissionraw e inspect-before, **retain-cli-reaped-cid-alive.json é
um raw próprio distinto**: parent88 o grava no inspect direto depois de
quiesce e antes de killCID. Exportador deve reconhecer papelretain, usar
CID/nome do registry/Intent e exigir SHA/tamanho compatível com um comando
inspect-cleanup-retain registrado; não comparar esse raw vivo com o raw
de admissão Statecreated. PortãoS1 em todos, sem alias que escape. Relatórios
do canário normal/negativo são metadata fechados, sem corpo/hash de seed.

## Gates antes de qualquer execução

AST de mudança única de validador/regex, somente quatro overrides, demais
métodos idênticos, EOFtrue/false, todos sete casos, publicação recusada sem
start e cleanup funcionando, Fonte mutável recusada/cleanup pela captura,
categorias sanitizadas, todos aliases inclusive retain vivo/CID incorreto,
whitelist de artefatos, integridade/reuso/HELD e preparador. Ruff/format/
mypy, revisão de código; depois root/task/estado/comando novos e revisão
antes de uma rodada única. Nenhuma mudança de outros perfis, labels, tetos,
canário/leitor, SQL, serviço ou produção. Oracle9.8/WSL2 continua sem atestar
kernel EnterpriseLinux/SELinux, B-1/B-2/D-090/C1 continuam abertos.

## Precisões do aceite, incorporadas antes do código — 2026-10-29

C1 obrigatório: classificar por tipo exato das classes dos namespaces
capturados pelo Host: BootstrapError com Fault exato→valor enum; IdentityError
→IDENTITY_UNKNOWN; EmergencyError→INPUT/PIN/BUDGET/COMMAND exatos; literal
RuntimeError do watchdog e demais need derivados; TimeoutError/CancelledError.
Tipo/args/enum desconhecidos viram INTERNAL, sem isinstance amplo/str(error).
Conjuntos testados por AST/enum das fontes pinadas. O classificador recebe os
namespaces do próprio host, não classes de outra carga dos mesmos arquivos.

Validador v2 recebe explicitamente a factory capturada para resolver seis
nomes locais identity/channel_bytes/Case/ENV/need/labels_for. Isso preserva a identidade
das classes Intent/Case do host sem alterar namespace congelado. Teste AST
retira somente esse parâmetro/seis bindings e normaliza o único booleano;
todo o resto é igual ao e3cf. Não há transformação de AST em runtime.

Ordem de inspeção: rawxb→manifesto→S1→posse→validadorv2→categoria gravada→gates
que abortam. Publicação negada aborta antes de criar ManagedBootstrap; cleanup
segue por posse. Inspect direto inicial de cleanup não é arquivado, marcado
false no resultado, salvo o alias vivo de retain escrito pelo parent88.
Esse alias exige match com pelo menos um inspect-cleanup-retain de mesmo
hash/tamanho (podem existir dois em falha), registryretain e nome/CID próprios.

Data nova29 vale para propostas/raízes novas; nada com data28 é reexecutado.
O código e os fakes têm revisão própria antes de estado/comando/efeitos.
