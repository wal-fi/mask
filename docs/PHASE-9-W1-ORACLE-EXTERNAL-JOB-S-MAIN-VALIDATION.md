# W1: main específico de Windows S — validação com SDK falso

2026-11-16. Claude2 programou somente na sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço medium, com escrita restrita a um arquivo por lote e sem comandos/execução. Root leu todos os oráculos, deltas e a implementação antes de QA. O aceite é do componente no laboratório; não é a disponibilização do Gateway.

## Artefatos finais

| Artefato | SHA-256 | Tamanho |
|---|---|---|
| `docs/poc/oracle9_w1_external_job_s_main.py` | `9ef5a21eec69e4f1ccbccd94569e624a00cf9d2bfe36139e8bd687ea9c45496e` | 290 linhas;10.029bytes |
| `tests/test_oracle9_w1_external_job_s_main.py` | `f8d519e5cc839b10b713b1eceafbc1f37c5bf01cbdb07da69e5be9d2e5a416c3` | 1.836 linhas;75.589bytes |
| `tests/test_oracle9_w1_external_job_s_main_review.py` | `9e1142cf7e0dee900bc276d2facaecf0157be614bdcde06ff88596e488903bf8` | 83 linhas;3.279bytes |

Fonte e os dois testes são integrados JUNTOS. Nenhum teste RED é publicado isoladamente. Os estados de fonte/teste ausentes no desenho SM3 são marcos históricos anteriores aos oráculos; o desenho pinado continua intacto, sob toda a revisão SM-R1–SM-R4.

## O que foi ligado

O arquivo próprio carrega os mesmos bytes pinados da entrada em módulo temporariamente registrado, obtém uma única AdoptionLoad e constrói o Request de sua classe exata. O perfil NATURAL e os limites são conferidos estaticamente contra os fontes pinados; o qualificador e C0 não são importados em runtime. O holder de10campos retém portas emprestadas, carregamento, Request, custódia/Owner e primeiros objetos. Guard de reentrada e guard público de custódia precedem a única chamada de run_entry.

A fase A recusa inputs/carga antes de entrar, sem chamar essa fase de recurso-livre: C pode já estar em S. Depois de entrar, incerteza leva à retenção. As sete categorias mantêm o mapeamento fechado, apenas DONE usa0. O park específico mantém referências e absorve controles posteriores; não fecha ou termina recursos. O main não emite stdout/stderr; só o ack da entrada pode escrever em stdout.

O main Linux W1 existente foi preservado. Este arquivo não o substitui, não implementa host H ou ingressos do produto e não foi acionado com inputs válidos nem park real.

## Revisão e regressões antes das correções

- Root recebeu integralmente os relatórios de121/61linhas, leu287linhasSM1 e os deltas522/86 até o SM3 de309linhas. Corrigiu a comparação impossível de literal_eval sobre re.compile, a alegação de contagem de invocações por job count e o tratamento indevido de custódia usada como recusa liberável. As decisões foram fechadas sob delegação, sem aprovação individual inventada.
- Root leu1.296linhas iniciais do teste e todos os deltas66/942/33/115. As primeiras32sanidades passaram, mas contraprovas independentes mostraram falsos aceites nos classificadores. RED6:32PASS/6FAIL. Depois, a família de escrita incondicional posterior ainda substituía os primeiros objetos; RED-W6:41PASS/6FAIL. Cada falha foi conferida antes de reparar os helpers. Ambos os históricos permanecem preservados.
- Após o reparo:47sanidades e15contraprovas AST independentes passaram, junto de Ruff/format/mypy win32 3.11/3.14 em1arquivo. Teste f8d congelado ANTES de pedir a fonte. RED do arquivo inteiro:102casos,47sanidades PASS e55FAIL exclusivamente pela ausência da implementação,0erros/skips/deseleções,1,494s; cada mensagem de falha foi conferida exatamente.
- Root leu todas as284linhas da primeira fonte6ec antes de QA. Os102casos passaram, mas a revisão independente reproduziu OSError bruto em Path.resolve, fora da proteção do erro fechado. Criou-se um teste de revisão SEPARADO, preservando f8d: Root leu83linhas e mediu1FAIL no erro ordinário e3PASS nos controles, sem erros/skips, antes de pedir o fix.
- A correção alterou só `_load_entry`: a preparação ordinária do caminho agora produz SMainLoadError/S_MAIN_LOAD levantado fora de except. Controles mantêm identidade. Root leu todo o delta e comprovou que os demais nós AST e os dois testes congelados ficaram intactos. Nenhum erro original/cadeia serve como resposta do loader.

As chamadas80442/29677/79390/72666/47382/33597/20306/82651 terminaram exit0/success/is_errorFalse, sem denials, e foram recuperadas. Os relatórios não foram usados como prova de gates: as medições são do Root. Nenhuma nova quota ou entrega futura foi presumida.

## Gates nos bytes finais

| Gate | Resultado |
|---|---|
| Próprios,dois testes | 106 PASS;0falhas/erros/skips/deseleções;4,024s |
| Matriz relacionada,24arquivos | 2.620 PASS,incluindo106próprios;0falhas/erros/skips/deseleções;56,718s |
| Ruff src/tests | PASS |
| Ruff PoC contratado | PASS E9,F63,F7,F82;101caminhos públicos explícitos |
| Formatação src/tests/main novo | PASS,380arquivos |
| Mypy strict win32,alvo3.11 | PASS,380arquivos |
| Mypy strict win32,alvo3.14 | PASS,380arquivos;somente estático |

A matriz é a lista explícita de22arquivos do fechamento da entrada mais os dois testes novos; nenhum filtro/deselection. QA em processo Python de desenvolvimento, sem wrapper de pilha64MiB. Os snapshots/evidências brutas são excluídos da lista de lint PoC; não foram formatados ou editados. Não é a suíte integral de produto com PostgreSQL. Frontend, pacotes, dependências e src não mudaram e seus testes funcionais não foram repetidos.

## Limites e continuação

Os classificadores são provas parciais de forma e das famílias adversariais medidas; não um analisador universal. A costura dinâmica usa run_entry real e SDK falso na MESMA cópia de backend. O main completo com portas reais, as lacunas entre bytecodes, a duração física do park/S, direitos/identidade/duplicação de C e EOF/causalidade/cleanup continuam sem prova física. Não há alegação de B4 global, nem de proteção contra alteração privilegiada do código/globais confiados.

Entrada b482/teste1835,N-S465/37a,backend10c,adaptereaeb,C0/qualificador e antigos fontes/testes/pins permaneceram fixos;9pins públicos foram conferidos. State16/tentativa consumida não foram lidos. Nenhum main válido, espera real, efeito nativo do produto, Docker/PG/SQL, credencial, rede externa ou deploy foi acionado. Git/CIM e processos CLI/QA são ferramentas de desenvolvimento, não filhos do experimento nativo.

Recibo compacto final: `poc/evidence/oracle9-w1-proactor-tests-review-20261112/external-job-s-main-final-validation-20261116.json`. Pareceres e recibos intermediários compactos acompanham o fechamento. Respostas CLI, XMLs, snapshots e artefatos pessoais permanecem locais.

Próximo lote: reconciliação PÚBLICA SOMENTE Read do menor vínculo N-H/host v2 e dos pré-requisitos N-C em vida de S, sob XJ3/EJ e APIs existentes. Identificar reuso exato e o que precisa de contrato/código/prova, sem novo framework/Owner/launcher, valores de invocação ou execução. Root lê TODO relatório antes de definir alteração. N-H/N-C/direitos/ambiente/kernel/S/G/N1–N16/B1/B2/D-090/TLS/ingressos/demais gates de produto OPEN; Gateway indisponível para produção.
