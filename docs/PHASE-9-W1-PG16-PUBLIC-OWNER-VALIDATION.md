# PG16 público — owner do processo CLI, primeiro incremento

2026-10-29, sob delegação. Desenho6796/P1–P4 incorporados antes do código.
`docs/poc/pg16_public_owner.py`, SHA-256:
`a02f0b71311fabd44685606e36134c50b719ecf863de98f164268a04d6b54e4c`.
Capturas por hash de e6ca e perfilfe2f8ba8; ambos permanecem intactos. Sem
chamador operacional, CLI real, novo container/root ou processo do produto.

## Contratos

Oito overrides exatos sobre ManagedBootstrap; os demais métodos de lifecycle
são os mesmos objetos do canal consumido. Target do próprio namespace,
papelPG/imagemcf78/fonte pública fixa da task. Spawn exclusivamente CLIpinada/
contextdesktop-linux/start--attachCID, seminteractive, DEVNULL/PIPE/DEVNULL.
Admissão runtime e ambiente do e6ca mantidos; owner/task antes do await.
READY/send_seed/retain são recusados antes de qualquer efeito.

Input sem pipe provado por stdinNone+transport0None na adoção, também no pump
de adoção tardia. Final ainda exige wait/reap. FD1 mantém o PipeHandle exato/
handleNone do e6ca; input inesperado ou handle desconhecido/vivo não emitem
ticket. Quiesce/ausência posterior/close continuam herdados; não há liberação
por saída textual, tentativa de kill ou mera ausência anterior do CID.

Prazo absoluto12s, não renovado por chunks: admissão expirada não registra
spawn, drain não aceita buffer já completo após o prazo. Limite8192/reads4096,
erro/excesso limpam buffer e seguem drenagem/descarte até cleanup. Código
42/137 chega intacto com saída completa protegida ao parser, não é sucesso
do produto ou resultado de banco. Sem frame/seed nem parser privado acessível.

## Validação

Windows3.11.3:29testes novos; seleção owner/perfil/volumes **149passed em2,03s**.
Fakes de Process/StreamReader/PipeHandle; nenhum Popen/Docker ou handle nativo
novo. Timer independente de teste8s herdado como proteção do harness, não
watchdog operacional. Ruff src/tests e helperlint restrito limpos; mypy
strict311/314 em319arquivos limpos; format322 conforme, runtime só3113.

Primeira rodada do owner encerrou após18casos sem resumo/exit1; sem atribuição
definitiva do término. Encontrado no harness: prazo curto era injetado no
namespace do wrapper, não do corpo decorado. Corrigido para __wrapped__, sem
aumentar timer; seleção dos dois últimos passou e repetição integral ficou
verde. Não mascarou erro de produto com skip/xfail/retry.

Regressão da admissão expirada falhou antes do fix: ainda havia taskspawn
registrada. Agora recusa antes do registro. Teste do buffer após prazo foi
refinado para aguardar as tasks/eof antes de expirar: a primeira versão não
isolava esse caso e já passava, portanto **não foi red-first**. Contraprova
em namespace isolado, sem as duas verificações finais novas, falhou com
DIDNOTRAISE; arquivo/depêndencias não foram alterados por essa contraprova.
Fonte atual passou. Mantida a distinção entre regressão e contraprova.

## Estado e próximos gates

Owner aceito isoladamente pelo Claude2 (70705), sem bloqueador. Notas de
integração: adoção tardia de processo já encerrado pode tentar input-close
antes do pump, depois de um start já reprovado; não vira sucesso. Qualquer
falha de drain pode deixar CID vivo e exige quiesce/posse/ausência posteriores.
Adapter/watch/emergency PG próprios,
integração de volume/posse/CLI fake, host/entrada, portões de evidência,
preparador e proposta única ainda faltam. Nenhuma nova rodada nativa ou
prova de DEVNULL em Docker foi alegada; e6ca privado não foi alterado.
Sem SQL/segredo/PG real/serviço/commit/push, quota/job ou segundo escritor.
Gateway indisponível; B1/B2/D090/C1 e produção continuam abertos.
