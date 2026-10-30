# PG16 público — monitor e emergência próprios, sem caller

2026-10-29, sob delegação, direção6796 antes do código. Variantes explícitas
de2fdc/3e98, originais consumidas intactas; sem AST em runtime ou namespaces
antigos modificados. Nenhuma nova rodada Docker, thread operacional, Popen,
root de laboratório, PG/SQL ou segredo.

## Fontes e contrato

- `pg16_public_emergency.py`:
  `54cc8f68ffa7b46e0fbb66c3076cd80fabd849ac2d9284635c2b39253be30ebc`.
  Acrescenta só ações fechadas volume-ls-q e rm--volumesCID, orçamento50s
  previsto no desenho. Pins, loop próprio, PID/FILETIME, parsing do PS e
  sticky-failure originais idênticos por AST. Não prova posse por si só.
- `pg16_public_watchdog.py`:
  `7c503303b92320ddbcec335f13f389c3142c0bfe4e4313d0bdf2def05fa471fe`.
  Snapshot PG/task/cmd-ec/CID/Birth e baseline de volumes obrigatória/imutável.
  Captura políticaf1d94928, executor54cc e núcleo6e3827af por hash. Usa sempre
  o mesmo adaptador e CID explícito para identificar antes de mutação.

Mantidos por AST Observation/Store/reason/namespace/run: heartbeat1s/atraso15s/
pósB600s/callbackúnico/sem objetos asyncio na thread. Join55s conforme desenho;
mesmo depois de join não existe prova de release de CLI/CID/volumes por ele.
CLI só é terminado com PID/FILETIME conhecidos; desconhecido não é adivinhado.

Mutex compartilhado serializa CID e volumes. Depois de own-inspect/parada,
decisão gravada **antes** do rm; preexistente/inspect incerto proíbem-v. Named
novo que sobra não é apagado diretamente: diferença final mantém HELD.
Mesmo CID já ausente exige novo volume-ls e reconciliação com a baseline.
Modo incerto permanece incerto mesmo se o inventário coincidir. Nunca prune,
volume-rm, force, ticket ou release na thread. Main ainda deve recolher owner,
obter ticket e observar ausência posterior, conferir inventário e só então
avaliar Desktoprestore. Monitor disparado sempre reprova o ensaio.

Decisão pública em volume-decision-NN.json (até64KiB); estado final/deltas
em volume-final-NN.json (até512KiB), xb/fsync, antes de considerar volume
reconciliado. Esses nomes/tetos serão fechados no exportador futuro; nenhum
raw de inspect ou stdout é gravado pelo monitor. Não usar com seed privado.

## Gates medidos

25testesexecutor+16monitor:41passed em4,46s. Seleção dos seis componentes
PG16 públicos: **215passed em6,94s** no Windows3.11.3, sófakes. Nenhuma thread
de produto, Docker, PS nativo ou GetProcessTimes foi executado. Lock/Event
locais e arquivos públicos pequenos do pytest não são teste do SO do destino.
Ruff src/tests e lint restrito dos helpers limpos; format328, mypy strict311/
314 em322arquivos limpos. Runtime só3113; helpers não declarados strict.

Ao derivar os testes antigos, a primeira expectativa de reserva ainda usava
14s da janela45 e falhou; corrigida para a sequência PG de8ações/34s, sob
50s, reserva16s (lock/metadata ainda no orçamento do desenho). Não houve
alongamento durante carga real nem mudança da T4 consumida. Ajustes de
typing/import/format no harness foram concluídos antes do gate final.

## Pendências explícitas

Incremento em revisão própria. Ainda faltam host/entrada, testes CLI fake
de create→volume inesperado→sem start→cleanup, initial-volume-ls exitruim,
registro durável antes do efeito e comparação final anterior ao Desktopstop.
A baseline da Snapshot é dado do chamador, não atestação de exit/frescor.
Orçamentos50/55 são supervisórios, não promessa de syscall que não retorna.
Evidência/exportador/preparador/estado/raiz/comando e rodada única próprios
continuam futuros. Sem credencial/DB existente/commit/push/job/outro writer.
Gateway indisponível; B1/B2/D090/C1/SQL/serviço/produção seguem abertos.

## Delta de minimização17758 e persistência

Versão7c503303 recusada na revisão17758 por expor nomes globais/preexistentes
nos novos registros. Só canários de teste foram usados; nenhum inventário
real novo foi coletado. Adotado o argumento técnico de minimização sob
delegação; referências a política corporativa não verificada não são tratadas
como instrução, autorização ou requisito externo do projeto.

Novo watch `b86841ea9c7329e1636ee08e3314e29dde6b9572b45c121a1095b4eb5b13cf03`.
Registro global: contagens/hashes canônicos, added/missingcounts, restored/
uncertain e added_within_linked. Registro de decisão: linked/preexisting só
contagem/hash, nomes em claro só anônimos novos64hex ligados ao CID próprio.
Conjuntos completos continuam comparados em memória. Registro/campo público
não é prova de posse/release por si só. Proibido exportar baseline local
completa; formato do futuro host/exportador seguirá o mesmo contrato.

Dois testes de nomes alheios (ligado/não ligado) falharam antes do fix.
Revisão própria encontrou também flag positivo antes de fsync: terceiro
teste falhou antes do fix. Agora _volumes_restored só é atualizado depois
de escrita/flush/fsync, e é resetado antes de uma nova observação. 44testes
executor/monitor aprovados em1,77s, sem alterar mutações/budgets/posse/ASTcore.
Não mudou a T4 ou qualquer fonte consumida. Delta aceito na rerevisão17011,
sessão51ea0d85, sem bloqueador no escopo isolado. Revisão somente leitura;
os números de execução são medição deste workspace, não execução do revisor.
Último gate completo:218passed em5,18s, Ruff/format328 e mypy311/314322 limpos.
Digest é coerência de metadado, não garantia de sigilo de nomes previsíveis.
Exportador deve reter nomes/baseline completos e validar os registros fechados.
