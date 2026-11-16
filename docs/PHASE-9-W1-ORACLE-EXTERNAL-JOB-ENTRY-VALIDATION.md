# W1: entrada S com SDK falso — validação de 2026-11-16

Claude2 programou somente na sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço medium. Root leu todos os oráculos, os deltas e toda a fonte antes de executar QA. Este aceite é do componente sob SDK falso, não da entrada nativa ou do Gateway em produção.

## Bytes finais

| Artefato | SHA-256 | Tamanho |
|---|---|---|
| `docs/poc/oracle9_w1_external_job_entry.py` | `b4826e0b649e37b485b4ca065e225e1103cbd41e19836c2ac95ca78172a62e18` | 433 linhas; 16.809 bytes |
| `tests/test_oracle9_w1_external_job_entry.py` | `1835ba817343cea1076fa95ec3add21d0828a074bfb8ac968f1e2dd8d0ef3fad` | 1.878 linhas; 76.003 bytes |

Fonte e teste são integrados juntos. O módulo define tipos e funções; não traz main, park, argv, perfil de P ou ligação de stdin/stdout reais. `load_adoption` verifica e executa os mesmos bytes do N-S pinado. `run_entry` usa apenas o Owner público: setup, entrada limitada até EOF, adoção, ack único com entrega local, start e supervisão com orçamento compartilhado. Resultado RETAIN mantém a custódia no chamador; não demonstra que um main futuro respeitou a obrigação até a saída física de S.

## Oráculos, correções e RED

1. A chamada3963 entregou o primeiro teste de1.457linhas,25bf694e. Root leu tudo e mediu179casos coletados; a estimativa de300do programador não foi usada. Cinco sanidades do fake passaram. Ruff, format e mypy apontaram reparos no próprio teste.
2. Root encontrou um oráculo de EOF mais estreito que o contrato: ele exigia outro turno mesmo quando, depois da última leitura e do inventário, available fresco já retornava None. Traços do Owner público com SDK falso comprovaram close None+CLOSED em4waits/4reads para3*MAX_READ+5bytes e em1wait/1read vazio seguido de EOF novo. A fonte da entrada ainda não existia. Não foi medida semântica física do kernel.
3. Os dois classificadores de import aceitavam uma atribuição que chamava função para escrever por builtins importado. Root aplicou os oráculos reais a fixtures sintéticos de import, nunca a uma entrada substituta: benigno aceito sem escrita, impuro aceito com marker controlado. Esse defeito do teste foi reproduzido antes da correção.
4. Claude2 corrigiu só o teste na chamada90134. Root leu todo o delta de686linhas;66definições alheias ficaram idênticas em AST. Os testes de drenagem passaram a aceitar EOF novo na mesma fatia, mantendo orçamento/limites e acrescentando o negativo real com5bytes ainda no buffer. Os classificadores estático/dinâmico foram reparados, com restauração das traps antes de diagnóstico do pytest. Dataclass/Enum legítimos foram preservados.
5. As mesmas contraprovas recusaram a família impura sem marker e aceitaram o fixture inerte. Ruff, format e mypy win32 3.11/3.14 passaram. RED193 medido e congelado ANTES de pedir fonte:17sanidades PASS e176falhas exclusivamente pela ausência da implementação, zero erros/skips/deseleções,1,609s. Cada mensagem foi conferida; nenhum erro de fixture ou collection foi contado como RED funcional.
6. A chamada3267 terminou exit1/API429, service is_errorTrue, DEPOIS de gravar a fonte b4826e0b. O retorno relatou limite até16h de São Paulo, inferido como2026-11-16T19:00:00Z, ainda não observado. Root não retomou nem trocou modelo/conta. Confirmou zero chamadas da sessão, leu TODAS433linhas e verificou os bytes finais e o teste congelado antes da QA.

Os dois primeiros serviços terminaram success/is_errorFalse, sem denials, e foram recuperados; o terceiro tem a interrupção preservada como tal. Um status de serviço não foi usado para afirmar qualidade do código: a fonte gravada passou pela revisão e pelos gates próprios do Root.

## Gates medidos nos bytes finais

| Gate | Resultado |
|---|---|
| Teste próprio completo | 193 PASS; zero falhas/erros/skips/deseleções; 10,590s |
| Matriz relacionada,22arquivos | 2.514 PASS, incluindo os193próprios; zero falhas/erros/skips/deseleções;58,138s |
| Ruff src/tests | PASS |
| Ruff PoC contratado | PASS E9,F63,F7,F82 |
| Formatação | PASS,379arquivos |
| Mypy strict win32, alvo3.11 | PASS,379arquivos |
| Mypy strict win32, alvo3.14 | PASS,379arquivos; somente estático |
| Probes puros dos guards reais | 16casos de domínio de available/accounting PASS |

A matriz reutiliza os18arquivos relacionados do fechamento C0, os dois testes de Kernel do backend/adaptador e os testes N-S/entrada. Seleção por caminhos explícitos, sem filtro de deselection. QA direta em processo de desenvolvimento, sem wrapper de pilha64MiB. Esses resultados são de SDK falso; não são a suíte integral de produto com PostgreSQL ou uma execução de DLL/job/processo/thread/loop de produto.

## Revisão de fonte e alcance

Root conferiu a chamada available FRESCA após `_drain_once` e o inventário positivo, inclusive com EOF cacheado. O fato de saída fica retido; um wait False posterior causa RETAIN. Os guards validam os domínios exatos de wait/read/available/exit_code/accounting/members; accounting posterior aceita total1ou2 com zero ativos e membros vazios. Tipo/resultado inesperado do adopt retém sem inventar ack. Todo close exige None+CLOSED. O único IO depois de primeiro controle é a tentativa única de ack CONTROL prevista para REFUSED_CONTROL, sem SDK posterior. Não há leitura de ledger pelo chamador, global de Owners, retenção de payload de P ou emissão de diagnóstico em stdout/stderr.

As lacunas dinâmicas foram mantidas explícitas: o SDK fiel com cache de EOF não distingue todas as chamadas available, nem produz tipos impossíveis nos retornos públicos do backend pinado. Root conferiu os guards e a ordem na fonte e aplicou16probes aos guards puros reais; não substituiu Owner ou funções de produto para fabricar cobertura. Isso não prova causalidade, EOF físico, quitação global ou proteção contra um chamador privilegiado que altere o carrier/globais confiados.

N-S465/teste37a, backend10c, adaptereaeb, C0/qualificador e antigos fontes/testes/pins permaneceram fixos. Aplicação, UI, dependências e empacotamento não mudaram; frontend, pacotes e PostgreSQL não foram repetidos. Snapshots, XMLs, respostas CLI e marker sintético permanecem locais. Recibos compactos e pareceres estão em `poc/evidence/oracle9-w1-proactor-tests-review-20261112/`; a evidência final é `external-job-entry-final-validation-20261116.json`.

## Continuação

A retomada usa somente a tarefa existente `Maskgw-Claude2-Resume-01a05804`, na mesma conversa e sessão/modelo/medium, depois do horário relatado. O recibo próprio registra o estado efetivamente relido; configuração não garante entrega ou liberação de quota. São necessários host ligado, usuário logado e app/daemon disponível. Nenhuma tentativa antes do horário ou contorno foi autorizado.

Próximo lote: reconciliação pública somente Read sob EXTERNAL-JOB-MAIN-BINDING-REVIEW MB1, distinguindo o main Linux W1 já existente da futura entrada de S, o vínculo de Request/park/portas e N-H/N-C ainda necessário. Sem novo framework, fonte, teste ou efeito antes de revisão. Main/park/perfil de P, N-H/N-C/direitos/kernel/S/G/N1–N16, B1/B2/D-090/demais gates de produto continuam OPEN; Gateway indisponível para produção.
