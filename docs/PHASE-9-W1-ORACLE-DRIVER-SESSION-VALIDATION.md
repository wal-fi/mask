# W1 Oracle — validação da integração SDK e owner do chamador

2026-11-09, São Paulo. Claude2 foi o único programador, sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, modelo claude-opus-5-5, esforço medium.
Root revisou, executou os gates e escreveu esta evidência sob a delegação
vigente. Nenhuma aprovação individual do usuário foi inventada.

## Parecer e fronteira

Aceito somente este incremento: WorkerSession pública real integrada ao
driver por SO inteiramente simulado, mais owner externo exato e de uso único.
Não há novo main, binding físico, mount, worker real, consulta, serviço ou
deploy. B1 fim a fim, B2, D090gate2, C1, T5 e produção continuam abertos.

| Arquivo | SHA-256 | Bytes / linhas |
|---|---|---|
| deploy/oracle9_w1_driver.py | 39a6890457c3bc9331fc371948fce896cbbc37e2d49f1584a5629490f43d2794 | 36956 / 1043 |
| tests/test_oracle9_w1_driver_session.py | 585540afafdc10b5f8a201770ff2fc1c33fd5f36219dc18907b1626498692bc7 | 45030 / 1266 |

Base de partida publicada: 5708b8f37111a4ae67e34e6e3de314f2c77f9a78.
Os 114 testes D1 antigos permanecem exatamente em 0e9a8cc1. Os 23 arquivos
upstream protegidos e os 124 insumos públicos da aplicação permanecem
iguais por SHA-256 e tamanho. Só o driver foi emendado após RED medido;
estado16 e tentativa consumida não foram alterados ou reutilizados.

## Contrato exercitado

- Factory gravadora devolve a classe WorkerSession real usando o ledger,
  token, chave, limites, perfil e guard recebidos do driver.
- Clock comum para driver, idle do SDK e todos os ResultDeadline, com troca
  somente dos namespaces do módulo SDK, sem mutação global da stdlib.
- SecretInit, snapshot, nonce/HMAC e identidade de frame/DONE conferidos.
  Saída por RawChannel exato sobre socket fake, só corpo sem header76.
- Pin ligado antes de leitura D113 e durante envio, desligado depois.
  P=33MiB-1 recusa na query após apenas o header de controle RESULT12,
  sem leitura D113 ou exposição. Identidade ou DONE inválidos não expõem.
- Driver roda dois resultados pelo SDK real, recebe EOF no GO3 e fecha
  coerentemente a sessão. Os bytes são sintéticos: não provam masking/PG.
- run(ports, *, owner=None) preserva a compatibilidade sem owner. Owner
  fornecido exige tipo exato deste namespace, sete campos conhecidos,
  latch bool False exato, referências None e listas exatas vazias.
  Recusa antes de qualquer porta, sem reset ou substituição.
- A trava é marcada antes do guard. RETAINED mantém o mesmo objeto.
  KeyboardInterrupt/SystemExit fora do SDK escapam com owner e recursos
  já registrados retidos pelo chamador. Dentro do SDK, controle é erro
  fechado de sessão; não se alega preservar a exceção original.
- Recusa OWNER tem args fechados, sem cause/context, inclusive dentro de
  um except ativo do chamador. Contexto é removido, não apenas ocultado.

Root leu o teste inicial inteiro e todos os deltas. Os 17 nomes de função
de teste iniciais e suas parametrizações foram preservados. A regressão
S8 foi anexada preservando todos os bytes e a AST do prefixo de 29 casos.
AST confirmou métodos/propriedades/repr originais de Owner intactos,
prefixo do construtor intacto e fluxo de run após a aquisição do owner
igual; todas as demais definições antigas permaneceram iguais.

## RED, correções e histórico real

1. CLI43145 entregou b38ab0cf, 40099 bytes/1137 linhas. Root leu tudo:
   RED28 com 11 aprovados/17 falhas, 1,27s. Ruff/format passaram; mypy
   reprovou acesso a nome de módulo não exportado e narrowing obsoleto.
   A observação parcial de 40045 bytes foi feita antes do término da
   gravação; foi corrigida nos metadados, sem alterar o arquivo arquivado,
   seu SHA b38ab0cf ou resultados.
2. CLI43934 fortaleceu a recusa para observar toda porta e o estado HELD
   do ledger; preservou casos anteriores. RED29:12/17 em1,45s. Mypy ainda
   detectava narrowing do pin; esse resultado reprovado foi preservado.
3. CLI64135 corrigiu só a leitura tipada do pin. Teste104086c9 congelado:
   RED29:12/17 em1,41s, Ruff/format/mypy311/314 aprovados antes da fonte.
4. CLI66525 criou candidata b3a412bf com propriedades de Owner aninhadas
   por engano em _claim. Root rejeitou ao ler o delta e confirmou por AST:
   matriz143 com131 aprovados/12 falhas,2,45s. Candidata e RED preservados;
   nenhum teste foi enfraquecido para aceitá-la.
5. CLI23351 reposicionou o bloco, restaurando os métodos antigos. Fonte
   f8e884a2 passou143 em1,43s e estáticos. Root ainda rejeitou publicação:
   sonda reproduziu __context__ apontando para exceção ativa do chamador.
6. CLI34650 anexou seis regressões S8; teste585540af congelado. RED35:
   29 aprovados/6 falhas em1,42s, exatamente em __context__, com Ruff,
   format e mypy311/314 aprovados, fontef8 fixa.
7. CLI12000 corrigiu somente o ramo de recusa em _claim: captura local da
   DriverRefusal gerada ali, zera __context__/__cause__ e relança a mesma
   exceção. Não captura controles das portas nem altera sua semântica.
   Root leu todo o delta antes dos gates finais.

Todos os terminais foram recuperados e encerraram0 antes da chamada
seguinte; zero escritor confirmado. Não houve nova sessão, conta,
modelo, subagente, contorno de quota ou tarefa de retomada neste lote.

## Gates finais medidos

| Gate | Resultado |
|---|---|
| Testes próprios | 35 aprovados,0,49s |
| Matriz relacionada de dez arquivos, incluindo os próprios | 1109 aprovados,9,17s |
| Falhas / erros / skips / xfail | 0 / 0 / 0 / 0 |
| Ruff src/tests | aprovado |
| Format src/tests | 360 arquivos conformes |
| Mypy strict src/tests, alvos3.11 e3.14 | 360 arquivos, aprovado em ambos |
| Lint fonte deploy E9,F63,F7,F82 | aprovado |
| Format driver e teste novo | 2 conformes |

Runtime Windows CPython3.11.3. Python3.14 foi somente alvo estático.
Deploy não integra mypy src/tests: não se declara mypy do driver.

Matriz exata: test_oracle9_w1_driver_session.py, test_oracle9_w1_driver.py,
test_oracle9_w1_controller.py, test_oracle9_w1_update.py,
test_oracle9_w1_context.py, test_oracle9_cycle_freshness.py,
test_runtime_snapshot.py, test_worker_protocol.py,
test_datasource_destination_review.py e test_sql_validator.py.

Escopo proporcional, não suíte integral: o arquivo antigo worker_session
contém um teste que inicia thread real, e as suítes result_receiver/frame
também têm IO físico/processo. Não foram incluídos neste lote de SO fake.
Nenhum caso foi marcado skip/xfail ou deselecionado para esconder falha.
O SDK/receiver real foi exercitado pelos testes novos sobre fakes.

Root conferiu 22 estados inválidos adicionais, incluindo objeto não
inicializado, campo ausente/extra, valor estrangeiro, subclasse de lista/
dict e chave estrangeira: recusas sem callbacks dos valores ou operações
de porta. owner=None explícito e contexto do chamador agora também passam.
A primeira sonda teve erro de montagem do revisor ao inserir uma chave de
hash colidente; ocorreu antes de run. A montagem foi corrigida e o fato
está registrado em independent-owner-probes.json, não como defeito de produto.

## Limites preservados e próximo incremento

O ramo condicional de coerência HELD confere estado, slot, epoch e reserva
antes/depois de close; foi revisto, mas uma sonda de perfil confirmou zero
entradas nele em I1-7 nesta matriz. Não se alega que a matriz forçou
incerteza física ou demonstrou cleanup/hold nativos. Nenhum teste avança
o clock além do idle; vida real, sinais, concorrência e tempo físico ainda
precisam de provas próprias.

Nenhuma imagem ou pacote da aplicação mudou; Node/browsers, PG integral,
wheel/sdist e readmissão da candidata não foram repetidos. A equivalência
dos 124 insumos não substitui readmissão operacional futura.

Próximo: desenho do main/bindings D2, MainRoot com owner e slots retidos,
regras de saída, sinais/hold e terceiro script RO fixado antes de código
ou efeitos. O desenho de07/11 continua referência prospectiva desse main.
Oracle Linux9.8 local permanece destino aceito; não houve deploy.
T5, gerador de expectativas, ponte/fixture/frescor, readmissão e todos os
gates de produto permanecem separados e abertos. SQL PGWire segue recusada.

Dados, logs/JUnit, testes congelados, candidata rejeitada, sondas e revisão
estão em docs/poc/evidence/oracle9-w1-driver-session-review-20261109/.
Os logs gerados pelo PowerShell5 eram UTF16LE/BOM. Foram convertidos sem
perda para UTF8, sem mudar conteúdo ou newlines; hashes originais e regra
de reconstrução byte a byte, conferida por round-trip, estão em
log-encoding-normalization.json. Código/testes e resultados não mudaram.
O layout dos textos foi normalizado para LF sem whitespace final para
o check Git padrão. Os bytes anteriores exatos dos JSON/XML/logs afetados
ficam preservados em base64, com hashes e regra de transformação, em
text-layout-originals.json; snapshots de fontes/testes não mudaram.
