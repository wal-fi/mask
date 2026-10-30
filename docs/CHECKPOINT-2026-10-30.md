# Checkpoint para continuidade em outro local

Criado por solicitação do usuário em2026-10-30. Inclui o trabalho acumulado
após4a5e556, preservando resultados históricos e tentativas reprovadas. É
checkpoint de desenvolvimento incompleto da Fase9, não release de produção.

## Continuidade posterior ao checkpoint81ead94

Entrada pública PG16a6089275 implementada e aceita pelo Claude2 (32225),
com319 testes conjuntos aprovados em43,26s; condição do parecer atendida.
Estáticos324 limpos, só fakes; nenhuma execução PG16 ou serviço ativados.
Próximo: exportador S1 próprio que retém local-* e baseline completa, depois
preparador/proposta/estado/raiz/comando revisados antes de uma rodada única.
Os contratos de HELD e diagnóstico constam em PUBLIC-ENTRY-VALIDATION.

Incremento de entrada commitado emf51d63a; clone novo autocrlftrue confirmou
698/698 arquivos sem diferenças, com entradaa6089275 preservada. Prova em
`docs/poc/evidence/checkpoint-entry-portability-20261030/verification.json`.
A publicação e o HEAD mais recente devem ser conferidos pelo Git. Novas
medições continuam só de fakes/bytes, sem iniciar serviço ou banco.

## Estado no checkpoint81ead94

- Destino aceito: Docker local nesta máquina, Oracle Linux9.8 sobre WSL2.
  Não presumir esse mesmo destino, daemon, imagens, pins ou credenciais em
  outra máquina. Confirmar o novo ambiente antes de efeitos nativos.
- Último laboratório real: T4v2/task42d363a1, exit0, sete owners liberados,
  sete CIDs removidos, Desktop restaurado Off; transporte3a274347 aceito39884.
  Fontes/raízes consumidas não podem ser alteradas ou reexecutadas.
- Núcleos B1/snapshot, resultado tipado/encoder/receiver, job/worker privado,
  guard Linux e instalação Oracle possuem evidências próprias em docs/.
  Não são integração fim a fim ou permissão operacional de SQL.
- PG16 público: perfilfe2f/owner a02f/adapterf1d9/volumes6e38 e watchb868/
  emergência54cc aceitos em revisões próprias. Novo coordenador7275c8ae
  aceito10847 após correções,39 testes simulados aprovados. Sem entrada,
  exportador, preparador, estado, raiz ou execução PG16 novos.
- B1 fim a fim/B2/D090gate2/C1 continuam abertos, SQL PGWire continua recusada.
  Gateway indisponível para teste IDE/MCP/Admin ou produção. Nenhum banco
  existente ou credencial antiga de aceitação deve ser utilizado.

## Próximo incremento registrado em81ead94 (histórico)

Implementar entrada PG16 pública sobre o coordenador aceito, com driver que
retém loop/owners em HELD e captura falha de reconciliação no restore como
categoria fechada, sem Desktopstop nem falsa interrupção do runner. Depois,
exportador S1 próprio (retém todos `local-*` e baseline completa), preparador,
proposta de estado/raiz/comando e revisão antes de uma única execução nativa.
Somente ferramentas/versões/UID/tmpfs públicos, sem initdb/SQL/seed privado.
Leitor shell e laboratório privado PG16 são passos posteriores com gates próprios.

As instruções de autonomia e de revisão pelo Claude2 continuam em AGENTS.md.
Não iniciar segundo escritor nem reexecutar tentativas históricas. A revisão
mais recente está em docs/CLAUDE2-PENDING-REVIEW.md; não há quota/job ativo.
Não pedir novas aprovações por lote para o escopo já delegado.

## Portabilidade e dados locais

O Git contém código/testes/documentos e evidência pública exportada. Imagens
Docker locais, wheels/RPMs no Temp, ambientes Python/Node, raízes de laboratório,
credenciais e dados privados não estão incluídos. Referências históricas a
caminhos/pins Windows são fatos de medição, não configuração pronta em outra
máquina. Preparar novo ambiente isolado e reprovar pins divergentes; nunca
reduzir verificações só para conseguir executar.

`.gitattributes` estabelece preservação de bytes exatos em docs/poc, deploy,
pyproject.toml e fontes Python src/tests, inclusive CRLF já medido. A comparação
do índice encontrou várias fontes históricas CRLF, além de postgres.py/result.py;
por isso todas as fontes Python usam preservação exata, sem normalização.
O objetivo é impedir que core.autocrlf altere os hashes; a segunda verificação
por clone novo confirmou os bytes no escopo abaixo. Nenhuma fonte consumida foi
renormalizada. Fixtures de tests também preservam bytes exatos. Configuração
.codex/.claude local, stackdumps e systeminfo ficam fora
do checkpoint e são preservados no disco.

Varredura dos candidatos encontrou só três URLs sintéticas nos testes de
recusa de proxy/URL. Nenhuma chave privada/token/credencial real detectada;
essa varredura é limitada por padrões e não equivale a DLP. Novas saídas do
daemon não foram coletadas: a correção de minimização foi medida só por fakes.

Seleção final dos sete componentes PG16 públicos:257passed em16,70s, só fakes.
Estáticos atuais: Ruff e mypy strict alvos3.11/3.14 em323 arquivos limpos;
runtime medido Windows3.11.3. A suíte PostgreSQL integral e os pacotes de
incrementos anteriores mantêm seus resultados nas evidências; não foram
reexecutados para este fechamento de checkpoint. Nenhuma alegação de
validação integral nova ou de disponibilidade de produção.

## Primeira verificação por clone novo

Commit7875dc8 clonado localmente em diretório novo, sem hardlinks, com
core.autocrlf=true:693/694 arquivos de fonte/evidência iguais, pyproject917fe735
e fonte histórica CRLF preservados. Um fixture JSON (phase7-ui-off.json)
foi convertido por autocrlf; rodada reprovada preservada em
`docs/poc/evidence/checkpoint-portability-20261030/verification.json`.
Acrescentada proteção de bytes para tests/fixtures, sem editar o fixture;
nova verificação concluída abaixo. Não é teste de execução do app.

## Segunda verificação por clone novo — aprovada

Commit5dc1f6a clonado em outro diretório novo, sem hardlinks, com
core.autocrlf=true: **695/695 arquivos comparados, zero diferença de bytes**.
Escopo: docs/poc, deploy, src, tests e pyproject.toml rastreados naquele
commit, incluindo a primeira medição reprovada. Fonte histórica CRLF,
pyproject917fe735, fontes e fixtures preservados. Evidência pública em
`docs/poc/evidence/checkpoint-portability-20261030-b/verification.json`.
Não houve execução de aplicativo, Docker, banco ou laboratório nativo.
As duas cópias locais de verificação estão no Temp, fora do Git; não são
instalações nem ambientes operacionais. A cópia dos bytes não certifica
o ambiente externo de outra máquina, conforme os limites acima.

Rerevisão64823, sessão51ea0d85: metadados e prova do clone aceitos para
checkpoint incompleto, sem bloqueador e sem declarar release. Depois de
5dc1f6a mudaram somente registros/documentos de fechamento, sem alterar
fontes executáveis, fixtures, atributos ou os bytes medidos.
