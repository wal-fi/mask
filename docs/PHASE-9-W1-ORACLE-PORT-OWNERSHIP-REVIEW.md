# W1 Oracle: revisão de posse e portas concretas

2026-11-11. Próximo desenho somente, sob delegação. Código e teste duplex
publicados emd9e8293bab4f32295b62ba586d96842f5fb8cb53; fetch confirmou
HEAD/origin iguais,0/0. Bytes dos blobs fonte/teste iguais aos testados.
1410relacionados/195próprios/6sondas e estáticos são evidência desse código;
nenhuma suíte foi repetida por esta reconciliação somente de leitura.

## Reconciliação recebida e lida integralmente

Claude2CLI55131, mesma sessão51ea0d85/claude-opus-5-5/medium, encerrou0/
success em43848ms. Ferramenta permitida somente Read, sem recusas. Root
leu toda a resposta em read-only-reconciliation.json. Não houve edição,
outro escritor, quota ou fallback. A proposta deste próximo escopo é de
Claude2, não atribuir ao Gemini. Nenhuma aprovação individual inventada.

Direção aceita somente para escrever o futuro
docs/PHASE-9-W1-ORACLE-PORT-OWNERSHIP-DESIGN.md, ainda AUSENTE no checkpoint.
Não é aceitação de uma implementação nativa, de argv operacional ou release.
Antes de escrever o desenho, ler este parecer e os contratos atuais; root
lerá o desenho inteiro antes de qualquer teste/RED ou futura fonte.

## Precisões normativas para o desenho, ancoradas no código público

1. Reusar main89c99c65/driverb54a8a94/puro4c155d76/EXPECTce6ff389,
   hoste86f8e32 e bridge5a09be1c sem editar. O reator é o único motor de
   protocolo. Portas/DTOs da ponte,56linhas/512incluindoLF/50controles/
   frames16bytes e reservas originais são fixos. Plano antigo256linhas,
   bind único e APIs antigas não voltam como autoridade.
2. Um owner deve existir por INVOCACAO de helper/ação, não só por classe
   de helper. Os dois ZERO24/ZERO25, erros e resultados tardios precisam
   de registros distintos e retenção, sem sobrescrever a operação anterior.
   Matar/recolher o CLI do gateway não encerra helpers ou conexões de ação.
3. Fechar como owner externo observa fatos físicos tardios sem chamar
   outcome() duas vezes, reobservar op já colhida/quarentenada, alterar
   outcome UNKNOWN original, limpar slot da ponte ou reabrir o protocolo.
   A observação física pertence aos registros nativos próprios do owner;
   o snapshot de protocolo permanece imutável após a primeira observação.
4. Root conferiu runtime/budget.py: CleanupConfirmation é explicitamente
   TRUSTED MODEL, com cinco bools e sem vínculo de identidade. release()
   devolve crédito lógico; BudgetLedger diz que isso não prova retorno
   de commit do SO. Não apresentar esse DTO, todos True ou token lógico
   como atestado nativo. O futuro owner precisa derivar fatos completos
   por identidade/recursos antes de pedir release, com contrato auditável
   próprio, sem modificar BudgetLedger ou criar framework genérico novo.
5. Fixar ponto exato de posse antes de cada efeito e sentido de SENT:
   handoff local completo, nunca ack do peer. NOT_SENT requer zero provado;
   parcial/erro incerto é UNKNOWN e retido. Explicar o que o API público
   concreto pode observar, o que não pode, e como isso produz os DTOs sem
   inventar contagem ou quietude. buffer/drain/is_closing/wait_for cancelado
   não são prova física de cleanup nem preempção do SO.
6. Fechar relógio/poll/deadline e retenção quando o SO não coopera, sem
   prometer teto absoluto com mera task cancelada. Fatos de exit/reap/CID,
   ausência por identidade e cada helper devem ter origens e limites
   claros. O contrato de quiescência fica FORA da ponte, que não ganha
   close/quiesce/ticket/nonce ou outro releaseAPI neste incremento.
7. Propor um adaptador específico e mínimo para o único processo futuro
   de CLI e as seis ações, reaproveitando portas/ledger existentes. Não
   escrever outro motor de protocolo, framework de SO ou cadeia genérica
   de proveniência. Separar a futura ligação concreta e sua prova do fake.
8. Operacionais continuam NOT_PREPARED: runtime/CLI/stdlib pins, perfil,
   margens, raiz, task, nonce, estado, CIDs, rede/IP, credenciais, comandos
   e argv. Não ler nem preencher esses itens agora.300s de freshness não
   é o domínio prospectivo overall300 da ponte. Tentativa consumida não
   renasce por um desenho, ticket de modelo ou novo documento.

## Próximo lote único

Mesmo Claude2/sessão51ea0d85/claude-opus-5-5/medium, após conferir Git
atual e zero agentes ativos. Somente Read/Edit/Write do novo DESIGN, sem
comandos/execução nem outro arquivo editável. Se ativo, apenas monitorar
e recuperar terminal, nunca segunda chamada. Não reutilizar d9e8293 como
guarda de HEAD depois de publicar este checkpoint documental.

Desenho deve fechar assinaturas concretas, fatos/owner/cache/posse e matriz
de falhas para futuros testes determinísticos, incluindo falha antes/depois
de cada reserva/start, escrituras parciais, entrada que não é lida, saída
limitada, wait sem prova, controles originais, late spawn e helper que
sobrevive ao kill do gateway. Testes/RED antes de código; nenhum fake
declara gate físico ou autoriza liberar recurso real.

Fonte/testes/pins/app124/estado16/attempt fixos. Sem Docker/PG/SQL/SO/nativo,
runtime/config/privado/binário/root/nonce/estado/entry/loader/collector/
publisher/comando/deploy. T5físico/B1/B2/D090gate2/C1/D119/TLS/ingressos/
produção continuam abertos; Gateway indisponível. Nenhum novo job/reset:
as5chamadas C2 desse turno terminaram sem quota. A tarefa antiga já entregue
continua sem próximo disparo conhecido; não é promessa de entrega futura.
