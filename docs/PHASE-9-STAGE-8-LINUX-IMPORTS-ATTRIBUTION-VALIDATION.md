# Etapa 8 — associação nativa por identidade, somente laboratório

**2026-10-21 — vínculo de `_openssl` medido; controle ainda inconclusivo.**
Plano: `PHASE-9-STAGE-8-LINUX-IMPORTS-ATTRIBUTION-PLAN.md`.
Terceira rodada preservada com o erro FILELESS_UNATTRIBUTED/_openssl;
ela não será relabelada como sucesso. Este código não foi usado nela.

## Código e regressões

Somente o probe diagnóstico e seu teste mudaram funcionalmente neste lote.
Uma associação constante para `_openssl`, extensão exata _rust e arquivo
_rust.abi3.so da cryptography. Tipos exatos ModuleType antes de qualquer
leitura do alvo/provider; dicionário exato, vínculo por **is** e mesma
entrada em sys.modules. Provider precisa de __file__ str no próprio dict,
origem/owner/caminho exatos pelas regras antigas; nada de import novo,
__getattr__ dinâmico, ==, nome/prefixo liberado ou origem fora da árvore.
Tag attached-by-identity explícita, não __file__ inventado ou autoria
independente. No registro pré-execução desta seção o provider ainda não
havia sido comprovado; o resultado runtime está na seção da quarta rodada.

Tipos hostis também não são consultados em audit_context. Erro mantém
schema fechado e parada75. Outros nomes fileless não são liberados; alvo
file-backed passa pela regra normal. Contraprovas de igualdade enganosa,
cache divergente, provider ausente/fileless/path/owner errado e atributo
de segredo não consultado. Treze casos inicialmente2 falhos/11 recusas
corretas; um caso adicional cobre __getattr__ no diagnóstico do erro.

**170 passed** relacionados, Ruff src/tests e E/F/I/B/UP dos PoCs verdes,
format249 arquivos, mypy strict3.11/3.14 em247 arquivos verdes. Houve um
diagnóstico Ruff PLW1641 no double com ==, corrigido adicionando __hash__;
não houve mudança de regra/configuração. Nenhuma suíte PG16 integral,
frontend, pacote operacional ou runtime3.14 foi medido neste lote.

Plano e código/testes revistos sem bloqueador pelo Claude2 na sessão51ea0d85.
Recomendou conferir offline path/owner antes da rodada; feito: linha exata
da árvore tem14.389.392 bytes/hash3d642366...c9501a1, arquivo atual idêntico,
e owners.cryptography=cryptography no runtime.json congelado da terceira
rodada. Nenhuma mudança no código para essa conferência. Uma única quarta rodada
identificada, mesma imagem/árvore/cotas/perfil: controle e AS32 só se
normal. Qualquer diagnóstico para; nenhum ajuste até verde. Sem banco,
SQL, src, worker integrado, dependência, commit/push ou produção.

Fontes da quarta rodada (não usadas nas anteriores): probe
`383fc7b05211f0198aa0c28fd785962797270af486fcd9be12815f188b00f680`,
observer `6a446e5fad7752e6527f17d9a6e542fee4792293d20233b9cbe77bc956f59fa3`.

## Quarta rodada — identidade medida, próxima lacuna explícita

Raiz própria `%LOCALAPPDATA%\Temp\maskgw-linux-import-run-20261021-6nlcuj0q`;
container único `2d2d8c0123a03d720daa69e12bbc8594fdb246feafdc7546566fa2370e3b7581`.
Mesmos engine29.7.2/Linux/amd64, imagem em cache/árvore e perfil, inventário
vazio antes; sem download, banco ou alteração de fonte depois de começar.
Controle5,219s/lote5,578s, Python exit2 medido, container exit0. Inconclusivo,
imports_fit_as32=false, **AS32 não executado**, limited.json ausente.

Primeira prova em runtime do vínculo: a linha da etapa1 é
`["_openssl","cryptography","attached-by-identity/installed/cryptography/hazmat/bindings/_rust.abi3.so"]`.
Ela só é emitida após os testes de tipo exato, mesma entrada/mesmo objeto,
dict e origem/owner/path verificados. Isso prova associação local medida,
não autoria independente, segurança geral do CFFI ou aceitação de produto.

A próxima entrada parou fail-closed:

```json
{"phase":"audit_error","stage":1,"module":"_openssl.lib","category":"FILELESS_UNATTRIBUTED","has_file":false,"under_installed":false}
```

Membro exit75/AUDIT_ERROR coletado. Inventário430 linhas,77baseline/
351etapa0/2etapa1/0etapa2; etapa0 tem end, etapa1 não tem end, etapa2 não
iniciou e native_check final não rodou. Não foi liberado `_openssl.*` por
prefixo, nem acrescentada nova regra para .lib depois do resultado.

Etapa0 VmPeak101.158.912 bytes virtuais (**não RAM**), VmSize97.697.792,
RSS59.887.616, thread1/fds[0,1,2], proc children disponível. Ready membro
VmSize19.718.144/VmPeak19.992.576; supervisor21.585.920/21.876.736.
Pico cgroup94.879.744, events max/oom/oom_kill=0/OOMKilled=false; sem
deadline ou exercício do teto192MiB. Não é pico completo ou cota calibrada.

Inventário final[1]/pids1, cleanup confirmado, container removido e engine
vazio reconferido. Desktop off antes/depois (start oculto/stop exit0); zero
processos Desktop/backend/build/Python depois. Fontes/cópias, árvore e
runtime.json intactos por hash, artefatos das quatro rodadas preservados.

SHA-256: summary.json
`df31fb39011e70982277453f84f6ec83b679fd3b2b449183cb731a1a04326a64`;
control.json `324e92f158d4997180b7cee69f72a23c19a373b3b2b11cae2c035e758f227415`.
Bundle sintético `docs/poc/evidence/linux-imports-attribution-20261021.json`,
com originais/hashes e430 linhas decodificadas pelo executor. Não é nova
execução nem validação independente do revisor. Fontes desta medição são
as383fc.../6a446... acima, nunca as das rodadas anteriores.

Próximo desenho separado: diagnóstico limitado do conjunto de entradas
fileless e suas relações de identidade, **sem aceitar novos objetos**.
Evita acrescentar regras uma a uma por suposição; plano ainda a revisar,
sem implementação/caso adicional. B-1/B-2/D-090/produção continuam abertos.

## Fechamento e auditoria do incremento

Claude2 conferiu o registro e bundle da quarta rodada, sem divergência ou
alegação acima do medido. O executor comparou semanticamente os três novos
bundles aos originais, decodificou seus inventários e conferiu por hash as
cinco fontes congeladas de cada rodada; nenhum desses hashes foi alegado
como cálculo independente do revisor. SHA do probe atual ainda383fc...,
exatamente o código da quarta rodada. Nenhuma modificação funcional depois
dela; plano batch permanece somente documental, revisado após A1–A5/U1–U5.

Baseline327 caminhos, fechamento336: dez existentes alterados (sete docs,
dois PoCs e um teste) e nove novos (seis docs/três bundles sintéticos), zero
ausentes, **zero src alterado em relação ao baseline desta conversa**.
Mudanças antigas do usuário foram preservadas. .venv/pyvenv.cfg permanece
`6e2514351382cfae93b50d0e64644884d45febbf6dbc6ed97bcf3cab6536ff82`;
tree.json preparado permanece8a60924c...196002. Helpers AS congelados iguais.

Gates finais repetidos:170 testes relacionados verdes, Ruff e format249,
mypy nos alvos3.11/3.14 em247 arquivos, diff check limpo (avisos LF/CRLF
anteriores, sem erros). Isso não repete/reivindica suíte integral PG16,
browsers, wheel/sdist ou execução runtime3.14 nesta conversa.
HEAD4a5e5560abb495898c9e1b8ca44ac2d155681015, origin/master **em cache**
5d173ea938eb12db33bc880bf67a2e81a208fd5e,0behind/1ahead. Sem fetch,
commit/push ou segundo escritor; .git segue efetivamente read-only.
Nenhuma cota observada ou job novo armado. Próximo passo sem nova aprovação
de usuário é implementar o plano batch revisado, ainda com revisão antes
da execução, sem permitir SQL ou declarar B-2/D-090/produção concluídos.
