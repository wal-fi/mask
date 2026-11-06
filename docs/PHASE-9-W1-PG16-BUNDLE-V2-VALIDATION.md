# Ponte privada slot A → metadado B — validação

Data: 2026-11-06. Incremento sob delegação vigente; nenhuma aprovação
individual do usuário é atribuída às decisões desta revisão. Claude2 é o
único programador, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo
`claude-opus-5-5`, esforço `medium`. O assistente principal revê e mede.

**Estado atual:** componente privado revisto e validado com fakes. CLI20622
terminou0 e seu terminal foi recuperado; zero escritor confirmado. O green151
inicial continua reprovado na revisão histórica. O resultado aceito é o
green186/1352 após as regressões, sem atestado de execução operacional.

## Base e limites

Partida `HEAD == origin/master == 14c7ce4126ce49c53d015aa2c8570f22d422b51e`,
master sincronizada, rastreados limpos e zero escritor antes da CLI24991.
Foram preservados `.codex/`, os dois stackdumps e `systeminfo`; esses arquivos
não fazem parte do incremento. Dezoito fontes/testes aceitos foram conferidos
por SHA-256 e tamanho, sem divergência. Estado16 e tentativa consumida antigos
não foram modificados ou reutilizados.

Contrato: [revisão do desenho](PHASE-9-W1-PG16-BUNDLE-V2-DESIGN-REVIEW.md).
O componente recebe o grupo original de oito referências e snapshots dos
slots; cria somente um candidato a evidência, para validação completa pela B.
Não autentica o produtor, momento de captura, frescor, filesystem, execução
nativa, quietude do SO ou cleanup. A confirmação CLOSED é lógica em Python.

Nenhum consumidor, entrada, loader, collector, publicador, comando, raiz ou
nonce operacional é criado. Nenhum Docker, PostgreSQL, SQL, DLL/job/processo/
controle real, leitura explícita de runtime/configuração/binário/privado ou
deploy é executado neste incremento. O destino aceito continua Oracle Linux
9.8 em Docker local; este laboratório de fakes no Windows não o substitui.

## Testes escritos antes do módulo

CLI24991 terminou0 e seu terminal foi recuperado. Root leu as 1158 linhas do
teste inicial `afd2b067dc4e833ce4d1e72f41017ab70dfead3dd6c44a472cd53148db69f60c`
(40757 bytes). O módulo estava ausente.

Primeira medição: **146 coletados; 7 sanidades passaram, 137 erros de setup e
2 falhas**, todos os 139 por `FileNotFoundError`; 16,226 s. Ruff apontou seis
argumentos não usados, o format um arquivo divergente, e mypy três acessos
de atributos após estreitamento dinâmico para object. Esses gates reprovaram.

CLI76876 terminou0 e foi recuperada; zero escritor confirmado. Root reviu o
delta: preservação dos cenários/asserts, correções de tipos/argumentos,
sanidade independente dos três helpers e cinco casos adicionados ao total.
A sonda do serializador passou a instalar a falha antes de carregar o módulo,
sem impor o estilo de import do builder. A chave collider conserva a contagem
válida e sua presença por identidade é afirmada antes de zerar contadores.

Segunda medição: **151 coletados; 8 sanidades passaram, 140 erros de setup e
3 falhas**, todos os 143 por `FileNotFoundError`; 16,003 s. Ruff check e mypy
passaram, mas o format ainda reprovou. CLI58764 terminou0 e foi recuperada:
somente colapso de três linhas de uma atribuição, sem mudança de AST.

O arquivo anterior ao format foi reconstruído invertendo apenas esse espaço
em branco; seu SHA-256 bateu exatamente com o medido `ae87ab3c921ee8226c3f25ae88e2ca583121df96cdb2caabd91c1d8f6ec61774`.
A primeira tentativa de arquivá-lo encontrou uma mudança concorrente e
recusou escrever pelo guard de hash; nenhum arquivo incorreto foi arquivado.

## RED congelado

Teste final pré-módulo: **84edd937c0e0fa63ecada074cd6abf27940b96ad0db4e0e74d9147c21394accf**,
43807 bytes, 1267 linhas. Cópia exata preservada como dados.

- **151 coletados e nodeids únicos; 8 sanidades passaram, 140 erros e 3 falhas**,
  todos os 143 por ausência do módulo; 15,933 s, exit1 esperado para este RED.
- Nenhum skip ou xfail marcado. Ausência não verifica comportamento do builder.
- Ruff check e format check: aprovados, um arquivo.
- Mypy strict: aprovado no teste, alvos 3.11 e 3.14; PoC fora do mypy.
- Runtime de testes: Windows CPython 3.11.3; 3.14 é somente alvo estático.

As oito sanidades independem do módulo novo: cinco perfis reais do caller A
com kernel fake e evidência manual aprovada/recusada pela B e pelo core reais;
formas/identidades/limites dos namespaces; aritmética conservadora do domínio;
e helpers reais de leitura com seam de FunctionType nos globais vivos de A.
Cada teste obtém slots e namespaces mutáveis próprios, sem sessão viva comum.
As chamadas nativas/processos/threads e escritas reais do harness são vedadas.

## Dados e sequência depois do RED de ausência

Baselines, cópias textuais e relatórios fechados em
`docs/poc/evidence/bundle-v2-review-20261106/`. Arquivos `.py.txt` são dados,
não módulos executáveis nem artefatos operacionais. Os históricos reprovados
não são reclassificados como verdes.

Depois do RED de ausência, CLI87249 foi autorizada a escrever somente
`docs/poc/pg16_shell_native_control_bundle_v2.py`, mantendo o teste congelado e
as 18 fontes anteriores. Depois do terminal, root deve ler toda a fonte,
rever os oráculos e executar os gates apropriados antes de publicar.
Não foi iniciado outro escritor; nenhuma cota, reset ou job novo é presumido.

Gateway indisponível; Native3s NOT_MEASURED, entry_gate NOT_EVALUATED e
B1/B2/D-090 gate2/C1/SQL/produção continuam abertos.

## Primeira implementação e finding reproduzido

CLI87249 terminou0, recuperada; zero escritor confirmado. Root leu toda a
fonte6129bb3257fa7c0f5d71646349da187b9a8838d7765d1b6f1f0d129defbcf182,
26821 bytes,788 linhas. Teste84edd937 intacto. **151/151 passaram em18,507s**,
sem falhas/erros/skips; Ruff PoC E9/F63/F7/F82 e format aprovados. Isso não
fechou a revisão: as sondas independentes abaixo reproduziram aceitação indevida.

Na chamada `_record` do terceiro slot, um seam com os globais originais de A
altera o primeiro caso e devolve o resultado normal do helper. Cinco sondas
retornaram BUNDLE_READY indevidamente: adicionar chave ao namespace de A;
trocar case.name; trocar case.clock; trocar referência do primeiro entry de
legacy; trocar refs.state. A guarda só conferia o teto dos namespaces, não
o tamanho capturado; não relia os vínculos dos entries nem o metadado do case;
e não guardava os demais campos diretos de refs. Nenhuma execução nativa ou
efeito operacional está envolvido. Resultado é finding de deriva no componente
privado, não prova de vazamento ou execução em produção.

Fonte rejeitada e relatório/script da sonda preservados como dados. Próximo
passo: regressões aditivas pelo mesmo Claude2, fonte6129 fixa; root mede RED
antes de autorizar a correção. Nenhum resultado foi publicado como aprovado.

## Regressões antes da correção

CLI23150 terminou0, recuperada. Root leu as adições e comparou AST: os151
casos anteriores ficaram intactos. Teste7aaaa9bf/49682bytes/1437linhas:
**182 coletados,153 passaram e29 falharam** por AssertionError,26,673s.
Os dois controles entries/context_type já eram detectados. A matriz nova
exerce adição/remoção de nome nos quatro namespaces; os dez campos de refs;
metadados e vínculos do case; e referências em legacy/lifecycle/host.
Ruff/format/mypy estrito3.11/3.14 passaram. Fonte6129 continuou fixa.

Outras quatro sondas reproduziram READY com meta/case coerentes mas fora do
domínio: start NaN/Inf, read_limit4095 e audit_limit511. A igualdade de tuplas
do caller A aceita o mesmo objeto NaN por identidade; esse detalhe não
dispensa a validação finita do perfil pelo builder.

CLI40014 terminou0, recuperada; root leu o acréscimo e provou AST182 intacta.
Teste final **dd329afec13e3a66302136ad0421df91f20353bcd2a54e5483abe6330cc6ccda**,
51189bytes,1477linhas, congelado: **186 coletados;153 passaram,33 falharam**,
16,791s. Todas as falhas são AssertionError de regressões, nenhum erro/skip/
xfail. Ruff check/format e mypy strict3.11/3.14 passaram. Fonte6129 manteve
seu hash durante ambas as medições vermelhas. Dados preservados.

Zero escritor antes de CLI20622. Essa chamada corrige somente a fonte nova,
com teste dd329afe e Source18/estado16 fixos. Guardas devem guardar contagens
originais, os 34 vínculos/10 campos de refs e metadados originais de todos os
slots, sem helpers extras ou congelamento profundo. A revisão do desenho
ganhou essa precisão sob delegação; nenhuma aprovação individual é inventada.

## Correção revista e resultado aceito

CLI20622 terminou0; terminal recuperado e zero escritor confirmado antes da
revisão. Root leu o delta completo contra a fonte rejeitada. A conferência
AST limita as mudanças a `_Row`, `_State`, `_group`, `_shape`, `_row_stable`,
`_stable`, inclusão de `_lengths` e constantes correspondentes; as demais
definições permaneceram idênticas.

Fonte aceita: **91c20df4670cda5450aa02795627b719bf30309ae8cb2447d426e86b298f4687**,
28551bytes,831linhas. Teste dd329afe permaneceu byte a byte igual ao RED186.
Os tamanhos originais dos quatro namespaces, todos os dez campos de refs,
os 34 vínculos capturados e os metadados do case são guardados sem callbacks
extras. Read4096/audit512/start finito são conferidos no preflight. A guarda
não congela recursivamente o case nem autentica mudanças coerentes anteriores.

| Gate sobre a fonte final | Resultado |
|---|---|
| Próprios |186 coletados,186 aprovados,16,075s |
| Relacionados,12 arquivos |1352 coletados,1352 aprovados,43,671s |
| Falhas/erros/skips/xfail |zero em ambas as execuções |
| Ruff do teste |política normal, aprovado |
| Ruff do PoC |E9/F63/F7/F82, aprovado |
| Format |2 arquivos conformes |
| Mypy strict do teste |3.11 e3.14 aprovados; PoC fora do mypy |
| Integridade |18 fontes/testes upstream por hash/tamanho intactos |

As cinco sondas independentes antes aceitas agora retornam BUNDLE_REFUSED/
DRIFT. NaN/Inf retornam BUNDLE_REFUSED/SHAPE; os quatro casos de domínio e as
31 regressões de identidade passam na suíte própria. São provas com fakes,
sem demonstrar comportamento nativo, limpeza real ou integração de produto.

A suíte relacionada inclui bundle, provenance, core verify, caller A,
lifecycle V2, reconciliação, admission Win32/host, control Win32, control,
control entry e held projection. Caminhos exatos e resultados fechados estão
em `final-review.json`. Não foram repetidos PostgreSQL, frontend, browsers
ou empacotamento: nenhum código de produto, recurso ou dependência mudou.

Nenhum finding reproduzido ficou aberto neste componente privado. Isso não
fecha B1/B2/D-090gate2/C1, Native3s, entry_gate, SQL ou produção. Não houve
controle nativo, root/nonce/comando operacional ou deploy. Nenhum novo job,
quota/reset ou troca de conta/modelo; um escritor por vez em toda a sequência.

Próximo lote: somente leitura/revisão do contrato de produtor/coordenador,
para a composição usar as mesmas origens antes dos efeitos e os mesmos bytes
na validação completa. Sem novo consumidor operacional neste lote. Conferir
Git/zero escritor, manter a mesma sessão/modelo/medium e recuperar o terminal
antes da chamada seguinte. Históricos reprovados permanecem preservados.
