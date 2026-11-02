# Sonda benigna de identidade — observação local

Data: 2026-11-02, America/Sao_Paulo. Base e origin/master:
`feb454137128d89c4c3105c81a35389544fd0ee8`, sincronizados por fetch;
árvore rastreada limpa. Lidos PENDING/CHECKPOINT primeiro. Nenhuma chamada
Claude2 da sessão/print/modelo ativa na conferência prévia.

Corpo e procedimento escritos pelo Claude2, Opus5.5/esforço medium, sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f. Revisor executou uma única vez o bloco
da seção3 de SHELL-NATIVE-IDENTITY-PROPOSAL após revisão e preflight, sob
delegação vigente. Nenhuma nova aprovação individual inventada.

## 1. Escopo executado

Apenas Python stdlib, via .venv/Scripts/python.exe -I -B -c, stdout no pipe,
sem tty, arquivo executável ou redirecionamento. Corpo não cria filhos,
threads, handlers, jobs ou arquivos explicitamente. O launcher da venv pode
ter efeitos próprios; nenhum binário/configuração local foi aberto para
conferi-los. Sem invocação da entrada ou do runner de controles, WinDLL,
raiz/nonce operacional, Docker/PG/SQL/serviço/deployment. Não houve rerun.

Texto extraído da proposta teve ParseInput0erros antes do lançamento.
Hashes SHA-256 do texto UTF8 extraído (não atestam argv/binário):
- bloco PowerShell: f7cedc3b589e6a282361ce7dadab18b18ea88af0df5a8cb49a7e83c33a7bd4e3;
- corpo Python: 8921191ef9abbfd4731e39ca36f24e79474a9d9fbb0ede33e27d5abbdfb16dfc.

## 2. Observações do harness e de metadados

| Item | Medido |
|---|---|
| T0 no relógio Windows antes do lançamento | 2026-11-02T22:59:37.2308659Z |
| Primeira amostra viva, após yield real | 2026-11-02T22:59:52.9762772Z |
| Segunda amostra viva | 2026-11-02T23:00:17.4058385Z |
| Intervalo entre amostras | 24.4295613s |
| Segunda amostra desde T0 | 40.1749726s, antes de45s |
| Pós-saída | 2026-11-02T23:00:31.9740977Z |
| Tempo observado T0→pós-saída | 54.7432318s, inclui orquestração |
| Saída terminal do exec | 0, sem saída adicional |
| Linha observada pelo tool | 118caracteres ASCII, com terminação de linha |

Uma linha JSON canônica de quatro chaves, kind/event fechados, par inteiro
positivo/distinto32bits, sem chave extra/duplicada ou NaN na representação
fornecida pelo tool. Dois yields do exec foram observados; nenhuma nova
sonda iniciou no polling. O período escolhido de45s não é limite de cleanup.

As duas amostras CIM foram filtradas somente pelos dois PIDs, solicitando
ProcessId/ParentProcessId/Name/CreationDate; sem enumeração geral, caminhos
ou linhas de comando. Ambos existiam, datas de criação estáveis, P chamado
python.exe e pai Q nas duas amostras, criação P posterior a T0, Q anterior
ou igual a P e criado na janela do lançamento. Q também chamado python.exe.
Isso observa uma família de dois python.exe; não certifica redirecionador,
binário, associação a jobs ou identidade do shell.

Após o término, consulta aos mesmos PIDs não encontrou as instâncias antigas.
Não houve kill, mudança de handle, reap externo ou recuperação nativa.
PIDs brutos ficaram somente em memória local do revisor, fora desta evidência,
Git e resumo. Datas locais servem só às comparações amostrais.

## 3. Limite do transporte e estado do parecer

O tool entrega texto agregado: não fornece os bytes brutos do pipe nem
captura stdout/stderr separadamente. 118 é o tamanho ASCII da representação
retornada, não uma atestação de bytes brutos. Não houve diagnóstico extra
visível; stderr vazio não foi medido por canal independente.

Resultado revisto: LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED. Vida/parentesco
amostrais e saída natural conferidos; PASS_SAMPLED integral não comprovado
(stderr separado e bytes brutos não medidos). Não houve observação contrária,
mas não se fecha gate estrito por inferência. A regra original aborta avanço
nativo por este resultado. Contrato prospectivo diferente exige revisão;
o rótulo desta rodada não muda retroativamente.
Não repetir a sonda para esconder/retroagir esse limite. Próximo incremento,
se necessário, deve ter contrato e procedimento próprios antes de efeito.

Native3s NOT_MEASURED, entry_gate NOT_EVALUATED; Gateway indisponível e
B1/B2/D090gate2/C1/SQL/produção abertos. Nenhum fonte fixo/estado16 alterado.
Tarefa histórica relida Disabled, sem próximo horário; última execução
01/11 às21h24m15Z/result0. A primeira leitura do revisor tentou formatar o
horário nulo e falhou; repetição somente leitura tratou nulo e conferiu o
estado, sem mudar a tarefa. Não houve quota/reset, outro escritor ou tarefa
nova neste lote.

## 4. Revisão Claude2 e precisão dos tempos

CLI92722 terminou0, somente Read, mesma sessão/modelo/esforço. Concordou com
os fatos amostrais e recusou PASS_SAMPLED estrito. Propôs o rótulo acima e
próximo lote documental para procedimento de controles com regra prospectiva
de observação agregada, sem replay desta tentativa nem wrapper adicional.
Root concordou com esse escopo; nenhuma invocação nativa foi liberada.

A linha já tinha sido parseada antes da primeira amostra: chegada anterior
a T0+15.7454113s, portanto dentro do orçamento de30s. Não foi medido um
instante independente de chegada. Os intervalos iniciais usavam Date.parse
do JavaScript, truncando frações além de milissegundos. Após a revisão, foram
recalculados dos mesmos timestamps com unidades de100ns; valores exatos na
tabela. Preservados timestamps originais, sem nova medição ou execução.

A leitura do código-fonte CPython registra tentativa de associação a job;
não prova sucesso no binário local nem herança/breakaway dos filhos futuros.
Condições de término do launcher pertencem aos desfechos externos UNKNOWN,
não a recuperação ou limpeza comprovada.
