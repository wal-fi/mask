# T4 — binding privado do coordenador

Estado em2026-10-28: implementado e em revisão somente leitura; **sem
entrypoint operacional, raiz, estado, DockerCLI ou thread nativa novos**.
Não habilita serviço, SQL, PG16 privado, B-1/B-2/D-090 ou produção.

## Escopo e contratos

`docs/poc/w1_bootstrap_t4_host.py` carrega definições congeladas v2/baseline
por hash e nunca seus mains consumidos. Os12 overrides declarados e os
métodos herdados de save/journal/start_cycle/sampler/restore_desktop são
verificados por identidade nos testes. Transporte/install/watchdog antigos
recusam; CLI chama diretamente o baseline, sem hook commit da v2.

Intent completo xb antes de create, owner antes de start e captura imediata
de nascimento pelo handle original. Cleanup usa identidade capturada e
observação nova depois de quiesce/ticket; ausência antes de ticket não serve.
Create incerto, recurso não recolhido ou join não comprovado mantém HELD.
Metadata de monitor só é lida depois de join positivo.

Matriz400s/caso54s/cleanup22s, tentativa única futura, sem ampliar prazos em
voo. Cálculo e alteração da ordem inspect→ausência no design correspondente.
O método de leitura de relatório/oráculo e os tipos de receipt são reais
nos testes; CLI e owner são simulados. Nenhuma alegação de EOF ou sucesso do
Docker é extraída dessas simulações.

## Medições

Windows/Python3.11.3, `pytest tests/test_w1_bootstrap_t4_host.py -q -o addopts=`:
**29 passed/3,59s** na árvore final desta rodada. Ruff src/tests limpo;
mypy strict alvos3.11 e3.14:305 arquivos sem erro. Execução só3.11.3.
Helper docs/poc passou somente lint restrito E9/F63/F7/F82 e format; não
declarar tipagem estrita desse helper.

Primeira execução do harness:9 falhas/11 pass. Erros do harness: nome view
inexistente (API correta Store.read), atributo de heartbeat errado e método
herdado restore inexistente (correto restore_desktop). Foram corrigidos nos
testes, sem mudança funcional para satisfazê-los. Repetição20/20; ampliação
para29/29. Primeiros checks estáticos também reprovaram por imports, lint e
anotações do novo teste; corrigidos antes dos checks finais acima.

## Pendente

Revisão do binding e dos contratos; depois entrypoint com admissão, posse
durável, parada/HELD sem encerrar loop com spawn pendente e fakes de fluxo
inteiro. Somente após revisão desses componentes preparar raiz/estado e
comando exato de uma nova rodada T4 pública. Nenhum efeito novo autorizado
por este documento; a delegação do usuário permanece com seus gates.

## Revisão de binding — três bloqueadores antes de qualquer T4

Claude2 rejeitou a primeira versão651ebe97: B1 flood chamava drain esperando
saída de produtor infinito; B2 timeout2s deixava só0,5s após observação EOF;
B3 retain podia fechar com ausência e pular a prova de CID vivo. Três testes
novos falharam no código anterior (3failed/29deselected/3,44s), reproduzindo
respectivamente chamada indevida de drain, timeout real2s e falta de recusa.

Correções: flood observa fault do pump com prazo2s, sem drain/EOF; relatórios
têm4s explícitos (1,5s observação +0,8s atraso simulado passaram); retain
exige inspect bem sucedido e RunningTrue no caminho de oráculo. Recuperação
final sem oráculo ainda recolhe e fecha owner de CID já ausente, sem sucesso
do caso. Fonte aceita do canário/canal não mudou.

Nova soma antes de qualquer efeito: caso56s, sete392s +22margem =414s matriz;
mais28 pendente +93restore +50join =585<600, margem15s. Substitui54/400/571
apenas neste desenho não executado, sem ajuste de prazo durante medição T4.
Teste32/32 passou8,06s; Ruff/mypy311/314305 limpos. Delta em rerevisão.

## Proposta de label herdado — REJEITADA antes da materialização

**A premissa de herança abaixo estava errada neste ambiente.** A revisão
conferiu o inspect real do CID e rejeitou1f708765. Nenhum Docker/raiz foi
executado/materializado com essa proposta. O texto seguinte é histórico,
não uma afirmação vigente sobre comportamento do Desktop.

Binding88e2 aceito. Conferência do candidate-image.json pinado mostrou label
`desktop.docker.io/ports.scheme=v2` da imagem621. Supus, incorretamente para
este perfil medido, que create herdaria esse label; e3cf exigia só os três próprios.
Harness anterior substituía todos os labels e escondia a incompatibilidade.
Regressão usando exatamente os labels da imagem falhou antes do fix:
1failed/32deselected/0,80s, categoria CONFIG. Nenhum Docker foi executado.

Binding atual1f708765 exige exatamente os três labels próprios mais aquele
label conhecido/v2. Cria view local apenas de Labels para delegar os demais
campos ao validador e3cf congelado, preservando objeto medido/raw originais.
Não tolera label extra, valor diferente ou ausência do label conhecido na
aceitação. Cleanup continua por identidade própria/subconjunto e captura,
aceitando desvios de apresentação sem alterar posse. Imagem/config exatos
continuam obrigatórios no preflight. Canal/canário/emergência/watchdog não
mudaram, nem código de produto, imagem ou comando create.

Quatro testes novos, incluindo as três recusas e cleanup; host36, entry27 e
preparo9: seleção72passed/15,84s. Ruff/mypy311/314307 limpos. Entry8580/prepFDA9
só atualizam pins da cadeia. Delta/perfil em revisão antes de qualquer A.

### Correção depois da rejeição

O inspect real `probe-inspect-before.json`, da mesma imagem621, contém só
os três labels próprios. A causa no Desktop não foi medida; não atribuí-la.
Proposta1f revertida: host voltou **byte a byte88e220eb**, entry835c2e21 e
preparadorc7892639 já aceitos. Teste de premissa de herança foi substituído
por teste dos dois registros reais: imagem4/CID3. Dois negativos adicionais
recusam quarto label no CID e preservam cleanup por posse. Não alegar que
esses testes corrigidos falharam antes da reversão: foram medidos depois.
Seleção final host35/entry27/preparo9:71passed/16,07s. A seleção72 anterior
fica histórica, mas seus testes de label codificavam uma premissa inválida.
