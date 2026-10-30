# Entrega pública do leitor PG16 — variante mínima, sem Docker

2026-10-30 sob delegação. pg16_shell_delivery.py captura owner d671, reader
efe6 e canal e6ca já revisados. Nenhum chamador operacional, shell, Docker,
cluster, SQL, seed privado ou recurso do ensaio criado. Testes de lifecycle
usam processo fake e Timer independente de8s como watchdog do pytest, sem
iniciar o watchdog de containers ou alegar que esse Timer é simulado.

## Desenho antes do código

Review33095/sessão51ea0d85 aceitou apenas incremento1 do HOST-DESIGN, com
cinco precisões incorporadas: prefixo idêntico/ordem da fonte shell, replace
somente wire/chunks, case str exata e erro fora de except, subclasse com só
constructor sobrescrito, e namespaces separados comparados por primitivos.
A seção2 do desenho (host) permanece sem revisão própria e sem implementação.

PublicDeliveryOwner sobrescreve apenas __init__; métodos de spawn/env/feed/
send_vector/pump/drain/close/quiesce/ticket/handles são os mesmos objetos do
owner d671. Só recebe task/CID/case str fechado. Regra fixa: nove HEADER
enviam wire[:16] (short-header já tinha15),14outros preservam wire/chunks/
hold_open exatos. Case/body/fault/tail não mudam. Nenhum Seed ou byte do
operador. Troca do Vector ocorre depois do constructor-base, antes de start.

Delivery congelado descreve case/mode/wire_bytes/chunk_sizes/hold_open.
É configuração, não prova de syscall/recepção. SENT continua handoff local.
O novo SHA será pinado separadamente no host; o manifesto8906 segue citando
a base d671 herdada, sem alegar autenticar a subclasse ou host inteiro.
Wrapper/CORE_SHA/Target e oráculos antigos são preservados.

## Gates finais

- Dois fakes da nota1 ampliaram a seleção própria para25casos. Seleção final
  reader/owner/perfil/entrega:143passed/5,97s, sem falhas/skips/deselected.
- Ruff src/tests e helper E9/F63/F7/F82: aprovados. Format333 conformes.
- Mypy strict src/tests:332 arquivos, alvos3.11/3.14 limpos. Runtime apenas
  Windows3.11.3; não alegar execução Linux/3.14 nem PipeHandles reais.
- Fonte42f7e647/2528bytes não mudou após a revisão42864. Só testes/notas de
  ordem antecipada e stubs tipados foram acrescentados/corrigidos.

## Gates próprios antes da revisão

-23passed/0,93s; primeira seleção21/0,97s antes dos dois testes de erros novos.
- Todos23casos comparados campo a campo; nove prefixes com chunk exato e
  tamanho≤16,14wiresexatos; short-header15sem corte adicional. Parser original
  conserva faultHEADER/exit42. A ordem de dd/header/failHEADER antes do corpo
  é conferida na fonte capturada, sem chamar modelo Python de prova do shell.
- Herança completa por identidade de atributos, caso enum próprio/estrangeiro/
  str derivada recusados, só primitivos cruzando perfil/owner; wrapper e hashes
  do Target/Intent concordam. Captura/erros sem contexto/str/repr do caller.
- Transporte fake envia bytes configurados, closes/RETAIN/WAIT preservados,
  BrokenPipe continua IO/UNKNOWN mesmo diante de recusa esperada; nenhum
  tratamento especial para ignorar I/O. Import/build não criam subprocesso,
  arquivo operacional ou diretório. Não se afirma medição shell/EOF/exit42.
- Fonte2528bytes SHA-256:
  42f7e647c548c1947be61fb7425142ec0f00b7c0fd12ca7700ecece6d2f56188.
- Helper E9/F63/F7/F82 limpo; linhas/formatação dos novos arquivos corrigidas.
  A seleção inicial relacionada passou141/5,57s. Mypy inicial apontou só dois
  stubs de métodos no teste; substituídos via monkeypatch, sem alterar helper.

## Revisão e ordem de saída antecipada

Claude2/review42864 aceitou o helper42f7 isolado, sem bloqueador. Nota1
incorporada em dois fakes adicionais: write→receiverstdout/exit42→close.
Com close/handles positivos, o transporte entrega faultHEADER/42 normalmente;
com BrokenPipe em close, continua IO/UNKNOWN, sem aproveitar esse prefixo.
Não é medição da ordem real do Docker/Proactor. A fixture troca PIPE_TYPE,
admit_runtime e CLOSE_SECONDS0,05 somente em fakes; orçamento original3s e
admissão/pins reais permanecem intactos. O SHA novo deve ser ligado a host/
estado/evidência futuros; ainda não há consumidor operacional dele.

Sem regressão vermelha de implementação reivindicada neste incremento; o
risco de envio após recusa foi antecipado no desenho. Futuro host ainda deve
comprovar Target/wrapper/perfil antes de start e returncode real vs State.
Nenhum prazo ampliado, produção/Gateway/B1/B2/D090/C1/SQL continuam abertos.
