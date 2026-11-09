# W1 Oracle — revisão do contrato main/bindings D2

2026-11-09. Revisão técnica sob delegação; não aprovação individual do usuário.
Base 058bad8699416e0e0d2165ca40d24bc7d80a5495. Claude2 único autor do desenho,
sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, esforço medium.
Root recuperou76883/49592/22983 encerradas0, confirmou zero escritor e leu
V1 inteira, V2 inteira e todo delta final.

## Parecer e escopo

Aceito o contrato de MAIN-DESIGN080c37ab (39922bytes/697linhas) **para
escrever testes com SO simulado e medir/congelar RED antes da fonte**,
com as precisões abaixo. Não autoriza efeitos físicos nem fecha gate de
produto. Main e teste ainda ausentes ao final desta revisão.

Fonte25 por SHA/tamanho e aplicação124 intactas. Nenhuma suíte funcional
foi repetida neste lote exclusivamente documental. O estado16, a tentativa
consumida, driver39a68904/teste585540af e puro4c155d76 não mudaram.

## Correções revistas

- A raiz nasce antes das aquisições explícitas; ticket fixo source_fd
  retém o fd conhecido e incerteza. Erro de validação fecha uma única vez
  o fd original antes de LOAD_FAILED seguro; open/close incerto retém.
- Link usa fd0/fd1 emprestados. Aposentadoria lógica verificada após o
  último output e sem leitor ativo permite limpar só o slot original.
- Handler permanente não levanta. O controle é cooperativo; não se promete
  cancelamento imediato ou atomicidade. Root continua retido através das
  falhas e dos controles, inclusive no bootstrap.
- _run_once recebe a raiz já criada e produz uma decisão finita sem
  transferir posse. hold_step é finito; hold não retorna. Nenhum rounds,
  final de seam ou exceção especial de teste permite saída real.
- Um lock cobre todo o frame INIT ou CONTROL. Poison é pegajoso inclusive
  nas operações em voo. Nunca se entrega OK depois de observar poison.
- Wire permanece só com eventos do driver,56 linhas e512bytes com LF.
  Não há evento MAIN nem output depois do predicado de saída.
- Semântica de close/_cleanup distingue saída de controle, RELEASED e HELD.
  Threads, sinais e fechamento físico continuam exigindo evidência própria.

## Precisões fechadas antes dos testes

1. Adicionar ao System fechado um callable **is_main_thread() -> bool**.
   O binding real compara threading.current_thread() com main_thread();
   o fake fornece contexto/role próprio ao executar callbacks fake. Assim
   M19 pode provar que watcher não recebe MainSignal sem criar thread real,
   sem patch global da stdlib e sem trocar algoritmos do SDK.
2. **HOLD_FAULTS_MAX =255**, int exato, fecha o LIMITE simbólico do desenho.
   hold_step satura esse contador; não limpa recursos nem marca PASS.
3. MainDecision é valor imutável com campos **kind: str e code: int|None**:
   kind str exata EXIT com code int exato64..70, ou kind str exata HOLD com
   code None. Bool não é código; não há owner, namespace ou raiz no valor.
   _run_once recebe a raiz do chamador; entry retém essa mesma raiz antes/
   depois da decisão e só retorna um código após saída segura. Decisão
   ausente, estrangeira ou incoerente nunca autoriza saída: segue para hold.
4. Testes retidos/de controle usam _run_once; testes finitos de espera usam
   hold_step. Nenhum teste executa o caminho sem fim de hold ou entry com
   decisão HOLD. AST e posterior prova física cobrem essa obrigação real.
5. Leitura de fonte só admite os dois pares caminho/tamanho públicos fixos:
   load_driver usa DRIVER_PATH/DRIVER_BYTES; a porta PinnedReader aceita
   somente PURE_PATH com limit PURE_BYTES+1. Nenhum caminho de arquivo,
   perfil, SQL ou limite operacional novo entra pelo canal do host.
6. Critérios do desenho são de objetos/runtime e contratos de syscall;
   active_count não é prova de quietude nativa. O risco de pause e sleep
   falharem persistentemente permanece falha não aprovada para gate nativo,
   nunca motivo para abandonar a raiz.

São decisões técnicas do revisor sob delegação, não mudanças de produto ou
licença para executar main físico. Incorporar este arquivo ao contexto do
próximo Claude2 antes de escrever o teste.

## Referências e limites

Python3.11 signal/threading, PEP475, linha de comando -I e pid_namespaces(7)
foram conferidos pelo root em fontes primárias; links/notas estão nos
dados primary-reference-review.json. Comportamento documentado não é
medição da candidata Oracle9.8/Python3.11.13. Não há prova nova de
Threads/VmSize, signals, liveness, close, mounts ou readmissão.

Próximo lote: apenas tests/test_oracle9_w1_main.py pelo mesmo Claude2,
com módulo deploy/oracle9_w1_main.py ausente até root rever oráculos e
medir/congelar RED. Conferir Git e zero escritor; ativo implica monitorar,
recuperar terminal antes de outra chamada. Sem efeito físico/SQL/deploy
nesse próximo lote. T5, gerador, ponte/fixture/frescor, readmissão e
B1/B2/D090gate2/C1/TLS/ingressos/produção permanecem abertos.

Dados/V1/V2/revisões preservados em
docs/poc/evidence/oracle9-w1-main-review-20261109/.
