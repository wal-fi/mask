# T4 — identidade pelo handle original e template PS, antes do teste nativo

2026-10-28, sob delegação. Desenho do host aceito com P1–P4 pelo Claude2.
Este incremento isola P1/P2: helper e template, fakes e unidade nativa
**ainda não executada**, antes de qualquer Docker/T4. Nenhum processo filho
novo, kill nativo, GetProcessTimes real, CID, DB ou segredo até este checkpoint.

## Código e contrato

docs/poc/w1_bootstrap_identity.py,dc2481f5a54c1408f6c91c38f99c138d82431b5b1324afdfe9443087323b140d:
Birth imutável PIDuint32/FILETIMEint64 exatos; raw_filetime consulta
GetProcessTimes no handle original **emprestado**, sem OpenProcess/CloseHandle
ou lookup por PID. capture é síncrono após start retornar/lançar com processo
adotado, antes de outro await; caminho privado Proactor/Popen explicitamente
pinado no futuro coordenador. Desconhecido retorna None e mantém pendência.

kill_script recebe só Birth validado e gera script fixo ASCII. Process obtido
uma vez, .Handle forçado antes de StartTimeUTC→FILETIME; compara inteiro
original, .Kill e .WaitForExit3000 no mesmo objeto, Dispose em finally.
Sem Stop-Process -Id ou segundo lookup para matar. Saída fechada JSON com
status KILLED/ABSENT/IDENTITY_MISMATCH/ERROR, pid e timestamp decimal string
com InvariantCulture. parse valida tipos/esquema/igualdade exata para KILLED;
mismatch nunca é confundido com sucesso. UTF16LE/EncodedCommand evita texto
PT/encoding ambíguo no transporte do comando.

O contrato/GetProcessTimes e a retenção de handle foram pesquisados só em
fontes Microsoft primárias, vinculadas no desenho HOST. São base do desenho,
não evidência de que o caminho foi executado neste host.

## Fakes e parser

tests/test_w1_bootstrap_identity.py,
c406058db840539c174cb2dc9fc02306c6ced994da5dc339d783e58e9165ca45.
**28pass/1deselected**,0,24s, seleção explícita `-k 'not native'`: a unidade
nativa está excluída até revisão do código/comando. Não é suíte integral.
Fakes verificam valores>2^53 sem float, handle emprestado sem fechar,
GetProcessTimes falso/erro/zero, ausência de processo adotado, uma captura
de Process no script, ordem handle→StartTime→Kill e categorias/tipos fechados.
Parser PowerShell ParseInput aprovou a estrutura sem executar o template;
não matou PID123 usado apenas como literal de preparação. Ruff/mypy3.11 do
teste aprovados; lint restrito do helper, sem claim de tipagem estrita.

## Unidade nativa proposta, requer revisão antes de executar

Um Python inofensivo e próprio dorme30s. Usar **diretamente** o CPython base
3.11.3 já instalado, nunca o redirector da venv que criaria outro descendente:
C:/Users/w.filho/AppData/Local/Programs/Python/Python311/python.exe,
SHAff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418.
Sem instalação/PATH/registro; flags-I-B, stdin/stdout/stderrDEVNULL, ambiente
Windows público allowlist, CREATE_NO_WINDOW. FILETIME lido do handle original.

Duas chamadas PS fixas, também ocultas: primeiro timestamp+1 exige
IDENTITY_MISMATCH, observed timestamp igual ao original e filho ainda vivo;
depois original exige KILLED, igualdade exata dos tempos e processo terminado.
Cada PS limitado8s, WaitForExit3s; finally do pytest mata/aguarda somente seu
próprio filho pelo handle original mesmo se a prova falhar. Sem lookup de
outros processos, acesso ao Docker, rede, banco, credencial ou serviço.

Comando proposto:
`.venv\Scripts\python.exe -m pytest -q -o addopts= tests/test_w1_bootstrap_identity.py -k native_original_handle --tb=short`

Executar fora do sandbox se necessário para o processo próprio, somente
depois da revisão deste helper/teste/template/comando. Não pedir aval por
lote ao usuário: a delegação vigente cobre teste local necessário/reversível;
permissões efetivas das ferramentas continuam obrigatórias. Recusa efetiva
da ferramenta deve ser reportada, sem contornar restrições.

Não é sonda Docker T4 nem prova de PID CLI/frame/worker. Coordenador/watchdog,
estado/raiz/comando/ciclo T4 ainda ausentes. B-1/B-2/D-090/C1/SQL/produção
continuam abertos; sem commit/push/job/segundo escritor.

## Execução nativa única, após revisão

Claude2 revisou dc2481f5/c406058d/template e o comando exato sem bloqueador.
Sob delegação vigente e permissão efetiva da ferramenta, executado **uma vez**
fora do sandbox em2026-10-28T15:36:15.2662260Z, com verificação prévia dos
pins do helper/teste/canal/PowerShell. Nenhum arquivo funcional mudou entre
revisão e execução. Comando da seção anterior, sem opção nova.

**1pass/28deselected,1,45s,exit0**. Dois caminhos de FILETIME iguais exatamente;
timestamp+1 recusou kill e preservou o filho, timestamp original encerrou o
filho próprio; finally/wait concluíram. Nenhum processo de terceiros/Docker/
rede/DB/secret/instalação. Não repetir a prova sem mudança/finding que justifique.

Fuso medido: E. South America Standard Time, nome local Hora oficial do Brasil,
offset-base-03:00, supports_dst=true (regras históricas), dst_now=false.
A igualdade foi medida nesse contexto; não é garantia para ambiguidade DST
futura. ABSENT continua sem prova nativa, só fakes. Não é identificação de
um docker.exe real nem substitui T4. Resultado enviado à revisão somente
leitura antes do uso como insumo do watchdog/coordenador.
