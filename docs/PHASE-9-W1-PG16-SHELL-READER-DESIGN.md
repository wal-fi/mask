# Leitor shell PG16 — contrato antes do código

2026-10-30, escolha técnica sob delegação. Incremento somente público:
fonte shell, construtor puro, vetores e parser de relatório. Nenhum processo,
Docker, diretório de tentativa, cluster, SQL, seed privado ou nova dependência.
A sonda pública task81e72756 foi aceita pelo Claude2. Presença de ferramentas
na imagem cf78 não comprova a semântica dos flags; a medição nativa do leitor
será outro incremento com perfil/canal/host/entrada e revisão próprios.

## Base e fronteira

- Imagem PG16 cf78: Alpine3.24.1/BusyBox1.37.0, UID/GID70, tmpfs PGDATA e /tmp
  com dono70/modo0700, root RO, sem rede/portas e sem servidor.
- Bootstrap privado e6ca e T4v2 continuam congelados. O framing não muda:
  header16 bytes = MGSEED01 + P + seis dígitos decimais + LF; corpo1..16384;
  trailer8 bytes SEEDEND\n. O trailer dentro do corpo não delimita nada.
- O corpo é binário. Nunca colocar corpo em variável shell, substituição de
  comando, argv, ENV ou stdout. Somente arquivo regular0600 em tmpfs0700 do
  container efêmero, após umask077. Não há promessa de zeroização.
- O futuro fixture privado poderá capturar a fonte exata do núcleo por hash,
  mas nunca usar o publicador/relatório de canário para material secreto.

## Decisão de leitura exata e prazo

O núcleo recebe stdin já ligado ao único attach admitido. Caminhos internos
são literais sob /tmp/maskgw-reader, criados novos, sem symlink/arquivo anterior.
O wrapper público confere UID/GID/tmpfs/modos, cria o diretório com mkdir e
umask077 e emite READY canônico enquanto é PID1. Não há eval/source do corpo.

1. dd bs=1 count=16 para header; conferir exit e wc -c ==16. Somente esse
   header limitado vira variável. Após remover LF por substituição de comando,
   o padrão deve ser exatamente MGSEED01P seguido de seis [0-9], sem wildcard.
   A variável sozinha não prova LF: ash pode descartar NUL. Reconstruir
   header esperado com printf e os seis dígitos validados em arquivo separado;
   SHA-256 do recebido e do esperado devem ser iguais. Só então remover zeros
   iniciais sem aritmética octal; recusar0 e >16384.
2. dd bs=1 count=N para corpo no arquivo novo; conferir exit e tamanho exato.
   bs=1 evita read-ahead do trailer em pipes fragmentados. Não usar head,
   cat, read de linha ou dd bs=N count=1 para consumir o frame.
3. dd bs=1 count=8 para trailer; conferir exit/tamanho8 e SHA-256 fixo dos
   bytes SEEDEND\n. Não usar variável shell para provar igualdade do trailer.
4. Sobra: uma leitura adicional de no máximo1 byte, dd bs=1 count=1, sob
   timeout -s KILL 1. Não exige EOF do Docker nem depende de read -t0 ou de
   dd iflag=nonblock. byte presente é SURPLUS, inclusive NUL/LF. EOF com0
   bytes/exit0 e silêncio com0 bytes/exit137 são estados distintos aceitos;
   outro exit/tamanho é IO. Não afirma que bytes futuros nunca chegarão.
   O segundo caso só será aceito nativamente após medir o timeout real e
   ausência de OOM/Dead no CID; o código137 isolado não autentica um timer.
5. O frame e a sonda adicional ficam dentro de um prazo único de8s desde
   antes da leitura, sem renovação por byte/fase. O wrapper PID1 executa
   timeout -s KILL 8 sh -ec <leitor fixo> como comando filho, espera o exit
   e termina imediatamente. Não fazer exec desse timeout como PID1: o
   supervisor BusyBox usa um descendente para sinalizar o processo observado.
   A morte de PID1 seguida de State parado/Pid0 é parte da prova de recursos;
   não declarar um dd recolhido só porque o shell recebeu137. Depois de
   qualquer exit desse comando, PID1 termina imediatamente, sem esperar dd
   órfão ou timer descendente: a saída de PID1 derruba o namespace. Caminho
   de sucesso não faz instrumentação no pai: relatório público é produzido
   no mesmo filho sob8s, depois do núcleo. Nenhum wait de outros filhos.
   Medir essa regra e ausência de processos
   residuais/zumbis na futura rodada nativa.

Todas as chamadas dd têm 2>/dev/null, inclusive as de arquivo; não presumir
status=none. umask077 precede mkdir, que deve falhar se o diretório já existe.
Nenhum arquivo pode ser escrito fora do diretório novo. Não usar conv=excl.

O prazo do host continua absoluto12s para spawn/READY/envio. O prazo shell8s
não cobre fila/create/preflight, nem promete teto para syscall do host. Após
timeout/falha, canal/coordenador devem recolher CLI/pipes e o CID pelo fluxo
ticket→ausência→release já revisto. Esse incremento não implementa esse caller.

As escolhas acima vêm da leitura do código-fonte de referência BusyBox:
[dd](https://raw.githubusercontent.com/mirror/busybox/master/coreutils/dd.c),
[timeout](https://raw.githubusercontent.com/mirror/busybox/master/coreutils/timeout.c)
e [read](https://raw.githubusercontent.com/mirror/busybox/master/shell/shell_common.c).
É inferência para propor o ensaio, não atestação de flags/build1.37.0 instalado.
Não se presume suporte GNU nonblock nem comportamento do read da Bash.

## API pública proposta para o incremento puro

Novo docs/poc/pg16_shell_reader.py, sem chamador nativo ou efeitos no import:

- constantes HEADER/BODY/TRAILER e READER_SOURCE literal ASCII, sem tarefa,
  corpo ou qualquer valor de runtime interpolado no núcleo;
- registros imutáveis de casos públicos fechados, todos determinísticos;
  nenhum builder aceita bytes fornecidos pelo operador como seed;
- construtor do wrapper recebe somente task32hex e nome de caso enumerado.
  READY tem mesmo schema/ordem canônica do e6ca e source_sha256 do núcleo;
  o hash do wrapper completo é separado no registro do caso/label futuro;
  não fingir auto-hash de uma fonte que contém o próprio hash;
- o resultado do núcleo é arquivo corpo e status interno fechado, sem
  relatório secreto. Wrapper público mede SHA do canário e imprime somente
  kind/task/case/core_sha256/body_bytes/body_sha256/tail=EOF|QUIET;
- parser recebe o returncode real e stdout completo≤2048bytes. Só aceita
  relatório inteiro canônico do caso esperado e digest do canário público.
  Recusa prefixos/nonzero/duplicação/chave extra/Unicode/contagem bool/troca
  de caso. Falha shell emite categoria fechada, nunca comando/dados/stderr;
- erros Python têm categoria fechada e nenhuma causa/contexto originário;
  nenhum str/repr de entradas hostis para formar erro.

O builder não libera criação/start de container; perfil, ownership/cleanup,
READY/pumps, watchdog, executor, exporter e entrada próprios vêm depois.
Summary futuro deve incluir returncode e stdout_bytes reais do owner e o
rótulo do inspect que forneceu post_execution_state (notas da revisão factual).

## Matriz pública a materializar antes de efeitos

Casos positivos: corpo1 byte; corpo16384 com todos os valores de byte,
NUL e SEEDEND\n no interior; frame fragmentado; stdin retido aberto depois
do frame completo; EOF após frame. O teste deve distinguir EOF de QUIET.

Negativos: magic/role/dígito/LF inválidos, NUL final no lugar do LF em header
e trailer e NUL interior, tamanho0/>16384, header/corpo/
trailer parciais, trailer errado, um byte extra ASCII/NUL/LF, I/O de arquivo,
leitura que nunca progride e fragmentação lenta que cruza o prazo global.
Negativos não emitem relatório positivo ou hash de corpo; somente categoria.

Antes de Docker, testes puros verificam a construção fechada, os vetores
contra o decoder Python e6ca capturado por hash, parser estrito, fontes/pins
históricos inalterados e import sem Popen/os.system/efeitos de filesystem.
Fakes não comprovam execução shell. Antes da rodada real, definir número
de CIDs/casos, tempos totais e prova de stdout/exit/I/O reais, com fonte,
perfil, proposta/raiz/comando exatos revistos. Nenhuma execução por este plano.

## O que permanece aberto

Sem servidor PG, fixture privado, PKI/credencial, worker, consulta ou ingresso.
Sem alegação de orçamento físico total, C1/B1/B2/D090gate2/produção. Gateway
indisponível; SQL PGWire recusada. Review78326 aceitou a direção e condicionou
o código ao B1 (NUL final) e três precisões: stderr DD, namespace após timer
e mkdir novo/umask antes. Incorporados acima antes do código. Nenhuma fonte
shell executada; semântica real continua não medida.
