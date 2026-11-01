# Núcleo Win32 privado da admissão PG16 — validação e parecer

2026-11-01, America/Sao_Paulo, sob delegação vigente. Baseline Git `94219aa`.
Claude2 foi o único programador, `claude-opus-5-5`, esforço `medium`, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`. O assistente principal revisou o código,
executou os gates e escreveu este relatório; não implementou helper ou testes.

## Escopo e fontes

Componente privado em `docs/poc`, sem consumidor, CLI ou `__main__`. Não faz
parte do runtime instalado do Gateway. O chamador, seu laço, persistência e
controle nativo ainda não existem. Não foi carregado kernel32 nem criado
handle/job/processo nativo por este backend nos testes.

- `docs/poc/pg16_shell_admission_win32.py`: 31.948 bytes, SHA-256
  `10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726`.
- `tests/test_pg16_shell_admission_win32.py`: 40.889 bytes, SHA-256
  `ab279a10df8f4af19e744f99f5ce5a49d851fe5356bc8b40b52ff28916cfb3d9`.
- Desenho: `PHASE-9-W1-PG16-SHELL-ADMISSION-HOST-DESIGN.md`.

Preparador `8d0bf39e`, sonda `738ee1e3`, entrada `afaffad0` e exportador
`ed491c01` conferidos, intactos. Fontes e raízes consumidas não foram repetidas.
O estado aceito continua com exatamente 16 campos; a admissão nativa de 3 s
continua **NOT_MEASURED**.

## Revisão inicial reprovada

A primeira versão do helper tinha SHA `24b717e5` e 28.363 bytes. Sua cópia
exata foi preservada como dados públicos em
`poc/evidence/pg16-win32-review-20261101/baseline-source.b64`, com manifesto e
SHA decodificado completo. É fonte rejeitada, não um artefato operacional;
não foi executada nativamente. O revisor apenas copiou os bytes que o
programador havia escrito, sem alterar essa fonte arquivada.

Primeiro gate: 87 aprovados e 1 falha em 1,18 s. A falha era da fixture AST,
que confundia símbolos importados por `ImportFrom` com nomes de módulos.
Ruff check passou; formato e duas linhas de mypy falharam. O Claude2 corrigiu
a fixture e a observação de `eof` depois da mutação, sem ignore/skip/xfail.

Um hook independente, executado somente com APIs simuladas, reproduziu cinco
findings antes das correções: 1 teste aprovado e 1 erro de teardown, exit 1.
Não houve publicação dessa versão.

| Finding | Reprodução na versão inicial | Resultado corrigido |
| --- | --- | --- |
| P1-A | `CreatePipe` retornava FALSE com 0x9001/0x9002; o owner fechava valores alheios e declarava CLOSED. | Saídas indeterminadas nunca entram no ledger e não recebem close/wait/terminate. |
| P1-B | `CreateProcessW` retornava FALSE; o owner chamava `TerminateProcess(0x9001)` sem propriedade confirmada. | Saídas em quarentena; contenção só pelo job próprio sobre criação incerta. |
| P2-C | Interrupção depois de preencher PROCESS_INFORMATION deixava STARTING, filho vivo e handles fora do ledger. | Estado HELD, saídas pendentes registradas e tentativa de contenção do job antes de repropagar a interrupção. |
| P2-D | MemoryError após inicializar atributos escapava cru e deixava STARTING com atributos vivos. | Falha comum inesperada em setup/start vira HELD com categoria fechada; atributos só deixam o registro após deleção confirmada. |
| P2-E | Lista de PIDs com tamanho retornado de 1 byte era aceita como vazia e permitia CLOSED. | Tamanho mínimo do cabeçalho mais count vezes ponteiro, teto e contagens coerentes são obrigatórios. |

O contrato de `CreatePipe` afirma explicitamente que as saídas em falha são
indeterminadas; a correção não supõe que zero ou qualquer valor preenchido
seja um handle próprio. [Microsoft — CreatePipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createpipe).
Para `CreateProcessW`, a revisão exige sucesso confirmado e um par coerente
antes de adotar os handles; essa é a regra de propriedade deste componente,
sem atribuir à página uma afirmação literal que ela não faz.
[Microsoft — CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).

O Claude2 escreveu as regressões antes de editar o helper. O mesmo hook
independente de cinco cenários, sem alteração dos seus predicados, passou
sobre a correção: **INDEPENDENT_FINDINGS []**, 1 aprovado em 0,16 s, exit 0.
As regressões formais também cobrem alias em retornos FALSE/TRUE, exceção
estrangeira hostil, interrupções no setup, alocação e quadros de PIDs curtos.
Não se afirma que todos esses testes adicionais tenham sido medidos contra
a fonte anterior: a medição vermelha independente foi a dos cinco casos.

## Gates medidos

- Próprios: **105 aprovados em 1,24 s**, sem falhas/skips, exit 0.
- Hook independente: cinco cenários CLEAN, 1 aprovado em 0,16 s, exit 0.
- Relacionados: **740 aprovados em 293,99 s**, 17 arquivos, sem falhas,
  erros, skips ou deselected; processo exit 0.
- Ruff em src/tests e lint E9/F63/F7/F82 do helper: aprovados.
- Format: **347 arquivos** conformes, incluindo os seis PoCs atuais indicados
  no comando. Após a correção lógica houve uma falha apenas de wrapping em
  `_absolute`, corrigida pelo Claude2 e conferida novamente.
- Mypy strict: **341 arquivos**, alvos **3.11 e 3.14**, sem erros.
- Runtime medido somente Windows/Python **3.11.3**. Alvo mypy 3.14 não é
  execução em Python 3.14 nem prova nativa do ABI.

Comandos: `python -m pytest -o addopts= -q --tb=short` com os 16 arquivos da
SHELL-ADMISSION-VALIDATION mais `tests/test_pg16_shell_admission_win32.py`;
`ruff check src tests`; lint restrito do helper; `ruff format --check src
 tests` mais pin_cost, pin_capture, shell_export, shell_prepare,
shell_admission_probe e shell_admission_win32; `mypy --python-version 3.11
 src tests` e equivalente 3.14. Os próprios estão incluídos nos relacionados.
A seleção não exige DSN nem executa PostgreSQL. Depois dela só documentos
mudaram; fingerprints de helper/testes permaneceram iguais. Não houve gate de browser,
frontend, wheel/sdist ou suíte integral, proporcionais a este PoC não embarcado.

## Desvio de leitura e restrição das ferramentas

Às **2026-11-01T15:32:13.035Z**, durante o desenho, Claude2 fez Grep em
`.venv/pyvenv.cfg`, fora do escopo deste lote. Não há aprovação retroativa.
Seu conteúdo não é publicado nem usado como evidência; o comportamento da
árvore real do launcher continua não provado. A alegação anterior de nenhuma
leitura de configuração foi corrigida no desenho e comunicada ao usuário.

As invocações seguintes retiraram Grep/Glob/Bash/MCP e usaram somente
Read/Edit/Write com negações explícitas para runtime, binários, arquivos
pessoais e segredos, limitando edição aos arquivos do incremento. Uma primeira
combinação excessivamente ampla de deny também bloqueou o documento permitido;
essa tentativa terminou sem editar arquivos. A regra foi corrigida e medida:

- Canário público próprio em docs: Read recusado pela permissão.
- Caminho canário inexistente em .venv: Read recusado pela permissão, antes de
  qualquer erro de arquivo inexistente; esse caminho nunca foi materializado.
- Documento autorizado: Read e Write permitidos.

O canário público foi removido somente depois de conferir caminho literal e
bytes exatos. Nenhuma configuração de conta ou permissão persistente mudou.
São restrições das ferramentas da CLI, não sandbox de SO nem garantia absoluta
de leitura apenas de fontes. Não foi iniciado outro escritor para contornar
permissão/quota. Execuções de implementação/correções terminaram; nenhum
escritor ativo, nova quota ou job neste fechamento.

## Limites e próximo incremento

A revisão aprova somente o núcleo isolado sob fakes, sem P1/P2 remanescentes
nesse escopo. Assinaturas, tamanhos e
ordem são conferidos por esses testes; a interoperabilidade Win32 real exige
o controle benigno futuro, com procedimento/comando próprios revisados antes
de executar. Falhas persistentes e interrupções deixam HELD; a quarentena não
é recuperada automaticamente. A tentativa de terminate na interrupção não
comprova término. Retenção vale apenas enquanto o processo dono vive.

O futuro chamador ainda precisa tratar interrupções em suas primitivas de
supervisão e preservar propriedade/pendência, impor o orçamento de decisão,
recolher a árvore, observar EOF e persistir antes de publicar. Nenhuma garantia
universal de prazo do SO ou limite de memória foi obtida. O desenho 60/10 s,
1024 bytes e 2 processos é prospectivo, sem medição nativa.

Próximo: chamador com fakes usando o SHA aceito deste backend. Depois, controle
nativo separado, proposta de sonda e rodada única, cada qual revisado antes de
qualquer efeito. Nenhuma raiz operacional, sonda, Docker, PG, SQL, serviço ou
worker foi acionado neste lote. Gateway/B1/B2/D090/C1/produção permanecem abertos.
