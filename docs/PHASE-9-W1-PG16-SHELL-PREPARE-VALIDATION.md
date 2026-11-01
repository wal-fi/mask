# Preparador do leitor PG16 — validação e parecer

2026-10-31 (São Paulo), sob delegação vigente. Claude2 programou com
`claude-opus-5-5`/esforço medium; o assistente principal revisou e executou
os gates. Baseline Git `719ae3e`; último componente anterior aprovado
`9e4e37e`. Este incremento termina somente o preparador e seus fakes.
Não fecha a fase, a admissão nativa nem qualquer gate de produção.

## Arquivos e resultado

- `docs/poc/pg16_shell_prepare.py`: 9.546 bytes, SHA-256
  `8d0bf39e07f058f5b8d53dba279daee0839f2ff50903358a4c59d03a8f695971`.
- `tests/test_pg16_shell_prepare.py`: 20.336 bytes, SHA-256
  `ed027162604c64328f57c2f6401d06a90254b123f66a8c3472444b246470dfdf`.
- Desenho em `PHASE-9-W1-PG16-SHELL-PREPARE-DESIGN.md`.
- Relatório preliminar/histórico da quota preservado em SHELL-PREPARE-REVIEW.

Estado puro: 16 campos, 6.959 bytes ASCII canônicos, FRESH/invokedFalse,
23 medidas de create e 23 planos de entrega. Os 16 campos foram comparados
ao conjunto literal do AST da entrada aceita afaffad0. A contagem 17 da
primeira instrução estava errada e não virou requisito nem código publicado.

`proposal` não escreve nem lê o launcher; informa que seu pin ainda não
foi verificado. `materialize` valida fontes, limites, raiz e ancestrais,
launcher e fontes novamente, cria uma raiz nova e grava somente
attempt.json por xb/contagem/flush/fsync/releitura. Qualquer falha após
mkdir consome a proposta e deixa o diretório parcial para diagnóstico;
não retorna descritor pronto, não limpa nem tenta de novo.

## Retomada e revisão da primeira entrega

O job Maskgw-Claude2-Resume-01a05804 executou em
2026-10-31T21:45:00-03:00, LastTaskResult 0, sem próximo horário.
A própria mensagem chegou a esta conversa. Não havia escritor ativo antes
da retomada. Configuração persistida e metadados do CLI confirmaram
claude-opus-5-5/medium. Sessão retomada:
51ea0d85-05bb-4d24-ba9a-c9627c3f832f; execuções 23244 e 89461 concluíram
exit 0, sem erro. Não houve outra conta, modelo, escritor ou contorno de quota.
Após confirmar a execução única, a tarefa foi desativada, preservando
LastRunTime/LastTaskResult e NextRunTime null.

A primeira execução dos 43 testes teve uma falha na fixture:
test_real_launcher_is_only_named_in_proposal restaurava PYTHON, mas
mantinha o PYTHON_SHA sintético. Claude2 restaurou ambos; nenhum código
do preparador mudou para acomodar a expectativa. O guard que recusa
leitura do launcher real permaneceu. Ruff/format/mypy do teste já passavam.

A revisão também corrigiu a descrição dos pins: a admit confere plataforma,
versão 3.11.3 e flags; final_pins confere os seis arquivos de STDLIB_PINS.
Isso não atesta o executável base nem toda a stdlib. O desenho prospectivo
da sonda recebeu nota do revisor: marcar consumo depois da medição não
resolve crash antes da marca; o procedimento futuro ainda precisa resolver
consumo prévio independente. Nenhuma sonda foi implementada ou executada.

## Gates finais medidos

- 43 testes próprios aprovados em 33,34 s, sem falhas ou skips.
- Hook independente sem arquivo de teste novo: 1 caso aprovado em 22,47 s,
  sete verificações CLEAN, exit 0.
- Seleção relacionada de 15 arquivos: 550 aprovados em 264,07 s, sem falhas,
  erros, skips ou deselected; processo encerrado com exit 0.
- Ruff src/tests e lint restrito E9/F63/F7/F82 do novo helper aprovados.
- Ruff format: 343 arquivos conformes em src/tests mais pin_cost, pin_capture,
  shell_export e shell_prepare. As demais PoCs históricas continuam fora do
  escopo configurado; nenhuma fonte congelada foi renormalizada.
- Mypy strict: 339 arquivos em src/tests, alvos Python 3.11 e 3.14, sem erros.
  Runtime executado somente Windows/Python 3.11.3.
- Diff checks e fontes aceitas conferidos antes do commit.

O hook independente usou apenas a fixture temporária própria:
importação/estado sem leitura privada, escrita ou spawn; admit real com
runtime/HOME simulados aceitando o estado; recusa de invokedTrue; recusa
de chave JSON duplicada; disputa na abertura xb preservando o arquivo;
erro no fechamento sem sucesso/retry; ancestral HOME marcado reparse
recusado. Não chamou Host, final_pins ou entry.prepare operacionais.

A seleção relacionada contém:
`test_pg16_shell_cleanup_policy.py`, `test_pg16_shell_delivery.py`,
`test_pg16_shell_export.py`, `test_pg16_shell_host.py`,
`test_pg16_shell_owner.py`, `test_pg16_shell_pin_capture.py`,
`test_pg16_shell_pin_cost.py`, `test_pg16_shell_pin_counts.py`,
`test_pg16_shell_prepare.py`, `test_pg16_shell_profile.py`,
`test_pg16_shell_reader.py`, `test_pg16_shell_run.py`,
`test_pg16_shell_watchdog.py`, `test_pg16_public_prepare.py` e
`test_pg16_public_export.py`, todos em tests/. Comando:
`python -m pytest -o addopts= -q <esses 15 arquivos>`.

## Parecer e limites

Aprovado no escopo isolado do preparador/fakes, sem P1/P2 remanescentes.
Código e testes permanecem nos SHA acima após os gates;
os ajustes posteriores são somente relatórios e estado documental.
O assistente principal não programou o helper nem os testes.

Nenhuma raiz operacional, leitura de executável/configuração real, Docker,
PG, SQL, worker ou serviço foi criado/acionado neste incremento. Os fakes
usam launcher sintético e HOME redirecionado para temporários de pytest.
Há I/O real de arquivos temporários e loops/timers auxiliares do harness;
seus tempos não são latência de admissão, CLI, PG ou owner. PostgreSQL,
browsers, frontend e novos pacotes não eram necessários para este lote
de docs/poc, sem mudança de produto, dependência ou recurso embarcado.

Admissão em até 3 s continua NOT_MEASURED; estado de 6.959 bytes não a
comprova. Também não há proposta operacional concreta ou autorização
técnica para executar a matriz de 23 casos. A sonda só pode avançar após
desenho/código/fakes e procedimento de execução próprios revisados.
Os limites 32768/3/12/8/300/600/655 não foram ampliados.

Fontes aceitas afaffad0/ed491c01 e a medição consumida 3eb3 intactas.
Gateway indisponível; B1/B2/D090/C1/SQL/produção continuam abertos.
