# Etapa 8 — preparação parcial do laboratório de imports Linux

**2026-10-21 — árvore preparada; rodada de imports posterior inconclusiva.**
Escopo deste incremento: preparar wheelhouse/árvore verificável antes do
harness de medição de imports. Plano em `PHASE-9-STAGE-8-LINUX-IMPORTS-PLAN.md`.
Não é resultado do caso controle/AS32, pacote operacional, contenção ou B-2.

## Checkpoint e revisão

`master` continua em `4a5e5560abb495898c9e1b8ca44ac2d155681015`, referência
local origin/master `5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind,
sem fetch. Lotes anteriores e arquivos pessoais preservados. Único escritor
é esta conversa; Claude2 revisa somente leitura, sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, sem limite de cota observado.

Primeira revisão do plano apontou I1–I6 (efeitos transitivos/proibidos,
origem/hash, completude de dependências, isolamento do sys.path, árvore
gerada no Windows e morte de extensão nativa). Contratos reforçados;
releitura aceitou implementar harness/preparar metadados, mas download e
instalação dependem de revisão do código real. Alternativas aceitas:
download HTTPS direto sem configuração/resolver pip e cap de ZIP antes da
instalação, sem fingir tamanho instalado conhecido nos metadados PyPI.

## Preparador e testes medidos

`docs/poc/prepare_linux_imports.py`: separado em metadata e prepare.
Nada de rede, instalação ou import nativo Linux na importação do helper.
ProxyHandler vazio (inclusive sem consultar registro Windows), redirects
recusados, TLS validado, duas origens fechadas; hash/tamanho em streaming,
rename só após validação. Pip só offline, target novo, isolated/no-cache/
no-deps/no-index/require-hashes/only-binary/no-compile. Checagem manual do
fechamento Linux/extras com cinco exceções explícitas de MCP/HTTP do produto.
Não é pip-check ou instalação completa.

Primeira rodada: **24 passed, 1 failed**, no caso ZIP com barra invertida.
Segunda rodada repetiu 24/1 mesmo após reforçar fixture: o leitor ZipInfo do
Windows normalizava o nome antes de validá-lo. Correção: validar também
orig_filename, e recusar controles/NUL. Não foi transformado em skip.
Houve também dois diagnósticos mypy nos novos testes, corrigidos com
Sequence/tipos explícitos. Rodada posterior: **25 passed**, Ruff do teste e
regras E/F/I/B/UP do PoC limpos; mypy strict alvos 3.11/3.14 em **246 arquivos**.
O alvo 3.14 é somente análise estática, não execução.

Comparação independente antes da preparação: **115 arquivos do produto** no
wheel D-115 idênticos byte a byte aos fontes/recursos atuais; hash
`de45edb1c8ea30bbccd9ef73cb9533c7d705fd1ade76cdb926f90a60c4b45449`,
419.631 bytes. Não reconstruído em silêncio; nenhum fonte funcional mudou.

## Metadados consultados, ainda sem wheels baixados

Ação metadata executada uma vez, pelo Python 3.11.3 existente do host.
Diretório novo próprio fora do checkout:
`%LOCALAPPDATA%\Temp\maskgw-linux-imports-20261021-a81ce6d2`.
Doze wheels oficiais selecionados por versão/tag, com hashes, tamanhos e
URLs de `files.pythonhosted.org` registrados em metadata.json. Soma declarada
com o wheel do produto: **20.485.214 bytes**, abaixo de 100 MiB. Zero wheels
baixados nesta ação. Tags x86_64 manylinux até2.34 ou pure Python, escolhidas
para CPython3.11/abi3. Compatibilidade da glibc efetiva ainda será conferida
no container antes da medição; não é certificação da plataforma.

SHA-256 de metadata.json:
`732ea99ad76658c52ac9c177362e36c77e4c2013652abaf0a438622cef8823af`.
Versões conferidas contra dist-info do host, com packaging26.3 já existente.
Confiança: TLS e hash vindos do PyPI; não há atestação independente das
distribuições. Nenhuma credencial foi usada/gravada. Docker segue desligado.

Revisão real do preparador apontou um bloqueador P1: faltava recusar raiz
dentro/acima do checkout. Corrigido em ambos os modos, com teste puro. Também
acrescentadas comparação inversa do inventário fonte/wheel e regressões para
colisão entre wheels, cap ZIP somado e launcher relocado. **28 testes puros**
passaram; o parecer condicionava a preparação a esse fix/teste, cumpridos
antes da execução. Não houve instalação prévia ao fix nem dentro do repo.

Ação prepare executada uma vez, exit0. Doze downloads com hash/tamanho
conferidos e o wheel existente do produto; pip offline com hashes/alvo novo.
Árvore resultante: **656 arquivos, 73.346.126 bytes**, abaixo de250MiB;
RECORDs completos, fechamento Linux/extras aprovado. As cinco exceções são
somente as declaradas (asn1crypto, fastapi, mcp, scramp, uvicorn do maskgw).
Dois entrypoints declarados: pgpp e cffi-gen-src, allowlist exata gerada antes
da checagem; launchers não executados. SSL_CERT_FILE/DIR ausentes no host.
`tree.json` SHA-256:
`8a60924c364882a1395d72415c1e166bca41da6a7208c1cfad32bbaede196002`.
Tamanhos são soma de arquivos, não blocos de disco ou consumo de memória.

Harness de imports implementado em `docs/poc/linux_import_probe.py` e
`docs/poc/run_linux_imports.py`, ainda sem execução. Novo validador de dois
mounts/comando; só helpers de baixo nível congelados são reutilizados.
Testes novos do harness: **25 passed**; com28 da preparação e46 anteriores,
**99 passed**, Ruff/format e mypy3.11/3.14 em247 arquivos. Um diagnóstico
de tipagem da lista de lambdas do teste novo foi corrigido com Callable.
Código real em revisão somente leitura na sessão indicada, antes de iniciar
Docker/casos. Nenhum número de memória do worker ou passagem de AS32 pode
ser inferido desta preparação. Estado posterior: após os reforços R1/R2 e
rerevisão sem bloqueador, 110 testes relacionados passaram. Uma rodada real
parou no controle inconclusivo, sem executar AS32 ou repetir. Resultado próprio
em `PHASE-9-STAGE-8-LINUX-IMPORTS-VALIDATION.md`; números acima descrevem a
preparação e seus gates históricos, não sucesso dos casos reais.

## Limites preservados

Não há SQL, banco, TLS real, runtime moderno, UI/browsers ou worker integrado.
Nenhuma mudança de pacote/dependência de produto, .venv ou Python do sistema.
O teste AS anterior não foi repetido. Suíte integral PG16 da D-115 é histórica,
não reivindicada por este lote. B-1 fim a fim, B-2, D-090 gate2 e produção
continuam abertos. Nenhum commit/push tentado nas permissões atuais de .git.
