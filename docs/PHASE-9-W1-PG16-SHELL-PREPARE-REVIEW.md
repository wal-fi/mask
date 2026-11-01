# Preparador do leitor PG16 — parecer final e histórico de retomada

Fechado em2026-10-31 (São Paulo). O job das21h45 executou, LastTaskResult0,
sem próximo horário; depois foi desativado. Nenhum escritor estava ativo
antes da retomada. Claude2 manteve Opus5.5/medium e concluiu código, testes
e desenho. O assistente principal executou os gates e a revisão independente.

Resultado final:43passed/33,34s, hook independente7CLEAN/1passed/22,47s,
550passed em15arquivos/264,07s, sem falhas/skips, todos processos exit0.
Ruff/lint restrito do helper/format343/mypy339 alvos311/314 limpos.
Parecer aprovado no escopo isolado; sem P1/P2 remanescentes. Fonte8d0bf39e
e testesed027162 estão documentados integralmente em SHELL-PREPARE-VALIDATION.
A falha inicial de fixture e a correção da descrição dos pins estão preservadas
nesse relatório. Nenhuma raiz operacional ou efeito Docker/PG/SQL/worker novo.
Gate3s continua NOT_MEASURED; procedimento da sonda é apenas direção futura.
Gateway/B1/B2/D090/C1/produção continuam bloqueados.

## Registro histórico — revisão preliminar e retomada

Estado: implementação interrompida por quota em2026-10-31; não aprovada.
Somente Claude2 programa, Opus5.5/esforço medium; assistente principal revisa
e executa validações. Último componente aprovado/publicado:9e4e37e.

## Entrega parcial preservada

Sessão Claude2:51ea0d85-05bb-4d24-ba9a-c9627c3f832f. Execução82419 terminou
exit1, API429, reset informado às21h40 America/Sao_Paulo de31/10.
Arquivo local não rastreado docs/poc/pg16_shell_prepare.py:9391bytes;
SHA256 b0359405d7f1d3ef38100a831e5bba702b10db751dadc212048839acf162c6d6.
Ainda faltam tests/test_pg16_shell_prepare.py e o desenho da preparação.
Não há escritor ativo; nenhum código parcial foi commitado ou publicado.

Leitura inicial conferiu estado FRESH derivado do exportador aceito,
proposta de argv distinta de execução e materialização exclusiva de
attempt.json com fsync/readback. Isso não encerra revisão: testes de falha,
reparse, fontes/launcher alterados e erros sanitizados ainda são necessários.

## Verificações independentes limitadas

Sonda Python3.11.3 em memória carregou as definições públicas e chamou
state_for com task sintética a repetida32vezes. Resultado:

- 16 campos exatos, 6.959 bytes ASCII canônicos;
- 23 create_measurements e 23 delivery_plan;
- phase FRESH, invokedFalse;
- nenhuma raiz operacional materializada, launcher/config externo lido ou
  processo de Docker/PG/SQL criado.

A entradaafaffad0 exige16campos. A contagem17 da primeira instrução ao
Claude2 era incorreta e fica substituída pela fonte aceita. O arquivo parcial
já usa16. O tempo total do comando de sonda inclui PowerShell/startup e não é
medição do gate de admissão3s; esse gate continua NOT_MEASURED.

Foram tentados Ruff/format e mypy strict diretamente no arquivo PoC. Esses
comandos retornaram diagnósticos de estilo/anotações, sem alterar o arquivo.
docs/poc é excluído deliberadamente do escopo Ruff em pyproject.toml; a
verificação direta não corresponde aos gates configurados de src/tests.
Não há resultado de suíte ou aprovação de tipagem do novo incremento.
O preparador não deve ganhar supressões/configuração nova para esconder defeitos.

Fontes congeladas relidas e iguais: exportadored491c01 e entradaafaffad0.
Não repetir a medição consumida3eb3, editar helpers aceitos ou reutilizar raiz.

## Retomada efetivamente registrada

Reutilizada a tarefa existente Maskgw-Claude2-Resume-01a05804, anteriormente
Disabled. Set-ScheduledTask inicial com parâmetro Description não suportado
falhou antes de qualquer alteração; a repetição com sintaxe suportada passou.

Readback final do Agendador:

- State Ready;
- NextRunTime 2026-10-31T21:45:00-03:00;
- um trigger MSFT_TaskTimeTrigger, sem repetição;
- MultipleInstances IgnoreNew e RunLevel Limited;
- ação codex queue na conversa existente
  01a05804-2c07-71f2-bfef-7e3c90c06476, argumentos/mensagem idênticos ao proposto.

A mensagem manda ler o checkpoint e pendências, conferir ausência de escritor,
retomar a mesma sessão Claude2 e preservar Opus5.5/medium e os gates atuais.
O job só enfileira mensagem; não inicia outro escritor diretamente nem
concede autorização adicional. A execução futura ainda não foi observada.
Depende da máquina ligada, usuário conectado e app server disponível.
Na retomada conferir LastRunTime/LastTaskResult e a conversa; se houver
Claude2 em andamento, acompanhar apenas, sem iniciar outra instância.

## Pendências antes de qualquer efeito operacional

Terminar testes/desenho, revisão independente, regressões e gates de src/tests;
somente depois propor a prova nativa de admissão com estado≤32768bytes e
prazo original3s. O envelope47012 continua prospectivo, não desempenho medido.
Não materializar raiz operacional nem executar entry/prepare/Host/final_pins
reais antes de procedimento próprio revisado. Nenhum Docker/PG/SQL/worker/
serviço ou observação nova do Desktop neste lote.

Gateway indisponível; B1/B2/D090/C1/SQL/produção permanecem abertos.
