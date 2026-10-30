# PG16 público — entrada e retenção do loop, somente fakes

2026-10-30, incremento sob delegação posterior ao checkpoint81ead94. Host
7275c8ae aceito10847 e metadados de portabilidade aceitos64823, já publicados.
Nenhum novo Desktop/DockerCLI/PS/container/PG/SQL/seed/credencial ou root nativo.
Import define funções; main exige argumento explícito de raiz nova válida.
Preparador/estado/comando próprios ainda não existem e não foram invocados.

## Fonte e contrato

`docs/poc/pg16_public_run.py`, SHA-256:
`88a3d43c3160f7f6f50815c41c80377e20bb02d664cc0d9752efe3035a88ab5e`.

Variante explícita da entrada835c consumida, sem editar/reexecutar o original.
Captura host7275 por hash; fontes4bc/b593 e colaboradores permanecem pinados.
Admissão exige Windows3.11.3 isolado/-B/sem optimize, raiz de nome PG próprio
no Temp esperado, somente attempt.json canônico FRESH/invokedfalse e schema/
pins/imagem/task fechados. Medida blueprint precisa coincidir antes de registrar
invocação. Checagem dos seis fontes stdlib e pins sem efeito de laboratório.
invoked.json é xb/fsync antes de phaseINVOKED, antes do ciclo A/B/qualquer spawn.

Fluxo: supervisão antes do foreground/ciclo herdado, journal12 e replay
verificados antes de B público; uma sonda, sucesso somente report/perfil/owner/
cleanup/inventários CID e volumes/restore/pins/journal todos positivos e
monitorjoined/nofire. SQL/worker/seed não entram neste chamador.

Incerteza de foreground/cleanup/tarefas/ticket/owner/join mantém HELD e o
mesmo loop, sem stop, segundo cleanup ou teardown automático asyncio.run.
Driver usa loop Proactor explícito; interrupção retorna ao mesmo loop sem
cancelar tasks próprias nem perder referências. Só fecha loop com context
released e nenhuma task pendente. Retenção operacional aguarda indefinidamente;
não é timeout que abandona tarefa ou promessa de teto do SO.

Restauração só depois do join e provas de recursos. A exceção de reconciliação
de volumes no restore, ou retorno desktop_restoredfalse, agora retém como
DESKTOP_RESTORE_UNPROVEN com categoria fechada, sem stop nem falsa atribuição
de interrupção do runner. Não tenta corrigir inventário externo ou repetir
rodada. Orçamento B90/pendência31/join55/restore93 do desenho continua269<600;
marcadores507/600 reprovam medição atrasada, sem impedir restauração segura
quando ela continua demonstrável. Nenhum aumento de limite durante execução.

## Testes e limites

31 testes aprovados em10,01s, Windows3.11.3, somente fakes. Seleção inicial
derivada27/27 em16,84s; quatro casos adicionados de restore incerto/volume
pós-join/retorno pending e obrigatoriedade da flag final de volumes passaram.
Esses quatro foram escritos depois da implementação; não são regressões
vermelhas primeiro. A diferença de duração não tem causa atribuída.

O teste normal exerce ciclo real herdado com nove observações simuladas,
12 arquivos imutáveis e replay real, preflight/perfil/CLI fake e uma sonda.
Negativos cobrem falha/cancelamento/prazo em B, owner/foreground/join incertos,
lock sem roubo, atraso507/600, root/estado/pins/reuso/canonicalização, measure/
admission-time antes de invoked, callback de emergência e interrupção no join.
Teardown de fake tasks existe só no teste; não altera regra de retenção do main.

Ruff src/tests, format325 e mypy strict311/314324 limpos; lint restrito do
helper limpo, sem alegação de helper mypy-strict. Sem suíte PG integral nova,
browser, build de pacote ou teste do SO de destino por este incremento.
Fontes consumidas e artefatos do checkpoint preservados. Em revisão própria
pelo Claude2 antes de exportador/preparador/proposta ou efeitos reais.

Gateway indisponível. B1 fim a fim/B2/D090gate2/C1, SQL, aceitação IDE/MCP/Admin
e produção continuam abertos. Nenhum job/quota ou segundo escritor.

## Finding99175 — categorias e origens

Fonte corrigida `a6089275cbbc3b9db251f587ec69f9bce5e892dcd093f1d285c1ae6efaff67be`.
Entrada88a3d43c recusada por reduzir falhas distintas a FAILED. O uso da
entrada835c como base trouxe de volta essa lacuna, já corrigida na T4v2;
achado aceito e corrigido antes de qualquer uso nativo.24 regressões de oito
origens nas três fronteiras failure/cleanup/restore falharam antes do fix:
24failed/31deselected em13,73s. Categoria e origem agora são pares fechados.

Classificador usa tipos exatos das classes capturadas do próprio Host, enum
Fault e args coerentes; subclasses, classes de outra captura, args malformados
ou origem desconhecida viram INTERNAL/INTERNAL. Não usa str/repr do erro.
Vocabulários literais materializados em código:179Runtime,19Probe,2Value,
34Bounded e4Emergency. Testes derivam os conjuntos por AST da cadeia de15
fontes pinadas e exigem igualdade exata; não há AST em runtime. O conjunto
Runtime é vocabulário de diagnóstico, não autoridade para operações.

O sampler e invoke de PS público criam namespaces bounded frescos. Suas
classes são reconhecidas só pelo tipo exato mantido no helper local dos dois
frames pais capturados: code-object e globals por identidade, e self do
mesmo Host em invoke. Nenhum nome de módulo, arquivo ou mensagem comprova
essa origem. Frame não reconhecido é INTERNAL. A inspeção do traceback é
limitada64 e usa o descriptor BaseException, sem hooks de exceção desconhecida.
Classes com metaclass/atributos hostis não têm seus hooks chamados.

Rodada ampliada deu61passed/1failed em25,25s: o teste de invoke usava o R de
outra captura do mesmo fonte. A âncora passou a ser o R capturado pelo próprio
Host, coerente com a regra já usada para os demais tipos. Cinco testes focados
de AST/origem fresca/opaco passaram em1,62s após ajuste. Não é evidência de
falha nativa nem causa atribuída ao SO. Gates finais registrados após a seleção.

KeyboardInterrupt no restore agora marca interrupted=true e mantém HELD;
divergência de volume continua sem inventar interrupção. Nenhuma mudança em
cleanup, tickets, prazos, pins, fontes consumidas, root ou configuração do host.

Gate final conjunto: **319passed em43,26s**, oito componentes PG16 públicos,
incluindo os62 casos atuais da entrada, sem skips/falhas/erros. Ruff src/tests,
format325 e mypy strict311/314324 limpos; lint restrito do helper limpo. Só
fakes, sem subprocesso nativo, DB, listener ou rodada Docker. Fonte a6089275
confirmada igual antes e depois da seleção. Rerevisão32225 aceitou o delta
isolado sob condição do resultado conjunto; condição atendida por essa saída
terminal exit0, sem falhas. Nenhuma alegação de release ou operação real.
