# Erros tipados — procedimento PG16 descartável

**2026-10-23 — plano CONSUMIDO: A/B/C concluídos uma vez.**
Procedimento abaixo preserva o desenho revisto antes de agir. Desktop próprio
observado9 vezes; B criou PG16.15 em loopback e concluiu suíte integral:
7.503 passed/20 skips de plataforma, sem falhas/erros ou skips por DSN.
Os17 casos obrigatórios passaram; container/volume próprios removidos,
inventário restaurado e fontes intactas. B terminal/exit0; C conferiu a
identidade, stop/exit0 e ausência de processos Docker. Desktop restaurado off.
Não repetir start/B/C nem iniciar outro escritor. Os estados iniciais e
comandos abaixo são históricos, não uma receita para repetir este attempt.
Código revisado,392 testes relacionados e95 de contrato/guards verdes.
Novo teste de integração tem5 casos para as notas do revisor (saúde positiva,
QUERY/cardinalidade, timeout e término do próprio backend). Banco do usuário
não será acessado; DSN preexistente não é herdado.

## Artefatos e comando

Raiz própria já criada:
C:\Users\w.filho\AppData\Local\Temp\maskgw-worker-errors-pg-20261023-3ce74efa
task=df9b8229bd5e4956a63406e0c410cb77, attempt.json kind=maskgw-worker-errors-pg16,invoked=false,
desktop_initial=unobserved,started=false,stop_allowed=false.
Nenhum comando start/CLI/container/consulta executado por este preparo.

Programa docs/poc/worker_errors_pg.py, SHA
1ec9d0071feaa1dd8706c6d8b252a5fe9270c5c65491cb79cc140616d60f2470.
Scripts externos copiados exatamente para revisão em
docs/poc/evidence/worker-errors-pg-procedure-20261023.json:
- start_desktop.ps1 SHAd2bf11cb8f1806163b2f97d4e6c072e70d88f1782bd26f3f604de31911cf165c,2939bytes;
- restore_desktop.py SHAb491f71d7c6d583e19b47da8a34d80695ad05dfa66f1e9cdb509b0d6ed8d495a,2453bytes.
Parser PowerShell:0 erros;26 testes puros de ownership/binding/env/JUnit e
guarda de -O, sem CLI/processos reais. main recusa optimize!=0 antes de
parse/I/O; não confiar em asserts quando desativados. Invoked é escrito por
temporário exclusivo, flush/fsync e replace antes de CLI; não promete fsync
de diretório Windows ou recuperação de toda falha do SO.

Antes de qualquer ação, recomputar hashes do programa, scripts, CLI e
config/contexto. DockerCLI60028870931ea6e91955bfeaee358ec6c6920f6162c17a3d828c3c82ab3c3599;
Desktopf3100322884b025ead78c49b512ece5e8c1f444ea91c57a4e045cc409386a3de.
Configf173396ef80b3c0bf4f8a5f6f944d3e426cee041ae3a2a8a07602ff6846a9f1a,
meta/contextoc16649b1a2f1c6fbb68b85158a956862331e86543e25df46341f5fe5df2f9a25.
Contexto desktop-linux/endpoint named-pipe local; DOCKER_HOST não é herdado.
Helper bounded congelado58c692a775a2dffdaa6be86866cdb15ddb307f97aeb8a04b4f7c737ea56c3627.

## A — observar/iniciar o Desktop

Uma chamada do script revisado, com cwd do checkout:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-worker-errors-pg-20261023-3ce74efa\start_desktop.ps1'
```
Se já houver processo Docker, registra active e não inicia/para esse app.
Senão, registra START_RESERVED antes de Start-Process Hidden, aplica
allowlist Windows padrão longa (mesma escolha S1 já revisada), restaura
ambiente somente do PowerShell no finally, registra PID/FileTime de criação
e nomes das chaves (nunca valores). Não repetir start/consumir outra conta.

Aguardar90s em observações de processos, nove intervalos10s, com atualização
do root antes de60s; sem readiness CLI extra. Com start próprio, PID e
FileTime devem continuar iguais. Se instável/ambíguo, abortar sem B.
Após observações efetivas registrar phase=APP_READY, sem inventar READY.

## B — uma invocação do gate, com stdout supervisionado

```powershell
Set-Location -LiteralPath 'C:\Users\w.filho\Desktop\codes\mask'
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\Desktop\codes\mask\docs\poc\worker_errors_pg.py' --run --root 'C:\Users\w.filho\AppData\Local\Temp\maskgw-worker-errors-pg-20261023-3ce74efa' --docker 'C:\Users\w.filho\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
```

Programa consome invoked antes de CLI. Usa cópia privada runpy do bounded,
sem modificar fonte: apenas colaborador de ambiente substituído naquele
namespace para encaminhar senha de teste **somente** ao create e DSN
**somente** ao runner. Allowlist remove secrets/contas/proxies e PYTHON*.
CLI5/10s e64KiB; runner1800s/4MiB, sem claim de teto absoluto sob falha do SO.

Sequência: version linux/amd64; ps global vazio; image inspect do
postgres:16-alpine já local, sem pull/download; guardar IDsha256 e usá-lo
no create --pull never. Primeira falha aborta, sem retry automático.
Create parado, nome+label/task exclusivos, auth-hostSCRAM, senha aleatória
48hex só em ambiente (não argv/repositório),512MiB memory/swap/pids256/CPU1,
log-driver none, única publicação127.0.0.1::5432, volume anônimo próprio.
Não é perfil de contenção do gateway/B-2, não limita todo host.

Guardar ID e conferir nome/label/image/profile antes de start. Inspect usa
Go template que exclui Config.Env, não captura senha em metadata.
Binding exato loopback e porta1..65535. Readiness do PG por até60s, conexões
com connect_timeout2 e statement_timeout5s; isso é polling de readiness,
não retry de escrita/start. Registrar versão real16.x; não pressupor16.15.

Runner separado, .venv Windows3.11.3 -I -B -u, stderr encaminhado a stdout
antes de importar pytest, stack temporária64MiB, pytest integral em tests,
JUnit fora do checkout, -p no:cacheprovider evita escrever novo cache pytest.
Nenhuma configuração do produto é mudada.
Ambiente novo contém apenas DSN gerado para este container; não usar banco
existente. Senha/DSN nunca em argv. Confirmar exit0+XML válido, zero falhas/
erros e nenhum skip por DSN; auditar individualmente skips de plataforma.
Além disso, exigir por classname/nome os5 casos novos e12 D-115 existentes,
cada um presente uma única vez, sem skipped/failure/error, independentemente
da mensagem de skip. Lista completa em EXPECTED_CASES, persistida como
required_cases_passed no resultado. Ausência/duplicata reprova o gate.
stdout capturado em memória e senha redigida antes de persistir; XML/log
final varridos pela senha; qualquer ocorrência reprova o gate, mesmo se
redigida. Não chamar isso de prova sobre toda RAM/host/logging do Docker.

Manifesto src/tests/docs-poc Python antes/depois deve concordar. Não editar
esses fontes durante a rodada. Se pytest travar/ser morto/faltar XML, o
gate falha; o helper supervisiona o processo direto, não prova ausência
universal de descendentes após falha. Não reiniciar teste automaticamente;
root precisa inspecionar/resolver qualquer recurso incerto.

Finally: inspect só ID/nome esperado e label/task/image; nunca apagar
recurso sem identidade. Stop próprio se Running; confirmar stopped;
rm -v só desse ID e conferir ausência dos volumes próprios (sem remover
volume por nome). ps global ao fim vazio, sem interferência. Se qualquer
cleanup/inventário/manifesto incerto, outcomeFAILED e não admitir nova rodada.
Resultados/erros anteriores preservados, sem excluir outros containers.

## C — restaurar somente app próprio e com identidade confirmada

Com processo do gate terminal, auditar result.json e codes/volumes/ps.
Se initial=active, preservar app. Se foi start próprio, conferir novamente
PID/FileTime iguais aos registrados; se diferente ou recursos incertos,
não parar app desconhecido. Só então registrar stop_allowed=true.

```powershell
& 'C:\Users\w.filho\Desktop\codes\mask\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-worker-errors-pg-20261023-3ce74efa\restore_desktop.py'
```

Restore consome a permissão antes de agir, exige resultado do mesmo task e
cleanup/inventário verdadeiros, valida CLI/helper/config/contexto, reconfirma
ps vazio e executa um desktop stop --timeout20 sob bounded25s/16KiB.
Sem force/kill de app/WSL ou apagar imagem.
A senha descartável existe em Config.Env do container até rm -v, nunca é
lida pelo template. Se cleanup falhar, não reutilizar senha nem iniciar outra
rodada; root deve resolver o recurso pelo ID exato/ownership antes de seguir. Depois, observação de processos
até10s confirma Desktop off; stop exit0 sozinho não prova ausência.
Snapshots não previnem ação concorrente futura; interferência conhecida
aborta, não se sobrepõe a usuário/terceiro.

## Critério e escopo

Fechar o gate PG somente após resultados reais e auditoria; copiar evidência
sem DSN/senha para revisão Claude2. SOURCE/servidor reais, saúde OK/IDLE positiva
e fatal após término do backend; teste53 faked não é OOM nativa.
Typed mensagens fixas diferem do legado, que mantém textos/classes antigos.
CONNECTION também é falha local/driver sem SQLSTATE; não prova causa de rede.
Conexão já fechada antes do cursor pode gerar DatabaseError genérico anterior:
worker futuro deve tratar falhas não reconhecidas como fatais, sem retry.

Não fecha B-1/B-2/D-090, não cria worker/IPC, não libera SQL PGWire/Admin v2
nem produção. Sem segundo escritor/job novo/commit/push/deploy.

## Revisão do procedimento antes de executar

Primeiro parecer51ea0d85 aceitou sequência/ownership com P1 (guard -O) e
P2 (17 integrações explicitamente passadas). Ambos corrigidos antes de
qualquer ação, com oito novos testes puros. N1 cache desabilitado e N2
senha temporária em metadata/cleanup documentados; escrita invoked mais
forte com fsync/replace. Rerevisão51ea0d85 fechou P1/P2 e leu os scripts
externos completos; sem bloqueador para uma rodada sob condições A/B/C.
APP_READY só após90s observados e PID/FileTime consistente, escrito por
replace atômico; antes de C comparar novamente a identidade e depois do
stop observar ausência por até10s. Hashes reconferidos a cada passo.
Se start ocorrer mas registro de identidade falhar, não parar app incerto:
arquivo fica START_RESERVED e C recusa; registrar app possivelmente ativo.
Ainda nenhuma execução de start/CLI/banco neste ponto do documento.
