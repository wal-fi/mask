# T4 — executor público de emergência, somente fakes

2026-10-28, sob delegação. Fatos da prova de identidade P1 aceitos pelo
Claude2; reuso do bounded58c692a7 aceito com E1–E4 antes deste código.
Não há watchdog/coordenador operacional ou chamada real deste executor.

docs/poc/w1_bootstrap_emergency.py,
e258fef8297f00203a7243503024fe9900c3e56bdfe38cb88af4842258949749,
é específico da T4: só5ações fechadas, sem argv/CLI arbitrários. Target contém
CID e PID/FILETIME públicos, **não atesta posse**. Antes de kill/rm, o chamador
futuro deve validar inspect contra sua intenção capturada. O executor não
carrega ManagedBootstrap, seed, ticket, Absent ou estado do loop do main.

## E1–E4 implementados nesta camada

- Cada instância compila bytes capturados/pinados do bounded58c e identidade
  dc248 em namespaces próprios. environment pertence ao namespace próprio,
  não ao dict do main. invoke usa asyncio.run no thread do watchdog futuro;
  chamada de dentro de loop já rodando recusa antes de criar coroutine.
- begin abre orçamento30s só na emergência. Antes de cada chamada, pins de
  executáveis/config/meta/endpoint; após esse custo, timeout≤4sPS/2sDocker
  e reserva10s (wait5+reader5) devem caber. Sem margem, nada executado.
  Resultado posterior ao end também é erro; orçamento não renovado.
- Frozen bounded usa stdinDEVNULL/ambiente público/stdout limitado/stderr
  DEVNULL. Seu spawn **não** tem prazo; não cancelá-lo com timeout externo.
  Spawn/cleanup/SO incertos continuam pendência/HELD. Watchdog futuro deve
  constatar join35s falho; esta camada não tem thread/join nem prova de E3
  em runtime e não promete prazo absoluto para syscall/spawn que não retorna.
- Timeout/OUTPUT_LIMIT/CLI_CLEANUP/exitnãozero/saída malformada são COMMAND
  fechado, sticky failed bloqueia nova ação. PS passa pelo parse_report e
  somente KILLED/ABSENT podem concluir sua ação; mismatch/ERROR abortam.
  Retorno Docker só vai para o parser de posse do chamador, nunca artefato.
  Metadata guarda ação/outcome, sem raw stdout/seed/digest privado.

## Medições

**18pass/0,36s** em tests/test_w1_bootstrap_emergency.py,
49e1c41300c276b24266d17187594ba82dd467a5ff3ba0da8bbd969196f2368d.
Fakes substituem bounded e pins; nenhum Docker/PS/kill/thread executado.
Namespaces/ambiente independentes, loop próprio recolhido,4comandos CID
fechados, pins por chamada, reserva exaurida após custo de pins,6falhas
fechadas/sticky, PS4categorias e recusa de uso do mainloop. Nenhuma saída
bruta em metadata. Ruff/mypy3.11 do teste e lint restrito do helper verdes;
sem claim de tipagem estrita para o helper privado.

## Pendentes e limites

Revisão de código desta camada; depois watchdog/heartbeat/snapshots/Lock/
join/executor de posse e coordenador completo com fakes de E3/P1–P4. Não
confundir low-level exit0 com ausência/release. Nenhum Absent pode vir do
watchdog. Source/currentpin ilegível pode abortar aceitação mas cleanup deve
continuar por captura e executable/endpointpins, conforme desenho HOST.

T4 real exige código, perfil, estado, raiz e comando únicos revisados antes
de A. Imagem621cc7f7 inalterada; nenhum PG/SQL/secret/serviço/liberação de
produção ou mudança de dependência/produto. Sem commit/push/job/segundo escritor.

## B1 — calibragem antes da primeira execução T4

Claude2 recusou e258fef8 por teto2s de rm incompatível com baseline. Conferi
diretamente result.json de oracle9-w1-restore-attempt1-20261027: recovery-rm
exit0,6,296999999962281s; inspect0,11s/absent0,125s. Não reexecutado.
Regressão primeiro: caso fake6,3s falhou com o teto2s; o9s já era recusado.

Delta sob delegação, antes de efeitos: CLI_KILL4s; CID_ABSENCE/INSPECT2s;
CID_KILL4s **proposto, ainda sem medição T4**; CID_REMOVE8s para cobrir6,297s
conhecidos com margem. Emergência45s, join do watchdog futuro50s, em lugar de
30/35 da proposta anterior. Cada pin tem limite de admissão1s após retorno
da leitura, sem promessa de interromper syscall. Uma execução somente leitura
de cleanup_pins neste host mediu **0,125s**, valid=true, nenhum DockerCLI.
Isso é amostra, não teto de SO. Fonte/contexto e quotas de container intactos.

Pior sequência declarada PS/absence/inspect/kill/inspect/rm/absence:
4+2+2+4+2+8+2=24s, até7x1s de pins=31s, reserva10s=41s, margem4s até45.
Ack2s+lock1s+exec45s+2s de coordenação cabem no join50s, sujeito à ressalva
de spawn/syscall que não retorna. Se insuficiente, HEld/pendência, não retry.
Timeouts do canal12/3s e limites do worker não mudaram.

**22pass/0,44s**. Novo fake da sequência consome todos os tetos/pins e termina
em31s, com14s restantes;6,3s passa,9s dá COMMAND; pin1,1s impede comando.
Código2fdc0084f4bf91ad0186779867353d2dfe4ff5943c54d973b4913ec8b12ed2d3;
teste8a53867d8a60f051388ba3d5ee17831fa9739dcaa744146340f71ec0d6afedcd.
Este delta ainda em revisão, nenhuma chamada real do executor ou thread.
