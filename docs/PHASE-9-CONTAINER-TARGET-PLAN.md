# Destino local Docker — família Enterprise Linux 9

**2026-10-23 — destino informado pelo usuário; preparo, não serviço disponível.**
O usuário pediu RHEL9.9 ou Oracle Linux9.9 em Docker nesta máquina e aviso
quando disponível. Máquina atual Windows, contexto Docker desktop-linux.
Nenhum servidor remoto/VM nova, credencial ou mudança no Windows foi pedido.
Isso identifica o destino local, sem fechar B-1/B-2/D-090 ou permitir SQL.
Escolhas técnicas restantes seguem delegação; manter revisor Claude2 e
root como único escritor. Não instalar Python/Node ou distro WSL no host.

## Estado medido depois da preparação

Base Oracle9.8 confirmada em execução pelo diagnóstico novo único, com
container próprio removido e Desktop restaurado. Primeira tentativa falhou
e permanece registrada sem causa atribuída. Ver
`PHASE-9-ORACLE9-BASE-VALIDATION.md`. Runtime Python ainda ausente; gateway
não disponível. Os parágrafos de descoberta/preparo abaixo são históricos,
não a afirmação de que nenhuma ação ocorreu depois deles.

## Versão: verificação e pendência restrita

Em2026-10-23, os índices oficiais RHEL9 e Oracle Linux9 listam9.8 como
update mais recente, sem9.9. Oracle9.8 tem release notes de junho2026:
- https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9
- https://docs.oracle.com/en/operating-systems/oracle-linux/9/
- https://docs.oracle.com/en/operating-systems/oracle-linux/9/relnotes9.8/

Consulta pública read-only, sem DockerCLI/engine/download/container:
DockerHub namespaces/library/repositories/oraclelinux/tags/9.9 → HTTP404;
tags/9-slim → HTTP200, atualizado2026-10-19T23:36:56.392023Z.
Índice:sha256:80729a271d86b1fd6848827fd8442c67c5770833ae3e5bf0fcd7538c72072e6d.
Descriptor linux/amd64:
sha256:d8c0a1f95f3394a2b40ece95dbff199cea94d06ac0ed354a7b88e96e2df5bb94,
size47.249.168bytes informado pela API (não espaço em disco descompactado).
Sem pull/executar imagem, ainda não se comprovou seu /etc/os-release.
Tag9-slim não significa9.9 nem fica silenciosamente aceita como substituta.
Não copiar token/credencial de registry para build ou código.

**Resposta do usuário em2026-10-23:** Oracle Linux9 oficial disponível9.8
aceito. Verificação adicional: tags DockerHub9.8 e9.8-slim também HTTP404;
imagens Oracle publicam tags de major como9-slim. Usar o digest candidato
acima e conferir /etc/os-release dentro da imagem **antes** de chamá-la9.8.
Revalidar origem/digest antes do pull; divergência de versão aborta, sem
substituição silenciosa. Ainda não houve pull/execução.

## Camadas que a evidência deve distinguir

Imagem Oracle/RHEL fornece userland/pacotes; o kernel do Docker Desktop
local vem de sua VM/backend Linux. Não certificar kernel RHEL/Oracle,
SELinux de um host Enterprise Linux ou bare metal por um container nesta
máquina. Registrar kernel, cgroup, runtime, arquitetura e distribuição
efetivos. Os testes Windows anteriores não certificam execução Linux.
Documentação Docker: https://docs.docker.com/desktop/features/wsl

Base pode ser Oracle Linux9 (pública) ou UBI9 (Red Hat); não usar imagem
RHEL que exija entitlement sem acesso já disponível, não cadastrar conta.
Oracle publica imagens próprias e pacote python3.11 em ol9_appstream:
https://github.com/oracle/container-images
https://docs.oracle.com/en/operating-systems/oracle-linux/9/python/python-InstallingPython.html
https://yum.oracle.com/oracle-linux-python.html
Versão exata Python/RPM e dependências Linux ainda serão resolvidas e
medidas na imagem, não herdadas de pip freeze Windows/pywin32.

## Caminho de entrega e guards

1. Fechar escolha de imagem/minor e verificar digest/origem/tamanho/runtime.
   Preparar build somente com wheel próprio, wheels de dependências Linux
   hashados e controles declarados. Contexto por whitelist, sem .git/.codex/
   .claude/docs/capturas/config/secrets/DSN, .venv ou frontend privado cru.
   Sem usar latest como identidade reproduzível. Não alegar determinismo de
   build por pin de base se RPM/pip ainda consultam repositório mutável.
2. Imagem e processos novos apenas; não migrar terminal, gateway existente
   ou Admin/MCP já aberto para limite de memória. Docker socket nunca será
   montado no gateway. Non-root, read-only quando compatível, cap-drop ALL,
   no-new-privileges, core0, pids/fd/memória/swap finitos; configuração e
   segredos externos. Volumes/aliases/revisões com ownership e validação.
3. B-2 no perfil real precisa incluir pai/auxiliares/listener/TLS/gerações e
   resultado em voo. AS não é RAM e memory.max documenta excesso transitório;
   não transformar cgroup normal em STRICT_PROVEN por uma margem. Nenhum
   perfil C1 atual pode ativar SQL. Novo contrato/alternativa deve ser
   justificado prospectivamente e revisto antes de implementação/pressão,
   sem converter medições FAIL anteriores em PASS ou omitir custos.
4. Worker persistente interno: D-111 snapshot, D-118 corpo do job,
   handshake/framing fechado e D-112/D-114 ownership/pin. Mesma conexão
   upstream por sessão; sem fallback para pai. Correlacionar identidade,
   job monotônico, prazos/EOF/erro/kill/reap e um job por vez. Testes
   controlados primeiro, depois PG16 descartável e imagem real sob guards.
5. Só após B-1/B-2/D-090: SQL PGWire, certificação de IDE, MCP multi-source,
   ativação Admin v2 e modo de serviço foreground compatível com Compose
   sem depender de manter stdin artificialmente aberto para fugir do EOF.
   Manter o MCP legado em stdio e seu EOF/shutdown inalterados.
6. Instância de teste em loopback; TLS/autenticação/configuração externa,
   portas validadas e secrets fora da imagem. Nenhuma exposição externa
   automática nem alteração de banco existente. Verificar readiness com
   testes reais de masking/read-only, UI, PGWire e falhas antes de avisar
   que está disponível. Entregar comandos/endpoints e perfil certificado.

Preparação/start do Desktop, inventário, imagem/download/build e rodada de
teste terão comandos/pins/ownership/cleanup revistos antes de executar.
Não reutilizar scripts/attempts consumidos de HELD ou do PG de D-117.
Desktop observado off nesta preparação; nenhum DockerCLI foi chamado.
Não alterar engine/WSL/serviço do host ou usar --privileged por conveniência.
Nenhuma imagem foi baixada ou container criado por este documento.

## Próximo lote após escolha do destino e dos recursos

**Opção A aprovada explicitamente em2026-10-23**, D-119: novo aceite de B-2
somente para o perfil de teste local, sem fechar gate ou mudar FAIL antigos.
Revisar com Claude2 a implementação do domínio Linux e worker/transporte. Não continuar acumulando provas sintéticas que não
respondam à lacuna do agregado. B-2 só fecha depois de cumprir os novos critérios/controles aprovados para
o perfil; os perfis estritos antigos continuam NOT_READY. Incompatibilidade deve ser
apresentada, não escondida por mais testes verdes de fakes.
Sem mudança funcional, dependência, listener, commit/push ou deploy aqui.
