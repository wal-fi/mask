# Chamador privado de admissão PG16 — validação e parecer

2026-11-01, America/Sao_Paulo, sob delegação vigente. Baseline Git publicado
`49865c643cabcdf5a761e552b086ce8b871db42f`. Claude2 foi o único programador,
`claude-opus-5-5`/esforço `medium`, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`. O assistente principal revisou,
executou gates e escreveu este fechamento, sem implementar helper/testes.
Somente código e fakes; não é uma rodada de admissão nativa.

## Fontes finais e escopo

- `docs/poc/pg16_shell_admission_host.py`:33.234bytes, SHA-256
  `dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7`.
- `tests/test_pg16_shell_admission_host.py`:41.031bytes, SHA-256
  `dcfbd5d55619858bd57c2d463a218bc32ec46e71e51cf7e19ad31d0e7418dac8`.
- Desenho e notas: `PHASE-9-W1-PG16-SHELL-ADMISSION-HOST-DESIGN.md`.
- Histórico inicial: `PHASE-9-W1-PG16-SHELL-ADMISSION-HOST-REVIEW.md`.

Backend10c9058f, preparador8d0bf39e, sonda738ee1e3, entradaafaffad0 e
exportadored491c01 conferidos intactos. Nenhuma fonte/raiz consumida foi
alterada ou repetida. Os16campos continuam exatos. O código é PoC privado
não embarcado, do laboratório Windows pinado deste checkout; não é
configuração de deployment ou serviço pronto para uso.

## Quota, retomada e autoria

CLI96055 terminou API429 antes do fechamento, com fonte db97193d e teste
7286545d parciais.103testes passaram, mas havia quatro findings independentes
e gates estáticos reprovados. Nada parcial foi publicado.

A tarefa única `Maskgw-Claude2-Resume-01a05804` foi registrada e relida para
01/11às16h25-03:00. A execução foi observada às19:25:00Z:LastTaskResult0,
mensagem recebida nesta conversa e nenhum processo da sessão Claude2 ativo
antes de retomar. A tarefa foi desativada após conferir o resultado, sem
próximo horário. Não é inferência baseada somente no agendamento.

A mesma sessão/modelo/esforço foi retomada, sem trocar conta, burlar quota ou
iniciar segundo escritor. CLI93212 e40628 escreveram somente regressões e
harness;58180 corrigiu o chamador e notas;79555 corrigiu os dois achados finais.
Todas terminaram exit0. O programador não executou testes nem efeitos nativos.
As regras Read/Edit/Write e negações de binários/runtime/config foram mantidas.
O desvio de leitura de configuração do lote anterior continua histórico, sem
aprovação retroativa; não houve novo desvio observado neste incremento.

## Regressões medidas antes da correção

Os quatro findings iniciais constam no histórico: relógio final inválido ainda
aceitava; start ocorria após setup consumir61s; overflow drenava sem pausa;
interrupção não gravava registro privado HELD/bytes parciais.

1. Fonte db97193d preservada; primeiras regressões mediram **6failed,
   104passed/24,45s**, exit1. O erro estático remanescente RUF007 foi devolvido.
2. Revisor exigiu injeção de NaN causal, após close, independente de quantas
   leituras existam; exigiu provar que falhas de fsync eram acionadas, para
   evitar controles verdes sem exercitar a gravação.
3. Fonte ainda db97193d; testes fd53e107 mediram **8failed,102passed/6,21s**,
   exit1. Hook causal independente:quatro findings,1passed/1error/1,65s.
   Ruff/formato e mypy342311/314 já estavam limpos antes da correção do helper.
4. Depois da correção, fonte5dd5a9fe/testes7719e5d:112passed/6,24s; hook causal
   CLEAN/1,07s; estáticos aprovados. O conjunto da fonte não foi publicado ainda.

Cópias base64 verificadas, manifestos e snapshots dos testes vermelhos estão
em `poc/evidence/pg16-host-review-20261101/`. São dados públicos de revisão,
não programas operacionais. Baselines rejeitadas permanecem rejeitadas.
O check do índice detectou CRLF nos três manifestos JSON novos gerados pelo
revisor no Windows. Somente esses metadados ainda não commitados foram
gravados em LF, com igualdade do JSON antes/depois; nenhum snapshot base64,
byte decodificado, hash de fonte/teste ou artefato histórico foi normalizado.

## Revisão adicional de integridade

A composição do chamador com a classe real do backend aceito, substituindo
somente kernel32 por Kernel fake, passou em três cenários: saída normal com
todos os handles simulados fechados uma vez; setup esgotando o prazo sem
CreateProcess; CloseHandle falhando e owner retido em HELD sem publicação.
Nenhuma DLL/API de job/processo real foi carregada ou chamada por esse teste.

O mesmo hook detectou mais dois problemas na fonte5dd5a9fe:

- **P2:** a projeção substituía o conjunto de artefatos; o transporte aceito
  vinculava só claim/marca/resultado, perdendo invocation/supervision/stdout.
- **P3:** registro HELD dizia terminated=false mesmo quando a chamada de
  terminate havia retornado sucesso.

Hook1passed/1error/1,43s, exit1, confirmou ambos. O snapshot binding-source
preserva aqueles bytes. Claude2 escreveu regressões antes das mudanças:
quatro desfechos aceitos exigem exatamente seis artefatos e recomputam cada
SHA/tamanho a partir dos arquivos; três casos de terminate verificam a flag.
Não se declara medição vermelha desses testes formais novos: o vermelho
medido foi o hook independente. A projeção agora acrescenta os artefatos sem
apagar os anteriores; a flag reflete só o retorno bem-sucedido da chamada,
sem significar prova de reaping/liberação nem permitir tirar o owner de HELD.

## Gates finais medidos

- Próprios: **119passed/5,56s**, exit0, sem falhas/skips.
- Hook causal:quatro cenários CLEAN,1passed/0,59s, exit0.
- Hook de composição/vínculo/flag:três cenários de composição e dois controles
  de integridade CLEAN,1passed/0,49s, exit0.
- Relacionados:**859passed/309,01s**,18arquivos, sem falhas/erros/skips/
  deselected, exit0; os119próprios estão incluídos.
- Ruff src/tests e lint E9/F63/F7/F82 do helper aprovados.
- Format:**349arquivos**, src/tests e sete PoCs atuais aprovados, sem
  normalizar fontes históricas congeladas.
- Mypy strict:**342arquivos**, src/tests, alvos3.11 e3.14 sem erros. O PoC
  docs/poc está fora desse escopo deliberadamente, conforme a configuração.
- Runtime executado somente Windows/Python3.11.3. Mypy3.14 não é execução
  nesse interpretador nem prova do ABI nativo.

Comandos:`python -m pytest -o addopts= -q --tb=short` com os17arquivos da
SHELL-ADMISSION-WIN32-VALIDATION mais `tests/test_pg16_shell_admission_host.py`;
`ruff check src tests`; lint restrito do helper; `ruff format --check src
 tests` mais pin_cost/pin_capture/shell_export/shell_prepare/
shell_admission_probe/shell_admission_win32/shell_admission_host;
`mypy --python-version 3.11 src tests` e equivalente3.14.
A seleção é de fakes/temporários próprios e não exige DSN. Depois desses
gates mudaram apenas relatórios e estado documental; helper/testes conservaram
os mesmos fingerprints. Não foi executada
suíte integral, PostgreSQL, browser/frontend ou novo pacote para este PoC
não embarcado. Não confundir estes resultados com integração de produção.

Parecer do revisor: aprovado somente no componente privado sob fakes,
sem P1/P2 remanescentes nesse escopo. Nenhuma aprovação individual do
usuário ou validação nativa é inferida deste parecer.

## Contrato revisado e limites

A API privada permanece `run(root,task)`, sem CLI, consumidor, callbacks ou
opções de executable/argv/ambiente/deadline. Request imutável, ambiente com
10nomes fixos, valores nunca persistidos. O hash próprio é metadado, com pin
externo previsto no procedimento futuro, sem circularidade.

Invocação xb/contagem/flush/fsync/releitura antes de lançar. Owner registrado
antes de setup e removido só depois de CLOSED; referência retida impede outra
run antes de efeitos. Deadline desde setup, orçamento60s+cleanup10s verificado
entre chamadas; relógio inválido/retrocesso e conclusão tardia não aprovam.
Retenção1024/leitura4096 com cooperação por turno, EOF/sinal/contas/lista de
PIDs em conjunto e close confirmado. Contexto parcial sobrevive à interrupção;
registro privado por melhor esforço preserva a exceção original mesmo se
terminate/gravação sofrerem outra interrupção. Backend HELD não é contornado.

Projeção estrita de schema/canonicalidade/tipos/relações numéricas. Framing
LF/CRLF fechado, sem alegar formato nativo medido. Seis fontes vinculadas nos
desfechos aceitos; resumo vinculado ao transporte, único marcador de conclusão.
Descriptor/bytes preparados antes do último rename não sobrescrevente; nenhum
I/O depois dele. `ACCEPTED_*` significa só evidência íntegra; `entry_gate` é
sempre NOT_EVALUATED e o gate original da entrada não foi substituído.

Não há prazo absoluto para chamadas síncronas do SO ou filesystem, contenção
de memória, retenção após morte do dono, garantia de persistência de diretório
após falta de energia ou defesa contra o mesmo usuário alterando o ambiente.
O registro HELD é melhor esforço; missing/partial nunca autoriza retry.
Nenhuma evidência de launcher/job/pipe/framing/latência nativos foi obtida.

Próximo: procedimento e controle benigno separados, revisados antes de qualquer
efeito real; só depois proposta e rodada da sonda. Nenhuma raiz operacional,
controle Win32 nativo, Docker/PG/SQL, deployment, worker ou serviço foi iniciado.
Admissão nativa3s permanece NOT_MEASURED; Gateway/B1/B2/D090/C1/SQL/produção
continuam abertos. Não usar o banco ou credenciais antigos de aceitação.

## Hooks finais do revisor para reprodução

Código de revisão em memória, sem adicionar ou editar testes de produto.
Usa somente fakes e temporários da fixture; não executar o chamador ou a
sonda operacional para reproduzir estes controles. O bloqueio de WinDLL é
instalado depois da coleta do framework e antes das fixtures. O primeiro
hook injeta NaN causalmente depois do close; o segundo compõe o backend
aceito com Kernel fake e confere vínculo/flag. Os tempos acima são de pytest,
não de execução nativa. Rodar os blocos separadamente com o Python do ambiente.

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
   close=item.module.Owner.close
   def bad_after_close(owner):
    close(owner)
    owner.lab.clock.values=[float("nan")]
   mp.setattr(item.module.Owner,"close",bad_after_close)
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

```python
import ctypes,json,runpy
from pathlib import Path
import pytest
findings=[]
checks=[]
original=ctypes.WinDLL
def forbidden(*a,**k):raise AssertionError("NATIVE_DLL_FORBIDDEN")
class Review:
 def pytest_collection_finish(self,session):ctypes.WinDLL=forbidden
 def pytest_sessionfinish(self,session,exitstatus):ctypes.WinDLL=original
 @pytest.hookimpl(tryfirst=True)
 def pytest_runtest_teardown(self,item,nextitem):
  if item.originalname!="test_invocation_is_durable_before_launch_and_has_no_env_values":return
  lab=item.funcargs["lab"]
  transport=json.loads((item.module.public(lab)/"transport.json").read_bytes())
  actual={entry["name"] for entry in transport["private"]}
  expected={"invocation.json","supervision.json","local-stdout.bin","probe-claim","probe-result","probe-marker"}
  missing=sorted(expected-actual)
  if missing:findings.append({"finding":"P2_TRANSPORT_OMITS_PRIVATE_SUPERVISION","missing":missing,"actual":sorted(actual)})
  fixture=item.module.lab.__wrapped__
  kernel_source=runpy.run_path("tests/test_pg16_shell_admission_win32.py")
  Base=kernel_source["Kernel"]
  for label in ("normal","before-start-deadline","close-failure"):
   with pytest.MonkeyPatch.context() as mp:
    directory=lab.tmp/("compose-"+label)
    directory.mkdir()
    fresh=fixture(directory,mp)
    backend=runpy.run_path("docs/poc/pg16_shell_admission_win32.py")
    ns=backend["Owner"].setup.__globals__
    class Kernel(Base):
     def CreatePipe(self,*args):
      result=super().CreatePipe(*args)
      if label=="before-start-deadline":fresh.clock.now=61.0
      return result
     def ResumeThread(self,thread):
      result=super().ResumeThread(thread)
      fresh.scenario.write()
      self.pipe.extend(fresh.scenario.chunks[0])
      self.alive=False
      return result
    k=Kernel()
    if label=="close-failure":k.plan[("CloseHandle",4)]=("false",5)
    mp.setitem(ns,"_load_api",lambda:backend["_Api"](k,lambda:k.last))
    mp.setitem(ns,"sys",kernel_source["runtime"]())
    mp.setitem(fresh.namespace,"_load_backend",lambda raw:backend)
    result=None
    try:result=item.module.run(fresh)
    except fresh.module["HostError"] as error:
     assert label=="close-failure" and error.args==("HOST_HELD",)
    if label=="normal":
     assert result["outcome"]=="ACCEPTED_WITHIN_3S"
     assert not k.alive and not k.double_closed and not k.attr_live
     assert set(k.closed)==set(k.handles.values()) and fresh.module["_LIVE"]==[]
    elif label=="before-start-deadline":
     assert result["category"]=="DEADLINE" and k.created is None
     assert not k.double_closed and set(k.closed)==set(k.handles.values())
     assert fresh.module["_LIVE"]==[]
    else:
     assert len(fresh.module["_LIVE"])==1 and fresh.module["_LIVE"][0].state=="HELD"
     assert not item.module.public(fresh).exists()
    checks.append(label)
  with pytest.MonkeyPatch.context() as mp:
   directory=lab.tmp/"review-interrupt-flag"
   directory.mkdir()
   fresh=fixture(directory,mp)
   fresh.scenario.interrupt="wait"
   try:item.module.run(fresh)
   except KeyboardInterrupt:pass
   record=json.loads((item.module.private(fresh)/"supervision.json").read_bytes())
   if fresh.owners[0].terminated and record["terminated"] is not True:
    findings.append({"finding":"P3_HELD_TERMINATE_FLAG_STALE","backend_terminate_returned":True,"recorded":record["terminated"]})
  print("COMPOSITION_CHECKS "+json.dumps(checks))
  print("INDEPENDENT_BINDING_FINDINGS "+json.dumps(findings))
  assert not findings,"PRIVATE_BINDING_REVIEW_BLOCKED"
status=pytest.main(["-o","addopts=","-q","-s","--tb=short","tests/test_pg16_shell_admission_host.py::test_invocation_is_durable_before_launch_and_has_no_env_values"],plugins=[Review()])
raise SystemExit(int(status))
```
