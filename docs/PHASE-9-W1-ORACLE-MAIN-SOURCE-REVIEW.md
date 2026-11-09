# W1 Oracle — revisão da fonte main D2

2026-11-09, sob delegação. Base24014be, Claude2 único programador na sessão
51ea0d85/claude-opus-5-5/medium. CLI49822 encerrou0, recuperada, zero escritor.
Root leu toda fonte48127217/35382bytes/1122linhas antes da execução.
145/145 passaram em1,587s; Ruff restrito da fonte e src/tests, format361 e
mypy361 alvos3.11/3.14 passaram. Format da fonte reprovou só __init__ do
ThreadHandle quebrado em três linhas. Fonte ainda local, sem publicação.

## Sondas independentes reproduzidas

Dados em oracle9-w1-main-source-review-20261109/independent-probes.json,
somente FakeOS, sem efeitos físicos.

1. MainDecision calcula kind==EXIT/HOLD antes de exigir str exata.
   Objeto estrangeiro recebeu duas chamadas __eq__. Rejeitar tipo antes de
   qualquer comparação e sem executar callback do valor recusado.
2. Durante System.os_write fake, com resultado já concluído registrado,
   retire() devolveu True, safe_exit() True, slot EMPTY; depois houve uma
   linha escrita. O write final False não desfaz a saída já autorizada.
   O contrato exige nenhuma escrita ativa na aposentadoria e nenhum output
   após saída segura. É demonstração de invariante por reentrada fake, não
   exploração real de host comprovada. Reter link durante toda escrita,
   inclusive select/send e falhas; retirement só após operação encerrada.
3. OSError em System.select da leitura escapou como FakeOSError, status OK,
   state POISONED. Falha de I/O deve devolver None/status IO na leitura ou
   False/POISONED na escrita; EINTR/EAGAIN finitos devem ser retomados no
   mesmo prazo, com checagem de estado/prazo a cada retorno. Após consumo
   parcial e erro, poison é obrigatório e impede novo IO.

## Próximo lote: regressões primeiro, fonte congelada

Mesmo Claude2 escreve apenas testes aditivos ao fim de
tests/test_oracle9_w1_main.py; prefixo1723ef50/92893bytes intacto. Nenhuma
alteração de fonte48127217 até root ler todos os oráculos e medir RED.
Cobrir tipos estrangeiro/str subclass com __eq__ contador sem callback;
aposentadoria reentrante durante select e write, slot original retido,
safe_exit falso até write terminar e retirement normal; select com
OSError/EAGAIN/EINTR em INIT/CONTROL e write, incluindo IO após consumo
parcial e proibição de IO futuro. Somente fakes, sem hold/entry-HOLD real.
Nada de skip/xfail/cast/ignore/supressão ou relaxamento de casos anteriores.

Depois do RED revisto, correção só no main e formatação manual do único
hunk da fonte. Upstream25/app124/estado16/attempt fixos. Não fechar gates
físicos, SQL, Docker, PG, Oracle, deploy ou produção por esses testes.

## Parecer final da fonte com SO simulado

CLI28740 encerrou0; zero escritor. Root leu todo delta sobre a fonte inicial
já lida. Fonte372f342f/36213bytes/1138linhas, teste5abe4582/101669/2814.
Prefixo145 intacto,16regressões aditivas revistas e RED161/145pass/16falhas
medido antes da correção,7,463s. Fonte inicial145/145 verde não bastou:
sondas e regressões reproduziram callbacks estrangeiros, retirement durante
write e erro cru de select. Todos corrigidos sem enfraquecer testes.

161/161 em2,150s e585/585 relacionados em4,206s, sem falhas/erros/skips/
xfail. Ruff src/tests, format361, mypy361 alvos3.11/3.14 limpos; fonte deploy
com lint restrito E9/F63/F7/F82 e format, fora do mypy. Runtime Windows3.11.3;
nenhuma medição de runtime3.14/Linux. Upstream25/app124 intactos por SHA/
tamanho. Raw de logs normalizados é recuperável de raw-console-originals.
Sondas finais independentes confirmam os três fixes; métricas e SHAs em
final-review.json. Terminal de cada escritor recuperado antes da próxima
chamada; nenhum escritor/modelo/conta alternativo foi usado neste lote.

Aceito sob delegação somente para SO fake. O binding pressupõe escritor
principal único e não reentrante do driver fixo, não segurança entre threads.
Sem main físico, kernel close, sinais/PID1, hold vivo, Oracle admission,
Docker/PG/SQL, worker real, novo runtime/config/privado/binário ou deploy.
Gates de produto continuam abertos. Próximo: menor plano concreto para
expectativas/ponte host/fixture/readmissão e T5, sem multiplicar camadas
privadas ou executar efeitos antes de revisar o caminho proposto.
