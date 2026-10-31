# Captura do diagnóstico de pins — implementação e fakes

2026-10-31, sob delegação vigente. Baseline1053379 sincronizado; arquivos
pessoais não rastreados preservados. Desenho34978 aceito antes do código.
Capturadorde8f03910836799f90705265264e2f9fc71c878b517ff06b46c56b7150b0559d
aceito pelo Claude2 em20331, sem P1/P2, só código/fakes. Nenhuma medição real
foi executada neste fechamento. Não é liberação de orçamento/rodada/produção.

## Contrato e escopo

`pg16_shell_pin_capture.py` executa o helper0195 como definições e chama
collect no mesmo processo. Importa só sys antes da recusa de runtime/argv;
import comum não cria loop/thread/processo nem captura. Confere helper+13fontes
públicas antes/depois, e compara os13SHA exatos do relatório. Self-hash é
dado; o comando externo revisará o SHA antes/depois, não atestação autônoma.

Task3eb3f616e3f24f3e943bd2135b0007ba e diretório relativo fixos. Pais sem
link/reparse, mkdir exclusivo, invoked→collect→result→capture, arquivos XB,
short-write recusado, flush/fsync de arquivo; sem promessa de fsync de
diretório no Windows. Nenhum dado inválido ou hash desse dado vira evidência.
Parser exige bytes≤16KiB, ASCII/uma linha/JSON canônico sem duplicatas ou
NaN/Inf, validate do helper e SHA públicos exatos. Falhas próprias têm kind
do capturador, não simulam falha reportada pelo helper. Relatório válido de
falha do helper permanece idêntico, sem estatísticas parciais. Interrupção
ou persistência parcial consome a proposta, sem retry/overwrite/cleanup.

Manifesto traz somente task/caminho relativo/fontes públicas/outcome/categoria/
bytes/SHA de resultado validado. Reler resultado+manifesto precede o resumo.
Falha/short-write/flush de stdout retorna1, ainda que os arquivos já estejam
completos; não autoriza outra medição. Orçamento exige exit0 observado e
manifesto íntegro, não um arquivo de resultado isolado.

## Gates medidos

-34testes próprios/0,99s, nenhuma falha/skip/deselected. Fonte de teste final
  821b3803aa944fa41c8f390cfdc3e8c128e6d0009050738e54655348525aa7c3.
- Matriz relacionada12arquivos:426passed/91,17s, sem falhas/skips/deselected.
  Essa execução começou com33testes da captura; depois dela foi acrescentado
  somente o teste de import pedido em20331, coberto na seleção própria34.
- Ruff src/tests e helper E9/F63/F7/F82 limpos; format339arquivos do escopo
  src/tests+pin_cost+pin_capture conformes; mypy337arquivos alvos3.11/3.14.
  Runtime efetivo Windows3.11.3; nenhum runtime3.14 declarado.
- Parse/admissão/ordem/collision, tamper após persistir, ausência de payload
  privado, falha em cada arquivo, interrupção, seis recusas pré-import e três
  falhas de stdout. Construtores/helper de validação só definições públicas;
  collect/tempo/binários/configuração são simulados nesses testes.
- Estáticos iniciais encontraram um argumento de fixture sem uso e retorno
  Any em função bytes, corrigidos antes dos gates. Não houve finding de
  produto ou regressão vermelha de segurança alegada nesta implementação.
- Uma inspeção exploratória do formatador em todos docs/poc apontou duas
  PoCs SCRAM históricas fora do padrão atual (scram_poc/scram_vector_check).
  Fontes fixadas foram preservadas; não entram no escopo alterado/conforme.

## Revisão20331

Aceitou a captura com três P3: categorias de arquivo menos precisas (fonte
ausente pode ser INTERNAL, colisão PERSISTENCE); teste de import/quietude;
cache aquecido. Categorias seguem fechadas e não comprometem a recusa.
O teste adicional verifica a lista exata de imports e impede escritos/mkdir,
asyncio/threading/subprocess/multiprocessing pelo capturador. Quiet completo
continua obrigatório no helper; o teste não afirma criar processo isolado.
Pins anteriores aquecem fontes: a medição futura não será cold-cache nem
pior caso de SO. Não se ampliou prazo/cota ou alterou fonte consumida.

## Próximo efeito, ainda pendente

Comando literal em PIN-CAPTURE-COMMAND aceito54015 com escopo global explícito
aplicado, após P2 de41271 (stderr/Stop) e54015 (LASTEXITCODE sem escopo).
Ambos preservados no documento; nenhum efeito nativo executado. Um
Python direto -I/-B, ambiente Process filtrado e restaurado, cwd/SHA fixos,
sem PATH/DOCKER/MASKGW/PYTHON/DSN/tokens, home preservado. Diretório ainda
ausente; não existe raiz operacional PG16. Após commit, uma única
leitura, com falha preservada sem repetir. Depois: composição do orçamento,
exportador/preparador/proposta/rodada próprios. B1/B2/D090/C1/SQL/Gateway/
produção permanecem abertos ou indisponíveis. Nenhum Docker/PG/worker,
quota/job ou segundo escritor criado neste incremento.
