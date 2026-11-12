# W1 Oracle: revisão dos primeiros testes de posse

2026-11-11, root sob delegação. Desenho V4 527ab514 e PORT-OWNERSHIP-REVIEW
continuam normativos. Nenhuma aprovação individual inventada. Módulos owner
e Proactor AUSENTES; nenhuma prova nativa ou gate de produto fechado.

## Autoria, candidatos e medições

Claude2CLI84154 terminou1/API429 antes de criar teste, reset exibido13h50
America/Sao_Paulo, inferido11/11/2026 às16h50UTC, não observado. Sem retry
antecipado. Fallback Gemini ArgonHigh/high expressamente autorizado.

Proposta é do Gemini, conversa26d0a462-bc2c-4a73-b7a0-b0ef5f1c80d9.
CLI93789 encerrou0/SUCCESS em857,040s;10cópias públicas intactas, terminal
recuperado. Código extraído26e7bf00/94288bytes/2584linhas tinha um espaço
extra na linha403 e não era Python válido. Mesmo GeminiCLI25209 encerrou
0/SUCCESS em26,422s e devolveu só o diff de um byte. Root aplicou literalmente
à candidata local:67ea9838/94287bytes/2584linhas,105funções/37testes nomeados.
Todos os outros bytes são idênticos. Root leu TODAS2584linhas e a nota final
de seis ambiguidades. Não é fonte escrita pelo root ou pelo Claude2.

Testes locais são rascunho para QA, NÃO aprovados nem RED congelado:

- Python válido após o diff do autor; sem fonte futura.
- Ruff:41ocorrências; format check reprovado.
- mypy strict3.11 e3.14:5erros em cada alvo (3.14 é só análise estática).
- Windows3.11.3/pilha64MiB:3sanidades PASS,137deselecionados pela seleção
  explícita `-k sanity`,0falhas/erros; não é suíte integral ou prova dos
  137casos que dependem do módulo ausente.
- Evidência local em port-tests-review-20261111/v3-statics-and-sanity.json.

## Findings antes de congelar oráculos

1. **DTOs tipados não podem exigir construção com Trap em todos os campos.**
   Linhas1055–1067 criam cada DTO com bt.Trap em campos int/str/enum/etc.
   Isso conflita com "tipo exato validado" do desenho e forçaria afrouxar
   o futuro construtor para passar um teste de repr. Separar a prova de
   repr constante da validação: instâncias válidas por DTO, ou objeto
   deliberadamente não inicializado SOMENTE para conferir que repr não
   inspeciona campos. Manter provas separadas de tipos/domínios inválidos.
   Também Scope/HelperPlan/CliPlan inválidos são construídos fora do
   pytest.raises em PLAN_REFUSAL_CASES; a validação mais cedo já deve ser
   aceita, sem impor artificialmente que só PortOwnership recuse.
2. **Fixtures positivas devem cumprir o contrato do Pump.** Vários testes
   chamam events.data/pipe_lost/exited/write_resumed diretamente fora de
   run_until (por exemplo P3, saída limitada e exit antes de pipes). §2.2
   entrega eventos somente dentro do pump. Agendar e bombear os eventos
   deterministicamente pela mesma seam pública. Não exigir que uma fonte
   correta aceite callback positivo fora da fase prevista. Injeções
   adversariais fora de contrato devem ser explícitas e ter recusa própria,
   sem atestar fatos por chamada privada do owner.
3. **Teste de __getattr__ deve usar ModuleType exato.** HostileModule é
   subclasse e já é recusada pelo tipo exato; os casos atuais não provam
   consulta a vars em módulo normal com hook. Manter a recusa de subclasse
   e adicionar módulo exato com __getattr__ instalado no dicionário e nome
   obrigatório ausente. O hook não pode ser chamado.
4. **Late overflow não deve depender de eventos duplicados impossíveis.**
   No teste de capacidade, o primeiro CHILD já terminou; repetir exit e
   pipe_lost não demonstra três fatos tardios legítimos. Criar filho vivo
   cuja ACT já concluiu UNKNOWN; depois do seal entregar exit e perdas dos
   dois pipes UMA vez cada dentro do Pump. Conferir cap do histórico,
   overflow e assentamento físico conhecido sem reabrir o protocolo.
5. **Estáticos e estilo, sem supressões nem enfraquecer assertions.**
   Corrigir as41ocorrências e os5erros de tipagem, preservando os casos e
   distinguindo Any legítimo de namespace dinâmico de anotação indiscriminada.
   Sem ignore/cast/skip/xfail/noqa/per-file-ignore novo ou mudança no gate.
   Refatorar helpers/testes longos em funções pequenas conservando oráculos,
   em vez de retirar verificações. Root pode formatar mecanicamente com
   prova de AST idêntica; alterações lógicas continuam do programador.
6. **Cobertura de limites não se resume ao default do DTO.** A-limits
   exercita max_writes/max_records/max_late, mas faltam recusas e retenção
   para max_acts/max_audits/max_disposals e limite de takes retidos.
   Adicionar positivos e negativos alcançáveis pela API, com ausência de
   efeito novo no limite; não tentar alocar 2**63bytes para simular saturação.
   Quaisquer limites não medidos devem ficar explícitos, não declarados
   cobertos só porque aparecem em DEFAULT_LIMITS.

## Precisões da nota de ambiguidades do Gemini

- O ClockAdapter recebe tuple dos OperationSlot originais, como a ponte
  publicada exige; valida os ops neles contidos como pertencentes ao owner.
  Não mudar a ponte nem inventar uma interface incompatível de ops diretos.
- Os nomes decode_* no desenho descrevem a semântica dos helpers. Os
  primeiros testes podem demonstrá-la por ActOutcome, AuditReport e
  RecordView/disposição públicos, sem exigir novos exports standalone ou
  importar namespaces não pinados. Não criar API nova só para testar parser.
- `pipes_lost` e índices de plano não têm codificação suficiente para uma
  igualdade literal nova nos testes. Não inventar um valor exato: conferir
  os fatos observáveis e os estados já normativos. A codificação deve ser
  fechada com o autor do desenho antes da fonte; isso não reduz os gates.
- OwnerLimits inválido pode recusar no DTO ou no construtor do owner antes
  de efeito; o teste já inclui ambos dentro do pytest.raises, corretamente.
- CAPACITY é recusa direta do owner ao reservar; PORT é a tradução pela
  ponte. Preservar ambas nas fronteiras próprias, sem exigir PORT direto.

Próxima revisão somente no novo teste, com o mesmo programador de fallback
enquanto Claude2 estiver em quota, sem execução pelo programador. Toda fonte
permanece ausente até root reler os deltas e congelar RED. Nenhum teste
parcial deve ser publicado como integração verde. Pins/app124/estado16/
attempt fixos;1410verdes anteriores são históricos. Sem Docker/PG/SQL,
efeito nativo/runtime/config/privado/binário/ambiente/root/nonce/estado/
entry/loader/collector/publisher/comando/deploy. Gates de produto abertos.

## Patch Gemini revisto; retorno ao Claude2 após horário informado

CLI23618 encerrou0/SUCCESS em579,193s, terminal recuperado. Root leu TODO
o patch1294linhas/54274bytes22089ebf e o inventário final. Direção atende
os seis findings, mas NÃO é patch aplicável: git apply --check --recount
falhou na região2182. NENHUM hunk aplicado; candidata local segue67ea9838.
Não corrigir hunk à mão no root nem atribuir a proposta ao Claude2.

A mensagem da mesma tarefa de retomada chegou nesta conversa11/11 às
16h55UTC/13h55SP. Clock confirmou16h55:34UTC; CIM16h55:43UTC confirmou0
agentes; owner/Proactor seguem ausentes. Já passou16h50UTC informado para
resetC2; isso permite nova chamada normal, não prova liberação de quota.
Próximo somente mesmoC2/sessão51ea0d85/claude-opus-5-5/medium, lendo este
parecer, toda candidata e a proposta de patch, para corrigir SOMENTE o
novo teste. Ferramentas Read/Edit/Write, sem comandos/execução.

Preservar os oráculos existentes, corrigir conflitos descritos e adicionar
limites alcançáveis sem inventar API. Sem supressão/cast/ignore/skip/xfail
ou enfraquecer assertions. Root relê TODOS os deltas e valida antes de
congelar RED; fonte permanece ausente. Patch e candidatas são dados locais,
não integração publicada.1410verdes anteriores são históricos.

## C2 v1: revisão semântica e gates medidos

CLI80494 encerrou0/success em832782ms; terminal recuperado, zero agentes
conferido17h25:26UTC. Corrigiu somente o teste, sem comandos. Candidata
14facd765412cd207ae053d2763695482626449ced2a7fc4a428bf9939aec2d1,
100803bytes/2648linhas/146funções/49testes nomeados. Root leu todas as
regiões alteradas semanticamente (1951linhas), com prova AST dos nós
superiores que ficaram idênticos à candidata já lida. Mapa/delta/snapshot
e terminal preservados localmente; nenhuma fonte futura.

Medição Windows3.11.3/pilha64MiB:4sanidades PASS/165deselecionados,0falhas
ou erros. Ruff0; mypy strict3.11 e3.14 sem erros; format check falha.
Não houve teste funcional do módulo ausente nem RED congelado. Nenhuma
supressão/cast/ignore/skip/xfail adicionada.

Direção das seis correções aceita, incluindo slots reais com fault injection
no método público bind via monkeypatch restaurado pelo pytest. Antes de
congelar, faltam estes ajustes pequenos, somente no novo teste:

1. **Sem esvaziar slot pela API privada da ponte.** Linhas2477/2487 usam
   vars(b_ns)["_empty_slot"]. A fonte publicada a define bridge-private,
   somente após outcome validado absorvido; §7 do desenho proíbe o owner
   de mexer no slot. O teste direto não é a ponte e não pode simular
   liberação limpando-a. Já nasce um OperationSlot fresco por take: manter
   esses slots originais intactos, sem chamar _empty_slot/_release nem
   alterar _op. Preservar as assertions por identidade sobre quais takes
   o OWNER retém; referências externas do teste não são posse do owner.
2. **Limite da varredura não pode aprovar por truncamento silencioso.**
   ht.walk_retained para em profundidade8. A prova positiva da última take
   evita zero falso, mas não protege o teto se uma referência estiver mais
   funda. Usar helper de QA pequeno para o estado simples fake/modelo, com
   visited/identidade e limites explícitos que FALHAM se esgotados, sem
   omitir nós só por profundidade. Não percorrer módulos/classes/código
   ou SO; não criar API de produção nem framework. Declarar o domínio da
   observação: grafo de estado simples, não prova de closure/native/global
   memory. Preservar as provas positiva da última falha e negativa das
   takes bem-sucedidas antigas. A fonte futura será lida integralmente
   também para conferir onde armazena essas referências.
3. **PENDING é operação sem conclusão, não quarentena efetivamente medida.**
   h.run_act usa portas diretamente; não chama bridge.run. A distinção
   PENDING com filho vivo é coerente com §7, enquanto UNKNOWN explícito de
   falha conhecida de transporte/limite conserva seu cache. Aceita sob
   delegação essa correção de oráculo. Trocar só comentários/docstrings
   que dizem que a ponte já quarentenou ou fixou UNKNOWN nesses testes
   diretos. Manter op PENDING e protocolo imutável após fatos tardios,
   sem consultar outcome de op ainda pendente. A prova da ponte real é
   dos cenários que de fato passam por ela, não inferida do helper.
4. **Prazo de startup não é vida útil do processo.** A ponte5a09be1c cria
   spawn_deadline separado do overall (linhas800–801), absorve o processo
   e só então libera o slot de spawn; escritas recebem seus próprios prazos
   (linha902). "Prazo do pai" em §4 significa encadeamento ativo de efeitos
   de ACT/AUDIT/DISPOSE, não reutilizar o deadline já concluído do SPAWN
   como teto de toda sessão. Adicionar positivo: após spawn bem-sucedido,
   relógio fake passa do deadline de startup, processo ainda vivo, nova
   escrita com deadline futuro faz SENT. Sem reabrir spawn ou zerar tempo.
   Manter negativo de novo helper cujo ACT pai chegou ao deadline: nenhum
   efeito de início após ele, sem depender de seal e sem prorrogar prazo.
   Enfileirar request inerte não equivale a iniciar processo; assertions
   devem distinguir a autorização/handle real do fake da fila.

Correções somente por mesmoC2/sessão/Opus5.5/medium, Read/Edit/Write do
novo teste, sem comandos. Root relê delta e pode aplicar Ruff format
mecânico com AST idêntica antes dos gates. Não enfraquecer nenhum oráculo,
não inventar novos exports ou valores operacionais e não tocar upstream.
Essas precisões são revisão sob delegação, não nova aprovação individual.
Sem fonte owner/Proactor antes de RED revisto e congelado.

## Correções finais Gemini e RED171 congelado — 2026-11-11

O usuário autorizou especificamente o envio dos dois arquivos não publicados
CURRENT-TEST.py.txt (100803 bytes, 14facd765) e FINAL-TEST-REQUEST.md
(4341 bytes, 007c4b83). A rejeição automática anterior permanece histórica;
o novo envio passou pela revisão normal depois dessa autorização. Evidência:
specific-unpublished-consent.json. Nenhuma conversa privada ou configuração
foi incluída. Não apresentar a candidata não publicada como blob público.

Mesmo Gemini Argon high/high, conversa26d0a462, PLAN/sandbox/read-only:
CLI61575 terminou0/SUCCESS em448,000s; root leu o diff inteiro. Encontrou
desempacotamento de tuplas de trace de tamanhos diferentes, antes do filtro;
NENHUM hunk V5 foi aplicado. CLI29622 terminou0/SUCCESS em66,531s,
devolvendo V6; root leu todo o delta V5/V6 e conferiu aplicação. Aplicou
literalmente a V6, depois formatou com Ruff e provou AST idêntica.

Essa candidata passou Ruff, format e quatro sanidades, mas ambos os alvos
mypy recusaram um callback que devolvia float em vez de None. CLI18944
terminou0/SUCCESS em26,573s; root leu e aplicou literalmente só o helper
tipado de V7, sem mudar avanço de tempo, ordem ou assertions. Todos os
terminais foram recuperados; zero escritores confirmado após cada entrega.
Não atribuir esses patches ao Claude2. Ele segue em quota semanal observada;
sem retry antes de12/11 às23h00UTC informado, sem reset medido.

Os quatro pontos estão resolvidos nos oráculos:

- Nenhuma liberação privada de slot: os quatro slots externos continuam
  ocupados; a inspeção de retenção começa no owner e conserva identidades.
- A varredura do estado simples tem visited por identidade e falha ao
  exceder profundidade/número de nós. Não atravessa módulos, classes ou
  código; não é prova de closure, memória nativa ou global. A futura fonte
  também deverá ser lida integralmente para conferir armazenamento.
- Casos de portas diretas mantêm PENDING com filho vivo e não alegam
  quarentena executada pela ponte. Fatos tardios não reabrem o protocolo.
- Escrita nova pode fazer SENT depois do startup concluído expirar.
  Em ACT, autorização e handle do próximo helper são recusados depois do
  prazo, inclusive sem seal. Request inerte não é processo iniciado.

Final congelado: e85f8b53a47ae060874555fcaac0eceaa819c361f9c09189fa863dfd66cc56c7,
107260 bytes, 2800 linhas, 151 funções, 51 testes nomeados. Windows
Python3.11.3, pilha64MiB:171 casos,4 sanidades PASS/167 FileNotFound FAIL,
0 erros/skips,4,199s. TODOS os167 falham somente pela ausência do módulo
owner. Ruff/format e mypy strict3.11/3.14 limpos;3.14 é análise estática.
frozen-red171.json e JUnit preservam a medição. RED por ausência NÃO é
evidência comportamental, suíte verde, integração ou produção disponível.

13 protegidos, bridge5a09be1c/teste97c26fbf e app124 intactos por SHA/tamanho;
state16/attempt não tocados. Owner e Proactor continuam AUSENTES. Nenhum
teste parcial publicado e nenhum commit/push nesta rodada.1410 verdes
anteriores continuam históricos. Antes de implementar, fechar as precisões
de contrato ainda assinaladas acima e conferir Git REAL/zero escritor;
apenas o programador autorizado escreve fonte, root revisa e executa QA.

A atualização da tarefa de retomada não teve readback: a chamada de criação
e as consultas ficaram sem resposta; só os helpers próprios foram encerrados,
sem alteração de serviço. scheduled-weekly-resume.json declara explicitamente
registration_confirmed=false. Não prometer retomada agendada nem inferir
estado da tarefa nativa da consulta que falhou no sandbox.

Sem Docker/PG/SQL/efeito nativo/runtime/config/privado/binário/ambiente/
root/nonce/estado/entry/loader/collector/publisher/comando/deploy. Todos
os gates nativos/produto continuam abertos; Gateway indisponível.
