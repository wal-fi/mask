# T4 — preparo de estado e comando públicos

2026-10-28: código em revisão, sem materialização operacional. Não cria
processo, thread, Docker, PG ou segredo; nunca chama entrypoint. Importa
somente definições pinadas de entry835c/host88e2/v2b593/program4bc. As duas
raízes W1 consumidas continuam intocadas.

`docs/poc/w1_bootstrap_t4_prepare.py` constrói estado fechado FRESH para
task32, seis pins históricos/cincoT4, imagem621 e sete comandos/medidas.
Comando somente Python do venv pinadobfff,-I,-B,entry/root exatos. Root só
sob Temp do usuário/data28/uuid32, mkdir exclusivo e attempt.json xb/fsync;
nunca apaga, substitui ou reusa root. Retorno contém apenas dados públicos
e hashes do estado/código, nenhum seed ou hash de seed. Sem main.

9testes/0,66s passaram em diretórios de pytest: sete casos/medidas, task
inválida, root fora do perfil, materialização pública sem invocação e reuso
recusado preservando bytes originais. Mypy src/tests307 limpos311/314;
helper só lint restrito e format. Ruff do teste corrigiu import antes do
fechamento. Runtime executado somente Windows3.11.3.

Próximo: aceite do preparador e delta N4; materializar uma única raiz/estado
FRESH com UUID/task próprios, registrar bytes/hashes/comando e revisá-los
antes de uma única invocação operacional T4. Nenhuma autorização nova é
inferida desta evidência; delegação e gates de segurança seguem vigentes.

## Proposta exata, ainda sem raiz operacional

Preparadorc789/9 e deltaentry835c aceitos pelo Claude2 como código. Achado
de label herdado da imagem corrigido no binding, conforme HOST-VALIDATION;
atualização somente de pins no entry8580df97/preparadorfda9be06 em revisão.

Proposta pública persistida **só no checkout** em
`docs/poc/evidence/oracle9-t4-prep-20261028/`: proposal.json, attempt.proposed.json
e run-once.ps1. Task255f1c284f296c836d930044bfbba53f e UUID da rootd5bd03a1
gerados independentemente; rootTemp ainda NÃO existe.2254bytes de estado,
SHA3e2849e3af1a991264cce51113cb3319c9623ad34b65e16a320ad3e5972cc15d.
Script018c7071fae49c871698058e7e1356e4c1308e68bffc5efaa85e33ae29654e76
confere fontes/Python/estado/root antes de chamar uma vez Python-I-B.
Comandos create continuam13049–13073chars, limite26000, sem alteração do
canário. Proposta/estado/comando e delta vão para revisão antes de mkdir/A.

## Primeira proposta REJEITADA, nunca materializada

Premissa de herança do label contradizia inspect real CID3/imagem4; ver
HOST-VALIDATION. Proposta d5bd03a1/task255f1c28, estado3e2849e3 e script018c
estão invalidados, com rejection.json adicional; originais preservados. Não
usar esses arquivos. Não houve mkdir da raiz, main, Docker ou nova medição.

Fonte revertida byte a byte para aceitos host88e220eb/entry835c2e21/prepc7892639.
Nova proposta pública independente em `oracle9-t4-prep-attempt2-20261028/`;
attempt2 refere-se à proposta, **zero rodadas Docker T4 até aqui**.
Root86e5417cd7958015ace880173d138553/task52cdd3407a6bcc71f77d8d2610c59e5c,
estado2254bytes/SHA2654800305d0159d005567d28016b66cb635e2f8566484369b9505dfce22373a,
script6ddb78bfc54d6c976b6152fe35b66e2c7b7cc0ab57201933c92ec1c904ba545c.
Valores novos; raiz ainda ausente. Em revisão antes de materializar/A.
