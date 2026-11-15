# W1: validação da entrada C0 para setup e close

2026-11-14, horário de São Paulo; as medições finais após meia-noite UTC estão identificadas pelos recibos. Claude2 programou exclusivamente na sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço medium. Root revisou os oráculos, a fonte e todos os deltas e executou a QA. Um escritor por vez.

## Artefatos finais

| Artefato | SHA-256 |
|---|---|
| `docs/poc/oracle9_w1_supervisor_setup_probe.py` | `43ffbf92c1fb747f61cc764f6db95fdfed800976cfe17cc2bd4e5c8f5657d511` |
| `tests/test_oracle9_w1_supervisor_setup_probe.py` | `d21800600d46feefaf4ae866905799e43273a6bccfa665bf275128a8517edb7f` |
| `tests/test_oracle9_w1_supervisor_setup_probe_review.py` | `a9e0430a0265c7d1287611f584adcc7b0948a5eef945c070e259267c4153a9cf` |

Fonte de 355 linhas/13.196 bytes. Importar apenas define objetos. A entrada C0 usa o qualificador público já pinado e a sua QualCustody; nenhum novo Owner ou framework. O único fluxo de Owner é setup, READY, close retornando None e CLOSED. Nenhum start ou perfil com filho é permitido. O `main` real está guardado; ele ainda não foi executado com o backend nativo.

## Cronologia dos oráculos e correções

1. O primeiro teste ficou parcial após limite da sessão. Root leu suas 540 linhas. Duas sanidades e Ruff/format passaram; dois erros de tipagem e um checker de estrutura contraditório impediram o freeze.
2. A sondagem do próprio checker confirmou três divergências: recusava main protegido e park específico, mas aceitava print em atribuição no import. Os fixtures eram compilados e nunca executados. As contraprovas foram publicadas antes da correção.
3. Root leu todos os deltas das chamadas 31781/39778. Depois dos reparos de fixtures, Ruff/format/mypy passaram. RED84: 22 sanidades PASS, 62 falhas exclusivamente pela fonte ausente, zero erros/skips. Todos os motivos conferidos; freeze antes da primeira fonte. A ausência não comprova comportamento.
4. Root leu as 340 linhas da fonte V1. Resultado 82 PASS/2 FAIL: o loader executava definições de dataclasses sem registro temporário de módulo. Uma sonda de linguagem confirmou a causa, sem chamar backend.
5. Outra sonda do `main` público, com entrada relativa inválida e captura de stdout, reproduziu a confirmação incorreta de uma escrita de zero bytes. Nova suíte de 198 linhas lida integralmente: RED15 medido contra a V1, 8 PASS/7 FAIL somente por reconhecer escrita inválida como entrega, zero erros/skips. Os 84 oráculos originais ficaram fixos.
6. Claude2 corrigiu somente a fonte. Root leu todo delta de registro temporário e confirmação de escrita exata. Uma renomeação local subsequente resolveu o gate de mypy sem mudar fluxo. Ambos os freezes e medições anteriores permanecem preservados.

As chamadas 31781, 39778, 85216, 39479, 26286 e 87797 terminaram com serviço success/is_errorFalse, sem denials, e foram recuperadas antes de outra chamada. A retomada agendada chegou nesta conversa às 23h45 UTC. Isso prova essa entrega; não garante disponibilidade ou entrega futura. Nenhuma troca de conta/modelo ou contorno foi usado.

## Gates finais sobre os bytes finais

| Gate | Resultado |
|---|---|
| Matriz relacionada, 18 arquivos | 2.083 PASS, incluindo 99 C0; zero falhas/erros/skips/deseleções; 28,392 s |
| Ruff de produto/testes | PASS em src/tests |
| Ruff PoC contratado | PASS em E9,F63,F7,F82 |
| Format | PASS, 377 arquivos |
| Mypy strict win32, alvos 3.11 e 3.14 | PASS, 377 arquivos em cada; 3.14 somente estático |
| Mesmas sondas de loader e escrita zero | PASS depois das correções; resultado intermediário identificado como bb9acae4 |
| Preservação | Qualificador 999f4a8d, backend10c, adaptereaeb, 140 testes anteriores e aplicação sem mudança |

Runtime QA: Python Windows 3.11.3, pilha temporária de 64 MiB. A matriz é a dos 14 arquivos de host-run, mais os dois testes do qualificador e os dois C0. É suíte com fakes; não é suíte integral de produto com PostgreSQL. Frontend e pacotes não foram repetidos, porque aplicação, recursos, dependências e empacotamento não mudaram.

Recibos compactos de freeze, revisão e resultado final em `poc/evidence/oracle9-w1-proactor-tests-review-20261112/`. A revisão detalhada é `supervisor-setup-c0-source-review-20261114.md`. Snapshots, XMLs, saídas CLI, artefatos pessoais e logs brutos ficam locais; fonte e testes entram juntos.

## Limites e próximo passo

O teste de `main` cobre somente recusas antes de aquisição e falhas de IO, com portas públicas de stdout/stderr simuladas. Não substitui o loader, funções ou operações do SDK. Sucesso nativo, estacionamento em UNKNOWN, custódia externa e transporte do host ainda exigem medição própria. Não se promete teto físico do SO nem cleanup pela expiração de prazo.

Próximo: host C0 específico sobre a primitiva pública de parada já medida, com campos e limites fechados e oráculos prospectivos antes da implementação/execução. C0 continua sem filho do Owner. Nenhum canário com filho, perfil novo, Docker, PostgreSQL/SQL, credencial, rede externa, estado16, tentativa consumida ou deploy foi usado.

N1–N16, S/G, T5 físico, B1/B2/D-090 gate2/C1/D119/TLS/ingressos/produção permanecem abertos. Gateway indisponível para produção.
