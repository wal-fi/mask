# HELD — captura e replay isolados, testes simulados

**2026-10-22 — núcleo isolado revisado sem bloqueador, somente fakes.**
Sob delegação vigente, não aval individual fictício. Sem nova rodada real,
worker/SQL ou fechamento B-1/B-2/D-090/produção. O plano loaded-as128 anterior
continua consumido e sua evidência é imutável.

## Entrega

Novo docs/poc/loaded_memory_evidence.py e teste próprio. Captura limitada a
duas linhas HELD<=1024 bytes, recebidas inalteradas pelo supervisor congelado;
delegação explícita de IO, pid dinâmico, sem __getattr__ genérico. Candidatas
sintáticas não são evidência positiva. HELD fora de posição dá relatório
negativo/lista vazia. Falha inesperada própria do tap o torna terminal/broken; supervisor
continua responsável pelo finally/cleanup, composição retorna fallback fixo.

Envelope novo loaded-as128-held-v1,<=65536 incluindo newline, original em
string ASCII com **bytes exatos**, SHA/tamanho reconferidos, linhas originais
escapadas no mesmo orçamento. Rejeita documento extra, duplicata/NaN, bool
em inteiro, chave/perfil/tipo errado e alterações de original/HELD/outcome.
Falha de serialização/cap/replay nunca devolve o positivo legado sem linhas.
Hash é integridade interna dos bytes, não autenticidade física dos fatos.

Replay usa validate_report do host e PressureProtocol congelados, não novo
classificador. Tabela fechada de ready/imports/pressão/platô/release/amostras/
pré-FINISH/completed; exatamente1 ou2 linhas na ordem dos alocadores, até4
amostras adicionais de descarte, nenhuma observação faltante/excedente.
Pico/limites corroborados por observações, relato do membro nos campos de
blocos/categoria/errno explicitamente **não** uma medição independente.
Relógio é lógico, não tempo medido; não prova EOF real, origem física, cota
total ou execução em Linux. SHA do host conferido antes de carregá-lo.

Somente fakes de IO/relógio e buffers pequenos neste lote; nenhum chamador
operacional, entrypoint ou observador atual importa o novo módulo. Sem factory
Linux, DockerCLI, thread/processo do laboratório, mmap/pressão, banco/conexão,
query, configuração/dependência ou mudança em src. Não se alteraram os dez
helpers congelados nem os testes/artefatos das rodadas anteriores.

## Revisão do desenho e testes primeiro

Claude2 somente leitura51ea0d85 revisou HELD-EVIDENCE-DESIGN antes do código:
E1 exigiu original em bytes exatos+SHA/tamanho, E2 tabela fechada do replay;
R-T1 delegação explícita, R-T2 fora de posição e R-T3 relato versus observação.
Incorporados antes do código; parecer permitiu testes primeiro com fakes,
não integração/carga. Revisor não executou testes.

Primeira coleta falhou pelo módulo novo ausente, sem alegar regressão antiga.
Primeira implementação:40 passaram/1 falhou por fixture inválida, que usava
JSON indentado com vários newlines, recusado corretamente pelo decoder antigo.
Fixture passou a variar espaços sem newline extra; parser não foi relaxado.
Expansão:54 passaram/1 falhou porque monkeypatch de json.dumps afetava também
o preparo de fixtures; isolado no módulo novo e expectativa calculada antes.
Nenhum desses erros implicou CLI/processo/carga.

Regressão adicional primeiro vermelha: MemoryError inesperado no decoder do
tap gerava um envelope negativo normal em vez do fallback previsto para falha
de captura. Fix: read marca broken antes de sair em erro inesperado, e novas
leituras falham fechadas; cleanup/final permanecem no supervisor e nenhuma
mensagem/causa/contexto original é exposta. Teste passou depois.

Fixtures novas normalizam só os detalhes parentais omitidos pelo fake antigo;
nenhum helper/teste antigo mudou. Descarte com cinco falhas foi ajustado para
16 observações válidas pelo host antigo, garantindo que a rejeição seja do
replay do core e não meramente do cap de contagem. Testes cobrem também1 e4
amostras adicionais válidas, preservação exata de bytes/espaços e erro de
serialização isolado sem monkeypatch em globais dos helpers congelados.

## Gates medidos antes da revisão

Windows3.11.3, .venv existente. Resultado provisório para revisão:

-56 testes novos passed em0,49s, sem skips/xfail;
-800 relacionados passed em5,16s (744 anteriores+56), seleção completa
  linux_as/linux_imports/loaded_memory, -o addopts=, sem deselect. Último
  refinamento da fixture de descarte repetiu os56; repetir seleção no final;
-Ruff src/tests e E/F/I/B/UP do PoC limpos; format257 arquivos conformes;
-mypy strict alvos3.11 e3.14,256 sources, ambos limpos;3.14 só estático.

Ruff apontou import/expressão do teste e mypy inferência de tupla vazia:
ajustados sem ignorar regras/configuração. Gates finais serão repetidos sobre
o resultado revisado. Sem suíte integral PG/frontend/pacotes repetida: não
há produto/dependência alterado e docs permanece fora do pacote.

Hashes provisórios, antes de revisão:

-helper:0744d6b5001e7c5d6746f423f71070b7cd3219d8b68267098a235c207b2ca9ad;
-teste:4ed352217023839b65af93d8b454911a8d510994517717065a840577c73807f4.

Próximos gates: revisão deste código/fakes, depois desenho próprio de captura
num entrypoint real e integração de host/perfil/argv/preflight/hashes/comando,
antes de qualquer carga futura. O núcleo isolado não revoga a limitação Q1
da rodada anterior nem fecha contenção total/pai/trabalho nativo/concorrência.
Sem commit/push/deploy, mudança de Desktop/ambiente ou outro escritor.

## Revisão de código: T1, corrigido antes da rerevisão

Primeiro parecer de código51ea0d85: sem bloqueador de segurança, E1/E2 e
R-T1–R-T3 corretos, mas T1 exigiu preservar erro do read delegado. A versão
inicial marcava broken e apagava diagnóstico DEADLINE/PROTOCOL com fallback.
Três regressões falharam primeiro: categorias originais perdidas e identidade
da exceção trocada. Fix separa io.read da captura própria: erro delegado vai
inalterado ao supervisor, que o sanitiza/publica em relatório negativo com
HELD vazio; só decoder/retenção próprios marcam broken/fallback. Regressões
passaram, cleanup/final confirmados e nenhum send posterior.

Nota menor incorporada: decode documenta que fallback retorna inconclusive,
nunca positivo. Hash do host em load_host é constante: mudança exige atualizar
a constante **e nova revisão**, não substituir fonte congelada silenciosamente.

Gates repetidos sobre o código corrigido:59 novos passed em0,45s;
803 relacionados passed em5,54s, sem skips/xfail/deselect; Ruff limpo,
format257 arquivos e mypy3.11/3.14 em256 sources limpos.
Runtime só Windows3.11.3/fakes. Novos hashes:

-helper:7f0307106e9a139f626c96b7bade14395863cd468f83e22730fceb57dc7d9f53;
-teste:09b43ba5962529447109cf78a792d06cb90c382d57f1802b8d15e1d73de208dc.

Rerevisão técnica51ea0d85 fechou T1, sem bloqueador residual no núcleo isolado.
Revisor não executou os testes e aceitou somente código/fakes, não integração
ou carga. Histórico dos56/800 anterior permanece acima, sem trocar números.

## Fechamento e limites preservados

Gates finais59/803, Ruff/format/mypy e hashes acima são do código corrigido.
Depois deles só documentos mudaram. Decode retorna fallback como inconclusive,
nunca como aprovação. Relatos HELD de blocos/categoria/errno continuam relatos
do membro; apenas consistência lógica e corroboração de pico/limites neste
núcleo. Tempo/EOF/origem física e domínio total não são provados por replay.

Próximos incrementos precisam desenho/revisão próprios para integração real,
entrypoint/host/perfil/hashes/argv/preflight/comando antes de qualquer carga;
o lote não modifica a evidência nem revoga Q1 da rodada já encerrada.
B-1 fim a fim/B-2/D-090 gate2, SQL PGWire e produção seguem abertos.

Baseline371 caminhos, mais quatro novos (desenho, evidência, helper e teste).
Somente seis documentos de estado existentes mudaram; zero src, teste/helper
antigo ou artefato anterior alterado. .venv/pyvenv.cfg e diferenças/arquivos
pessoais preservados. GitHEAD4a5e556, origin em cache5d173ea,0behind/1ahead,
sem fetch/escrita Git. Diff/whitespace limpos. Não houve DockerCLI, backend
Linux, processo/thread de laboratório, pressão real, banco/SQL, start/stop do
Desktop, instalação, segundo escritor, cota/job novo, commit/push ou deploy.
