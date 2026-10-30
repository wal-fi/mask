# Diagnóstico de admissão — dois perfis medidos, transporte ainda não testado

2026-10-28: uma execução, **ORACLE9_ADMISSION_CAPTURED/exit0**. Não é T4,
aceitação do perfil, liberação de canal/PG/SQL/produção ou serviço disponível.
Os containers foram somente criados e inspecionados, nunca iniciados.

## Procedimento

Runner7c113617/core9612/preparador1b069987/exportadorbeeb85d6 e proposta
aceitos pelo Claude2 antes de materializar. RootTemp
`maskgw-oracle9-admission-20261028-2dd94bfb4502755ce8fa8cd496f637c8`,
task34346ce8ed18f936d482c3c19aaeb04f.2392bytes de estado/SHA24d647a0 iguais
byte a byte à proposta, apenas attempt.json, comando idêntico. Script
a17e4275 invocado uma vez19:14:58.9736169Z, DesktopOff. Não houve ajuste
em voo, repetição, CLI manual, start/attach/owner/seed, PG ou outro escritor.

12checkpoints xb/replayB_CONSUMED, A→B119156ms, cabeça
f6d2b746fad5127b7830483c8db64f399656799b170fa833f8d15055b2e2b841,
igual ao result. Imagem621/config exatos admitidos antes de B.

## Medições, sem atribuição retroativa

NormalUID10001 e retainUID70: Statecriado/Pid0, OpenStdintrue,
AttachStdin/Stdout/Stderrtrue, Ttyfalse. **Única divergência de predicado:
Config.StdinOnce, esperadofalse/observadotrue em ambos.** Validador original
retornou CONFIG, profile_acceptedfalse. Todos os outros predicados medidos
concordaram. Três labels próprios, valores corretos; apresentação ausente
nos CIDs, mantendo a diferença imagem4/CID3. Sem supor causa no Desktop.

A fonte oficial29.7.2 confirma o caminho de parse compatível, mas agora o
booleano é uma observação do host, não só hipótese. Isso não recupera o raw
perdido da T4 anterior nem prova qual campo daquela observação31711 divergiu.
A próxima revisão de perfil pode usar esta medição nova, preservando a
rodada anterior como NOT_PASSED e sem alterar seu aceite.

## Coleta, publicação e limites

33comandos registrados, todos0 (18DockerCLI/15PS registrados, amostras do
helper clock separadas). Dois CIDs próprios confirmados e removidos semforce,
ausências individuais e inventários vazios. Watchdognão disparado/heldfalse/
threadjoinedtrue; owned_cleanup/inventory_restored/desktop_restored/
inputs_unchangedtrue. Desktopstop13,391s/exit0, after-stop vazio e
OFF_CONFIRMED. Relido Off19:18:42.2818895Z sem CLI. Nenhum recurso vivo pendente.

Só depois de exit0 e provas terminais, uma chamada ao exportador pinado
recalculou S1 em cada raw/alias e varreu chaves privadas de todo metadata.
**33fontes/33publicados/0retidos**; todos os gates permitiram. O raw local
não foi lido em ferramenta/conversa nem copiado antes desse filtro. Quatro
cópias raw (duas admissões e dois inspect-before) foram publicadas com
hash/tamanho e releitura de origem. Inspect direto de cleanup não foi
arquivado; hashes registrados iguais aos da admissão em cada perfil.

Transporte em `docs/poc/evidence/oracle9-admission-run-20261028-34346ce8ed18/`,
SHA4f7717771d6c12c678536c457ffe6a230b7d6fad5d0467c8d7b3276c266911ea.
Console.txt é suplemento da saída do comando. Fontes/raízes T4 e diagnóstico
agora consumidas, congeladas, não reexecutar ou editar. Nenhuma credencial,
listener ou banco existente foi usado. B-1/B-2/D-090/C1 e produção abertos.

Próximo: revisão factual deste resultado; desenho de novo perfil estrito
com StdinOncetrue medido, preservando todo o restante e S1, antes de novo
código/estado/comando e de qualquer sonda completa de transporte.
