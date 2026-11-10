# W1 Oracle — revisão da implementação local T5

2026-11-10, sob delegação. Base publicada `5a3dec7`. Incremento local ainda
incompleto: o main fixa o hash/API antigos. Não publicar a fonte parcial.

Claude2, sessão51ea0d85/claude-opus-5-5/medium, CLI30613 recuperada0,
escreveu somente o driver. Root leu o delta completo de 432 linhas sobre
a fonte39a68904 já revista: candidata8c67ee4e/51.515bytes/1.406linhas.
Teste congelado3402d681 permanece intacto; zero escritor confirmado.

## Verde insuficiente e findings reproduzidos

83/83 passaram em1,519s, sem falhas/erros/skips; lint restrito da fonte e
formatação passaram. Isso não bastou para aceitar a candidata. Sondas do
revisor, somente sobre os mesmos fakes e pelo run público, reproduziram:

1. **Reserva tardia:** retorno da reserva no instante1015 para prazo1014
   ainda foi seguido por adopt. Resultado ABORTED depois da adoção; houve
   transição de abertura posterior ao prazo.
2. **Verificação OPENED tardia:** compare_digest verdadeiro delegado ao
   algoritmo real, seguido de avanço do clock fake, permitiu READY1015
   com open_end1014 e RESULT24 PASS. É falso positivo do limite de abertura.
3. **Metadado pid tardio:** um getter do processo fake avançou o relógio;
   leitura do cabeçalho GUARD ocorreu1015 com prazo1014, antes da checagem
   posterior. Não houve INIT, mas o próximo I/O indevido foi demonstrado.

Nenhuma sonda executou hmac falso, mudou algoritmo do SDK/global da stdlib,
criou recurso físico ou comprovou exploração nativa. A observação do
compare_digest foi ligada somente ao namespace do driver e delegou a
comparação real antes de alterar o clock fake. Dados em independent-probes.

## Próximo passo obrigatório: regressões antes do fix

**RED comportamental revisto e congelado:** CLI34179/24079 recuperadas0,
zero escritor. Teste2b509c87/50.963bytes/1.292linhas. Root leu todo delta
aditivo e a última correção somente de anotações; AST das funções anteriores
preservada. 89 casos:86 aprovados/3 falhas,0erros/skips,3,392s, exatamente
reserva tardia, verificação OPENED tardia e metadado pid tardio. Ruff e
format364 (inclui driver), mypy363 src/tests alvos3.11/3.14 limpos. Fonte
8c67 permaneceu fixa durante a medição. root Ruff não mudou o teste.

Próximo lote sob delegação: corrigir somente o driver nesses três pontos,
teste2b509c87 congelado. Sem migração ou alteração de main/pins/SDK/testes.
Root lê o delta completo e repete os oráculos antes de qualquer publicação.
Não anunciar integração: main continua com hash e portas antigos.

Somente o teste T5 recebe regressões aditivas para os três cenários.
Fonte8c67ee4e fica fixa até root ler os novos oráculos e medir/congelar RED.
As 83 funções/casos prévios não podem perder asserções ou ganhar fallback.
Após reserva tardia, reter conservadoramente o token sem chamar adopt para
viabilizar limpeza. Após abertura tardia com processo conhecido, limpeza
comprovada deve terminar em ABORT SESSION, sem READY/RESULT de EOF/T6.

Precisão sob delegação para a ambiguidade do desenho: se o próprio close
da ponta do pai retorna quando a cerca já venceu, nenhum wait natural é
elegível. O caso usa fallback de limpeza e FAIL NO_EXIT, nunca PASS. Essa
é a interpretação conservadora já aplicada na candidata, coerente com a
regra de que kill não produz EXIT_LATE/EXIT_NONZERO. O passo11 da v3 dizia
EXIT_LATE e fica superado somente nessa situação; o restante da tabela de
returncodes/prazos permanece igual. Acrescentar oráculo explícito desse
ramo, sem alterar limite, janela ou critérios nativos para obter verde.

T5/B1/B2/D090gate2/C1/ingressos/produção continuam abertos. Nenhum Docker,
PG, SQL, processo/socket/thread/guard/sinal/controle nativo do produto,
runtime/configuração privada/binário operacional, nonce real ou deploy.

## Fonte corrigida: verde restrito, integração ainda ausente

CLI38482 recuperada0; zero escritor. Root leu o delta de seis linhas sobre
a candidata já lida. Fonteb54a8a94/51.913bytes/1.412linhas, teste2b509c87
intacto. 89/89 em2,146s, sem falhas/erros/skips. As três sondas independentes
agora recusam adopt, GUARD e READY indevidos. Lint restrito da fonte,
Ruff src/tests, format364 e mypy363 src/tests3.11/3.14 limpos; deploy
continua fora do mypy. É evidência somente com fakes.

Antes da migração, os dois arquivos antigos do driver/SDK coletaram149:
61 passaram e88 falharam exclusivamente pelo argumento children ausente,
8,687s. Não tratar essa matriz como gate verde. O main também segue de pin
e API antigos, deliberadamente fora desta qualificação parcial.

Próximo lote sob delegação: só `tests/test_oracle9_w1_driver.py` e
`tests/test_oracle9_w1_driver_session.py`, para a migração expressa do
desenho. Fonteb54a8a94 e teste novo2b509c87 ficam fixos. Acrescentar o fake
children/nonce, nono campo de construtores/PortTrap, checker exato de EOF e
SUMMARY sem24 obrigatório. Substituir no sanity o antigo exemplo SUMMARY
vazio inválido por exemplo genuinamente inválido; preservar o teste de
global_pass falso. Mudar somente os veredictos/resumos antigos que exigiam
T5_PENDING. Preservar as demais asserções e acrescentar contraprovas de
EOF/PENDING, sem afrouxar schema ou reescrever casos não relacionados.

Sem publicar código parcial antes dos gates conjuntos com o main.

## Migração do driver concluída em fakes

CLI9390/35214 recuperadas0, zero escritor. Root leu todo delta de migração,
confirmou por AST somente as três mudanças autorizadas nos testes D1;
funções de teste do SDK e EXPECT intactas. D1 ficou37848735/81.023bytes,
SDK e7c2a1c2/45.321bytes. EXPECT teste mudou só os dois literais de pin do
driver para b54a8a94/51913, resultando e24f80a5; fonte/vetores/oráculos
funcionais EXPECT continuam iguais. Os cinco argumentos novos dos fakes
ganharam verificações reais de prazo/fd em vez de supressões de lint.

Matriz final A:645 aprovados,0falhas/erros/skips,7,949s. Ruff src/tests,
lint restrito da fonte, format364 e mypy363 src/tests3.11/3.14 limpos.
Histórico643/2falhas por pin EXPECT antigo e5ARG002 foi preservado, sem
ser reclassificado como verde. Fonteb54 e teste novo2b50 permaneceram fixos.

Próximo lote somente `tests/test_oracle9_w1_main_t5.py`, antes do main:
binding System22/SLOTS10, pipe2 preguiçoso, posse dos quatro fds antes do
Popen, env/argv e herança exatos, prazos, reap e limpeza através de FakeOS.
Reaproveitar o harness do main; relógio/ledger/owner únicos nas composições.
O novo teste é o próximo trabalho do programador. Nenhuma mudança do
main antes de revisar os novos oráculos e medir/congelar RED:
fonte main372f342f permanece fixa nesse primeiro lote de testes.

## Integração fake com main fechada — 2026-11-10

A incompatibilidade parcial mencionada nos blocos históricos acima foi
resolvida no lote B, revisto em T5-MAIN-REVIEW. Main89c99c65 usa pin/API
b54a8a94 e System22/SLOTS10; testes migrados deliberadamente. Gate conjunto
849pass12,615s, sem falhas/erros/skips; statics limpos. Isso permite publicar
os componentes coerentes do laboratório, sem fechar qualquer gate nativo
ou de produto. Fonte driverb54 e testeT5 2b509c87 permaneceram fixos.
