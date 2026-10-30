# loaded-as128 — produtor e coletor, somente testes com fakes

**2026-10-22 — código isolado revisado sem bloqueador, sem integração/carga.**
Trabalho sob delegação vigente; não é aprovação individual fictícia nem
fechamento de B-1, B-2 ou D-090 gate2. Histórico AS32 did_not_fit e seis
rodadas anteriores preservado. Não houve novo caso de memória.

## Entrega e limites

- docs/poc/loaded_memory_member.py: produtor, backend LinuxIO concreto com
  factory restrita a Linux isolado/no-site, pid>=2/ppid1, prazo<=20s;
  status fd RO/CLOEXEC, scratch<=64KiB+1, writer não bloqueante com select,
  held<=1024 em buffer existente, slots e padrões preparados antes da pressão.
- docs/poc/loaded_memory_collect.py: reuso das regras/ROOTS/codec de imports,
  interceptação dos seis pares exatos de harness antes das regras antigas,
  coletor fechado baseline/start/module/end012/verified, envelopes e parser
  de limits. Não envia comandos ou calcula digest de admissão.
- Dois arquivos de testes novos, só fakes. Não se construiu a factory Linux,
  nem se alocou payload4MiB/reserva2MiB real, abriu /proc ou iniciou processo,
  Docker, DB, conexão, SQL ou serviço. Spies conferem tamanhos/flags do mmap
  e bytearray sem alocar os payloads. Scratch pequeno real não é pressão.

Não há entrypoint, supervisor executável, consumidor de produção, dependência
ou configuração externa nova. Os módulos não ficam em src e não mudam o
produto. Funções injetadas de teste são colaboradores confiáveis, não seleção
por cliente ou argumento externo. Preparar buffers não garante ausência de
alocações Python nem diagnóstico bem-sucedido em todo OOM.

Alocação privada bytearray4MiB, compartilhada mmap anônimo MAP_SHARED4MiB e
reserva mmap anônimo MAP_PRIVATE2MiB são explicitadas no código. Só a chamada
do alocador está no try que classifica MEMORY/ENOMEM/OTHER. Touch usa um slice
estendido com padrão preparado, não loop alocador por página. Bloco é retido
antes do touch. Amostra é anterior ao close da reserva; payload fica vivo
até RELEASE_PRIVATE/SHARED exato. Cleanup tenta todos os recursos e qualquer
incerteza prevalece com exit77. Nada disso foi medido contra o SO neste lote.

Uma saída com prazo serve todos os eventos, inclusive audit/check antigos via
adaptador. Falha capturada por helper antigo ainda marca io.failed, e77
prevalece. Em particular sample falhando no fim de uma etapa pode emitir
check_error76 mas sair77: inconclusivo/PROTOCOL, não admissão. Fds esperados
são012+status_fd; future spawn precisa close_fds. Exit0 sozinho não é prova.

## Desenho e testes primeiro

Claude2 revisou o desenho antes do código (sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f), sem bloqueador condicionado a M1–M4;
os quatro refinamentos e M5 foram incorporados antes da implementação.
Desenho em PHASE-9-STAGE-8-LINUX-LOADED-MEMBER-DESIGN.md.

Cada arquivo de teste foi criado antes do módulo correspondente. As primeiras
coletas falharam por arquivo ausente. Não são alegações de regressões contra
código anterior inexistente. Primeira implementação passou58 testes de
membro; depois o conjunto inicial passou118. Dois testes da coleta tiveram
ajuste do fake para semântica de paths Linux (PurePosixPath). A rodada também
teve dois erros de setup com parâmetro gigante; ele ganhou ID curto, evitando
nomes enormes no pytest. A repetição ficou verde; não atribuí causa adicional
sem diagnóstico separado. Nenhuma regra de origem foi relaxada por isso.

## Revisão bloqueante e correção antes da integração

Revisão somente leitura do código encontrou B1: o membro esperava RELEASE
genérico, mas o core envia RELEASE_PRIVATE/SHARED. T1 exigiu teste que
consumisse os bytes do core real, em vez de repetir comandos à mão no fake.

Cinco testes novos falharam antes da correção: três fluxos guiados pelo core
(controle com dois allocators e cada caso128), e duas trocas de kind no
release. Correção limitada ao allowlist e espera do comando correspondente;
fake básico ajustado, genérico recusado. Esses cinco passaram depois.

CoreChannel agora obtém todos os comandos de PressureProtocol real, devolve
held para core.held e termina core.completed com EOF/exit/cleanup/inventário
**declarados pelo fake**, não medidos. Teste não substitui leituras independentes
do supervisor. Casos adicionais cobrem reader exato, genérico recusado, flags
e tamanhos das chamadas nativas via spies, cleanup de fd, falha de amostra e
deriva do limite nas quatro fases. Matriz final:136 novos casos.

Rerevisão na mesma sessão confirmou B1/T1 fechados, sem bloqueador restante
de comando, ownership, cleanup ou coletor, **somente no código isolado com
fakes**. O revisor não executou os testes: números/hashes são medições deste
executor. Um PLW0108 do spy foi corrigido trocando lambda por calls.append,
sem mudança funcional ou relaxamento de configuração.

## Gates medidos sobre o resultado funcional final

Windows, .venv existente Python3.11.3; sem instalação ou mudança do ambiente.

- Novos testes de membro/coleta: **136 passed**, sem skips/xfail.
- Seleção completa de regressão do laboratório: **610 passed em2,76s**
  (474 anteriores +136 novos), sem skips/xfail; `-o addopts=`, sem deselect.
  Uma seleção intermediária menor passou439; depois a seleção completa
  passou592 antes dos18 casos finais. Não confundir com suíte do produto.
- Ruff src/tests: limpo; E/F/I/B/UP nos dois PoCs: limpos.
- Format check: **255 arquivos** conformes (src/tests e dois PoCs novos).
- mypy strict alvos3.11 e3.14: **253 source files**, ambos limpos.
  O alvo3.14 é análise estática; runtime3.14 não foi executado neste lote.
- git diff --check limpo, com avisos LF/CRLF já conhecidos.

Não repetidas suíte integral com PG16, frontend, pacotes ou carga Linux:
nenhuma alteração de produto/recursos/dependências neste lote. Os números
anteriores continuam históricos, não foram reaproveitados como nova medição.

Hashes SHA-256 finais do código/testes:

- membro fea05d739b61eff9ba8b23d49cf283f8de9837e711218f7f1965d7392d47eddd;
- coleta 6d06bfe5344e53596dbbde9e3ae14914b6550cb73147b399e788300e54a733bb;
- teste membro 1f6afae395c08596dde6ae994606e28be1d18945bae7112ef9e92018ee670da4;
- teste coleta fd5b611c37b3a37010ee646dcc72c42212986fd0102cf5c24cd956bbf71651c2.

## Próximo gate, não entregue por este lote

Supervisor precisa compor os helpers/core, ler /proc/<pid>/status e limits
independentemente, confirmar efeitos e inventários, EOF/reap/cleanup reais,
deadline global, spawn/AS herdado antes de criar o membro e quatro fds exatos.
Também faltam argv/inspect com digest esperado, perfil e preflight do host,
comando exato e revisão antes de qualquer rodada própria.

AS128 experimental não vira default de produção nem redefine AS32. Domínio
externo192MiB não foi saturado. B-1 fim a fim/B-2/D-090 gate2 permanecem
abertos; SQL PGWire continua0A000, MCP legado inalterado. Sem deploy,
commit/push, outro escritor ou job novo; nenhuma cota do Claude2 observada.

## Auditoria do fechamento local

Baseline novo do início deste lote:354 caminhos; final360, zero ausentes.
Só seis documentos existentes de estado foram atualizados, mais seis novos
(desenho/evidência, dois helpers e dois testes). **Zero arquivo src alterado
neste lote**; diferenças anteriores continuam preservadas. Fontes e artefatos
anteriores e .venv/pyvenv.cfg iguais ao baseline. Sem fetch ou escrita Git:
HEAD4a5e556, origin/master em cache5d173ea,0behind/1ahead.
Nenhum processo Python/Docker ao fim; Desktop não foi iniciado.
Depois dos gates só documentos foram atualizados; não repetidas suítes por
isso. Novos arquivos passam conferência de whitespace além do diff Git.
