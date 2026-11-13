# W1 Oracle: validação do helper de bind Proactor

2026-11-13. Incremento puro sobre SDK falso, não operação nativa.

## Insumos e sequência

- Desenho B2 e48639a5 e BIND-REVIEW completo, B4 normativo.
- Root leu todos os oráculos e deltas; RED45 congelado ANTES da fonte:
  3 sanidades PASS / 42 KeyError por ausência de `_bind_over`, nenhum
  erro, skip ou deselect, 1,540 s. Todos os textos de falha conferidos.
- O mesmo probe independente 1eefc4af passou de falso negativo reproduzido
  (mutante também passava) para detecção do mutante, sem mudar seu código.
- Claude2 escreveu somente helper e delegação do wrapper. Root leu TODO
  delta; restante do módulo e prefixo do wrapper têm AST idêntica.
- Somente formatação mecânica posterior, com prova de AST igual.

## Resultado medido

| Gate | Resultado |
|---|---|
| Relacionados, 13 arquivos | 1.784 PASS; 0 falhas, erros, skips ou deselects; 24.102 s |
| Casos do pump anterior incluídos | 135 PASS, oráculos congelados intactos |
| Casos novos do bind incluídos | 45 PASS, oráculos congelados intactos |
| Bind após formatação mecânica | 45 PASS; 0.382 s |
| Sonda de fronteiras do pump | 9 PASS |
| Sonda de controles do waiter falso | 2 PASS |
| Witness | 3 sanidades PASS; mutante sem filtro detectado |
| Ruff de src/tests e lint PoC contratado | PASS |
| Format-check final | 371 arquivos conformes |
| Mypy strict win32, alvos 3.11 e 3.14 | 371 arquivos, PASS nos dois |
| Textos protegidos | 147 intactos; fonte em edição excluída |

Runtime: Windows Python 3.11.3, pilha QA de 64 MiB. Python 3.14 somente
análise estática. A matriz relacionada, sondas e mypy foram medidos antes
da única formatação semântica idêntica; format e os 45 casos foram repetidos
sobre os bytes finais. Isso não é nova execução de PostgreSQL/frontend ou
suíte integral do produto; tais componentes não foram alterados.

Fonte final: `3cb74292da35050088b2d451bdd91007e4b6a962319bc0a900fc8f771a02f244` (38.627 bytes / 1.109 linhas).
Teste congelado: `f6724a8f3614883dbff28634bdfbb13f8bdbb01ec3fe58deefe93ef4b60a4fce` (19.488 bytes / 483 linhas).
O arquivo bind-final-validation.json contém paths, hashes, contagens e
alcance. Raw logs, respostas CLI e metadados pessoais ficam somente locais.

## Limites preservados

Nenhum bind real, SDK nativo, Docker, PostgreSQL, SQL ou receita operacional
foi executado ou preparado. Uma chamada fake de close não prova cleanup
físico. Retenção no frame do helper não implementa o chamador futuro nem
fecha construção parcial, close bloqueado ou handoff assíncrono. Todos os
gates nativos e de produto continuam OPEN; Gateway ainda indisponível.
State16 / tentativa consumida intactos, sem leitura. Fonte e teste devem
ser publicados juntos somente após a revisão, nunca o RED isoladamente.
