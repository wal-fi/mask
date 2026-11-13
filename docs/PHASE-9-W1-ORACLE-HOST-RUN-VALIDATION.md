# W1 Oracle: validação do chamador host linear

2026-11-13. Integração pura, sobre SDK falso. Nenhuma execução nativa.

## Sequência e atribuição

1. Desenho H3 `7e230883`, aceito apenas sob HOST-RUN-REVIEW/HR5.
2. Root leu todas as 1.022 linhas do primeiro teste e todo delta V2.
   O freeze `69545074` mediu 56 casos: uma sanidade aprovada e 55 falhas
   pela fonte ausente, sem erros ou skips, **antes da fonte V1**.
3. Root leu as 842 linhas da fonte V1 `5f1e9c` antes da QA. Resultado:
   49 aprovados/7 falhas. Contraprovas sobre os fixtures congelados
   atribuíram cinco falhas a `vars(dict)`, uma a contagem arbitrária e
   uma à ordem por linhas da AST. Não se alterou a fonte para satisfazer
   esses oráculos inválidos.
4. Uma sonda independente reproduziu quatro defeitos reais na admissão
   pública de carriers próprios incompletos: `AttributeError`, zero binds.
5. Claude2 reparou somente o teste com a fonte V1 fixa. Root leu todo
   delta; 56 nós anteriores inalterados. H11 agora exige enumeração
   completa de processos/disposições, mais forte que o mínimo arbitrário.
   H1/H9 e os demais asserts corretos foram preservados.
6. Teste final `e3ef7737`: 60 casos, 56 aprovados e quatro falhas esperadas
   de admissão, sem erros/skips, 2,489 s. Novo freeze **depois da V1 e
   antes da correção V2**. O freeze e as medições anteriores permanecem
   históricos; não se afirma que este hash precedeu a V1.
7. Claude2 corrigiu somente a fonte. Root leu todo delta, reconferiu HR5
   e aplicou apenas Ruff format com prova de AST igual. Testes, probes,
   componentes anteriores, app124, state16 e tentativa permaneceram fixos.

## Resultado final medido

| Gate | Resultado |
|---|---|
| Próprios | 60 PASS; 0 falhas/erros/skips; 1,309 s |
| Relacionados, 14 arquivos | 1.844 PASS; 0 falhas/erros/skips/deseleções; 26,462 s |
| Mesma sonda de admissão | RED4 → 4 PASS; zero binds, recusas fechadas |
| Mesma sonda dos fixtures | 5 PASS; não carrega a implementação host_run |
| Fronteiras do pump anterior | 9 PASS |
| Controles do waiter falso | 2 PASS |
| Witness de retenção | 3 sanidades PASS; mutante sem filtro detectado |
| Ruff src/tests e lint PoC contratado | PASS |
| Format-check | 373 arquivos conformes |
| Mypy strict win32, alvos 3.11 e 3.14 | 373 arquivos, PASS nos dois |
| Preservação por SHA | 149 anteriores + teste + 2 probes intactos |

Runtime: Windows Python 3.11.3; pilha temporária QA de 64 MiB. Python
3.14 somente análise estática. Os 60 próprios integram os 1.844; sondas
independentes são contadas à parte. Nenhum teste com banco foi executado.

Fonte: `c8d38d21548ad91f735b0389c007d9ec8cfa358c3b3ace63b980d922be851795`,
29.936 bytes/870 linhas. Teste:
`e3ef77375d03ffc5eddddd0412c726edea1ca8a45dced3c03f80d872882e4c97`,
49.697 bytes/1.173 linhas. Evidência compacta em
`poc/evidence/oracle9-w1-proactor-tests-review-20261112/host-run-final-validation.json`.

## Limites e próximo trabalho

H14 exercita a coleta protegida real com leitores sintéticos. A validação
de Done exato antes de outcome e a conjunção de report_complete dentro
de run_host foram auditadas diretamente na fonte; H14 não as comprova
dinamicamente. A via de controle durante admissão também é somente revista
na fonte; os quatro casos dinâmicos são falhas ordinárias de slots próprios.

Bind, close e chamadas síncronas do SDK não têm teto físico demonstrado.
Disposição CLOSE_HANDLE no modelo não prova término/remoção física, nem
há contenção provada para os riscos de binding já documentados. Relatório
não equivale a sucesso nativo ou disponibilidade do Gateway.

Aceite somente do incremento puro, fonte/testes integrados juntos após
revisão. Nenhum loader, entrypoint operacional, valor de root/nonce/estado,
Docker, PostgreSQL, SQL ou deploy foi iniciado. Próxima etapa exige
reconciliação pública do binding e dos pré-requisitos de prova nativa,
antes de definir qualquer novo teste/fonte. N1–N16/T5 físico/B1/B2/D-090
gate2/C1/D119/TLS/ingressos/produção continuam abertos.
