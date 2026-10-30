# Docker local — preparo de runtime

Destino aceito: Oracle Linux9 disponível9.8 em Docker nesta máquina.
Base oficial9.8 já conferida pelo diagnóstico documentado em
`docs/PHASE-9-ORACLE9-BASE-VALIDATION.md`; A base pura não contém Python; a imagem derivada já validada contém Python3.11.13.
A evidência final do runtime está em `docs/PHASE-9-ORACLE9-PYTHON-VALIDATION.md`;
ID local sha256:1546afefa358aa8c6049350948b1d5d4f272017da8997ae3974c93af7fdc07c4.
A receita inicial abaixo ainda precisa ser atualizada para partir dessa imagem
e de um fechamento Linux de dependências; não executá-la como entrega pronta.
**Ainda não há build da aplicação, instância disponível, SQL liberada ou deploy aprovado
por estes arquivos.** O produto ainda depende dos gates B-1/B-2/D-090.

Containerfile.oracle9 é receita inicial para um **contexto gerado separado**,
somente os nomes de context.allowlist. Não usar a raiz do checkout como
contexto, copiar .venv, configuração, catálogo, secrets, docs/capturas ou
fontes privadas frontend. A allowlist é contrato do futuro gerador, não
filtro automático que o Docker aplique sozinho. Não há comando de build
executável entregue enquanto faltam resolver/validar os insumos abaixo.

Insumos obrigatórios antes do build:

- BASE_IMAGE oficial verificada por digest linux/amd64 e /etc/os-release
  Oracle9.8 conferido. A tag major9-slim é só ponto de descoberta; tags
  minor9.8/9.8-slim não foram localizadas no DockerHub. Não chamar o digest
  candidato de9.8 antes de inspecionar a imagem em execução.
- PYTHON311_NEVRA e PIP311_NEVRA exatos dos RPMs Oracle. Dependências
  transitivas RPM/metadata de repo e pacote de CA ainda precisam ser
  inventariados: um pin de dois RPMs não torna o build bit a bit reproduzível.
- requirements.lock com projeto e fechamento completo de dependências
  **Linux**, versões exatas/hashes; wheels compatíveis, verificadas antes
  do contexto. Não derivar o fechamento de pip freeze Windows ou aceitar
  sdist arbitrário no container. O wheel próprio será construído fora dele.
- Manifesto do contexto sem symlink/traversal/entrada extra, com teto de
  quantidade/bytes e hashes; o gerador ainda não foi implementado/revisto.
- Comandos/ambiente/ownership/pins da preparação e build revistos antes
  de iniciar Docker, download, container ou carga; não reutilizar attempts
  consumidos de outros experimentos.

O build usa rede somente para RPMs Oracle; pip é offline com hashes e
only-binary. Instalações dentro da imagem não mudam Python do host ou .venv.
Não se afirma isolamento reprodutível de repo RPM ainda mutável. A entrega
reproduzível será identificada pelo digest final da imagem e seus insumos;
qualquer promessa mais forte exige gates próprios.

UID/GID10001 é identidade interna sem privilégio, não usuário do PostgreSQL
ou principal do gateway. Configuração/credenciais/portas/aliases serão
externos. Não há VOLUME/EXPOSE/HEALTHCHECK/restart que esconda ativação.
No estado atual o entrypoint conserva MCP stdio/EOF e SQL PGWire0A000;
não é serviço foreground para deixar ligado. Esse modo será entregue após
os gates próprios, sem manter stdin aberto artificialmente.

Controles do container em execução ainda deverão ser comprovados no perfil:
read-only, cap-drop/NNP, core/dumpable, pids/fds, memória/swap, state volume
limitado pela aplicação, logs limitados/none e loopback/TLS/config externa.
Não montar Docker socket, usar privileged ou modificar Windows/WSL/daemon.
Opção A de recursos aprovada explicitamente (D-119); evidência/controles
pendentes em docs/PHASE-9-CONTAINER-MEMORY-DECISION.md. A receita não a implementa nem
marca C1 pronto. Só avisar disponibilidade após testes de aceitação reais.
