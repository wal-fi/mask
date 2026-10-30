# Próximo incremento — preflight obrigatório no observador do laboratório

**2026-10-21 — plano revisado; implementação local em revisão, só testes fake.**
Motivo: o executor encadeou chamadas apesar de timeout externo na quinta
rodada. Desvio preservado na BATCH-VALIDATION; não repetir para apagá-lo.
Um conselho ao operador não basta como defesa estrutural. Nada de produto,
SQL, worker, dependência ou configuração operacional nova.

## Escolha proposta

O mesmo `Observer.run` deve realizar o preflight antes de qualquer case,
sem depender de arquivo/token produzido por outra ferramenta. Usar só as
chamadas já permitidas: version, ps e image inspect. Perfil/caps/limites
do container, imagem pinada, modo --diagnose e casos não mudam.

1. Readiness explícita: no máximo **três** polls de docker version, timeout
   fixo5s/call, janela monotônica de decisão20s incluindo tempo de cleanup
   e intervalo1s. Poll só começa com pelo menos5s restantes; não encurtar
   timeout para caber. Resposta válida depois da janela é LATE/NOT_READY,
   nunca admissão. Cleanup em voo pode ultrapassar a janela; não é teto
   absoluto de retorno do SO. Watchdog120s começa antes e cobre preflight.
   Readiness consome parte do orçamento do lote. Só timeout de transporte
   com cleanup do CLI comprovado ou exit não zero podem consumir nova poll;
   JSON inválido/duplicado/perfil errado abortam imediatamente. Não repetir
   medição/carga: ainda não há container. A janela é para decisão/admissão,
   não promessa de encerrar processo do SO em20s; cleanup limitado do helper
   congelado e watchdog global120s seguem obrigatórios. Incerteza de cleanup
   aborta, nunca inicia nova poll/case sobre recurso incerto.
2. Comando exato: docker version --format "{{json .}}". Captura até16KiB,
   parser sem chaves duplicadas, objeto Server obrigatório/não-null;
   Server Os linux/Arch amd64,
   Version str ASCII limitada. Só persistir campos fechados/versionamento e
   resultado por tentativa (READY/NONZERO/TIMEOUT/LATE), sem stderr/exceção/ambiente.
   Se janela/tentativas acabam, PREFLIGHT_REQUIRED/NOT_READY e zero cases.
3. Depois de readiness, ps vazio e image inspect são **uma tentativa** cada;
   qualquer não-zero/timeout/schema/perfil inválido aborta. Imagem/config
   seguem a validação existente; não conferir depois para simular antes.
4. Flag interna preflight_passed só vira True após todos os checks, reset
   em cada run. case recusa antes de timer/intenção/create quando não True.
   Não é autenticação nem prova criptográfica: é barreira no fluxo confiável
   do processo do observador. Nenhum token ou arquivo externo de aprovação.
   report registra estado e tentativa; em abort cases=[]/sem pending/create.
5. Cleanup do watchdog/CLI permanece obrigatório, inclusive em abort. Desktop
   só é restaurado por quem o iniciou e após inventário seguro; não matar
   uso alheio. A ferramenta deve verificar exit_code e nunca avançar a carga
   após falha de readiness/preflight, mesmo com a barreira interna.

## Antes de qualquer execução nova

Revisar este plano com Claude2, testes puros primeiro para sucesso e todas
as falhas sem Docker real, implementação e revisão de código. Fixtures que
chamam case diretamente devem declarar preflight fake explícito apenas nos
testes do lifecycle já existente; uma regressão comprova ausência de create
quando a flag não é True. Tempo/CLI são fakes nos testes de readiness.
Nenhuma sexta rodada por este plano. Primeiro registrar/revisar os gates.

Desenho futuro de .lib vem separadamente, usando só relação por identidade
qualificada da quinta rodada e a nota estática Q2; nenhuma regra para os
wrappers ou29 módulos pulados. B-1/B-2/D-090/produção continuam abertos.

P2 fechado: TimeoutError do helper significa finally concluído e permite
nova poll; rc não-zero também. HostFault CLI_CLEANUP/OUTPUT_LIMIT, OSError
ou outra falha de spawn/transporte abortam sem retry; CLI_CLEANUP fica com
cleanup incerto explícito. rc0 com JSON inválido/duplicado/Server null ou
perfil inválido aborta imediatamente, não é startup lento. Version é ASCII
1..64 caracteres do conjunto alfanumérico/._+-, sem strings livres extras.
ps/imagem falhos ou timeout são abort de uma tentativa, sem casos.

P3 fechado: abort com cases=[]/sem create/pending é tentativa de preflight
com raiz própria, **não** rodada de medição. Só depois de registrar o abort
pode haver nova invocação identificada; nunca repetir caso que criou
container. Este incremento não executa tentativa/medição real, só fakes.
P4: observador nunca inicia/para Desktop; isso é do executor e só restaura
o estado que ele mudou, após checks seguros. Conferir exit_code continua
obrigatório. ps/imagem já eram internos na quinta rodada; este plano
acrescenta readiness/flag e organiza esses checks, não inventa sua ausência.

P1–P4 revistos sem contradição pelo Claude2 na sessão51ea0d85. Implementação
depois do aval técnico:22 casos vermelhos/um já passava, mais sete limites;
250 relacionados verdes. Relatório de código/gates em
`PHASE-9-STAGE-8-LINUX-IMPORTS-PREFLIGHT-VALIDATION.md`; sem tentativa real
ou sexta rodada. Releitura do código antes de qualquer execução futura.
