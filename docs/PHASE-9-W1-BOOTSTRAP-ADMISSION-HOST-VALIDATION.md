# Admissão — integração privada, sem execução real

2026-10-28: código em revisão; nenhuma raiz/estado/comando operacional de
admission, novo DockerCLI/processo/thread do produto. Desktop continua Off.
Núcleo9612/71 e cinco hooks aceitos antes da integração; T4 reprovada0566
e fontes consumidas88e2/835c/c789 intactas.

## Variante explícita

`docs/poc/w1_bootstrap_admission_run.py` é variante nova do entry835c, com
captura pinada do núcleo, classe DiagnosticHost, kind/root específicos e
condição/outcome ORACLE9_ADMISSION_CAPTURED de **duas medições**, sem release
de perfil/T4. Teste AST confirma handlers/join/retention/driver/ciclo sem
alteração e diferenças fechadas em admit/prepare/category/run. Não há AST
transformado em runtime ou rebind oculto de classe. Prepare chama a classe
explicitamente. Cinco overrides da classe, demais métodos mesmos objetos88.

Raw fica somente em Temp no experimento futuro. Captura xb antes de parse,
guarda de publicação com CID/nome do registro, relatório campo a campo e
categoria do validador original. Retorna info apenas por posse comprovada;
diferença de perfil vira medição, nunca admissão de transporte. _case sempre
recusa. Dois perfis sequenciais usam create_args e3cf sem start/attach/seed,
depois _collect conhecido, ausência e remoção. Privacydenied reprova depois
da coleta própria, antes de outro create. State vivo reprova, captura de
cleanup não conta como admissão. O inspect direto inicial de cleanup não é
arquivado, marcado false no resultado. Captura síncrona>3s reprova ao voltar,
não promete interrupção de syscall. Matriz80/caso36 e demais caps preservados.

## Medições

17passed/4,69s Windows3.11.3, apenas fakes/arquivos públicos: fluxo herdado
com12checkpoints/replay/dois perfis/join/restore, perfil aceito e hipótese
StdinOncetrue ambos capturáveis sem declarar transporte pronto; raw antes
de parse/segunda cópia herdada idêntica, colisão preservada, malformação,
State vivo/coleta, Envproxy fictício sem valor no relatório, zeroattach,
createincerto retido sem retry/restore, pins estendidos antes do núcleo,
arquivo mutável recusado fora de cleanup/captura aceita nele, configproxies
recusada, kind/root cruzados, estado fechado/reuso e atraso de captura.

Primeira seleção9/9/1,97s, ampliação17/17 acima. Mypy src/tests309 limpos nos
alvos311/314 (runtime só3113). Ruff inicialmente encontrou imports e uma
linha longa no teste; corrigidos antes do fechamento. Helper só lint
restrito E9/F63/F7/F82 e format, sem declarar strict helper.

## Ainda pendente

Exportador que aplica S1 a **cada** alias raw, incluindo inspect-before e
cleanup, com manifesto de hashes/recusas sem valores privados. Não alegar
sigilo ponta a ponta antes dessa implementação/revisão. Depois revisão do
preparador/estado/comando próprios antes de qualquer novo efeito real.
Sem raiz/materialização/DockerCLI/seed/PG/SQL ou mudança de produto neste lote.

## Revisão aceita e preservação de relatório nas falhas

09302ef2/17 aceito pelo Claude2 de forma estreita. Recomendação1 confirmada
com duas regressões vermelhas antes: KeyError do validador e desacordo com
o núcleo deixavam de gravar o relatório,2failed/17deselected/0,91s.
Delta grava campos em xb antes de chamar o validador, captura Exception como
categoria fechada (nunca mensagem), salva completed/category/agreement e
só depois aplica os gates de aborto. Não remapeia INTERNAL para SOURCE_PIN:
preserva categoria fechada original. Relatórios parciais não contam como
uma das duas admissões concluídas.20passed/5,01s finais, Ruff/mypy309311/314
limpos, execução só3113. A guarda temporal também recusa intervalo negativo.

Recomendação2 registrada como limite: o teto3s pós-retorno também vale nas
capturas de cleanup e pode causar HELD em lentidão, sem alegar teto do SO.
Nenhuma medição de parse real31KB foi inventada; raw da rodada anterior não
existe. Delta em rerevisão; exportador ainda ausente, nenhum efeito novo.
