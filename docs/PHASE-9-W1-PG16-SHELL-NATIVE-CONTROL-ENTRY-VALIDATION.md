# Entrada privada dos controles — revisão e fakes

Data:2026-11-02, America/Sao_Paulo. Base:0b2ddab7163f983b39823e1164dc43317ac9132e,
reconfirmada por fetch no início do lote. Claude2 foi o único programador,
sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, sempre claude-opus-5-5/esforço
medium. Root revisou, executou gates, guardou dados de revisão e documentou.
Escolhas sob delegação geral, sem inventar aprovação individual do usuário.

## 1. Desenho e limite do incremento

Lidos PENDING e CHECKPOINT primeiro; Git sincronizado, árvore rastreada limpa
e zero Claude CLI antes de iniciar. CLI32201 propôs uma entrada pequena,
mas sua alternativa de sair em HELD foi rejeitada: descartar o processo
descarta também o registro de posse e admite resíduo não observado fora do
job. O timeout externo de600s para matar o controlador também foi rejeitado.
Nenhuma dessas alternativas chegou a uma implementação operacional.

CLI78683 releu trechos de backend/host e revisou o plano para estacionamento
foreground, sem retry, cleanup ou saída automática com posse retida/incerta.
CLI39981 escreveu somente ENTRY-DESIGN. Root reforçou a proteção de S2–S5,
reserva antes de run, rechecagem de saída, estacionamento pegajoso e testes
de referências sem weakref em dict/list exatos. Documentação primária está
citada no desenho; foi consultada pelo revisor, não pelo programador.

CLI30611 escreveu primeiro testes, depois a entrada e notas. A nova CLI é
privada em docs/poc; não existe integração com produto, MCP ou Admin HTTP.
Nunca se executou o arquivo como controlador nem se chamou o runner real.
main foi exercitado somente com namespace/runner falsos em caminhos finitos.
Nenhum laço estacionado real, handler de sinal real, WinDLL ou Job Object.

Somente Read/Edit/Write com escopos explícitos foram disponibilizados ao
programador. Antes de cada chamada foi conferida a ausência de escritor;
respostas terminais foram recolhidas antes de novas chamadas. Não houve
outra conta/modelo, quota/reset observado ou tarefa nova. A tarefa histórica
foi relida Disabled, sem próximo horário; última execução continua sendo
01/11 às21h24m15Z/result0, não uma retomada nova em02/11.

## 2. Contrato que foi revisado

- S0/S1 são recusas puras antes do namespace. A partir de S2, só um registro
  original de tipo list exato, ainda identificado em N e vazio, permite sair.
  Registro substituído, malformado, retido ou desconhecido estaciona.
- Namespace e lista original ficam referenciados em KEEP antes de run. A
  interrupção original fica no progresso antes de registro falível. Nenhuma
  etapa libera owner ou chama método de cleanup; o lifecycle fica no runner.
- Reserva attempted precede a única chamada. Passagem interrompida não é
  retomada como fluxo normal; estado incerto segue para decisão. Não há retry.
- decide/settle/cycle são finitos. O driver e o hold infinitos são analisados
  por estrutura; não se executam em estado retido nos testes. PARK é pegajoso
  e retorno inesperado de auxiliar não autoriza exit0/None com recursos.
- O par controller/parent exige tuple de dois int exatos, positivos, abaixo
  de2**32 e distintos, antes de handlers, IDENTITY ou run. PIDs são só locais
  no pipe e não são persistidos como evidência.
- O descritor exige rótulos str exatos antes de comparação; igualdade hostil
  não é chamada. A entrada não duplica a validação do transporte do runner.
- Só eventos fechados IDENTITY/FINAL/PARKED, sem caminhos, valores de ambiente,
  texto/tipo de exceção ou PIDs de filhos. Após o runner não há I/O explícito
  de arquivos nem formatação de traceback. O procedimento futuro exige pipe
  de stdout, sem redirecionar para arquivo; a entrada não verifica esse tipo.
- SIGINT/SIGBREAK são instalados somente antes dos efeitos da chamada.
  Durante run levantam KeyboardInterrupt; inativos não escrevem nem contam.
  Entrega nativa, console close e sobrevivência a término externo não foram
  medidas ou prometidas. A entrada não tem recuperação de HELD.

## 3. Baseline rejeitada e regressões antes do fix

Entrada a3620eba/14018bytes e testes2024abc9/26008bytes:65passed/0,65s,exit0.
Mypy345 alvo3.11 passou; Ruff tinha3 erros e format recusava1 arquivo.
Contraprovas independentes finitas:3failed/0,20s,exit1:

1. P1: KEEP.append com falha de alocação substituía a interrupção original;
   o registrador de falhas também levantava fora da proteção do driver,
   permitindo saída com um owner falso retido. Observado MemoryError,
   parkedFalse e original não registrada. Nenhum owner ou processo real.
2. P2: identidade inválida (None,-1) emitia IDENTITY e alcançava o runner falso,
   terminando com decisão APPROVED.
3. P2: scope/admission_3s com objeto de igualdade permissiva eram aceitos.

Os bytes rejeitados foram preservados como base64/manifesto em
docs/poc/evidence/native-entry-review-20261102. CLI64875 anexou regressões e
notas, sem editar a entrada. Root confirmou SHA a3620eba intacto e prefixo
exato dos65 testes anteriores. Medição antes de liberar o fix:
**22failed/74passed/0,84s,exit1**. Testes32c41142/33498bytes preservados.

Foi usado o relatório efêmero fechado pytest_runtest_makereport do revisor,
que não inspeciona traceback enquanto o fixture proíbe leitura de runtime.
Ele mantém resultado das asserções, tipos e nodeids; nenhum ban foi relaxado.

CLI64387 corrigiu os três caminhos e o estilo dos testes, sem retirar casos:
captura da original antes do append protegido; _fault não levanta e o caller
também o protege; passagem incerta nunca repete run; identidade validada antes
dos efeitos; str exato antes da comparação. O teste parametrizado de seis
argumentos agrupou os três valores esperados, preservando casos/assertivas.

## 4. Gates finais

Runtime confirmado por metadados: Windows, CPython3.11.3. Alvo3.14 só estático.

| Gate | Resultado |
|---|---|
| Próprios da entrada | 96passed/0,92s,exit0 |
| Três contraprovas independentes | CLEAN,3passed/0,24s,exit0 |
| Relacionados21arquivos, bytes finais | 1071passed/298,76s,exit0;zero falhas/skips |
| Ruff em src/tests | Aprovado |
| PoC, lint restrito E9/F63/F7/F82 | Aprovado |
| Formatação em src/tests e10PoCs explícitos | 355 arquivos conformes |
| Mypy alvo3.11 em src/tests | 345 arquivos,sem erros |
| Mypy alvo3.14 em src/tests | 345 arquivos,sem erros |

Na repetição do probe P1, o caminho finito avança e passa por settle quando
o registro não escapa, observando o PARK que o driver aplicaria; nunca chama
o laço real. A original permaneceu no progresso e o owner falso ficou retido.
Identidade inválida gerou ENTRY_ARM sem run; rótulos hostis geraram ENTRY_RESULT.

Depois dos96 e probes, restava um assert com quebra recusada pelo formatter.
Uma chamada Claude2 restrita ao teste juntou só essa linha. AST completo
continuou idêntico (SHA e578582b…) e a fonte permaneceu356d2291. Format passou;
a matriz relacionada inclui os96 casos e roda sobre os bytes posteriores.
Não se repetiu a própria só por whitespace. Nenhum skip/xfail, supressão,
dependência ou configuração foi alterado para aprovar gates.

Fixture impede WinDLL, Popen, os.system, Thread.start, signal.signal real,
criação de diretórios e leituras sob .venv. O carregador real foi testado só
para ler/executar definições do runner pinado; run nunca foi chamado ali.
Os relacionados são os20 arquivos do runner mais o novo teste de entrada.

Produto/src/frontend/dependências não mudaram; sem Node/browser, wheel/sdist,
PostgreSQL ou suíte integral de produto neste lote. O PoC não é aplicação
instalada nem superfície operacional do Gateway. Ferramentas fazem seus
imports normais; não se promete ausência de leituras implícitas do Python.

## 5. Pins, dados e limites

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| docs/poc/pg16_shell_native_control_entry.py | 15580 | 356d22914c21c7fefb195b9471b12591cd7120deb152524104ff3b4559fbf0c6 |
| tests/test_pg16_shell_native_control_entry.py | 33379 | 1d65de063839bf8a108d13b7d9918c98ca60ec637518faad6f473b2155418f95 |

Os5 arquivos de revisão têm tamanho/SHA dos bytes decodificados conferidos.
Dados rejeitados/vermelhos não são scripts operacionais para executar.
Runnerb4198fe1, adaptereaebedd6, backend10c9058f e hostdfcc4ed6 reconferidos
intactos. Estado aceito de16campos e fontes/raízes consumidas continuam fixos.

Limitações explícitas: uma regressão num caminho positivo de main pode
estacionar o processo de testes; não há timeout automático comprovado, nem
teste de hold real. Unidades finitas e checks estruturais não certificam
entrega de sinais, vida do processo ou Job Objects. Término do app/sessão,
logoff, reboot, kill externo e falha fatal do Python são FAILED/UNKNOWN.

FINAL pode ter sido emitido antes de uma rechecagem que resulte em PARK,
sem segunda linha; o observador não pode deduzir cleanup só da linha emitida.
Pré-namespace segue comportamento padrão para interrupção. A relação entre
redirecionador da venv e Python base não foi medida. Permanecem limites
herdados: segunda interrupção no terminate do backend; auditoria512;
pin do launcher não atômico e leituras implícitas do runtime na partida.

Parecer aprovado somente para esta entrada privada simulada, sem P1/P2
remanescentes nesta revisão. Procedimento, comando/nonce/raiz operacional,
sonda de identidade e controles reais continuam posteriores à revisão própria.
Native3s NOT_MEASURED, entry_gate NOT_EVALUATED; Gateway indisponível e
B1/B2/D090gate2/C1/SQL/produção abertos. Nenhum banco/credencial antigo usado.
