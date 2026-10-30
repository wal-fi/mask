# T4 — fonte e builders públicos, sem coordenador operacional

2026-10-28, sob delegação. Direção e contratos W1–W7/O1–O5 revisados antes do
código. Implementação **pura** em docs/poc/w1_bootstrap_probe.py; nenhuma
chamada Docker, rede, container, processo ou seed privado. Nenhuma raiz,
estado, comando único ou serviço criado. O watchdog/coordenador concreto
continua sem implementação e precisa de revisão própria.

## Componentes

- Sete casos fechados, canário público fixo16384bytes com trailer no corpo.
- Loader argv recebe helper e6ca9e60 e fonte pública comprimidos; descompressão
  limitada65536bytes, SHA conferido antes de compile/exec, sem ler stdin como
  fonte. Código Python no container usa reader exato original, PID/UID reais,
  -I-B,3.11.13, cwd/Cap*/NNP/seccomp antes de READY. Não importa produto/PG.
- Corpo comparado byte a byte; relatos só igualdade/tamanho/EOF booleano e
  categorias fechadas. Nenhum hash do seed. Negativos usam pipe Linux local
  curto com EOF explícito, sem transitar frame inválido por outro transporte.
- Builder cria perfil proposto sem montar/copiar arquivos, RO128MiB/pids8/
  networknone. UID70 é numérico simulado para papelP, não PostgreSQL/Alpine.
- Posse por CID/nome/task/imagem/comando/3labels; aceitação separada confere
  Config/limits/superfícies. Identidade ainda reconhece o próprio recurso com
  perfil recusado, para permitir limpeza segura.

Manifesto público434bytes/SHA
bd3b78b02dee1bab7d78d703bab0c7e4086e3f2fc88b59c1108a1211641d5433,
fonte pública35dbbbcad95c6540ab9a56c4065f97e2ba0c2ae044218dc60a8b9bfacf5ef537.
Inclui helper/fonte/imagem/casos/perfil, sem nonce/segredo do ensaio.
Usa os3nomes de labels históricos sobrescritos, sem residual de identidade
antiga; label Desktop não presumido herdado. Teste próprio desse contrato
falhou antes do fix: o draft usava labelchannel novo e deixava manifest antigo
potencialmente herdado. Agora manifesto público real ocupa manifest-sha256.
O primeiro ENV escrito no draft também foi corrigido contra o fonte histórico
antes dos testes; não presumir PATH do venv no ENV, entry usa caminho absoluto.

## Medições públicas/fakes Windows3.11.3

**40 testes aprovados**,0,57s. Sete linhas create inteiras por list2cmdline:

| Caso | Caracteres | Margem até26000 |
|---|---:|---:|
| normal |12885|13115|
| retain |12879|13121|
| bad-ready |12891|13109|
| blackhole |12891|13109|
| flood |12883|13117|
| cancel-start |12897|13103|
| reader-negative |12903|13097|

Decoder limitado testado sem executar os programas decodificados. Import do
helper com branch sys.platformLinux simulado e definições do canário no host
não executam main. **Não é import Linux real**, que a T4 deverá medir.
Testes de Config/HostConfig/posse usam cópias do inspect histórico, sem nova
observação Docker. Drift de privilégios/limites/stdin/portas recusa; posse
permanece para recurso próprio, e identidade alheia é recusada. Oráculos
rejeitam campos extras/hash/prefixo de sucesso/tipos incorretos; EOFtrue/false
é informativo. Perfil ainda proposto, não instalado/medido.

Ruff integral/mypy3.11 do teste e lint E9/F63/F7/F82 do helper aprovados;
helper não é tipado estritamente. Erros iniciais de tipagem do teste foram
corrigidos antes da revisão. Código40c01f5c127ff6c5cb8811607a1f4f24e33caa77f642c0dae858b52870795d0a;
teste591766ddb12e14417fe6dea587910f2bd69aa4e65418632884e71ec5c6772d65.

## Limites

Código/fakes em revisão somente leitura. T4 não executada; não há afirmação
de StdinOnce/EOF/killCLI/handles no attach real. Script canário só será
executado depois do coordenador, perfil/estado/raiz/comando passarem suas
revisões. Não reutilizar estes oráculos como autorização de banco/segredo.
Sem mudança de produto, dependência, candidato621cc7f7 ou fontes consumidas.
B-1/B-2/D-090/C1/SQL/produção abertos. Sem commit/push/job/segundo escritor.

## Revisão: B1/B2 de posse e delta

Claude2 recusou40c01f5c: labels exatos na posse poderiam impedir remoção, e
identity recalculava comando relendo o helper. Testes novos primeiro:
**2fail**, label Desktop extra e fonte indisponível após captura. Correção:
Intent congelado captura argv **uma vez** antes de create; builder e posse
usam essa tupla sem fonte/disco. Posse confere3chaves próprias como subconjunto,
ignora metadado extra, mas recusa label próprio alterado. Aceitação continua
com labels exatos e pin atual do helper; fonte alterada impede aceitar/avançar,
sem impedir identificar/recolher o recurso próprio pela intenção original.

Recomendações incorporadas: loader usa if/SystemExit3, independente de -O,
antes de ambos os exec. A observação de EOF passa a ter janela fixa1,5s,
posterior à leitura/comparação do frame, dentro dos2s propostos. Relato usa
eof_observed e observation_ms reais, sem exigir chegada de EOF. Fakes de
EOF imediato/tardio/ausente/byte extra comprovam o teto lógico, não a chegada
real no Docker. Imutabilidade da intenção e criação sem releitura testadas.

**47pass/0,51s**. Código
e3cf9f4d5b6150c4c3d975fd17d6296348fa14b9e22a43543c9913d34361afd4;
teste1f07d0a3232ac924ecd483037680ea8aa215a4978db0a0f7d3fcd82db40c8ab2.
Fonte9dd1a21fdbea9e828a9baebf5ef490ba7b51c925763106c2c18de16552e5ee88;
manifesto434bytes/b42aeffd3e51ab7c46ec57061544ae5007a9815f1e4bfb134374abfe39982e6e.
Novas linhas completas: normal13055/retain13049/bad-ready13061/blackhole13061/
flood13053/cancel-start13067/reader-negative13073; margem mínima12927.
As medições e hashes anteriores ficam históricos, não são os do delta.
Nenhum efeito real, coordenador ou watchdog executável neste incremento.
