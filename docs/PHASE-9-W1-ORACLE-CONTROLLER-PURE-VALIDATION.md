# W1 Oracle — validação do primeiro núcleo puro

2026-11-06, horário de São Paulo. Implementação por Claude2, única sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, esforço medium.
Revisão, medições e este registro pelo assistente principal. Decisões sob
a delegação vigente; nenhuma aprovação individual do usuário inventada.

## Parecer e fronteira

Aceito somente o núcleo puro de laboratório. Não é controlador PID1 em
execução, ingresso ou fechamento de W1/B1/B2/D-090/C1. Não houve Docker,
PostgreSQL, consulta, controle nativo ou deployment. Gateway indisponível.

O caminho seguinte permanece a prova real no Oracle Linux9.8 aceito, com a
candidata instalada621cc7f7, se readmitida. O laboratório Windows antigo não
é declarado aprovado nem usado para substituir essa prova.

## Fontes revistas

| Arquivo | SHA-256 | Bytes / linhas |
|---|---|---|
| deploy/oracle9_w1_controller.py | 4c155d76208f113852f95fec4c57253eef480c610aa390423fa6f82baf1f7bc7 | 22453 / 658 |
| tests/test_oracle9_w1_controller.py | 084d62cd2a567a0710a7e13b5e9b33896c255ee743fa58e3cc0dab08135b9039 | 44298 / 1108 |

Root leu o teste inicial completo, o delta completo e toda a fonte final,
contra W1-ORACLE-NATIVE-PLAN v4 e PLAN-REVIEW. O módulo não existia durante
o RED; nenhum teste foi alterado durante sua implementação.

## Sequência real e oráculos

1. CLI8979 escreveu somente o teste inicial e encerrou0. Root recuperou o
   terminal e confirmou zero escritor.
2. Teste e71c4ab2/40782bytes/1032linhas: 245 coletados, 28 sanidades
   aprovadas, 217 FileNotFoundError, 1,337s. Ruff/mypy limpos; formato
   reprovou o literal HEAVY.
3. Root pediu recusas aninhadas/tipos, imutabilidade do alvo, porta estrita
   do resolver, RESULT antes do join e READY repetido. Corrigiu a alegação
   de máximo exato para amostra grande válida. CLI70101 mudou só o teste,
   encerrou0 e foi recuperada antes da próxima chamada.
4. Root confirmou zero asserções AST anteriores removidas. RED final275:
   28 sanidades aprovadas, 247 FileNotFoundError, 1,618s; 275 nodeids
   únicos, sem xfail. Ruff/format/mypy3.11/3.14 aprovados. Congelou084d62cd.
5. Root confirmou ainda a policy completa do laboratório nas gerações1/2:
   composição pública idêntica ao controle fake, sem connect/DNS/Popen/
   thread/EnvSecretProvider. Não é teste de banco.
6. CLI28188 criou somente o módulo e encerrou0; terminal recuperado e zero
   escritor. Root revisou e mediu o verde abaixo.

O primeiro wrapper pytest do revisor errou o nome de um argumento de hook,
antes de coletar testes. Foi corrigido sem mudança no teste. A execução
posterior é a medição RED registrada; a falha do wrapper não foi ocultada.

As sanidades independentes fixam os headers por aritmética/binário, a
sequência manual de50frames, a intenção dos19SQL no validator padrão e
quatro equivalências da captura pública. O fake Candidate é somente
controle de comparação; o módulo não usa Candidate, adapter ou verifier.

Escolhas mínimas sob delegação: tabela maskgw_lab.t, identidade sintética
dso_00000000000000000000000000000001, record_revision1, API do cabeçalho
do teste, recusas fechadas e EOF como ABORT também em T6. Nenhuma dessas
escolhas cria identidade, segredo ou autoridade operacional.

## Medições finais

| Verificação | Resultado |
|---|---|
| Testes próprios | 275 aprovados, 1,513s |
| Matriz relacionada, incluindo próprios | 960 aprovados, 8,287s |
| Falhas / erros / skips / xfail | 0 / 0 / 0 / 0 |
| Ruff src/tests | aprovado |
| Lint do módulo deploy E9,F63,F7,F82 | aprovado |
| Format src/tests | 358 arquivos conformes |
| Format dos dois arquivos novos | 2 conformes |
| Mypy strict src/tests, alvo3.11 | 358 arquivos, aprovado |
| Mypy strict src/tests, alvo3.14 | 358 arquivos, aprovado |

Matriz: controller, oracle9_w1_update, oracle9_w1_context,
oracle9_cycle_freshness, runtime_snapshot, worker_protocol,
datasource_destination_review e sql_validator. Runtime Windows CPython3.11.3.
Alvo3.14 é tipagem estática, não runtime. O módulo deploy não integra o
mypy src/tests; não se declara tipagem integral desse módulo.

Sondas próprias do revisor:

- Cinco entradas JSON adversariais: nesting profundo, inteiro de5000
  dígitos, overflow para infinito, constante não finita e byte não ASCII.
  Todas recusadas em INIT sem cause/contexto.
- Quatro caminhos com subclasses de int/str: zero callbacks estrangeiros,
  recusa fechada em SQL/PHASE/DESTINATION.
- 4080 mutações de um byte no header CONTROL. Só76 mantêm o schema
  fechado; as demais recusadas. Nenhuma mutação inválida foi aceita.
- Quatro frames de peer incompatíveis com a fase: dono permanece abortado,
  contagem0/next_seq1, replay válido posterior recusado.

Não apareceu finding adicional de comportamento neste escopo.

## O que foi entregue

Somente definições: LAB_INIT canônico limitado, LAB_CONTROL16bytes, DTOs
imutáveis/redigidos, transições de25casos/50frames e handoff do leitor T4,
SUMMARY somente de prefixo, SQL fixo com canário como dado, resolver literal
sem DNS e captura pública explícita com HMAC como texto.

Source20 por hash/tamanho intactos. Os124insumos públicos da candidata
instalada permanecem iguais por hash/tamanho e por conjunto de paths
(123pacote + pyproject). Manifesto d4d4b29b mantido. Estado16 e tentativa
consumida não mudaram. Não foi necessário rebuild de fonte inalterada;
disponibilidade/imagem/perfil instalados ainda exigem readmissão futura.

## Limites e próxima entrega

Ausência no RED não prova comportamento. Traps de atributos e checagem AST
de nomes não são sandbox de execução nem prova de import frio; root leu a
fonte também. Captura equivalente a fake não prova sessão real, sigilo no
SO ou cleanup. Não há alegação de zeroização.

Amostra INIT grande não é máximo exato. A futura fixture deve gerar canário
não numérico para a expectativa QUERY do job13; schema imprimível e escape
não garantem que todo canário provoque erro de cast. NOSTOP só registra
falha de prefixo; stop_applied, join físico e resultados são do driver.

Próximo lote: desenho restrito do driver com fakes, incluindo owner/ledger,
sink e stop. T5 exige contrato próprio antes de spawn: posse e orçamento
antes do efeito, saída natural0 para comprovar EOF e reap físico antes de
liberar créditos. Nenhum driver/main/ponte/fixture operacional foi entregue.

Native3s, T5, B1 fim a fim, B2, D-090gate2, perfil C1, pressão/concorrência,
TLS, ingressos/IDEs/MCP/Admin, patches e produção permanecem abertos. SQL
PGWire continua recusada. Nenhum serviço disponível ou job/quota novo.

Dados preservados em docs/poc/evidence/oracle9-w1-controller-review-20261106:
baselines exatos, RED e revisões/QA. Suíte integral com PG, Node, browsers e
pacotes não foram repetidos para este núcleo isolado fora do pacote.
