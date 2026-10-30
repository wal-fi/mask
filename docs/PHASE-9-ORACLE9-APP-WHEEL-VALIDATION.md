# Oracle9 — wheel próprio local medido em2026-10-26

Resultado: APP_WHEEL_BUILT_VERIFIED/exit0. Dois hooks PEP517 nas cópias
source1/source2, no mesmo processo Windows3.11.3, produziram exatamente
o mesmo maskgw-0.1.0-py3-none-any.whl de429.231bytes, SHA
9181d95511ef8f791ab79d84d09705f0e8bcbcbe7c27465a8d1c64039b759724.
Não é prova de igualdade entre interpretadores/plataformas ou rebuild
geral futuro. Nenhum pacote foi instalado, importado da wheelhouse ou
executado como Gateway. Docker não foi iniciado neste lote.

## Revisão/procedimento

O Claude2 aceitou o código/procedimento com P1: inventariar e conferir
plugins setuptools do ambiente antes de importar o backend. Implementado
apenas esse delta e dois testes, conforme condição para executar sem nova
revisão. Cinco grupos/46entradas exatos, donos setuptools84.0.0,
wheel0.48.0 e o keyword cffi_modules de cffi2.1.1 (não usado pelo projeto),
plugin estranho recusado sem .load. Registro público pinado d3da970d.
21novos testes:20pass/1skip symlink sem privilégio;166relacionados:
165pass/1skip. Ruff/mypy do teste, format2 e sintaxe do helper verdes.
Nada disso substitui a suíte integral do produto.

Raizv1b3566164 preservada sem invocação. Uma execução real na v2
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-app-wheel-20261026-ad017213,
taskb0aeaaf146cf4a749f6dd60b07f1ae0c. Programa
a964890b2b6a3acaea87fcaeb0f780f14c0bc4b4656d8f983fb24b3e32a38507;
estado616b125c/snapshot678b09f6. Pins completos/raiz fresca conferidos
antes da chamada. I2bbcfd53 e resumoId2f0bfca revalidados, assim como
todo o conjunto D. Sem rede solicitada/instalação/segredos/DB/commit/push.

## Fontes e conteúdo

119arquivos capturados/1.463.784bytes: pyproject917fe735 mais118arquivos
de pacote/assets. Fonte atual inclui os incrementos autorizados ainda
não commitados; o Git não foi usado como substituto dos bytes reais.
Manifestos de fonte e cópias comparados antes/depois dos dois hooks e
novamente depois do terminal, sem modificar checkout. Quebras de linha
reais preservadas. Sem config, catálogo, secrets, frontend privado,
.venv/.codex/.claude, tests/docs/capturas ou caches no wheel.

122membros exatos:118de pacote e quatro de metadata. Conferidos bytes de
cada fonte, estruturaI/RECORD/CRC/hash, tags py3-none-any/purelib, dez
RequiresDist de runtime +quatrodev semânticos e somente extra dev. Sem
pth, entrypoints próprios, .data/scripts ou binários nativos. O extra dev
não entra no lock de runtime. O wheel é Python puro, não cópia de qualquer
pacote Windows. Compatibilidade da aplicação Linux ainda não foi medida.

Backend: setuptools84.0.0, wheel0.48.0, packaging26.3. build_meta.py SHA
6f4a583e1b6bb0d5ef3af2ac0a6e9a033d06f364e4a550e3b112812674b38419;
outros módulos admitidos por versão, não hash completo do ambiente.
SOURCE_DATE_EPOCH315532800. Ambiente mínimo durante backend, cwd/env
restaurados no finally. Primeiro log26.596bytes, segundo log0bytes;
o segundo arquivo vazio é fato observado, sem inferir causa ou afirmar
que representa a saída completa de módulos com estado compartilhado.
Os dois outputs físicos novos e hashes foram conferidos independentemente.

## Evidências preservadas

Em docs/poc/evidence/:
- oracle9-app-wheel-result-20261026.json:95.565bytes, SHA
  d0909fcf1ee17ff4ebb79d42746589f06a84c44a4686b65e30cf6ed22387606a;
  manifesto completo, plugins e inventário de122membros.
- oracle9-app-wheel-summary-20261026.json:8.599bytes, SHA
  3378a5be75ce0036ea7f69e3097321e4b2b67c3887c523b423168214bc337983.
Os dois wheels/logs continuam somente na raiz Temp própria. Segundo
arquivo de log tem SHA padrão de vazio; primeiro
3a1b0ef61b8ece186204e9001986d6a31fe09aaa51d5851153055bb7013439e0.

Próximo: contexto/lock37fechado e instalação candidata offline em Oracle
sob revisão própria de código/recursos/comandos e restauração do Desktop.
Ainda sem aplicação instalada, serviço disponível, SQL ou produção.
B-1/B-2/D-090 gate2 permanecem abertos. Nada em src/produto mudou.

Revisão final do Claude2 aceitou o wheel como entrada fixa, sem bloqueador:
122membros/119fontes, versões/backend/projeto/task e limitações conferidos.
Próximo código/contexto/recursos/comandos de instalação passam por revisão
própria, com pipcheck, arquivos instalados, donos/modos e sonda nonroot.
