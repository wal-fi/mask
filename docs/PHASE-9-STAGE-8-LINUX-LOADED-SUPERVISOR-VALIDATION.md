# loaded-as128 — supervisor, somente testes simulados

**2026-10-22 — código isolado revisado sem bloqueador; nenhuma execução real.**
Sob delegação vigente, sem atribuir aprovação individual fictícia. B-1 fim
a fim/B-2/D-090 gate2, SQL PGWire e produção continuam abertos. AS32 permanece
did_not_fit; as seis rodadas anteriores não foram alteradas ou repetidas.

## Entrega delimitada

docs/poc/linux_loaded_probe.py compõe core, produtor/coletor e helpers
congelados. Importar o arquivo não inicia trabalho. Entrypoint permite só
Linux isolado/no-site/UID65534, supervisor PID1 ou membro pid>=2/ppid1;
argv fechado do core, case/digest no supervisor, só case no membro.
Runtime manifest preserva owners/versions/generated. Helpers são carregados
por spec com os nomes/arquivos exatos já aprovados, sem ampliar origens.

Backend real confere perfil/NNP/caps/cgroup/AS antes de criar um único filho;
pré-aloca o objeto de ownership antes de Popen e anexa o handle antes de
configurar canal. close_fds, -I -B -S, env só PATH, pipes sem buffering,
stderr descartado. Canal preserva held cru, limites de linha/buffer, quiet
por buffer e select, writes parciais com saldo do prazo, EOF só sem resto.

Leituras independentes de status/limits/PPid/inventário/cgroup precedem
comandos. Fds exatos só nos pontos bloqueados; end012 registra fds=None na
leitura do pai, mantendo a auditoria de fds do membro. Digest comparado antes
de PRESSURE. Candidato de resultado não é exportado antes de done/EOF/wait,
reap/fechamento dos pipes, inventário final[1] e cgroup sem pressão. FAIL
também exige confirmação independente antes do kill; sinal não vira recusa.

No controle, descarte privado usa o mesmo core: duas condições, até cinco
amostras separadas por1s dentro dos20s, sem novo comando ou ampliar prazo.
Leitura completa final ocorre antes de FINISH, nunca depois de done (o filho
já pode ter saído). Early exits exigem EOF/exit natural concordante/cleanup,
sem leitura de fd racy após o evento. Kill próprio é registrado por proxy
que reusa o reap antigo; nenhum outro processo é recolhido por esse código.

Medição tem prazo único20s. Depois de cleanup/final, emissão de até64KiB tem
prazo próprio2s, sem STOP impedir só essa tentativa de diagnóstico; não
renova medição ou autoriza trabalho novo. Canal de relatório falhando sai70,
sem traceback/fallback bloqueante. Cap/falha de serialização produz fallback
inconclusive sem digest. Margem de tamanho é risco registrado, não medida
de memória total.

## Desenho e testes primeiro

Desenho em PHASE-9-STAGE-8-LINUX-LOADED-SUPERVISOR-DESIGN.md, revisado na
sessão somente leitura51ea0d85-05bb-4d24-ba9a-c9627c3f832f antes do código.
R1–R4 incorporadas. R4 foi corrigido em conferência antes da implementação:
depois de done não existe ponto estável; usar pré-FINISH. N1 reforçou FAIL
independente e N2 restringiu incompatible aos dois casos128 com72/73 natural.

Teste criado antes do módulo: primeira coleta falhou por arquivo ausente;
não são regressões contra módulo anterior inexistente. Primeira seleção
passou35 casos, depois50 com backend/canal. Um placeholder sem asserção útil
de sleep foi substituído por testes reais do descarte e falha de sleep.

Duas regressões adicionais foram executadas vermelhas antes do ajuste:
arquivo children vazio sem newline (comportamento legítimo do proc) e
manifesto existente com versions. Corrigidos sem fallback/relaxamento de
origem. Anotações/estilo dos testes foram acertados sem mudar configuração.

## Revisão bloqueante e correções

Primeira revisão de código encontrou S1 e exigiu S2:

- S1: end012 não é estável para fds: a próxima importação pode abrir arquivo.
  Recomendação inicial do desenho também era incorreta. Corrigido observe
  stable=False nessas janelas, sem listar/readlink/comparar fd ou inventar
  sua medição; status/limits/PPid/inventário/cgroup permanecem obrigatórios.
  Ready/loaded/pré-PRESSURE/HELD/released/amostras/pré-FINISH continuam com
  verificação de fd exato. Teste de extra fd transitório falhou primeiro,
  depois passou no modo mid-import e continuou recusado no ponto bloqueado.
- S2: timer da medição expirado fazia perder relatório de timeout. Teste no
  main falhou antes da correção; passou com orçamento separado2s após cleanup.
  Teste de timeout do próprio relatório confirma que não espera indefinido
  e restaura flags. Prazo de medição não muda.

Rerevisão confirmou S1/S2 fechados e nenhum bloqueador novo no código isolado
com fakes. Revisor não executou testes; números/hashes são deste executor.
Não aprovou host/inspect/preflight/comando/carga/produção.

## Gates finais medidos

Windows, .venv existente Python3.11.3, somente APIs/processos/arquivos/clock
simulados. Nenhum LinuxSupervisor real, Popen real, mmap/payload/reserva real,
/proc, banco, SQL ou Docker foi executado por este lote.

- **59 testes novos passed em0,31s**, sem skips/xfail; incluindo fluxos
  completos com core/collector reais, origem/digest antes de pressão,
  limites/inventário/fds/PPid divergentes, exit natural/categoria, cleanup,
  pressão externa, FAIL sem/com confirmação, bytes crus/EOF extra/parcial,
  read agrupado, held antecipado/grande, quiet/select, EAGAIN/EINTR/parciais,
  AS antes de spawn, argv/env exatos, canal falhando com filho já criado,
  /proc fd negado sem fallback, descarte convergindo/falhando e relatórios.
- **669 relacionados passed em2,58s**:610 anteriores+59 novos, seleção completa
  dos testes linux_as/linux_imports/loaded_memory, -o addopts=, sem deselect.
- Ruff src/tests limpo; E/F/I/B/UP do novo PoC limpos.
- Format check **255 arquivos** (src/tests e novo PoC), todos conformes.
- mypy strict alvos3.11 e3.14: **254 source files**, ambos limpos.
  Alvo3.14 é somente análise estática, não execução desse runtime.
- git diff --check limpo, avisos LF/CRLF já conhecidos; novos arquivos
  conferidos separadamente quanto a whitespace.

Sem repetição de suíte integral PG16, frontend ou pacotes: src/recursos/
dependências não mudaram neste lote. Medições anteriores não são novo gate.

SHA-256 finais:

- linux_loaded_probe.py:40ead31f7fe57cb2102f30c1be3f535fa342e3ae22d8696e0970d4eab4315466;
- test_loaded_memory_supervisor.py:2a2d6afb07673e5b032bbeb90bf0bccbd6bb68f8d7ea9a80cb0f7ac41af2ef16.

## Limites e próximo gate

Primeiro acesso real a /proc/<pid>/fd/readlink do filho depende de ptrace/
dumpability/perfil do container, não comprovado por fakes. Falha deve encerrar
inconclusive sem usar fds declarados. Igualdade estrita do pico pode dar falso
inconclusive por pequena alocação após a amostra do membro; não relaxar depois
de medir. Supervisor sob AS128 também pode falhar em coleta/pack/JSON.

Falta observador externo próprio: perfil loaded-as128/argv/inspect, passagem
do digest só do controle concluído, cópia/hash dos novos helpers e fontes,
preflight obrigatório, identidade/cleanup/watchdog, resultado e stop do lote,
comando exato revisado antes da rodada única. Nada real foi iniciado por este
entrypoint.192MiB externo não foi saturado;128 não é default de produção.

Inspeção de processos encontrou Docker Desktop ativo; **não foi iniciado nem
parado por este lote**, e nenhum comando Docker foi emitido. Não atribuir
origem à atividade observada nem tocar em recursos de outros trabalhos.
Sem limite do Claude2 observado, job novo ou escritor concorrente iniciado.
Sem commit/push ou deploy. Alterações anteriores e arquivos pessoais preservados.

## Auditoria do fechamento

Baseline novo do início deste lote:360 caminhos, final364, zero ausentes.
Mudanças em existentes somente nos seis documentos de estado; quatro novos
(desenho/evidência, supervisor e teste). Zero arquivo src alterado neste
lote, helpers/core/produtor/coletor anteriores e .venv/pyvenv.cfg preservados.
HEAD4a5e556, origin/master em cache5d173ea,0behind/1ahead; sem fetch ou escrita
Git. Diff e whitespace dos novos limpos. Depois dos gates só documentação
mudou; suítes não repetidas por isso. Nenhum processo de laboratório próprio
foi iniciado ou ficou aguardando comando.
