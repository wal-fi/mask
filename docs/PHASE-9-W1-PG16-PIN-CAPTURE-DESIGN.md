# Captura da medição de pins — desenho para revisão

2026-10-31, sob delegação vigente. Helper0195b1e4 aceito99073 e publicado em
1053379,37próprios/399relacionados aprovados. Este texto não executa helper,
não lê configuração/binários reais nem materializa evidência/tentativa.

## Modelo simples de execução

Criar `docs/poc/pg16_shell_pin_capture.py`, import somente definições. Em uma
execução própria Python3113/-I/-B/optimize0 e sem argumentos, o capturador
verifica SHA/arquivo do helper, executa seus bytes só como definições e chama
collect no **mesmo processo**. Não há subprocesso, thread ou loop no capturador;
quiet do helper permanece válido. Não chamar main do helper, da entrada ou
do Host, nem API de Docker/clock/processo/identidade/bootstrap/owner.

O capturador é o comando que grava a evidência, e o helper continua só
produzindo seu relatório público. Isso evita supervisão/pipes entre dois
processos e usa exatamente o measurement/collect aceito, sem monkeypatch ou
alteração de namespace. Main do capturador duplica a recusa runtime/argv antes
de imports não builtin; collect também exige o runtime antes das capturas.

## Tentativa e arquivo

Task pública fixa proposta:3eb3f616e3f24f3e943bd2135b0007ba. Diretório relativo
proposto `docs/poc/evidence/pg16-pin-cost-20261031-3eb3f616e3f2`, ainda ausente.
É evidência diagnóstica, não raiz operacional PG16/Oracle, sem attempt FRESH,
seed, secret ou comando de rodada. Qualquer falha consome esta proposta:
não repetir nem criar outra task/diretório sem nova proposta revisada.

Antes de medir, validar os pais existentes sob REPO sem symlink/reparse,
criar somente esse diretório por mkdir exclusivo e persistir invoked.json
XB/fsync. Qualquer existência/colisão recusa sem modificar conteúdo alheio.
Falha em admissão/captura/medição também consome a proposta. Sem limpar,
apagar, mover, sobrescrever ou reexecutar artefato consumido.

Helper0195, entradaafaf, Host8c e os13SHA públicos emitidos pelo helper ficam
fixados no capturador, sem parâmetros do operador. Conferir fontes públicas
ao vivo antes/depois; configuração privada continua lida só pelas funções
de pins aceitas. Hash do capturador é conferido pelo comando externo antes
e depois da execução; seu self-hash é só dado, não atestação de código rodado.

## Validação e publicação

collect retorna bytes públicos, mas o capturador trata a saída como não
validada: tipo bytes,0<tamanho≤16KiB,ASCII,uma linha,JSON sem duplicatas ou
NaN/Inf, canonicalidade exata, schema validado pelo helper e SHA públicos
iguais ao conjunto esperado. Sem executar outro Python para validar.

Nada cru é salvo. Relatório completo válido é gravado em result.json por
XB/fsync, depois capture.json referencia bytes/SHA/outcome/fontes. Só então
stdout recebe um resumo fechado e a saída é0 para MEASURED,1 para falha.
O orçamento futuro exige manifesto íntegro + hash/tamanho do resultado +
exit observado, não apenas result.json. Não há promessa de transação atômica
entre vários arquivos: persistência incompleta é NOT_PASSED e não é publicada
como evidência completa. Diretório parcial fica preservado para diagnóstico.

Se helper falhar com relatório NOT_PASSED fechado, preservar somente esse
resultado sem estatísticas parciais. Se houver saída inválida, erro de leitura,
fonte alterada ou persistência falha, usar categoria enumerada própria, sem
copiar bytes não validados, hash de payload privado, exceção/caminho/str/repr.
Sem regravar arquivo existente para tentar corrigir sucesso parcial. Nenhum
valor de configuração ou mensagem original vai para stdout/Git.

Uma falha de stdout do capturador retorna1 sem traceback, mantendo evidência
própria válida se já concluída. Esse caso não autoriza nova medição; eventual
recuperação da evidência exige revisão própria. O helper não ganha writer.

## Comando externo posterior

Antes da execução, revisar fonte/fakes e depois comando literal com SHA/cwd/
runtime/diretório proposto. Um único `python.exe -I -B <capturador>` direto,
sem Start-Process, shell dentro do Python ou processo verificador adicional.
O processo é possuído pela sessão da ferramenta; se demorar, aguardar a mesma
sessão, sem outro escritor/invocação. Não inventar teto absoluto de I/O do SO.

PowerShell do comando usa somente seu ambiente Process: salva valores sem
exibi-los, mantém whitelist SystemRoot/WINDIR/TEMP/TMP/USERPROFILE/LOCALAPPDATA/
APPDATA/HOMEDRIVE/HOMEPATH/SystemDrive/ComSpec, retira demais variáveis e restaura
no finally depois da chamada. Nunca altera User/Machine ou imprime valores.
Sem MASKGW/PYTHON/DSN/tokens/herança de secrets de sessão. Python é chamado por
path absoluto fixado, sem depender de PATH; stdout é resumo validado, stderr
é descartado. O comando registra a única invocação/resultado sem repetir.

## Fakes e gates

Testar import sem captura/efeito; recusa pré-import; parent/root/collision/
symlink/reparse; invoked antes de collect; fontes antes/depois; JSON duplicado/
não canônico/NaN/campo desconhecido/SHA privado/tamanho; falha no meio sem
partial; persistência/short-write/stdout falho; nenhuma chamada de processo,
thread, loop ou operação de entrada/Host. Fakes não leem config/binários reais.
Medição em si continua pendente até revisão do comando, uma vez só.

P2-4 de orçamento continua aberto. Depois da leitura real, compor estimativas
por caminho, máximos observados/margens/compilação fora de pins/emergência,
sem chamar fake de tempo nativo. Exportador da rodada, preparador/proposta/
rodada e B1/B2/D090/C1/SQL/Gateway/produção permanecem posteriores. Oracle e
Docker não são iniciados por este capturador. Sem quota/job/segundo escritor.

## Precisões34978 incorporadas antes do código

Claude2 aceitou a direção do desenho/fakes. Helper por lstat/tipo/tamanho/SHA,
namespace próprio e __file__ real; somente collect, depois validate sobre
JSON reparseado. Nenhum import pode criar thread/policy antes do collect.
Pins antes/depois:13arquivos públicos (entrada+host+7SOURCES+4TRANSITIVE) e
helper; demais fontes já estão nos pins internos. Self-hash não atesta código.

Mkdir de único nível e arquivos XB/fsync; sem alegar fsync de diretório no
Windows. capture.json contém só kind/task/caminho relativo/SHA públicos e
bytes/SHA/outcome/categoria do resultado; nenhum usuário/cwd/host/timestamp.
Parser rejeita duplicatas/NaN/Inf, exigeASCII/linha única/canonicalidade/schema
e conjunto13exato. Qualquer falha inclusive stdout consome task/diretório.

Comando usa o mesmo Python3113 cujos STDLIB_PINS são conferidos, preserva
USERPROFILE ou HOMEDRIVE/HOMEPATH para Path.home e não herda DOCKER/PYTHON/
DSN/tokens. Env Process restaurado sem impressão; exit observado0 obrigatório
junto ao manifesto/resultado íntegros para orçamento. Native leitura continua
pendente; fakes incluem interrupção collect, SHA estranho, root lógico errado
e manifesto sem caminhos absolutos. Nada disso libera orçamento/produção.
