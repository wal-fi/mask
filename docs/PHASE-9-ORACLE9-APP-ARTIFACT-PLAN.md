# Oracle9 — próximo artefato da aplicação e instalação offline

Preparação sob delegação; nenhum build/instalação executado por este plano.
Entrada necessária: revisão aceita de I sobre os36wheels imutáveis do D.
Não executar o Containerfile inicial: ainda instala RPMs pela rede e não
parte da fundação já medida. Substituição deve ser revisada antes do uso.

## Wheel próprio, fora do checkout

Construir somente a aplicação pure-Python com as ferramentas já existentes
na .venv Windows, sem instalar/atualizar nada: Python3.11.3, build1.6.1,
setuptools84.0.0 e wheel0.48.0 medidos em2026-10-25. Versões são fatos do
ambiente de build; não certificam Linux ou versão de pacote instalado.

Gerador com raiz Temp exclusiva e manifesto dos bytes de pyproject.toml e
src/maskgw: somente arquivos de código .py e os quatro tipos de assets
declarados no package-data. Nunca incluir .venv, .git, .codex, .claude,
configuração, chaves, catálogo, testes, docs/capturas ou frontend privado.
Listar entradas sem seguir symlink/reparse; rejeitar desconhecidos, exceto
cache __pycache__ explicitamente ignorado. Tetos/hash/contagem antes e
depois da cópia e do build; fontes do checkout preservadas. Sem exportar
git HEAD, pois deixaria de fora incrementos válidos ainda não commitados.

Build sem isolamento que baixa dependências: --no-isolation, sem rede
necessária, ferramentas conferidas e somente projeto capturado. Duas cópias
idênticas próprias e SOURCE_DATE_EPOCH fixo não confidencial permitem
comparar dois wheels. Não anunciar determinismo antes de medir os bytes.
Nenhum wheel remoto será importado no Windows. Validar o wheel próprio
como ZIP/RECORD, pacote/assets exatos e METADATA contra o projeto; o teste
de compatibilidade da dependência ocorre no Linux instalado, não no host.

## Instalação candidata Linux

Novo contexto gerado limitado: Containerfile revisado, manifesto/lock final,
wheel próprio e36wheels aceitos por I, sem fontes/segredos. Base local
sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4
e DiffIDs já medidos; ausência bloqueia, sem pull nem fallback de tag.
Comando/recursos/cleanup/restauração do Desktop serão revisados à parte.

Instalar com networknone, no-index/no-deps/only-binary/require-hashes e
no-compile. A admissão confere todos os hashes e política I antes de
instalar. Inventário .pth/entrypoints terá decisão técnica explícita: não
executar nem apagar silenciosamente. Entrypoints opcionais cujos extras
não foram selecionados não viram interface operacional do produto.

Exigir pipcheck, versões/arquivos instalados iguais ao lock + ferramentas
base declaradas, imports da aplicação e recursos, bibliotecas efetivas
libpq/OpenSSL de psycopg e cryptography. Ferramentas de build e materiais
da preparação da fundação serão removidos ou mantidos explicitamente na
receita revisada, sem alegar que atualizar RPM corrige binários do wheel.
Imagem candidata ainda não é release ou serviço pronto. Perfil final sem
rede na sondagem/nonroot/read-only/NNP/capdrop/limites; rede upstream e
configuração operacional entram em gate posterior.

Depois: integração do worker, snapshot/lease/budget/resultados, PostgreSQL
descartável, gates B-1/B-2/D-090 e testes PGWire/MCP/IDE/Admin. A aplicação
atual continua recusando SQL e mantendo stdio/EOF; não simular daemon
segurando stdin. Só informar disponibilidade quando o serviço realmente
passar a aceitação. Nenhuma conexão a banco existente ou credencial antiga.

## Precisões após revisão do plano e escolha do mecanismo

I aceito na revisão final sem bloqueador técnico. Pyproject capturado deve
ter exatamente917fe7353178849ec9e7f53627fc0ce2e0be9fb7678d6dcd2e42f79b925de8f9,
mesmo da resolução, com10raízes. Conferir no wheel o conjunto semântico
Requires-Dist das dez e dos quatro dev sob extra=dev; dev não entra no
lock de runtime. Não resolver novamente ou aceitar divergência por rename.

Implementação preferida para este pequeno projeto declarativo: chamar o
hook público PEP517 setuptools.build_meta.build_wheel diretamente **no
processo isolado de preparo**, nas duas cópias Temp, sem frontend que crie
um backend filho e sem instalar build-system. Isso é --no-isolation em
termos de ambiente; não executar python-mbuild nem setup.py de origem.
Fontes primárias consultadas: https://setuptools.pypa.io/en/latest/build_meta.html
e https://peps.python.org/pep-0517/#build-wheel . O projeto tem só backend
setuptools estático, sem backend-path/setup.py/setup.cfg/dynamic na cópia.
O hook pode gerar arquivos auxiliares/build/egg-info apenas nas cópias próprias.

Usar as ferramentas já existentes: setuptools84.0.0/wheel0.48.0 e
packaging26.3 para comparar Requirements do **wheel próprio**, não para I
dos wheels remotos. build1.6.1 medido mas não invocado. Versões/backend
build_meta.py pinados no procedimento; sem mudança de .venv. Capturar logs
limitados, ambiente process-local mínimo antes de importar backend, cwd
próprio, SOURCE_DATE_EPOCH fixo1980-01-01. Não há solicitação de rede ou
instalação; não se afirma firewall do host ou deadline absoluto do hook.

No Linux futuro, conferir modos/donos reais (sem escrita grupo/outros),
executáveis opcionais existentes explicitamente registrados e fora do
PATH operacional. Plugins OpenTelemetry fazem parte do uso da API,
não presumir que nenhum entrypoint é carregado em runtime. Manter
inventário das15libs próprias de psycopg-binary e medir libpq/OpenSSL.

## Código/procedimento preparado, antes do hook real

Novo docs/poc/oracle9_app_wheel.py: captura119arquivos/1.463.784bytes,
incluindo o pyproject917fe735 e os118arquivos de pacote/assets atuais.
Allowlist não segue links/reparse, recusa arquivos desconhecidos/especiais;
só cache __pycache__ ignorado após conferir que é diretório sem reparse.
Tetos:512arquivos/1MiB porarquivo/16MiB total; cópias xb e hashes dos
bytes reais, incluindo CRLF. O manifesto é comparado antes e depois dos
builds; não usar Git export nem modificar os incrementos anteriores.

I2bbcfd53 e resumoId2f0bfca pinados e admissãoD novamente antes do build.
Pyproject idêntico ao da resolução; raízes nominalmente iguais às
requested do relatório. Backend setuptools84.0.0 build_meta.py SHA
6f4a583e1b6bb0d5ef3af2ac0a6e9a033d06f364e4a550e3b112812674b38419;
wheel0.48.0/packaging26.3 conferidos, nada instalado. Hook PEP517 direto,
cwd e ambiente mínimos/restaurados no finally; logs até1MiB UTF8 também
preservados em falha. Backend e fonte são código próprio/toolchain já
instalado, não executar qualquer arquivo dos36wheels Linux no Windows.

Duas cópias próprias independentes, um hook em cada. Validar nomes/bytes
exatos dos118membros do pacote, só quatro metadados declarados, dez
RequiresDist+quatrodev comparados como Requirements do packaging26.3,
sem extras em runtime. I reaplicado ao wheel próprio, sem pth/entrypoints/
scripts/native. Hash dos dois wheels precisa ser idêntico antes de ready;
qualquer falha consome a raiz e preserva artefatos/logs, sem retry silencioso.

Testes novos19coletados:18passaram/1skip por privilégio de symlink Windows;
164relacionados:163passed/1skip. Só capturas pequenas/ZIPs sintéticos e
backend fake; nenhum hook real. Ruff/mypy strict do teste e format2 e
E9/F63/F7/F82 do script passaram, não lint integral do script laboratorial.

Raiz preparada: C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-app-wheel-20261026-b3566164,
taskff6942494ef84ada8d3384f943eb4c7b, invokedfalse. Programa
f72a611d2bfc5e89739727f414445b69058f916faf3caf3201bee046bfa26a44;
estadoe532a0ae16175866515be2e64b36976a964704c013c2407d558e8c41d7fff8df;
snapshot oracle9-app-wheel-procedure-v1-20261026.json SHA
2764c686a66461b52f71eb340354758a2aad437e8539f7b2644da39237f59773.
Raiz deve conter só state.json; conferir pins acima, inspector/resumoI,
backend/versões, manifesto de fonte e ausência de invoked.json antes de
executar. Fontes congeladas durante os dois hooks. Sem Docker/instalação,
rede solicitada, banco, carga, commit/push ou deploy.

Comando só após revisão deste código e procedimento:
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_app_wheel.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-app-wheel-20261026-b3566164'
exit $LASTEXITCODE
```
Esperado APP_WHEEL_BUILT_VERIFIED e dois wheels idênticos, não declarar
antes da medição. Resultado de recusa também deve registrar os limites:
o backend confiável não recebe um watchdog externo neste lote e o helper
não promete prazo absoluto do SO. Não usar o pacote como serviço pronto.

### Precisão P1 incorporada e execução v2

Revisão do código aceitou o procedimento após P1, sem nova revisão se o
delta fosse só inventário/guard de plugins e testes. Listados por metadata,
sem .load, cinco grupos de extensões setuptools. Artefato
oracle9-build-plugins-20261026.json/7.045bytes SHA
d3da970d913ff9f75c42e56d45437a2c68aabb78fc5ca850b2f2ea71496918c9:
46entradas, donos setuptools84.0.0/wheel0.48.0 e somente o keyword
cffi_modules de cffi2.1.1. O projeto não usa essa keyword. Guard exige o
conjunto exato, não só nomes/donos, antes de cada import/hook. Lista salva
na evidência; plugin estranho simulado recusado sem load.21novos testes:
20pass/1skip de privilégio symlink,166relacionados:165pass/1skip. Escopos
estáticos anteriores aprovados. Nenhum hook real invocado ainda.

Os dois hooks serão no mesmo processo: igualdade significa repetibilidade
observada nesse processo/cópias, não entre interpretadores ou garantia
geral de rebuild. SHA do backend fixa só build_meta.py; os demais módulos
do toolchain são admitidos por versão, não há attestation bit a bit de
todo o ambiente de desenvolvimento. Limitação explícita do build local.

Raizv1b3566164 não invocada e preservada. Raizv2final
C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-app-wheel-20261026-ad017213,
taskb0aeaaf146cf4a749f6dd60b07f1ae0c, invokedfalse. Programa
a964890b2b6a3acaea87fcaeb0f780f14c0bc4b4656d8f983fb24b3e32a38507;
estado616b125c63d48a6f713353c232af85cedb4733a447b66827e9aa27e05267d705;
snapshot oracle9-app-wheel-procedure-v2-20261026.json SHA
678b09f6cf4bca5c2f25b067aa34dbf12c8dacf85509e532b23907f612fbf584.
Manifesto119arquivos/1.463.784bytes igual ao v1. Conferir todos os pins,
plugins e estado fresco antes da execução única; fonte congelada até fim.
```powershell
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_app_wheel.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-app-wheel-20261026-ad017213'
exit $LASTEXITCODE
```
