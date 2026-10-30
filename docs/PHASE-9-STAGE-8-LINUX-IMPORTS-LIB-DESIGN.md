# Proposta separada — associação exata do objeto `_openssl.lib`

**2026-10-21 — desenho/código/testes revisados; execução separada registrada.**
Preparado sob delegação depois da revisão da quinta coleta qualificada e
da nota estática Q2. Depende primeiro do preflight obrigatório implementado,
testado e revisado. Nenhuma nova execução/cota/SQL por este documento.

## Fatos e limite de confiança

O batch da quinta rodada observou _openssl.lib como NON_MODULE (não-exato
ModuleType) e o mesmo objeto do slot lib do _openssl ancorado. Procedimento
externo teve desvio e não foi aprovado; o revisor permitiu usar a observação
qualificada só para preparar este desenho. Isso não mede tipo CFFI ou
autoria independente. Não tratar algorithms/modes como erros ou criar
regra para eles: nota estática aponta wrappers e a auditoria antiga deve
decidir suas origens, assim como as29 ainda não avaliadas.

## Contrato proposto, a revisar antes de código

1. Constante fechada só para nome `_openssl.lib`, slot `lib`, âncora
   existente _openssl -> extensão Rust no path/owner exatos já verificados.
   Não aplicar a prefixos, outros slots, wrappers ou todos os não-módulos.
2. Tratar o nome antes de **qualquer** leitura do objeto candidato, inclusive
   getattr(__file__), __dict__, metadados de tipo, ==, repr e audit_context.
   Escopo L1(a), escolha mínima: promessa só da regra própria desse nome,
   de seu contexto de erro e do batch. Laços genéricos antigos de ancestral/
   Cython ainda podem ler esse objeto em outros caminhos, e a biblioteca
   importada pode usá-lo. Não alegar auditoria/processo global sem leituras;
   não alterar esses caminhos neste lote. Leituras das rodadas4/5 preservadas.
   Revalidar apenas a âncora de ModuleTypes exatos; chave lib deve existir
   e valor não-None. Exigir `anchor['lib'] is module` e que module seja a
   mesma entrada de sys.modules no nome exato. None/ausência recusados.
3. Se as provas não fecharem, erro fechado sem fallback de getattr. Se
   fecharem, linha com owner da âncora e tag distinta
   attached-by-identity-slot/lib/installed/cryptography/hazmat/bindings/_rust.abi3.so.
   É **associação por identidade**, não filename próprio ou autoria do objeto.
   Nenhum método do objeto é chamado. Não generalizar ao resto do processo.
4. Forma L2 recomendada pelo revisor: audit_context desse nome não acessa
   candidato; has_file=null e under_installed=null significam não medidos.
   Nenhum campo novo ou falso booleano. Só permitir ambos null para module
   exatamente `_openssl.lib`; mistura null/bool ou null em outro nome é
   PROTOCOL. Demais nomes mantêm bools estritos/regra de coerência atual.
   Falha de identidade é FILELESS_UNATTRIBUTED; exceção inesperada é OTHER.
   Não reescrever/reinterpretar campos das rodadas1–5; schema é só futuro.
5. Regressões primeiro: slot ausente/None, cache ausente/divergente,
   == enganoso, âncora não verificada ou owner/path errado, objeto hostil
   sem leitura alguma até no erro, outro nome ainda recusado, e marcador
   adulterado (null fora do nome/mistura), âncora trocada depois da linha
   de _openssl e nenhuma leitura do alvo na recusa. Repetir guards/codec/
   contagens anteriores. Objeto hostil inclui __class__/__hash__/__repr__.
6. Revisão do plano e do código pelo Claude2 antes de nova rodada própria.
   Não repetir a quinta. Caso posterior deve passar preflight interno e
   externo do procedimento; modo/casos são escolha separada antes de executar.
   Origem dos wrappers e29 módulos não é inferida, controles podem falhar.

Prova futura mede a relação no novo runtime/rodada, não transforma a quinta
em procedimento aprovado nem fecha B-1/B-2/D-090/memória/produção. Nenhum
src, worker, listener, banco, dependência, credencial ou configuração nova.

Revisão somente leitura: núcleo considerado correto pelo Claude2; L1(a)
e forma null de L2 acima escolhidos sob delegação antes de código. Preflight
obrigatório já passou revisão/fakes em incremento próprio, não engine real.
Releitura final do desenho antes de testes/implementação; nenhuma regra
foi aprovada por uma rodada inconclusiva ou por este documento.

Releitura L1(a)/L2 concluída sem contradição na sessão51ea0d85; apto a
testes primeiro e revisão de código no próximo lote. Nenhuma nova rodada
autorizada por esse parecer. Reusar batch_anchor/código compartilhado para
não divergir a prova; incluir teste do host de que contexto null continua
inconclusivo e não abre AS32. Esses testes/código foram feitos depois da
releitura:294 relacionados passaram,295 com a contraprova opcional posterior.
Código/testes revisados sem bloqueador na mesma sessão; LIB-VALIDATION.
Rodada posterior teve plano/revisão próprios e está em LIB-RUN-VALIDATION:
controle completo e limited did_not_fit. Este desenho não é sua autorização
de execução nem aprova contenção ou produção.
