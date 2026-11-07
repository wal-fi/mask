# W1 Oracle — revisão do desenho do driver

2026-11-06. Decisões do revisor sob a delegação vigente, sem aprovação
individual inventada. CLI85542/90785 foram somente Read; CLI34291 escreveu
somente DRIVER-DESIGN. Todas encerraram0, terminais recuperados e zero
escritor confirmado antes da próxima chamada.

Root leu a v3 inteira, SHA-256
9e58a3ff6179cd0b88c74b6b69dab5d10714cbbea3234d6a709c8ac36356b58f,
contra APIs atuais de WorkerSession, ledger, codec, receiver, frame e guard.
Aceita sua direção **somente para os primeiros testes D1 sem efeitos**,
com as precisões obrigatórias abaixo. Não autoriza código do driver antes
de rever/medir/congelar o RED. Não autoriza execução física.

## Precisões para o contrato de teste

1. Há uma inconsistência na API v3: run(ports, pure=namespace) pressupõe
   carga anterior, mas o startup exige guard antes do loader. O contrato
   será run(ports), que cria Owner, aplica guard e só então chama
   load_pure(ports.reader). O reader entrega bytes limitados do path fixo.
   PURE_PATH/PURE_SHA/PURE_BYTES são constantes do driver, correspondentes
   ao núcleo4c155d76/22453bytes. Não há path/hash/tamanho substituíveis
   pela chamada operacional, nem namespace pronto que burle a ordem.
   O helper loader pode ser testado isoladamente com o reader fake.
2. O loader executa exatamente os bytes conferidos. Não reabre o arquivo
   depois do hash nem usa import de vizinho, sys.path ou PYTHONPATH.
   Importar o módulo do driver não chama run, não carrega o arquivo puro
   e não aplica guard. D1 contém definições, sem main ou bindings físicos.
3. Todas as portas de D1 são contratos internos confiáveis e precisam de
   assinaturas explícitas no cabeçalho do teste antes do módulo. Fonte de
   bytes, clock, host, factory, pares e threads são determinísticos, sem
   sockets/threads/processos reais. Callbacks de porta não são uma API
   contra código Python malicioso. Não se promete autenticar esse código.
4. Handle de thread é registrado antes de start. T4 faz transição interna
   ARMED, handoff, registra/inicia watcher e só então publica ARMED. O
   watcher confere STOP/case23/seq46 antes de stop e não muda a máquina;
   principal comita somente após join. A união de verdicts do driver com
   falhas da máquina inclui24 enquanto T5 estiver PENDING.
5. O sink usa EOF por resultado, limite incremental e deadline absoluto.
   Para imediatamente ao exceder cap, com sentinela cap+1. Não drena sem
   limite, não reaproveita o canal e não continua a rodada após divergência.
   Conteúdo esperado é só corpo D113; o header76 não chega ao sink.
6. A janela idle é um limite conservador para a próxima transferência,
   não prova de vida nem teto de todo o shutdown. A API pública
   send_result_to(channel) não recebe deadline; D2 terá de compor o stop
   do RawChannel e o prazo do sink com a janela do driver, sem mudar o
   timeout interno ou ler _idle_end. D1 testa essa exigência por porta
   explícita. Cleanup pode ultrapassar a janela sem autorizar outra query.
   A separação ACK/GO não reinicia um prazo agregado vencido.
7. DriverResult é finito, imutável e redigido. RETAINED mantém referência
   forte a Owner, tokens e todos os objetos/slots incertos; teste não faz
   hold infinito nem cria thread real que fique viva. D2 precisa impedir
   saída física que abandone recurso incerto. Não há confirmação de
   limpeza inferida de um booleano de porta sem os fatos do modelo.
8. Todo evento inclui e com nome fechado da tabela v3, chaves exatas e
   tipos exatos. Bool não substitui int. next_seq51 é somente metadado
   pós-GO50 no ARMED25; nenhum frame51. Nenhum SHA, canário, credencial,
   SQL ou texto de exceção entra nas linhas, reprs ou erros fechados.
   GuardFacts não tem campo threads: Threads1 é requisito verificado pelo
   guard, não atributo inventado. BudgetLedger.status é propriedade.
9. SessionKey é validada antes da factory: bytes exatos16, identidade e
   geração correspondentes ao snapshot, sem reutilizar ID entre as seis
   sessões do mesmo driver. A porta ids é determinística no D1 e será
   binding explícito no D2; não acrescenta campo ao LAB_INIT.

## Decisões prospectivas e aritmética

Dois binds RO fixos em lugar do bind único do plano antigo; puro e driver
separados. Nenhuma imagem ou fonte app124 muda por essa decisão. Só o
futuro inspect, com conjunto exato de binds/tmpfs e hashes, poderá admitir
uma execução. O script físico e seus bindings não existem.

Custos v3 aceitos como valores prospectivos, não prova de RSS/cgroup:
base128MiB, headroom64MiB, shared1MiB por geração, W256MiB, P33MiB,
total512MiB; duas gerações e uma sessão usam483MiB, sobram29MiB.
Root exercitou reserva/publicação G1/G2, adoção, pin2F+1MiB e recusa
CAPACITY da segunda sessão na API pública. Nenhum processo ou SO simulado
nesse cálculo. Dois erros do harness do revisor foram preservados:
status chamado como método e um rótulo que somou base/headroom duas vezes.
O número correto reservado já os inclui; nenhum defeito de produto.

## Próximo incremento e bloqueios

Mesmo Claude2/sessão51ea0d85/claude-opus-5-5/medium escreve SOMENTE
tests/test_oracle9_w1_driver.py. deploy/oracle9_w1_driver.py continua
ausente até root ler os oráculos, medir sanidades/RED e congelar. A
matriz D1-1..18 pode usar parametrização finita; contagem prevista não é
medição. Erros/falhas de ausência não provam comportamento.

Não modificar núcleo/teste4c155d76/084d62cd, source20, estado16, app124
ou tentativa consumida. Não há main, native, Docker, PG, SQL executado,
runtime/config/binário/privado, raiz/nonce/comando operacional ou deploy.
Sem segundo escritor, outra conta/modelo ou contorno de quota.

T5, gerador independente de expectativas, binding e retenção física D2,
ponte/fixture/recursos/frescor/prova de vida T6 e readmissão da candidata
continuam bloqueadores próprios antes de rodar. Nenhum B1/B2/D090/C1/
ingresso/produção foi fechado. SQL PGWire recusada; serviço indisponível.
