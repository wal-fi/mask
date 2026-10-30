# Etapa 8 — observação limitada de candidatos, sem nova aceitação

**2026-10-21 — dados diagnósticos coletados; desvio de procedimento explícito.**
Plano: `PHASE-9-STAGE-8-LINUX-IMPORTS-BATCH-PLAN.md`, revisado pelo Claude2
na sessão51ea0d85. Quatro rodadas anteriores/fontes/artefatos preservados.
Nenhum novo container, import Linux, banco, SQL ou runtime operacional até
o registro pré-execução desta seção. Docker estava desligado; não havia processo de
teste da interrupção anterior. Checkpoint HEAD4a5e556, origin/master em
cache5d173ea,0behind/1ahead; arquivos anteriores preservados, sem fetch.

## Implementação

`docs/poc/linux_import_probe.py` ganha passe diagnóstico depois do primeiro
FILELESS_UNATTRIBUTED nas etapas0..2; baseline e outras categorias não
abrem batch. Mesma lista do delta/ordem, bookkeeping dos nomes já emitidos,
no máximo1.500 examinados e oito detalhes; prioridade NON_MODULE,
MODULE_EXACT, ABSENT, totais e diagnóstico incompleto explícitos. Nenhum
candidato vira linha aceita nem muda module_inventory. module_row e regras
de origem/atribuição não foram ampliados. O código novo não aceita .lib.

O passe próprio não lê atributos, tipo por nome, repr ou == de candidato
não-módulo. ModuleType exato só usa o dict. A âncora fechada _openssl/Rust
é revalidada por tipos/dicts/identidade/origem/owner/path; só ela usa a
regra existente de origem. Chaves lib/ffi por is, sem None falso positivo;
LIB/FFI/BOTH/NONE, UNANCHORED implica todos NONE. Isso só observa relação,
não prova autoria independente ou contenção.

**Limite importante:** o caminho antigo de auditoria, antes de disparar o
batch, ainda lê __file__ por getattr, inclusive na quarta rodada. Não foi
alterado aqui nem alegado read-free. A restrição sem atributos é do passe
batch. Uma eventual mudança da aceitação desses objetos é outro lote.

Terminal audit_error -> até8 detalhes -> batch_end -> EOF limpo ->75.
Schema/tipos/etapa/contagens/âncora validados pelo supervisor; falta/forja,
linha extra, timeout ou exit divergente viram PROTOCOL/incomplete=true.
LineReader agora recusa cauda parcial sem newline no EOF, para não aceitar
bytes extras como EOF limpo. Mesmos4KiB/linha,8.000bytes de metadados,
56/64KiB de resposta,20/30/120s e cleanup. Observador recusa presença de
batch mesmo vazio no classificador de fit. SQL/worker/produto inalterados.

## Regressões e gates locais

35 testes novos falharam contra a versão anterior; após implementação e
13 reforços adicionais: **218 passed** nos cinco módulos relacionados
(170 anteriores/48 novos). Sem Docker ou binários Linux executados no host.
Cobertura: atributos/equality hostis e subclass, origem/identidade da âncora,
dict ímpar simulado (não alegado possível em ModuleType real), None/BOTH/
ABSENT, oito/nove candidatos, cap1.500, prioridade, nomes inválidos,
protocolo/contagens forjados, falta de fim/linha extra/cauda parcial,
timeout/exit/saldo de metadados e falhas de emissão. Inventário aceito
permanece idêntico; nenhuma mensagem original é refletida.

Primeiros checks estáticos: duas ocorrências PLC0414 nos aliases de fixtures
e nove diagnósticos mypy em helpers de teste. Corrigidos por reutilização
explícita das fixtures, assinaturas e um double de dict de teste; nenhuma
regra/configuração relaxada. Resultado final: Ruff src/tests e E/F/I/B/UP
dos dois PoCs, format250 arquivos e mypy strict3.11/3.14 em248 arquivos
limpos. Não é suíte PG16 integral, execução runtime3.14 ou gate operacional.

## Revisão e próximo caso

Revisão de código/testes somente leitura solicitada na mesma sessão.
Nenhum caso antes da resposta. Se não houver bloqueador, uma rodada nova
identificada com mesmas imagem/árvore/perfil/cotas e cleanup próprio; o
batch mantém o controle inconclusivo, sem AS32. Não repetir até verde nem
criar regra de aceitação depois do resultado sem revisão separada.
B-1 fim a fim, B-2, D-090 gate2, SQL e produção continuam abertos.
Sem segundo escritor, commit/push ou mudanças em dependências/.venv.

## Primeira revisão e defesa da admissão antes de executar

Claude2 não apontou bloqueador na implementação; confirmou coleta sem
atributos, schemas/contagens e terminal. Registrou limitações conservadoras:
o prazo20s do filho inicia depois do20s do supervisor, de modo que pode
perder a corrida e virar PROTOCOL; ordem dos grupos não é autenticada pelo
supervisor, então não é prova baseada na ordem das linhas recebidas.

O executor encontrou uma defesa faltante na admissão do caso limitado:
classify_limited recusa batch, mas é chamado após esse caso. Adicionado um
teste com controle falso normal/batch vazio: antes chamou control+limited;
depois da condição explícita em Observer.run chama só control. Nenhum
container foi criado nesse teste; fake com artefatos em tmp_path. Isso
preserva o requisito de não abrir AS32 com qualquer batch, mesmo se o campo
outcome estiver errado. Releitura somente leitura do acréscimo solicitada.
Resultado: **219 passed** relacionados (49 novos/170 anteriores), Ruff,
format250 e mypy3.11/3.14 em248 arquivos limpos. Docker continua off.

Antes da execução foi acrescentado um modo **somente do PoC** --diagnose:
itera exclusivamente control, mesmo se ele vier normal sem batch. Isso
torna a proibição de AS32 incondicional nesta quinta rodada. --run/default
preserva os dois casos condicionais anteriores. Campo diagnostic_only no
sumário distingue a intenção; complete continua false sem dois casos,
imports_fit_as32 permanece false e saída não-fit continua2. Novo parâmetro
do teste fake ficou vermelho antes e verde depois. **220 passed** (50 novos),
mesmos checks limpos; delta restritivo em releitura antes de Docker.
Não é variável/configuração de produto, novo listener ou mudança de cota.

## Quinta rodada --diagnose: desvio de orquestração

Revisões do código, da defesa de admissão e do modo restritivo concluídas
sem bloqueador antes da medição. **Houve desvio posterior do executor:** a
chamada externa `docker version` expirou no prazo5s durante a inicialização
do Desktop. A sequência de chamadas da ferramenta não parou nessa falha e
iniciou o observador mesmo assim. Não era o procedimento aprovado. A
responsabilidade é da orquestração desta conversa, não foi atribuída à rede,
ao produto ou ao usuário. **Nenhuma repetição foi feita.** Não declarar
preflight externo aprovado, versão do engine medida ou gate integral fechado.

O observador executou seus próprios checks de inventário vazio, imagem
Linux/amd64, perfil antes do start, árvore/hash e cgroup efetivo. Isso consta
do caminho validado e do relatório, mas **não substitui retroativamente** o
preflight externo ausente. Os dados abaixo são observações diagnósticas
qualificadas por esse desvio, não certificação da rodada/procedimento.
Próxima invocação deve testar exit_code de cada chamada e abortar antes
de --diagnose se qualquer preflight falhar; só cleanup seguro pode seguir.

Raiz própria `%LOCALAPPDATA%\Temp\maskgw-linux-import-run-20261021-hkoqg8a7`;
container único `1e32d1753f230d90792a18b6775b77befc08bf7cda1444b54aa6b84d69ce0ecd`.
Imagem pinada igual ao plano; sem pull/download/reinstalação. Produto
comparado aos115 fontes antes, árvore preparada inalterada. Modo --diagnose,
diagnostic_only=true; controle5,203s/lote5,562s. Python exit2 coletado,
container exit0, membro75. complete=false/imports_fit_as32=false/exit2 são
esperados nesse modo, não sinais de aceitação ou falha de memória. Controle
inconclusivo/AUDIT_ERROR de `_openssl.lib`, **nenhum caso AS32** criado.

## Detalhes exatamente recebidos, não origens aceitas

| module | kind | dict_file | identity_slot |
|---|---|---|---|
| `_openssl.lib` | NON_MODULE | null | LIB |
| `cryptography.hazmat.primitives.ciphers.algorithms` | NON_MODULE | null | NONE |
| `cryptography.hazmat.primitives.ciphers.modes` | NON_MODULE | null | NONE |

Todos têm phase=batch_detail/stage=1. batch_end recebido:

```json
{"phase":"batch_end","stage":1,"examined":34,"details":3,"non_module_total":3,"module_exact_total":0,"absent_total":0,"incomplete":false,"anchor":"ANCHORED"}
```

batch.incomplete=false significa que o passe terminal não omitiu candidatos
segundo suas contagens, **não** inventário/import aprovado ou origem
verificada desses três. dict_file=null em NON_MODULE não prova ausência
de __file__, pois o passe não o lê. Algoritmos/modes são candidatos, não
findings de FILELESS_UNATTRIBUTED: essa categoria foi medida só para o
primeiro erro `_openssl.lib`. Nenhum tipo real por nome foi inspecionado,
nenhum wrapper ou dono foi inferido. LIB é relação por is com o slot do
ModuleType ancorado; não mede tipo CFFI nem autoria independente do objeto.
Os detalhes não foram duplicados em events nem inseridos no inventário.

Inventário aceito430 linhas,77baseline/351etapa0/2etapa1/0etapa2, igual à
estrutura da quarta rodada. Etapa0 com end, etapa1 sem end, etapa2 não
iniciou; sem native_check final ou pico completo do pipeline. Etapa0:
VmPeak101.629.952 bytes de espaço virtual (**não RAM**), VmSize98.193.408,
VmRSS60.403.712, thread1/fds[0,1,2], proc children disponível. Ready membro
VmSize19.599.360/VmPeak20.582.400, supervisor22.048.768/22.339.584;
AS[-1,-1]. Não calibra nova cota nem prova contenção total.

Pico cgroup95.432.704, events max/oom/oom_kill=0, OOMKilled=false; sem
deadline excedido ou exercício do teto192MiB. Linux Python3.11.17/glibc2.36
e kernel6.18.54.1-microsoft-standard-WSL2 registrados dentro do container.
Fontes/cópias, árvore e runtime.json iguais por hash. Membro recolhido,
inventário final[1]/pids1, container removido, engine vazio reconferido;
Desktop inicialmente off iniciado oculto/restaurado por stop exit0, zero
processos Desktop/backend/build/Python depois. Artefatos preservados.

## Fontes e evidência, atribuídas somente à quinta rodada

- probe: `93e654ed43e62e1883274474d8172dc4a65d09449c642ec1f1e8c46462a024d1`;
- observer: `a0eb02128f545e4f20958a0f6ae9e98e715d613dd27a0368dd948396d04d1e8d`;
- summary.json: `1f9e9f6b9c813fd5f6b479c23f59d6c1655544832b5fbad762973c0cf43195d0`;
- control.json: `20cc0e78c46d704cfb75479f2c957d24d8d5f4074aa5fb8b89b8ef5e2d5b2b81`.

Bundle sintético `docs/poc/evidence/linux-imports-batch-20261021.json`, com
originais, hashes, inventário decodificado e desvio de procedimento separado
sem alterar os originais. Sem código novo depois da execução; revisão do
registro/dados e limites solicitada antes de qualquer uso posterior.
Nada fecha B-1/B-2/D-090 ou libera .lib, SQL, worker ou produção.

Revisão somente leitura do registro/bundle concluída na sessão51ea0d85,
sem divergência ou sobrealegação. Acrescentada a ressalva recomendada:
34 examinados =2 nomes já emitidos excluídos +3 candidatos +29 módulos
exatos com __file__ str pulados **sem veredito de origem**. Resolver os
candidatos não garante aprovação dessas29 origens ou da etapa1. O revisor
considerou os dados qualificados suficientes só para preparar desenho de
identidade exata de .lib, não implementar/aceitar ou repetir a rodada.
Pediu antes a nota estática dos outros dois candidatos; feita sem import
em `PHASE-9-STAGE-8-LINUX-IMPORTS-STATIC-NOTE.md`. Procedimento não foi
declarado aprovado e todos os fatos/limitações anteriores permanecem.
