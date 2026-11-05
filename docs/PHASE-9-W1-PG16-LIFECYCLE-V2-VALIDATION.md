# Lifecycle privado V2 — revisão e validação com fakes

Data: 2026-11-05. Incremento sob a delegação vigente, não aprovação
individual inventada. Claude2 programou exclusivamente na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, modelo `claude-opus-5-5`, esforço
`medium`; o assistente principal revisou as alterações e executou os gates.
Última chamada de código, CLI5351, terminou0; terminal recuperado e zero
Claude2 ativo confirmado antes dos gates finais. Nenhum segundo escritor.

## Resultado e alcance

O módulo privado captura as referências originais de um caso, reserva seu
ciclo antes do setup e reserva uma reconciliação TREE antes do close. Só
libera o owner da lista original depois da prova de fechamento; a rejeição
TREE e os fatos do supervisor permanecem. Falha de integridade preserva o
contexto e o registro sem chamar limpeza legada. O fluxo não usa o
`_close_unstarted` legado, que libera por globais mutáveis: há um passo local
mínimo com as guardas e o registro originais.

Não existe consumidor operacional, loader, CLI, entrada, root, nonce ou
comando novo. Os testes compõem Owner/NestedJobOwner e kernels falsos em
namespaces novos. Não reexecutam a tentativa consumida. Os artefatos dos
testes usam os pins antigos apenas como fixture de schema: o verify completo
valida a lógica sintética, não proveniência de uma execução V2 real.

## Arquivos finais medidos

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| `docs/poc/pg16_shell_native_control_lifecycle_v2.py` | 14964 | `7bbf734c8b4a1fefe1617fc8c1cff2a5de0b33f8996eb98b0016233ab0b040cb` |
| `tests/test_pg16_shell_native_control_lifecycle_v2.py` | 30476 | `4027984417a9dc811fb26859fd87acedb36b108a6b45d0090de681c0a8d065f8` |

A fonte tem423 linhas. Comparação integral com a candidata580392b2 comprovou
uma única linha acrescentada: o par de identidade do ledger, com comentário.
As dez fontes congeladas, helperbb1f1984 e seu testead0742c0 foram conferidos
por hash e tamanho quando aplicável, sem alterações. Estado16 não foi
editado. Nenhum arquivo antigo de produto ou teste mudou.

## Histórico de testes e finding

1. O baseline final de funcionalidade ausente coletou42:3 passaram e39
   tiveram erro de setup por `FileNotFoundError`,3,137s. Isso não é prova de
   correção comportamental. Testead70c3b9/AST9f4955d9 arquivados em `red42*`.
   A única formatação posterior manteve a AST e as60 asserções originais.
2. A primeira implementação580392b2 passou42/42 em3,811s. Ruff e format
   passaram. A revisão independente encontrou a identidade do campo
   `owner.ledger` ausente do guarda. Mutar o dict original não exige nem
   justifica aceitar sua substituição.
3. A sonda substituiu o ledger por `{}` durante reconcile e retornou RETAIN:
   o código anterior lançou um erro legado novo e escreveu `held.json`, em
   vez de usar o erro de integridade pré-construído. O registro permaneceu
   retido, mas o contrato de recusa estava incorreto. Somente kernels falsos.
4. Claude2 acrescentou duas regressões, sem mudar a AST dos42 testes
   anteriores. RED44:42 passaram/2 falharam,4,324s, exatamente troca antes
   do ciclo e troca durante reconcile. Teste40279844 congelado antes do fix.
5. Claude2 corrigiu apenas o par `(ctx.owner.ledger, ctx.ledger)` em
   `_intact`. As44 regressões ficaram byte a byte iguais ao RED44. O dict
   original continua podendo mudar in loco; trocar o campo agora recusa.

Antes desse baseline houve uma colisão de caminhos no armazenamento falso,
reproduzida como CONTROL_PERSISTENCE e corrigida pelo programador com números
de caso distintos. Três diagnósticos de lint e uma quebra de linha de format
também foram corrigidos antes da implementação; nenhum ignore/supressão ou
enfraquecimento de asserção. O cabeçalho do teste descreve a etapa histórica
de módulo ausente; o estado final medido é o desta validação.

## Gates finais

| Gate | Resultado |
|---|---|
| Arquivo novo,44 casos | 44 passed,3,824s; zero falhas/erros/skips |
| Seleção relacionada,8 arquivos | 636 passed,56,863s; zero falhas/erros/skips |
| Ruff PoC | E9,F63,F7,F82 aprovados, conforme política existente |
| Ruff teste | Aprovado, seleção normal do repositório |
| Format |2 arquivos conformes |
| Mypy strict |1 teste, alvos3.11 e3.14 aprovados; PoC fora do mypy |
| Origem e integridade |10 fontes congeladas + helper/teste antigos intactos; teste44 congelado |

Runtime executado: Windows, CPython3.11.3. O alvo estático3.14 não significa
execução em Python3.14. A seleção relacionada inclui o helper, backend,
host, adaptador, runner, entry e projeção de HELD. Não é a suíte integral
do produto; não foram executados PostgreSQL, Docker, browsers, Node ou
packaging neste lote, que não mudou produto/frontend/dependências.

Uma sonda independente repetiu a troca de ledger na fonte final: erro
pré-construído, zero `held.json`, zero chamada adicional ao kernel falso,
ledger original com4 entradas e owner na lista original. Também confirmou
3 entradas inválidas da fase A recusadas com CONTEXT_REFUSED e sem cadeia.
É sonda fechada adicional, não teste nativo. A comparação literal inicial
do harness omitiu o comentário da linha nova; o diff integral esclareceu a
divergência e só a expectativa do harness foi corrigida, sem mudar fonte ou
teste. Resultados e snapshots estão em
`docs/poc/evidence/lifecycle-v2-review-20261105/`.

## Limites e próxima continuação

- As fontes originais fixadas são pré-condição; guardas não autenticam
  código nem contêm Python arbitrário, reflexão ou mutação dentro de helper
  legado confiável. Não há garantia de SO/API/ABI/NTFS/sinais reais.
- O EOF em cache é a limitação herdada do backend, não uma nova leitura
  posterior à quietude. O helper não foi afrouxado.
- LAST_CLOSE preserva AUDIT_INVALID e FAILED_LAST_CLOSE antes de TREE. O
  caso sintético TREE quieto terminou VERIFIED_REJECTED/FAILED_LAST_CLOSE;
  NORMAL terminou VERIFIED_REJECTED/TREE_UNPROVEN. DEADLINE/CLEANUP em
  TERMINATE continua inelegível e retido.
- O caller protegido ainda não existe. O `_case` antigo, cujo catch resolve
  o global mutável e pode chamar `_contain`, não serve para essa integração.
  A futura composição exige proveniência própria e schema/verificador
  revisado; pins v1 não podem atestar uma operação V2.
- A tentativa3f12dc584c29 continua FAILED_ONLY_OPERATOR_ABORT, consumida;
  identidade Nov2 continua LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED. Nenhuma
  fonte/root/nonce dessa tentativa foi reutilizada ou relida em privado.
- Próximo lote seguro: desenho somente leitura do caller protegido e da
  proveniência, sem código operacional ou novo efeito. Native3s
  NOT_MEASURED, entry_gate NOT_EVALUATED, B1/B2/D090gate2/C1/SQL e produção
  continuam abertos; Gateway indisponível. Alvo final já aceito: Docker
  local com Oracle Linux9.8, sem nova pergunta de destino.

Não houve nova quota/reset/job nem troca de conta/modelo. A autenticação401
histórica foi resolvida por login já presente e chamada API concluída; não
se trata de bypass de quota. A tarefa histórica permaneceu Disabled.
