# Preparador do leitor PG16 — desenho e limites

2026-10-31, sob delegação vigente. Incremento só de código/fakes:
`docs/poc/pg16_shell_prepare.py` e `tests/test_pg16_shell_prepare.py`.
Nenhuma raiz operacional, proposta, comando, Docker, PG, SQL, worker,
serviço ou leitura do launcher/configuração reais. Entrada afaffad0, Host 8c,
exportador ed491c01 e a evidência 3eb3 ficam intactos. Resultados de testes:
não executados pelo programador; a validação é do revisor.

## API

- `state_for(task)`: estado FRESH exato da `admit` da entrada afaffad0, sem
  escrita e sem launcher. Carrega o exportador ed491c01 por SHA (leitura
  limitada) e usa `definitions`/`expected_state`; como `expected_state`
  descreve um terminal exportado (`invoked=True`), o preparador fixa
  `invoked=False`, `phase=FRESH` e exige os **16** campos da `admit` (a
  contagem 17 de uma instrução anterior estava errada; os testes derivam o
  conjunto do AST da entrada). 23 medidas de create, 23 planos de entrega,
  JSON canônico ASCII igual ao `json_bytes` do 4bc e no máximo 32768 bytes
  (mínimo entre a constante local e `STATE_LIMIT` da entrada), checado antes
  de qualquer raiz.
- `proposal(root, task)`: descritor com argv, tamanho da linha de comando,
  bytes/SHA do estado, SHAs de entrada/exportador/host/launcher esperado,
  `materialized=false`, `launcher_verified=false` e
  `admission_3s="NOT_MEASURED"`. Não escreve, não lê o launcher, não executa.
- `materialize(root, task)`: uma única criação exclusiva da raiz com somente
  `attempt.json`. Nunca chama prepare/admit/run/drive da entrada.

## Raiz e comando

Raiz absoluta `HOME/AppData/Local/Temp/maskgw-pg16-shell-reader-v1-<32hex>`
com HOME do 4bc, exatamente a forma da `admit`; nonce independente do task.
Temp e todos os ancestrais precisam ser diretórios reais, sem link ou reparse;
ancestral ausente é recusa de raiz. O nome não pode estar ocupado nem por link
pendente (`lstat`). argv é tupla fechada `(python.exe do venv, -I, -B,
entrada, raiz)`, caminhos absolutos fixos, sem argumento/ambiente/caminho do
chamador; `list2cmdline` só mede, limite explícito 2048 caracteres. Nenhum
subprocesso é criado.

## Materialização

Ordem: fontes por SHA → estado/limite → raiz/ancestrais → argv/limite →
launcher (leitura limitada a 1 MiB e SHA bfff5171) → recheck do exportador e
de todos os fontes públicos capturados → descritor pronto → raiz/ancestrais
de novo → `mkdir` exclusivo → `attempt.json` xb com contagem exata/flush/
fsync → diretório contém só `attempt.json` → ancestrais reais → releitura
limitada igual. Depois do `mkdir` a proposta está consumida: qualquer falha
deixa o diretório parcial próprio, levanta erro e nunca devolve descritor;
não há limpeza, remoção, sobrescrita, retry nem reuso. Nenhuma execução
automática posterior. Erros saem como `PrepareError` com código fechado,
fora de except, sem causa/contexto nem mensagem original.

## Riscos restantes declarados

- O launcher do venv pode iniciar o interpretador base; o SHA cobre só o
  launcher. Em tempo de execução a `admit` da entrada confere apenas
  plataforma Windows, versão 3.11.3 e os flags `-I`/`-B`/optimize 0, e
  `final_pins` faz hash só dos seis arquivos de `C.STDLIB_PINS`. O executável
  do interpretador base e o restante da stdlib não são pinados por ninguém.
- Entre a releitura e a futura invocação o diretório pode ser alterado por
  outro processo do mesmo usuário; a `admit` da entrada reconfere raiz,
  pais e estado canônico no início.
- Ancestral legítimo que seja reparse point (por exemplo pasta redirecionada)
  faz a preparação recusar fechada.
- Os fakes redirecionam HOME numa cópia privada das definições e usam um
  launcher sintético; não provam o binário real nem tempos nativos.

## Admissão 3 s — continua NOT_MEASURED

Nem o tamanho do estado, nem relógios falsos, nem o diagnóstico de pins ou o
tempo total de qualquer comando estabelecem o limite de 3 s da `prepare` da
entrada. Esse gate é obrigatório antes de qualquer proposta nativa de 23 casos
e não é medido neste incremento.

### Procedimento proposto para o próximo passo (não implementado)

Nota do revisor: este roteiro é uma direção, ainda não um procedimento
operacional aprovado. A marcação posterior à medição não garante consumo
durável se o processo cair antes de gravá-la. Antes de qualquer execução,
o desenho próprio da sonda deve resolver e testar esse intervalo, incluindo
um registro prévio independente de consumo e a regra de não reutilizar a raiz.
Não há atestação de recuperação após crash neste incremento do preparador.

1. Sonda própria `pg16_shell_admission_probe.py`, revisada antes de existir
   execução, carrega a entrada afaffad0 por SHA e mede com `perf_counter_ns`
   exatamente o prefixo da `prepare`: `admit(root)` → `Host(root, state)` →
   `Context` → `final_pins(context)`. Não chama `start_supervision`,
   `start_cycle`, amostrador de relógio, Docker, monitores, `drive` nem grava
   `invoked.json`.
2. Python nativo 3.11.3 com `-I -B`, mesmo launcher pinado, comando literal
   revisado à parte, uma única execução, sem retry para descartar amostra.
3. Raiz de sonda materializada por este preparador com task/nonce próprios.
   Logo após a medição a sonda grava `admission-probe.json` (xb/fsync): como
   a `admit` exige o diretório contendo só `attempt.json`, a raiz deixa de ser
   executável para sempre. Se essa marca falhar, o resultado é
   `PROBE_CONSUMPTION_UNPROVEN` e o nome da raiz é registrado como queimado;
   nunca reutilizar nem confundir com tentativa FRESH.
4. Saída pública fechada: duração total e por etapa em ns, contagens, SHAs
   públicos, sem caminhos/configuração. Acima de 3 s é NOT_PASSED; não ampliar
   3 s, 32768, 12, 8, 300, 600 ou 655 e não reinterpretar depois.
5. Só com esse resultado revisado a proposta nativa de 23 casos pode citar a
   admissão; o próprio `prepare` da entrada continua recusando acima de 3 s.

Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.
