# Orçamento prospectivo do ensaio público do leitor — proposta

**Envelope aceito47012, com as quatro precisões incorporadas abaixo.** Base
somente para propor uma matriz23 diagnóstica; não executa/libera rodada.

2026-10-31, sob delegação vigente. Evidência de pins3eb3 aceita69592, sem
repetição. Orientação1125 aceita envelope de planejamento para uma primeira
matriz23 fail-closed; controle de tempo separado não é necessário por si só.
Conta/hipóteses revisadas47012, sem P1/P2. Nenhum root/attempt,
exportador/preparador/comando de rodada ou efeito nativo é criado aqui.

## Regra de planejamento, não teto de SO

Escolha técnica sob delegação, sem inventar aprovação individual: fator2
sobre maiores observados dos pins, pois há só5samples/modo e a VM ativa
disputará IO/CPU. Não é garantia contra outliers. Não mudar host8c/entradaafaf,
B300, owner12, shell8, watchdog600, margem507/600 ou retenção655/HELD.
Nenhum dado privado/raw é usado, nenhuma amostra lenta é descartada.

Fonte medida de pins: PIN-CAPTURE-RUN-VALIDATION/result.json. Referência parcial
de CLI: T4v2 pública42d363a11156, conforme SHELL-HOST-DESIGN: create≤0,328s,
inspect≤0,141s, rm≤0,141s e ausência≤0,140s observados. São amostras Oracle/
outro wrapper, não medidas desta imagem/PG/attach. Não subtrair eventualmente
custos já inclusos no registro histórico; somá-los novamente é conservador.
Cauda de rm6,3s é **histórico citado**, sem evidência primária da medida
neste pacote; W1 registra também sua reprodução fake. Não promover esse
fake a tempo nativo. O valor permanece só allowance separado de planejamento.

Hipóteses novas e **não medidas**, declaradas antes de qualquer rodada:

- Volume ls:0,5s por chamada; duas por caso. Não veio da amostra T4.
- Owner O:2,0s médios de overhead por caso, excluindo os8s dos WAIT. Inclui
  admissão de runtime/pins próprios do canal, spawn/start do container,
  READY, vetor, exit, EOF e
  handles. É plausibilidade de engenharia para wrapper público local sem
  initdb/servidor/rede externa, não latência demonstrada. O sucesso da sonda
  PG anterior só prova funcionamento parcial, não prova esses2s.
- w:0,5s médios por caso de persistência/fsync/troca de monitor/metadata,
  incluindo o join sem fire de cada monitor (poll stop.wait0,1 no código;
  cerca2,3s totais seria referência nominal, não tempo nativo medido).
  Não veio de teste fake nem da soma de durações dos pins.
- Só uma cauda adicional6,3s de rm na estimativa. Repetição de caudas é risco
  de reprovação, não fenômeno medido nem excluído pela hipótese.

O propósito é decidir se vale a tentativa diagnóstica. O tempo real de O,
CLI e fsync será dado da primeira matriz; violar hipótese não autoriza retry,
ampliar limites ou converter NOT_PASSED em passe. A presença de hipóteses
não libera serviço, DB privado ou SQL. São somente canários públicos.

## Janela B,23casos

Contagem aceita:6NORMAL+4CLEANUP e8CLIs por caso. As8 são volumes-before,
create, inspect-pre, inspect-result, inspect-cleanup, rm, ps-absence e
volumes-final. Pins desses comandos entram em P, não em C. Não há PowerShell
em B; construção23monitores é anterior a A/B.

P típico usa medianas de pins:6×0,1944215+4×0,169269=1,843605s.
P conservador usa2×maiores:2×(6×0,2424909+4×0,2221903)=4,6874132s.
C referência=(0,328+3×0,141+0,141+0,140+2×0,5)=2,032s/caso.
Usar C referência mesmo no típico, embora contenha maiores observados;
conservador dobra todo C, inclusive hipótese de volume:4,064s.

Modelo: **B_estimado=23×(P+C+O+w)+24+6,3**.24 são3WAIT×8s; somar O como
overhead não contado nesses8s. Owner continua limitado12s na implementação.
Não somar12s completos e depois24 novamente como se fossem disjuntos.

| Cenário | P | C | O hipotético | w hipotético | B estimado | Folga |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Típico/meta210 |1,843605|2,032|2,0|0,5|176,938915|33,061085 até210|
| Conservador/meta300 |4,6874132|4,064|2,0|0,5|289,0825036|10,9174964 até300|

Todas as durações estão em segundos. A meta típica70% é satisfeita por esta
hipótese; a folga conservadora é pequena, explicitamente3,64% de300.
Se20casos rápidos/3WAIT forem mais lentos, asyncio.timeout cancela o foreground
em curso; gate antes dos comandos recusa efeitos novos. Coleta com supervisão
e falha no histórico permanecem. Não se promete completar23.

Resolver a incógnita O sem escolher outra latência: com demais termos iguais,
a média permitida é≤3,4374385s para210 e≤2,4746738s para300. Hipótese2s cabe
em ambas, mas permanece sem medição. O e w não foram dobrados no conservador:
a média permitida de O já precisa absorver a lentidão de Desktop/VM ativos
sobre admissão, spawn, attach e coleta; não somar essa disputa depois como
se fosse margem livre. w0,5 também é hipótese, não promessa de fsync/join.
Alguns owners podem chegar12s; sua soma
dos tetos276s, antes dos CLIs/pins, não cabe. Esse pior caso não é o cenário
estimado; não alegar garantia de prazo ou probabilidade estatística.

## Depois de B, aritmética conservadora de aprovação

Preservar estrutura antiga com **32s**, não31:2quiesce×3 + lock1 + cleanup25.
Somar pins novamente mesmo quando parte já é consumida dentro das janelas,
para não tratar os seconds dos CLIs como duração completa. Contar um join55
de excesso síncrono e outro55 antes de restore é deliberadamente conservador;
não afirmar que todos23joins demoram55. Só um caso fica ativo por vez.

qC=2×0,2221903=0,4443806s; qF=2×0,3487221=0,6974442s (maior pin observado,
usado também como allowance síncrono). Reservas para recompilação/IO/journal/
persistência:15s antes e15s durante/depois de restore, **não medidas**. Não
derivar30ms de builder_ns: builder inclui outros custos e não isola compile.
Os30s são allowance de planejamento sob delegação, não prazo imposto ao SO.

Antes do restore:300+55+32+55+8qC+qF+15=461,252489s<507.
8qC cobre6invokes de coleta com kill/reinspect e2globais, além dos32s.
Restore/final:93+20qC+qF+15=117,5850562s.
Total:578,8375452s<600, folga21,1624548s. A/admissão/constructors e seus pins
ficam fora de B; não são adicionados silenciosamente a esse limite relativo.

É envelope **condicional**, não garantia de limpeza ou memória/IO do kernel.
No caminho com kill, tetos dos6CLIs somam24s; pins podem ultrapassar cleanup25
porque remaining é calculado antes deles. CLEANUP_DEADLINE reprova e mantém
coleta/monitor/HELD; não ampliar25 nem suprimir esse erro.

Se fire ou prova falhar, não aplicar o cenário de aprovação acima: conservar
recursos/loop, aguardar emergência/mutex e join positivo antes da coleta única
permitida. Ultrapassar600/655 não libera posse nem transforma coleta incerta
em comprovada. Restaurar Desktop somente depois dos joins/provas positivos.
Pins de emergência leem sincronamente e só depois conferem1s; nenhum teto
absoluto de IO é alegado. Limitações originais permanecem.

## Fechamento47012 e próximos requisitos

Claude2 aceitou este envelope prospectivo para propor **uma** matriz23
pública com falha fechada, antes de materialização/comando próprios. Recalculou
todas as contas e conferiu a classificação dos números, sem executar código.
Quatro precisões de cancelamento/termos O-w/histórico6,3/contenda incorporadas.
É decisão técnica sob delegação, não aprovação individual inventada. Não é
aceite automático da rodada: exportador para23diretórios, preparador/estado
≤32768/admissão3s e proposta/comando continuam exigidos. Não executar nada
com base apenas neste arquivo. Sem segundo escritor/quota/job/novo Docker.
B1/B2/D090/C1/SQL/Gateway/produção permanecem abertos ou indisponíveis.
