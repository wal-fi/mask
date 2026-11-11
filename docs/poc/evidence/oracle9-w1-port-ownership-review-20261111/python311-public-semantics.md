# Semânticas públicas consultadas para o desenho

Root consultou a documentação oficial em2026-11-11. As páginas atuais
mostram Python3.11.18; não certificam o CPython3.11.3 instalado nem seus
binários/handles. Nenhum runtime/config/binário local foi lido para isto.

- Subprocessos em Windows requerem Proactor. `limit` controla o buffer do
  StreamReader. Esperar o processo com pipes sem drenar pode bloquear.
  `communicate` reúne envio/leitura/espera e pode ignorar erro de pipe no
  envio. Não o usar para o protocolo duplex limitado já aprovado.
  [Python: subprocesses](https://docs.python.org/3.11/library/asyncio-subprocess.html)
- `StreamWriter.write` pode encaminhar ao buffer interno; `drain` regula
  fluxo por watermarks. `is_closing` inclui fechamento em andamento;
  `wait_closed` aguarda fechamento da conexão. A revisão infere que isso
  não demonstra ausência do container ou quietude de helpers. O desenho
  deve definir exatamente o handoff local que chama SENT, sem convertê-lo
  em ack remoto ou em prova física de liberação.
  [Python: streams](https://docs.python.org/3.11/library/asyncio-stream.html)
- O callback de saída do processo pode preceder callbacks de dados ou de
  fechamento dos pipes. A revisão exige fatos separados e ligados ao
  owner correto; não deduzir todos os encerramentos só desse evento.
  [Python: subprocess protocols](https://docs.python.org/3.11/library/asyncio-protocol.html#asyncio.SubprocessProtocol.process_exited)

Estas são referências de contrato, não código/experimento nativo. Qualquer
pin/perfil, admissão e prova física permanece NOT_PREPARED neste lote.

Revisão V1: as mesmas páginas documentam o tamanho do buffer como dado de
flow-control, não um atestado de handles encerrados. SubprocessTransport.close
pode matar subprocesso ainda vivo e fechar pipes: eventual recuperação tem
de ser explícita e por identidade, não um finalizador oculto.
[Transportes](https://docs.python.org/3.11/library/asyncio-protocol.html)

O loop pode usar task factory customizada; get_task_factory informa se é
a padrão. Logo a reserva/arm não pode assumir comportamento preguiçoso só
pelo tipo Proactor. Loop e política precisam de precondições verificáveis.
[Event loop](https://docs.python.org/3.11/library/asyncio-eventloop.html#asyncio.loop.set_task_factory)
