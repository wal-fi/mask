# Fase 9 — validação da Etapa 1 documental

**Data:** 2026-09-22
**Estado:** concluída e aprovada; nenhuma implementação funcional da Etapa 2 foi iniciada.

## 1. Checkpoint obrigatório

O checkpoint foi executado antes de qualquer edição:

| Item | Resultado |
|---|---|
| Branch | `master` |
| HEAD inicial | `42cd2df8aeef4a1e39ffae0ecf33a6ce86bd8445` |
| `origin/master` inicial | `42cd2df8aeef4a1e39ffae0ecf33a6ce86bd8445` |
| Ahead/behind inicial | `0/0` |
| Working tree inicial | As alterações documentais intencionais listadas pelo responsável, incluindo os dois documentos novos da Fase 9 |
| Ações proibidas | Nenhum `reset`, `checkout`, `restore`, `clean` ou `stash` executado |

As alterações documentais existentes foram preservadas. As medições da Fase 8
continuam históricas e não foram reatribuídas à Fase 9.

## 2. Escopo e revisão

Foram lidos integralmente os documentos obrigatórios: `AGENTS.md`, `CLAUDE.md`,
`docs/HANDOFF.md`, `docs/PHASE-9-SPEC.md`, `docs/PHASE-9-TRACEABILITY.md`,
`docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/SECURITY-REVIEW.md`,
`docs/DECISIONS.md`, `docs/TEST-PLAN.md`, `docs/THREAT-MODEL.md` e
`docs/PHASE-8-SPEC.md`.

A revisão fechou ambiguidades documentais sobre autenticação SCRAM do Gateway,
separação de credenciais, carregamento condicional do catálogo, TLS fora de
loopback literal, drenagem por geração, autenticação integral do catálogo,
replay de arquivo inteiro, rollback legado explícito e falha fechada no startup.
O requisito de âncora monotônica confiável para detectar restauração de um
arquivo autenticado antigo ficou explícito; sem essa âncora a implementação
deve falhar fechada e não pode alegar replay resolvido.

Não foram criados listener, store, modelos, API, rotas, UI, dependências,
socket, recurso ou módulo funcional da Fase 9.

## 3. Decisões aprovadas

As doze decisões aprovadas em 2026-09-22 foram registradas como D-065–D-076:

| ID | Tema |
|---|---|
| D-065 | PGWire como façade segura, não proxy transparente |
| D-066 | `dbname` como alias estável do datasource |
| D-067 | Login do Gateway e credencial upstream separados, com SCRAM |
| D-068 | Um principal operacional no MVP, sem RBAC implícito |
| D-069 | AEAD/AES-256-GCM, catálogo autenticado e âncora contra replay de arquivo |
| D-070 | TLS obrigatório fora de loopback literal |
| D-071 | Conexão upstream por sessão |
| D-072 | Compatibilidade certificada, sem promessa universal |
| D-073 | Admin UX v2 local e com fronteira segura |
| D-074 | MCP continua `stdio`, com alias opcional somente na Etapa 11 |
| D-075 | Rollback legado somente explícito |
| D-076 | Datasource habilitado inválido bloqueia o startup |

As referências normativas e a cobertura por Etapa 2–12 estão em
`docs/PHASE-9-TRACEABILITY.md`.

## 4. Gates medidos

### Python e PostgreSQL

- PostgreSQL real **16.15**, cluster descartável criado com binários portáteis,
  somente em loopback e sem tocar em banco existente. `MASKGW_TEST_DSN` foi
  montado somente no ambiente do processo; seu conteúdo e a senha aleatória
  não foram registrados.
- Suíte Python integral, sem `deselect` e sem skip por ausência de DSN:
  **3.830 coletados; 3.822 passados; 8 skips POSIX esperados; 0 falhas; 0
  erros; 0 xfail**.
- Windows: execução com `threading.stack_size(64 * 1024 * 1024)`.
- Ruff check: **exit 0**.
- Ruff format check: **exit 0; 140 arquivos já formatados**.
- mypy strict: **exit 0; 140 arquivos sem issues**.
- `git diff --check`: executado no fechamento, sem whitespace inválido.

A primeira tentativa do cluster herdou o timezone local do host e revelou um
failure determinístico de representação de `timestamptz`; nenhum código foi
alterado. O gate foi repetido com `TimeZone=UTC`, como na baseline, e então
passou integralmente.

### Frontend baseline

- Runtime fixado usado fora do checkout: **Node 24.20.0**, **npm 11.19.0**.
- Instalação congelada: `npm ci --ignore-scripts`, **exit 0; 6 pacotes**.
- `npm run typecheck`: **exit 0**; `checkJs`/strict/noEmit aprovados.
- `npm test`: **241 passados; 0 falhas; 0 skips**.
- `npm run inspect`: **exit 0; artefatos públicos limpos**.
- `npm run build`: **duas execuções com exit 0**; os **5 hashes** dos assets
  foram idênticos.
- Browsers não foram executados nesta Etapa 1: não são gate de aprovação
  documental; nenhuma aprovação de compatibilidade visual/browser foi alegada.

O Node/npm inicialmente disponíveis no host eram `24.21.0`/`12.0.2` e foram
recusados pelo `engine-strict` do projeto. O runtime portátil fixado foi usado
sem alterar `package.json`, lockfile ou dependências.

## 5. Arquivos incluídos no commit

As alterações existentes da Fase 8 abaixo foram preservadas como fornecidas no
checkpoint; não constituem nova medição da Fase 9.

- `AGENTS.md`
- `CLAUDE.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/PHASE-8-SPEC.md`
- `docs/PHASE-8-STAGE-9-VALIDATION.md`
- `docs/PHASE-8-TRACEABILITY.md`
- `docs/PHASE-9-SPEC.md`
- `docs/PHASE-9-STAGE-1-VALIDATION.md`
- `docs/PHASE-9-TRACEABILITY.md`
- `docs/ROADMAP.md`
- `docs/SECURITY.md`
- `docs/TEST-PLAN.md`
- `docs/THREAT-MODEL.md`

## 6. Limitações e conclusão

O Docker Desktop não disponibilizou o engine Linux neste host; por isso o gate
usou o cluster PostgreSQL portátil descartável descrito acima. Não houve acesso
a banco ou serviço já existente.

A Etapa 1 documental está concluída e aprovada. A matriz de rastreabilidade
mantém as Etapas 2–12 como `não iniciada`, e nenhuma alteração funcional foi
autorizada ou iniciada nesta sessão. O commit único local desta etapa e seu
parent/estado remoto são registrados no relatório de encerramento da sessão;
nenhum push foi feito.
