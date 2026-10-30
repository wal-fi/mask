# Adapter de posse do leitor PG16 — sem autoridade de limpeza

2026-10-30 sob delegação. Novo pg16_shell_cleanup_policy.py e fakes. Nenhum
CLI/Docker, processo, arquivo operacional, nova raiz, servidor, SQL ou segredo.
Capture lê definições já revisadas; identity não relê fontes vivas.

## Desenho e implementação

Claude2/review99525 aceitou o desenho antes do código, com quatro precisões
incorporadas: case exatamente str convertido no enum do perfil; command de
dois str exatos e Intent local preenchido só com valores reconstruídos; tipos
JSON exatos nos campos comparados para recusar __eq__ que sempre retorna
True; falhas de captura/exec aninhadas mapeadas para SOURCE fora de except.

Perfil8906e846 capturado e hash rechecado em memória em cada identity. API
leva CID capturado do create, task/case/Cmd esperados; nunca infere posse do
CID recebido por inspect alheio. _capture reconstrói nome/Cmd/labels próprios;
objeto Intent local com imageNone e todos os oito campos é usado somente pela
identity do perfil, não retornado ou fornecido a create/start. Env/limites/
stdin ruins não impedem reconhecer recurso próprio. Nenhuma imagem admitida
ou permissão para rm é devolvida, apenas o mesmo CID quando comprovado.

Erros operacionais/input viram PG16_READER_OWNERSHIP, fonte vira
PG16_READER_SOURCE, levantados fora de except sem cadeia/mensagem original.
Interrupção propaga e nunca é tratada como sucesso. Fonte anterior intacta.

## Gates próprios medidos antes da revisão

- **37 passed/1,12s** (primeira rodada1,17s), com os23casos e captura do perfil;
  identidade alheia, troca de caso/task/CID/Cmd/entry/labels/imagem, perfil
  recusado mantendo posse, tipos exatos, enum/subclasse str recusados,
  __eq__ hostil que retorna True ou levanta erro nunca chamado, sem releitura
  viva, fonte corrompida/nestedexec sanitizados, objeto local reconstruído,
  interrupção e ausência de spawn/write/mkdir.
- Ruff dos testes e E9/F63/F7/F82 do helper limpos depois de ordenar imports
  e formatar somente os dois arquivos novos. Tipos hostis dos testes declaram
  __hash__ coerente; não é alteração de produto ou fonte consumida.
- Fonte3984bytes SHA-256:
  96e8a4c430c55e66c95c5c8f5a6fe5c9430fdf8389f418d4c4f7888ac39923b0.
- Nenhum teste vermelho de implementação reivindicado neste incremento:
  as proteções vieram do desenho revisado antes do código.

## Gates finais e revisão

- Seleção adapter anterior/perfil reader/adapter novo:117passed/3,74s,
  nenhuma falha, skip ou deselect; sem unidade nativa antiga de PipeHandle.
- Ruff src/tests: limpo; format src/tests+helper novo:331 conformes.
- Mypy strict src/tests:330 arquivos limpos para alvos3.11 e3.14. Runtime
  executado apenas Windows3.11.3, sem alegação Linux/3.14 medidos.
- Claude2/sessão51ea0d85/review35578 aceitou o adapter isolado, sem bloqueador.
  Sua nota menor sobre contagem dos casos foi incorporada: assert explícito
  de23membros, preservando a fonte do adapter. Garantia de hash é só dos bytes
  capturados PROFILE_RAW; não autentica o namespace P já executado. Nenhuma
  mutação dos namespaces é permitida pelo contrato do coordenador confiável.

Não houve prova nativa deste adapter ou declaração de cleanup real. O futuro
consumidor deve obter inspect atual, serializar ações, persistir decisão de
volumes antes de rm, recolher CLI/handles/ticket e provar ausência antes de
release. Watchdog/host/entrada/exportador/caller desse perfil ainda ausentes.
Gateway indisponível; B1/B2/D090/C1/SQL/produção seguem abertos.
