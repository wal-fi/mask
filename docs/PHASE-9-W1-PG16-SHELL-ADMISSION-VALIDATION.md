# Sonda de admissão do leitor PG16 — validação e parecer

2026-11-01, São Paulo, sob delegação vigente. Claude2 programou com
`claude-opus-5-5`/esforço medium; o assistente principal revisou e executou
os testes. Baseline Git `c26f0ab`. Somente helper/fakes e documentação:
nenhuma sonda operacional ou medição nativa foi executada.

## Fontes finais

- `docs/poc/pg16_shell_admission_probe.py`: 12.499 bytes, SHA-256
  `738ee1e39466bced17d65671222f7de71661122a34616fde4c98446cb4eee0fe`.
- `tests/test_pg16_shell_admission_probe.py`: 24.257 bytes, SHA-256
  `5dd02d7b9ddda149b6bdd9a0ecf5bfcdde25a4a045651a0d796d6a11169895b0`.
- Desenho: `PHASE-9-W1-PG16-SHELL-ADMISSION-DESIGN.md`.

Preparador8d0bf39e, entradaafaffad0 e exportadored491c01 permanecem iguais.
Nenhuma fonte ou raiz consumida foi alterada/reexecutada.

## Contrato revisado antes de código

O desenho inicial precisou de seis correções: classificação com a diferença
float de time.monotonic e limite original inclusivo3.0; categoria de falha
por etapa independente de Context/atributos da exceção; falha de claim que
pode anteceder a criação de arquivo; guarda de runtime antes das leituras
capturadas (sem promessa sobre imports builtin); classificação retrospectiva,
sem timeout interruptivo ou promessa de cache frio; datas com fuso explícito.
Cli42540/48032 concluíram a elaboração/revisão sem efeitos operacionais;
74011 entregou helper/testes, e1808 corrigiu somente o harness.

A API probe(root, task) admite somente a forma fixa de raiz e task32hex.
Runtime/flags, fontes limitadas por SHA, raiz/ancestrais e estado exato são
conferidos antes do claim. Qualquer ocupante de claim/pendente/final é
recusado. Claim xb/contagem/flush/fsync/releitura antecede a primeira etapa.

O prefixo faz admit → Host → Context → final_pins uma vez. O total usa a
mesma aritmética float da entrada:0<=elapsed<=3.0. Os ticks ns são diagnóstico,
podem ter delta zero, não podem diminuir; sua instrumentação entra no total.
Precedência determinística: STAGE_FAILED, CLOCK_INVALID, depois WITHIN_3S/
OVER_3S. Campos inválidos viram null; JSON nunca emite NaN/Infinity.
Exceções comuns de etapa geram somente STAGE_EXCEPTION e etapa fechada,
sem acessar str/repr/args/category. BaseException não vira sucesso.

A marca na raiz e o resultado .next são persistidos e relidos antes do
rename final, última operação de filesystem. Não há leitura posterior.
Resultado tem no máximo 4.096 bytes. CLI 0 somente para WITHIN_3S persistido;
demais desfechos/erros são não zero, com uma linha pública fechada.
Nenhum callback, executável, módulo ou caminho de saída é parâmetro da API.

## Primeira rodada e correções de harness

Primeira execução:77passed,7failed,2errors/3,74s, sem aprovação/publicação.
As sete falhas eram expectativas de PROBE_CLAIMED depois de já existir marca:
a guarda de raiz corretamente recusa primeiro como PROBE_ROOT. O código
do helper não mudou. Os testes agora conferem a primeira guarda aplicável,
nenhuma chamada adicional às etapas e snapshots dos artefatos intactos.

Os dois erros eram setup e teardown do mesmo parâmetro oversized, cujo ID
automático ultrapassava32767 caracteres em PYTEST_CURRENT_TEST no Windows.
Foram usados IDs explícitos mismatch/oversize, mantendo o payload32769.
RuffN818 pediu renomear Hostile para HostileError. Nenhum limite, caso,
skip/xfail ou proteção foi relaxado. O rerun --lf confirmou as causas antes
de devolver as correções ao Claude2; mensagens/ambiente privados não entram
nesta evidência.

## Gates finais medidos

- 85 testes próprios aprovados em 20,13 s, sem falhas/skips/deselected, exit 0.
- Hook independente em memória: 1 passed/0,60 s, sete verificações CLEAN, exit 0.
- Seleção relacionada de 16 arquivos: 635 aprovados em 270,87 s, sem falhas,
  erros, skips ou deselected; processo exit 0.
- Ruff src/tests e sintaxe E9/F63/F7/F82 do helper aprovados.
- Format: 345 arquivos: src/tests e pin_cost/pin_capture/shell_export/
  shell_prepare/shell_admission_probe. Não normaliza PoCs históricas congeladas.
- Mypy strict: 340 arquivos, alvos 3.11 e 3.14, sem erros.
- Runtime executado somente Windows/Python 3.11.3.
- Diff checks e fingerprints finais conferidos antes do commit.

A seleção usa os mesmos15arquivos da SHELL-PREPARE-VALIDATION, mais
tests/test_pg16_shell_admission_probe.py, por
`python -m pytest -o addopts= -q <esses 16 arquivos>`.
Os85 casos próprios estão incluídos na seleção relacionada, não somados a ela.

## Verificações independentes

Hook sem adicionar/editar testes de produto; HOME e etapas são fakes,
I/O somente nos temporários próprios da fixture:

1. PermissionError ao abrir claim antes de criar arquivo: nenhuma etapa,
   uma tentativa de abertura, erro fechado e sem claim inventado.
2. Ocupante criado na corrida do rename final: o Windows preserva seus bytes,
   não publica o resultado da sonda e mantém o pendente.
3. Depois do rename final, lstat/open/iterdir configurados para falhar:
   nenhum deles é chamado e o resultado é devolvido normalmente.
4. OSError na chamada do relógio: erro fechado, claim preservado e repetição
   recusada sem etapas.
5. SystemExit(0) numa etapa: CLI não zero, resultado não publicado e claim
   preservado; o zero interno não é confundido com sucesso.
6. Falha de stdout depois da publicação: CLI não zero, resultado persistido
   e claim preservado. É falha de confirmação; não autoriza repetir.
7. Exceção com args/category/str/repr hostis: STAGE_FAILED/HOST/
   STAGE_EXCEPTION, sem ler esses atributos.

Parecer aprovado no escopo isolado do helper/fakes, sem P1/P2 remanescentes.
Nenhum código ou teste foi reescrito pelo revisor.
Após os gates só relatórios/estado documental mudaram.

## Limites e próximo passo

O claim queima a tentativa para este caller, mas uma queda antes da marca
pode deixar uma raiz que a entrada original ainda aceitaria se o operador
ignorasse o claim. Uma falha anterior a criar o claim pode não deixar arquivo:
o futuro chamador precisa registrar a invocação antes de lançar o processo.
Fsync de arquivo não prova persistência de entrada de diretório após falta
de energia no Windows. Não há garantia contra adulteração pelo mesmo usuário.

O self-hash da sonda é metadado, não autenticação. A futura execução precisa
de launcher/comando/procedimento próprios revisados, supervisão limitada e
coleta do processo;3s é classificação após as operações, não interrupção.
O gate original da entrada continua decidindo numa rodada futura.

Sem leitura de launcher/config/executável real, raiz operacional, Docker,
PG, SQL, worker, listener ou serviço neste lote. Os testes proíbem spawn,
Thread.start e criação de loop; a carga de definições reais só lê fontes,
sem instanciar Host. I/O temporário real e timers de harness não são medição
de latência nativa. Não houve necessidade de PostgreSQL, frontend/browser
ou pacote novo para esta alteração não embarcada.

Admissão nativa3s permanece NOT_MEASURED; estado16campos/6959bytes e tempos
de pytest não a comprovam. Nenhum limite3/32768/12/8/300/600/655 ampliado.
Gateway/B1/B2/D090/C1/SQL/produção continuam abertos.
