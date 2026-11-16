# Entrada S: revisão dos primeiros oráculos antes de RED

## V2 — R1/R2/R3 revistos; RED193 medido e teste congelado

90134 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODO delta686linhas e comprovou AST de66definições não relacionadas idêntica à V1. Final1835ba817343cea1076fa95ec3add21d0828a074bfb8ac968f1e2dd8d0ef3fad,76.003bytes/1.878linhas. Antigo25bf/snapshot e provas iniciais preservados. Alterações de EOF são as motivadas pelo contrato público R1; nenhum outro assert foi relaxado.

Mesmas contraprovas com os classificadores REAIS novos: benigno aceito, impuro por builtins importado recusado SEM marker; dataclass/Enum legítimos aceitos. As17sanidades do fake passaram. Ruff/format e mypy strict win32311/314 em1arquivo PASS,314 somente estático. Root mediu TODO teste:193casos,17sanidadesPASS,176FAIL exclusivamente por ausência da fonte,0erros/skips/deseleções,1,609s. CADA mensagem foi conferida; nenhum erro de fixture/collection oculto. Recibo frozen-red e cópia raw local preservam o freeze.

Próximo único lote: mesmo C2 escreve SOMENTE docs/poc/oracle9_w1_external_job_entry.py, que segue AUSENTE neste fechamento. Teste1835/contratos/N-S/backend/adapter/C0/pins READONLY. Root lê TODA fonte antes de QA e integra fonte+teste juntos somente depois dos gates. Não publicar o teste RED sozinho. Atenção obrigatória na fonte: fresh available APÓS inventário e última leitura, inclusive com EOF cacheado; guardas de domínios públicos/adopt impossível, sem adicionar fake Owner ou patch para alcançá-los. A API RETAIN não prova main/park físicos; todos os nativos e gates de produto permanecem OPEN. Histórico abaixo.

## V1 — 1457 linhas lidas; oráculos ainda não aceitos

3963 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODO retorno e TODAS as1457linhas do teste25bf694e898b85c27f3199ed7a6bc501e28ac889c4ef9dc21ef035a29f625edc,60.079bytes. Fonte continua AUSENTE, teste local NÃO congelado/publicado. A estimativa de300casos do programador não foi tratada como medição: Root coletou179,exit0,sem erro de collection. Cinco sanidades só do fake PASS,0falhas/erros/skips,0,816s. Não é RED nem prova de produto.

Gates iniciais do teste: Ruff PLR0912 em _arm(13ramos); format pede assinatura da função de budget em uma linha; mypy strict win32311/314 com4diagnósticos cada: object.args na382, falta anotação de item na763, narrowing de dataclasses.is_dataclass em826 gera dois union-attr.3.14 somente estático. Recibo initial-gates e snapshot local preservados. Não alterar gates/supressões/asserts para passar.

## R1 — turno extra de EOF não é requisito do contrato

Root executou SOMENTE traços de métodos PÚBLICOS do Owner/N-S pinados com o EntryKernel FALSO do teste. Nenhum fonte da entrada foi criado, nenhum Owner foi substituído, nenhum efeito nativo foi chamado. São testemunhas de compatibilidade de contrato, não uma implementação substituta da entrada.

- Saída3*MAX_READ+5, quatro turnos: cada turno usa um wait(MAX_WAIT_MS) e um read(); depois vêm exit_code/accounting/members e available fresco. No4ºturno os5bytes finais são drenados e available retorna None DEPOIS do inventário; close retorna None+CLOSED, ainda com4waits/4reads. O teste atual obriga5turnos e manda RETAIN para budget4, embora ER2/ER3 não exijam outro wait para observar esse EOF.
- ReadFile scripted com ERROR_BROKEN_PIPE produz read()==b""; DEPOIS vêm inventário e available fresco None, e close None+CLOSED com um wait/um read. O teste budget1 exige RETAIN mesmo com essa observação nova. Read vazio SOZINHO não prova EOF; o available posterior é que o prova no contrato público.
- Recibo external-job-entry-initial-oracle-probes-20261116.json guarda cada retorno. Não é medição do kernel físico. Não obrigar chamada extra para satisfazer um oráculo mais estreito.

Corrigir só os oráculos motivados: permitir conclusão na mesma fatia quando houver available None fresco depois do inventário/última leitura. Cobrir negativo real com budget3 e saída3*MAX_READ+5 ainda não drenada; positivo budget4 e maior, sem exigir exatamente5waits. Preservar limite de um wait/um read por turno, budget compartilhado, bytes contados e obrigação de EOF fresco. Para read vazio, diferenciar ausência de observação nova de um available positivo de EOF após inventário; não exigir RETAIN quando o traço público acima permite close. Se o SDK fiel não torna a chamada available distinguível por usar cache, registrar esse limite e conferir ordem pela revisão/AST da futura fonte, sem forçar SDK artificial ou substituir Owner.

## R2 — os classificadores atuais aceitam efeito no import

Root aplicou as DUAS funções de oráculo REAIS a fixtures sintéticos .py.txt separados (API apenas com nomes/classes/funções inertes para classificar import; funções de entrada nunca chamadas). Benigno passou e não escreveu. Impuro executou uma atribuição que chama função de módulo; essa função usa __import__('builtins').open para escrever um marker controlado no diretório de evidência. Tanto o AST como o oráculo dinâmico aceitaram, e o marker apareceu. Nenhum fonte real da entrada foi criado. Mesmo recibo initial-oracle-probes.

Causa: AST permite Assign com Call em nível de módulo; builtins falsos só no dicionário __builtins__ não interceptam o módulo builtins importado. Path traps também não cobrem esse escape. Corrigir o próprio harness/checker, sem copiar uma implementação de entrada nem executar qualquer fonte de produto alterado:

- Conferência estática deve recusar execução em atribuição de módulo além das expressões constantes/definições/decoradores explicitamente permitidos. Não impedir dataclass/Enum legítimos ou definições de funções. Não transformar nomes em comentários/docstrings, como CloseHandle, em proibição de comportamento: conferir operações, não palavras soltas quando isso criar falsos negativos.
- Harness dinâmico deve cobrir os ports stdlib reais de abertura/compilação/execução usados pelo CORPO. Preparar a leitura/compilação do harness antes das traps, guardar os callables reais necessários e limitar/restaurar todas as traps antes de propagar diagnóstico ao pytest. Não fazer o próprio runpy/importador falhar antes de executar o corpo. Registro temporário de módulo pelo HARNESS, se necessário à semântica normal de dataclasses, deve ser explicitamente restaurado; não atribuir esse registro ao fonte.
- Extrair helpers do checker/harness se útil e acrescentar sanidades que aceitam definições legítimas e rejeitam a mesma família de efeito em import por builtin importado, SEM criar marker. É contraprova do oráculo de import, não fake de run_entry/Owner. O fonte da entrada continua AUSENTE. Root repetirá a mesma contraprova com o helper/oráculo real antes do freeze.

## R3 — reparos de gates e limites de cobertura

- Reduzir ramos de _arm por tabela/pequena seleção fiel, sem excluir pontos ou controle. Colapsar a assinatura pedida pelo format; não mudar pyproject.
- Tipar erro com o domínio apropriado/checar BaseException antes de args; anotar item de _forge sem cast/ignore; evitar narrowing indevido de is_dataclass no objeto dinâmico sem perder a asserção de dataclass. Sem supressões.
- Manter todos os demais oráculos, especialmente total2/0, C por papel, primeiro snapshot imutável, ack uma única vez, segredo não ecoado, custódia e RELEASE somente None+CLOSED. Falha ordinária de reader pode produzir INPUT e fechar READY antes de P, retendo a exceção observada; isso é a interpretação explícita escolhida para esta entrada.
- Os retornos impossíveis do Owner/N-S pinados não serão fabricados por patch de função ou fake Owner. Registrar a lacuna dinâmica e exigir inspeção dos guards na fonte futura; não declarar cobertura inexistente nem enfraquecer o contrato ER3.

Próximo único lote: mesmo Claude2/sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f/claude-opus-5-5/medium edita SOMENTE tests/test_oracle9_w1_external_job_entry.py. Read/Edit/Write restritos, sem comandos/execução; fonte/desenho/N-S/backend/adapter/C0/pins/testes antigos READONLY. Root lê TODO delta e repete probes/sanidades/gates antes de medir e congelar RED. Não publicar o candidato ou RED sozinho. Todos os gates nativos/produto continuam OPEN; Gateway indisponível.
