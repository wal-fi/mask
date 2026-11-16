# N-S: revisão da primeira implementação e compatibilidade de members

## Fechamento R1 — fonte final e gates de 2026-11-16

89656 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODO delta: nome local exact→minimum e predicado de intervalo herdado em query_members. AST de TODOS os demais nós idêntica à fonte86d, comprovada mecanicamente. Fonte final465ae9067e0f24fe656259e3757f45e8a5788f55ed177db2ab82160d5b6ba5ae,394linhas/15.836bytes. Teste37a permanece intacto; nenhum oráculo foi alterado para obter verde.

Root mediu100próprios PASS em3,810s e2.321relacionados PASS em21arquivos/47,771s;0falhas/erros/skips/deseleções. Ruff produto/PoC contratado,format377 e mypy strict win32 311/314 em377arquivos PASS,314 somente estático. QA direta sem wrapper64MiB. Backend/adapter/qualificador/C0 e antigos fontes/testes intactos. Ver recibo final e EXTERNAL-JOB-ADOPTION-VALIDATION. R1 fechada como compatibilidade com leitor pinado sob SDK falso; não é medição física do kernel ou admissão N-H/N-C/produto. Históricos abaixo preservados.

## R1: regressões medidas antes da correção

36387 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODO delta do teste: só o dado short de MEMBERS, fault padded e duas funções positivas. AST de TODOS os outros nós idêntica ao teste7601. Nova revisão37a757ad69b8d032e44e59d008a183149f9bb1f6fd0f46901553e0b00fbc9224,42.063bytes/994linhas, congelada localmente; o RED98 anterior permanece intacto.

Contra fonte86d INALTERADA:100casos,98PASS e2FAIL exatamente nas novas regressões (adopt REFUSED_QUERY indevido; pré-resume WIN32_RESUME indevido),0erros/skips/deseleções,3.423s. Ruff/format/mypy311/314 em2arquivos PASS. Recibo external-job-adoption-padding-frozen-red-20261115.json registra cada motivo; dados não foram inventados para ajustar a implementação.

Próximo único lote: C2 fonteONLY, trocar o predicado de comprimento de members para o intervalo herdado mínimo<=length<=sizeof(info), mantendo count/assigned/PID bounds e o resto. Teste37a e backend/adaptador/referências/C0 ficam READONLY. Root lê TODO delta e compara AST dos outros nós antes de repetir QA. Sem efeitos nativos ou aprovação de produto.

77890 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root confirmou zero escritores e leu TODAS394linhas do fonte86d2049eef7203ea4c9b99d4e2eb772ee1b7493d870f668089e4b84a5ca0ec43,15.832bytes. Teste7601d8a permaneceu congelado e intacto. Fonte candidata, ainda não integrada.

Gates próprios iniciais:98/98PASS,0falhas/erros/skips,2.690s no JUnit; lintPoC contratado E9/F63/F7/F82, format e mypy strict win32 alvo311/314 em2arquivos PASS (314 estático). Isso não encerra a revisão e não é prova nativa/produto.

## R1 — falso dado de truncamento no oráculo e estreitamento indevido no fonte

O contrato herdado do backend _members e do adaptador _job_members aceita header+count*entry <= returned_length <= sizeof(info). O fonte novo aceita SÓ comprimento mínimo EXATO ou buffer cheio. A escolha mais estrita foi descrita como feita para o oráculo short. Entretanto o fake V2 usou sizeof(info)-1 para MEMBERS; em uma lista variável esse valor ainda pode pertencer ao intervalo admitido pelo contrato pinado.

Root mediu com o SDK FALSO:header8,entrada8,count1,mínimo16,buffer24,retorno23. O método PÚBLICO members herdado aceita essa resposta; a verificação de C nova recusa a mesma resposta bounded, provocando WIN32_RESUME/LAUNCH_FAILED. Recibo external-job-adoption-members-contract-probe-20261115.json. É uma divergência estática/de compatibilidade de contrato, NÃO afirma medição de semântica do kernel real.

O dado que root congelou como short estava incorreto para MEMBERS. Correção deve ser bilateral e não ajustar código/teste para manter verde artificial:

1. Preservar o RED98 original, teste raw7601 e fonte86d como história. Reabrir SOMENTE o dado short para MEMBERS e novas regressões positivas. Nenhuma asserção antiga é relaxada.
2. PRIMEIRO C2 edita SÓ tests/test_oracle9_w1_external_job_adoption.py. No fake, short de MEMBERS deve reportar abaixo de header+count*entry (por exemplo mínimo−1); para estruturas fixas, sizeof−1 continua inválido. Acrescentar fault padded que reporta sizeof−1, e DUAS regressões positivas (fase adopt/count0 e fase created/count1) aceitando esse comprimento dentro do intervalo original. O fonte permanece86d READONLY.
3. Root lê TODO delta, prova que demais nós são iguais, mede as DUAS regressões falhando contra86d e todos os demais casos íntegros. Só então congela nova revisão do teste, sem sobrescrever a prova anterior.
4. DEPOIS C2 corrige SÓ o fonte para o intervalo herdado, mantendo limites de array/count/PID e todo o resto. Nenhum novo contrato de SO ou ajuste de backend/adapter/frozen reference. Root relê delta e repete os gates antes de integrar fonte+testes juntos.

Não preservar uma diferença de contrato só porque os98testes iniciais ficaram verdes. Não afirmar que23bytes ocorreram no kernel físico; a compatibilidade é com os leitores pinados já aceitos. Sem chamada real de DLL/job/processo/thread/loop, Docker/PG/SQL/runtime/config/privado/binário/estado16/tentativa/deploy. N-H/N-C/direitos/kernel/S/G/N1–N16/produto continuam OPEN.
