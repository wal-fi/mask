# Chamador de admissão PG16 — histórico da revisão parcial e da quota

2026-11-01, America/Sao_Paulo, sob delegação vigente. Baseline publicado
`49865c643cabcdf5a761e552b086ce8b871db42f`. Claude2 é o único programador,
`claude-opus-5-5`/esforço `medium`, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`. O assistente principal apenas revisou,
executou fakes e registrou evidência. **Parecer inicial: não aprovado.**
Naquele ponto nenhum código do incremento havia sido commitado ou publicado.
O histórico abaixo fica preservado; o fechamento posterior está em
`PHASE-9-W1-PG16-SHELL-ADMISSION-HOST-VALIDATION.md`.

## Estado e fontes parciais

CLI49174 concluiu um plano em leitura apenas. O revisor fechou retenção do
owner antes de setup, framing LF/CRLF exato, orçamento incluindo setup/start,
validação condicional dos resultados e ausência de CLI neste incremento.
CLI96055 gravou helper/testes e terminou exit1/API429 antes de fechar o desenho.
Resposta: limite da sessão, reset às16h20 America/Sao_Paulo de01/11.

- `docs/poc/pg16_shell_admission_host.py`:30.239bytes, SHA-256
  `db97193dae8a076b94594a7b0b1979666303c013441ceb50c8a3f2c8e4bb4799`.
- `tests/test_pg16_shell_admission_host.py`:30.795bytes, SHA-256
  `7286545d718b42a12505bfb9009b405c01c6a8ffe91ce0709e9863875d5414b7`.
- Backend aceito10c9058f e desenho9022290a intactos; as notas do chamador
  não foram atualizadas pelo programador antes da quota.

Cópias exatas dos dois arquivos como base64 e manifesto estão em
`poc/evidence/pg16-host-review-20261101/`, apenas dados de revisão, ainda
locais, não artefatos operacionais. Decodificação conferida contra os arquivos.
Não executar esses snapshots como programa. Fontes consumidas intactas.

## Gates medidos, sem aprovação

- Testes próprios parciais: **103passed/6,50s**, exit0, com backend/launcher/
  relógio/ambiente substituídos. Guarda de ctypes.WinDLL instalada após a
  coleta do pytest; nenhuma API do backend Win32 foi exercitada.
- Duas tentativas anteriores do wrapper do revisor não chegaram aos testes:
  uma falha de quoting e outra por bloquear também o bootstrap Colorama do
  pytest. Não são falhas do produto nem execuções adicionais dos103casos.
- Ruff src/tests: **2 erros**, C420 na construção de estado da fixture e
  PLR0913 nos7argumentos do helper de cenário `probe`.
- Lint restrito E9/F63/F7/F82 do helper: aprovado.
- Formato: helper conforme; teste requer ajustar um decorator, 1 aprovado/
  1 reprovado. Nenhum autoformat foi aplicado pelo revisor.
- Mypy3.11: **2 erros**, retorno Any em `Owner.read` e retorno object em
  `classification`, 342arquivos inspecionados. Alvo3.14 e relacionados não
  executados: há findings e a implementação está parcial.

## Quatro findings independentes reproduzidos

Um hook em memória, sem editar teste/helper, usou quatro fixtures novas e
APIs simuladas. Resultado **1passed/1error em18,61s**, exit1, com os quatro
findings abaixo. O erro de teardown é a asserção deliberada do parecer
bloqueado; os103testes anteriores não detectavam estes casos.

| Finding | Reprodução | Correção exigida antes de aprovação |
| --- | --- | --- |
| P2-A — relógio inválido após close ainda aceita | Leituras `[0.0,0.01,0.02,0.03,NaN]`: devolve `ACCEPTED_WITHIN_3S` e `caller_seconds:null`. | A última leitura inválida deve impedir aceite, mantendo os recursos já fechados e a classificação negativa coerente. |
| P2-B — start após esgotar orçamento no setup | Setup avança o relógio para61s; `start` ainda é chamado e só depois há `DEADLINE`. | Conferir orçamento/relógio entre setup e start; não criar o filho depois de vencido. Fechar o owner READY se comprovável. |
| P2-C — drain de overflow sem pausa |1500bytes seguidos de5chunks de4096 geram7reads antes da primeira espera e zero pausas. | Todo turno de drain deve ceder controle; o continue não pode burlar espera/pausa e consumir artificialmente o teto de turnos de cleanup. |
| P2-D — interrupção sem registro privado de HELD | KeyboardInterrupt em read mantém owner registrado e termina uma vez, mas não tenta gravar supervision.json em diretório gravável. | Registrar HELD e bytes parciais em privado por melhor esforço, sem apagar a referência, publicar ou mascarar a interrupção original. |

Saída do hook: `P2_POST_CLOSE_BAD_CLOCK_ACCEPTED`,
`P2_STARTED_AFTER_SETUP_EXHAUSTED_DEADLINE`,
`P2_OVERFLOW_DRAIN_NO_COOPERATIVE_WAIT`,
`P2_INTERRUPTION_NO_PRIVATE_HELD_RECORD`. Regressões formais devem ser
escritas e medidas vermelhas antes de corrigir o helper. Corrigir também os
gates de harness, sem skip/xfail/ignore ou enfraquecer limites.

## Retomada confirmada

Tarefa existente `Maskgw-Claude2-Resume-01a05804` foi ajustada e relida:
**Ready**, uma execução em **2026-11-01T16:25:00-03:00**
(**19:25:00Z**),1trigger,`IgnoreNew`,`Limited`,`StartWhenAvailable=true`.
Ação `codex queue` na conversa `01a05804-2c07-71f2-bfef-7e3c90c06476`;
argumentos/mensagem conferidos por igualdade. Não é prova de execução futura.
Depende do computador ligado, usuário conectado e app server disponível.
O LastTaskResult0 observado é da rodada antiga, não deste novo agendamento.

Antes de retomar: conferir Git, fonte/teste parciais e escritor ativo; se
existir, apenas acompanhar. Retomar somente a mesma sessão Claude2, mesmo
modelo/esforço e regras Read/Edit/Write com negações de runtime/binários.
Não usar outra conta/modelo nem tentar antes do reset para contornar quota.
O revisor não programa a correção em seu lugar.

Após corrigir os quatro casos: repetir o mesmo hook, próprios, relacionados e
estáticos; revisar notas do desenho e publicar somente o resultado verificado.
Não há CLI/consumidor operacional. Nenhuma raiz de tentativa, controle nativo,
sonda, Docker/PG/SQL/worker/serviço foi iniciado. Apenas arquivos públicos e
árvores temporárias sintéticas das fixtures. Estado16campos permanece exato;
3s NOT_MEASURED, Gateway/B1/B2/D090/C1/produção continuam abertos.

## Hook do revisor (somente fakes, arquivo de teste parcial como autoridade)

Texto para reprodução pelo revisor, não código de produto ou controle nativo.
A asserção final deve permanecer; não transformar os findings em expectativa
verde. O teste selecionado é só a âncora da fixture.

```python
import ctypes,json
from pathlib import Path
import pytest
findings=[]
original_dll=ctypes.WinDLL
def forbidden(*args,**kwargs):
 raise AssertionError("NATIVE_DLL_FORBIDDEN_IN_REVIEW")
class Review:
 def pytest_collection_finish(self,session):
  ctypes.WinDLL=forbidden
 def pytest_sessionfinish(self,session,exitstatus):
  ctypes.WinDLL=original_dll
 @pytest.hookimpl(tryfirst=True)
 def pytest_runtest_teardown(self,item,nextitem):
  if item.originalname!="test_invocation_is_durable_before_launch_and_has_no_env_values":return
  base=item.funcargs["lab"]; factory=item.module.lab.__wrapped__
  def fresh(label,mp):
   directory=base.tmp/label
   directory.mkdir()
   return factory(directory,mp)
  with pytest.MonkeyPatch.context() as mp:
   lab=fresh("review-clock",mp)
   lab.clock.values=[0.0,0.01,0.02,0.03,float("nan")]
   result=item.module.run(lab)
   if result["outcome"].startswith("ACCEPTED_") and result["caller_seconds"] is None:
    findings.append({"finding":"P2_POST_CLOSE_BAD_CLOCK_ACCEPTED","outcome":result["outcome"],"caller_seconds":None})
  with pytest.MonkeyPatch.context() as mp:
   lab=fresh("review-setup-deadline",mp)
   setup=item.module.Owner.setup
   def slow_setup(owner):
    setup(owner)
    owner.lab.clock.now=61.0
   mp.setattr(item.module.Owner,"setup",slow_setup)
   result=item.module.run(lab)
   if "start" in lab.events:
    findings.append({"finding":"P2_STARTED_AFTER_SETUP_EXHAUSTED_DEADLINE","category":result["category"],"started":True})
  with pytest.MonkeyPatch.context() as mp:
   lab=fresh("review-drain",mp)
   lab.scenario.chunks=[b"x"*1500]+[b"y"*4096]*5
   result=item.module.run(lab)
   first_wait=lab.events.index("wait") if "wait" in lab.events else len(lab.events)
   reads_before_wait=lab.events[:first_wait].count("read")
   if reads_before_wait>2 and not lab.sleeps:
    findings.append({"finding":"P2_OVERFLOW_DRAIN_NO_COOPERATIVE_WAIT","reads_before_wait":reads_before_wait,"pauses":0,"category":result["category"]})
  with pytest.MonkeyPatch.context() as mp:
   lab=fresh("review-interrupt-record",mp)
   lab.scenario.interrupt="read"
   interrupted=False
   try:item.module.run(lab)
   except KeyboardInterrupt:interrupted=True
   record=item.module.private(lab)/"supervision.json"
   if interrupted and lab.module["_LIVE"] and not record.exists():
    findings.append({"finding":"P2_INTERRUPTION_NO_PRIVATE_HELD_RECORD","retained":True,"supervision_exists":False})
  print("INDEPENDENT_FINDINGS "+json.dumps(findings))
  assert not findings,"INDEPENDENT_REVIEW_BLOCKED"
status=pytest.main(["-o","addopts=","-q","-s","--tb=short","tests/test_pg16_shell_admission_host.py::test_invocation_is_durable_before_launch_and_has_no_env_values"],plugins=[Review()])
raise SystemExit(int(status))
```

## Fechamento posterior, mantendo o registro inicial

Retomada de01/11às16h25 foi observada com LastTaskResult0 e mensagem nesta
conversa; tarefa única desativada sem próximo horário. Claude2 corrigiu os
quatro casos após8regressões vermelhas/102aprovadas. Revisão posterior ainda
achou P2 de vinculação de artefatos e P3 de flag; ambos corrigidos após
contraprova independente. O helper/testes finais dfcc4ed6/dcfbd5d5 tiveram
119próprios e859relacionados aprovados; hooks causais/composição/vínculo
CLEAN e estáticos conformes. Parecer final no componente sob fakes aprovado,
sem P1/P2 remanescentes nesse escopo; este histórico não muda as baselines
rejeitadas. Números completos e limites na SHELL-ADMISSION-HOST-VALIDATION.
Sem escritor ativo ou nova quota/job. Nenhum controle nativo, raiz operacional,
Docker/PG/SQL/serviço;3s NOT_MEASURED e produção continuam pendentes.
