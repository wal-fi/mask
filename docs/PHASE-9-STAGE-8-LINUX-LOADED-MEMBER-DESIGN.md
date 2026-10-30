# loaded-as128 — produtor e coletor, desenho antes do código

**2026-10-22 — proposta sob delegação, sem código/carga deste lote.**
Core puro anterior revisado:179 focados/474 relacionados. Preservar seus
resultados e as seis rodadas anteriores. Este incremento propõe implementar
produtor, leitura Linux e coletor de imports, com testes usando fakes. Ainda
sem supervisor executável, Docker, pressão real, banco, SQL ou produção.

## Arquivos e limite de confiança

- docs/poc/loaded_memory_member.py: produtor e LinuxIO concreto, construção
  de held em buffer fixo, leitura de status com buffer pré-alocado.
- docs/poc/loaded_memory_collect.py: coleta de imports por regra existente,
  reconstrução fechada do fluxo no supervisor e parser de /proc/limits.
- Testes correspondentes: sem construir LinuxIO real, alocar4MiB/2MiB,
  importar produto/Linux nativo, abrir /proc ou iniciar processos.

Não são módulos de src ou API genérica do produto; não há chamador operacional
nem entrypoint executável. LinuxIO real só pode ser construído por factory
Linux isolado/no-site, membro pid>=2 e ppid1, com deadline próprio<=20s.
Construtor privado recebe APIs confiáveis para testes, nunca configuração
externa/cliente. Composição do supervisor e comando serão outro gate.

## Produtor: ownership e ordem

1. Preparar saída held de1024 bytes, scratch de status<=64KiB+1 e dez slots
   de retenção **antes** da pressão. Abrir um fd RO/CLOEXEC de /proc/self/status
   no início e mantê-lo até fim: ele faz parte dos efeitos iniciais, não é fd
   extra oculto. Factory real configura stdin/stdout não bloqueantes e usa
   select com saldo do deadline; construção parcial limpa só os próprios
   recursos e restaura flags que alterou. Sem thread, subprocesso ou socket.
2. mmap privado anônimo2MiB explícito, páginas tocadas, incluído no baseline.
   Emitir ready com pid/ppid, VM e limites; esperar GO_IMPORTS. Imports novos
   de stdlib (mmap/resource/select) ocorrem antes do baseline em todos casos.
3. Callback confiável da coleta percorre os três imports aprovados e emite
   o inventário auditado. Só sucesso completo permite loaded com limits/VM.
   Depois esperar PRESSURE_PRIVATE/SHARED correspondente. Não escolher caso
   limitado por sinal do cliente, ler ambiente ou usar digest no membro.
4. Conferir getrlimit antes da pressão e em sua amostra final. Limites reais
   devem ser [-1,-1] no controle ou [134217728,134217728] nos128. Nenhum
   setrlimit é feito pelo membro; herança antes do spawn é gate do supervisor.
5. Para cada degrau, check de prazo **fora** do try de alocação. Só
   MemoryError/OSError lançado pelo alocador vira MEMORY/ENOMEM/OTHER.
   Guardar imediatamente o bloco no slot pré-alocado e tocar todas páginas.
   Falha de touch, amostra, comando ou relatório é diagnóstico inválido,
   nunca recusa de alocação. Não soltar cada degrau nem tentar depois da recusa.
6. Capturar limites e VM usando scratch preexistente, com todos os blocos e
   reserva ainda vivos. Leitura via lseek+readv limitada, parser só de quatro
   campos (VmSize/VmPeak/VmRSS/Threads), sem texto de erro/ambiente no relatório.
   A captura ainda pode falhar sob OOM: nenhum resultado imposto nesse caso.
7. Em128 após recusa, fechar **só** a reserva. Codificar held no buffer1024
   por literais fechados/números limitados, sem JSON de inventário/str/repr de
   erro. Escrever com deadline, aceitando writes parciais até completar uma
   linha; falha de emissão não cria held válido. Isso não garante recuperar OOM.
8. Manter payload até RELEASE_PRIVATE/RELEASE_SHARED correspondente ao kind,
   exatamente como os bytes do core, nunca RELEASE genérico. Liberar os slots e emitir
   released com kind; o supervisor lê VM/limits diretamente. No controle não
   começar shared antes de receber PRESSURE_SHARED: o pai deve comprovar queda
   anon/VM primeiro. Esperar FINISH, emitir done; sem ACK ou no timeout,
   falhar e limpar o que pertence ao membro, sem declarar sucesso.

Cleanup sempre tenta todos os slots, reserva e fd próprio, mesmo se um close
falhar. Só caminho completo e cleanup local confirmado devolve0; falha de
diagnóstico/cleanup devolve77 fixo, sem mensagem/cadeia original. Código0
sozinho não é resultado aprovado: supervisor ainda exige EOF e reap reais.
Interrupções devem levar a falha/cleanup, não a outra fase. Falha de cleanup
no SO pode requerer recolher o processo; não afirmar ausência de resíduo só
porque houve uma tentativa. Nenhum fallback ilimitado ou retry de pressão.

## Coletor de imports e harness fechado

Reusar ROOTS, module_row/audit_module, efeitos, native_check e codec do probe
de imports já revisado. Não copiar matching de origens nem criar wildcard.
Membro usa audit_module(batch=None); erro de auditoria interrompe sem batch,
sem imports seguintes ou pressão. MemoryError/ImportError na importação
conservam categorias/códigos antigos; outras falhas são fechadas.

Exceções de harness novas são pares exatos nome/arquivo em /probe:
__main__ -> linux_loaded_probe.py (ainda futuro),
_lab_loaded_protocol -> loaded_memory_protocol.py,
_lab_loaded_member -> loaded_memory_member.py,
_lab_loaded_collect -> loaded_memory_collect.py,
_lab_import_probe -> linux_import_probe.py,
_lab_support -> linux_as_probe.py (já existente).
Exigir ModuleType exato, __dict__ com __file__ str e path resolvido exato.
Não usar essa lista para produto/dependências; owner=harness e caminho
probe/arquivo. Fontes serão copiadas/hash conferido pelo futuro observador.
Nenhuma regra nova para wrappers ou módulos sem origem.

Parser de eventos do supervisor mantém baseline -> start/module/end0..2 ->
verified, com schema fechado, stage int exato,<=1500 linhas e mesmos limites
de codec. Cada end exige threads1/fds invariantes; verified exige binary e
quatro roots nativos não vazios, relacionados a .so já auditados em /installed.
Não permitir que marker/flag isolado substitua a sequência. Linha extra ou
faltante, audit_error/check_error/error fecham a coleta e não entregam linhas
para admit_imports. Parser nunca envia comandos; só fluxo completo devolve
snapshot das linhas para o core calcular o digest antes de PRESSURE.

Picos/limits independentes virão de /proc/<pid>/status e /proc/<pid>/limits,
com leitura limitada. Parser limits só aceita a linha Max address space,
soft/hard inteiros ou unlimited e unidade bytes; duplicado/truncado/fora
de faixa é recusa. Não inventar counters se arquivo falhar. A integração
dessas leituras com pid/inventário/lifecycle ainda será gate do supervisor.

## Testes e revisão antes de qualquer uso real

Fakes de allocator/clock/fds/select/readv/getrlimit e blocos pequenos com
endereçamento simulado: testar toque/retention, alocação vs touch, primeira
recusa, errno, amostra antes do close, reserva antes da emissão e payload
até RELEASE, dez slots, fase/comando errado, writes parciais/timeout/EOF,
cleanup parcial e interrompido. Não usar pressão real como teste de unidade.

Testar status/limits com bytes sintéticos, chaves/unidades/overflow/duplicado;
coleta legítima e fluxos forjados, origens do harness só por pares exatos,
hooks hostis não autorizados, callback import falhando sem vazamento e nenhum
PRESSURE emitido pelo coletor. Conferir compatibilidade da linha held pelo
core existente e preservar474 testes anteriores.

Revisar plano, código/testes e integração antes de novo supervisor executável
e de qualquer comando/caso real. Domínio externo192MiB não exercitado,
128MiB não default/cota de produção; B-1/B-2/D-090/SQL/produção abertos.
Sem dependência, ambiente, segundo escritor, commit/push ou deploy.

## Refinamentos obrigatórios da revisão antes do código

Claude2 revisou somente o desenho em 2026-10-22, na sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f. Sem bloqueador de desenho, condicionado
a M1–M4, incorporados aqui; M5 também incorporado. Aval apenas para testes
com fakes primeiro, não para carga, integração ou produção.

- M1: tabela fechada: 0 caminho completo/cleanup confirmado; 72 MEMORY,
  73 IMPORT, 74 OTHER da importação; 75 audit_error; 76 check_error;
  77 demais falhas de diagnóstico/protocolo/prazo/cleanup. Cleanup ou falha
  do transporte prevalecem sobre qualquer código anterior com 77. O evento
  emitido não substitui a conferência posterior do exit code pelo supervisor.
- M2: um único writer com deadline para **todos** os eventos, inclusive os
  emitidos por audit_module/check_failure via adaptador. EAGAIN espera select,
  writes parciais completam só a linha atual. A falha do writer fica marcada,
  mesmo quando o helper antigo a captura; nunca vira recusa ou auditoria
  aprovada. Todos os comandos passam pelo reader novo; emit/command antigos
  não tocam nos fds não bloqueantes.
- M3: os pares fechados de harness são verificados **antes** de module_row.
  Nome de harness com tipo/path errado produz OUTSIDE_ORIGIN, sem fallback.
  Ausência de um par em sys.modules é permitida: spec/exec_module não o
  insere necessariamente. Nomes não harness usam as regras antigas intactas.
- M4: os padrões de toque (1024 páginas por bloco, 512 na reserva) são
  preparados antes da pressão. Um único slice estendido buf[0::4096] recebe
  o padrão; sem loop Python alocando um int por página. Contagem vem do
  tamanho do bloco. Falha do slice continua diagnóstico, não recusa.
- M5: held tem ordem fixa phase/kind/limits/vm/accepted_bytes/touched_pages/
  blocks/failure/errno; vm tem size/peak/rss/threads; decimal simples e null
  literal. Testar todas as variantes pelo decode_held já revisado.
  loaded tem exatamente phase="loaded", limits e vm; ready tem exatamente
  phase="ready", pid, ppid, limits e vm. O futuro supervisor deve validar
  esses envelopes antes de chamar o core; loaded não substitui verified.

Buffers preexistentes reduzem demanda, não prometem que operações Python
sejam livres de alocação nem que qualquer OOM permita relatório válido.

Revisão do código encontrou B1: RELEASE genérico no produtor não correspondia
ao comando específico do core. Cinco regressões primeiro falharam; correção
mantém a origem dos comandos no core real nos testes de interop com fakes.
Falha de sample dentro da coleta pode emitir check_error76, mas o transporte
marcado failed faz o exit final77 prevalecer: diagnóstico inconclusivo, nunca
admissão. Spawn futuro precisa close_fds, pois só012+status_fd são aceitos.
