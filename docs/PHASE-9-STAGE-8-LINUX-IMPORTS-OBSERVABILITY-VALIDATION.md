# Etapa 8 — diagnóstico fechado da auditoria de imports Linux

**2026-10-21 — incremento diagnóstico medido; nova rodada inconclusiva.**
Não é correção de atribuição, contenção, worker ou aceitação operacional.
Rodada anterior preservada em `PHASE-9-STAGE-8-LINUX-IMPORTS-VALIDATION.md`,
com suas fontes congeladas e hashes originais. O código aqui modificado
**não** foi o código daquela primeira medição inconclusiva. A preparação
pré-execução abaixo precedeu a segunda rodada, descrita separadamente ao fim.
Docker foi restaurado desligado e o caso AS32 novamente não rodou.

## Contrato e código

Plano: `PHASE-9-STAGE-8-LINUX-IMPORTS-OBSERVABILITY.md`.
Somente `docs/poc/linux_import_probe.py`, `docs/poc/run_linux_imports.py` e
`tests/test_linux_imports_probe.py` alterados funcionalmente. Nenhum src,
dependência, configuração, perfil de container, origem permitida, associação
de módulo nativo, fd ou cota relaxado. Helpers do diagnóstico AS congelados.
O novo guard de nome acrescentou uma recusa antes inexistente: a regressão
e sua inferência estão registradas abaixo, sem declará-la corrigida.

- Falhas de auditoria distinguem FORBIDDEN, OUTSIDE_ORIGIN, UNOWNED_TOP,
  FILELESS_UNATTRIBUTED e OTHER. Evento audit_error tem apenas etapa,
  nome ASCII validado até200 caracteres (null se inválido), categoria e
  bools has_file/under_installed. Sem exceção, traceback ou caminho absoluto.
- Baseline após GO usa etapa-1; deltas usam etapa ativa0/1/2. Qualquer falha,
  inclusive ao emitir a linha ou o diagnóstico, interrompe o membro com75.
  Não continua auditando nem conclui que o import falhou.
- Supervisor valida schema/etapa/bools/nome, preserva evento válido e espera
  o membro dentro do prazo. Linhas inesperadas só geram marcador fechado,
  nunca cópia do corpo: PROTOCOL, COLLECTION_FAILED, EOF, TIMEOUT,
  DIAGNOSTIC ou AUDIT_ERROR. Returncode coletado; se obtido só no cleanup,
  essa origem é marcada. Cleanup e limites anteriores permanecem obrigatórios.
- Classificador recusa qualquer diagnóstico como mismatch de AS32, mesmo
  se outro campo sugerir MEMORY/IMPORT/SIGNAL. Nenhum fallback de origem.

## Testes e checks antes da revisão

Windows, `.venv` existente, Python3.11.3; nenhum import Linux nativo no host.
Primeiros27 casos novos falharam contra a versão sem observabilidade.
Após implementação e quatro casos adicionais: **141 passed** nos quatro
módulos puros (110 anteriores mais31 novos). Incluem cinco categorias,
nomes inválidos/limite200, erro de atributo/emissão, interrupção do membro
sem próximo import/ACK, baseline/erro após linha válida, schema adulterado,
EOF, linha fora do protocolo, collection_failed e returncode. Os testes de
codec limitado, perfil e cleanup permanecem verdes. Sem skips/xfail novos.

Ruff de src/tests e E/F/I/B/UP dos dois PoCs alterados verdes; format check
em249 arquivos e mypy strict nos alvos3.11/3.14 em247 arquivos verdes.
Isso não é execução em Python3.14 nem suíte integral PG16. O primeiro
comando Ruff amplo incluiu PoCs fora do gate e regras de anotação não usadas
por esses scripts:379 diagnósticos e dois PoCs antigos não formatados;
nenhum desses arquivos foi reescrito. O primeiro mypy apontou três chamadas
a helper de teste sem anotação; assinatura corrigida, ambos os alvos limpos.

## Revisão e execução real

Solicitada somente leitura ao Claude2 na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, antes de qualquer novo container.
Enquanto pendente, nenhum caso real será iniciado. Sem novo escritor.
Uma rodada posterior só pode usar o mesmo controle/caso AS32 condicional,
com identificador e fontes próprios. Se houver audit_error, registrar
módulo/categoria e parar antes de AS32. Correção de atribuição é outro lote
revisado, não permitida por este diagnóstico. B-1/B-2/D-090 seguem abertos.

Sem commit/push, deploy, banco, SQL de cliente ou liberação de produção.

## Acréscimo recomendado na primeira revisão (antes de executar)

Claude2 não encontrou bloqueador no código inicial, permitindo uma rodada
estreita identificada, mas recomendou diagnosticar também as checagens de
efeitos/nativos. Recomendação implementada antes de executar: check_error,
exit76 e categorias fechadas SOCKET_FD/CHILD/FD_SET_CHANGED/THREADS/
PSYCOPG_IMPL/NATIVE_MISSING/OTHER. Nenhum fd/path é refletido; root só do
conjunto nativo fechado ou null. Mesmas checagens e limiares, sem relaxar.
Supervisor distingue etapa-1/0/1/2/3 e resultado continua inconclusivo.
Também exige categoria e código de saída72/73/74 coerentes nos erros de
import; sinal ou saída divergente não viram diagnóstico de memória aprovado.
STOPPED distingue SIGTERM de timeout de leitura. Fontes antigas intactas.

Treze regressões adicionais verdes: **154 passed** relacionados, Ruff/format
e mypy3.11/3.14 verdes em247 arquivos (format249 incluindo os dois PoCs).
Fixture histórica de protocolo corrigida: antes devolvia72 em todo erro,
agora devolve os72/73/74 que o membro efetivamente retorna. Nenhum código
de produto ou teste de produto alterado. Releitura somente leitura concluída
sem bloqueador antes do segundo caso real. O revisor não executou o código
nem certificou os gates de produto.

## Segunda rodada real — diagnóstico de auditoria, sem AS32

Mesma imagem, montagem parcial e limites do plano; sem download/reinstalação.
Preflight: Docker29.7.2/Linux/amd64, engine vazio e imagem já em cache.
Wheel do produto comparado novamente aos115 arquivos atuais, hash D-115
preservado. Um comando auxiliar inicialmente tentou um helper digest
inexistente: AttributeError local, sem container; corrigido para hashlib
antes do preflight. Não foi nova tentativa de carga.

Raiz própria nova: `%LOCALAPPDATA%\Temp\maskgw-linux-import-run-20261021-gdo6l6yo`.
Container único: `a08a43a6d0bbea3a6b55ce1ac97c7e1713bc37f2733d1f970f9a0c6b61c91736`.
Controle inconclusivo em4,531s; lote4,890s; Python exit2 capturado
separadamente, container/supervisor exit0. Membro exit75 coletado antes do
cleanup, diagnostic_failure=AUDIT_ERROR. Evento:

```json
{"phase":"audit_error","stage":0,"module":null,"category":"OTHER","has_file":true,"under_installed":false}
```

Baseline77 linhas, etapa0 com26 linhas, sem end; última linha `_string`.
Etapas1/2 não começaram. **AS32 não executado**, limited.json ausente.
Sem native_check completo, pico de etapa ou custo total reivindicado.
Sem OOM/pressão/deadline: events max/oom/oom_kill=0, OOMKilled=false;
pico cgroup91.111.424 bytes, sem exercitar o teto192MiB. Ready do membro
VmSize19.668.992/VmPeak19.951.616; supervisor20.471.808/20.762.624 bytes.
Esses valores não calibram cota nem são pico completo dos imports.

O código novo verifica valid_module_name **antes** de module_row: essa é
uma recusa nova, não só sanitização do erro. A lista da primeira rodada
contém, depois de `_string`, `_sysconfigdata__linux_x86_64-linux-gnu`, que
tem hífen e vinha da stdlib. Ele foi aceito na primeira rodada, mas o novo
guard o recusaria. Isso explica por inferência a parada antecipada e mostra
uma regressão da observabilidade; o nome não veio do evento, que é null.
Não prova nem corrige a causa da interrupção antiga na auditoria da etapa1.
Não relaxar regex de erro ou permitir origem arbitrária para contornar.

Fontes e cópias executadas, árvore e runtime.json intactos; inventário
vivo[1,7], final[1]/pids1, membro recolhido, container removido, inventário
do engine vazio reconferido. Desktop inicialmente desligado iniciado oculto,
depois stop graciosamente exit0; zero processos Desktop/backend/build/Python
na conferência posterior. Artefatos laboratoriais e imagem preservados.

SHA-256 desta rodada (nunca atribuídos à primeira):

- probe: `e17f540331541b6b7b168cdfa16fa851d1cf3f58de0950f5ac74e9b88f9d33cd`;
- observer: `6a446e5fad7752e6527f17d9a6e542fee4792293d20233b9cbe77bc956f59fa3`;
- summary.json: `fe920967909bb9e529826c562d9a6d3849b4aae2a18df2031474c3b27aca6408`;
- control.json: `4708ebc7fd70dfc304410234d1d9904010fcd20efa635810efd73489e3689779`.

Bundle sintético para revisão somente leitura:
`docs/poc/evidence/linux-imports-observability-20261021.json`, com os dois
originais, seus hashes e as103 linhas decodificadas pelo executor. Não é
segunda execução nem prova independente de identidade do nome suprimido.
Próximo passo separado: revisar a regressão do guard, restaurando só a
aceitação anterior e mantendo a sanitização fechada do campo de erro.
B-1/B-2/D-090 e produção continuam abertos. Sem commit/push.
