# W1: revisão do qualificador do Owner público

2026-11-14. Implementação pelo Claude2, sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço medium. Root revisou os oráculos, fonte, deltas e medições. Aceite somente deste chamador concreto com SDK falso; nenhuma execução nativa do qualificador ou admissão de S.

## Contrato e sequência

SQ1 e SQ2, preservados na evidência compacta, fixam a API fechada, custódia do chamador antes de setup, dois perfis benignos e orçamento global de turnos. O backend é o Owner público existente `10c9058f`; não se criou outro owner, guardião ou framework. Importar o qualificador apenas define objetos. `load_backend` verifica e executa os mesmos bytes capturados do irmão fixo, somente quando explicitamente chamado.

Root leu todas as 1.351 linhas dos primeiros oráculos e todo delta SQ2. O fake Request foi corrigido para respeitar a imutabilidade real antes do congelamento; foram reforçados limites dos relatórios e a contraprova de digest. RED132: seis sanidades aprovadas, 126 falhas exclusivamente pela ausência da fonte, zero erros/skips. Os hashes e a cronologia estão nos recibos de freeze; ausência de fonte não prova comportamento.

Depois de ler toda a fonte V1 de 705 linhas, os 132 casos passaram. Uma sondagem independente com o fake fiel reproduziu SQ3: o backend muda o atributo público `state` para HELD durante um controle, mas o relatório conservava NEW, READY ou RUNNING. O backend real contém essa transição em `_interrupt`; não se inferiu HELD a partir da exceção.

Oito novas regressões, quatro métodos vezes dois controles hostis, foram lidas integralmente e medidas RED contra a V1: todas falharam somente no estado desatualizado. Os 132 oráculos originais permaneceram intactos. Claude2 corrigiu só a fonte: a montagem do relatório lê o atributo público ordinário e o sanitiza também após controle. A AST comprova que somente `report` mudou semanticamente; as outras duas diferenças foram formatação.

## Invariantes revistos

- Backend, Request e Owner originais ficam na custódia do chamador antes de setup e continuam retidos em dúvida. Sem ledger privado ou consulta de métodos depois de CLOSED.
- Controles preservam a identidade original, error/first_control e UNKNOWN/CONTROL; nenhuma chamada posterior ao SDK, relógio ou cleanup. A observação de `state` é metadado público ordinário. Valores opacos não são convertidos por truthiness ou repr.
- Turnos globais, limite de leitura/retensão e EOF positivo fresco após inventário são distintos. Espera finita é orçamento de decisão, sem promessa de prazo físico do SO.
- OBSERVED exige a conjunção de saída esperada, accounting(1,0), members vazio, linha exata, EOF positivo e close retornando None com estado CLOSED. Canal inválido pode terminar em FAIL com cleanup positivamente comprovado; nunca vira sucesso.
- Falhas de SDK, inventário, estado ou EOF incerto não autorizam close. O chamador continua dono dos recursos; UNKNOWN não equivale a limpeza.

Não foi encontrado outro bloqueio neste incremento. Ruff completo sobre a PoC teve 20 diagnósticos fora do gate contratado preexistente; não foram ocultados por supressões, novos ignores ou troca do loader. Produto/testes mantêm Ruff completo e a PoC mantém E9,F63,F7,F82.

## Limites do aceite

Os 1.984 casos relacionados são fakes. Não certificam runtime/ABI/hooks nativos, startup incerto, descendentes, external-stop ou o conjunto N1–N16. A primitiva isolada de parada publicada antes é uma medição distinta, sem nova execução neste incremento. S/G, T5 físico e todos os gates de produto permanecem abertos; Gateway indisponível.

Próximo: definir a entrada mínima e a custódia externa para executar os dois canários com o Owner real, usando a primitiva de parada já medida. Revisar o contrato e as condições de contenção antes de qualquer execução nativa. Nenhum Docker, PG/SQL, credencial, rede externa, estado16, tentativa consumida ou deploy está incluído.
