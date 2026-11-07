# W1 Oracle — integração SDK e caller owner pendentes

## Atualização documental — 2026-11-07

A retomada executou às05h35UTC, terminou0 e a mensagem foi recebida nesta
conversa, sem próximo disparo. CLI23876 e88521 encerraram0, terminais
recuperados antes da chamada seguinte e zero escritor confirmado.

O desenho DRIVER-SESSION-DESIGN foi entregue, SHA-256
92191298182d4f023c0f2ce336991e825ea23af8fc2dded8f9baebaddb88b614,
16412bytes/297linhas. Root leu a V1 inteira e o delta final; aceita o
contrato técnico sob delegação somente como desenho prospectivo. I1-1..7
e S-1..7 continuam propostos, sem arquivo de teste ou implementação.

Tipo exato/frescor/uso único do owner, controles fora de Exception e
slots ocupados nunca sobrescritos ficaram explícitos. Terceiro bind é
encaminhamento arquitetural prospectivo aceito pelo root, sem executar
mount ou main. Hold, sinais e prova física continuam pendentes.

Upstream24 e app124 por hashes/tamanhos intactos; nenhum teste/source
alterado ou suíte repetida. Dados/revisão em
evidence/oracle9-w1-driver-session-review-20261107/design-final-review.json.
Este lote agendado encerra somente o documento. Não iniciou testes,
código, ingressos, infraestrutura ou produção. Seções abaixo preservam
o estado histórico de06/11, inclusive a ausência do desenho naquela hora.

2026-11-06 em São Paulo. Código publicado ec8e736, D1 medido em114
testes próprios e1122 relacionados. Nenhuma mudança funcional nesta retomada.
Claude2 continua único programador, sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5, esforço medium; root revisa e valida.

## Estado do próximo lote

CLI15745 foi somente Read e encerrou0. Root recuperou o terminal e
confirmou zero escritor antes de chamar novamente. A proposta está
preservada como dados em initial-proposal-review.json, sem aprovação para
testes ou código. Root conferiu nas fontes o harness de WorkerSession,
o builder de frame e o transporte.

A chamada seguinte, restrita a escrever somente
docs/PHASE-9-W1-ORACLE-DRIVER-SESSION-DESIGN.md, retornou
API429/exit1 antes de editar. O documento e
tests/test_oracle9_w1_driver_session.py continuam ausentes. Não houve
retry posterior ao429, outro escritor, outra conta/modelo ou contorno.

O primeiro launcher desta retomada havia barrado uma guarda de HEAD antiga
140be3a antes de chamar C2. O revisor corrigiu para o checkpoint então atual;
essa tentativa não executou o programador. Retomadas devem inspecionar o
Git atual e os pins, evitando reutilizar uma guarda de HEAD desatualizada
após commits exclusivamente documentais.

## Correções exigidas no desenho, antes de testes

1. Não instanciar o World antigo, que cria ledger, token, chave e sessão
   próprios. A factory deve registrar os valores recebidos do driver e
   devolver a WorkerSession real exata com esses valores.
2. Harness novo e pequeno por sessão; reusar comportamentos Endpoint/
   Process/Pipe somente quando compatíveis. Não alterar testes antigos,
   algoritmo do SDK ou produto para adaptar o harness.
3. Encontrar a única reserva SESSION pelos metadados públicos de
   ledger.status, sem fixar slot1. O slot muda com G2.
4. Compartilhar o clock entre driver, _set_idle e todos os ResultDeadline
   construídos pelo SDK. Substituir apenas _deadline deixa o construtor
   direto da query e o idle com clocks distintos. Usar namespaces locais
   ao módulo do SDK em lugar de mutar stdlib global.
5. Snapshot e SessionKey LAB devem ser conferidos no SecretInit decodificado
   e no HMAC. Frames usam identidade recebida, não os defaults do helper.
   O RawChannel de saída precisa ter o tipo público exato.
6. Pin P33MiB-1 deve falhar na query antes de qualquer leitura de cabeçalho/
   corpo D113; open não adquire esse pin. Incluir identidade de resultado
   e DONE inválidos sem exposição externa.
7. run com owner fornecido deve preservar exatamente o objeto do chamador.
   Fechar tipo exato, uso único/freshness e recusa sem efeito para owner
   estrangeiro ou reutilizado; nada de substituição silenciosa.
8. Não alegar preservação de controle dentro da WorkerSession: ela converte
   BaseException em erro fechado de sessão e executa seu cleanup. O
   chamador externo precisa conservar o owner original quando controle
   escapar fora desses trechos.

## Fronteira física futura, ainda não implementada

O main externo deve manter tanto o owner quanto as raízes de binding.
Slots fixos marcados UNKNOWN antes da alocação permitem reter incerteza;
não tornam atômico o intervalo entre retorno do SO e atribuição em Python.
Não presumir que máscaras de sinal não medidas resolvem esse intervalo.
Hold e encerramento do domínio próprio pelo host exigem desenho/prova
físicos posteriores.

Saída segura distingue recursos de referências lógicas: o owner continua
guardando ledger e gerações sem serem recursos nativos vivos. Exigir que
todo objeto referenciado esteja vazio seria uma regra falsa.

Um main/bindings separado implica terceiro script RO pinado, prospectivo
sob delegação e sujeito a revisão, não mudança de pacote ou rebuild.
Carregar código de bootstrap público confiável antes do guard deve ser
declarado como import; toda leitura de segredo e captura permanece depois.
Nenhuma execução, mount ou arquivo de main foi criado.

## Retomada registrada

Resposta C2: limite de sessão, reset exibido às02h30 America/Sao_Paulo.
No horário da medição eram23h24 de06/11 no fuso local: inferência de
reset em07/11/2026 às02h30,05h30UTC. Reset não foi observado diretamente.

A mesma tarefa Maskgw-Claude2-Resume-01a05804 foi reprogramada e relida
Ready para07/11 às02h35-03:00,05h35UTC. Um trigger, uma action,
Limited/Interactive/IgnoreNew, StartWhenAvailable; ação queue nesta
conversa01a05804 conferida por igualdade da mensagem. LastRun05/11 às
23h05UTC/result0 é histórico. A nova ocorrência ainda não executou.

A inscrição não comprova entrega nem liberação de cota. Depende do host,
logon interativo e aplicativo disponíveis. A documentação oficial explica
queue como mensagem para a próxima resposta e a disponibilidade do
computador para trabalho local:

- https://developers.openai.com/blog/mastering-codex-remote-for-engineering
- https://developers.openai.com/training/walkthroughs/scheduled-tasks

## Procedimento conservador

Ler este registro e os dois checkpoints; conferir Git, clock e zero escritor.
Se C2 estiver ativo, apenas monitorar e recuperar o terminal. Não chamar
antes do reset informado. Usar a mesma sessão/modelo/medium; escrever
somente o desenho ausente, com os pontos acima, depois root revisa.
Nenhum teste/source novo até contrato e RED revistos.

Source20, núcleo4c155d76/teste084d62cd, driver e9d8de9b/teste0e9a8cc1,
app124, estado16 e tentativa consumida fixos. T5/gerador/ponte/main/hold/
readmissão, B1/B2/D090/C1/ingressos/produção continuam abertos. Nenhum
Docker/PG/SQL/nativo, runtime/config/binário/privado ou deployment neste
lote. Não foi repetida suíte para documentos e agendamento sem código novo.
