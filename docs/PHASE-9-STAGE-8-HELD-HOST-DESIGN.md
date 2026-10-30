# HELD integração II — observador próprio, delta após I

**2026-10-22 — desenho aplicado em II; código/fakes revisados.**
I foi revisado sem bloqueador com fakes, não rodado em Linux. Este delta
refina HELD-INTEGRATION-DESIGN depois de I1; preserva os13 helpers anteriores
(dez loaded-as128, E e tap/wrapper), o produto e todas as medições antigas.
III/procedimento/comando/rodada permanece gate separado. Sem CLI/carga real.

## Perfil, fontes e reuso

Novo docs/poc/run_linux_held.py, sem herança de case/run/check antigos.
H/E/T são loaders/validadores congelados, não algoritmos de lote antigos.
E tem SHA7f030710..., conferido antes do load, e exige H=d95cdfe2...;
wrapper exige S=40ead31f.../T=aae25eb1..., sem alterar nenhuma constante.
As14 fontes e posições do desenho de integração:8 probe RO e6 hosts fora.
Runtime.json é manifesto separado, também hashado/verificado.

Reusar primitivas anteriores: bounded CLI, save/inspect/identity/cleanup,
watchdog, init de preparação (sem CLI/thread iniciada) e readiness/preflight.
No arquivo novo, fluxo superior próprio derivado do contrato já revisado,
com argv/inspect e decoder HELD explícitos. Não monkeypatch em globais
antigos, reescrever inspect/retornar só original legado para encaixar no
algoritmo antigo, nem alterar perfil para usar diagnostic_success antigo.

Init acrescenta9 fontes às5 da preparação inicial, total14. Conferir conjunto
e copiar probe/host nas posições exatas; identidade held-as128-<uuid>/bundle
do mapa canônico14 substituída antes de pending/labels/watchdog CID. Cópias
iniciais/sobrescritas são cobradas no total_written; nada de subtrair bytes
retidos para permitir write extra. Integridade cobre originais/cópias,
runtime/árvore e artefatos. Não preparar árvore real nos testes deste lote.

Entrypoint=["python"], Cmd exato=["-I","-B","-S",
"/probe/linux_held_probe.py","--case",case,"--expected",expected];
mesmos imagem/UID/NNP/caps/rede/mounts/limits/env. Nenhuma quota sobe para
caber o custo novo. Perfil summary/execution loaded-as128-held-v1; raw do
container tem perfil loaded-as128-held-transport-v1. Não confundir os dois.

## Transporte fechado e dois artefatos

Bounded CLI limita leitura e resposta65.536. **Salvar raw imutável antes do
parser**, nome <case>-transport.json, SHA/bytes contados no1MiB. Depois
HOST.decode_report (ASCII/única linha/duplicatas/NaN/cap) e schema exato:
profile/original/held/tap_broken; profile exato, bool exato, original str
ASCII<=64KiB com único newline, held lista<=2 de str ASCII<=1024. Não há
outcome no transporte normal. Fallback tem exatamente o schema/valores de
T.FALLBACK e só significa inconclusivo; tipos conferidos antes de igualdade.
Não tratar documento antigo/extra como compatível nem normalizá-lo.

Transporte inválido: raw permanece e caso inconclusivo, sem envelope válido
inventado. Transporte fallback: salvar E.FALLBACK como segundo artefato e
parar. Transporte normal: E.encode(original,tuple(held),case,expected), depois
E.decode. Guardar envelope como <case>-envelope.json, também imutável e
contado no1MiB, mesmo se for fallback. Case.json referencia ambos por SHA/
bytes; não envolve novamente seu conteúdo no metadata.

tap_broken=true sempre torna caso inconclusivo e interrompe. Pode-se guardar
envelope negativo com original exato quando o original é negativo. Original
positivo com tap_broken nunca produz envelope positivo: usar E.FALLBACK.
Isso preserva diagnóstico sem deixar um artefato positivo contradizer o stop.
HELD de bloco/categoria/errno continua relato do membro; E só revalida regras
e corroboração de pico/limites. Relógio lógico não é tempo real nem prova EOF.

Envelope positivo exige E.decode completo e revalidação do original pelo
host para obter digest calculado; nunca confiar só no marcador outcome ou
validated. Fallback/erro/tap_broken interrompe, nenhum próximo create.
Negativo forte fail/incompatible só após validação congelada; não promovê-lo
a conclusão forte quando falta evidência. Raw negativo original preservado.

Escaping original+HELD pode ultrapassar cap mesmo se original cabe64KiB:
transporte então fallback e original se perde antes do host. Não há margem
garantida de55KiB (depende de caracteres escapados). Registrar inconclusivo,
sem truncar, elevar teto ou repetir para obter sucesso.

## Lifecycle e admissão

Próprio case/run: preflight interno obrigatório, grant único por caso e
uma invocação por instância. Até3 version5s/16KiB em20s, ps global vazio,
imagem/config inspecionados antes de create. Controle só admite privado128
após control_ok+2 HELD+replay/digest+cleanup+integridade. Privado imposto
admite shared; caso contrário stop/not_executed explícitos. Digest desse
controle, não antigo. Não predeterminar inventário467 nem relaxar origens.

Pending antes de create; CID ao watchdog só depois de inspect+identidade;
recolher somente recursos próprios verificados. Criação incerta permanece
negativa mesmo se cleanup recupera ID por nome exato. Timer30/caso e120/lote
com checks monotônicos antes de grant/create/start, attach limitado ao saldo;
integridade fora do caso, dentro do lote. Limpeza ainda tentada, sem prometer
teto absoluto do SO. Erro de CLI/pump/watchdog/cleanup não libera caso novo.

Sumário novo com profile/bundle/source_hashes/cases/not_executed/integrity/
inventory_restored/watchdog/deadline e total_memory_contained=false. Cada
case referencia os2 artefatos e seu metadata. diagnostic_success próprio
exige exatamente3 resultados esperados, E positivo validado, ambos artefatos,
cleanup/integridade/inventário/prazo, nunca herda reclassificação do H.

CLI futura --run <docker> <prepared_root>, raiz própria held-as128, mas não
invocar neste lote. Testes só IO/clock/CLI/watchdog/árvore pequena simulados.
Derivação mecânica do fluxo superior congelado deve ser revisada como código
novo, sem apresentar os testes antigos como prova suficiente.

## Matriz antes de revisar código

Preflight/argv/perfil/env/mount/limites/identidade,14 posições/hash/accounting,
raw antes do parser/imutabilidade dos2 arquivos, overflow/corrupt transport/
envelope/HELD/old profile, broken contra positivo e negativo, ausência de
segunda tentativa, grants/deadlines/watchdog tardio, criação incerta/estrangeira,
cleanup/integridade/próprio summary, stop antes dos demais casos.
Repetir I/E e anteriores (849 relacionados atuais) mais os novos; estáticos.
Sem Linux/proc/pressão real, banco/SQL, dependência, produto ou deploy.
Depois da revisão de código ainda III, jamais repetir plano consumido.

## R1–R4 da revisão, incorporados antes do código

R1: argv completo acima; remover -I/-B/-S separadamente deve recusar antes
de start. R2: integrity antes de cada create também confere pins entre fontes:
S e T copiados iguais a SUPERVISOR_SHA/TAP_SHA do wrapper, H na raiz igual ao
pin d95cdfe2 de E, E igual ao pin7f030710 de II. Inconsistência para antes
do create, não dentro do container. Hash do wrapper também congelado/revisado.

R3: case faz somente lifecycle: salva transporte bruto, inspect pós-exit e
remoção/cleanup confirmados antes de qualquer parse/E. Encerrar timer30s do
caso. Processamento E e segundo artefato ocorrem **fora do timer30**, dentro
do lote120, antes do próximo grant. Expirar lote durante E torna resultado
inconclusivo e interrompe, mesmo que tenha sido salvo envelope válido.
Artefato não altera retroativamente o prazo/lifecycle observado do caso.

R4: tabela fechada, raw recebido preservado antes de classificar exit:

| Saída do container | Resultado antes de parse |
| --- | --- |
| ExitCode0 e raw presente, OOM false/CLI0 | pode processar, só após cleanup |
| Exit70 ou raw ausente | inconclusivo, TRANSPORT_MISSING/TRANSPORT_EXECUTION, sem envelope |
| Exit64 | inconclusivo, TRANSPORT_ARGV, stop |
| outro exit ou OOMKilled | inconclusivo, CONTAINER_EXIT, stop |

Revisão somente leitura51ea0d85 aceitou delta sem bloqueador após registrar
R1–R4, permitindo testes primeiro II com fakes e revisão de código própria.
Não autoriza III ou produção. Revisor não executou código.

No fechamento, teste adicional reproduziu timestamp antes de integrity final
aceitando121s. II corrigido e rerevisado: timestamp/deadline depois de integrity
e watchdog.close, antes de persistir summary; elapsed_scope explicita esse
checkpoint, não teto absoluto de fsync/startup. Somente código II mudou.
