# W1 Oracle — revisão do desenho T5

2026-11-09, sob delegação vigente, sem atribuir aprovação individual ao
usuário. Base `9748d2b`. Claude2 foi o único autor do desenho, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço `medium`.
Root revisou, sem escrever código funcional ou executar o desenho.

## Parecer

V3 aceita como direção técnica **somente para preparar os testes com fakes
do driver**. SHA-256:
`5eb14030f7100af00ad280681703c48d448a376833b01bc4620d06efdcc8173d`,
22.567 bytes, 330 linhas. Root leu as 250 linhas da v1, todas as 303 da v2
e o delta completo final. Não há teste novo, RED ou sonda implementada.

O próximo arquivo de teste será `tests/test_oracle9_w1_driver_t5.py`.
Os oráculos serão lidos e o RED medido/congelado antes de qualquer mudança
do driver. Migrações dos testes antigos ficam restritas à lista expressa
do desenho; não autorizam apagar cenários ou enfraquecer outras asserções.
Não publicar uma integração parcial com o pin do main incompatível: o
driver e o binding do main exigem seus gates conjuntos antes de anunciar
integração concluída. Nenhuma etapa física está autorizada por este parecer.

## Findings corrigidos no contrato

1. **Cerca EOF/idle:** timestamp posterior ao retorno de envio/fechamento
   podia adiar a cerca e aceitar exit0 por idle. A v3 usa o instante anterior
   a `write_all`, que precede necessariamente o EOF do stdin e o início do
   idle. A cerca é um limite inferior conservador do fim do idle, nunca
   ampliada por retorno tardio. A premissa de relógio comum continua nativa
   e não medida. O traço lógico arquivado em review-v1 não é prova de SO.
2. **Prazo da espera:** sucesso exige retorno antes de `wait_end` capturado
   uma vez e antes da cerca de idle. WAIT_LATE é distinto de EXIT_LATE.
   Abertura confere seu prazo antes/depois dos retornos; não se promete
   interromper chamada arbitrária bloqueada no kernel.
3. **Posse do stdin:** pipe explícito antes do Popen, com quatro pontas
   conhecidas enraizadas e processo reservado UNKNOWN. `stdin` recebe o
   leitor já possuído; o escritor não entra em `pass_fds`. Resíduos internos
   do Popen são declarados, sem inventar posse. Fechamento incerto ou
   aquisição interrompida retém os recursos e impede saída segura.
4. **Fronteira de confiança:** interface sem send é um contrato do binding
   confiável, não impossibilidade física nem sandbox contra Python hostil.
5. **Identidade e créditos:** SessionKey nova, id exato16 e único, G2,
   datasource/revisão pinados; nonce exato32 separado. Token no owner antes
   do adopt, sob ledger/lock originais. Recursos confirmadamente fechados
   podem sair; retenção preserva os originais ainda não resolvidos.
6. **Binding Linux:** `pipe2` por wrapper preguiçoso, como os bindings
   existentes. Import e `real_system()` continuam sem procurar símbolo
   Linux ausente no Windows. Encaminhamento por AST; testes de efeitos
   somente com `System` fake. Não criar skip ou patch global da stdlib.

Exit0 só pode ser candidato a PASS após GUARD/OPENED válidos, fechamento
da ponta do pai e reap no prazo conservador. Kill é sempre fallback de
limpeza e nunca converte o caso em PASS. Quatro pontas e processo são
recursos distintos; créditos só voltam com fatos completos. O main futuro
terá 22 campos de System e 10 slots; o driver, nove portas. Isso é contrato
prospectivo, não mudança aplicada ou verificação física.

## Execuções e validação desta rodada

CLI13267,14897 e43658 terminaram0 e foram recuperadas antes da chamada
seguinte. Marcadores da primeira execução confirmaram sessão/modelo/esforço
e ferramentas Read/Edit/Write; as três chamadas fixaram os mesmos flags.
Guardas posteriores confirmaram zero escritores da tarefa. Nenhuma chamada
de Antigravity ou outro programador ocorreu neste lote.

Protegidos27, app124 e EXPECT fonte/teste permanecem intactos por tamanho
e SHA. Não houve mudança de SDK, driver, main, núcleo puro, teste existente
ou estado16/tentativa consumida. Não se repetiram suítes por alteração
exclusivamente documental; os 704 testes EXPECT são medição histórica do
lote anterior, não evidência nova de T5. `git diff --check` integra o
fechamento documental.

Retomada de 21h55UTC executou com resultado0, mensagem recebida nesta mesma
conversa e tarefa sem próximo disparo. Isso comprova essa entrega, não uma
liberação permanente de cota. Não houve429 nas três chamadas de desenho,
novo agendamento, segundo escritor ou contorno de quota/permissão.

## Limites preservados

Nada de sockets, threads, processos, sinais, guard ou controle nativo do
produto, Docker, PG, SQL, leitura de runtime/configuração privada/binário,
root operacional, nonce real, deployment ou readmissão. A observação local
de ausência do atributo público `os.pipe2` não invocou a função nativa.

Todos os testes listados no desenho são planejados. Não demonstram EOF do
kernel, herança, close-on-exec, waitpid/returncode, ambiente/guard do worker
instalado, relógio comum ou fechamento dos backends. T5 continua
**BLOCK_NATIVE**, obrigatório antes do laboratório completo. B1 fim a fim,
B2, D-090 gate2, C1, ingressos, IDE, MCP e produção seguem abertos;
o Gateway permanece indisponível.

Evidência em `docs/poc/evidence/oracle9-w1-t5-design-review-20261109/`:
snapshots rejeitados e findings originais, respostas finais dos agentes,
delta V3 e integridade final. Não reescrever o histórico vermelho como
aprovação da primeira proposta.
