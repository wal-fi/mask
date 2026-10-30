# Oracle9 — bundle público baixado e conferido

2026-10-23. Estágio D v6 aceito na revisão15171 e executado **uma vez**,
exec8868 terminal0, BUNDLE_DOWNLOADED. Root499ec65a/task2fb1281f.
Nove curl exit0, status200/URL literal, magicRPM e hashes conferidos.
Total dos RPMs19.806.175bytes, maior12.654.764, abaixo dos tetos declarados.
Nada instalado ou executado no Windows; nenhum Desktop/Docker nesse lote.

Bundle tem13 arquivos regulares: nove RPMs, probe público e três arquivos
de manifesto/headers/hashes. Check_bundle executado novamente após D:
nomes, bytes, hashes, auxiliares exatos e ausência de extra/link/reparse
passaram. Manifesto SHA256
`21c5165685cf730cb8912eff244a9be182884e181b48b42df50ff518c7d35e41`.
Estado bundle_readytrue/download_invokedtrue, mas invokedfalse, unobserved
e sem phase. Assinaturas/headers reais só serão verificados no Linux;
transporte com hash não foi chamado de autenticação de pacote.

Cópia imutável dos originais e resultados:
`docs/poc/evidence/oracle9-rpm-download-result-20261023.json`,10.015bytes,
SHA256 `5d28e938a691a18c3f6cccac9abf0fa2b63029760a997d6d7d56840ece9e4897`.
RPMs continuam no Temp próprio, não copiados ao repositório ou wheel.
Ainda não há imagem Python/gateway. B-1/B-2/D-090 e SQL seguem abertos.

## Refinamento do B antes de sua revisão

Fonte v7, sem repetir D, antes de qualquer A: copiar bundle para diretório
nonce na raiz do container, que existe por definição. Bash deve iniciar
e então exigir /opt diretório e /opt/maskgw ausente, sem symlink; mover
somente input próprio para lá. Copiados normalizados e conferidos0:0/644,
diretório0755. Sem suposição de semântica cp sobre /opt inexistente.
Base também deve declarar Cmd/bin/bash conforme configuração OCI pinada;
a presença executável efetiva será testada pelo startup, com falha fechada
e sem fallback. Não foi declarada comprovada por Git Bash ausente no host.

RPM CLI normal -ivh instala a documentação dos nove RPMs: diferença
explícita da v5 --nodocs. Ela é pública e passa pelos mesmos guards de
owner/modo/diff/limites. Não muda RPMs, bytes de input ou payload.

Estado program_sha atualizado para o B v7 ainda não consumido; origem D
v6 e manifesto original preservados. Copias/pins v7:
`docs/poc/evidence/oracle9-python-procedure-v7-20261023.json`, SHA256
`94cbbf7710f8e362e5021c7bcba0405e87385d992dabf316024384f621f46671`.
Host5653bad08dba71a9fd89cde0893a25a29ccfc0d80f0b78363f4ab64b69a72bf1;
payload32a1a972.../download7b610a37.../A-control-restore inalterados da v6.
59 testes puros, Ruff/format/mypy dos dois testes passaram novamente.
Próximo: revisão desse manifesto/roteiro e só depois A/B/C uma vez.
