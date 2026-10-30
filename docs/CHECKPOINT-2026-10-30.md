# Checkpoint para continuidade em outro local

Criado por solicitação do usuário em2026-10-30. Inclui o trabalho acumulado
após4a5e556, preservando resultados históricos e tentativas reprovadas. É
checkpoint de desenvolvimento incompleto da Fase9, não release de produção.

## Estado atual

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

## Próximo incremento

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
O objetivo é impedir que core.autocrlf altere os hashes; verificação
por clone novo ainda pendente neste ponto. Nenhuma fonte consumida foi
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
nova verificação ainda pendente neste ponto. Não é teste de execução do app.
