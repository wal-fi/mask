# Próximo ciclo W1 — núcleo puro de admissão de idade

2026-10-26, escolha sob delegação. Desenho NATIVE-CYCLE-PLAN revisado pelo
Claude2 com F1/F2/precisões incorporados. Novo helper somente laboratório
docs/poc/oracle9_cycle_freshness.py: nenhum import por produto/runner real,
clock/WindowsAPI/CIM/arquivo/Docker/processo executado. Não autoriza ações.

Estado imutável canônico com contadores/FILETIME em strings uint64 exatas,
fases/ordem/contagem fechadas, A→B300s, nove observações10..30s, READY/B0..30s.
Teto total prevalece sobre a soma dos tetos por fase. Tick e UTC concordam
desde A e desde último checkpoint, com tolerância2s+0,1%, cálculo inteiro;
UTC não é fallback. Boot exige igualdade exata até medição F2 e revisão.
FAILED/ABORTED/B_CONSUMED terminais, segunda admissão B sempre REFUSE mesmo
quando a fase armazenada permanece B_CONSUMED. Decision tem bool proibido.
Chamador futuro deve persistir estado retornado antes do efeito, não apenas
olhar a fase. Dados são fatos de sampler confiável, não prova autenticada;
shape/intervalos necessários não provam sozinho a origem de cada amostra.

61testes puros aprovados no Windows3.11.3: limites±1ms, pausas/suspensão
simulada, boot exato diferente, rollback/tickUTC divergentes e deriva
acumulada, teto total, ordem/consumo, abort sem necessidade de amostra nova,
schema/duplicatas/truncamento, precisão acima2^53 e mutação hostil de frozen.
Nenhum teste de restauração física ou propriedade do Desktop é declarado;
esse núcleo não oferece stop nem decide inventário/ownership.

Quatro regressões de coerência de estado ficaram vermelhas antes do fix:
contagem9 incompatível com1ms, observações além de270s, estado além300s e
UTC incompatível. Agora revalida elapsed/count/fase/UTC ao desserializar,
codificar e transicionar. Isso não transforma snapshot de arquivo editável
em evidência criptográfica. Primeiros57testes passaram antes dessas quatro.

Ruff syntax E9/F63/F7/F82 e format do helper limpos; Ruff/check do teste e
mypy strict alvo3.11/3.14 no teste limpos. Não se declara mypy/full Ruff do
helper de laboratório sem tipos. Runtime só Windows3.11.3. Binding Windows
e estabilidade real do boot ainda não medidos, sem A/Observe/Ready/B real.

Revisão do núcleo puro pelo Claude2 concluída sem bloqueador. A amostra que
motivou recusa deverá ser guardada pelo integrador separadamente do último
checkpoint aceito; helper não autentica dados nem controla Desktop.
CoreSHA d2b485c29d2cef36599af51fc342ac39a991f9564bb919baa18d3cb1ff7e5b66.

Binding separado oracle9_clock_sample.py, somente fakes até a revisão:
18testes/79com o núcleo, ABI de DLL simulado inclusive64bits, ordem
boot→tick→UTC, saída/exit/flags, ausência de fallback. Reutiliza bounded
58c692a7 exatamente, com colaborador de ambiente público fixo no namespace
privado. PowerShell do sistema e core hashados antes/depois; CIM local com
stdout256bytes/8s e stderr descartado. Imports sem efeitos. Nenhum sampler
real/WindowsAPI/CIM invocado ainda.

Procedimento proposto de medição F2, após revisão do binding/comando: sete
invocações de `.venv/Scripts/python.exe -I -B docs/poc/oracle9_clock_sample.py`,
mesmo cwd, sem argumento/segredo/env adicional, com20s entre amostras em
esperas menores60s. Metadados públicos somente, cada exit0/frame/schema
conferido antes da próxima amostra; falha aborta série sem retry. Não é A,
Observe/Ready/B nem chama Docker. Capturar JSONs exatos e hashes/prefixo
se falhar; conferir monotonia/UTC e boot exato, sem relaxar política se variar.
Preflight pós-revisão e pós-série confere SHA do sampler/core/bounded/PowerShell.
Essa série lê relógio/CIM; não altera serviços, registro, credenciais ou
bancos. Nenhum scheduler ou escritor concorrente. Esse era o procedimento
revisto antes da execução; resultados da série única seguem abaixo.

## Série F2 executada uma vez após revisão do código/procedimento

Claude2 aceitou sampler/procedimento sem bloqueador antes da primeira chamada.
Task38cf5c14027341a88bb934243b43f26d, raiz própria Temp/maskgw-clock-f2-
20261026-9b4f94a6656647619230d7a196992cff, attempt consumido antes da chamada1;
sete arquivos sample-N.json persistidos, nenhuma repetição. Sete invocações
exatas terminaram exit0/JSON válido;20s de espera entre retorno/persistência
e próxima invocação. Intervalos do tick incluem custo das chamadas/persistência:
28422/29078/28453/27656/28250/27688ms; janela total169547ms.

Boot FILETIME exatamente igual nas sete. Avanço tick/UTC positivo e coerente
com tolerância2s+0,1%, conferido contra âncora e anterior. Resíduo exigido pelo
revisor boot−(UTC−tick×10000):347642138..347794000 unidades100ns, amplitude
151862unidades=15,1862ms. O resíduo absoluto não é zero e não se atribui causa;
a medição sustenta apenas estabilidade nessa janela. Não prova comportamento
após NTP/suspensão/hibernação/FastStartup nem torna a referência de boot
autenticada. Igualdade exata segue proposta até revisão da evidência.

Pins conferidos antes de cada chamada e após série:
- sampler6bcbdbe5b9345a5d70e408e1988226ad300d4e57d64eb6beec1d4d7cd55a692d
- core d2b485c29d2cef36599af51fc342ac39a991f9564bb919baa18d3cb1ff7e5b66
- bounded58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627
- PowerShell60c9b29843624dd8af6b6a7b26147753be6aeef65098b9a503cc50850afe410f

JSONs exatos, exits, análise inteira e fonte de cada campo preservados em
`docs/poc/evidence/oracle9-clock-f2-attempt1-20261026.json`, SHA-256
ceeb95eb4c81ab6ed71647b5eb40e5f38f53e824dff01c75e4dd2920304d04c1.
Samplers/core anteriores não mudaram. Estáticos finais src/tests293arquivos
limpos e79testes core/binding aprovados antes da série; depois dela só
documentação/evidência. Nenhuma medição A/B, Docker ou W1/PG16 ocorreu.
Evidência agora em revisão somente leitura, não declarar gate nativo W1 fechado.

Revisão dessa evidência concluída: sem bloqueador para manter boot exato,
fail-closed, no próximo ciclo integrado. Não se transforma janela curta em
certificação após suspensão/NTP. Essas mudanças podem causar abortos legítimos
e conservadores. Tempo do sampler deve contar no teto por observação/READY/B;
blocos curtos com duas observações evitam aproximação do teto60s de uma chamada.
Scripts/runner/restore ainda precisam de código/testes/revisão antes de A/B.

Produto/src/W1
aceito não mudou neste incremento, sem commit/push/deploy, quota/job ou
segundo escritor. DesktopOff; B-1/B-2/D-090/C1/SQL/produção abertos.
