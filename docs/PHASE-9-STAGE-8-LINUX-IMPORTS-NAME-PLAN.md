# Correção separada — guard diagnóstico não muda aceitação de módulos

**2026-10-21 — correção revisada e medida na terceira rodada inconclusiva.**
Rodadas anteriores e fontes congeladas não serão modificadas ou repetidas.
Evidência: `PHASE-9-STAGE-8-LINUX-IMPORTS-OBSERVABILITY-VALIDATION.md`.

A segunda rodada identificou uma recusa nova, inserida pela observabilidade:
audit_module exige nome ASCII sem hífen antes de chamar module_row. A
stdlib da primeira rodada inclui `_sysconfigdata__linux_x86_64-linux-gnu`,
aceito pela política original. Não alterar as regras de origem para ele.

Proposta mínima, sem atribuição nova de módulo nativo:

1. Remover apenas o uso de valid_module_name como condição de aceitação
   **antes** de module_row. Quem decide é a mesma política de origem da
   primeira rodada. Um módulo aceito continua no inventário de sucesso
   com o schema/limites anteriores, sem nova origem/whitelist de exceção.
2. valid_module_name continua obrigatório para refletir nome em audit_error;
   inválido vira null/OTHER. Erros não exibem nome fora da gramática,
   caminhos absolutos, exceções ou atributos. Nenhum erro é aceito como fit.
3. Regressão pura demonstra que nome com hífen e arquivo na stdlib tinha
   module_row aceito antes, enquanto o guard novo o recusa; depois comprova
   linha de sucesso idêntica à antiga. Erros com nomes inválidos permanecem
   fechados/null, usando origem indevida no teste para provocar auditoria.
4. Repetir gates puros/estáticos e revisão somente leitura do Claude2 antes
   de uma **terceira rodada identificada**, controle e AS32 apenas se normal.
   Mesmos limites, nenhum fallback, repetição automática ou mudança no fd.
   Se auditoria parar na causa antiga ou outra, registrar e parar sem AS32.
5. Correção futura de atribuição de módulo é outro desenho/revisão. Nada de
   produto, worker, SQL, banco, cota nova, commit/push ou liberação operacional.

Este plano trata só da regressão criada na observabilidade, não fecha B-2
ou D-090 e não torna o controle anterior aprovado.

Revisão somente leitura do plano/evidência concluída na sessão
`51ea0d85-05bb-4d24-ba9a-c9627c3f832f`; Claude2 recomendou fixar a linha
exata do módulo da stdlib e conferir o tratamento de todos os429 nomes do
inventário congelado. Dois testes novos fizeram isso e falharam contra o
guard novo, antes da correção. Removida só a condição antecipada; nome de
erro continua validado/null/OTHER, e tests de origem continuam iguais.
156 testes relacionados e estáticos3.11/3.14 verdes. Antes de outra rodada,
releitura do código/testes é obrigatória; Docker segue desligado.
