# HELD — captura e rechecagem de evidência, núcleo isolado

**2026-10-22 — desenho revisado com E1/E2/R-T1–R-T3 incorporados.**
Resolve a recomendação Q1 da rodada loaded-as128, não contenção de produção.
O plano anterior está consumido: nenhuma nova carga ou reconstrução de sua
evidência. Preservar os dez helpers congelados, testes/artefatos antigos e
produto/src; não trocar perfil/cap para obter verde. Sem DockerCLI, banco,
subprocesso, worker, SQL, nova dependência/configuração ou commit/push.

## Menor incremento proposto

Novo `docs/poc/loaded_memory_evidence.py` e teste próprio. Somente funções
puras e composição do supervisor existente com IO **simulado neste lote**.
Nenhum entrypoint Linux, backend real ou host observador o importa/chama.
Carregar por spec os helpers revisados, sem monkeypatch em seus globais,
duplicar classificador/decoder/algoritmo de cleanup ou alterar seus arquivos.
O módulo não deve fazer IO, iniciar timer/thread/processo/carga ao importar.
Ler as próprias fontes para carregar helpers é distinto de IO do laboratório.

Três peças, testadas juntas e adversarialmente:

1. Tap de leitura limitado sobre IO fornecido; delega explicitamente prepare,
   spawn, clock, pid (propriedade dinâmica), observe, send, sleep, wait,
   cleanup e final, sem __getattr__ genérico. Só `read()` é interceptado.
   Retém no máximo duas linhas **bytes imutáveis**, cada<=1024, apenas quando
   `decode_held` congelado as aceita como HELD fechado/canônico. Linhas ready,
   inventário, erros ou inválidas continuam indo inalteradas ao supervisor,
   que decide protocolo/cleanup; não publicá-las como HELD validado. Terceira
   candidata aborta a supervisão, que ainda executa seu finally/cleanup.
   Captura sintática não é validação semântica e não é alegação de sucesso.
   HELD válido fora de posição (por exemplo durante imports) continua sendo
   recusado pelo supervisor e nunca publicado positivo; testar isso.
   T1 da revisão de código: exceção do read delegado passa inalterada ao
   supervisor, sem marcar broken, para preservar categoria e relatório
   negativo. Só erros próprios da captura (decoder inesperado/retenção/cap)
   marcam broken e produzem fallback. Cleanup continua único no supervisor.
2. Composição chama `supervise` congelado sobre o tap. Somente depois de
   ele terminar, validar o relatório pelo host congelado e reexecutar as
   transições do core com as linhas capturadas e observações independentes.
   Publicar HELD como validado só se a rechecagem positiva inteira completar.
   Resultado negativo conserva relatório negativo mas lista HELD vazia;
   candidato parcial/errado nunca vira evidência positiva. Erro da captura,
   rechecagem, serialização ou limite produz fallback fechado inconclusivo,
   nunca o positivo original sem HELD. A composição não assume ownership
   diferente do IO; o supervisor continua único responsável por cleanup.
3. Codec/replayer puro recebe raw ASCII limitado, caso/digest esperados e
   revalida tudo na leitura. Não confiar num booleano `validated=true` ou no
   outcome. Pode ser usado por host futuro **depois** de integração revisada;
   não adaptar silenciosamente o host atual nem seus perfis.

## Formato versionado, sem modificar o original

Envelope novo, campos exatos:

```text
profile = "loaded-as128-held-v1"
case = control | private | shared
outcome = o outcome do original somente após validação
total_memory_contained = false (tipo bool exato)
original_report = string ASCII dos bytes exatos do raw original, com newline
original_sha256 = SHA256 hexadecimal desses bytes exatos
original_bytes = comprimento inteiro exato desses bytes
validated_held = [linha ASCII original, incluindo newline]
```

Controle positivo exige duas linhas, private depois shared. Limitado positivo
exige uma, do alocador do caso. Cada linha<=1024 bytes e os mesmos bytes que
passaram pelo tap: sem recompor números ou sintetizar a partir de VmSize/
shmem. Recomputar comprimento/SHA antes de decode_report e validate_report do
host congelado; não reserializar o original como objeto. O SHA confere bytes,
não autenticidade física: identidade/origem continuam gates externos.
Decoder canônico congelado recusa duplicatas/NaN, contagem inconsistente,
tipo bool em inteiro, errno inválido etc. Linha válida em sintaxe ainda passa
pelas condições semânticas do core (recusa/retido/limite/pico/ordem).
Negativo original validado pelo host exige lista vazia, sem alegar que houve
linha HELD validada até o fim. Fallback próprio exato:

```json
{"profile":"loaded-as128-held-v1","outcome":"inconclusive","evidence_failure":"EVIDENCE","total_memory_contained":false}
```

Raw total<=65536 incluindo único newline final; ASCII, sem duplicatas/NaN,
sem documento extra, chave desconhecida ou truncamento. O overhead das linhas
escapadas conta no mesmo teto; original perto do cap pode virar fallback.
Construção/parse não mutam nem compartilham dicionários do chamador: usar
snapshot via codec limitado. Evidência deste laboratório não recebe dados de
usuário/SQL/segredos. Falhas externas têm categoria fixa sem mensagem/cadeia.

## Replay, usando o core existente

Primeiro host.validate_report no original com caso/digest esperados; inventário
descomprimido/limitado e digest recalculado pelo caminho congelado. Nada de
aceitar outro perfil ou relatório antigo sem HELD como positivo deste formato.
Para original positivo, criar PressureProtocol novo com relógio **lógico**.
Tabela fechada, depois de o host conferir tipos/limites/coerência:

| Chamada | Fonte exata |
| --- | --- |
| construção | P=observations[0].inventory[1], int>=2 igual em todas; relógio0,deadline20 |
| ready | observação0 VM/limites, pid=P/ppid=1 |
| nenhuma | observações1–3 transitórias, fds=None |
| admit_imports | inventário decodificado + observação4 |
| pressure por alocador | próxima observação, iniciando no índice5 |
| held | próxima linha capturada, private depois shared no controle |
| release | próxima observação, com anon e inventory dela |
| released | próxima observação, com anon dela |
| release_wait/release_sample | só privado do controle enquanto false; avançar exatamente1s, consumir próxima observação; até4 adicionais |
| nenhuma antes de finish | exatamente uma observação estável restante, mesmo conjunto de descritores |
| finish/completed | done/eof=True, member_returncode,cleanup=True/final_inventory já validados |

Comparar outcome; no controle, control_digest igual ao inventory_digest do
original e ao digest recalculado pelo host. Não aceitar sobra/falta de
observação/linha ou índice fora da tabela. Segundo alocador do controle
somente após o core confirmar descarte privado.

Isso revalida condições lógicas/valores/ordem, **não mede tempo transcorrido**,
não prova EOF real por si só nem origem física dos números. Lifecycle e prazos
reais continuam dependendo do supervisor/host/artefatos de execução. Não
fabricar timestamps; o relógio lógico serve apenas para replay do contrato.
Contagem de blocos/categoria/errno são **relatos do membro**, não medições
independentes; replay checa consistência/regras. Pico e limites têm a
corroboração da observação independente, não autoria física de todo campo.
Todos os fatos e tipos precisam ser verificados antes de igualdade/índice.
Qualquer falta/excesso, troca de alocador, pico desigual, limite errado,
falso positivo, falha de descarte/cleanup ou inventário divergente recusa o
envelope, sem recuperar caminho positivo legado nem tentar de novo.

## Testes e gates antes de qualquer integração

Testes primeiro: módulo ainda ausente deve falhar na coleta, não alegar bug
antigo. Fakes do supervisor e pequenos buffers/linhas, sem fábrica Linux.
Normalizar só no fake novo os detalhes parentais omitidos pelo fake antigo
(startup inherited_as e cgroup final/procs), sem editar teste congelado.

- controle/privado/shared completos com linhas byte a byte e replay positivo;
- negativo/import interrompido/cleanup falho: nenhum HELD publicado positivo;
- linhas ausentes, extras, trocadas, reorder, falsas recusas, zero retido,
  tamanho/páginas/blocos/errno/limites/pico/cleanup inconsistentes;
- canonicalidade/ASCII/duplicatas/NaN/extra documento, bool em inteiro;
- overflow de linha e do envelope/overhead, falha de captura/serialização;
- confirmação de cleanup quando tap/replay falham, sem IO novo após falha;
- snapshot sem alias/mutação e originais/fontes congelados preservados;
- amostras de descarte adicionais e falta/excesso de observações;
- nenhum chamador operacional/CLI, rede, processo/thread ou pressão.

Revisão deste desenho antes do código; revisão de código/fakes depois dos
gates proporcionais. Novos testes+relacionados, Ruff/format e mypy3.11/3.14
quando aplicável. Runtime só Windows3.11.3, sem alegar3.14 ou Linux medidos.
Nenhuma rodada real neste incremento. Depois ainda serão necessários desenho
e revisão próprios de entrypoint/host/novos hashes/argv/perfil/preflight e
comando exato antes de carga futura. B-1/B-2/D-090/SQL/produção permanecem
abertos, inclusive orçamento total/pai, trabalho nativo e concorrência.

Revisão somente leitura51ea0d85: E1 exigiu original em bytes exatos com
SHA/tamanho, E2 a tabela fechada; R-T1 delegação explícita, R-T2 fora de
posição e R-T3 distinção de relato/corroboração. Incorporados antes do código.
Parecer permite testes primeiro e implementação isolada com essas condições,
não integração/carga. Revisor não executou código nem aprovou produção.
Mudança futura do hash do host exige atualizar a constante do helper e nova
revisão; não trocar silenciosamente a implementação congelada sob este codec.
