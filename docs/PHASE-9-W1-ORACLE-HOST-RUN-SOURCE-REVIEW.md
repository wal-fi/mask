# W1 Oracle: revisão da fonte do chamador host

## HS3 — fonte V2 revista e integração pura aprovada

81263 terminou exit0/success/is_errorFalse, sem denials; recuperada.
Root leu TODO delta V1→V2 e conferiu os nós anteriores por AST. Dez métodos
do _Run, incluindo finish, _done_outcome, close_pump e _confirmed_closes,
continuam idênticos. A mudança de stopped() apenas expressa uma releitura
de control is not None após chamadas; nenhum ramo real foi removido.
Callbacks tipados preservam a captura por iteração e o acesso dentro do
guard. _member_value exige enum capturado exato e enum.Enum antes de value.

A admissão passa pelo guard existente para todas as leituras: Exception
comum dá recusa fechada; custódia inválida não recebe escrita, input
inválido recebe claim/stage/report antes de retornar, sem bind. Controle
é relançado fora do except, pela mesma identidade, sem bool ou inspeção
de args. Antes do claim não escreve; depois guarda first_control e o
relatório. Esta via de controle na admissão é revisão de fonte, não novo
teste dinâmico: os quatro casos medidos são entradas próprias incompletas.

HR5 foi reconferido diretamente: _done_outcome mantém tipo exato de
BridgeRunResult, depois Done ANTES de outcome e Outcome exato. finish
mantém a conjunção e nunca restaura True após validação reprovada. Ambos
têm AST igual à V1 já lida. H14 continua sem provar dinamicamente esta
conjunção em run_host; não existe alegação dessa cobertura.

Ruff mecânico com AST igual: d4ff01d2→c8d38d21548ad91f735b0389c007d9ec8cfa358c3b3ace63b980d922be851795,
29.936 bytes, 870 linhas. Teste e3ef7737/probes congelados intactos.
60 próprios PASS/1,309s; 1.844 relacionados em14arquivos PASS/26,462s,
0falhas/erros/skips/deseleções. Mesmas sondas: admissão4/4, fixtures5/5,
fronteiras9/9, controles do waiter2/2, witness3/3 com mutante detectado.
Ruff src/tests e lint PoC contratado, format373 e mypy strict win32
373alvos3.11/3.14 PASS. Runtime Windows3.11.3/pilhaQA64MiB;3.14 estático.
149textos protegidos mais teste/doisprobes intactos por SHA (152 ao todo).

Aceite sob delegação SOMENTE para integração do chamador puro com SDK
falso e testes juntos. Nada nativo foi iniciado, contido ou comprovado.
Relatório separa resultado de protocolo, auditoria de escopo e disposição
local; não comprova liberação física. Bind/close/SDK síncrono continuam
sem teto de parede. Sem produto pronto ou levantamento de gate operacional.

## HS1 — V1 integralmente lida; candidata não aprovada

78619 terminou exit0/success,is_errorFalse,sem denials;recuperada. Root leu
TODAS842linhas/28714bytes da fonte5f1e9cbdd3f4f35290b801b6ad844e0517d832f480bee5a0eaa94f21f32bf857
ANTES de executar QA. Teste inicial69545074 manteve bytes do RED56.
Esta fonte continua privada,NÃO aceita;nenhum native/produto foi admitido.

QA inicial:56casos,49PASS/7FAIL,0erros/skips,2,100s. Root leu TODOS7textos.
Cinco falhas são lookup vars(dict) do TESTE;uma é mínimo15 indevido no
cenário H11 sem auditorias;uma AST exige chamada direta,embora o código
use bound-method guardado. Ver HOST-RUN-TEST-REVIEW HT4 e contraprova.

RuffPoC contratual PASS;format-check FAIL. Mypy strict win32311/314:
11erros iguais (2None.value,7unreachable por narrowing de atributo mutável,
2lambdas com parâmetro default não inferido). Runtime apenas3.11.3.

Conferência DIRETA da obrigação HR5 não coberta por H14:
- _done_outcome:689–697 checa BridgeRunResult exato,depois Done exato ANTES
  de outcome,depois Outcome exato;objeto estrangeiro não tem getter lido.
- finish:657–664 faz conjunção da coleta e do estado completo anterior,
  invalida se result existente não produz outcome válido e só depois
  decide stage;nenhum check reprovado volta a True. Isto é revisão de
  fonte,não alegação de teste dinâmico adicional dessa via impossível
  pela composição admitida sem adulterar os motores.

## HS2 — defeito de admissão reproduzido ANTES de correção

Sonda root probe_host_run_review_findings.py usa somente run_host público
e carriers próprios incompletos,sem mudar produto/SDK. Quatro casos
(custódia sem slots preenchidos,custódia sem report,input sem campos,
janela sem audit_s) deixam escapar AttributeError. Todos têm0chamadas de
bind. Custódia inválida fica intacta,mas não há relatório fechado;input
inválido já marcou claim e não gravou o relatório. Esperado:REFUSED_CUSTODY
sem escrita ou REFUSED_INPUT com claim/relatório,conforme o objeto errado.

É finding do CONTRATO DO MODELO,não falha nativa nem vazamento observado
de dados reais. Resultado inicial RED4 preservado em
 host-run-review-findings-initial-red.json;script fica igual para repetir.
Não tratar retorno incompleto de dataclass exata como exceção crua fora
da fronteira. Proteger a leitura/admissão de carriers por invariante:
Exception -> relatório de recusa apropriado,sem args/texto/cadeia;controle
não deve ser convertido em recusa ou testado por bool. Reuso/custódia
alheia não recebe escrita. Nenhum efeito antes da recusa de input.

## Sequência obrigatória da correção

Primeiro reparar SOMENTE o teste conforme HT4 e acrescentar RED4 equivalente,
com esta fonte5f1e9c HELD/byte a byte fixa. Root lê deltas e mede RED
comportamental antes de re-congelar os oráculos. O freeze69545074 continua
histórico,não é apagado ou emendado. Depois,mesmoC2 corrige SOMENTE fonte,
sem alterar os novos testes/probes congelados. Root lê TODO delta,repete
MESMAS regressões e gates antes de integração/publicação conjunta.

Fonte futura deve também recuperar mypy sem cast/ignore/noqa/supressões e
sem remover ramos de controle reais só porque a análise de narrowing os
considera unreachable. Captura local/predicado tipado pode expressar a
mutação depois das chamadas;Não bool sobre o controle. Guard explícito
para None.value e callback tipado para lambdas é escolha de implementação.
Root pode formatar mecanicamente com AST igual após as correções semânticas.

N1–N16/T5/B1/B2/D090/C1/D119/TLS/ingressos/produção OPEN;Gateway indisponível.
