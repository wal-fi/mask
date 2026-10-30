# Próximo incremento — observabilidade da auditoria de imports, não relaxamento

**2026-10-21, plano histórico do incremento diagnóstico implementado/revisado.**
A segunda rodada real descrita na evidência parou na recusa nova do guard
de nome; depois corrigido separadamente em NAME-PLAN/NAME-VALIDATION.
As medições posteriores estão em ATTRIBUTION-VALIDATION. Nenhuma rodada
anterior virou aprovada por essas correções; este plano preserva o desenho
inicial. A primeira rodada permanece inconclusiva,
`PHASE-9-STAGE-8-LINUX-IMPORTS-VALIDATION.md`; não repetir aquele perfil.

Objetivo: saber qual regra/módulo faz a auditoria parar, mantendo as mesmas
origens, allowlists, fds, quotas e casos. Não legitimar módulo sem arquivo
por suposição ou wildcard, nem elevar AS32 ou limites do relatório.

1. `module_row` deve distinguir categorias fechadas FORBIDDEN, OUTSIDE_ORIGIN,
   UNOWNED_TOP, FILELESS_UNATTRIBUTED e OTHER, sem mensagem original.
2. No laço por módulo, emitir erro limitado com fase audit_error, etapa,
   nome de módulo validado (`[A-Za-z0-9_.]`, até200 caracteres), categoria e
   bools has_file/under_installed. Sem caminho absoluto, str/repr/traceback,
   valor de atributo ou ambiente. Nome inválido não é refletido; recusar em
   categoria OTHER e campo module=null (sentinela, não nome atribuído).
   Parar auditoria com código75, sem continuar, inclusive se a emissão do
   próprio erro falhar. O supervisor coleta EOF/returncode nesse último caso.
3. Cobrir também baseline **pré-import** (fase-1), coletado após GO e antes
   do estágio0; não confundir com ready anterior ao GO. Supervisor aceita
   audit_error só no estágio ativo correspondente, ou baseline antes do
   primeiro start. Evento mantém outcome inconclusive, nunca did_not_fit por
   memória. Não concluir que o erro de auditoria implica falha do import.
4. Para linha fora do protocolo ou collection_failed, registrar marcador
   fechado, esperar/recolher no prazo e capturar returncode. Sem copiar a
   linha recebida ou o corpo potencialmente indevido. EOF/sinal/timeout e
   exceção durante o próprio diagnóstico continuam distintos e fail-closed.
5. Testes puros das cinco categorias, linha inválida/longa, baseline e erro
   após módulo válido, erro de emissão, EOF e linha fora do protocolo com
   returncode. Preservar os110 anteriores, codec limitado e testes de cleanup.
6. Revisar código antes de qualquer novo caso. Uma nova rodada, identificada
   e separada da anterior, com o mesmo controle e caso limitado condicional;
   só serve para diagnóstico. Se audit_error ocorrer, parar sem AS32 e
   registrar. Possível correção de atribuição é outro incremento revisado,
   não fallback automático ou repetição até verde.

Fontes da rodada anterior existem congeladas nos artefatos temporários com
hashes na evidência. Alterações futuras devem indicar explicitamente que
nunca foram as fontes daquela medição. Produto/worker não entram neste lote.
B-1/B-2/D-090 e produção seguem abertos; nenhum commit/push autorizado por
inferência do parecer (publicação continua sujeita a gates/permissões).

Revisão pré-execução: Claude2 não encontrou bloqueador, mas recomendou
também tornar observáveis as checagens posteriores ao inventário. Incluído
no mesmo escopo diagnóstico, sem mudar aceitação: check_error/exit76 para
SOCKET_FD, CHILD, FD_SET_CHANGED, THREADS, PSYCOPG_IMPL, NATIVE_MISSING e
OTHER, com raiz nativa apenas do conjunto fechado ou null. Etapa-1 para
baseline,0/1/2 para checagem por import e3 para a verificação nativa final.
Supervisor valida schema/etapa/raiz e nunca classifica isso como mismatch
de AS32. Erro de import agora exige categoria/exit coerentes; parada por
SIGTERM é distinguida de TIMEOUT por STOPPED. Sem caminhos/alvos de fd.
Releitura somente leitura solicitada antes da execução sobre esse acréscimo.

Evidência deste incremento, separada da rodada anterior:
`PHASE-9-STAGE-8-LINUX-IMPORTS-OBSERVABILITY-VALIDATION.md`.
