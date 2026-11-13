# W1 Oracle: revisão da reconciliação e contrato do bind

## B4 — desenho B2 aceito somente para primeiros oráculos puros

14959 recuperada exit0/success, mesma sessão/modelo/medium, sem denials.
Root leu TODAS168linhas/8620bytes da B2 original14bd2a00. Para cumprir o
teto editorial, juntou apenas66soft-wraps: tokens normalizados por espaço,
linhas em branco, títulos, tabelas e novos marcadores de lista idênticos;
nenhuma palavra/contrato mudou. Não se afirma comparação de AST Markdown.
Root leu TODA versão resultante:102linhas,
e48639a574de18fb35a6600f6ae05086bf5ba89f45797dae5c98b9eae168ccba.
As duas versões e a evidência da transformação ficaram preservadas.

Aceite sob delegação SOMENTE da direção B2 para criar
tests/test_oracle9_w1_proactor_bind.py. Não é aceite de fonte ou uso nativo.
Fonte0a4dcd57, teste13536b2ba54, probe0192ef43 e todo upstream ficam FIXOS.
_bind_over ainda AUSENTE. Root lê TODOS os oráculos e mede/congela RED
antes de qualquer alteração da fonte. Nunca chamar o bind real nos testes.

Precisões NORMATIVAS para BD-7 e para o futuro chamador:

- O caminho forte deve partir do Throwable recebido e chegar ao loop
  conhecido através do FRAME DO PRÓPRIO HELPER _bind_over. Conferir
  tb_frame.f_code por identidade com o __code__ da função carregada.
  Não aceitar frame de teste/chamador: ele pode conter uma referência
  forte esperada e fabricar um falsoPASS, mesmo que o helper a apague.
- Caminhar no máximo64frames; inspecionar f_locals apenas de frames do
  helper sintético/revisto. Sem runtime alheio/SDK privado, GC/finalizador,
  limpar frames ou alterar controles/tracebacks. Comparar objetos com is.
- Acrescentar sanidades do próprio oráculo de retenção: fixture sintética
  que mantém a referência passa; fixture que a apaga falha MESMO quando
  o frame do teste mantém uma referência forte. Não é stub do bind.
- Obrigações prospectivas do futuro chamador adotadas para este contrato:
  reter um único Throwable exato e seu traceback por invocação; não liberar
  essa custódia ou admitir nova tentativa por mero erro fechado/close
  tentado. Recuperação admitida exige evidência externa aplicável de
  disposição/quiescência da tentativa, a definir no gate nativo próprio.
  O chamador ainda não existe; esta obrigação NÃO está implementada.
- F1 sem objeto devolvido, close bloqueado e a janela de controle
  assíncrono na entrega ao chamador permanecem sem prova de contenção.
  Reter traceback não fecha essas lacunas nem os gates N1–N16/T5/produto.

BD-8 deve verificar apenas a fiação mínima do wrapper e os imports locais;
não prometer cobertura comportamental dos guards reais por AST. A matriz
de falhas prova a regra de contexto/precedência do HELPER FALSO, separada
de efeitos nativos. Nenhuma biblioteca extra ou outro framework de SO.

## B3 — revisão integral do primeiro desenho, antes de testes

53670 recuperada exit0/success, sem denials, mesma sessão/modelo/medium.
Root leu TODAS161linhas/8375bytes do desenho812bc0fb; o relatório dizia
aproximadamente110linhas, mas a contagem real excede o teto120. Snapshot
preservado. Não aceito ainda para oráculos; novo teste continua AUSENTE.

Direção de classe usada como fábrica E referência de tipo é adequada.
Precedência de controles e distinção de gates puros/nativos também.
Revisar SÓ o documento, <=120linhas, sem mudar fonte/testes/APIs:

1. Corrigir a conclusão absoluta de L1. Args vazios não tornam impossível
   reter um recurso: traceback da exceção levantada mantém seus frames e
   locais enquanto o chamador retém o mesmo objeto. Root mediu isso em
   caso Python inteiramente sintético, com args/cause/context vazios e
   referência exata ao objeto conhecido ainda acessível pelo traceback.
   synthetic-traceback-reference-proof.json é evidência da linguagem,
   NÃO do bind, de cleanup ou de um contrato já implementado.
2. Decisão sob delegação para este desenho: explorar a menor obrigação
   explícita do futuro chamador, um único Throwable de bind por invocação,
   retido com traceback original sem serialização/limpeza/substituição até
   recuperação admitida. O helper conserva a referência ao loop conhecido
   no frame da exceção que levanta; não a apaga. Sem novos atributos em
   exceções, registry global ou API pública. Explicar que os chamadores
   atuais ainda NÃO implementam essa obrigação (o chamador host é ausente).
   Se algum caminho concreto não a sustentar, identificá-lo precisamente.
3. Propor oráculo aditivo da retenção de loop conhecido pelo Throwable
   retornado: verificar identidade e caminho forte via seus frames, sem
   confiar só em weakref viva (ciclos ou refs do fake podem dar falsoPASS).
   Só frames/objetos SINTÉTICOS próprios; nunca SDK privado ou runtime alheio.
   Não alterar controles/tracebacks nem executar GC/finalizadores.
4. Não estender essa prova a objeto que a fábrica não retornou. Efeitos
   parciais desconhecidos e close bloqueado/falho continuam sem quitação
   física; o gate nativo deve fechar contenção e posse externa da tentativa
   ANTES de qualquer efeito. Nada operacional é preparado neste documento.
5. Corrigir BD-8: proibir close DENTRO do except PRIMÁRIO, não proibir
   o próprio try/except de cleanup, necessário para tratar suas falhas.
   Evitar oráculo AST que imponha algoritmo em vez da regra efetiva.

O plano de retenção é prospectivo e deve ser conferido nos futuros
oráculos/código/chamador; não transforma P3/1739verdes em garantia nativa.
Manter o contrato de um único close EXPLÍCITO tentado pelo helper,
separado dos automatismos do SDK e de liberação comprovada. Controles
falsos/hostis preservam identidade e nunca têm sua veracidade consultada.

## Histórico da revisão antes do primeiro desenho

2026-11-13.68252 recuperada exit0/success, mesma sessão51ea0d85,
claude-opus-5-5/medium, ferramentas somente Read, sem denials. Root leu
TODO relatório e conferiu as citações críticas no código publicado52cf350:
main/real_system/entry, driverT5, composição do Harness, ponte/owner e bind.
Git grep dos insumos públicos não encontrou chamador do bind fora da sua
definição. Não houve efeito ou inspeção operacional.

A direção de reusar a composição existente é aceita para planejar o menor
incremento. Não se adota um novo framework/coordenador nem se certifica T5.
O main concreto existe no Linux; o host Proactor não é o alvo de produção.
CliPlan/receitas/readmissão continuam NOT_PREPARED e fora deste lote.

## B1 — desenho mínimo antes de testes/código

Próximo SOMENTE docs/PHASE-9-W1-ORACLE-PROACTOR-BIND-DESIGN.md, no máximo
120linhas, pelo mesmo Claude2. Read/Edit/Write só esse documento; sem
comandos, execução, teste/fonte ou alteração de qualquer artefato existente.
O módulo e o teste novo sugerido de bind permanecem FIXOS/AUSENTE,
respectivamente, até root revisar o desenho e congelar oráculos novos.
O teste13536b2ba54 nunca muda; qualquer teste futuro será aditivo.

## B2 — precisões que a proposta de quatro parâmetros não fechou

1. Definir assinatura privada e inputs exatos para fábrica/tipo esperado.
   Não se pode exigir recusa de tipo divergente sem uma referência de tipo
   conhecida. Uma classe concreta usada como fábrica pode fornecer essa
   referência, mas o desenho precisa dizê-lo. Não inserir constantes de
   testes, wrappers falsos no produto ou uma nova API pública.
2. Fixar precedência: o PRIMEIRO controle não-Exception vence qualquer
   falha posterior. Se só havia Exception/fault e close levanta um controle,
   esse controle passa pela mesma identidade. Não exigir PumpFault para
   toda combinação de Exception primária + close falho. Fechar os quatro
   pares Exception/controle, sem bool de controle ou cadeia original criada
   pelo cleanup; manter close fora do except primário.
3. Separar cobertura pura da admissão do wrapper real. Plataforma/thread/
   running-loop do bind real não passam a estar testados só porque o helper
   recebeu uma fábrica falsa. Se não houver um seam público já suficiente,
   identificar esses casos como gate nativo, sem importar/executar SDK ou
   chamar bind_proactor_pump nos testes desta etapa.
4. Fechar posse em sucesso e falha: um close tentado ou que levanta não é
   liberação comprovada. Explicar o destino da referência ao loop conhecido
   e o dever do chamador quando o close falhar; sem registry global,
   liberação fictícia, alteração silenciosa de API ou promessa física.
   Se isso exigir autoridade/contrato além da assinatura atual, declarar
   explicitamente o bloqueio em vez de escondê-lo numa abstração nova.
5. Falha de construção sem loop retornado não permite afirmar zero efeito
   no SO. O SDK pode ter criado recursos parcialmente. Além disso,
   SDK-base_events.py.txt:690–694 contém __del__ que pode tentar close.
   Distinguir a chamada explícita única do helper dos automatismos do SDK;
   não afirmar close globalmente único ou cleanup garantido.
6. Propor matriz curta de oráculos aditivos ANTES da fonte. Preservar todos
   os135positivos/adversariais do pump e o probe0192ef43. Não criar outra
   máquina de protocolo nem alterar owner/DTOs/enums/pins/upstream/app124/
   state16/attempt. Não repetir formatação já concluída ou QA inalterada.

Os defeitos no bind foram identificados por leitura, NÃO medidos: criação
do loop sem fronteira; close substituindo primeiro controle; close expondo
erro cru depois de recusa/Exception. Um teste futuro puramente falso não
é reprodução nativa nem readmissão da imagem. N1–N16/T5/B1fimafim/B2produto/
D090gate2/C1/D119/TLS/ingressos/produção continuam OPEN. Gateway indisponível.

Sem AGY, loop/socket/thread/processo/guard/sinal/nativo/Docker/PG/SQL reais,
runtime/config/privado/ambiente/binário, valores/receitas de root/nonce/
estado/entry/loader/collector/publisher/comando/deploy. Caso o desenho não
possa fechar o contrato dentro desses limites, relatar isso sem codificar.
