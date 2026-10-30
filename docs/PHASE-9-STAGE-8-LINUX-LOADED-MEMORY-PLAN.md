# Próximo lote — memória com imports reais, proposta separada

**2026-10-21 — desenho revisado; R1–R8 incorporadas, sem código ou execução.**
Depende da evidência LIB-RUN-VALIDATION, revisada sem bloqueador. O ensaio
AS32 continua **did_not_fit**; não será refeito, reclassificado ou elevado.
Este lote tem outra pergunta: há imposição individual observável depois de
carregar o perfil real? Não é calibrar sessões/query nem fechar B-2.

## Hipótese e cap predeclarado, não default

O controle real teve VmPeak110.063.616 bytes após três imports. Para um
único perfil exploratório, escolher AS **128MiB**: pico observado +16MiB
de folga, arredondado ao próximo múltiplo de16MiB =134.217.728 bytes.
Essa folga é uma escolha **não medida**, não orçamento para libpq/SQL/AST,
masking, TLS, processo pai, gerações ou resposta. O número não é configuração
de produto nem quota certificada. Não haverá busca binária ou incremento
de limite se o perfil falhar: registrar incompatível/falha e parar.

Expectativa, não critério de aceitação:105MiB de pico deixam cerca de23MiB
até128MiB; uma recusa por volta do quinto/sexto degrau4MiB é plausível.
O baseline real do novo harness pode diferir e será registrado, incluindo
buffers/reserva de relatório. Não mudar limite/degrau depois de medi-lo.

Cap por processo não é cap total do host. O domínio externo192MiB/swap0
permanece só defesa finita e não será deliberadamente saturado. AS não
cobre todos os custos desse domínio; lacunas conhecidas do kernel, cache,
tmpfs sem mmap, sockets e pai continuam bloqueantes. Não somar shmem a file,
não chamar VmPeak de RAM e não inferir limite global a partir de um membro.
Windows/Jobs e suas falhas antigas não são aprovados por este perfil Linux.

## Menor matriz proposta: três casos, uma rodada futura

Todos importam cumulativamente db.postgres, runtime.snapshot e
pgwire.result_encoder sem instanciar adapter/serviço, conectar ou receber
SQL. A mesma auditoria fechada de origem, inventário, efeitos e native_check
deve completar antes de qualquer pressão. Usar a regra exata do slot LIB;
nenhuma exceção para módulo novo. Se o harness precisar de stdlib adicional,
documentar antes/revisar e incluí-la no baseline dos três casos igualmente.

1. **Controle carregado, sem AS**, ainda sob domínio externo192MiB. Após
   imports/auditoria, alocar bytearrays em degraus de4MiB até40MiB, tocar e
   reter todos os blocos até amostra/ACK. Liberar e confirmar descarte antes
   de fazer o mesmo com MAP_SHARED anônimo,40MiB tocados/retidos. Os dois
   alocadores não coexistem no controle; não usar um só para validar outro.
   Qualquer recusa prematura torna o controle inválido e impede casos128.
   Confirmação de descarte proposta, fixa: VmSize após liberação<=VmSize
   pré-pressão+4MiB **e** anon do cgroup cair pelo menos32MiB em relação
   ao platô privado. Registrar valores antes/platô/depois; até cinco amostras
   separadas por1s, dentro do deadline30s, sem malloc_trim ou novo mecanismo
   para forçar resultado. Se não cumprir, controle inconclusivo, não relaxar.
2. **Privado AS128**, supervisor aplica soft=hard antes do spawn. Confirmar
   limite no membro antes de GO e após os imports. Bytearrays acumulados
   em4MiB até recusa ou40MiB, tocados/retidos até amostra. Sem liberar cada
   degrau para fabricar sucesso. Nenhum fallback ilimitado.
3. **Compartilhado AS128**, mesma sequência, só MAP_SHARED anônimo acumulado.
   Não é /dev/shm; shm-size1MiB não explica sua recusa. Mesma obrigação de
   blocos anteriores mantidos e limite conferido antes/depois.

Controle inválido impede ambos128. Se privado128 não completar imports/
native_check/efeitos, compartilhado não será executado (registrar não
executado). Falha de cleanup/protocolo/setup também interrompe o lote.
Qualquer FAIL/incompatible/inconclusive interrompe os casos restantes;
só controle válido e depois imposed do privado admitem o próximo caso.
Antes de pressão em cada128, exigir o **mesmo conjunto de linhas de imports
do controle desta rodada**, não da sexta. Divergência é inconclusiva e
impede pressão. O protocolo terá de provar comparação antes de PRESSURE,
não apenas observar igualdade a posteriori; desenho dessa barreira ainda
será revisado antes de preparar código.

Um supervisor PID1 e um membro por caso; sem workers concorrentes. No
controle há no máximo40MiB de payload extra coexistente, não80MiB. Nos
casos limitados, também pedido máximo40MiB e degrau4MiB, sem insistir depois
da primeira recusa. Budget externo/tempo/caps não aumentam para obter verde.
Se imports falharem sob128 antes de pressão, resultado **incompatível**;
não chamar isso de imposição de alocação nem trocar o limite.

## Asserções e classificação antes de implementar

- Pré-AS: VmSize do supervisor<=124MiB (folga4MiB), perfil/cgroup/UID/fds/
  inventário conferidos. Falha de setup/spawn/coleta é inconclusiva, não
  imposição. Membro precisa reportar AS efetivo e completar imports, origem,
  native_check e efeitos antes da pressão. Ready do membro também exige
  VmSize<=124MiB; getrlimit deve registrar soft=hard134.217.728 no ready,
  depois dos imports e imediatamente antes da pressão. Divergência é
  inconclusiva. AS no supervisor também limita
  sua coleta; não prometer que erro de coleta é recuperável em todos os casos.
- **Imposição observada neste membro** exige recusa MemoryError/ENOMEM no
  próprio alocador, pelo menos um bloco4MiB tocado e ainda retido, limite
  efetivo128MiB e VmPeak<=134.217.728. Registrar bytes/degrau aceito e
  recusado. Não basta emitir erro ou morrer antes de acumular.
- **FAIL** se completar40MiB sem recusa ou pico exceder o teto reivindicado;
  **incompatível** se não completar imports sob128; **inconclusivo** para
  outro errno, sinal, timeout, pressão externa/OOM, falha de protocolo/
  coleta/setup/cleanup. Nenhum desses resultados aprova contenção.
  Recusa do primeiro bloco4MiB, sem bloco anterior retido, é especificamente
  **inconclusiva por falta de folga**, não imposed nem incompatible.
- Mesmo imposição observada não prova segurança de todos os alocadores,
  memória total, concorrência, custo do pai ou compatibilidade de consultas.
  Congelar os três resultados, incluindo não executados, sem repetir até verde.
  Não exerce alocações nativas internas de libpq/pglast/Rust/TLS, nem seus
  caminhos de falha. Bibliotecas carregadas não equivalem a trabalho nativo
  saturado; sucesso nunca significa "trabalho nativo contido em128MiB".

## Harness e execução ainda não feitos

Preservar scripts e artefatos das seis rodadas anteriores. Código novo do
laboratório precisa desenho de protocolo/reuso e testes puros primeiro,
depois revisão de código pelo Claude2 **antes** de qualquer execução real.
Não editar as fontes congeladas para gerar variante que pareça AS32.
Reusar funções verificadas de auditoria/codec/CLI/identidade/cleanup quando
possível, sem duplicar regra de origem. Distinguir nomes/perfil128 nos
artefatos e mensagens; nunca rotular fits_as32. Relatório final deste lote
não pode usar classificador de fit de imports como teste de imposição.
Perfil explícito `loaded-as128`, chaves de resultado próprias, raiz/task/
hashes novos. Nenhum artefato das rodadas1–6 é alterado por esse perfil.

Mesmas imagem/árvore parcial/digest já verificadas, sem download/instalação,
dois mounts RO, não-root/rede none/capdropALL/NNP, CPU1/pids16/shm1MiB/
nofile64/core0,30s/caso/120s/lote,64KiB/caso e1MiB/lote, sem logs de payload.
Snapshot novo/hashes antes/depois, protocolo incremental fechado e controlador
externo com watchdog independente; recursos só por ID próprio confirmado.
Manter preflight obrigatório interno e procedimento externo com cada exit
code conferido. Abort sem create é registrado e encerra a autorização da
tentativa; qualquer outra invocação exige plano/revisão próprios. Desktop
oculto só se inicialmente off e restaurado só depois de inventário seguro.

Antes de executar, o protocolo precisa dizer como distinguir ACK/platô/fim,
manter resposta limitada sob OOM e demonstrar recolhimento após qualquer
falha. Não receber dados, secretos, DSN, chave, policy ou query; nenhum banco.
Depois da recusa, não montar inventário/estrutura grande: linha fechada
de até1KiB com bytes/blocos retidos, categoria/errno e VmPeak, buffer
pré-alocado. Proposta de reserva de emergência2MiB em todos os casos,
incluída no baseline/cap (não acima dele), liberada só para relatório após
recusa, sem liberar payload retido antes da amostra. O protocolo/código
devem testar falha da emissão: resultado inconclusivo, nunca imposed.
Essa estratégia não garante recuperar todo OOM; precisa revisão/testes.
Só poderá haver execução após revisão desse código/protocolo e do comando
exato, não por este desenho. Não adicionar variável de produto/dependência.

Próximos gates, fora deste lote: múltiplos membros, domínio externo efetivo,
custos do pai/saída, ledger/admissão atômica, gerações e pipeline real.
B-1 fim a fim, B-2, D-090 gate2, SQL PGWire e produção continuam abertos.

Revisão somente leitura51ea0d85: diagnóstico considerado distinto e
defensável, sem bloqueador na escolha; R1–R8 exigidas antes do harness e
incorporadas acima (falha nativa fora do escopo, primeiro bloco, stop,
inventário/barreira, descarte mensurável, limites, resposta pequena e perfil).
Os critérios concretos de descarte e protocolo/reserva acima são propostas,
ainda precisam conferência ao desenhar o harness. Nenhuma carga autorizada
por esta preparação e nenhum gate de produto reclassificado.

Conferência final51ea0d85: sem contradição/implicação insegura restante,
apto **somente a desenhar o protocolo**. Restrições D1–D3 a resolver nele:

- D1: escolher canal explícito de digest do inventário do controle para
  cada128 antes de PRESSURE (argv fechado ou input separado com hash).
  Não mutar silenciosamente mount RO/manifest nem enviar linhas/segredos.
- D2: reserva2MiB deve ser mmap privado anônimo explícito, não bytearray
  cuja liberação possa reter espaço virtual. A amostra decisiva precisa
  ocorrer **antes** de close da reserva, mantendo os payloads. Liberação
  ajuda relatório, não é prova de recuperação universal de OOM.
- D3: prazo interno do supervisor/membro é20s, além do30s externo/caso.
  Controle inteiro (imports, degraus, descarte e ACKs) precisa caber no20s
  ou ter mudança própria declarada/revisada; estourar é inconclusivo.

ACK/platô/fim, saída limitada e cleanup também ainda são desenho. Nenhum
harness, subprocesso, pressão ou quota de produto implementado por este plano.
