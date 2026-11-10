# W1 Oracle: revisão da primeira fonte do reator host

2026-11-10. Root revisor, sob delegação. CLI97378 terminou0, recuperada;
zero escritor confirmado antes de leitura/execução. Fonte inteira lida:
f7de78b2 (hash integral no registro de sondas). Teste congelado c595c426 intacto.
335/335 passaram,0falhas/erros/skips,5,453s (JUnit3,961s), Windows3.11.3.
Lint restrito PoC limpo; format falha só na assinatura _expectations (3linhas
cabem em1), ainda pendente. Nada publicado nesta revisão.

## Findings reproduzidos com API pública, antes de correção

1. Numérico fechado: Line.at=10**400 gera OverflowError cru e não marca
   REFUSED. HostPolicy.init_s ou t6_margin_s com o mesmo inteiro também
   escapa como OverflowError. _finite_or_none usa math.isfinite diretamente
   sobre int exato que pode não caber em float. Fixar contrato: número não
   representável como duração/instante finito deve recusar TIME em feed,
   POLICY no construtor, sem mensagem original/cause/context, antes de
   mutação parcial. Nenhum teto nativo novo ou leitura de relógio.
2. Sigilo de repr: Line(raw=PACKET) tem repr automático de dataclass e mostra
   o INIT inteiro e as três strings sintéticas secretas. O desenho exige repr
   redigido em TODO DTO com bytes; não só Send. Não houve dado real utilizado.
3. Veredito de efeito: FAILED em TERMINATE/PAUSE mantém NOT_RUN; em RESTORE
   e ZERO24 mantém PASS do RESULT. Contrato4.4 diz casoFAIL para ação que
   falha, UNKNOWN ou tardia. Antes de DRAINING, marcar FAIL do caso da ação
   (20/21/23/24), preservando o resto e proibindo envio/efeito novo. Uma falha
   no restore/zero invalida o PASS anterior; o terminal posterior não o apaga.

Sonda de controle: segundo Exited enquanto ZERO25 pendente já recusa ORDER e
mantém o objeto pendente original; acrescentar teste positivo de regressão.
Evidência independente: independent-v1-probes.json, fonte V1/335/logs/JUnit.

## Precisões aceitas e limites

A projeção imutável (kind/rows/bytes/reason) dos19jobs do mesmo decode_init,
em vez de reter os ExpectedJob integrais, é aceita sob delegação: não existe
expectativa externa nem uso de digest no host; as credenciais não ficam em
campos separados. Não é aprovação individual inventada ou prova nativa.

Mapa extra de saída relatado pelo autor foi lido; nenhuma dessas escolhas
permite CANDIDATE sem a sequência T6 aprovada. Done sem orçamento de kill
não é prova de término e nenhum flag libera recursos: retenção/limpeza física
permanece obrigação do futuro owner. Não usar esse caminho como sucesso.

## Próximo incremento: SOMENTE regressões, fonte V1 fixa

Mesmo C2/sessão51ea0d85/modelo claude-opus-5-5/medium. Somente acrescer testes
em tests/test_oracle9_w1_host_reactor.py; preservar exatamente o prefixo
c595c426/73515bytes. Fonte f7de78b2 fixa até root ler regressões e congelar
RED comportamental. Não aplicar o pequeno formato ainda: fonte imutável.

Casos compactos: inteiro10**400 em Line.at/Delivered.pre/post/ActDone.at/
Exited.at ->TIME pegajoso/sem estado parcial; cada campo HostPolicy enorme
->POLICY fechado; Line repr sem bytes/segredos; efeitos T1/T2-pause/T2-restore/
T4-observe/T5-zero em FAILED/UNKNOWN/tardio ->FAIL/DRAINING/sem ação nova,
e FAIL conservado após ABORT/TERMINAL/EXIT68. Reuso dos helpers existentes,
sem nova API, fake reactor ou enfraquecer asserções. Acrescentar segundoExited
ZERO25 ->ORDER com identidade retida como controle que já passa.

Root medirá RED antes do fix da fonte, relerá todo delta e validará próprios+
relacionados antes de publicar. Sem comando/execução no programador. Sem
SDK/app/estado16/attempt, Docker/PG/SQL, SO/nativo/guard/sinal, runtime/config/
privado/binary/root/nonce/operationalcommand/deploy. Gates nativos e produto
abertos; modelo puro é candidato de evidência somente.

## Regressões lidas, RED366 comportamental congelado

CLI76400 terminou0 e foi recuperada. Zero escritor confirmado; root leu todo
acréscimo113linhas. O prefixo73515bytes/c595c426 ficou idêntico; teste final
f177102a/77736bytes/2144linhas, fontef7de78b2 fixa durante RED.
366coletados:336PASS/30FAIL/0erros/skips em11,672s;14OverflowError,1repr e
15veredictos. Contraprova segundoExited/pendência original passou. Ruff/
format e mypy1teste3.11/3.14 limpos. Este RED prova os três defeitos na
fonte, diferentemente da ausência do módulo no RED335. Dados preservados.

Sem ambiguidade pendente: falha de restore/zero invalida o PASS anterior
do mesmo caso, como exigido pela revisão e pelo contrato4.4. Não altera
RESULT emitido pelo driver, só o veredito agregado do host.

Sob delegação, próximo mesmoC2 altera SOMENTE a fonte para: recusar números
não representáveis de forma fechada antes de qualquer atualização; redigir
Line sem mostrar raw; marcar FAIL do caso de qualquer ação que falhou/
UNKNOWN/tardia antes de DRAINING. Corrigir só a assinatura _expectations
para formato de1linha. Teste f177102a congelado, nenhum fallback ou API nova.
Root lê delta, mede366 e relacionados/estáticos e repete sondas antes de
publicar. Sem autorizar efeitos nativos ou considerar produção disponível.

## Parecer final após fix e revisão

CLI60662 recuperada0/zero escritor. Delta inteiro relido: só três fixes e
assinatura. Fontee86f8e32/38610bytes/1104linhas, testef177102a/77736bytes/
2144linhas intacto.1215relacionados (366próprios) PASS/0falhas/erros/skips
em21,578s;18sondas independentes passaram. Ruff/format370/mypy3653.11/3.14
limpos; PoC fora do mypy/runtimeWindows3.11.3.11upstream/app124 intactos.
Nenhum finding novo nessas verificações. Aceito como componente privado
puro sob delegação, não gate nativo/produção. Histórico e limitações em
HOST-VALIDATION; próximo só desenho de ponte antes de efeitos.
