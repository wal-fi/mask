# PG16 público — preparador separado da execução

2026-10-30 sob delegação. Variante explícita do preparador8e024, original
consumido intacto. Novo `docs/poc/pg16_public_prepare.py`, SHA-256
`02d1dadd0772a873943f434423bb103ad8781ffaf4dea44274c49e2e71846c7c`.
Fixa entradaa6089275 e launcherbfff5171, sem invocar mains antigos ou atuais.
StateFRESH/task/pins/imagemcf78/medida única exatamente no schema da entrada.
Blueprint computado sem readmissão de imagem e sem fonte administrativa.

command_for só confere path/nome de raiz/launcher pinado/tamanho do argv e
retorna python -I -B entry root. materialize é explícito, mkdir novo e arquivo
attempt.json xb/flush/fsync, nunca reutiliza/limpa/sobrescreve. Não inicia
clock/loop/Docker/PS/PG nem chama entry.prepare/drive. Proposta concreta e
revisão antes de raiz real continuam pendentes.

17 casos aprovados em2,19s, Windows3.11.3, somente arquivos públicos pequenos
de pytest/fakes. Cobrem schema/blueprint, task inválida, nome/parent de raiz,
comando isolado sem criação de raiz, double materialize, conteúdo existente,
pin adulterado antes de exec e falha de fsync sem sucesso. Nenhum subprocesso
ou raiz operacional criado. Estáticos iniciais encontraram só dois ajustes
de lint e retorno Any no harness, corrigidos antes dos gates finais.

Preparador e direção EXPORT-DESIGN aceitos na revisão55166, sem bloqueador no
escopo isolado. Três precisões do exportador foram registradas no desenho
antes do código. Ruff e mypy311/314325 limpos após os ajustes do harness.
Nenhuma proposta real/raiz/comando de execução materializados ainda.
Fonte/pins/raízes consumidas preservadas; Gateway indisponível. B1/B2/D090/C1,
SQL, serviço e produção continuam abertos. Sem job/quota/outro escritor.
