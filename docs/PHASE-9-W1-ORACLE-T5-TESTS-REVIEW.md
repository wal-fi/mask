# W1 Oracle — revisão e RED dos testes do driver T5

2026-11-10, sob delegação vigente. Base `5a3dec7`. Claude2 escreveu somente
o teste novo na sessão51ea0d85, `claude-opus-5-5`, esforço `medium`.
CLI43627/84916 terminaram0 e foram recuperadas; zero escritor confirmado
antes da próxima chamada. Root leu as 1.065 linhas iniciais e todo delta
final, sem escrever código funcional ou testes.

Teste congelado: `tests/test_oracle9_w1_driver_t5.py`, SHA-256
`3402d6818d424efe2a59372e9283d1e5f83070f0a5a1022c1e2567a031af2cbd`,
45.565 bytes, 1.165 linhas. AST de todas as funções de teste iniciais
preservada; correções aditivas de cobertura, anotações honestas e layout.

## Revisão anterior ao pytest

A primeira versão omitira D5-12, afirmando que a recusa genuína do adopt
exigiria resultado inventado. Root demonstrou duas transições reais da API
pública: begin_drain antes de adopt produz STATE; begin_output antes de
drain/release completo produz HELD com pin presente. Claude2 acrescentou
sanidades e casos de feature com essas transições, só pela subclasse de
registro ligada ao namespace do driver e delegando aos algoritmos reais.
Não houve alteração global do SDK. São falhas lógicas simuladas, não prova
de concorrência, receiver físico ou comportamento nativo.

O primeiro probe do revisor esqueceu de filtrar slots None do status e
levantou AttributeError; o probe corrigido e a limitação estão arquivados.
Esse erro do harness do revisor não é finding do produto.

Estáticos iniciais: Ruff passou; format apontou dois hunks; mypy apontou
Clock sem atributo bad e duas entradas incompatíveis no dicionário local
de endpoints. A revisão corrigiu os tipos sem cast/ignore/supressão ou
remoção de asserções. Nenhum pytest foi executado antes de ler os oráculos.

## Medições

| Gate | Resultado |
| --- | --- |
| Novo teste isolado | 83 coletados: 8 sanidades aprovadas, 75 falhas, 0 erros/skips, 5,113 s |
| Matriz conjunta | 787 coletados: 712 aprovados, 75 falhas, 0 erros/skips, 12,975 s |
| Casos anteriores dentro da matriz conjunta | 704 aprovados, nenhuma falha/erro/skip |
| Causa de todas as falhas novas | TypeError: Ports não aceita o argumento children |
| Ruff src/tests | Aprovado |
| Formatação src/tests | 363 arquivos conformes |
| Mypy strict src/tests, alvos3.11/3.14 | 363 arquivos, ambos aprovados |

Runtime medido: Windows CPython3.11.3. Alvo de mypy não comprova runtime3.14
ou Linux. O RED é de API e **não prova comportamento temporal ou limpeza
da futura implementação**. Os oito casos independentes verificam somente
fakes, codecs, cálculo da cerca e transições públicas do ledger.

Protegidos27/app124 intactos durante o RED. Testes antigos, main, núcleo
puro, EXPECT, SDK, estado16 e tentativa consumida não foram alterados.
Sem Docker, PG, SQL, socket/thread/processo/guard/sinal/controle nativo do
produto, ambiente privado, runtime/config/binário operacional ou deploy.

## Próximo incremento sob delegação

Aceito para implementar **somente** `deploy/oracle9_w1_driver.py` contra o
teste congelado e T5-DESIGN v3. O driver é a única exceção prospectiva aos
27 pins; os outros26, app124, EXPECT e todos os testes ficam fixos nesse
primeiro lote de fonte. Porta children obrigatória, sem fallback para a
API antiga ou resultado PENDING. Nenhuma mudança de SDK ou chamada física.

Root lerá a fonte/delta completo antes de executar o novo driver. Findings
reproduzidos exigem regressões antes do fix; testes congelados não podem
ser afrouxados para produzir verde. Depois virão migrações restritas dos
testes antigos e o lote próprio de testes/binding do main, conforme desenho.

**Não publicar integração parcial:** o main ainda fixa o hash antigo do
driver e usa oito portas. Passar os testes novos do driver isolado não
qualifica esse conjunto nem autoriza atualizar pins sem a revisão do main.
Publicação funcional só depois dos gates conjuntos. Checkpoints de RED
podem preservar evidência, sem anunciar implementação integrada.

T5 continua BLOCK_NATIVE. B1 fim a fim, B2, D-090 gate2, C1, ingressos,
IDE, MCP e produção seguem abertos; o Gateway permanece indisponível.
Evidência: `docs/poc/evidence/oracle9-w1-driver-t5-tests-review-20261110/`.
