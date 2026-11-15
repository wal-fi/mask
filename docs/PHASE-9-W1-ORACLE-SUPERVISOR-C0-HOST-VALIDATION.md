# W1: host e primeira qualificação nativa C0

2026-11-14, horário de São Paulo. Root revisou e executou as medições nativas; Claude2 escreveu o script, sem execução, na mesma sessão `51ea0d85-05bb-4d24-ba9a-c9627c3f832f`, `claude-opus-5-5`, esforço medium. Um escritor por vez.

## Escopo e autoridade

O usuário autorizou implementação W1 local e testes nativos isolados no Windows após revisão do contrato e das condições de contenção. Este lote usou somente os modos fixos TRANSPORT e C0. Nenhum Docker, PostgreSQL/SQL, credencial, rede externa, listener, estado16, tentativa consumida ou deploy foi acessado.

Host: `docs/poc/oracle9_w1_supervisor_c0_host.ps1`, SHA-256 `c695a68b6b3ea4b81ff5ab64249039f948ce9080288c81d81706f8c94bde810d`, 283 linhas/13.943 bytes. É uma sonda específica do SDK. Não constitui outro Owner, framework ou supervisor admitido.

Os parâmetros recebem o interpretador base direto previamente qualificado (103.192 bytes, SHA `ff9b6698…`); nenhum caminho local foi publicado ou enviado ao programador. O host abre quatro artefatos nomeados com compartilhamento de leitura, verifica os mesmos streams e mantém-nos antes do único Process/Start e até a saída e fechamento. Fonte C0 `43ffbf92`, qualificador `999f4a8d` e backend `10c9058f` permaneceram intactos. Pai de diretório, identidade completa de runtime e TOCTOU não foram admitidos por essa checagem.

## Sequência e revisão

Os oráculos NQ1–NQ3 foram declarados com a fonte ausente, antes de Claude2 escrever o script. São medições prospectivas de APIs existentes, sem alegação de RED artificial pela ausência de uma sonda.

Root leu as 264 linhas da V1 e todo o delta final. Antes de qualquer execução, parser PowerShell com zero erros, inventário de comandos/tipos, 21 chaves fechadas, um Start e no máximo um Kill, custódia, ordem e limites foram revistos. Os quatro casos do helper real de aspas passaram. Duas contraprovas do helper real de frames reproduziram classificação indevida de registros malformados; foram corrigidas. A fonte final passou em 11 casos de frames. Também foi corrigida a limpeza segura da instância cujo Start nunca foi tentado. Não se executou o corpo do script nesses testes de helpers.

As chamadas 25643, 22741 e 63067 terminaram com serviço success/is_errorFalse, sem denials, e foram recuperadas. Root confirmou zero escritores antes de cada medição. Nenhuma troca de conta/modelo ou contorno.

## Medições nativas, três invocações separadas

| Caso | Resultado observado | Duração do script |
|---|---|---|
| NQ1, digest esperado incorreto | REFUSED/PREFLIGHT_DIGEST; instance=0 e start_attempted=0; arquivos abertos fechados | 138 ms |
| NQ2, TRANSPORT | PASS/T127; 128 bytes + EOF; stderr=0 + EOF; saída natural 0; kill=0; disposed=1; assets_closed=1 | 314 ms |
| NQ3, C0 | PASS/C0_OBSERVED; 26 bytes + EOF; stderr=0 + EOF; saída natural 0; kill=0; disposed=1; assets_closed=1 | 432 ms |

Os tempos são observações desta execução, sem promessa de teto físico. Root verificou integralmente o recibo de NQ2 antes de NQ3. Houve uma instância S em TRANSPORT e outra em C0; nenhuma tentativa de Start no preflight negativo e nenhum retry. O recibo de cada invocação teve uma linha ASCII e respeitou o teto de 512 bytes, sem caminhos, argv, PIDs, mensagem original de erro ou bytes crus do filho.

TRANSPORT usou Python isolado, `-I -B -S`, ambiente filho esvaziado pelo SDK, sem importar o projeto: emitiu 127 bytes T e LF. Isso mediu compartilhamento do executável e transporte/EOF. C0, só depois dessa aprovação, leu os fontes mantidos abertos e executou o Owner público real: o caminho checado exige setup retornando None e estado READY, depois close retornando None e estado CLOSED. **Owner.start nunca é chamado.** Foram criados/fechados recursos de setup do backend; nenhum filho do Owner foi iniciado.

## Limites e gates restantes

O host mantém custódia em Start/saída incertos e não transforma fallback kill, silêncio, prazo ou UNKNOWN em PASS. Não há teto de parede demonstrado para SDK, filesystem ou Read síncrono; um escritor não observado poderia impedir EOF. Controles fora de fronteiras capturáveis, morte do host, leitura de inventário de descendentes e contenção externa completa seguem sem prova. O campo descendants permaneceu UNKNOWN.

O resultado qualifica somente este caminho C0 local e o transporte observado. Não admite S/G, kill-on-close com filho, canários NATURAL/TERMINATE, nem o conjunto N1–N16. B1/B2/D-090 gate2/C1/D119/TLS/ingressos/produção continuam abertos. **Gateway indisponível para produção.**

A suíte Python relacionada 2.083/estáticos 377 continua a medição do commit `5cf0035`. Não foi repetida para este script isolado; Python, frontend, pacotes e dependências não mudaram. A evidência deste lote é a revisão do script, os helpers e as medições nativas acima.

Recibos compactos, contrato, oráculos e revisão ficam em `poc/evidence/oracle9-w1-proactor-tests-review-20261112/`. Logs, snapshots e metadados locais do caminho do base permanecem fora do Git. Próximo lote: reconciliação pública somente leitura do observador/custódia externa antes de propor qualquer caso com filho; reutilizar APIs existentes, sem preparar ou executar esses casos agora.
