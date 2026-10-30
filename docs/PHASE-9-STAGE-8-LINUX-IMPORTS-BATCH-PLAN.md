# Próximo diagnóstico — relações fileless limitadas, sem nova aceitação

**2026-10-21 — implementado localmente, em revisão de código antes da execução.**
Quarta rodada preservada em `PHASE-9-STAGE-8-LINUX-IMPORTS-ATTRIBUTION-VALIDATION.md`.
Ela comprovou vínculo por identidade de `_openssl`, parou em `_openssl.lib`
e não abriu AS32. Não inferir que .lib tem o mesmo tipo ou origem, nem
liberar `_openssl.*` ou CFFI genericamente. Nada de regra nova neste plano.

Para reduzir rodadas de descoberta, adotar a opção diagnóstica sugerida
pelo Claude2, ainda com revisão separada de plano e código antes de executar:

1. Só depois de audit_error FILELESS_UNATTRIBUTED na etapa já importada,
   manter o resultado inconclusivo e não continuar imports/start/end/verified
   ou AS32. Outra categoria ou baseline(-1) não abre batch; só etapas0..2.
   Reusar a lista ordenada do **delta inteiro da mesma etapa**, já calculada
   pela auditoria, sem nova captura de sys.modules; inclusive a entrada
   que falhou. Examinar até1.500 nomes. Lookup get com sentinela distingue
   entrada ausente de valor None; ausente vira ABSENT/dict_file=null/slotNONE.
   Nomes já emitidos com sucesso na etapa são excluídos por bookkeeping,
   sem revalidar origem. Emitir até **oito candidatos**, não erros ou linhas aceitas. Não
   afirmar inventário aprovado: o classificador de **candidatos** não usa
   module_row, audit_context, varredura de ancestral/Cython ou decisão de
   aceitação. Só a revalidação da âncora permite module_row no provider
   exato ModuleType/file-backed, pela regra de identidade já existente;
   nunca module_row em candidatos. Âncora falha -> UNANCHORED/slotsNONE.
2. Classificador próprio sem leitura de atributo do candidato não-módulo:
   type(obj) is ModuleType -> só dict exato e get('__file__'); se str não
   vazia, pular. Caso contrário MODULE_EXACT/dict_file=false; se o dict
   não é exatamente dict, usar dict_file=null, sem fallback. Qualquer
   outro tipo (inclusive valor None presente no cache) -> NON_MODULE/
   dict_file=null, sem acessar __dict__, __file__,
   __class__, metadados de tipo, ==, repr ou getattr. Isso não declara que
   o objeto é fileless por prova de ausência de __file__, só candidato.
   A auditoria antiga que produz o primeiro erro **já** leu __file__ em
   module_row/audit_context na quarta rodada, inclusive no objeto .lib.
   Este incremento não altera esse caminho; a promessa sem leitura se
   aplica exclusivamente ao passe batch, não retrospectivamente.
   Primeiro classificar/contar os nomes examinados e depois emitir por
   grupos: NON_MODULE, MODULE_EXACT, ABSENT, ordenado por nome em cada um.
   Isso prioriza o objeto ainda desconhecido sem tocar em seus atributos.
3. Só observar relações por **is** com chaves fechadas lib/ffi no dict do
   `_openssl` exato já ancorado por identidade na extensão Rust verificada.
   Revalidar a âncora antes dos slots: tipos exatos, dict, mesma entrada
   sys.modules, mesma identidade e origem/owner/path verificados, não confiar
   apenas em linha emitida anteriormente. Chave deve existir e seu valor
   não ser None; candidato None sempre tem slot NONE (get ausente não é
   evidência). Nunca usar == nem consultar o objeto valor.
   Ler somente dict de ModuleType exato, nunca atributos do objeto .lib.
   Detalhe identity_slot=LIB/FFI/BOTH/NONE; se ambos os valores são o mesmo
   objeto candidato não-None, BOTH. Não é declaração de autoria/aceitação.
   Falha de ancoragem deve ser marcada e não autoriza exploração genérica.
4. Protocolo terminal: audit_error -> batch_detail* -> batch_end -> EOF,
   membro exit75 coletado. batch_detail tem exatamente phase,stage,module
   (nome validado<=200/null),kind,dict_file e identity_slot (LIB/FFI/BOTH/NONE).
   batch_end tem exatamente phase,stage,examined (int0..1500),details
   (int0..8),non_module_total,module_exact_total,absent_total (cada int0..1500),
   incomplete (bool),anchor (ANCHORED/UNANCHORED). Totais contam candidatos
   nos nomes examinados, inclusive não emitidos, não entradas aceitas/puladas.
   Soma dos totais<=examined; details<=soma e cada kind emitido<=seu total.
   Se incomplete=false, soma=details (nenhum candidato omitido). Se a âncora
   falhar, todos os slots são NONE. Oito candidatos permitem complete só
   se não há nono no delta; nono não emitido -> incomplete=true. Atingir
   cap de1.500 nomes -> incomplete=true, conservador mesmo no último nome.
   details é contagem das linhas emitidas; totais só descrevem a amostra
   examinada, nunca prova de conjunto aprovado. KindABSENT sempre slotNONE,
   NON_MODULE/ABSENT têm dict_file=null, MODULE_EXACT tem false/null.
   Mais linhas/forja/EOF antes do fim/ausência de batch_end/timeout viram
   PROTOCOL e incomplete=true, com cleanup e returncode pelo prazo.
   Validar tipos exatos e etapa ativa; não copiar corpo indevido. Detalhes
   separados, não duplicados em events/module_inventory. Cap4KiB/linha,
   8.000 bytes de metadados,56/64KiB de resposta e20/30/120s não mudam.
   Excesso fica inconclusivo, nunca aumenta limite. Nenhum batch abre AS32.
5. Testes puros primeiro: múltiplos recusados, oito/nove detalhes, identidade
   falsa com == enganoso, ModuleType subclass, candidato não-módulo com
   atributos hostis nunca lidos, nome inválido e cap/deadline. Revisão de
   código Claude2 antes de nova rodada própria. Nenhum fonte executado até
   agora será alterado nos artefatos congelados.
   Incluir contraprovas de prioridade/orçamento com módulos já aceitos,
   chave ausente versus None, BOTH, baseline sem batch, dict não exato,
   totais/contagens forjados e None nunca associado por default de get.

Somente depois de medir/revisar as relações será possível desenhar uma
eventual regra exata para objeto não-módulo. Não implementá-la por este
plano. Sem produto, worker, SQL, banco, cota maior, dependência ou produção.
B-1 fim a fim, B-2 e D-090 gate2 continuam abertos.

Revisão do plano na sessão51ea0d85: A1–A5 e U1–U5 respondidos. Última
condição textual aplicada: proibição de module_row é só para candidatos,
não para a âncora verificada; nenhum código alterado. Opção None mantém
NON_MODULE/slotNONE explicitamente, sem novo kind; pode consumir vaga antes
de outros tipos, uma limitação diagnóstica, nunca aceitação. Próximo lote:
testes primeiro, implementação, gates e revisão do código antes de executar.

Implementação diagnóstica em linux_import_probe.py e defesa no classificador
do observador; nenhum src alterado.35 testes novos vermelhos contra a versão
anterior,48 novos no total/218 relacionados verdes. Gates estáticos limpos.
Revisão somente leitura de código/testes solicitada na sessão51ea0d85,
sem container/Docker iniciado. Evidência própria:
`PHASE-9-STAGE-8-LINUX-IMPORTS-BATCH-VALIDATION.md`. Plano não libera uma
regra para .lib, SQL, worker, B-2/D-090 ou operação real.

Reforços pré-execução: condição no host recusa batch mesmo com outcome
normal (teste vermelho antes); modo --diagnose somente do PoC fixa control
como único caso nesta rodada, sem AS32 em qualquer resultado. --run/default
preserva os dois casos condicionais. Novo teste de modo normal sem batch
também vermelho antes;220 relacionados verdes. Revisão restritiva final
solicitada antes de executar. Nenhum setting ou código de produto alterado.
