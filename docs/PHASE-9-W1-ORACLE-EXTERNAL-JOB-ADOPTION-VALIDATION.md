# W1: validação do adaptador N-S com SDK falso

2026-11-16. Claude2 programou na sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço medium. Root leu todos os oráculos, a primeira fonte de 394 linhas e todos os deltas; revisou e executou os gates. Os terminais interativos do usuário não são chamadas do Claude2: a verificação de escritor acompanha a sessão autorizada, sem inspecionar conversas ou configurações alheias.

## Artefatos finais

| Artefato | SHA-256 |
|---|---|
| `docs/poc/oracle9_w1_external_job_adoption.py` | `465ae9067e0f24fe656259e3757f45e8a5788f55ed177db2ab82160d5b6ba5ae` |
| `tests/test_oracle9_w1_external_job_adoption.py` | `37a757ad69b8d032e44e59d008a183149f9bb1f6fd0f46901553e0b00fbc9224` |

Fonte: 394 linhas/15.836 bytes. Teste: 994 linhas/42.063 bytes. Fonte e teste entram juntos; nenhum teste RED é publicado isoladamente. O contrato consolidado `0e26bddc` e todo o EXTERNAL-JOB-OBSERVATION-REVIEW EJ1–EJ6 continuam normativos.

O módulo carrega explicitamente os mesmos bytes do backend pinado, de forma limitada e preguiçosa, e publica um cache completo em uma atribuição. O adaptador específico retém uma única referência emprestada C, recusa aliases de posse genuína, verifica a adoção e o estado antes de iniciar P e verifica C novamente antes de resume. C não entra no ledger que o close herdado libera. O primeiro controle durante adopt deixa HELD/REFUSED_CONTROL, preservando o objeto exato e impedindo SDK posterior. Nenhuma chamada física de DLL/job/processo/thread/loop de produto foi executada.

## Sequência de revisão e RED preservada

1. Root leu as 815 linhas do primeiro teste. Sondas do próprio oráculo mostraram que uma lista de terminações vazia e uma consulta extra depois do controle ainda passavam. Também foram encontrados problemas de lint/tipagem. Nenhum fonte existia.
2. Root leu as 952 linhas da V2. A contenção passou a exigir efeito positivo, mas o fake ainda substituía o snapshot em um segundo controle. A sonda reproduziu o problema. Claude2 corrigiu só o teste; Root leu o delta e comprovou igualdade de AST dos demais nós.
3. O teste `7601d8a8` foi congelado após RED98: quatro sanidades do fake PASS e 94 falhas exclusivamente por ausência da fonte, zero erros/skips/deseleções, 6,871 s. Ruff, format e mypy win32 3.11/3.14 passaram. A ausência da fonte não comprova comportamento do produto.
4. Claude2 entregou a fonte `86d2049e`. Root leu todas as 394 linhas; 98/98 testes passaram em 2,690 s. A revisão encontrou, porém, um erro no dado de truncamento de MEMBERS e uma diferença indevida entre o leitor novo e os leitores pinados.
5. A sonda com SDK falso mediu header 8, entrada 8, mínimo 16, buffer 24 e comprimento reportado 23. O método público herdado aceita esse intervalo; o leitor novo recusava padding válido. Isso é compatibilidade com o contrato pinado, sem alegar observação do kernel físico.
6. A reabertura foi restrita: short de MEMBERS passou a mínimo−1; nenhuma asserção antiga foi relaxada. Foram acrescentadas duas regressões positivas de padding, na adoção e antes de resume. AST de todos os outros nós permaneceu igual. Teste `37a757ad` congelado contra a fonte `86d2049e`: 98 PASS/2 FAIL somente nas novas regressões, zero erros/skips/deseleções, 3,423 s. O RED98 original foi preservado.
7. Claude2 corrigiu somente a fonte: `minimum <= length <= sizeof(info)` substituiu o predicado de mínimo exato ou buffer cheio. Root leu todo o delta; AST de todos os nós fora de `query_members` comprovadamente idêntica. Count, assigned, limites de array e PID permaneceram iguais. O teste congelado não mudou.

As seis chamadas 53214/66781/40367/77890/36387/89656 terminaram com sucesso/is_errorFalse, sem denials, e foram recuperadas. Nenhuma chamada foi reaberta ou duplicada nesta validação. Não houve novo limite de quota, reagendamento, troca de conta/modelo ou contorno.

## Gates medidos sobre os bytes finais

| Gate | Resultado |
|---|---|
| Teste próprio completo | 100 PASS; zero falhas/erros/skips/deseleções; 3,810 s |
| Matriz relacionada, 21 arquivos | 2.321 PASS, incluindo os 100 próprios; zero falhas/erros/skips/deseleções; 47,771 s |
| Ruff de produto/testes | PASS em src/tests |
| Ruff PoC contratado | PASS em E9,F63,F7,F82 |
| Format | PASS, 377 arquivos |
| Mypy strict win32, alvo 3.11 | PASS, 377 arquivos |
| Mypy strict win32, alvo 3.14 | PASS, 377 arquivos; somente estático |
| Preservação | Backend10c9058f, adaptereaebedd6, qualificador999f4a8d e C043ffbf92 intactos; código e testes anteriores sem mudanças |

A matriz contém os 18 arquivos relacionados do fechamento C0, o teste N-S novo e os dois testes de Kernel falso do backend/adaptador. Seleção por caminhos explícitos, sem filtro de deselection. Foi usado pytest diretamente no processo de desenvolvimento, sem wrapper de pilha de 64 MiB. Os tempos vêm dos XMLs JUnit locais; códigos de saída foram zero. Não é execução da suíte integral de produto com PostgreSQL.

Fonte, teste e pins foram conferidos depois dos gates. Nenhuma configuração de gate, dependência, aplicação, recurso de UI ou empacotamento mudou. Por isso frontend, pacotes e PostgreSQL não foram repetidos. Recibo compacto: `poc/evidence/oracle9-w1-proactor-tests-review-20261112/external-job-adoption-final-validation-20261116.json`. Os pareceres detalhados, probes e dois REDs permanecem preservados. XMLs, respostas CLI, snapshots e artefatos pessoais continuam locais.

## Limites e continuação

Aceite somente do adaptador específico N-S sob SDK falso. Direitos reais, identidade do mesmo job, transferência por N-H/N-C, transporte vivo e custódia física externa continuam não admitidos. Adoção positiva no fake não prova nenhum desses fatos. Close de Owner não significa close de C nem liberação global do job.

Próximo lote mínimo: reconciliação pública somente leitura do vínculo N-H/N-C ainda necessário contra XJ3/EJ1–EJ6 e as APIs existentes. Fechar contrato e evidências concretas antes de quaisquer novos oráculos, fonte ou efeito nativo; reusar os componentes revistos, sem outro Owner/framework/guardião. Se delegado, somente a mesma sessão Claude2, Read restrito, sem comandos/execução; Root lê todo o relatório antes da próxima decisão.

Nenhuma leitura de runtime/configuração/privado/binário/estado16/tentativa consumida, Docker, PG/SQL, credencial, rede externa ou deploy neste lote. N-H/N-C/direitos/kernel/S/G/N1–N16 e B1/B2/D-090/demais gates de produto permanecem OPEN. Gateway ainda indisponível para produção.
