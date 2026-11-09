# W1 Oracle — revisão dos testes do main D2

2026-11-09. Revisão técnica sob delegação, não aprovação individual.
Base publicada5590b59; Claude2 único programador/sessão51ea0d85,
claude-opus-5-5/medium. CLI31468 encerrou0 e foi recuperada; zero escritor.
Root leu as2145linhas de de10f8df/76422bytes, MAIN-DESIGN080c37ab e a
revisão. Fonte main permanece ausente; nenhum efeito físico autorizado.

## Baseline medido, ainda não congelado

118casos:3sanidades passam,115falham em18,255s;114falhas são de ausência do
main,1 é defeito do harness (chunk5 mantido ao esperar frame16 inteiro).
Ausência não prova comportamento. Ruff acusa S105/N818, format quatro
hunks, mypy311/314 duas leituras estreitadas indevidamente. Preservados em
oracle9-w1-main-tests-review-20261109/initial-*.

## Precisões e correções necessárias antes do RED final

1. **Aposentadoria só após fim/controle contido.** O helper clean_root e M12/
   M19 aposentam um link recém-vinculado sem resultado/controle. Isso viola
   §6.6. Registrar resultado real fechado ou controle contido antes dos
   testes positivos. Acrescentar recusa durante LINKED/RUNNING sem término,
   preservando slot/link/IO; depois, aposentadoria legítima sem novo IO.
2. **B5 conservador.** §6.6 reserva link antes de fstat/isatty; falha depois
   da reserva deixa UNKNOWN e HOLD, mesmo sem set_blocking. Não limpar
   UNKNOWN para satisfazer66. Esta precisão substitui a expectativa ambígua
   de M18/66 para tty/arquivo regular. Código66 continua no domínio, mas
   só seria limpo com recusa comprovada anterior à reserva. Testar UNKNOWN/
   HOLD e ausência de set_blocking/guard nesses dois casos, não EXIT66.
3. **Posse do INIT completo.** Adicionar intrusão entre header e corpo;
   leitor secundário não consome dados, envenena e o primeiro nunca entrega
   bytes. O teste atual de CONTROL não cobre a lacuna header/body.
4. **Cercas pós-retorno.** Adicionar CONTROL completo que retorna tarde e
   escrita que completa tarde, além do select tardio. Nada retorna OK;
   veneno/sem IO posterior verificáveis. Adicionar EAGAIN/EINTR finitos.
5. **Retenção no hold.** Capturar valores/estados e identidades dos slots/
   ticket antes dos passos; cópia rasa de dict não detecta alteração interna.
   Usar raiz realmente preenchida/retida e confirmar owner/namespace/ledger/
   sessões/valores exatos através de WOKE/BACKOFF/FAULT, sem reavaliar cleanup.
6. **Decisão fechada.** Além de forge/decision_code, construtores públicos
   inválidos recusam; entrada EXIT finita exercita wiring real com fake OS
   e saída limpa, sem chamar hold ou entry-HOLD. AST deve vincular retorno
   ao código validado, não só constatar a presença de decision_code.
7. **Predicado e reserva.** Acrescentar owner.session_token/endpoints,
   ledger.failed, linha SESSION/quarentena ou output_pin como fatos ruins,
   quando representáveis com ledger real. Verificar reserva múltipla sem
   alteração parcial ao encontrar segundo slot ocupado; ticket/slot originais
   não são substituídos. Não imitar status com fake sempre-verde.
8. **Flags de fonte.** Fake open deve registrar flags; verificar O_RDONLY,
   O_NOFOLLOW/O_CLOEXEC do contrato Linux com inteiros literais esperados,
   sem exigir constantes Linux ausentes no Windows nem chamada real.
9. **M11 negativo T4.** Fechar o oráculo que falta: watcher ainda com posse
   do frame e join negativo não permite nova leitura principal/aposentadoria
   nem safe_exit; somente fakes/portas determinísticas e raiz retida. Não
   alegar prova de concorrência ou ciclo físico23 medido se for composição
   finita de bindings; registrar essa limitação de forma explícita.
10. Corrigir sanidade chunk5 por leitura fragmentada explícita; renomear
    marcador sintético e FakeFailure para atender lint sem supressão; obter
    leituras novas de atributos após chamadas para mypy, sem cast/ignore;
    aplicar manualmente os quatro ajustes de formatação (sem comandos C2).

Preservar casos/asserts anteriores, exceto os oráculos contraditórios acima.
Apenas mesmo Claude2 altera o novo teste; main e25upstream/app124/estado16/
attempt permanecem fixos. Root mede novamente após terminal recuperado e
zero escritor. Nenhum teste de hold infinito/entry-HOLD, global patch da
stdlib ou efeito real. Sem fonte antes de revisão e RED final congelado.

## Revisão R1 e RED congelado

CLI69483 encerrou0, terminal recuperado e zero escritor. Root leu todo o
delta922linhas sobre a versão inicial já lida:1723ef50/92893bytes/2565linhas.
As dez exigências acima foram atendidas para o contrato de testes; os dois
oráculos contraditórios foram corrigidos, sem editar qualquer fonte aceita.

RED final145:5sanidades passam,140falhas apenas FileNotFoundError do main,
0erros/skips/xfail,24,877s, exit1 esperado. Não é evidência comportamental.
429relacionados passaram em2,646s (5sanidades+114D1+35sessão+275puro),
0falhas/erros/skips/xfail. Ruff src/tests, format361 e mypy361 alvos3.11/
3.14 limpos; runtime WindowsCPython3.11.3, sem runtime3.14/Linux.
Upstream25/app124 por SHA/tamanho intactos; main continua ausente.

Aceito e congelado somente como RED para o futuro módulo. Não fecha gate
físico/produto. Ledger.failed/quarentena não foram exercitados isoladamente;
output_pin usa linha SESSION, logo esse caso não prova a guarda específica
independente de pin. Negativo watcher é composição finita, não T4 completo.
Entry EXIT usa armadilha fake em hold só para um defeito não travar; nunca
executa hold real/entry-HOLD. Flags literais são contrato Linux x86-64 a
conferir depois; nenhum syscall nativo foi medido. Root não alegou cobertura
que estes testes não fornecem.

Snapshot exato e métricas estão em frozen-red145.json e r1-1723ef50.py.txt.
Publicar somente docs/dados congelados; novo teste descobrível fica local
até fonte correspondente revista, para não acrescentar RED esperado ao CI
remoto. Próximo lote futuro é apenas fonte main pelo mesmo Claude2, com este
SHA de teste fixo e novas regressões aditivas se houver findings. Não iniciado
nesta retomada restrita a testes. Não requer nova aprovação de rotina; exige
conferir Git/zero escritor e preservar todos os limites antes de retomar.
