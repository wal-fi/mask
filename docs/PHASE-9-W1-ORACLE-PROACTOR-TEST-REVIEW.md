# W1 Oracle: revisão dos primeiros oráculos Proactor

## V2 revista e RED135 congelado localmente — 2026-11-13

Root recuperou o resultado terminal da V2: exit0/success, mesma sessão,
modelo e esforço, sem denials. Zero escritores Claude2/AGY confirmado por
metadados em13/11 às14h19UTC. Não é uma observação de reset de quota.

Depois de ler toda a V1 (2855linhas), root leu TODOS os deltas da V2;
220nós de função/método inalterados foram conferidos por AST. T1–T4
resolvidos: precedência dos controles do waiter; primeiro ident válido
sem referência global; snapshot durante a drenagem inicial; lint.
Ruff format foi aplicado mecanicamente com AST idêntica, sem mudar
oráculos. V2 final:36b2ba548da0966736123f6bfbd05c8c39af3e0d9e33e79e1797d32f07dcf150,
113465bytes/2973linhas/67funções de teste.

- SDK falso:9sanidades PASS. A MESMA sondagem independente passou2/2
  após ter reproduzido2falhas antes da correção; código aec2781a intacto.
- Ruff/format e mypy strict win32 alvos3.11/3.14:PASS,1arquivo cada.
  Execução somente Windows/Python3.11.3;3.14 é análise estática.
- RED integral:135casos,9sanidades PASS/126FileNotFoundError esperados,
  0erros/skips/deseleções,29,479s, pilha QA64MiB. Todos126textos conferidos:
  uma única mensagem/caminho do módulo Proactor ausente, sem outra falha.
  O parser inicial supunha failure.type no JUnit, que não tem esse campo;
  a saída foi preservada e a classificação refeita por mensagem E trace.
- 142fontes protegidas intactas por hash/tamanho; state16/attempt não lidos
  nem tocados. Nenhum efeito nativo ou de produto.

Aceite sob delegação SOMENTE destes oráculos de modelo. Manifesto local
imutável:evidence/oracle9-w1-proactor-tests-review-20261112/frozen-red135.json.
V1, V2 pré-formatação, REDs e sondagem anterior preservados. Ausência de
implementação não é prova comportamental nem integração verde. Nenhum
teste parcial foi publicado; gates nativos/produto continuam OPEN.

Pré-requisito para a fonte satisfeito: revisão integral + RED congelado.
O próximo incremento pode escrever SOMENTE
docs/poc/oracle9_w1_proactor_pump.py pelo mesmo Claude2/Opus5.5/medium,
Read/Edit/Write restritos, sem comandos/execução. Teste36b2ba54, owner,
APIs, upstream/app124/state16/attempt FIXOS. Ler P3 E TODO PROACTOR-REVIEW
(R8 normativo) e esta revisão. Root lerá TODA fonte antes de QA; não
publicar candidato ou criar stubs para satisfazer ausência de módulo.
Todos os limites nativos N1–N16 permanecem abertos. Não chamar a ligação
real, instalar loop, criar socket/thread/processo/sinal/guard/Docker/PG/SQL,
ler runtime/config/privado/ambiente/binário ou preparar operacional/deploy.

## Histórico da V1 — antes da V2

2026-11-12, hora local. Root recuperou44109: exit0/success, mesma sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, Opus5.5/medium,23turnos, sem denials.
Leu TODAS2855linhas/108022bytes da V1
4e4ac9ce6020a8b7daac77406bbc042d7e257873ac72b250cdfdc25af3a0d778.
Snapshot local preservado literalmente.247funções/64funções de teste.
Fonte Proactor AUSENTE; oráculos NÃO aceitos/congelados.

## Medições da V1 antes de qualquer correção

- Windows/Python3.11.3, pilha QA64MiB.
- Cinco sanidades PASS, sem erro/skip.
- RED inicial completo:130casos,5PASS/125FileNotFoundError,0erros/skips,
  25,160s. Todas as125falhas apontam somente o módulo futuro ausente.
  Isso não é prova comportamental nem integração verde; NÃO congelado.
- Mypy2.3.1 strict, plataforma win32, alvos3.11 e3.14:PASS (1arquivo cada).
  Não é runtime3.14. HostileContext não precisa mudar por receio de tipagem.
- Ruff0.16.5:8achados (7E501,1PLC0207); format-check:FAIL.
- Sondagem independente do waiter:0PASS/2FAIL, ambas reproduzidas no fake
  antes do fix. Código aec2781a5122e3aa063eaf499cfff6671e7e349abd5691a03af9b8a699400b1f.
  Não carregou a implementação ausente nem executou SDK/nativo.

Dados locais: evidence/oracle9-w1-proactor-tests-review-20261112/,
v1-initial-qa-summary.json, v1-sanity.xml, v1-initial-red.xml e
probe-waiter-controls-red2.json. Logs brutos preservados.

## T1 — precedência do SDK no waiter está errada no fake

FakeLoop.subprocess_exec (V1 linhas553–558) captura toda BaseException e
faz sdk_auto_close + espera eterna. O SDK3.11.3 distingue:
[windows_events.py, _make_subprocess_transport](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_events.py#L403-L410)
repassa KeyboardInterrupt/SystemExit antes do catch de BaseException.

Root roteirizou somente o waiter do SDK FALSO para receber cada controle.
Ambos foram engolidos e geraram1sdk.close/1sdk.kill no trace, quando deveriam
atravessar por identidade sem esse cleanup automático. A sondagem já é RED
medido antes da correção; arquivo probe_waiter_controls.py, resultado red2.

Adicionar a regressão equivalente às sanidades e corrigir o fake, mantendo
o caminho de Exception comum que fecha/espera. Não transformar controles
customizados em KeyboardInterrupt nem alegar que o teste prova injeção
nativa. Respeitar também a distinção do _connect_pipes real ao decidir
como o fake injeta exceção no waiter, sem importar ou executar o SDK.

## T2 — primeiro ident válido não tem outra thread como referência

O construtor em P3 §2 grava me=ident() como identidade dona. Não tem um
OWNER_THREAD global, não recebe outra referência de thread e não pode
rejeitar7002 só porque a constante do teste é7001.

IDENT_FAILURES inclui other-thread e o teste de construtor espera recusa,
forçando uma implementação a adivinhar/hardcodear a constante. Corrigir
esse oráculo e acrescentar o positivo: identidade inicial válida diferente
de7001 constrói normalmente; mantida essa identidade funciona; mudá-la
DEPOIS da construção recusa antes dos efeitos. Manter todos os casos
inválidos de tipo/Exception/controle e as recusas em métodos públicos.
Isso esclarece a matriz R7-a; não muda nenhuma API ou regra de isolamento.

## T3 — R8.4 precisa exercitar o snapshot durante a drenagem inicial

O teste atual R8.4 cria o filho no callback started, já no loop; ele não
detecta um _flush_deferred incorreto que consuma novos itens acrescentados
durante a própria drenagem inicial.

Adicionar o caso: um not_started que já estava diferido cria, em seu hook,
outro pedido cujo agendamento falha, captura PumpFault e deixa outro
not_started diferido. Stop permanece falso. A primeira condução entrega
somente o snapshot original; a nova entrega só ocorre na condução seguinte,
sem authorize/exec da entrada recusada e sem exceder os bounds. Manter
também o caso atual criado no started, além das barreiras R5-i/j e R8.2.
Não ler fila privada do SDK nem produzir fato fora de run_until.

## T4 — estilo sem alterar as asserções

Corrigir os8achados Ruff da V1:

- E501 nas linhas123,346,1470,1717,1966,2377,2428;
- PLC0207 na linha2426: split com maxsplit=1.

Comentários longos precisam ser encurtados/quebrados. Root pode aplicar
Ruff format mecânico com AST idêntica após os ajustes; o programador não
executa comandos. Não acrescentar noqa/ignore/cast/skip/xfail/supressão e
não mexer em HostileContext cuja tipagem já passou.

## Próximo lote e limites

Mesmo Claude2/sessão/modelo/medium, Read/Edit/Write somente
tests/test_oracle9_w1_proactor_pump.py. Ler esta revisão, o teste inteiro
e o probe independente; incorporar as correções sem refazer a arquitetura.
Nenhum outro arquivo, source/stub ou teste antigo pode mudar. Root relê
todos os deltas, mede novamente sanity/probe/estáticos e só depois decide
sobre RED aceito/congelado. Fonte Proactor continua AUSENTE.

Ownera5/testese85/f86/15upstream/app124/state16/attempt fixos. Nenhum efeito
nativo/Docker/PG/SQL/loop/thread/processo/sinal/guard, runtime/config/
privado/binário/root/nonce/estado/entry/loader/collector/publisher/comando/
deploy. SDKs são contexto textual público, não dependência de runtime dos
testes nem simulador substituto da implementação. N1–N16 e gates de produto
seguem OPEN; Gateway indisponível. Não publicar este RED como suíte verde.
