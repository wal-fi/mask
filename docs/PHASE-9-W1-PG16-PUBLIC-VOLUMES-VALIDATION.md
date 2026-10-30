# PG16 público — núcleo puro da decisão de volumes

2026-10-29, sob delegação. Desenho60182 com precisões P1 confirmado22157;
nenhum bloqueador de desenho remanescente para o incremento puro/fakes.
T4 real3a274347 permanece consumida/aceita. Nenhum novo DockerCLI, raiz,
container, volume, PG/SQL, segredo ou processo do produto neste núcleo.

`docs/poc/pg16_public_volumes.py`, SHA-256:
`6e3827affcb1a02c00c365a54ecccae5d8e768c188d8232b699efa4c6ddad128`.
Sem caller operacional. Parser público bounded64KiB/256nomes/ASCII e nomes
Docker fechados; inventário imutável, duplicata/linha extra/control inválido
recusados. Decisão imutável de WITH_V/PRESERVE_EXISTING/PRESERVE_UNCERTAIN:
volume preexistente, inclusive hash anônimo, sempre proíbe-v. Mounts incertos
também proíbem-v. Retorna nomes observados/preexistentes, sem argv/CLI.
Diferença inicial/final só relata adicionados/ausentes, nunca libera recursos.

O chamador futuro deve provar primeiro CID/inspect próprios, registrar a
decisão antes de rm, bloquear start em volume inesperado e conferir nova
ausência/inventários/exit. WITH_V não é autorização de remoção ou aceite de
perfil; o núcleo não remove, inicia ou marca release/HELD. Fakes de CLI/rm
falhando/named remanescente ainda pertencem à integração futura, não foram
inventados como medidos aqui. Builder/perfil/fonte pública/supervisor faltam.

33 testes aprovados em0,27s no Windows3.11.3, só memória. Primeira execução
teve erro de setup/teardown porque pytest usou64KiB como ID e caminho de
fixture; IDs curtos corrigidos no teste, sem relaxar limite. Ruff src/tests,
lint restrito do helper, format318 e mypy strict311/314 em317arquivos limpos.
Não é runtime314, teste de Docker/PG, suíte integral ou prova de cleanup real.
Código aceito isoladamente pelo Claude2 (78090), sem bloqueador. Na integração,
bind tolerado pela decisão de-v continua proibido na aceitação do perfil;
inspect do próprio CID/exit0 inicial e premissa de um writer são obrigatórios.
Nenhum commit/push, quota/job/outro
writer. DesktopOff; B1/B2/D090/C1/SQL/produção abertos, Gateway indisponível.
