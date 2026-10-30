# B2-C1 — reconciliação pura de domínio e orçamento

**2026-10-23 — implementado sob delegação; código revisado sem bloqueador.**
Escolha técnica D-116, não aprovação individual inventada. Sem backend de SO,
worker, SQL, commit/push/deploy. B-1 fim a fim, B-2 e D-090 gate2 abertos.

## Escopo e checkpoint

master, HEAD4a5e5560abb495898c9e1b8ca44ac2d155681015; origin/master **em cache**
5d173ea938eb12db33bc880bf67a2e81a208fd5e,0behind/1ahead. Sem fetch/escrita
em .git. Baseline613 arquivos versionáveis + .venv/pyvenv.cfg, incluindo
capturas; alterações e evidências anteriores preservadas.

Windows nativo, Python3.11.3 da .venv existente. Não recriada, nenhum Python
sistêmico instalado; execução 3.14/POSIX não feita. Não houve DockerCLI,
processo de laboratório ou carga de memória, conexão, banco ou SQL.
Nenhum outro escritor. Código do MCP, listener, registry e UI inalterados.

## Contrato implementado

Plano DOMAIN-DESIGN revisto pelo Claude2 antes do código: D1 separa custos
dentro/fora, D2 exige identidade em registro fechado, R1 uma grandeza para
todo o ledger, R2 dono único de geração/candidato/snapshot fora de B.
Não duplica ledger, lock ou lifecycle; D-112 permanece dono dos créditos.

runtime/domain.py contém somente estruturas frozen, enums fechados e
reconcile(profile, plan, BudgetLimits). Cost é a entrada limitada do plano;
nenhum backend/plugin genérico ou registro por arquivo/ambiente/JSON.
Até64 custos, inteiros exatos até2^63-1, coleções/labels/capacidades limitados.
Verifica BudgetLimits pela validação existente, sem alterar objeto/ledger.

- Só duas constantes históricas no registro, por identidade: Linux HELD
  AS128 e Windows private32. Clone/evidence string/fixture são UNVERIFIED.
  Nenhuma entrada STRICT_PROVEN; ambos perfis atuais sempre NOT_READY.
- Perfil descreve evidência revisada, **não atesta SO/runtime vivo**. Plano é
  dado confiável/modelo, não medição de custo. Nenhum setting chama o núcleo.
- W>=cota imposta na mesma grandeza; uma reserva menor nunca é aprovada.
  AS/private commit/residente não são convertidos implicitamente.
- Não calcula/publica total se custos misturam grandezas. Totais IN/OUT são
  distintos; somente IN compara com seu domínio, OUT exige perfil próprio
  conhecido e suficiente, agrupando custos do mesmo domínio externo.
  Margem arbitrária não transforma cgroup transiente em prova estrita.
- IDs repetidos recusados mesmo entre BASE e GENERATION; identidade do mesmo
  custo físico sob IDs diferentes depende do plano confiável. Não há
  deduplicação semântica ou inventário físico neste núcleo.
- Geração/candidato/snapshot em shared_bytes, nunca também em B; BASE contém
  fixos sem token próprio. Quantidades por papel correspondem a BudgetLimits;
  supervisor/bootstrap dentro do domínio, workers/sessões/auxiliares/threads
  e auxiliares fixos entram na topologia. P>=2F+overhead.
- Verdict tem apenas bool explícito, motivos enum e totais numéricos.
  bool(verdict) recusa; repr dos insumos redigido. INVALID/FAULT não carregam
  entrada, erro ou cadeia original. Testes não provam recuperação de todo OOM.
- Pin, HELD, liberação e barreira continuam D-112/D-114. Futuro chamador
  precisa reconciliar antes de criar o ledger **e** cobrar nele valores pelo
  menos tão grandes; ainda precisa comprovar OS/cleanup/custo real antes de
  trabalho. Este núcleo não fiscaliza chamadas futuras.

O perfil Windows registra SHARED_ANON=GAP_OBSERVED (medição B2-B2a), não
UNKNOWN. Linux registra apenas cobertura individual dos dois mapeamentos,
cgroup transiente não certificado; AS e contador residente diferentes dão
UNIT_MISMATCH por construção. Composição futura exige contrato próprio,
não troca de rótulo para dar verde. Perfis não são defaults de produção.

## Testes e correções, preservando resultados iniciais

Testes de contrato escritos antes do módulo: primeira coleta falhou por
API ainda ausente (não finding/regressão de produto entregue). Na primeira
execução, uma fixture nova tentou release de sessão LIVE; corrigida para
begin_drain antes de release, sem alterar D-112. Estilo/tipagem iniciais dos
novos arquivos foram corrigidos antes dos gates finais.

Revisão própria acrescentou três regressões primeiro, todas vermelhas:
1. custo OUT residente misturado a IN AS ainda devolvia1438/100/1538 como
   total numérico; agora recusa antes da soma e totais0;
2. AS_VIRTUAL podia ser reetiquetado como PRIVATE_COMMIT;
3. JOB_PRIVATE podia ser reetiquetado como VIRTUAL_ADDRESS_SPACE.
Kind e grandeza agora precisam concordar, sem autorizar conversão.

Primeira revisão de código51ea0d85 aceitou núcleo isolado com correção F1:
Windows shared era UNKNOWN apesar da lacuna medida. Teste vermelho
UNKNOWN!=GAP_OBSERVED, fix fechado e rerevisão confirmou sem bloqueador.
Adicionada contraprova de ordem posicional dos dez vetores.
As notas sobre unidades Linux/IDs/cobrança futura foram incorporadas.

| Gate | Resultado medido |
| --- | --- |
| Novos casos C1 |113|
| Relacionados antes de F1 |914 passed/12,60s|
| Relacionados finais após F1 |916 passed/12,96s, zero falhas/erros/skips|
| Ruff src/tests |aprovado|
| Format src/tests |261 arquivos conformes|
| mypy strict alvos3.11 e3.14 src/tests |261 arquivos, nenhum erro em cada|
| Runtime executado |somente Windows3.11.3|
| git diff --check |limpo|

Seleção final: test_runtime_domain, test_runtime_budget, test_result_budget,
test_result_frame, test_result_receiver, test_result_receive_primitives,
test_purity, test_plan_separation, sem seleção negativa dentro dos arquivos.
Contraprovas: tipo/overflow, clone, quantidades, limite exato/+1byte, grupos
externos, custos omitidos/repetidos, supervisor/fixedaux/tasks, saída,
reserva abaixo/igual/acima da cota, falha local e pin/HELD no D-112 real.
Teste estrutural de isolamento resolve imports relativos/absolutos e possui
sete contraprovas; não comprova ausência de toda importação refletida.
Único teste anterior alterado admite explicitamente domain.py como leitor
puro de BudgetLimits, sem liberar consumidor operacional.

Não executei suíte integral PG/frontend/browser: nenhum desses caminhos
mudou ou passou a chamar C1. Não transformar916 casos relacionados em
alegação de validação integral, runtime3.14 ou contenção física.

## Pacotes — sonda limitada de módulo, não aplicação

Raiz própria %LOCALAPPDATA%/Temp/maskgw-domain-package-20261023-c1f24dc8.
Build wheel/sdist sem isolamento/rede; rebuild do sdist fora do checkout.
146 membros do sdist validados antes da extração: sem caminho absoluto,
traversal/backslash/drive/link/tipo especial, teto1024 entradas/16MiB.
Wheel120 entradas; docs/tests/frontend/pessoais/stackdumps fora do pacote.
Nenhuma alegação de determinismo entre wheels ou isolamento de dependências.

Instalações em targets novos separados, --no-index --no-deps --no-compile;
dependências do interpretador existente. Ambiente subprocess reconstruído
por allowlist Windows padrão, PIP_NO_INDEX e PIP_CONFIG_FILE=nul, sem secrets
ou PYTHONPATH. Probe copiado para pasta externa, -I -B, cwd externo.

Sonda tests/domain_package_probe.py revisada antes do uso. Revisor apontou
P1: só reportar hash permitiria wheel obsoleto. Corrigida **antes** da
primeira sonda: bytes de todos os módulos maskgw carregados precisam ser
iguais ao checkout revisado. Nos dois targets:39 módulos vindos apenas do
target, source_match=true; domain e budget com hashes idênticos aos fontes;
dois perfis NOT_READY. Fixtures numéricas da sonda não são calibração/default.

Wheel/sdist iniciais foram construídos antes do checker, exit0 medido pelo
executor na chamada6790aa; por isso esse build não integra a lista commands
do result.json. A entrada build-sdist é o **wheel reconstruído do sdist**,
exit0. Instalações/sondas positivas exit0. Duas contraprovas exit1
esperado: target próprio copiado com comentário obsoleto em domain.py
recusado por diferença de bytes; target checkout/src recusado antes do import.
Originais wheel/targets positivos e fonte não foram adulterados.

| Artefato | SHA256 |
| --- | --- |
| wheel |f73a335218ce2e7377107b0c8370b4eebd744e96cf3cac89889bac5f6cba5909|
| sdist |5b45596cefd6daa6f74f5253223be8f2a91a6b7fef94a859176645235ddae90d|
| wheel reconstruído |25954b071dc45d214dd815e80ca7ce93441b3bfca9044597a1264c921533cfdb|
| result.json original |cc4a2a2e8f65c137da14d05726219b527cc40ddf157fe83a3c271121957886c3|

Cópia revisável docs/poc/evidence/domain-package-20261023.json,
15.316 bytes/SHA14a5b19b1e44c734349daf4e3dc831e8ff4397211a0ce6af0302aa1632390d66.
Seis arquivos externos preservados com UTF8/hash/tamanho: resultado, programa
de validação/extrator e logs positivos/negativos. Executor mediu hashes/exits;
revisor não executa nem recebe atribuição desses resultados.

## Fontes e limites restantes

| Fonte | SHA256 |
| --- | --- |
| runtime/domain.py |414c9b0957f1d40ebb54ca080ec270fc5fdb59130e8415f8d63f63dcd629e91d|
| runtime/budget.py (inalterado) |510ca741cac660afb33ce5ae97da2685f472ebcac36e90dc8cd94fd2dcf1ed7e|
| test_runtime_domain.py |350c7b98e9f423fe3c67ff51a1553e4077cae2dcea6d100c28362c46d5a755d8|
| domain_package_probe.py |62ed224d188deed4e5e708dd80178426fbe16cb110df389ca1aaa330734ad3fc|
| test_runtime_budget.py |c15659c60563680dec017b45e40a6bca3b295cda3cc9c7313ae83a7a47de465e|

Nada aplica cota ou migra processo existente, calibra B/P, cria worker,
abre SQL ou comprova B-1/B-2/D-090. Próximo é domínio real incluindo pai/
auxiliares, contrato de cobertura agregado honesto e worker interno sob
esse domínio, com testes de falha; não repetir HELD. Destino de produção
ainda não informado; não escolher SO/servidor/credenciais por inferência.

## Revisão final e fechamento do registro

Claude2, somente leitura51ea0d85, conferiu código, F1, P1 e depois este
relatório, D-116 e cópia dos artefatos. Sem bloqueador para fechar C1 puro
e a sonda limitada; não executou testes/hashes/exits. E1 esclareceu o build
inicial separado e o nome build-sdist do rebuild, sem editar o raw. E2
acrescentou budget.py inalterado à tabela de fontes. Somente documentação
mudou depois dos gates finais, sem repetição das suítes ou pacote.

Sem revisão/cota pendente, job novo, segundo escritor, commit/push ou deploy.

Auditoria final: baseline613→618 arquivos; cinco novos (módulo, dois testes/
sonda, relatório e cópia JSON), nove alterados (oito documentos e o teste
de isolamento com whitelist explícita). Nada removido; fontes/helpers/
recursos/ambiente anteriores preservados por SHA. A reversão em memória
somente da whitelist reconstruiu exatamente o SHA anterior do teste, sem
reescrevê-lo. HEAD/referência em cache/0behind1ahead iguais ao checkpoint;
diff check limpo. Build só atualizou metadata/saídas ignoradas próprias.
