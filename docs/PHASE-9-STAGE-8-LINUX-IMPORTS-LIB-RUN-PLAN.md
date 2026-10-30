# Sexta rodada proposta — controle e AS32 estritamente condicionado

**2026-10-21 — plano revisado sem bloqueador; uma invocação nova permitida.**
Depende da revisão do código LIB e do preflight obrigatório. Não repetir
a quinta nem aprovar seu procedimento retroativamente. Não é gate de
produção, SQL, worker ou prova de memória total.

R1 resolvido pela opção(a) recomendada na revisão: **nenhuma segunda
tentativa sob este plano**, mesmo após abort somente de preflight. Registrar
o abort sem create/pending, parar e preparar um registro/revisão próprios
antes de qualquer outra invocação. Não reaproveitar esta autorização.

## Pergunta e escolha do modo

Escolha explícita: uma invocação `--run`, não `--diagnose`. Controle sem
RLIMIT_AS primeiro; caso limited de32MiB só se o controle completar as três
etapas, sem audit_error/check_error/batch/protocolo inválido e com cleanup
confirmado. É o fluxo anterior do observador, não novo comportamento.
Se o controle falhar, registrar e parar: não adicionar exceções nem repetir
caso nesta rodada. Se limited falhar, registrar categoria/etapa/returncode
sem aumentar cota, repetir até verde ou atribuir causalidade ao AS.

Objetivo: medir se a associação exata do slot lib fecha no runtime real e
deixar as regras antigas decidirem sobre os wrappers e29 origens, sem
inferência prévia. O controle pode continuar inconclusivo. NON_MODULE da
quinta não prova tipo; nota estática dos wrappers não prova identidade.
Mesmo controle completo não certifica setup de aplicação completa.

Fontes novas próprias: probe com regra exata L1(a)/L2 e observador com
preflight obrigatório. Congelar hashes/cópias antes de rodar, distintos dos
93e654/a0eb021 da quinta. Mesma imagem pinada8a00ecb8..., árvore parcial
a81ce6d2/tree8a60924c..., helpers AS congelados, pins/dependências e produto
D-115. Não baixar, instalar, rebuildar ou copiar checkout/segredos.

## Preflights e disciplina do executor

1. Reconferir Git/hash dos arquivos do lote, produto/D-115 e árvore preparada;
   nenhum outro escritor/processo de teste. Nenhum Docker alheio tocado.
2. Registrar estado inicial do Desktop. Se off, pode iniciar **oculto** e
   aguardar até30s sem lançar carga. Fazer uma chamada externa version com
   helper bounded já revisado, timeout5s/16KiB. Qualquer falha encerra a
   tentativa antes da carga: registrar abort próprio, não chamar observador
   dependente. Só checks seguros/cleanup do que esta tentativa iniciou.
   Não encadear tool calls sem verificar exit_code de cada dependência.
3. Readiness externa aprovada não substitui preflight interno: o observador
   fará suas polls limitadas version, ps vazio e image inspect antes de
   qualquer create. Flag interna obrigatória não pode ser forjada pelo
   executor. Abort interno tem cases=[] e raiz própria, não medição válida.
4. Uma invocação do observador, nova raiz. Mesmos envelopes192MiB/swap0,
   CPU1/pids16/shm1MiB/nofile64/core0, rede none/RO/UID65534/capdropALL/NNP,
   sem portas/ambiente de host;30s/caso/120s/lote e caps de resposta antigos.
   Sem SQL, banco, pressão extra ou serviço operacional.
5. Tratar exit2 do observador como resultado não-fit/inconclusivo **somente
   depois de inspecionar o resumo**, não como autorização de continuação.
   Conferir cleanup/inventário próprio, fontes/árvore/runtime.json iguais,
   watchdog fechado e ausência de interferência. Se algum recurso incerto,
   não iniciar outro caso/rodada. Nunca remover container alheio.
6. Salvar sumário/casos/hashes e inventário em bundle do checkout para revisão
   somente leitura; manter originais congelados fora dele. Restaurar Desktop
   off apenas se esta tentativa o iniciou e inventário seguro/vazio. Se
   não puder confirmar, reportar sem forçar shutdown de trabalho alheio.

`fits_as32` exige todos os imports e native_check, inventário completo igual
ao controle e pico limitado<=32MiB. `did_not_fit` não prova causa; sucesso
de import não prova espaço para query/AST ou memória compartilhada/native.
Não usar pico virtual como RAM. Lacunas B-1/B-2/D-090 permanecem abertas
independentemente do resultado. Sem mudança de produto/SQL/produção.

Expectativa declarada antes da execução: VmSize antigo stage0 cerca de97MB
(VmPeak cerca de101MB) já excedeu32MiB; se o controle completar, é plausível limited não
caber. Isso não antecipa o resultado real nem atribui causalidade ao AS;
registrar apenas categoria/etapa/returncode efetivamente observados.

Revisão final somente leitura na sessão51ea0d85 confirmou R1(a), o teste
adicional e ausência de bloqueador para uma invocação. A precisão VmSize/
VmPeak acima foi corrigida antes de executar; nenhum código mudou depois
da revisão. Hashes conferidos pelo executor (não atestados pelo revisor):
probe e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b;
observador5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e.
Nenhuma cota observada, job novo, segundo escritor, commit ou push.
