# T4 pública — rodada única reprovada, recursos restaurados

2026-10-28. **NOT_PASSED, exit1**. Não repetir main/root consumidos nem ajustar
esta evidência retroativamente. Não houve attach/start do canário, entrega
de seed, PG, SQL ou credencial. Gateway permanece indisponível.

## Insumos e execução

Host88e220eb, entry835c2e21, preparadorc7892639 e proposta2 foram aceitos pelo
Claude2 antes da materialização e comando. RootTemp
`maskgw-oracle9-t4-20261028-86e5417cd7958015ace880173d138553`,
task52cdd3407a6bcc71f77d8d2610c59e5c. EstadoFRESH2254bytes/SHA26548003 foi
materializado uma vez e comparado byte a byte com a proposta, só attempt.json
na raiz, comando igual. Script6ddb78bf invocado uma vez17:53:03.7936399Z.
Desktop Off antes. Nenhuma mudança/CLI manual ou segundo escritor em paralelo.

Janela herdada:12checkpoints xb, replay B_CONSUMED, A→B121360ms, cabeça
10d5cba0e37fba90089a404a8714f264300b15c282aa77af96c6b45a74c4f770
igual à registrada no result. Imagem621/config exatos passaram no preflight.

## Falha e limites da atribuição

create-normal confirmou CID
94d9d33a7f3ef7dd93a6ad52e7c053f6a4954164a1cf4b7f10a0ac9989d269d2.
inspect-normal retornou exit0/31711bytes, SHA
3cece26457746bf9ceaf48319d2236ccb44652dba74101e5e68104b30dc3809f.
A validação seguinte falhou antes de ManagedBootstrap ser construído.
Nenhum caso concluído, sem cases.json nem normal-inspect-before.json.

**Lacuna de diagnóstico:** esse raw de inspect não foi persistido. O helper
salvava inspect-before só depois de validar. Category externa ficou FAILED;
não é possível atribuir agora a falha a um campo específico desse raw.
Não reconstruir JSON a partir do hash nem declarar label/StdinOnce como causa.
É necessário desenho de diagnóstico público separado que capture a admissão
antes de validá-la, sem afrouxar regras ou repetir a rodada consumida.

## Coleta e restauração medidas

28comandos registrados, todos exit0 (13DockerCLI/15PS registrados; as
amostras do helper de relógio são separadas). Inspect de cleanup próprio,
rm-normal semforce, ausência por CID e inventário final vazios confirmados.
Registro removedtrue/create_uncertainfalse. Sem owner/attach, não houve
ticket de transporte nem alegação de teste real de PipeHandle nesta rodada.
Watchdog firedfalse/heldfalse/thread_joinedtrue; tarefas recolhidas permitiram
encerrar normalmente. owned_cleanup/inventory_restored/inputs_unchangedtrue.
Desktop stop13,469s/exit0, after-stop-0 vazio, OFF_CONFIRMED; relido depois
sem processo correspondente, sem DockerCLI extra. Não resta recurso próprio.

## Transporte imutável

`docs/poc/evidence/oracle9-t4-run-20261028/`:24arquivos da raiz/37910bytes,
SHA do transport.json0566dd402ee27b5419387c8196f84d68b94188ad99766a8084aadfa9bedf50ab.
Todos hashes/tamanhos e releitura final da origem conferidos. console.txt
é suplemento da saída do comando, não um arquivo inventado na raiz.
Proposta1 rejeitada e proposta2 aceita preservadas separadamente; estado
attempt agoraABORTED na raiz consumida, não editar/reusar.

## Próximo gate

Revisão somente leitura destes fatos e da lacuna; depois desenho de diagnóstico
create/inspect público, sem start/attach/seed, com código/comando próprios e
captura antes da validação. Fonte consumida88e2/835c/c789 permanece congelada.
Sem nova rodada, alteração de perfil, relaxamento de prazo ou inferência de
sucesso. B-1/B-2/D-090/C1/SQL/PG/produção seguem abertos.
