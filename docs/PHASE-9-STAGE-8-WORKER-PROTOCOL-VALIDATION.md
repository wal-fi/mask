# W1 — codecs privados do worker

## Atualização v2 — 2026-10-26

O registro v1 abaixo é histórico. A fonte/teste aceitos foram preservados em
`docs/poc/evidence/worker-protocol-v1-accepted-20261026.json`, SHA-256
eb9553886abdd79f7264c352ec4c9f82e516b97d255185314c65fe40934257dc.
Sem consumidor ou execução nativa do v1, a revisão da integração aprovou
MGW2/versão2 e RESULT vazio: D-113 é a única fonte do comprimento do frame.
O pai deve pinar o máximo da sessão antes do header D-113 e exigir DONE
correlacionado antes de expor o resultado. Sem fallback v1/cruzado.

O codec atual tem101testes; o loop privado e suas limitações são registrados
em WORKER-PROCESS-VALIDATION. As whitelists estruturais agora permitem só
esse entrypoint privado, sem chamador operacional ou alteração em D-113.
Fonte atual: cd6b3123ba0137ec85ff7d12d7fcefca3ff2b2168200c99a3cddde3e6d21fd09.
Não é prova nativa, conexão PostgreSQL ou liberação de SQL.

## Registro histórico v1

2026-10-26. Escolha técnica sob delegação, desenho WORKER-SESSION-PLAN
revisado pelo Claude2. **Não há loop/owner/worker operacional ou SQL nova**
neste incremento. Novo runtime/worker_protocol.py é puro, sem I/O ou chamador
em produção. D-111/D-113/D-114/D-118 não foram substituídos.

Cabeçalho12bytes !4sBBHI fechado, tetos por tipo antes de bodyallocation;
INIT tem metadata fixa+snapshot≤64KiB e nonce32; QUERY tem identidade/job/
prazo e SQLUTF8semNUL≤64KiB. GUARD/OPENED/ERROR/RESULTsize/DONE/CLOSE fixos.
RESULT anuncia frame D-113, sem codec novo de linhas. Erros de schema têm
mensagem fixa/sem payload; MemoryError propaga como falha fatal distinta.
Registros imutáveis/redigidos; SecretInit eq=False. Só categoria/forma de
can_continue é validada aqui; saúde/S1/prazo/ownership continuam do loop.

**100testes novos;700relacionados aprovados** no Windows3.11.3. Ruff/check e
mypy strict alvos3.11/3.14 no escopo codec+teste+test_result_frame (3arquivos)
limpos. Não é execução3.14 ou prova nativa. Cobrem máximos, mutação hostil,
header/flags/tipos/larguras, UTF8/NUL, corpus de erros, identidades, repr,
declaredlengths e deadlines não renovados. INIT máximo excede64KiB somando
metadata; é roundtrip de codec, não transporte de pipe já provado.

Primeira rodada81passed/2setup_errors/1failed. Os erros ocorreram com IDs
de parâmetros grandes/marcadores; IDs explícitos resolveram, sem atribuir
mecanismo não medido. A asserção reprovada esperava recusar SQL variável
válida com ASCII a mais sem fornecer o header original: teste corrigido,
pois é o transporte que deve ler exatamente o tamanho declarado. Não se
alega rejeição de SQL válida só por ser diferente de uma fixture anterior.
Truncamento UTF8/NUL e header incompatível são testados separadamente.

Revisão própria encontrou/corrigiu erro de classificação:2regressões
vermelhas antes do fix demonstraram MemoryError virando erro de protocolo
nos wrappers ResultLimits. Agora ele propaga sem conversão; owner futuro
deve encerrar por recurso, nunca reutilizar. Outros erros continuam fixos.

Revisão de código do Claude2 aceitou o codec. Duas precisões investigadas:
ResultLimits já limita TODOS os campos válidos dentro de !IIIHH; testes
de todos os máximos e5mutações de overflow confirmam recusa antes de pack,
sem política numérica duplicada. SecretInit mudou para eq=False; comparação
de tag no futuro será compare_digest. Revisão final aceitou esses deltas.

Um teste estrutural existente corretamente recusou o novo import de
result_frame. Whitelist agora acrescenta **só** o helper puro worker_protocol;
teste novo exige imports puros exatos e nenhum importador operacional. Não
foi alterada a lógica de result_frame.py, receiver, encoder ou worker_job.
O pin histórico ef776988... de tests/test_result_frame.py continua válido
para aquela versão; **agora** é32d767c34fc614089677d04523cd2b99b8fd1af229170321d30cc047a62eb654,
mudança da whitelist explícita, não alegação de arquivo ainda idêntico.

Pins finais:
- src/maskgw/runtime/worker_protocol.py
  b337153241a51a3e09dcc2ac663dfd25b6021eab451ae28d016e593229c99519
- tests/test_worker_protocol.py
  ec94091fb9a16cdee45eb28fe6516b9dd1efef5a3abbf855db6de9bd01b98749

Obrigações ainda pendentes do loop/owner: guarda antes de secrets, prazo de
cada mensagem decodificada, frame lido exatamente/validado/pinado e DONE
antes de expor, identidade/job corretos em cada resposta, descarte de
buffer INIT, S1, lease/ledger/reap/HELD e EOF/PID1. Não cria perfil C1 nem
fecha B-1/B-2/D-090. Nenhum DockerCLI/install/artefato novo/DB/segredo/rede,
commit/push/deploy, quota/job ou segundo escritor. Desktop permaneceOff.
