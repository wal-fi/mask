# W1: validação do qualificador do Owner público

2026-11-14. Somente SDK falso neste incremento. Autorização W1 local preservada; não é admissão nativa nem liberação de produção.

## Artefatos finais

| Artefato | SHA-256 |
|---|---|
| `docs/poc/oracle9_w1_supervisor_qualification.py` | `999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015` |
| `tests/test_oracle9_w1_supervisor_qualification.py` | `7905f2295ff065ab207cd99a09c84214f4b6c637bd730d2d3a968a005b8a7163` |
| `tests/test_oracle9_w1_supervisor_qualification_review.py` | `ba61f89a734f069de76029409a32c46fe980d58a64c9961edf671298fc688633` |

O teste132 foi congelado antes da primeira fonte. A revisão8 foi congelada contra a fonte V1 `484980a0`, antes da correção SQ3. A ordem não é apresentada como se os oito novos casos precedessem a V1. As duas versões dos testes permaneceram intactas após os respectivos freezes.

## Gates medidos

| Gate | Resultado |
|---|---|
| RED inicial | 132 casos: 6 sanidades PASS, 126 falhas por fonte ausente; zero erros/skips |
| Primeira fonte | 132 PASS; defeito SQ3 descoberto depois por sonda independente |
| RED SQ3 | 8 falhas pelo estado desatualizado; zero erros/skips |
| Matriz final, 16 arquivos | 1.984 PASS, incluindo 140 próprios; zero falhas/erros/skips/deseleções; 27,474 s |
| Mesma sonda de estado | RED antes; PASS depois: HELD real e reportado, controle idêntico, zero chamadas SDK posteriores |
| Ruff produto/testes | PASS em `src tests` |
| Ruff PoC contratado | PASS em E9,F63,F7,F82 |
| Formatação | PASS, 374 arquivos |
| Mypy strict win32, 3.11 e 3.14 | PASS, 374 arquivos em cada alvo; 3.14 somente estático |
| Preservação | Backend `10c9058f`, adapter `eaebedd6` e árvores anteriores rastreadas intactos |

Runtime QA: Python Windows 3.11.3, pilha temporária de 64 MiB. Os 14 arquivos anteriores são os do manifesto `host-run-final-validation.json`, acrescidos dos dois testes deste incremento. Não houve retry, skip/xfail, enfraquecimento de asserções ou execução com banco.

As execuções Claude2 6128, 4942, 16025, 83233 e 27280 terminaram e foram recuperadas. Mesmo modelo, esforço e sessão; um escritor por vez. Root leu a fonte V1 inteira e todos os deltas, os oráculos originais e todos os seus deltas, além do novo teste de revisão completo. Os retornos do serviço foram success/is_errorFalse, sem denials. Não houve quota observada neste incremento.

O Ruff amplo exploratório da PoC teve 20 diagnósticos fora do gate preexistente; o gate não foi alterado. Frontend, wheel/sdist e suíte de produto com PostgreSQL não foram repetidos: não mudou aplicação, recurso, dependência ou empacotamento. Nenhum sucesso desses gates é declarado como nova medição.

## Escopo e continuação

Integração conjunta de fonte, testes e evidência compacta revista. Saídas CLI, XMLs, snapshots privados e artefatos pessoais ficam locais. O qualificador ainda não foi executado sobre Owner nativo; a próxima entrada e sua custódia externa precisam de revisão antes dos canários. Não se considera UNKNOWN como cleanup nem orçamento de turnos como teto físico.

N1–N16, S/G, T5 físico, B1/B2/D-090 gate2/C1/D119/TLS/ingressos/produção continuam abertos. Gateway indisponível. Docker, PG/SQL, credenciais, rede externa, estado16, tentativa consumida e deploy permanecem fora deste lote.
