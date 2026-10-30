# Bootstrap público T4 v2 — validação incremental

Estado em 2026-10-29: perfil puro implementado; integração ainda em preparo.
Não houve nova raiz, DockerCLI, container, attach, seed, banco ou serviço.
Delegação vigente; revisão de código própria, sem inventar aval individual.

## 1. Perfil puro

`docs/poc/w1_bootstrap_transport_profile_v2.py`, SHA-256
`4699bb204ced65dcb1cbcb4f4d2908bde224c39f3c8aaeb4b4dd8cb3e10dcca4`.
Dependências consumidas e3cf/9612/e6ca preservadas. Validador explicitamente
recebe a factory do host: seis colaboradores, incluindo labels_for. Retirados
esses seis bindings e o parâmetro adicional, AST idêntica ao original após
normalizar somente StdinOnce True para False. Publication só amplia a regex
de nomes aos sete casos, sem relaxar S1 ou normalizar observação.

Categorias usam tipos exatos dos namespaces capturados do próprio Host,
Fault exato, argumentos fechados; estranho/subclasse/erro malformado vira
INTERNAL sem texto. Capturas verificadas mesmo em cleanup; arquivos vivos
só fora dele. Nenhum AST transformado em runtime.

Windows nativo Python3.11.3: 24 testes aprovados em 0,54s; mypy strict do
teste limpo. Ruff e format do teste, lint restrito/format do helper limpos.
Primeira execução: regressões falharam antes de corrigir labels_for ausente
(NameError); binding acrescentado e desenho precisado de cinco para seis.
Houve erros de fixture nos construtores de exceções e uma expectativa que
ignorava a normalização de EmergencyError: corrigidos só no teste. Não são
medições do canal real. Sem suíte PG/frontend/pacotes neste núcleo isolado.

Revisão somente leitura do Claude2 solicitada. O aceite do desenho27358 com
C1 não substitui revisão deste código. T4/B-1/B-2/D-090/C1/SQL/produção abertos.

## 2. C1 herdado e integração do Host

Revisão85705 recusou o perfil inicial: C1 faltava nas origens herdadas de
clock/ciclo/journal/coordenadores/bounded. Regressão CYCLE_REFUSED falhou
primeiro (INTERNAL); mapa ampliado com tipos exatos/literais derivados por
AST de cada fonte pinada. ValueError só CYCLE_SCHEMA/CLOCK_REFUSED;
HostFault só classe do bounded capturado e categoria/args coerentes.
Conjunto RuntimeError inclui need e raises literais de 4bc/b593/88/e3cf
e entrypoint novo. Sem AST em runtime. Perfil final desta medição:
`3a5bb9a3c6b38fcefb910fd498d01fc3a4fc9c04ae379d81dbc48b462f8c116a`.

`docs/poc/w1_bootstrap_t4_v2_run.py`:
`28b5601348fb7c8e95df9780b7f2424cb49ecf21306fffd3d2e39cb18d124538`.
TransportHost tem somente quatro overrides; os demais métodos de 88e2
são os mesmos objetos. Sem alteração dos sete casos ou tetos. Driver,
retenção HELD, join e restauração iguais por AST ao835c. Factory é o próprio
namespace e3cf capturado pelo Host, passado sem cópia/mutação. Rawxb local
e manifesto antes da validação, S1 independente, categoria persistida antes
de propagar. Publicação negada não inicia owner e não impede limpeza própria.
Inspect direto inicial de cleanup não é arquivado, flagfalse; retain vivo
continua sendo artefato distinto obrigatório do filtro futuro.

Windows3.11.3: 65 testes novos aprovados em14,41s (26perfil/11host/28entry);
sem processos/threads reais, DockerCLI, raízes ou seed. Ruff src/tests limpo,
format316 conforme; mypy strict311/314 em314 arquivos limpo, runtime só3113.
Diffcheck limpo (avisos de futura conversão LF/CRLF preservados).
Um teste de identidade de métodos inicialmente comparava os métodos built-in
ligados a cada classe: fixture precisada para excluir init_subclass/subclasshook,
mantendo a igualdade de todos os métodos herdados do coordenador.
Exportador/preparador/estado/comando e rodada nativa ainda não entregues.

## 3. Aceite do núcleo e exportador/preparador

Revisão14731 aceitou perfil3a5bb9a3 e entry28b56013 sem bloqueador, inclusive
C1/factory/quatro overrides. Recomendação não bloqueante de origem adicional
da categoria não incorporada: os tipos são conferidos, categoria já é fechada;
mantém-se o incremento delimitado. Não é aceite operacional.

Exportador novo `w1_bootstrap_t4_v2_export.py`:
`aeade45d01106756489e8e1cbe2bfdd6758b5b3ee07b3e16dc246bda750f900a`.
Derivado do beeb preservado, específico sete papéis/novas raízes/resultados/
pins. Mesmos limites, scanner metadata e releitura; sem raw antes do filtro.
Retain vivo é raw distinto: só publica se hash/tamanho têm correspondência
com inspect-cleanup-retain exit0 registrado, CID/nome próprios e S1 próprio.
Ausência de registro/hash trocado/CID errado/chave privada são retidos.
Não trata o inspect-before como prova de retain vivo. Outros aliases têm
captura registrada/hash/tamanho, publicação sempre recalculada.

Preparador `w1_bootstrap_t4_v2_prepare.py`:
`8e024cf4c24ddfe66fa1cc54f8fcf65d952f75cb65fde388403f823d97f41826`.
Kind/rootdate29/transport_pins novos, main28b pinado, original congelado.
Só funções de materialização exclusiva, sem chamada operacional no import.

28 testes de exporter/preparador passaram em31,07s, Ruff/mypy dos dois
testes limpos. Fake Engine não usa recorder real: fixture simula explicitamente
o único registro CLI de retain vivo; não é medição nativa. Expectativa inicial
de16aliases estava errada: são20 nesta simulação (7before+12captures+1retain),
ajustada só no teste. Sem efeitos reais novos. Código em revisão própria;
proposta exata/raiz temporária/comando/rodada ainda pendentes.

## 4. Proposta exata, ainda sem efeitos

Revisão76265 aceitou exporter/preparer sem bloqueador; notas cosméticas/origem
fechada adicional são opcionais e não mudaram pins. Nova proposta no checkout
`docs/poc/evidence/oracle9-t4-v2-prep-20261029/`, ainda sem raiz temporária:
rootde8e832ca4c67fd35f3647779adfaad0/task42d363a1115633d15fbb809fc0dc666e,
3305bytes/SHA bec0accdf51e18e94fd66a14a2272d8b54464005ad40cc133b1bd4e068ac4116,
script b01ce0b2f2681d45dc0ea11c37604b1c4aed467bad1b2298448980fcfed09ce3.
Estado canônico, sete medições/createargs inalterados, comando literal-I-B.
Revisão própria do estado/comando antes de materialização e invocação única.
Ruff/format320 e mypy311/314 em316arquivos limpos; runtime só3113. Ainda sem
nova rodada nativa, sem produção. Nenhuma fonte consumida foi modificada.
Uma atualização documental via pipe foi recusada antes da escrita porque a
codificação do pipe alterou a comparação do título; refeita por apply_patch,
sem transmitir texto não ASCII por PowerShell para Python.

## 5. Materialização e invocação únicas

Review52272 aceitou estado/comando/procedimento, condicionado a bytes exatos.
Materialização única pelo8e024cf4 em Temp conferiu3305bytes/bec0accd, somente
attempt, argv igual; materialized-proof.json preservado no checkout. Desktop
sem processos app/backend em13:11:00.1125191Z. Scriptb01ce0b2 invocado uma
vez, sessão10282; acompanhar terminal/recursos sem outra CLI ou writer.
Fontes/root agora consumidos, não editar/reutilizar/repetir. Resultado nativo
ainda pendente, nenhum gate real declarado aprovado. Categorias são fechadas;
o campo opcional de origem sugerido pelo revisor não foi implementado.
Seleção relacionada anterior à rodada:478passed/2deselected em100,52s, excluídas
explicitamente as duas provas nativas consumidas de handle/pipe. Não é suíte
integral nem prova nova de PG, worker ou memória total.
