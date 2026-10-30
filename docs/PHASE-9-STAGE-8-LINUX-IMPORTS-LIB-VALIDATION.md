# Etapa 8 — associação exata do slot opaco, incremento de código

**2026-10-21 — código/testes revisados sem bloqueador, antes da execução separada.**
Contrato em `PHASE-9-STAGE-8-LINUX-IMPORTS-LIB-DESIGN.md`, revisado antes
dos testes na sessão somente leitura51ea0d85. L1(a) e L2 escolhidos sob a
delegação vigente. Nenhum Docker, import Linux ou SQL neste incremento.
As cinco rodadas anteriores e o desvio de procedimento da quinta continuam
preservados; nada aqui aprova retroativamente aquele procedimento.

## Regra restrita do laboratório

Só o nome `_openssl.lib` entra na regra antes de qualquer acesso ao objeto.
Exige candidato não-None, identidade com a entrada atual de sys.modules e
slot lib presente/não-None da âncora _openssl. A mesma função batch_anchor
revalida tipos ModuleType exatos, vínculo com provider Rust e owner/path
fechados. O parâmetro interno strict distingue erro inesperado (OTHER)
de identidade/origem insuficiente (FILELESS_UNATTRIBUTED); o batch conserva
o comportamento diagnóstico UNANCHORED. Nenhuma leitura de atributo,
igualdade, hash ou repr do candidato. No caminho próprio e no contexto de
erro não há consulta de tipo; no batch existe `type(candidate) is ModuleType`,
comparação de identidade do tipo que não dispara __class__ nem consulta
metadados de tipo. O batch também usa is para comparar slots.

Linha aceita recebe tag separada
`attached-by-identity-slot/lib/installed/cryptography/hazmat/bindings/_rust.abi3.so`
e owner da âncora. É associação por identidade, não arquivo próprio, tipo
CFFI, autoria independente ou atestado do objeto. Não é regra para prefixos,
ffi, wrappers, outras extensões ou os29 módulos ainda sem veredito.

No erro desse nome exato, has_file e under_installed são ambos null:
**não medidos**, nunca falso inventado. Só esse par nesse nome é permitido
pelo novo schema; bools/mistura nesse nome, ou null nos demais, são PROTOCOL.
Outros nomes conservam bools estritos/coerência. Supervisor e classificador
continuam inconclusivos e não aceitam inventário nem admitem AS32 pelo erro.
Os campos booleanos das rodadas1–5 são medições antigas, não reinterpretados.

L1(a) é restrito: os laços genéricos antigos PyO3/Cython podem acessar esse
objeto em outros caminhos, e bibliotecas importadas podem usá-lo. Nenhuma
promessa de processo global read-free. Esses caminhos não foram alterados.
Preflight interno obrigatório do observador é pré-requisito para qualquer
futuro caso real; naquele fechamento estava testado só com fakes.

## Contraprovas e gates medidos

44 testes novos primeiro:33 falharam contra o código anterior e11 passaram.
Entre as falhas: __file__ lido no objeto hostil, None aceito como cache-none
e schema/contexto ainda booleanos. Depois da implementação, **294 passed**
(250 anteriores/44 novos), sem skips/xfail. Só fakes em Windows/Python3.11.3.
Matriz: sucesso nos estágios-1/0/1/2;16 falhas de slot/cache/âncora/provider/
owner/path; None, igualdade enganosa, âncora alterada após sua linha;
erro inesperado e emissão falha sem leitura; outros nomes recusados;
null fechado, erro sem inventário e resultado inconclusivo no host.

Ruff src/tests e E/F/I/B/UP nos dois PoCs limpos; format252 arquivos;
mypy strict nos alvos3.11 e3.14,250 arquivos, sem erro. Os primeiros
diagnósticos do teste (branches/hash/dict genérico/formato) foram corrigidos
sem relaxar regras/configuração. Não é execução do runtime3.14, suíte PG16
integral, frontend, pacote instalado ou medição de contenção.

## Revisão e passagem

Código foi revisado somente leitura pelo Claude2 antes da rodada nova.
Modo/casos foram decisão separada, registrada e revisada. Não repetir a
quinta, inferir origem dos wrappers/29 módulos,
ou admitir AS32 a partir de inventário parcial ou batch.

Sem src/produto, worker, conexão, listener, banco, dependência ou configuração
nova; MCP legado preservado. B-1 fim a fim, B-2, D-090 gate2, SQL PGWire e
produção continuam abertos. Sem commit/push, segundo escritor ou job novo.

Primeiro parecer somente leitura: sem bloqueador ou ampliação do código;
F1 corrigido acima, pois o batch usa type(candidate) por identidade (não é
ausência total de consulta de tipo). Revisor declarou não ter lido o teste
inteiro nessa primeira passagem. A segunda revisão leu todos os testes e
fixtures usados, confirmou a fronteira sem bloqueador e recomendou mais uma
contraprova opcional do batch ancorado retornando LIB. Ela foi acrescentada;
total atual45 testes novos/295 relacionados. Não tratar leitura parcial
inicial como revisão completa.

Comparação AST com a cópia congelada93e654 da quinta confirmou só quatro
funções alteradas (audit_context, valid_audit_error, batch_anchor, module_row)
e o corpo antigo de module_row, depois da nova ramificação, idêntico.
SHA-256 do probe novo: e92acbacded3aeab72c8237a26bd9471a0e43a83358f250d8dd0933d63af9c1b.
Observador continua5f85bec9..., posterior e distinto do a0eb021 da quinta.

Plano separado LIB-RUN-PLAN revisado com R1: após abort de preflight não
há segunda tentativa sob esse plano (opção a escolhida), exigindo registro
e revisão próprios. O --run só pôde ocorrer depois da conferência final
desse fechamento, em lote posterior ao incremento de código/testes.

Posteriormente, a sexta rodada própria do plano foi executada uma vez,
após revisão final e preflights. Medição/evidência em LIB-RUN-VALIDATION:
controle normal e AS32 did_not_fit. As alegações sem Docker deste documento
são do incremento de código/testes anterior àquela execução, não do lote
posterior. Isso não altera os resultados históricos nem fecha os gates.
