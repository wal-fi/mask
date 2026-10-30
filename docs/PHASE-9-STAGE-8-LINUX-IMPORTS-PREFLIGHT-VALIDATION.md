# Preflight obrigatório — correção estrutural testada, sem nova rodada real

**2026-10-21 — código local revisado sem bloqueador, testado só com fakes.**
Plano próprio PREFLIGHT-PLAN revisado com P1–P4 pelo Claude2 na sessão
51ea0d85. A quinta coleta teve desvio de procedimento e não é aprovada
retroativamente por este incremento. Fontes/artefatos a0eb021/93e654 da
quinta rodada permanecem congelados fora do checkout; observador atual
é intencionalmente posterior. Nenhum Docker foi iniciado neste incremento.

## Barreira no código do laboratório

`docs/poc/run_linux_imports.py` agora exige readiness interna, seguida dos
checks de inventário vazio/imagem já existentes, antes de qualquer case.
Não depende de uma chamada externa ter dado certo. Flag interna só vira
True ao fim, é resetada no início/final de run e case a confere **antes**
de timer/pending/create. Não é token de autenticação ou prova criptográfica;
é fluxo confiável do mesmo observador, não configuração de produto.

Readiness usa no máximo3 polls,5s/16KiB cada,20s monotônicos incluindo
cleanup e intervalo1s; exige5s inteiros antes da próxima poll. Resposta
válida tardia vira LATE/NOT_READY, não admissão. Cleanup em voo pode passar
da janela; não há alegação de teto absoluto do SO. Watchdog120s começa
antes e impede abrir caso se disparar. Só TIMEOUT com finally concluído e
NONZERO repetem poll; cleanup/output/spawn/parse/perfil falhos abortam.
ps/imagem são uma tentativa cada. Server deve ser objeto com Os/Arch
linux/amd64 e Version ASCII limitada. Só esses campos e contadores/resultados
fechados são registrados, sem stderr/ambiente/texto de exceção.

Abort antes de criar container tem cases=[] e resumo próprio, não é medição
repetida. CLI_CLEANUP marca cleanup incerto e não tenta nova poll. Desktop
nunca é iniciado/parado pelo observador. Executor ainda deve conferir todos
os exit_code e só restaurar o estado que mudou, após checks seguros.

## Regressões e checks

30 casos novos, todos com CLI/clock/watchdog/case fakes. Primeiro23 deram
22 falhas/um watchdog já passava; mais sete limites adicionados. Cobrem
READY, timeout/nonzero com retry finito, janela consumida por cleanup,
resposta tardia, JSON inválido/duplicado/Server null, Os/Arch/Version errados,
OUTPUT_LIMIT/CLI_CLEANUP/OSError sem retry, ps/imagem falhos uma vez,
flag antiga resetada, flag ausente sem timer/create e watchdog disparado.
Retorno default --run e --diagnose preservados; fixtures de lifecycle que
chamam case isoladamente agora declaram preflight **fake** explicitamente.
Isso não é prova de preflight em engine real nem contenção do SO.

**250 passed** nos seis módulos relacionados (220 anteriores/30 novos),
Ruff src/tests e E/F/I/B/UP dos PoCs verdes, format251 arquivos e mypy strict
3.11/3.14 em249 arquivos verdes. Check inicial E501 e duas anotações de
teste corrigidos sem mudar regra/configuração. Suíte integral PG16,
frontend/pacotes e runtime3.14 não foram repetidos ou reivindicados.

Revisão somente leitura do código solicitada ao Claude2 antes de qualquer
tentativa real. Nota estática Q2 existe separadamente; LIB-DESIGN é proposta,
não implementada. Nenhuma nova origem de objeto/lib/wrapper foi aceita.
B-1/B-2/D-090/SQL PGWire/produção continuam bloqueados; sem commit/push.

Revisão do código concluída na sessão51ea0d85 sem bug/bypass bloqueante.
Limitações registradas, sem ampliar código por elas: o marcador fechado
INVALID perde subcausa (stage reduz a ambiguidade); attempt_count inclui
poll iniciada que falha no parse e por isso pode ser maior que attempts
(só resultados READY/NONZERO/TIMEOUT/LATE); watchdog durante readiness
pode ser INVALID; inventory_restored ausente em abort de preflight é
esperado, pois nada foi criado. Não alegar tentativas alinhadas ou engine
restaurado como medição em fakes. Nenhum sexto caso/tentativa real feito.

SHA-256 do observador **posterior e não usado na quinta rodada**:
`5f85bec97f2c55d7bae13e0663507d78e42698323a3ed460a49a51b45ce60e3e`.
Probe permanece93e654...; helpers congelados e árvore parcial preservados.
Próximo desenho separado é LIB-DESIGN, ainda sem código. Notas de origem
dos wrappers/29 módulos não viraram exceções ou vereditos aceitos.

## Auditoria final e passagem do próximo lote

Baseline336 caminhos,344 no fechamento: dez existentes modificados (sete
docs, dois PoCs e um teste) e oito novos (cinco docs, dois testes e bundle),
zero ausentes e **zero src alterado desde o baseline desta conversa**.
Bundle da quinta rodada comparado aos originais/hashes e às cinco fontes
congeladas; perfil de container AST idêntico ao da medição. Produto,
helpers AS e alterações antigas do usuário preservados. .venv/pyvenv.cfg
permanece6e251435...36ff82; nenhum pacote, Node ou Python foi instalado.

Gates finais250 relacionados/estáticos nos dois alvos verdes; sem medição
real depois da quinta, cujo desvio segue registrado sem aprovação. Docker
Desktop e Python encerrados, inventário restaurado antes do stop, não houve
cota observada, job novo ou segundo escritor. Git continuaHEAD4a5e556 e
origin/master **em cache**5d173ea,0behind/1ahead; sem fetch, commit ou push.

Desenho de .lib revisado com L1(a)/L2, pronto só para testes/implementação
seguida de revisão. Sem regra de aceitação, schema null ou novo caso
implementado por esse desenho ainda. Isso não fecha B-1/B-2/D-090/produção.
