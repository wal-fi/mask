# W1 Oracle: validação do pump Proactor com SDK falso

2026-11-13. Implementação:Claude2, mesma sessão51ea0d85, Opus5.5/medium.
Root revisou toda fonte original e todos os deltas antes de executar QA.
Somente modelo integrado com SDK falso; nenhuma ligação nativa executada.

## Artefatos e sequência

- Fonte:docs/poc/oracle9_w1_proactor_pump.py,
  SHA2560a4dcd574c9c2d3f2e855d0cd3752a1a86b041966b9a628bc5ed76bcf6a798a8,
  36637bytes/1077linhas. O bind real está definido, nunca chamado.
- Teste:tests/test_oracle9_w1_proactor_pump.py,
  SHA25636b2ba548da0966736123f6bfbd05c8c39af3e0d9e33e79e1797d32f07dcf150,
  113465bytes/2973linhas. Congelado antes de escrever a fonte.
- Sondagem independente:probe_source_boundaries.py,
  SHA2560192ef43a8126b1b09e7ce763357b5244e2b214fafe0bbed6bed1bbdbf8004cc.
  Somente API pública e fakes do teste; não altera campos privados do pump.

Root leu2855linhas da V1 dos oráculos e todos os deltas V2;220nós de função
inalterados por AST. Corrigidos waiter do SDK falso, primeiro ident válido
e snapshot inicial dos diferidos antes de congelar. RED135:9sanidades PASS/
126FileNotFoundError esperados,0erros/skips/deseleções,29,479s; todos126textos
conferidos. A ausência do módulo não é evidência comportamental.

Depois, root leu1007linhas da fonte V1. Seus135testes passaram, mas um
roteiro independente reproduziu S1/S2: exceções em leituras S0 expunham
mensagem original, e close permitido no callback podia causar fault falso
antes do retorno S4. RED9:3PASS/6FAIL, medido antes da correção. V2 foi
revista integralmente por delta (91nós de função inalterados), seguida de
Ruff format com prova de AST igual. O MESMO roteiro passou9/9 depois.

## Gates finais medidos

| Gate | Resultado |
|---|---|
| Matriz relacionada,12arquivos |1739PASS,135próprios;0falhas/erros/skips/deseleções;25,067s |
| Sondagens públicas independentes |9/9PASS; RED anterior preservado |
| Ruff de produto em src/tests |PASS |
| LintPoC contratual E9,F63,F7,F82 |PASS |
| Formatação |370arquivos conformes |
| Mypy strict win32,3.11 e3.14 |370alvos conformes em cada execução |
| Proteções por hash/tamanho |142textos intactos; estado16/attempt não lidos/tocados |

Runtime:Windows/Python3.11.3, pilha QA temporária64MiB.3.14 é análise
estática, sem execução alegada. Os11arquivos relacionados anteriores são
os da matriz1604 do owner, acrescidos do novo teste135. Paths e contagens
estão no manifesto compacto final-validation.json nesta pasta de evidência.

Comandos de QA, na raiz do checkout, com o Python da venv:

```text
python -m ruff check src tests
python -m ruff check --select E9,F63,F7,F82 docs/poc/oracle9_w1_proactor_pump.py
python -m ruff format --check src tests docs/poc/oracle9_w1_proactor_pump.py
python -m mypy --strict --platform win32 --python-version 3.11 src tests docs/poc/oracle9_w1_proactor_pump.py
python -m mypy --strict --platform win32 --python-version 3.14 src tests docs/poc/oracle9_w1_proactor_pump.py
python -c "import runpy; runpy.run_path('docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112/probe_source_boundaries.py',run_name='__main__')"
```

Para a matriz, pytest recebeu exatamente os12paths do manifesto, -q e
JUnit XML, por pytest.main no runner de pilha64MiB. Não houve deselect,
skip/xfail novo, retry, supressão ou mudança dos oráculos para a fonte.
Wheel/frontend/PostgreSQL não foram repetidos: nenhuma aplicação, recurso,
dependência ou empacotamento mudou; todos124textos da aplicação foram
conferidos intactos. Esta matriz é de fakes, não suíte integral de produto.

A tentativa exploratória de Ruff amplo sobre a PoC teve33diagnósticos e
permanece registrada na revisão; docs/poc já é excluído pelo projeto.
Não se mudou o gate existente E9,F63,F7,F82, a API PumpFault, imports
nativos locais exigidos, configuração ou supressões para obter verde.

## Limites e publicação

N1–N16 do desenho permanecem abertos, incluindo EOF pausado, partidas sem
handle observável, S4 pendente, códigos fora de0..255, hooks/wakeup fd,
cleanup automático do SDK e bloqueio possível de loop.close. A classe de
snapshot usa estado privado isolado; não é uma nova API pública.
Não se afirma recuperação física, prazo nativo ou quitação de recurso.

T5físico/B1/B2/D090gate2/C1/D119/TLS/ingressos/produção seguem OPEN.
Gateway indisponível para produção. Sem Docker,PG,SQL,loop/socket/thread/
processo/sinal/guard/nativo de produto, valores operacionais ou deploy.
Os processos executados foram somente programador/QA/orquestração.
Recursos de produto e tentativa consumida não foram acessados.

Integração deve publicar fonte E teste135 juntos, com este parecer e só
evidência compacta revista. Propostas reprovadas, saídas/transcrições CLI,
XMLs de teste/tarefa, pacotes, notas pessoais e caches permanecem locais.
Este aceite não é aprovação de produção nem fechamento de gates nativos.
