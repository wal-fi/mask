# W1 Oracle: revisão da fonte pura de posse

2026-11-11, root sob delegação. Fonte candidata privada, não aprovada e
não publicada. Não houve efeito nativo, PG, SQL, Docker ou deployment.

## Autoria e leitura antes de executar

Claude2 continua em quota semanal observada, sem retry antes de12/11 às
23hUTC informado. Fallback autorizado Gemini Argon high/high, mesma
conversa26d0a462. CLI6415 terminou0/SUCCESS em530,203s; terminal recuperado,
zero escritores conferido depois. O novo pacote isolado tinha apenas os
9blobs públicos já autorizados de fcb18d2,444620bytes. Nenhum teste local,
nota privada, transcript, configuração, ambiente ou binário foi copiado.

Root extraiu um único bloco Python e leu TODAS2494linhas, em intervalos
1–665,666–1268,1269–1885 e1886–2494. Fonte4276d9fc/90393bytes,170funções,
42classes. Só depois da leitura integral copiou literalmente o candidato
para docs/poc/oracle9_w1_port_ownership.py, para QA determinístico privado.
Não é implementação funcional do root nem aceitação para publicação.
O módulo Proactor continua ausente. Teste171/e85f8b53 permanece congelado.

## Medições da V1

- Windows CPython3.11.3/pilha64MiB:171casos,170PASS/1FAIL,0erros/skips,
  4,370s. A falha é a recusa de auditoria exatamente em work_settled_at;
  a fonte usa tempos anteriores aos eventos e aceita a auditoria cedo.
- Mypy strict explícito da fonte, alvos3.11 e3.14: ambos sem erros.
  3.14 é análise estática, não runtime medido.
- Lint PoC vigente E9,F63,F7,F82: limpo. Format check falha.
- Ruff amplo exploratório da fonte:59diagnósticos. Não é o perfil vigente
  de docs/poc; inclui o nome público fixado OwnershipRefusal/N818 e Any
  de namespaces dinâmicos. Não renomear API nem inventar supressão para
  ocultar isso. O perfil anterior é documentado em EXPECT-SOURCE-REVIEW.
- Nenhuma suíte relacionada/integral foi repetida ainda.1410 verdes
  anteriores são históricos. Não declarar integração verde.

## Oito contraexemplos adicionais medidos pela API pública

Roteiro independente do root em owner-source-v1-probes.py, usando somente
os fakes congelados e portas públicas. Não usa efeitos nativos ou modifica
a fonte. Resultados em owner-source-v1-probes.json:

1. **Partida enfileirada não é NOT_STARTED por ausência.** Após begin_spawn,
   registro ARMED é reportado NOT_STARTED. seal+settle encerra sem sequer
   bombear authorize/not_started (zero eventos de autorização). Contraria
   §7: só gate NOT_ARMED ou fato not_started permitem essa conclusão.
2. **Cache muda depois de observado.** SpawnOutcome(True) foi obtido pela
   API; start_failed tardio no Pump durante settle mudou o mesmo op para
   SpawnOutcome(False), objeto diferente. _overwrite_unharvested não tem
   prova de que o resultado não foi observado e viola congelamento único.
3. **Sucesso depois do prazo.** ACT com filho vivo ficou PENDING ao vencer
   o prazo; dados válidos/exit/pipes em deadline+DT, sem seal, fizeram o
   protocolo virar SUCCEEDED. protocol_at=101,0, evento=101,015625. Fatos
   tardios não podem produzir conclusão nova nem usar _last_now antigo.
4. **Erro de handle escapa cru.** write_limits com OSError sintético sai
   como OSError e expõe a mensagem-canário, sem OwnershipRefusal fechada.
   Auditar pré/pós-condições e chamadas ao Pump/handle, não só write().
5. **Controle no handle não é registrado.** KeyboardInterrupt em
   write_limits é re-levantado, mas first_control permanece None. Guardar
   a primeira identidade e fechar trabalho novo em toda fronteira relevante.
6. **Contexto original em falha de bind do read.** OwnershipRefusal usa
   from None dentro do except: __cause__ é None, mas __context__ conserva
   o OSError original. Converter fora do handler como nas demais fronteiras.
7. **DTO público inválido é aceito.** HelperRaw aceita bool em index/code,
   stdout4097 e contadores negativos. V4 exige tipos/domínios exatos;
   não confundir repr constante com validação. Não afrouxar o contrato.
8. **Alias extra de enum é aceito.** Delivery com EXTRA_ALIAS apontando ao
   valor de NOT_SENT passa pelo construtor. Iterar Enum não inclui aliases;
   a forma deve conferir os nomes reais completos do namespace confiável.

Esses são findings do modelo puro reproduzidos, não incidente ou teste de
produção. A V1 não está aprovada apesar de170casos verdes.

## Observações estáticas ainda não declaradas medidas

Os contadores stdout/dropped somam sem saturação2**63-1, embora stderr
tenha essa proteção. O caminho de poll também aceita ops diretos em vez
de exigir a tupla de slots originais revisada. São diferenças de contrato
vistas na leitura; não declarar teste de tráfego2**63 nem prova nativa.
Verificar armazenamento de faults repetidos para não introduzir histórico
sem limite. Nenhum desses pontos autoriza novos efeitos ou exports.

## Próximo incremento seguro

Mesmo programador de fallback, zero escritor antes da chamada: devolver
somente testes ADITIVOS em tests/test_oracle9_w1_port_ownership_review.py
para os oito contraexemplos, sem alterar o teste171 ou a fonte4276. Root
lerá todos os novos oráculos e medirá/congelará RED comportamental antes
de qualquer correção da fonte. Depois, fonte pura apenas, com nova revisão
integral dos deltas. Sem casts/ignore/noqa/skip/xfail ou assertions fracas.

13protegidos/bridge5a/test97/app124/state16/attempt preservados; confirmar
por hash antes de fechar o lote. Código/testes parciais não publicados.
Todos os gates físicos/nativos e de produto continuam abertos; Gateway
indisponível. Agendamento semanal continua sem readback confirmado.

## Revisão das regressões e três sondagens adicionais

GeminiCLI40532 recuperada0/SUCCESS/111,495s. Root leu a proposta inteira,
rejeitada por espaço no identificador, estado OPEN único não prescrito e
categoria PLAN não prescrita para todo DTO. CLI61188 recuperada0/SUCCESS/
109,534s; delta inteiro lido. V2 corrigiu esses pontos, copiada literalmente
e formatada pelo root com AST idêntica:6fe23de0/12806bytes/332linhas.
Ainda NÃO congelada: Ruff apontou docstring101colunas, mypy311/314 dois
acessos a base.d1 que não é export explícito. Importar driver diretamente,
sem alterar o teste171 nem seus exports. Source4276 continua sem correção.

Sondagens públicas adicionais em owner-source-v1-additional-probes.json:

- Segunda WAIT é aceita (dois registros) e substitui a primeira pendente;
  no exit, só a segunda conclui. §5.4 fixa uma WAIT por vida do owner.
- Segunda ReadTake pendente é aceita; o dado resolve só a segunda e a
  primeira deixa de ser acompanhada. Preservar posse da primeira; rejeitar
  sobreposição antes do bind e permitir nova leitura depois de concluída.
- Clock.poll aceita o op diretamente, apesar da interface revisada exigir
  a tupla dos OperationSlot originais. Deve recusar PORT sem bombear.

Esses três casos foram reproduzidos antes de qualquer fix. Acrescentar
regressões no novo arquivo ainda não congelado, preservando os vinte
oráculos propostos, corrigindo apenas estáticos/editorial necessários.
Root lê cada delta e só congela RED após gates limpos. Nenhuma modificação
da fonte ou do teste171 está autorizada enquanto esse RED não for medido.

## RED comportamental23 revisto e congelado

Gemini23146/41840/77697 recuperadas0/SUCCESS,137,422s/76,633s/256,049s.
Root leu todos os deltas e os casos novos. V3 rejeitada ANTES de aplicação:
inventava keyword de FakePump, kind READ_TAKE e campo eof. V4 corrigiu os
APIs e o traço do run_until, sem exigir zero leituras inertes do relógio.
Após cópia literal/format com AST igual, mypy apontou narrowing antigo
de occupied=False através de chamada opaca que pode mudar o slot. V5 é
só helper tipado que preserva as duas assertions False/True e a reutilização
do mesmo slot; patch inteiro lido e aplicado literalmente. Sem supressões.

Final f86f54aa/18106bytes/479linhas, todos os vinte casos prévios mantidos
mais três aditivos. Ruff/format/mypy strict311/314 limpos. Windows3.11.3/
pilha64MiB:23casos,1positivo PASS/22FAIL comportamentais/0erros/skips,
2,914s. Root leu TODOS os22textos de falha: todos correspondem aos onze
findings, nenhum erro de harness, ausência de arquivo ou API inventada.
frozen-behavioral-red23.json fixa os bytes, fonte4276 e teste171e85.
13protegidos/app124 conferidos por SHA/tamanho, Proactor ausente.

Próximo sob delegação: mesmo programador de fallback pode corrigir SOMENTE
docs/poc/oracle9_w1_port_ownership.py contra esses oráculos congelados e a
falha original de tempo de auditoria. Nenhum teste ou upstream muda. Root
deve ler TODO patch, comprovar aplicação exata e medir194próprios antes
de aceitar; depois ampliar à matriz relacionada pertinente. Não implementar
fallback universal UNKNOWN, remover casos, mudar DTO/enum/API ou simular
quitação de recurso. Cache de resultado e protocolo não pode depender de
adivinhar que um resultado já concluído ainda não foi observado. Preservar
também o caso existente de falha de startup na mesma rodada do Pump antes
da publicação: ambos os contratos precisam ser satisfeitos pela fonte.

Observações estáticas de saturação stdout/contadores e armazenamento de
faults continuam para a leitura da correção, sem alegar tráfego2**63 ou
prova física. Op direto, WAIT extra e leitura sobreposta agora têm RED
próprio. Nenhuma fonte corrigida foi aprovada/publicada ainda; todos os
gates nativos/produto continuam abertos.

## Contexto do autor e alternativa pública em andamento

CLI6704 terminou0/SUCCESS em86,475s e foi recuperada; NÃO entregou patch.
O Gemini informou que a compactação automática retirou a fonte2494linhas
do contexto ativo. Essa explicação é relato do agente; root não leu seus
transcripts/histórico nem verificou a compactação por outra via.

Root preparou cópia4276 idêntica à resposta original do próprio Gemini,
com prova de origem/igualdade byte a byte em source-own-return-proof.json.
O reenvio desse arquivo NÃO PUBLICADO90393bytes foi rejeitado pela revisão
automática ANTES de CreateProcess: a autorização anterior não cobria esse
arquivo específico. A prova não foi suficiente para aprovação. Arquivo
NÃO enviado; nenhuma repetição/contorno/novo transporte ou modelo.
own-source-return-rejected.json preserva o motivo.

Alternativa mais segura proposta pelo próprio autor: gerar implementação
completa somente pelos nove contratos públicos. Root preparou scratch
NOVO com exatamente9blobs fcb18d2/444620bytes; nenhum arquivo rejeitado,
teste local, revisão privada, histórico, configuração, ambiente ou binário.
A revisão normal aprovou essa ação distinta sem exportação privada.

CLI94202 está ATIVA, mesma conversa26d0a462/ArgonHigh/high/PLAN-read-only,
devolvendo somente Python completo, sem editar/executar. Recuperar esse
terminal antes de outra chamada; ativo só monitorar, nunca segundo escritor.
Root deve ler TODA implementação antes de executá-la. Source4276 e ambos
testes congelados continuam intactos. Não declarar alternativa como entrega
concluída nem assumir que preservará o comportamento sem medir194casos.

## Retomada12/11: limite de saída e candidato estruturalmente reprovado

Handle94202 não existe mais; resultado terminal salvo foi recuperado.
CLIexit0, mas status do serviço ERROR/finished_reason=error por limite de
tokens da RESPOSTA, não quota. Wrapper mediu807,550s. Não chamar SUCCESS.
CIM fresco confirmou zero escritores. Source4276 e testes e85/f86 intactos.

Resposta194061bytes contém um primeiro bloco interrompido (f818606a,
59187bytes/1795linhas, SyntaxError) e um segundo bloco fechado completo
(a8e65058,134850bytes/3629linhas, AST válido). Root NÃO juntou os blocos.
Preservou ambos, leu TODAS3629linhas do segundo, incluindo trecho relido
para completar uma saída truncada da ferramenta. Nenhum foi executado
ou copiado sobre a fonte de trabalho. Sintaxe válida não é comportamento.

Segundo candidato reprovado por leitura estática, antes de executar:

- _READ_TAKE_STATES global guarda estado, take e owner por id para sempre;
  viola posse/limites por invocação e escapa ao walker que exclui globais.
- _LAST_REACTOR_NS global e sys.modules são descoberta implícita de runtime;
  o desenho exige apenas os namespaces explicitamente recebidos pelo owner.
- records() altera protocol_published e trava outcomes. _physical_of também
  escreve settled_at quando views/audit/fence o chamam; leituras não são puras.
- _on_started marca os pipes abertos com False, mas data/pipe_lost só
  aceitam None e _all_pipes_lost trata False como perda observada. Isso
  recusa dados/EOF normais e pode inferir assentamento sem fato de pipe.
- Disposição direta usa plan_index=-1; complemento aceito fixa0.
- Decoders standalone opcionais/overloads e a resolução ambiente não são
  necessários ao contrato do owner; não introduzir API/fábrica para isso.

Esses são findings estáticos de um candidato não executado, não nova
medição comportamental ou nativa. owner-public-rebuild-review.json registra
as faixas lidas e o status real. Próximo patch deve corrigir somente essas
violações no próprio bloco fechado recente, sem reenviar arquivo rejeitado,
alterar os194oráculos, criar globals alternativos ou regenerar outro motor.
Se o autor já não tiver o bloco literal no contexto, deve informar e parar;
não ler transcript/histórico nem reconstruir por via indireta bloqueada.

## Autorização específica pendente para a correção exata — 2026-11-12

O pedido de patch estrutural com os9blobs públicos NÃO iniciou agente:
revisão automática rejeitou ANTES de CreateProcess também os detalhes
técnicos do prompt derivados do candidato privado e dos oráculos, por
não haver autorização específica para esse conteúdo. Não houve retry,
outro transporte/modelo ou exportação indireta. Esse é bloqueio do serviço
de aprovação, não quota Gemini nem ausência de revisão local.

Root completou o trabalho independente: parecer integral do bloco a8,
artefatos preservados,13protegidos/app124 e source4276/testes e85/f86
novamente íntegros. Nenhum código candidato a8 foi executado ou integrado.

Pacote CONCRETO preparado e NÃO ENVIADO em
pending-four-file-authorization.json,220935bytes/4arquivos:

| Arquivo no pacote | Bytes | SHA-256 |
|---|---:|---|
| CURRENT-SOURCE.py.txt |90393|4276d9fcf8ed47ad9ac829878c3531ac833c3a466757d3c6f676cf00b182c650|
| FROZEN-BASE-TEST.py.txt |107260|e85f8b53a47ae060874555fcaac0eceaa819c361f9c09189fa863dfd66cc56c7|
| FROZEN-REVIEW-TEST.py.txt |18106|f86f54aa1694218e331cd229c9485d8e7707613c29b54a6241089c2d2ffeda6c|
| SOURCE-FIX-REQUEST.md |5176|4ed3e32a22a57e88c54b65b4bddbd30ce6f32b76e994b12c0e635e76361c7626|

Destino solicitado: mesmo Gemini Argon high/high, conversa26d0a462.
Finalidade: somente correção da fonte pura contra os194testes congelados,
sem comandos/execução pelo programador, root revisa e mede antes de publicar.
Exclui credenciais reais, dados de banco, runtime/configuração/ambiente,
binários e histórico de conversas. Não chamar esses arquivos de públicos.
Pergunta específica apresentada ao usuário, RESPOSTA AINDA PENDENTE.
Sem ela, não enviar arquivos ou detalhes privados nem tentar outra via.

Zero escritor deve ser reconferido antes de futura chamada. C2 não pode
ser retomado antes12/11 às23hUTC informado. Agendamento semanal permanece
não confirmado. Goal segue active: houve progresso verificável neste turno,
nenhum critério de conclusão ou blocked atingido. Demais gates abertos.

## Primeira revalidação da autorização pendente

Em12/11 a retomada automática do goal não trouxe resposta à pergunta de
envio. Manifesto continua approval_received=false/sent=false, mesmo Git e
nenhum programador novo. A consulta independente da tarefa existente foi
limitada a15s, expirou e seu helper próprio25752 foi morto/recolhido, sem
alterar tarefa ou serviço. Não há prova de Ready/NextRun; não anunciar job.

Esta revalidação é **no progress**, não espera verificada por agente vivo:
a autoridade necessária permanece ausente, e o agendador não retornou
estado útil. Segundo turno da mesma pendência contando a pergunta original;
limiar de blocked ainda não atingido. Goal permanece active. Sem novo
envio, retry/reformulação do payload rejeitado, publicação ou alteração
dos testes/fonte. A pergunta específica já está pendente, sem duplicá-la.

## Segunda revalidação: limiar de bloqueio satisfeito

Em12/11 às11h58UTC, a nova retomada não trouxe autorização específica
para os4arquivos. Manifesto continua approval_received=false/sent=false;
seus4hashes e a ausência do Proactor foram reconferidos. Git fcb18d2.
Metadados mostram aplicativos/helpers Claude abertos, mas nenhuma chamada
print ou da sessão-alvo; nenhum agy observado. Não iniciou novo agente.

Terceiro turno consecutivo da mesma pendência, incluindo a pergunta
original: no_progress, limiar para goal blocked satisfeito. Solicitar
essa transição ao serviço de goal e reportar o estado devolvido. Nenhum
envio, retry ou contorno; fonte/testes não alterados, sem commit/push.
C2 continua sem retry antes23hUTC informado; agendamento não comprovado.

## Autoriza??o espec?fica recebida ? 2026-11-12

O usu?rio respondeu "autorizado" ? pergunta expl?cita dos4arquivos/220935bytes.
Consentimento registrado no manifesto, com hashes intactos. Os9blobs
p?blicos previamente autorizados foram copiados das c?pias originais
verificadas;13entradas/665555bytes, nenhum outro arquivo privado. Envio
ainda n?o iniciado neste registro; sujeito ? revis?o normal da ferramenta.
A rejei??o hist?rica permanece, sem contorno. C2 n?o foi retomado.

## Patch autorizado recebido:194/1604verdes, dois findings adicionais

CLI46446 terminou exit0, mas servi?o ERROR/limite de sa?da, n?o quota.
Resposta8659da6e/31490bytes/772linhas foi lida INTEGRALMENTE. Um diff
fechado d09f4e30/11hunks aplica com git apply --check --recount. Aplicado
literalmente; candidato4f1e0aef. Ruff mec?nico com AST id?ntica gerou
e0e7297d/95783bytes. Nenhum teste foi alterado.194pr?prios PASS em2,996s;
1604relacionados PASS em30,531s, zero falhas/erros/skips. Mypy expl?cito
3arquivos e src/tests368alvos311/314, Ruff src/tests e PoC restrito limpos;
format3arquivos limpo.3.14 permanece s? an?lise est?tica.

Revis?o adicional reproduziu dois defeitos antes de publica??o, sem alterar
fonte/testes: polling at? prazo+2DT, sem poll anterior no prazo, permite
write_resumed em101,015625 ap?s deadline101 virar SENT/SUCCEEDED; data
recebido no mesmo instante conclui ReadTake vencida com ok=True. Expira??o
s? ao retorno do Pump ? tarde. Evid?ncia em owner-authorized-fix-deadline-
probes.json. N?o publicar este candidato apesar da matriz verde. Corre??o
deve conservar UNKNOWN/resultado de leitura vencida e registrar somente
fatos f?sicos tardios, com bytes ainda sob posse; nenhum novo motor/API.

## Fechamento da revis?o da fonte pura ? 2026-11-12

Root leu TODAS107linhas do suplemento45316; CLI0/servi?oERROR por limite
de sa?da, n?o se inferiu a causa da mensagem nem quota. Diffa295b371
aplicado literalmente, sem editar hunk ou teste. Fonte finala5d233ae/
96838bytes/2657linhas. As4sondagens independentes divergem na fontee0
e passam nesta: handoff tardio, data e EOF tardios, write s?ncrono que
atravessa o prazo. Bytes retidos e outcome de leitura anterior imut?vel.

Matriz repetida sobre a fonte FINAL:1604PASS/30,578s, incluindo194pr?prios,
0falhas/erros/skips. Ruff/format/mypy expl?cito311/314 limpos;368alvos
src/tests limpos, n?o alterados pelo suplemento.15upstream/ponte+app124
conferidos por SHA/tamanho. Nenhum teste congelado mudou. Primeira vers?o
do roteiro adicional consultou segunda leitura pendente e falhou no harness;
corre??o done() ocorreu antes do RED4 e est? distinguida da falha da fonte.

Aceita somente integra??o do MODELO PURO com seus testes; nenhuma aprova??o
nativa ou de produ??o. PORT-OWNERSHIP-VALIDATION e final-validation.json
registram resultados, autoria e limites. Preservar logs/propostas rejeitadas
localmente; integrar s? c?digo, testes, documentos e evid?ncia compacta
revistos. Nenhum programador ativo; Proactor ausente, demais gates abertos.
