# loaded-as128 — protocolo proposto e núcleo puro

**2026-10-21 — desenho sob delegação, antes de código; sem execução.**
Complementa LOADED-MEMORY-PLAN, com D1–D3 resolvidos abaixo. Não muda AS32,
quotas de produto ou os resultados das seis rodadas preservadas. Próximo
incremento proposto é só núcleo puro/testes do protocolo em docs/poc, sem
harness de pressão, subprocesso ou Docker. Código e comando reais terão
revisões próprias antes de qualquer caso. B-1/B-2/D-090 continuam abertos.

## D1: digest por argumento fechado, sem mutar mount

Escolha(b): futuro Cmd exato do supervisor inclui `--case control|private|shared`
e `--expected -|<sha256>`; control exige -, os128 exigem64 caracteres hex
minúsculos. Perfil/entrypoint/argumentos devem ser conferidos por inspect,
não interpolados em shell. Sem -e, novo arquivo mutável ou linha de dados.
Só o supervisor recebe o digest; o membro recebe case e não precisa do hash.
Não é segredo, autenticação ou opção de produto. Perfil ainda não implementado.

Digest é SHA-256 de JSON ASCII canônico (separadores compactos) da lista
ordenada das linhas [nome,owner,origem], desconsiderando etapa. Antes do hash:
mesmos tetos1500 linhas/768 caracteres por campo/1MiB do inventário antigo,
sem nome duplicado (mesmo com owner/origem igual). Reusar validate_inventory
do probe antigo via colaborador confiável, além dos limites locais; não
criar outra regra de origem. Bytes exatos: SHA-256 de b"loaded-as128-v1\n"
seguido do JSON ASCII compacto das linhas ordenadas lexicograficamente.
Uma única função calcula hash no host/supervisor, com vetor conhecido em teste.
Hash do controle **deste lote** só é entregue após controle inteiro válido,
descarte privado confirmado, membro exit0 e cleanup comprovado. Nunca usar
digest da sexta rodada nem de controle que só completou imports.

Coletor confiável do supervisor deve verificar o fluxo de imports/origem/
native_check/efeitos e reconstruir as linhas. Só então chama a barreira pura
com essas linhas, limites e VM, todos fatos já coletados. O núcleo calcula
o digest: divergência impede qualquer comando PRESSURE. A aprovação do
coletor não pode ser substituída por booleano alegado pelo membro. O núcleo
puro não comprova SO, execução do coletor ou integração dessa barreira.

## D2: amostra, reserva e relatório

Antes de ready: reserva explícita mmap privado anônimo2MiB, páginas tocadas,
e buffer de relatório<=1KiB, nos três casos; tudo no baseline/cap. Importar
mmap/resource antes do baseline em todos os membros igualmente. Futuro
harness declara seus próprios nomes/paths exatos como harness; nenhuma
regra de origem genérica, modificação dos probes antigos ou import arbitrário.

Pressão só em alocador próprio, degrau4MiB/target40MiB. Blocos tocados e
retidos; primeiro bloco recusado é inconclusivo. Capturar limits/VM/bytes/
páginas/blocos/categoria/errno **antes** de fechar reserva, sem liberar
payload. Depois de recusa limitada, close da reserva devolve espaço virtual
antes de formatar/escrever a linha pequena. Não usar inventário/repr/erro
original no caminho de recusa; testes futuros do produtor exigirão a ordem
amostra -> close reserva -> emissão, inclusive falhas. Reserva não garante
recuperação de todo OOM; ausência/erro de emissão é inconclusivo.

Evento held (JSON ASCII, campos exatos,<=1KiB incluindo newline): phase,
kind, limits, vm (size,peak,rss,threads), accepted_bytes, touched_pages,
blocks, failure (NONE/MEMORY/ENOMEM/OTHER), errno (null ou inteiro limitado).
Aceito precisa ser múltiplo4MiB, blocks=accepted/step, pages=accepted/4096;
MEMORY implica errno=null, ENOMEM implica12; recusa exige accepted<target.
Control só vale com NONE/null e target40MiB em cada alocador. Limited só
observa imposed com recusa de memória, bloco anterior, limits128 e pico<=cap.
Nos casos128, pico acima do cap ou40MiB sem recusa é fail; demais falhas
inconclusivas. Controle tem limits[-1,-1], target completo/NONE/null e
descarte confirmado: pico acima de128 é esperado e **não** o reprova.

O futuro supervisor recebe held, confere protocolo/inventário e amostra
cgroup e /proc/<pid>/status/limits enquanto o membro **ainda retém o payload**.
Limites devem concordar; por conservadorismo picos declarados/observados
devem concordar (ambos<=cap em128), senão inconclusivo. Size/RSS não precisam
ser idênticos, pois reserva já pode ter sido fechada depois da amostra do
membro. Diferenças não são corrigidas/subtraídas. Só depois envia RELEASE.
Amostras de descarte vêm diretamente do supervisor, até5, sem comandos
extras de amostra ao membro.
ACK não afirma limpeza nem libera orçamento de produto. EOF/linha extra,
exit divergente ou cleanup incerto invalidam o outcome, preservando dados.

## Estados e comandos (uma instância por membro)

1. READY: limits/VM/pid/ppid coletados/conferidos; GO_IMPORTS.
2. IMPORTING: coletor confiável executa auditoria existente; sem pressão.
3. ADMITTED: digest calculado e comparado; limites após imports conferidos.
4. PRESSURE: conferir getrlimit/VM novamente **antes** de emitir comando
   PRESSURE_PRIVATE ou PRESSURE_SHARED. Uma vez por alocador, ordem fixa.
5. HELD: validar linha pequena e amostrar cgroup/inventário; RELEASE_PRIVATE
   ou RELEASE_SHARED somente após amostra pelo supervisor.
6. RELEASED: descarte lógico pelo produtor e VM pós-liberação coletada.
   No controle privado exigir VmSize<=pré-pressão+4MiB e queda anon>=32MiB
   do platô, com até5 amostras/1s, sem relaxar, antes de PRESSURE_SHARED.
7. FINISH: depois de último released, FINISH -> done -> EOF limpo/exit0.
   Só cleanup confirmado/final_inventory=[1] permite resultado diagnóstico.

Mensagens/comandos fora da ordem, duplicados, nome/campo extra, NaN, tipo
errado (bool não é int), limite divergente, timeout, prefixo/sufixo de
linha ou falha de callback fecham o núcleo em ABORTED e nunca retornam
outro comando. Sem retry/resync. No controle, qualquer resultado diferente
de control_ok interrompe antes do segundo alocador. Em128, imposed é só
observação e só vira resultado final após saída/cleanup comprovados.
ABORTED também proíbe RELEASE/FINISH: o chamador faz kill/reap e coleta.
Morte do membro não é descarte medido bem-sucedido. No controle, ADMITTED
calcula/guarda digest sem compará-lo (--expected -); em128, digest ausente/
divergente aborta inconclusivo antes de qualquer PRESSURE.

## D3: um orçamento de tempo, sem renovar por fase

Prazo absoluto monotônico20s do supervisor, capturado **antes do spawn**;
cada transição lê o mesmo deadline. Inclui ready/imports/digest/pressão/
ACKs/descarte/EOF/exit. Member tem prazo próprio<=20s desde entrada, mas
não renova a autoridade do supervisor. Esperas usam saldo; coleta não
ganha20s novos depois de import.30s externo/caso e120s/lote permanecem.
Cinco amostras de descarte1s também consomem esse saldo; não iniciar espera
de1s sem saldo inteiro. Deadline esgotado é inconclusivo e segue cleanup,
não autorização para outra pressão. Clock anormal/não finito é recusa.

## Implementação delimitada e provas necessárias

Núcleo em novo docs/poc/loaded_memory_protocol.py: schema pequeno, digest,
máquina de estados e classificação com fatos injetados pelo coletor confiável.
Sem resource/mmap/OS/processo/env/SQL. Testes puros com clock e fatos fakes:
mesmos tetos/codec existentes; alteração de owner/origem/digest/ordem;
primeiro bloco/recusa/peak; descarte, deadlines, callbacks falhando, EOF/exit/
cleanup incertos. Não é teste de imposição nem prova de barreira real.

Antes do harness real: revisar produtor da reserva e amostra, ordem de
alocação/touch/retention/ACK, parser incremental limitado, coletor de imports,
argv/inspect, lifecycle e preflight. Reusar CLI/identidade/watchdogs/reap sem
interceptar ou reescrever argumentos de outro observador silenciosamente.
Só então testes de integração/harness e comando para nova raiz/rodada,
com revisão antes da carga. Sem merge, dependência, commit/push ou deploy.

Revisão51ea0d85: D1–D3 corretos para núcleo puro. P1–P5 incorporados antes
do código: pico só em128, bytes/hash único e vetor, ADMITTED do controle,
observações do supervisor e ABORTED sem comando de cleanup. Comparação
conservadora dos picos terá teste próprio; produtor/observador reais ainda
precisarão provar sua viabilidade. Nenhum caso autorizado por esse parecer.

Implementação local posterior: revisão do núcleo apontou B1 (igualdade
antes do tipo em fatos de término).18 regressões vermelhas confirmaram;
tipos antes da comparação e wrapper terminal por operação corrigem o caso.
Rerevisão confirmou B1 fechado; melhoria opcional de chaves VM str foi
aplicada com duas regressões vermelhas/verdes,474 relacionados aprovados.
Conferência final sem bloqueador no núcleo puro em LOADED-PROTOCOL-VALIDATION.
As garantias de ABORTED incluem exceção inesperada, sem cause/context.
