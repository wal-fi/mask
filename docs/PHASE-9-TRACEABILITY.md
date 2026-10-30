# Fase 9 — matriz de rastreabilidade normativa

## Runtime Oracle Linux medido — 2026-10-25

A imagem intermediária local com Oracle Linux 9.8 e Python 3.11.13 passou
na atestação e na sonda final (UID 10001, read-only, network none,
cap-drop ALL, 128 MiB). ID:
`sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4`.
Os nove RPMs vieram da mesma cópia verificada; sem novo download. Fontes,
manifesto e imagem identificados por hash, sem promessa de rebuild bit a bit.
154 testes direcionados passaram; 24 comandos Docker da rodada final com
exit 0. Dois containers próprios removidos, inventário vazio; Desktop
restaurado off em 2026-10-25T23:07:58.6258954Z. Nove tentativas anteriores
NOT_PASSED e imagem anterior em quarentena preservadas. Evidência:
`docs/PHASE-9-ORACLE9-PYTHON-VALIDATION.md` e cópias attempt10/summary.
Revisão final 79449 aceitou esta imagem como base da preparação seguinte.
Resolução nativa posterior selecionou36wheels, sem instalação; evidência
em PHASE-9-ORACLE9-DEPENDENCIES-VALIDATION. B-1/B-2/D-090 seguem abertos.

**Gateway ainda não disponível:** faltam fechamento das dependências Linux,
aplicação instalada e integração do worker/domínio. B-1 fim a fim, B-2,
D-090 gate 2, SQL PGWire e produção continuam abertos/recusados. O destino
é Docker nesta máquina, Oracle 9.8 aceita pelo usuário; não perguntar de
novo. Userland Oracle sobre kernel WSL2, sem certificação de kernel RHEL/
Oracle ou SELinux. D-119/opção A mantém o contrato prospectivo, sem marcar
C1 pronto. Não usar o banco ou credenciais antigos de aceitação.

**Registro histórico do destino em2026-10-23 — Docker local, família Enterprise Linux9:**
O usuário indicou esta máquina, imagem RHEL9.9 ou Oracle Linux9.9, e pediu
aviso quando disponível. Ainda não existe instância pronta para testar.
Usuário aceitou Oracle Linux9 disponível9.8. Tags minor não publicadas no
DockerHub;9-slim foi conferida por digest: /etc/os-release confirmou9.8.
Primeiro attempt NOT_PASSED preservado; diagnóstico novo passou uma vez,
container próprio removido, Desktop restaurado off. Evidência em
PHASE-9-ORACLE9-BASE-VALIDATION. Python3.11 ainda ausente na base.
Userland EL9 não certifica kernel RHEL: kernel medido WSL2 nesta máquina. Contrato/
sequência em PHASE-9-CONTAINER-TARGET-PLAN. Opção A aprovada explicitamente pelo usuário: D-119, contrato prospectivo
Docker local com excesso transitório/possível queda e restart manual.
Aceite B-2 muda só para este perfil; evidência/controles ainda pendentes.
CONTAINER-MEMORY-DECISION preserva garantias e riscos explícitos. C1 NOT_READY,
B-1/B-2/D-090 e SQL/produção continuam bloqueados.
Não voltar a pedir host como desconhecido; manter históricos anteriores.

**Estado local 2026-10-23 — corpo privado do job revisado:**
D-118, runtime/worker_job.py novo, compõe uma chamada typed e um encoder;
nenhum produto anterior ou ingresso operacional alterado. SQL64KiB UTF8,
max_rows da geração, saúde/deadline por fase e somente frame completo ou
categoria fechada. J6: interrupções são fatal, dono futuro deve parar/reap;
sem lifecycle/ledger/worker novo. J7 (igualdade de metaclass) reproduzida
vermelha e corrigida para identidade is.104 próprios/1.410 relacionados
finais verdes. Rodada Unicode anterior estourou40s; causa indeterminada,
isolado30,25s e repetição relacionada107,11s passaram sem ampliar teto.
Ruff/format/mypy3.11/3.14 em267 arquivos limpos, runtime só Windows3.11.3.
Pacotes A históricos antesJ7 e B finais separados;44 módulos iguais aos
fontes, sonda só adapter fechado, não job saudável/PG/OS. WORKER-JOB-VALIDATION
e J7 revistos pelo Claude2 sem bloqueador. Dois guards admitem só este
consumidor privado; guarda operacional continua ativa. Sem novo PG/DockerCLI,
worker processual, SQL, commit/push/deploy. B-1/B-2/D-090 e produção abertos,
C1 NOT_READY; destino ainda não identificado.

**Lote anterior 2026-10-23 — erros tipados e saúde revisados:**
D-117 implementada sob delegação, sem worker/SQL operacional. Classificador
privado só typed=True; legado preservado. Continuidade exige categoria
permitida e saúde libpq positiva pós-settle, não prova de rede/read-only.
100 testes novos; PG16.15 próprio:7.503 passed/20 skips de plataforma,
nenhuma falha/erro ou skip por DSN;17 obrigatórios passaram. Container/volume
removidos, Desktop restaurado off. Wheel/sdist:40 módulos iguais aos fontes,
contraprovas stale/checkout recusadas; sonda limitada. Ruff/format/mypy3.11/
3.14 em265 arquivos limpos; runtime só Windows3.11.3. Código, procedimento
e evidência WORKER-ERRORS-VALIDATION revistos pelo Claude2 sem bloqueador.
Domínios C1 continuam NOT_READY; B-1/B-2/D-090, SQL e produção seguem
abertos/recusadas. Destino ainda não informado; sem commit/push/deploy.
Próximo: domínio real/worker e integração sob gates próprios.

**Lote anterior 2026-10-23 — C1 implementado e revisado:**
D-116, reconciliação pura em runtime/domain.py, sem chamador operacional.
Registro fechado de perfis, custos IN/OUT, grandeza única e W>=cota; ambos
perfis atuais NOT_READY, sem atestado de SO ou custo físico. Três regressões
próprias e F1 (gap Windows) corrigidas antes do aceite do Claude2; P1 da
sonda corrigido antes do uso.113 novos/916 relacionados verdes, Ruff/format/
mypy3.11/3.14 em261 arquivos; runtime só Windows3.11.3. Wheel/sdist:39
módulos iguais aos fontes, stale/checkout recusados; sonda limitada.
Evidência DOMAIN-VALIDATION e cópia de pacote revisadas sem bloqueador.
Próximo: domínio real incluindo pai/auxiliares e worker, com prova própria.
Destino ainda não informado; não presumir OS/servidor/credencial.
B-1/B-2/D-090/SQL/produção seguem abertos; sem commit/push/deploy.

**Lote anterior 2026-10-23 — HELD III real revisado:**
Procedimento corrigido por S1/R1 e revisado antes de start/A/B/C únicos.
Externo READY/exit0; control_ok/imposed/imposed,37,141s/exit0,467 linhas
iguais e14 fontes intactas. Transportes/envelopes imutáveis persistem HELD;
rechecagem lógica conserva categoria/blocos como relatos do membro, só
pico/limites corroborados. Cleanup próprio e Desktop restaurado off.
Evidência HELD-RUN-VALIDATION e cópia linux-held-20261023.json revisadas
pelo Claude2 sem bloqueador para registro diagnóstico; plano consumido.
Nenhum código de produto/teste/helper mudou neste lote. Próximo C1:
DOMAIN-DESIGN revisado, D1/D2 e R1/R2 corrigidos no contrato antes de código;
reconciliação pura com D-112, sem backend/ativação. Implementação ainda ausente.
Destino de produção perguntado ao usuário, ainda não identificado.
B-1/B-2/D-090/SQL/produção seguem abertos; sem commit/push/deploy.

**Lote anterior 2026-10-22 — integração HELD I/II revisada, só fakes:**
novos tap stdlib/wrapper PID1 e observador próprio. I1 corrigido antes de
código: captura no container, E/replay só no host, sem packaging sob -S.
Artefatos transporte/envelope separados, imutáveis, com admissão/cleanup e
pins cruzados. Prazo final corrigido após regressão vermelha de121s.
Revisões e rerevisão sem bloqueador no escopo isolado.92 testes novos
(46 I+46 II),895 relacionados verdes; Ruff/format/mypy3.11/3.14 limpos,
runtime só Windows3.11.3. Nenhum DockerCLI, factory Linux ou carga neste lote.
Evidências HELD-ENTRY-VALIDATION e HELD-HOST-VALIDATION em docs/.
Fontes/medições anteriores preservadas. Próximo gate III: procedimento,
Desktop/contexto,14 hashes e comando/rodada única revisados antes de executar.
B-1/B-2/D-090/SQL/produção continuam abertos. Sem commit/push/deploy.

**Lote anterior — evidência HELD isolada revisada:**
novo docs/poc/loaded_memory_evidence.py,59 testes novos/803 relacionados
verdes com fakes; Ruff/format e mypy3.11/3.14 limpos (runtime só3.11.3).
Envelope versionado preserva bytes exatos/hash/tamanho do original e linhas
HELD; replay lógico revalida regras/observações sem inventar tempo ou origem.
T1 reproduzido primeiro e corrigido: erro delegado mantém categoria, só
falha própria da captura gera broken/fallback. Rerevisão sem bloqueador.
Evidência: `docs/PHASE-9-STAGE-8-HELD-EVIDENCE-VALIDATION.md`.
Sem integração/entrypoint/host real, DockerCLI ou nova carga; dez helpers e
artefatos anteriores preservados. Q1 da rodada anterior não é reescrita.
Próximo: desenho/revisão da integração e perfis/hashes/comando antes de carga.
B-1/B-2/D-090/SQL/produção seguem abertos. Sem commit/push/deploy.

**Rodada anterior — loaded-as128 real revisada:**
procedimento/comandos revisados antes de uma única execução. Preflight
externo READY/exit0 conferido; interno obrigatório passou antes de create.
Controle control_ok e privado/shared128 imposed; três inventários iguais467
linhas,25,671s/exit0, cleanup e integridade confirmados. Desktop já ativo foi
preservado; sem SQL/banco/produção. Evidência e limitação da linha HELD não
persistida em `docs/PHASE-9-STAGE-8-LINUX-LOADED-RUN-VALIDATION.md`.
Revisão sem bloqueador para registro diagnóstico, com Q1–Q3: classificação
depende do supervisor hashado; escopo/kernel/imports limitados; fd/readlink
só comprovados neste perfil. Próximo desenho deve persistir HELD validado.
Não fecha contenção total/B-2/D-090 ou B-1 fim a fim. Nenhum produto/src,
dependência ou configuração mudou.
Sem retry, outro escritor, commit/push/deploy ou tarefa nova.

**Lote anterior — observador externo do laboratório (somente fakes):** novo
docs/poc/run_linux_loaded.py implementado e revisado pelo Claude2 sem
bloqueador após corrigir B1 (evidência dos negativos fortes).
75 novos testes/744 relacionados verdes; Ruff/format e mypy3.11/3.14 limpos.
Só CLI/watchdog simulados e arquivos pequenos Windows3.11.3; nenhum DockerCLI,
processo de laboratório, preparação real ou carga executado. Supervisor59/669,
produtor/coletor136/610, núcleo puro179/474 e seis rodadas preservados.
Evidência: `docs/PHASE-9-STAGE-8-LINUX-LOADED-HOST-VALIDATION.md`.
Próximos gates: procedimento externo/estado do Desktop, preflight externo
com exits conferidos, abort sem retry, comando exato e rodada única revisados.
Sem mudança de src/produto/MCP legado, dependência, ambiente, commit/push;
B-1/B-2/D-090 gate2, SQL e produção continuam abertos.

**Medição anterior preservada — sexta rodada:**
identificada --run concluída depois de revisão de código/testes/plano.
Preflight externo READY/exit0 conferido antes do observador e interno
obrigatório READY, ps/imagem aprovados. Controle normal:465 linhas
auditadas, três imports completos, native_check/binary psycopg; _openssl.lib
associado só por identidade ao slot da âncora. Wrappers algorithms/modes
vieram de seus .py pelas regras antigas, sem nova exceção. Limited AS32
falhou IMPORT/etapa0/member73: **did_not_fit**, sem atribuir causa ao AS.
complete=true significa dois casos, não contenção/fit. Sem repetição,
aumento de cota, SQL ou serviço operacional. Evidência revisada sem bloqueador:
`docs/PHASE-9-STAGE-8-LINUX-IMPORTS-LIB-RUN-VALIDATION.md`.
295 testes puros relacionados e estáticos limpos; contexto null só no
nome exato, L1(a) sem promessa global read-free. Os cinco lotes anteriores
e suas fontes preservados; desvio de procedimento da quinta continua
**não aprovado**, sem repetição retroativa. Cleanup próprio confirmado,
inventário Docker vazio antes de stop; Desktop restaurado off.
Produto/src e MCP legado inalterados neste incremento. Sem cota observada,
job novo, segundo escritor, commit ou push. B-1/B-2/D-090/SQL PGWire/produção abertos.

**Autoridade vigente (2026-10-20):** avanço autônomo até a entrega em produção,
com revisão pelo Claude2, autorizado pelo usuário. Restrições de autorização
por lote abaixo são históricas; requisitos e gates continuam obrigatórios.
B-1 fim a fim, B-2 e D-090 gate 2 ainda abertos. Ver
`PRODUCTION-EXECUTION.md`; nenhuma etapa é fechada só por esta delegação.

B2-B2a (2026-10-20): cinco controles sintéticos executados após revisão;
SEC_COMMIT/SEC_RESERVE de 40 MiB sob cota privada de 32 MiB demonstram lacuna
compartilhada no perfil medido, com cleanup confirmado. Evidência revisada:
`PHASE-9-STAGE-8-B2-B2A-VALIDATION.md`. Nenhum gate de produto foi fechado.

D-113 (2026-10-20): representação imutável/validação limitada do resultado
no pai, núcleo puro local revisado pelo Claude2, sem importador operacional.
293 novos/916 relacionados aprovados; sonda pura de pacotes, não E2E.
`PHASE-9-STAGE-8-RESULT-VALIDATION.md`. Receiver/2F, worker/memória real/SSL,
B-1 fim a fim, B-2 e D-090 gate 2 seguem abertos.

D-114 posterior (2026-10-20): receiver/ownership/pin integrados internamente,
sem chamador operacional, worker ou SQL. Header antes da alocação, máximo
2F proporcional e descarte antes de unpin com prova complementar; 85 focados,
1.036 relacionados/306 antigos selecionados aprovados, revisão Claude2.
`PHASE-9-STAGE-8-RECEIVER-VALIDATION.md`, incluindo os contratos de quarentena,
saída não comprovada e canal quieto. Não fecha memória real/SSL/B-1/B-2/D-090.

D-115 posterior (2026-10-20): mesmo pipeline do adapter com API tipada
opt-in e encoder de saída já protegida, sem chamador operacional/worker.
408 relacionados e pacotes com sonda limitada PG16 aprovados; Ruff/format/mypy
3.11/3.14 em 243 arquivos. Revisado pelo Claude2 sem bloqueador isolado;
suíte integral PG16 **6.395 passed/20 skips de plataforma**, zero falhas/erros
ou skip DSN; integração tipada 12/12. Evidência:
`PHASE-9-STAGE-8-ENCODER-VALIDATION.md`. Não fecha B-1/B-2/D-090 ou libera SQL.

Diagnóstico AS posterior (2026-10-20): harness/testes isolados em `docs/poc/`
e `tests/test_linux_as_{diagnostic,observer}.py`; 46 testes puros, estáticos
em 245 arquivos, quatro casos Linux/WSL2 executados uma vez após revisão.
Recusa privada/shared sob AS32 MiB e cleanup confirmados; não é contenção
total, worker, imposição dos 192 MiB externos ou certificação de plataforma.
`PHASE-9-STAGE-8-LINUX-AS-VALIDATION.md`. B-1/B-2/D-090 continuam abertos.

**Estado:** Etapa 1 documental concluída e aprovada em 2026-09-22; Etapa 2
concluída; Etapa 3 (registry multi-datasource e lifecycle) implementada
localmente em 2026-09-23, ativada somente pelo composition root (D-087). A
Etapa 4 (Admin API v2 de datasources) foi autorizada e implementada localmente
em 2026-09-24, sem push (D-092–D-096). A Etapa 5 (UX v2 somente leitura) foi
publicada em `4d5b78f`; a Etapa 6 (CRUD visual) foi aprovada pelo usuário
(D-103–D-106) e publicada em `5115a75`. A Etapa 7 está parcial: verificador em
processo filho (D-107, `e9eb01a`) e fila administrativa, barreira e leitura
selada (D-108, fechamento aprovado e publicação autorizada em 2026-10-07;
estado confirmado pelo Git). Em 2026-10-08 entrou a terceira exceção
estreita, a D-109: só peças puras do startup (framing, credencial, SCRAM-SHA-256
e -PLUS, channel binding), locais, sem commit e em revisão. Em 2026-10-09 o
usuário autorizou explicitamente a integração do listener (D-110), sem SQL,
deploy nem liberação de produção, em lotes revisados; existem o lote 1
(settings e preparo do `SSLContext`), o lote 2 (transporte e driver de
startup/autenticação), o lote 3 (listener) e o lote 4 (composição interna no
composition root; o `main` recusava a ativação até 2026-10-14, e em
2026-10-15 foi autorizada só localmente a ativação sobre catálogo existente,
sem Admin/UI e sem SQL, implementada localmente e medida só no Windows,
nos runtimes legado e moderno temporário (3.14.8), sem POSIX, e fechada num
commit local aprovado em 2026-10-16; depois, em revisão local, a correção dos
4 `union-attr` de `destination.py` e o desenho-proposta
`docs/PHASE-9-STAGE-8-DESIGN.md`, não aprovado), locais e sem commit (estado
anterior a esse fechamento), com os
gates finais do lote 4 medidos em 2026-10-12 e o gate de runtime moderno
medido em 2026-10-13, só no Windows com CPython 3.14.8 (lotes A–C). A
resolução limitada do hostname do bind foi implementada localmente em
2026-10-14 e medida no Windows, e o usuário aprovou fechar esse trabalho
validado num commit local, sem push (o "sem commit" acima é o estado
anterior). Ativação operacional e
as Etapas 8–12 continuam não iniciados; nada disso está liberado para
operação real.

**Atualização (2026-10-19):** o desenho da Etapa 8 foi aprovado em
2026-10-18, e o usuário autorizou só B-1 (snapshot/equivalência), sem worker
ou SQL de cliente, commit/push. O núcleo opt-in interno está implementado
(D-111; `PHASE-9-STAGE-8-B1-VALIDATION.md`); nenhum chamador operacional o
habilita. O lote e a D-111 foram aprovados pelo usuário em 2026-10-19, sem
ampliar a autorização. Isso não satisfaz o gate normativo de saída da Etapa 8: B-1 fim a
fim, B-2 e D-090 gate 2 continuam abertos. O estado anterior de desenho não
aprovado permanece acima como histórico.

Incremento autorizado em 2026-10-19: prova de equivalência em outro processo,
implementada somente em testes, sem integração operacional ou SQL de cliente,
com revisão pelo Claude2 e sem commit/push. Evidência:
`PHASE-9-STAGE-8-B1-PROCESS-VALIDATION.md`. Nenhum gate normativo foi fechado.
O usuário aprovou explicitamente esse incremento em 2026-10-19; a aprovação
não amplia a autorização nem autoriza commit/push.

Preparação B-2 autorizada em 2026-10-19, somente documental e com revisão
pelo Claude2: `PHASE-9-STAGE-8-B2-PLAN.md`. Em seguida, autorizado só B2-A,
§4: harness temporário fora do checkout e execução após revisão do Claude2.
Não fecha gate ou autoriza produto, banco/Docker, worker integrado,
SQL de cliente, commit/push ou os demais lotes.
B2-A executado no Windows 3.11.3: seis controles e 36 casos com cleanup
confirmado, mas pico excedido nos 12 job-only. Diagnóstico não é gate de
contenção aprovado; `PHASE-9-STAGE-8-B2-A-VALIDATION.md` revisada tecnicamente,
com o registro aprovado pelo usuário em 2026-10-19. O aval não fecha B-2
nem autoriza outros lotes, commit/push ou produção.

Autorização posterior em 2026-10-19: apenas preparação do plano B2-B de
contenção/orçamento global com o Claude2. Ver
`PHASE-9-STAGE-8-B2-B-PLAN.md`, proposta não aprovada e sem implementação,
teste novo, pressão, harness, worker ou SQL. Não fecha B-2/D-090 nem autoriza
commit/push ou produção.

Depois, em 2026-10-19, autorizado somente B2-B1: núcleo lógico de reservas
e testes de estado/ordens, revisados pelo Claude2 antes de fechamento.
Implementação local isolada em `runtime/budget.py`, sem chamador operacional;
D-112 e `PHASE-9-STAGE-8-B2-B1-VALIDATION.md`, revisão técnica concluída sem
bloqueador no núcleo isolado; fechamento e D-112 aprovados pelo usuário
em 2026-10-20, sem ampliar a autorização. Não é contenção
real nem gate de saída da Etapa 8; sem integração, worker, SQL, pressão ou
commit/push. B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.

**Fonte normativa:** [PHASE-9-SPEC.md](PHASE-9-SPEC.md). A matriz cobre todas
as Etapas 2–12 e distingue requisito, etapa responsável, prova obrigatória e
estado atual. “Planejada” não é evidência de execução: cada etapa só pode ser
fechada com os artefatos e números medidos no seu próprio registro de validação.

## Requisitos e evidência verificável

| ID | Requisito normativo | Seções | Etapa(s) | Evidência obrigatória | Estado |
|---|---|---:|---:|---|---|
| F9-001 | IDE usa host/port/dbname/user/password do Gateway | 1, 4.1–4.2 | 7–10 | conexão real nos quatro clientes certificados, sem conexão direta ao destino | planejada |
| F9-002 | MCP permanece e compartilha o pipeline seguro | 2, 10–11 | 3, 8, 11 | paridade de masking, read-only, timeout e erros entre MCP e PGWire | Etapa 3: sessões de datasource usam o mesmo `execute_validated` e `run_audited` do MCP, provado contra PostgreSQL 16; paridade com PGWire pendente (8, 11) |
| F9-003 | Somente SELECT, com defesa também no PostgreSQL | 2, 5.4, 12 | 3, 8–10 | validator, sessão read-only, tentativas de escrita e funções perigosas | Etapa 3: cada sessão verifica read-only/timeout/proveniência; escrita recusada pelo validator e pelo PostgreSQL; PGWire pendente (8–10) |
| F9-004 | Alias fechado resolve datasource, nunca destino informado pelo cliente | 4.1, 6.1 | 2–4, 7 | aliases inválidos, desconhecidos, desabilitados e enumeração bloqueados | Etapa 4: alias validado no schema, imutável (`IMMUTABLE_FIELD`), conflito sem ecoar o alias, destino só por campos administrativos; PGWire pendente (7) |
| F9-005 | Autenticação Gateway separada da upstream | 4.2–4.3, 5.3 | 2, 7 | SCRAM-SHA-256, proof não reutilizável, credencial upstream nunca retornada | Etapa 7 (D-109), parcial: troca SCRAM-SHA-256/-PLUS pura, vetor RFC 7677 e interop libpq num harness de teste (`PHASE-9-STAGE-7-VALIDATION.md`, §1.5); listener e upstream pendentes |
| F9-006 | Um principal operacional; sem RBAC implícito | 4.2, 8–9 | 4, 6, 7 | inventário fechado de identidades e ausência de autorização por alias | Etapa 4: a v2 usa o mesmo token administrativo, sem identidade nova nem autorização por alias; UI da Etapa 6 implementada; PGWire de produção pendente (7) |
| F9-007 | TLS obrigatório fora de loopback | 5.1–5.2 | 7 | bind externo, SSLRequest, downgrade, certificado/chave inválidos | Etapa 7 (D-110, lote 1), parcial: settings exigem cert e chave fora de `127.0.0.1`/`::1` e o preparo do `SSLContext` recusa certificado/chave inválidos (`PHASE-9-STAGE-7-VALIDATION.md`, §1.6); bind externo, SSLRequest e downgrade sobre socket pendentes |
| F9-008 | Settings PGWire estritos e opt-in | 5.1, 11 | 7 | matriz de valores brutos; falhas antes de bind, store e MCP | Etapa 7 (D-110, lote 1), parcial: matriz de valores brutos e opt-in `1` bruto medidos sem efeito (§1.6); falha antes de bind, store e MCP depende da integração, pendente |
| F9-009 | Simple query no subconjunto seguro | 5.3–5.5 | 8 | psql/psycopg, framing adversarial, masking e CommandComplete | planejada |
| F9-010 | Extended query e parâmetros por sessão | 5.3–5.4 | 9 | Parse/Bind/Describe/Execute/Close/Sync, JDBC e prepared statements | planejada |
| F9-011 | Cancelamento isolado por sessão | 5.3, 7, 12 | 9 | CancelRequest válido, inválido e cruzado, sem enumeração | planejada |
| F9-012 | Catálogo mínimo de IDE sem allowlist genérica | 5.4, 12 | 10 | snapshots das queries dos quatro clientes e contraprovas de bypass | planejada |
| F9-013 | Protocolo/formato não suportado falha fechado | 5.3–5.5, 12 | 7–10 | frames malformados, máquina de estados, tamanhos e UTF-8 | planejada |
| F9-014 | Tipos/metadados não expõem proveniência | 5.5, 13 | 8–10 | RowDescription, OID/typmod, NULL, duplicatas e colunas mascaradas como texto | planejada |
| F9-015 | Limite de linhas observável sem dado extra | 5.5, 14.2 | 8 | NOTICE fixo, linha N+1 descartada antes de masking e sem leakage | planejada |
| F9-016 | Catálogo persistente multi-datasource, fechado e autenticado | 6.1–6.2 | 2 | roundtrip, schema, metadata tamper, truncamento e integridade | implementada na Etapa 2; evidência local |
| F9-017 | Segredo upstream write-only e cifrado por AEAD | 4.3, 6.2, 13 | 2, 4, 6 | AES-256-GCM, nonce único, tamper, transplant e canários de leakage | implementada na Etapa 2; Etapa 6: senha só em campo mascarado, nunca preenchida nem relida, apagada ao concluir/descartar/sair; canários das senhas digitadas ausentes de DOM, storage, URL, logs e auditoria (`datasources.spec.js`) |
| F9-018 | Chave-mestra externa e rotação explícita | 5.1, 6.2 | 2, 12 | chave ausente/errada, rotação, ausência de fallback e nenhum plaintext | implementada na Etapa 2; evidência local |
| F9-019 | Migração do DSN único explícita e reversível | 6.3, 10, 17 | 2, 11 | importação, restart, desligamento explícito e retorno real ao legado | migração explícita implementada; rollback/runtime pendentes |
| F9-020 | Registry por alias/generation com refcount | 7, 11 | 3 | concorrência, fechamento único, aposentadoria e isolamento | implementada na Etapa 3; evidência local |
| F9-021 | Conexão upstream por sessão e limites | 5.1, 7, 11–12 | 3, 7–10 | sessões máximas, por-datasource, idle, slow clients e cleanup | Etapa 3: conexão por sessão, limites globais/por datasource e cleanup implementados; idle e slow clients pendentes (7–10) |
| F9-022 | Candidato testado antes de persistir/publicar | 6.3, 7–8 | 2–4 | falhas de conexão/capability sem efeito em bytes, runtime ou revision | Etapas 3–4: coordenador e rotas v2 provados, inclusive contra PostgreSQL 16 real |
| F9-023 | Datasource habilitado inválido falha startup | 7, 11 | 2–3 | subprocesso com zero Admin HTTP, PGWire ou MCP publicados | implementada na Etapa 3 pelo composition root (D-087); ativação por settings de processo pendente (7) |
| F9-024 | Admin API v2 não quebra v1 | 8, 11 | 4 | inventário v1 imutável, v2 fechado e regressão byte a byte | implementada na Etapa 4: inventários literais, comparação sonda a sonda com e sem v2, v1 sem importar a v2 |
| F9-025 | Concorrência otimista por datasource | 6.1, 8 | 4, 6 | revision, conflito, busy, durability e uma publicação por vencedor | Etapa 4: revision por datasource sob o lock, um vencedor por revision, busy, falha certa/incerta; Etapa 6: duas sessões, um `409` sem retry, rascunho preservado sem rebase, `busy`/`blocked`/`uncertain` distintos na UI |
| F9-026 | Teste de conexão não publica runtime | 2, 7–8 | 4, 6 | identidade, digest, revision, arquivo e registry inalterados | Etapa 4: rascunho e persistido sem efeito em bytes, revisions, `last_test`, registry e candidatos; Etapa 6: teste do rascunho e do gravado pela UI, sem carimbo de revision e sem bloquear escritas mesmo com resultado desconhecido |
| F9-027 | UI não executa SQL nem mostra resultados | 3.1, 8–9 | 5–6, 12 | inventário, AST, rede e chamadas fechadas; contraprovas positivas | Etapa 5: v2 da UI só lê (4 GETs sob `/admin/v2/`, verificados no Python, no verificador público e no transporte); sem editor SQL, resultado, POST/PUT/DELETE novo ou campo de senha; Etapa 6: só as nove escritas da D-093 (inventário exato), ainda sem editor SQL, consulta ou resultado |
| F9-028 | UX v2 possui dashboard, lista, wizard e detalhe | 9 | 5–6 | screenshots aprovados, E2E e estados de erro/concorrência | Etapa 5: painel, lista com busca, detalhe com abas e protótipo de passos implementados e capturados (`docs/ux-v2/`); Etapa 6: assistente real, edição, troca de senha, teste, habilitar/desabilitar, remoção e política, com capturas de rascunho, revisão, conflito, remoção e resultado desconhecido |
| F9-029 | Token, segredos e drafts continuam voláteis | 4.1, 9.1–9.3 | 5–6 | lifecycle, BFCache, storage, URL, DOM, logs e leakage | Etapa 5: token só em memória, tema sem storage, BFCache/pagehide/logout provados nos três engines; rascunhos de datasource inexistentes nesta etapa; Etapa 6: rascunhos e senha só em memória, descartados ao sair, ao fechar com confirmação e no logout |
| F9-030 | Acessibilidade em 320 px, 200% e reduced motion | 9.2, 14 | 5–6 | três browsers, teclado/foco e revisão manual registrada | Etapa 5: 320 CSS px, 640 px (200%), movimento reduzido, temas claro/escuro, contraste AA medido e teclado/foco nos três engines; Etapa 6: formulários com rótulo, ajuda e erro ligados ao campo, foco preso no diálogo, Esc com confirmação, reordenação por teclado com foco preservado, contraste AA e reflow nos diálogos |
| F9-031 | Nenhuma dependência ou recurso externo na UI | 9.2–9.3, 14 | 5–6, 12 | CSP, rede, pacote instalado e inventário de dependências | Etapa 5: sem recurso externo; CSP/mesma origem mantidas; vocabulário privado da v2 por token (D-099); pacote instalado sem Node verificado |
| F9-032 | MCP aceita alias opcional sem quebrar `sql` | 10 | 11 | clientes antigos, novo cliente e default explícito | planejada |
| F9-033 | MCP não enumera aliases nem altera catálogo | 10 | 11 | schema/tool único, erros fixos e AST de separação de planos | planejada |
| F9-034 | SSRF e DNS rebinding no destino são bloqueados | 6.1, 12 | 2, 4, 12 | loopback, link-local, multicast, metadata cloud e resolução mutável | Etapa 4: destinos proibidos e DNS trocado recusados pelas rotas, sem ecoar o destino; resolução com prazo (D-092); revisão final pendente (12) |
| F9-035 | Nenhuma informação sensível em observabilidade | 2, 6.2, 13 | 2–12 | canários de senhas, chave, SQL, destino, ciphertext, nonce e célula | redaction da Etapa 2 implementada; Etapa 6: senhas digitadas e segredo upstream ausentes de logs e auditoria `datasource_*` no harness de escrita; cobertura das etapas seguintes pendente |
| F9-036 | Lifecycle ordenado das três fronteiras | 11 | 3–12 | falha em cada passo, bind confirmado, drain e shutdown sem órfãos; limite DNS antes da Admin v2; limite da verificação pós-conexão de candidatos antes da ativação da v2 pelo operador (7); limite de validação/masking locais antes de novo ingresso SQL (8, 11); nada abandonado | Etapas 3–4: passos 3–7 da §11, drain, shutdown e limite efetivo de DNS (D-092, shutdown com resolução em voo provado). Etapa 7 parcial: gate pós-conexão entregue na D-107, com limites de recolhimento documentados; fila/barreira na D-108. **Em aberto:** validação/masking locais (gate 2, Etapas 8 e 11), listener e lifecycle PGWire; operação real não liberada |
| F9-037 | Riscos F-01 a F-11 não regridem | 2, 5, 12 | 8–12 | suíte de segurança completa por datasource e função/catálogo | planejada |
| F9-038 | Pacote instalado funciona sem checkout/Node | 14 | 12 | wheel e sdist isolados, sem fallback ao checkout ou Node | planejada |
| F9-039 | Rollback volta ao modo legado sem fallback silencioso | 6.3, 10–11, 17 | 11–12 | restart com PGWire/store desligados e MCP legado funcionando | planejada |
| F9-040 | Compatibilidade declarada é certificada, não universal | 5.3, 14 | 10, 12 | versões fixadas, tabela de suporte e recusa fora do subconjunto | planejada |

## Cobertura por etapa

| Etapa | Entrega normativa | IDs principais | Gate de saída verificável | Estado |
|---:|---|---|---|---|
| 2 | modelo, store autenticado/cifrado e migração | F9-016–019, F9-022–023, F9-034–035 | testes AEAD/metadata, âncora de replay, atomicidade, SSRF, leakage e subprocesso fail-closed | concluída; F9-022–023 integrados na Etapa 3 |
| 3 | registry multi-datasource e lifecycle | F9-002–003, F9-020–023, F9-036 | concorrência, generations, refcount, drain, fechamento único e isolamento | implementada localmente; evidência em `PHASE-9-STAGE-3-VALIDATION.md` |
| 4 | Admin API v2 de datasources | F9-004–006, F9-022, F9-024–026, F9-034, F9-036 | auth/CSRF, revisões, teste sem publicação, v1 intacta, destino validado e resolução DNS com limite efetivo | implementada em 2026-09-24 e publicada em `c37be36`; evidência em `PHASE-9-STAGE-4-VALIDATION.md` |
| 5 | UX v2 somente leitura | F9-027–031 | screenshots, a11y, token/draft lifecycle, CSP e três browsers fixados | publicada em `4d5b78f`; refinamento visual (D-101, D-102) e capturas aprovados pelo usuário em 2026-09-28; evidência em `PHASE-9-STAGE-5-VALIDATION.md` |
| 6 | CRUD visual de datasources e policies | F9-016–019, F9-025–031, F9-035 | segredo write-only, rotação, concorrência, confirmação destrutiva e sem SQL/resultados | autorizada em 2026-09-28; implementada e aprovada pelo usuário em 2026-09-30 (D-103–D-106, capturas, correção por Esc); publicada em `5115a75`; evidência em `PHASE-9-STAGE-6-VALIDATION.md` |
| 7 | PGWire startup, TLS e autenticação | F9-001, F9-005–008, F9-011, F9-013, F9-021, F9-036 | harness binário, SCRAM, TLS externo, limites, erro sanitizado e lifecycle; limite efetivo da verificação pós-conexão de candidatos antes de ativar a Admin v2 pelo operador, sem abandonar thread, processo ou conexão | parcial: verificador em processo filho (D-107) e fila/barreira/leitura selada (D-108) validados; peças puras de framing/SCRAM/binding da D-109 locais e em revisão; D-110 autorizada em 2026-10-09, com o lote 1 (settings e preparo TLS) local e sem commit; listener, driver, integração e autenticação de produção pendentes; evidência em `PHASE-9-STAGE-7-VALIDATION.md` |
| 8 | simple query e masking | F9-002–003, F9-009, F9-014–015, F9-036–037 | psql/psycopg, PostgreSQL 16 real, SELECT-only, masking, truncamento e limite efetivo do processamento local | somente núcleo B-1 opt-in local aprovado (D-111); worker, SQL e gate de saída não entregues; B-1 fim a fim/B-2 abertos |
| 9 | extended query, parâmetros e cancelamento | F9-010–011, F9-013–015, F9-021, F9-036–037 | JDBC/prepared statements, Sync, formatos, CancelRequest e isolamento | não iniciada |
| 10 | catálogo seguro e quatro IDEs | F9-001, F9-012–015, F9-040 | navegação real, snapshots fechados, tipos e matriz certificada | não iniciada |
| 11 | MCP multi-datasource e migração legada | F9-002, F9-004, F9-019, F9-032–033, F9-036, F9-039 | clientes antigos, alias/default, rollback real, zero enumeração/configuração e limite do processamento local antes do novo ingresso | não iniciada |
| 12 | pacote, revisão adversarial e fechamento | F9-007, F9-018, F9-027–031, F9-034–040 | wheel/sdist, todos os gates, canários de leakage, browsers e critérios da §17 | não iniciada |

## Rastreabilidade das decisões D-065–D-076

| Decisão | Tema | Seções normativas | Etapas que provam |
|---|---|---|---:|
| D-065 | façade segura, não proxy | 1–2, 5.3–5.5, 7, 12 | 7–10 |
| D-066 | alias em `dbname` | 4.1, 6.1, 7, 10 | 2–4, 7, 11 |
| D-067 | identidades separadas/SCRAM | 4.2–4.3, 5.3, 12 | 2, 6, 7 |
| D-068 | principal único, sem RBAC | 4.2, 8–9 | 4, 6, 7 |
| D-069 | AEAD, catálogo autenticado e replay | 6.1–6.3, 12–13 | 2, 6, 12 |
| D-070 | TLS fora de loopback | 5.1–5.3, 8, 11 | 7, 12 |
| D-071 | conexão por sessão | 7, 11–12 | 3, 7–10 |
| D-072 | clientes certificados | 5.3–5.5, 14 | 7–10, 12 |
| D-073 | UX v2 segura/local | 2, 8–9, 12–14 | 4–6, 12 |
| D-074 | MCP stdio e alias posterior | 2, 10–11 | 8, 11–12 |
| D-075 | rollback legado explícito | 6.3, 10–11, 17 | 2, 11–12 |
| D-076 | fail-closed no startup | 5–8, 11–14 | 2–4, 7, 12 |

## Rastreabilidade das decisões de implementação D-077–D-086

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-077 | `cryptography==50.0.1`, AESGCM/HKDF/HMAC | `src/maskgw/datasource/crypto.py`; validação de dependência |
| D-078 | JSON canônico, schema fechado, digest SHA-256 | `crypto.py`, `store.py`; roundtrip/tamper |
| D-079 | envelope v1, nonce de 12 bytes e AAD por ID/campo/revision | `crypto.py`; cifra, rotação e chave errada |
| D-080 | âncora em diretório separado, sem arquivo comum confiável | `store.py`; replay/transplant e filesystem |
| D-081 | journal old/new e recuperação old/old, new/old, new/new decidida antes de qualquer escrita; erro pós-replace incerto | `store.py`; pontos de crash de escrita, inicialização e rotação; abertura com chave errada sem escrita |
| D-082 | rotação explícita sem fallback; determinação e recuperação explícitas com as duas chaves; conclusão só após remover backups da chave anterior | `CatalogStore.rotate_master_key`, `inspect_master_key_rotation`, `recover_master_key_rotation`; sete limites de crash × chave antiga/nova/errada, idempotência e chaves inválidas |
| D-083 | locks, temporários, backups, replace, fsync e limpeza seletiva; remoção verificada dos backups após o commit da rotação | `store.py`; testes de lock/recuperação, falha/retomada da remoção, remoção sem efeito, nomes desconhecidos, diretórios e symlinks |
| D-084 | validação SSRF e conjunto DNS fixado | `destination.py`; metadata e rebinding |
| D-085 | ausência, corrupção e chave inválida falham fechadas | `CatalogStore.open`; testes de tamper/anchor/key |
| D-086 | migração DSN explícita, em memória e não destrutiva | `migration.py`; teste byte a byte do legado |

## Rastreabilidade das decisões da Etapa 3 D-087–D-091

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-087 | `build_application(datasource_catalog=...)`; import tardio do catálogo | `test_datasource_bootstrap.py`: legado sem módulo de catálogo, ordem de startup, subprocesso fail-closed |
| D-088 | `effective_database_settings` (mínimo entre policy e limits) | `test_datasource_runtime_service.py` |
| D-089 | `DatasourceRegistry`, `DatasourceGeneration`, `DatasourceLease`, reservas | `test_datasource_registry.py`: gerações, limites, isolamento e concorrência |
| D-090 | shutdown em duas fases, `PostgresAdapter.cancel` | `test_datasource_registry.py`, `test_datasource_bootstrap.py` e cancelamento real em `test_datasource_runtime_integration.py` |
| D-091 | `DatasourceRuntimeService`, `build_candidate` | `test_datasource_runtime_service.py` e `test_datasource_runtime_integration.py` |

## Rastreabilidade das decisões da Etapa 4 D-092–D-096

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-092 | `maskgw/datasource/resolver.py`, default de `resolve_destination` | `test_datasource_resolver.py`, shutdown com DNS lento em `test_admin_v2_lifecycle.py`, integração real |
| D-093 | `maskgw/admin/http/v2/`, `build_router(datasources=...)`, `_build_admin_http` | `test_admin_v2_http.py`: inventário, v1 byte a byte, fronteira, schema fechado e leituras sem segredo |
| D-094 | `DatasourceRuntimeService`: revision por datasource, mutação/confirmação sob lock, probe, teste de desabilitado, política compilada | `test_datasource_service_v2.py`, `test_admin_v2_concurrency.py`, `test_admin_v2_http.py` |
| D-095 | `admin/http/v2/errors.py`, `audit/datasource.py`, `AuditLog.record_datasource_admin` | `test_admin_v2_audit.py` e auditoria nos testes HTTP |
| D-096 | ausência da rota de default do MCP | inventário literal em `test_admin_v2_http.py` |

## Rastreabilidade das decisões da Etapa 5 D-097–D-100

| Decisão | Implementação verificável | Evidência |
|---|---|---|
| D-097 | `protocol.py`/`protocol.js` formato 2, `console`, `transport.js` (v2 só GET, identidade, 404/503), `screen.js` | `surface.test.js`, `test_phase8_final_inventory.py` (selos v1 e da Etapa 5), `console.spec.js` |
| D-098 | `frontend/tools/screenshots.js`, `docs/ux-v2/` | 57 capturas de fixture sintética (após o refinamento visual) e conjunto "antes" em `docs/ux-v2/antes/`; reporter sem screenshot |
| D-099 | `generate.py` (`vocabulary-tokens.json`), `inspect.js` por token | `surface.test.js`, `package.spec.js`, build com inspetor limpo |
| D-100 | shell único, tema em memória, toolchain fixada | `reading.spec.js`, `console.spec.js` nos três engines |
| D-103 | `protocol.py` (`V2_WRITES`, operações próprias), `protocol.js`, `transport.js` (`submit`, `place`) | `test_phase8_final_inventory.py` (selo e inventário da Etapa 6, espelho de `V2_WRITE_ROUTES`), `test_admin_ui_resources.py`, `surface.test.js`, `protocol.test.js` |
| D-104 | `console.actions`, `outcomes`, `reasons`, `latest`; `console.py`; `presentation.py` (padrão não-ID) | `test_admin_ui_actions.py`, `surface.test.js` |
| D-105 | `desk.js` (uma escrita, rascunho volátil, revisão, estados), `screen.js` | `datasources.spec.js` nos três engines, com PostgreSQL 16 e pacote instalado |
| D-106 | `desk.js` (erros ligados, foco, diálogo), CSS | `datasources.spec.js` (teclado, 320/200%, contraste, temas) |

## Gates comuns e limites desta matriz

- PostgreSQL 16 real em todos os gates de integração; `MASKGW_TEST_DSN` deve
  ser usado sem imprimir seu conteúdo, e nenhum skip por ausência de DSN é
  aceitável.
- Ruff, format check, mypy strict, `git diff --check`, Node/checkJs, testes
  Node, builds determinísticos e browsers fixados entram somente nas etapas em
  que a especificação os exige; suas versões e resultados devem ser medidos,
  não herdados de evidência histórica.
- No Windows, a suíte Python usa a pilha de thread de 64 MiB já documentada;
  o teste adversarial não pode ser deselected, skipped ou xfailed.
- Nenhum finding pode virar skip/xfail. Skips exclusivamente de plataforma
  devem ser separados e explicados na evidência da etapa.
- A matriz não autoriza as Etapas 4–12. A evidência executável das Etapas 2 e
  3 está em `docs/PHASE-9-STAGE-2-VALIDATION.md` e
  `docs/PHASE-9-STAGE-3-VALIDATION.md`; os resultados históricos da Fase 8
  continuam exclusivamente em sua própria evidência e não são reatribuídos.
