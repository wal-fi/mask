# Leitor shell PG16 — implementação pura, sem medição nativa

2026-10-30, sob delegação. Somente docs/poc/pg16_shell_reader.py e testes de
contrato, sem chamador de subprocesso/Docker. Nenhuma fonte consumida anterior
foi alterada, nenhum container, cluster, consulta, seed privado ou dependência.

## Revisão do desenho antes do código

Claude2, sessão51ea0d85/review78326, aceitou a direção e apontou B1: trocar o
LF final por NUL pode passar pela substituição de comando do ash. O desenho
foi corrigido antes da implementação: header recebido é comparado por SHA
ao printf canônico dos seis dígitos; trailer tem digest literal dos oito
bytes. NUL final/interior têm vetores próprios. É correção de desenho, não
teste vermelho de um shell executado. Três precisões incorporadas: stderr
DD descartado, PID1 termina sem aguardar descendentes após o comando global,
e umask077 antes de mkdir que recusa diretório existente.

## Entrega e limites

Núcleo ASCII fixo: dd bs=1 lê16/N/8 bytes, corpo binário só no tmpfs, verificação
por contagem/exit e hashes de header/trailer, sonda adicional1byte sob1s.
EOF e QUIET separados. Wrapper tem prazo global8s incluindo instrumentação
pública do corpo; PID1 aguarda esse único comando e termina. READY usa schema
e6ca e SHA do núcleo, diferente do SHA do wrapper completo, sem auto-hash.

23 vetores públicos fechados: quatro positivos (1byte NUL,16KiB binário com
todos os bytes e trailer interior, fragmentado, stdin retido) e19 negativos
(formato/tamanho/parcial/NUL/byte extra/espera em cada fase). Nenhum builder
recebe corpo do operador. Parser usa o código de saída real e só aceita o
relatório inteiro canônico do caso esperado, já separado do READY pelo canal.
Negativo esperado é categoria exata e exit42; prefixo útil não vira sucesso.

O estado QUIET depende da semântica futura do timeout instalado e de State
sem OOM/Dead. Fonte de referência BusyBox orientou o desenho, não comprovou
essa build. Nenhum shell foi executado, nenhum prazo, arquivo0600, kill ou
fechamento de namespace foi medido neste incremento. Os testes não alegam
que a inspeção estática da fonte comprove sua execução. O futuro perfil/canal/
watchdog/coordenador/exportador/entrada exigem revisão própria antes de uso.

## Gates medidos até a revisão de código

- Testes próprios:30passed/0,41s (primeira execução30/0,40s).
- Ruff dos testes e check isolado E9/F63/F7/F82 do helper: limpos após ordenar
  imports e aplicar formatação apenas nos dois arquivos novos.
- Núcleo/fonte nunca consumidos em rodada real. As quatro fontes anteriores
  prepare02d1/export95f0/entrya608/host7275 mantêm os hashes medidos.
- Sem suíte integral PostgreSQL, browser ou novos pacotes neste incremento:
  produto e dependências não mudaram.

## Gates finais e revisão de código

- Seleção conjunta dos dez componentes PG público mais o leitor novo:
  **408 passed/82,03s**, sem falha, skip ou deselect.
- Ruff src/tests e check E9/F63/F7/F82 do helper: aprovados.
- Format src/tests e helper novo:328 arquivos conformes.
- Mypy strict src/tests:327 arquivos, alvos3.11 e3.14 limpos; execução de
  testes somente Windows3.11.3. Não alegar runtime3.14/Linux medido.
- Fonte Python SHA-256:
  efe69a79a0743e49de602067d624c075cf5af8321a2654b7c2e87d023f498a85.
- Núcleo shell SHA-256:
  802192691f7294baf5b41a39979110a881453c6eb4cfe6d6585a655b7afabd32.
- Wrapper binário para task pública32hex:3575 caracteres; medição do comando
  Docker completo ainda cabe ao futuro perfil, antes de A.

Claude2/sessão51ea0d85/review32442 aceitou o incremento puro, sem bloqueador.
Ressalva de contrato para o caller futuro: send_seed do e6ca fecha o stdin;
com StdinOnce=true isso produz EOF. O caso RETAIN espera QUIET e precisa de
variante explícita que mantenha o pipe aberto, ou ficar fora da rodada.
Essa escolha deve anteceder execução; não adaptar o oráculo após uma falha.
Mantido no próximo desenho, sem editar o canal e6ca consumido.

Notas da revisão factual anterior preservadas para o próximo resumo: publicar
returncode/stdout_bytes reais do owner e rótulo do inspect final. Não alterar
o exporter95f0 ou resumo consumido retroativamente. Gateway indisponível,
B1/B2/D090gate2/C1/SQL/produção continuam abertos. Código puro aceito; nenhum
efeito nativo ou liberação operacional decorre desse aceite.
