# HELD — integração no laboratório, desenho revisto antes do código

**2026-10-22 — desenho aplicado em I/II, revisados somente com fakes.**
Núcleo HELD-EVIDENCE revisado, nenhuma rodada anterior reaberta. Os onze
helpers e suas evidências permanecem byte a byte. B-1/B-2/D-090/SQL/produção
abertos. Sem alteração em src, dependências, configuração, banco ou worker.

## I1: separar captura de validação, antes de implementar

A primeira proposta carregava E (loaded_memory_evidence.py) no PID1 e
montava13 fontes. Revisão51ea0d85 encontrou bloqueador: E carrega host ->
prepare_linux_imports.py -> packaging. Python -I -B -S do container não tem
site-packages nem packaging nos pins preparados. Essa proposta foi rejeitada
**antes de código ou execução**; montar fontes não resolveria a dependência.
Não instalar packaging, adicionar /installed ao PID1 ou remover -S para fazê-la
passar. O desenho vigente abaixo substitui aquele caminho, não o encobre.

- **Container**: só captura e transporte limitado, sem E/host/packaging.
- **Host Windows/.venv**: validação e replay por E já revisado.

## Incrementos e gates

I. Novos docs/poc/loaded_memory_tap.py e linux_held_probe.py. Capture-only e
entrypoint PID1; fakes primeiro e revisão de código. Sem nova factory real.
II. Novo docs/poc/run_linux_held.py. Observador próprio com perfil/argv/shape
exatos e E no host, artefatos imutáveis. Delta de desenho/revisão depois de I;
não adaptar inspect/resultado novo para parecer um perfil antigo.
III. Depois do código/fakes: procedimento externo/estado do Desktop/contexto,
hashes/comando exato/rodada única revisados antes de qualquer carga.
Nenhum destes textos executa CLI/containers ou prepara árvore real. O plano
anterior está consumido. I não dispensa o gate próprio de II, nem libera III.

## I — tap sem dependência de host

loaded_memory_tap.py recebe core e supervisor congelados como colaboradores,
não carrega E/HOST nem qualquer host/preparador. Somente stdlib e funções
definidas, sem source IO/factory/thread/processo/CLI ao importar.

Tap pequeno reproduz as regras mecânicas de captura, **não** o classificador:
delega prepare/spawn/clock/pid dinâmico/observe/send/sleep/wait/cleanup/final
explicitamente. Só read é interceptado. Exceções do read delegado passam
inalteradas; decoder inesperado/retenção/terceira candidata marcam broken e
falham fechado. Decoder é core.decode_held congelado, não cópia da gramática.
Até2 bytes imutáveis de até1024, captura sintática, sem alegar validação.
Testes de paridade com E.Tap para linhas/falhas/delegação, sem modificar E.

Composição chama supervise congelado com o tap; supervisor continua único
owner de cleanup. Depois usa bounded_report congelado para obter os bytes
originais. Emite um transporte de campos exatos, **não** envelope validado:

```text
profile = "loaded-as128-held-transport-v1"
original = string ASCII dos bytes exatos de bounded_report, com newline
held = 0..2 strings ASCII originais de candidatas HELD, cada<=1024 bytes
tap_broken = bool exato
```

Não incluir validated=true/outcome positivo no transporte. Original e
candidatas são relatos da mesma supervisão; nenhuma autenticidade física
nova é presumida. tap_broken preserva o original negativo e as candidatas,
mas impede admissão no host. Não publicar candidatas como semanticamente
validadas. HELD fora de posição continua sendo erro do supervisor.
Erro de codec/cap usa fallback de transporte exato:

```json
{"profile":"loaded-as128-held-transport-v1","outcome":"inconclusive","transport_failure":"EVIDENCE","total_memory_contained":false}
```

Raw total<=65536 incluindo newline, overhead de escaping contado; sem
truncamento/fallback positivo. Sem decoder completo de relatório no container:
o host usará seu decoder JSON fechado existente. Os bytes originais serão
checados/hasheados por E somente no host.

## I — entrypoint só PID1, filho antigo

Guard antes de carregar helpers/factory: Linux, isolated/no_site/-B,
UID65534 e PID1. Wrapper novo não aceita --member. Guard inválido retorna64.
Depois do load, caso/digest conferidos pelo parser congelado antes da factory;
argumento inválido64, load/factory/canal70 sem traceback/saída ilimitada.
Guard inválido não chama loader; argv inválido exige loader do parser, mas
não chama factory/writer. Import no Windows só define constantes/funções.

Deadline20s começa antes de carregar tap/supervisor/load_parts. Loader lê
arquivo irmão<=65536 e confere SHA fixado antes de executar: supervisor
40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466,
tap terá hash fixado depois do código revisado. Executar somente os bytes
verificados (compile/exec em ModuleType com __file__ correto), sem reabrir
arquivo entre hash e execução. Não alterar sys.path ou globais do supervisor.
Conferir saldo depois do load e de parts, antes da
factory, para não criar filho depois do prazo.

from_linux, core e cleanup são os anteriores. O filho continua exatamente
/probe/linux_loaded_probe.py --member <case>; nomes/origens auditadas e
coletor não mudam. Não importar tap/E/hosts no filho. PID1 tem custo novo,
não se assume baseline antigo nem fit nos mesmos128/192MiB e20/30/120s.

Supervisor limita a medição até completed/control_digest (inclui cleanup);
somente depois bounded_report/transporte limitado e write_report congelado
com prazo próprio2s, que não renova medição20s. Não fazer replay no container,
nem medir o relógio lógico como tempo real. Positivo tardio que falha o core
permanece negativo; preservar DEADLINE/PROTOCOL, sem reescrever diagnóstico.
Exit0 significa apenas emissão concluída; erro do writer70, sem traceback
ou nova escrita ilimitada. Host precisa classificar o raw e seu original.

## II — mapa de fontes e artefatos

Mount /probe RO: seis fontes antigas do membro/supervisor, mais tap e wrapper
(8 fontes), além do runtime.json validado. Não há host/E no mount.
Raiz fora do mount: quatro hosts/preparadores antigos, E e novo observador
(6 fontes). Bundle canônico de **14 fontes**, com cada posição explícita.
Fonte de código público não inclui secrets, DSN, policy ou checkout inteiro.

Classe própria sem case/run/check antigos no MRO. Reusar só primitivas
selecionadas (CLI bounded, save/inspect/identity/cleanup/watchdog, preparação
e readiness/preflight). Construir novo argv, validar inspect diretamente:
não mutar medição/perfil ou devolver raw legado para enganar algoritmo antigo.
Task held-as128-<uuid>, source_hash do mapa14, owner/root novos antes de
pending/label/create/identity; raiz maskgw-held-as128-20261022-*.
Integridade de todas fontes/cópias/runtime/árvore/artefatos; contar cópias e
regravações no1MiB. Não confundir retained bytes com total_written.

Perfil de execução loaded-as128-held-v1, Cmd exato do wrapper/caso/expected.
Imagem pinada, UID65534/NNP/capdropALL/rede none, dois mounts RO,192MiB/swap0/
CPU1/pids16/shm1MiB/nofile64/core0;30s/caso,120s/lote,20s internos,64KiB por
raw,1MiB por lote. Sem elevar cotas para caber o custo novo.

Salvar **transport raw imutável antes de decodificar**. Conferir schema/
ASCII/tipos/caps com decoder fechado do host. E.encode(original,held,case,
expected) valida original e replay no host, E.decode reconfere envelope.
Salvar envelope como **segundo artefato imutável**; referências SHA/tamanho de
ambos em case.json, sem duplicar raw completo. Ambos contam no1MiB.
Fallback/erro/tap_broken/perfil antigo/HELD ausente interrompe o lote; E pode
preservar original negativo num envelope sem HELD, nunca admitir tap_broken.

Preflight interno obrigatório até3 version5s/16KiB em20s, ps global vazio e
image inspect antes de create. Pending durável antes de create, identidade
antes de CID ao watchdog, deadline por relógio mesmo com watchdog atrasado,
cleanup só de ID/task/bundle próprios, incerteza negativa, integrity antes/
depois dos casos e fim, ps final vazio. Sumário próprio/total_memory_contained
sempre false. Não herdar nem reclassificar diagnostic_success de perfil antigo.

Controle exige control_ok,2 HELD private/shared, replay/digest, cleanup e
integridade; só então admite privado128 com digest desse lote. Imposed privado
admite shared. Primeiro fail/incompatible/inconclusive interrompe; registrar
not_executed. Inventário novo deve concordar entre casos, não467/digest antigo
predefinidos. Sem exceções de origem/fallback ilimitado para obter fit.

## Testes e limites de autorização técnica

I: runtime/argv inválidos sem factory, import/tap sem E/host/packaging,
hash errado/loader atrasado, partes/factory/capture/writer falhando, emissão
limitada, captura verdadeira sobre FakeIO nos3 casos, erro delegado preservado,
broken e overflow negativos, paridade com E.Tap. Sem fábrica Linux real.
II: perfil/argv/env/limites/identidade, guard/preflight sem create,14 posições/
hashes/accounting, novo raw antes do parser e envelope imutável, HELD forjado/
fallback, deadlines/cleanup/criação incerta, stop/admissão e sumário próprios.
Repetir relacionados/estáticos; nenhum Docker/proc/pressão real nesses gates.

III precisa seu plano/comando próprios, exits conferidos e abort sem retry.
Desktop alheio preservado, recursos somente por identidade própria. Todo
resultado pode ser inconclusivo; não corrigir e rerodar sob plano consumido.
Nenhum incremento certifica memória total, trabalho nativo, custo do pai/
saída, concorrência, worker real, B-1/B-2/D-090 ou produção.

Revisão somente leitura51ea0d85: I1 bloqueou proposta inicial antes do código.
Parecer permite testes primeiro I **após** adotar esta separação, não II/III
sem seus gates. Não houve CLI/carga nem cota observada.

I e II depois implementados, medidos com fakes e revisados sem bloqueador:
HELD-ENTRY-VALIDATION e HELD-HOST-VALIDATION. III continua não iniciado.
