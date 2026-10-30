# Entrega em produção — execução delegada

## 1. Autoridade e checkpoint (2026-10-20)

O usuário autorizou seguir pelo melhor caminho até a entrega em produção,
sem pedir aprovação por lote, e deixar retomada programada quando o Claude2
atingir limite. Não é aprovação fictícia de decisões individuais nem dispensa
de evidência, revisão, permissões efetivas ou proteção de dados.

Checkpoint local, sem fetch: `master`, HEAD
`4a5e5560abb495898c9e1b8ca44ac2d155681015`, referência `origin/master`
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind. Working tree
com lotes anteriores não commitados e arquivos pessoais não rastreados,
preservados. Nenhum resultado histórico é substituído por esta autorização.

## 2. Sequência de trabalho

1. B-2: demonstrar contenção na plataforma candidata para múltiplos processos, com criação já
   associada e inventário completo; definir orçamento efetivo do pai/saída.
   B2-B1 fornece apenas contabilidade lógica. O FAIL de 384 MiB e os 12
   excessos job-only do B2-A continuam FAIL; não elevar cotas ou reinterpretar
   contadores para obter aprovação.
   O diagnóstico Windows B2-B2a também falhou para memória compartilhada.
   Alternativa de laboratório Linux/AS foi medida em quatro casos sintéticos
   (`PHASE-9-STAGE-8-LINUX-AS-VALIDATION.md`), sem certificar plataforma,
   worker real ou domínio externo. Próxima prova deve medir imports/custos
   reais antes de integrar o worker; não elevar uma cota até obter verde.
2. Worker por sessão, integração de geração/snapshot/lease e orçamento,
   cleanup confirmado, deadline e caminho de resultado limitado. Mesmos
   validator, proveniência, masking e conexão da sessão; fechar B-1 fim a fim
   e D-090 gate 2 com provas próprias, não por inferência.
3. Completar protocolo/compatibilidade das IDEs e MCP multi-datasource nos
   limites de `PHASE-9-SPEC.md`; Admin/UI operacional segura, configuração
   externa e lifecycle adequado, sem dados de consulta na UI administrativa.
4. Gates finais de produto e pacotes instalados: PostgreSQL descartável real,
   plataformas/runtimes reivindicados, adversarial, concorrência, clientes
   lentos, falhas, segurança, UI e browsers quando afetados. Publicar somente
   incrementos revisados, sem incluir temporários ou arquivos pessoais.
5. Deploy reproduzível com configuração/segredos externos, TLS, mínimo
   privilégio/read-only, procedimento de backup/rotação/rollback e aceitação
   no destino identificado. Não criar credenciais de produção, expor portas
   externas ou alterar banco existente por suposição. Não prometer suporte
   universal a IDEs: certificar os perfis efetivamente testados.

Cada incremento registra hipótese, controles negativos, resultado observado,
limites e revisão. Falha inicial permanece documentada mesmo após correção.
Nenhum modo ilimitado, fallback inseguro, retry/rebase de escrita ou relaxamento
de masking/read-only para acelerar o cronograma.

## 3. Orquestração e retomada

O objetivo persistente desta conversa está ativo. Claude2 atua na conta já
selecionada, com tarefas em ASCII e revisões somente leitura para não disputar
o working tree. Não usar bypass de permissões, troca automática de contas ou
tentativas em alta frequência para contornar limite.

Quando houver limite real: persistir a revisão pendente sem secrets, registrar
o horário de reset se informado (senão usar espera conservadora), armar uma
retomada única para esta conversa e confirmar seu registro. A retomada não
autoriza um segundo escritor nem declara revisão aprovada. Desarmar ao concluir
ou cancelar; erro de autenticação/permissão não é tratado como cota.

Tarefas locais exigem computador e aplicativo disponíveis. A tarefa
`Maskgw-Claude2-Resume-01a05804` foi registrada sob o usuário interativo, com
privilégio limitado, sem senha e com instâncias simultâneas recusadas. O teste
único executou em 2026-10-20 às 08:54:25 (America/Sao_Paulo), com resultado
0 do comando `codex queue`; a mensagem de retomada chegou efetivamente nesta
conversa, comprovando entrega ponta a ponta, não revisão do Claude2 nem
deploy. A tarefa foi desarmada após o teste e não possui
retry ativo agora, pois o Claude2 respondeu normalmente.

Ao primeiro limite real, rearmar essa mesma tarefa para o reset informado
(mais margem) ou, sem horário, uma espera inicial conservadora de uma hora.
Persistir a tarefa técnica em `CLAUDE2-PENDING-REVIEW.md` antes de armar.
O objetivo persistente não substitui a confirmação de uma tarefa com horário.

## 4. Pendências que exigem informação externa

**Destino informado em2026-10-23:** esta máquina Windows, gateway em Docker,
userland RHEL9.9 ou Oracle Linux9.9. Avisar quando a instância estiver de
fato disponível para testes. Não instalar uma VM/RHEL no Windows ou presumir
servidor remoto. Perfil kernel/backend é o do Docker Desktop Linux local,
ainda não validação de host RHEL/Oracle. Detalhes e fontes em
PHASE-9-CONTAINER-TARGET-PLAN.md.

Minor confirmado pelo usuário: Oracle Linux9 disponível9.8 aceito. Tag
Oracle9.9 HTTP404, assim como tags minor9.8/9.8-slim;9-slim HTTP200 com
descriptor amd64 pinado no plano. /etc/os-release confirmou9.8 no novo
diagnóstico, com cleanup/off; primeira falha preservada. Base não é instância
disponível; runtime Python e produto ainda não foram preparados.
Dependências e runtime deverão ser verificados dentro da imagem Linux,
sem transformar validações Windows anteriores em evidência Linux.

Nomes DNS/TLS, portas finais e origem das credenciais ainda não estão
definidos; nenhuma senha precisa ser enviada à conversa. A instância será
local/loopback inicialmente, com configuração externa e gates de produto
antes de exposição ou declaração de disponibilidade. Isso não impede
trabalho independente no worker, transporte e orçamento.

B-1 fim a fim, B-2, D-090 gate 2 e certificação operacional permanecem abertos.
Este documento não registra testes novos ou liberação de produção.
