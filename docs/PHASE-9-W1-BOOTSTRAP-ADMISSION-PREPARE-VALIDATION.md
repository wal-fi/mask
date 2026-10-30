# Admissão — preparador público, antes de qualquer raiz real

2026-10-28: `docs/poc/w1_bootstrap_admission_prepare.py`1b069987, em revisão.
Sem main/invocação/Docker/PG/seed/thread ou materialização operacional.
Carrega só definições pinadas do runner7c113617; state_for tem kind admission,
FRESH/invokedfalse, task32, pins6+5+diagnostic, imagem621 e sete medidas dos
Intents legados (só dois serão usados). Command_for aceita somente a root
admission exata como filha de Temp, venvbfff pinado,-I,-B,entry/root literais.
Materialize calcula tudo antes de mkdir exclusivo, grava attempt.json em
xb/fsync, não apaga/substitui/reutiliza. Retorno é só manifesto público.

8passed/0,48s Windows3.11.3: estado produzido admitido pelo próprio runner
com flags simulados, diretório de teste contém só attempt.json/invokedfalse,
comando fixo, reuso recusado preservando bytes, task inválida e root T4/
outro diretório recusados sem criação. Ruff src/tests limpo, mypy311/314311
arquivos limpos, runtime só3113. Helper só lint restrito/format, não strict.

Pendente: revisão do preparador e da proposta exata (task/root novos e
independentes), comprovar bytes/hashes/comando após materializar antes de
uma execução create/inspect-only. Exportador S1beeb85d6 separado em revisão;
nenhuma raiz operacional nova nem diagnóstico real foi executado neste lote.

## Proposta exata antes de materializar

Preparador1b069987/exportadorbeeb85d6 aceitos pelo Claude2. Seleção conjunta
núcleo71/runner20/export16/preparo8:115passed/16,07s, sem efeito Docker novo.
Proposta pública no checkout `oracle9-admission-prep-20261028/`: rootTemp
`maskgw-oracle9-admission-20261028-2dd94bfb4502755ce8fa8cd496f637c8`,
task34346ce8ed18f936d482c3c19aaeb04f, geradas independentemente. Root ainda
ausente. Estado2392bytes/SHA24d647a044e10cdb25fe42593ee1010587b658382c6634f279f3e7857031ae64.
Script a17e4275fa92f11d9954cded468fd2b02b84d3dc0c017b5103d95189661fc566,
com pins runner/preparador/exportador/núcleo/host/venv/basePython, rootfresca/
estado e uma chamada-I-B. Só dois creates sequenciais, nunca start/attach.
Em revisão antes de mkdir e da execução única. Nenhum raw real novo existe.
