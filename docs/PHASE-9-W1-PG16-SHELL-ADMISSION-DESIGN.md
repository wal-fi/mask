# Sonda de admissão do leitor PG16 — desenho antes de código

Desenho criado em 2026-11-01 UTC (2026-10-31 em São Paulo); implementação
e revisão com fakes em 2026-11-01, São Paulo, sob delegação vigente.
Somente helper e testes; nenhuma raiz, claim ou execução operacional.
Resultados medidos ficam em SHELL-ADMISSION-VALIDATION. Preparador 8d0bf39e,
entrada afaffad0, exportador ed491c01 e raízes consumidas ficam intactos. O
gate de 3 s da `prepare` da entrada continua NOT_MEASURED e continua sendo o
gate real: a sonda produz evidência prévia, não substitui essa checagem.

## Objetivo e prefixo medido

Medir uma única vez, em processo nativo Windows/Python 3.11.3 `-I -B`, o mesmo
prefixo que a `prepare` da entrada cronometra: `admit(root)` →
`H["Host"](root, state)` → `Context(root, state, host)` → `final_pins(context)`,
com todo o trabalho deles (inclusive os hashes que `final_pins` já faz). Nunca
chamar `prepare`, `run`, `drive`, `start_supervision`, `start_cycle`,
amostrador de relógio, Docker, PG, SQL, worker ou serviço, nem gravar
`invoked.json`.

Fora do prefixo medido: import/carga da sonda, captura da entrada por SHA
(a `prepare` real também roda depois do import do módulo), validações de
estado/raiz, claim prévio e toda gravação posterior. Não há passada extra de
aquecimento; as leituras de validação antes da medição podem aquecer caches
de disco, então não se promete medição com cache frio.

## Helper proposto: `docs/poc/pg16_shell_admission_probe.py`

API pública mínima: `probe(root, task)` e um `__main__` que aceita exatamente
dois argumentos (raiz e task) e imprime só um resumo fechado. Nenhum
parâmetro de executável, módulo, callback, caminho de saída ou ambiente. As
quatro etapas são resolvidas por nome fixo dentro da entrada capturada.

O módulo importa apenas stdlib no carregamento. A guarda de runtime roda
antes de qualquer carga de fonte capturada, leitura externa ou gravação; não
se afirma que nenhum import não builtin ocorre. Uma guarda antecipada de
`__main__` só com `sys` é opcional; se for implementada, terá teste próprio.

Ordem dentro de `probe`:

1. Runtime: win32, 3.11.3, isolated, dont_write_bytecode, optimize 0.
2. Fontes por SHA com leitura limitada (`read(limit+1)`): preparador 8d0bf39e
   (≤64 KiB) e entrada afaffad0 (≤64 KiB); carga da entrada só como definições.
3. Task 32 hex minúsculo; raiz `HOME/AppData/Local/Temp/
   maskgw-pg16-shell-reader-v1-<32hex>` (HOME do 4bc), diretório real, todos
   os ancestrais reais sem link/reparse, conteúdo exatamente `attempt.json`,
   igual byte a byte ao `state_for(task)` do preparador (≤32768).
4. **Claim prévio exclusivo** (antes da primeira operação medida), em
   `Temp/maskgw-pg16-shell-admission-claim-v1-<nonce>.json`, fora da raiz,
   para que a `admit` medida continue vendo um diretório FRESH. Conteúdo
   canônico: kind, task, root_name, nonce, SHAs da sonda/preparador/entrada,
   SHA e tamanho do estado. Criado com `xb`, contagem exata, flush, fsync e
   releitura idêntica. Qualquer arquivo já existente nesse nome (completo,
   parcial ou ilegível) recusa (`PROBE_CLAIMED`). Qualquer falha na criação
   recusa a medição (`PROBE_CLAIM_IO`); a falha pode ocorrer antes de existir
   arquivo, então não se promete claim parcial. Em todos esses casos a
   proposta/nome fica procedimentalmente queimada, mesmo sem arquivo.
5. Medição: `time.monotonic()` (float, mesmo relógio e mesma aritmética da
   `prepare`) imediatamente antes de `admit` e depois de `final_pins`;
   `perf_counter_ns` entre etapas só como diagnóstico. O custo dessa
   instrumentação fica dentro do total medido, não é subtraído. Uma única
   passada, sem retry.
6. Marca na raiz: `admission-probe.json` com `xb`/fsync/releitura. Como a
   `admit` exige o diretório só com `attempt.json`, a raiz deixa de ser
   admissível pela entrada inalterada.
7. Resultado: grava um `.json.next` com `xb`/fsync/releitura e publica em
   `Temp/maskgw-pg16-shell-admission-result-v1-<nonce>.json` por rename,
   como última operação de filesystem. Marca e pendente são conferidos antes
   da publicação; não há releitura depois do rename. Falha em 6 ou 7 levanta
   `PROBE_MARK_IO`/`PROBE_RESULT_IO` e nunca devolve sucesso.

Depois do claim, qualquer desfecho (etapa que falhou, relógio inválido,
dentro ou acima de 3 s) segue para 6 e 7; o claim nunca é apagado ou
substituído. Sem remoção, retry, troca de estado ou limpeza.

## Classificação e schema público

- `elapsed = monotonic_fim - monotonic_início` em float, com o teste original
  da `prepare`: `WITHIN_3S` se `0 <= elapsed <= 3.0`, `OVER_3S` se maior. Não
  se usa aritmética em ns como fronteira equivalente. `elapsed` não finito
  (NaN/inf) ou negativo: `CLOCK_INVALID`, sem classificação.
- Diagnóstico por etapa em `perf_counter_ns`: tick decrescente é
  `CLOCK_INVALID`; delta zero é resolução válida do relógio, não erro.
- 3 s é classificação retrospectiva, não timeout que interrompe. A futura
  execução nativa precisa de supervisão própria com prazo limitado e plano
  de coleta (reap) do processo, revisados à parte.
- Etapa que levanta: `STAGE_FAILED` com etapa fechada `ADMIT`/`HOST`/
  `CONTEXT`/`FINAL_PINS` e categoria fixa `STAGE_EXCEPTION`. Não se usa a
  `diagnostic` da entrada (que pressupõe um Context completo), não se cria
  Context falso e não se lê mensagem ou atributo da exceção.
- Resultado: kind, task, root_name, nonce, SHAs, outcome, stage, category,
  `elapsed_seconds` (float finito ou null), `stages_ns` (quatro inteiros ou
  null), `limit_seconds` 3.0, runtime fixo. Sem caminho absoluto,
  configuração, ambiente, raw, stdout ou exceção.
- Erros: `ProbeError` com código fechado (`PROBE_RUNTIME`, `PROBE_SOURCE`,
  `PROBE_SIZE`, `PROBE_ROOT`, `PROBE_STATE`, `PROBE_CLAIMED`,
  `PROBE_CLAIM_IO`, `PROBE_MARK_IO`, `PROBE_RESULT_IO`, `PROBE_INTERNAL`),
  levantado fora de except, sem causa/contexto.

## Queda e durabilidade — limites honestos

Se o processo cair depois do claim e antes de 6, o claim existe e a sonda
recusa qualquer repetição para esse nonce: a tentativa está queimada para o
chamador. Mas a raiz continua FRESH, e uma `admit` da entrada inalterada
**aceitaria** essa raiz se um operador ignorasse o claim. Não há proteção
técnica contra isso nesta camada nem contra o mesmo usuário alterando
arquivos.

`flush`/`fsync` de arquivo resiste a queda do processo, mas no Windows não
prova durabilidade da entrada de diretório em caso de falta de energia.

Mitigação procedural: task/nonce da sonda são registrados como "somente
sonda" e nunca entram em proposta de rodada; o chamador nativo futuro deve
registrar duravelmente a invocação antes de lançar o processo; a futura
proposta de 23 casos usa task/nonce novos e confere ausência de claim e de
resultado de sonda para o próprio nonce antes de materializar.

## Contrato de testes com fakes (para o próximo lote)

Sem launcher/config/executável reais, raiz operacional, prefixo real nem
subprocesso. HOME redirecionado a `tmp_path`; entrada substituída por fakes
das quatro etapas via carga interna; relógios por sequência fake.

- Positivos: ordem exata claim → medição → marca → resultado; schema/tamanho
  do resultado; claim/marca/resultado com bytes canônicos e SHA coerentes.
- Fronteira: `elapsed` exatamente 3.0 é `WITHIN_3S`; `math.nextafter(3.0,
  inf)` é `OVER_3S`; 0.0 é `WITHIN_3S`; negativo, NaN e inf são
  `CLOCK_INVALID`; delta de diagnóstico zero é aceito; tick decrescente é
  `CLOCK_INVALID`.
- Fontes: SHA errado e tamanho acima do limite para preparador e entrada;
  arquivo que cresce lido no máximo `limite+1`.
- Runtime: plataforma, versão, isolated, bytecode e optimize errados recusam
  antes de carregar fonte capturada, ler externo, criar claim ou medir; argv
  errado no `__main__`; guarda antecipada só se implementada.
- Raiz/estado: fora do Temp, padrão errado, link/reparse/ausente em
  ancestral, arquivo extra, estado diferente ou maior que 32768.
- Claim: já existente, parcial, ilegível; falha antes de existir arquivo;
  escrita curta, fsync e releitura falhos; nenhuma etapa chamada antes do
  claim relido.
- Replay: segunda chamada com claim existente recusa sem medir, inclusive
  após queda simulada (KeyboardInterrupt) entre medição e marca; raiz
  continua FRESH e o teste documenta isso.
- Etapas: falha em cada uma das quatro gera `STAGE_FAILED` com etapa e
  `STAGE_EXCEPTION`, sem mensagem, mesmo com exceção de `__str__` hostil;
  etapas seguintes não são chamadas; marca e resultado ainda são gravados.
- Pós-medição: escrita curta/fsync/releitura falhos na marca e no resultado
  nunca devolvem sucesso; nada é apagado nem repetido.
- Efeitos: `subprocess.Popen`, `os.system`, criação de loop asyncio e novas
  threads proibidos durante import e `probe`; AST da sonda não referencia
  `prepare`, `run`, `drive`, `start_supervision`, `start_cycle` nem `sample`.

## Tradeoffs em aberto

1. A janela de queda deixa uma raiz FRESH; só a disciplina procedural impede
   seu uso. Alternativa (marca antes da medição) quebraria a `admit` medida.
2. Uma amostra única não é distribuição; `WITHIN_3S` é evidência necessária,
   não garantia para a rodada, e a `prepare` real continua decidindo.
3. A execução nativa futura lê os executáveis/configurações pinados de
   verdade, como a `prepare`; isso é parte do custo medido e exige comando
   próprio revisado, ambiente filtrado, supervisão com prazo e saída fechada.
4. `Context` e `final_pins` aqui recebem uma instância de Host sem monitores
   (igual à `prepare`); o custo terminal FINAL23 não é medido.
5. Sem controle de cache de disco/antivírus; as validações prévias podem
   aquecer o cache em relação a uma `prepare` real.

## Notas de implementação (helper/fakes, 2026-11-01 UTC)

Desenho corrigido aceito para implementação, não como procedimento nativo.
Arquivos: `docs/poc/pg16_shell_admission_probe.py` e
`tests/test_pg16_shell_admission_probe.py`. Testes NÃO executados pelo
programador; validação pelo revisor.

- Fontes: preparador 8d0bf39e07f0…695971 (9 546 bytes) e entrada afaffad0 lidos
  com `read(limite+1)`, ≤64 KiB; estado e as quatro etapas vêm da cadeia já
  pinada preparador → exportador → entrada (`load`/`fresh_state` internos do
  preparador, `d["entry"]`), sem nova Host antes da medição. Self-hash da
  sonda só como dado.
- Código acrescentado à lista fechada: `PROBE_TASK` (task inválido), além dos
  do desenho. Nenhum limite ampliado.
- Claim/resultado pendente/resultado final: qualquer ocupante do nome (arquivo,
  vazio, diretório, link pendente, reparse) recusa por `lstat`, sem abrir. A
  criação é só `xb`; corrida resulta `PROBE_CLAIMED` sem sobrescrever.
- Conclusão: marca na raiz e `result.json.next` são gravados, fsync e relidos;
  depois `os.rename` para o nome final é a última operação, sem leitura
  posterior. Falha de rename deixa o `.next` e não publica o resultado desta
  tentativa; um ocupante concorrente do nome final é preservado no Windows.
- Precedência: `STAGE_FAILED` > `CLOCK_INVALID` > `WITHIN_3S`/`OVER_3S`. Em
  relógio inválido `elapsed_seconds` e `stages_ns` são null; em falha de
  etapa os deltas das etapas concluídas e da que falhou ficam, as seguintes
  null. JSON com `allow_nan=False`, resultado ≤4096 bytes validado antes da
  marca.
- Interrupção (`BaseException`) propaga sem resultado; claim fica e bloqueia
  repetição. CLI: 0 só para `WITHIN_3S` persistido; 1 para outros desfechos
  e erros fechados; 2 para interrupção; uma linha JSON fechada.
- Limites restantes: o teste de definições reais lê só fontes do repositório
  e não constrói Host; nenhum teste prova o prefixo real, binários/config ou
  tempos nativos. A janela de queda e os tradeoffs acima continuam.

Observação de confirmação: uma falha de stdout após publicar o resultado
gera status não zero no CLI, mas não desfaz o artefato nem o claim. O futuro
chamador deve conferir os artefatos dessa tentativa e não repetir a medição.

Próximo após os gates de helper/fakes: procedimento nativo com registro prévio
de invocação, supervisão limitada/coleta e comando literal, revistos antes de
materializar uma raiz operacional ou executar a sonda. Gateway, B1/B2/D090/C1/
SQL e produção seguem abertos.
