# Etapa 8 — receptor limitado e ownership real de saída (D-114)

**2026-10-20: incremento interno local sob delegação, sem commit/push.
Revisão somente leitura do Claude2; não é liberação de SQL ou produção.
B-1 fim a fim, B-2 e D-090 gate 2 continuam abertos.**

## 1. Checkpoint e escopo

`master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`, referência local
`origin/master` em `5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind,
sem fetch. Working tree já continha lotes anteriores e arquivos pessoais;
foram preservados. Freeze de 296 arquivos selecionados antes deste lote.

Plano: `PHASE-9-STAGE-8-RECEIVER-PLAN.md`. Revisão do plano e do código na
sessão `e3df1a1e-ecca-4b1f-b5a6-0b2633f83d03`, só Read/Glob/Grep, sem
comandos, agentes ou edição. Executor desta conversa é o único escritor.
As contagens abaixo são medições do executor, não execução pelo revisor.

## 2. Implementação

- `pgwire/result_receiver.py`: lê só os 76 bytes fixos, valida tamanho,
  identidade e mínimo estrutural com o mesmo `inspect_result_header` usado
  pelo validador completo. Só depois aloca bytearray exato; recv_into em
  fatias, cópia imutável e descarte do mutável antes de validar.
- `ResultDeadline.remaining` compartilha prazo absoluto entre I/O e parser;
  relógio inválido/falho retorna zero. `RawChannel.recv_into` exige view
  gravável, contígua, 1D/B, válida e não vazia; progresso int exato dentro da
  fatia. As views de recepção/envio são liberadas, inclusive nas falhas.
- `BudgetLedger.begin_output` usa os créditos P já reservados da sessão LIVE:
  F/overhead positivos, `2F + overhead <= P`, token separado com épocas de
  sessão e saída sem wrap. Não admite segundo resultado. `release` não
  libera sessão pinada, mesmo com confirmação output=True.
- Mesmo plain Lock externo serializa ledger/decisões; espera limitada pelo
  prazo e 250 ms. I/O, alocação e descarte pesado ocorrem fora do lock.
  Cada operação possui seu próprio Event de conclusão, sem corrida com a
  conclusão atrasada da operação anterior.
- Receptor não retorna payload, descritor ou chunks. `send_to` aceita só as
  classes auditadas RawChannel/TlsChannel e devolve metadados escalares;
  envia exclusivamente corpo validado. Mesmo depois de SENT, mantém o pin.
- `close` retira o dono sob lock, descarta fora dele e só então limpa pin e,
  se necessário, faz drain num commit lógico único. Não libera worker, P,
  conexão ou vaga da sessão. Não possui finalizer devolvendo créditos.
- Erros externos fechados, sem mensagem/cadeia original; tracebacks inativos
  limpos. Interrupção, grupo/chain opaco ou limpeza não comprovada mantém
  pin. Transporte transmite só um bool de incerteza quando sanitiza uma
  cadeia; nunca anexa a exceção. Timeout nativo simples continua no mesmo
  prazo, mas timeout opaco falha fechado em vez de perder esse fato.

Não foi alterado nenhum chamador operacional do receiver, pipeline, registry,
lease, worker, listener, driver, SQL, MCP, Admin/UI, configuração ou dependência.
`transport.py` existente mudou e recebeu regressões próprias, inclusive TLS.

## 3. Contratos obrigatórios para a integração futura

1. **Quarentena permanente:** incerteza marca HELD; este receptor não possui
   API para remover essa incerteza. Pin e créditos continuam indisponíveis
   até encerrar/reiniciar o processo, sem reutilização otimista ou por GC.
2. **Envio pode ter concluído antes de BUSY/DEADLINE:** a aquisição do lock
   posterior ao I/O pode falhar depois que todo o corpo chegou ao cliente.
   Qualquer ReceiverError em send_to significa saída não comprovada; drenar
   e fechar a conexão, sem retry/reenvio. Não é rollback do que já foi enviado.
3. **Um frame por job e canal quieto:** lê exatamente frame_bytes, não EOF.
   Bytes residuais continuam no canal. Coordenador/worker devem garantir
   um frame por job, identidade/job novos e canal quieto, ou fazer drain.
   Receptor isolado não autentica produtor, pipeline nem monotonicidade de job.

Close de saída não enviada/falha marca sessão DRAINING; só envio normal e
close comprovado permitem sessão LIVE novamente. Shutdown aceita limpar pin
existente, mas não admite saída nova. Prazo de cleanup deve ser novo, não o
deadline de leitura já expirado. Estas são obrigações, não integração entregue.

## 4. Testes e falhas preservadas

Antes da implementação houve erros de coleta para as APIs ainda ausentes
(pin, inspect_result_header, result_receiver). Primeira rodada ampliada do pin:
4 failed/384 passed porque monkeypatch em instância com slots é read-only;
harness corrigido para injetar no método da classe, sem relaxar os asserts.

Regressões reproduzidas antes dos fixes:

- grupo de exceções era tratado como limpeza confirmada; view já liberada
  levantava ValueError cru: **2 failed, 59 deselected** na seleção específica;
- OSError com contexto de grupo perdia a incerteza ao virar IO no transporte:
  **1 failed, 82 passed**; agora flag escalar conserva a retenção do pin;
- timeout com grupo em contexto era ignorado e a operação seguia: **2 failed,
  39 deselected**; agora IO/incerto, sem retentar esse caso.

Uma rodada intermediária ampliada teve 1 falha e 2 erros de setup, com IDs
parametrizados gigantes no relatório; o harness passou a usar IDs curtos.
Os dois erros não foram declarados findings de produto sem atribuição própria.
A falha de contexto acima foi mantida e corrigida, não removida/skipada.
Gates estáticos intermediários recusaram anotações/formatação do harness;
foram corrigidas e repetidos sobre os arquivos finais.

Cobertura final: cabeçalho antes de alocação, short reads/EOF/prazo absoluto,
OOM/IO/progresso inválido, sessões/tokens/épocas, custos, barreira, commit e
rollback lógico, no release sob pin, descarte/reentry, duas janelas de closers,
conclusão atrasada de receive, interrupções e traceback salvo de receive/send.
Sockets locais reais: frame completo, EOF no corpo, cliente que não lê
(prefixo real incompleto), TLS com certificado verificado, envio multi-chunk
de 256 KiB e fechamento do peer durante 2 MiB detectado sem depender de timeout.

Medição complementar: frame de **16.777.216 bytes** criado antes do tracemalloc;
recepção real + cópia + validação com pico **< 2F + 524.288 bytes**; retenção
de um F até close, e **< 524.288 bytes no ponto de end_output**. Esse ponto
é instrumentado para comprovar descarte antes do unpin. Não prova commit do SO,
arenas, SSL/OpenSSL, buffers nativos/compartilhados ou ausência de debugger
guardando locals. O overhead continua custo declarado pelo coordenador confiável.

## 5. Gates finais medidos

Windows nativo, CPython **3.11.3** existente, sem recriar .venv:

| Seleção | Resultado |
|---|---|
| Novos pin/primitivas/receptor | **85 passed** (17/27/41), zero skips |
| Resultado, orçamento, snapshots, pureza e separação | **1.036 passed**, 45,09 s |
| Transporte/driver/bootstrap/listener/bind existentes selecionados | **306 passed**, 37,14 s |
| Ruff check/format | **238 arquivos**, aprovados |
| Mypy strict alvos 3.11 e 3.14 | **238 arquivos**, aprovados |

Cada seleção pytest final terminou com exit 0, zero falhas/erros/skips.
Não somar seleções sobrepostas como testes distintos. Mypy 3.14 é análise
estática executada no 3.11, não execução do receiver em CPython 3.14.
Suíte Python integral/PG16, browsers/frontend, runtime 3.14 e POSIX não foram
executados neste lote. Nenhum PostgreSQL, Docker ou banco existente foi tocado.

## 6. Pacotes — sonda limitada, não aplicação completa

Raiz temporária própria fora do checkout:
`%LOCALAPPDATA%/Temp/maskgw-receiver-package-20261020-b9b77bcb/`.
Build final em `final-v2`, sem isolamento/rede/instalação de dependências.
144 membros do sdist validados antes de extrair; wheel reconstruído do sdist
fora do checkout em `sdist-wheel-v2`. Cada wheel instalado em target novo com
`--no-index --no-deps`; dependências vêm do interpretador de teste existente.

`tests/result_receiver_package_probe.py` executado de cwd temporário com
`python -I -B`, sem PYTHONPATH. Conferiu que todos os módulos maskgw carregados
vieram do target instalado, não do checkout. Nos dois artefatos, sockets reais
provaram corpo válido enviado e job incorreto recusado, com retenção do pin até
close e release posterior da sessão. Hashes dos quatro módulos coincidem com
os arquivos finais, conferidos automaticamente no arquivo de distribuição e no
target instalado. Cada wheel tem 118 entradas; nenhuma de docs/tests/frontend,
.codex/.claude, stackdump ou systeminfo. Não é ambiente com dependências isoladas nem smoke de toda
a aplicação, PG16, UI, TLS instalado ou runtime moderno. Tentativas preliminares
de pacote anteriores ao último fix não são usadas como evidência do final.

| Artefato final | SHA-256 |
|---|---|
| wheel | `d02dfa3ec5a2e310694b2c09f3f2b43c2c508b30db6c8e7a82fa6e552298d847` |
| sdist | `4274398ae11328be634b91ab48d661d5dbad32b3d9483c6d1765135ddfaca4ca` |
| wheel reconstruído do sdist | `fb46959e0e62b8f0bea4065b4ea5bb7a6d561fa9cddbbadf18a45b70b84e81c9` |

Não há alegação de determinismo entre wheels. Builds só atualizaram saídas
ignoradas/metadata de empacotamento, sem alterar dependências ou .venv.

## 7. Fontes finais e estado

| Módulo | SHA-256 |
|---|---|
| pgwire/result_receiver.py | `730c6c8e2cf7f1df6b4ef0f02325e0927ddaa173cf0689eaba54e6eb4c652495` |
| pgwire/result_frame.py | `be0bf9bb6098431bb40fb08f576f416ee9607c3e3908639caf58e103d2a3c7ff` |
| pgwire/transport.py | `2ae86fe27b288d59d1f6d7e8c63113e1188152b14ec16ae664e4c07f64115444` |
| runtime/budget.py | `510ca741cac660afb33ce5ae97da2685f472ebcac36e90dc8cd94fd2dcf1ed7e` |

Claude2 revisou sem executar testes e sem bloqueador de código no escopo
interno; pediu os reforços de evidência e os três contratos da §3. O último
ajuste de timeout opaco e o fechamento documental foram conferidos na mesma
sessão: sem bloqueador técnico/documental para registrar somente este lote
interno sob a delegação vigente. Revisor não executou testes nem certificou
produção. Nenhuma aprovação individual de usuário é inventada.

Não houve commit, push, novo chamador operacional, SQL ou deploy. B-1 fim a
fim, B-2 (pai/worker/compartilhada/nativa/SSL), D-090 gate 2, compatibilidade
de IDEs, MCP multi-datasource e produção continuam pendentes.

Auditoria final do freeze: 296 → 303 arquivos selecionados, 13 alterados e
sete novos pertinentes, nenhum ausente. Fora desses 20, hashes anteriores
preservados, inclusive os lotes antigos, typing fix, snapshot/candidate, UI,
dependências e testes não abrangidos. .venv/pyvenv.cfg permanece idêntico.
HEAD/referência remota local/1 ahead não mudaram e não há index.lock.
