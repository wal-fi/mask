# Oracle9 Python — correspondência lib64 e cache do linker

Desenho sob delegação, antes de implementar; não aprovação individual.
Nenhum Docker ativo. v13/attempt8 foi diagnóstico NOT_PASSED uma vez;
registro imutável `oracle9-python-attempt8-20261025.json` SHA
56bf111fd97cab72c92212e50c2dc513c0c0de4f0f2443e68de3882df7c9ad7c.
Sem imagem commitada/sem OOM, cleanup/Offtrue22:45:25.5493398Z.
Três caminhos completos: /etc/ld.so.cache e /usr/lib64/libtirpc.so.3 e
/usr/lib64/libtirpc.so.3.0.0. Policy dos diretórios aceita e fatos medidos:
man/man1 root0755 e ldconfig root0700; unchangedfalse corretamente.

Leitura limitada dos metadados do RPM original no Windows, sem executá-lo,
confirmou dois itens em **/lib64** com owner libtirpc e link/digest declarados;
fatos públicos em `oracle9-libtirpc-header-20261025.json`. Isso não prova
que /lib64 seja o alias correto no container: próxima execução deve medir.
Documentação primária: https://rpm.org/docs/latest/manual/tags e
https://man7.org/linux/man-pages/man8/ldconfig.8.html (cache/links).

## Correção proposta, estrita

1. Antes de instalar, gravar somente fatos públicos de /lib64: symlink real,
uid/gid0, target literal usr/lib64 ou /usr/lib64, resolução exata /usr/lib64;
alvo real diretório root sem bits de privilégio ou escrita group/other,
owner rx. Depois exigir os mesmos fatos. Nenhuma resolução de link de
arquivo para mapear ownership: preservar o basename/symlink próprio.
2. Mapear **somente os dois paths libtirpc acima**, quando a lista do RPM
novo libtirpc|x86_64 declarar a variante /lib64 correspondente e a prova
anterior/depois do alias for íntegra. Colisão/owner diferente recusa. Não
abrir /lib*, aliases genéricos, realpath arbitrário ou prefixo de diff.
O rpm -V libtirpc canônico continua obrigatório; arquivos passam por
stat/xattr/metadata da imagem e inventário/hash já existentes.
3. /etc/ld.so.cache já é exceção explícita de bytes mutáveis no desenho,
mas o inventário novo o exigia como arquivo de um RPM adicionado. Passa a
exigir atestação própria: regular real, root0:0, sem6022,0<size<=16MiB,
SHA256, consulta rpm-qf exata glibc|x86_64/rc0/stderr vazio; glibc anterior
com NEVRA inalterada. Sem isso recusa. Não apagar esse cache ou permitir
outros arquivos. Caso fosse preexistente, a mesma prova continua exigida.
4. Relatório runtime/host/sonda compartilha validação de esquema/fatos,
incluindo alias e cache; nunca inferir conformidade de apenas um bool.
Diff do cache exato exige a prova nova em vez do bool de passwd/group.
Novo caminho de cache é apartado do inventário de pacotes novos; dois
libtirpc mapeados continuam nele com owner/hash/tipo. Diagnósticos v13
preservados; nenhum NOT_PASSED anterior vira PASS.

Testes puros/fake-stat negativos antes da próxima ação: target/owner/modo/
colisão/arquivo extra ou alias alterado e cache inválido recusam; nenhuma
mudança de bytes do payload ou limiares durante execução. Não certificam
POSIX no Windows. Fonte/pins/root novos e roteiro A/Observe3/Ready/B/C
terão revisão após código antes de uma execução. Sem D/rede no builder,
mesmos caps7/2GiB e sonda128MiB/RO/nonroot/capdropALL, sem retry/override.
Sem produto, DB, SQL, worker, commit/push ou disponibilidade. Gate do
Python intermediário não fecha B-1/B-2/D-090 ou domínio completo.


## Implementação local v14, aguardando revisão antes da ação

Revisão5269 sem bloqueador antes de código; cinco requisitos incorporados:
inode/dev dos dois caminhos iguais sem realpath; metadata/link/hash do RPM
iguais ao header original; mapeamento só dois literais/sem colisão; cache
com presença/hash anterior e ação A/C correspondente; esquema compartilhado
estrito. Alias é medido antes via readlink/stat no shell e depois por lstat,
incluindo identidade do alias e alvo. Query canônica -V continua obrigatória.
Somente glibc anterior/NEVRA inalterado pode ser dono dos dois caches.
Sem bytes originais ou domínio/SQL/produto novos.39 testes novos (138 total)
passaram; depois foi acrescentado um controle positivo fake do construtor
(total139 esperado;40 focados passaram). Estáticos dos testes e formato
verdes antes desse último caso; escopos de lint de scripts limitados como
registrados, não lint completo. Nenhuma execução nativa desses fatos ainda.

Raiz nova52d3b130/task55c8f06e224144e3b4f8239fc3a93fc3, estado inicial.
Manifesto02b6c7164ea6ace8e0de65114221b3e0d7f74facce3bf3ce3abe564f90ddce6b.
Cópia `docs/poc/evidence/oracle9-python-procedure-v14-20261023.json` SHA
cad2be7d101395db946865cdd374da021a96749b66d7b8c276605cbccceb2bf8.
Pins start65f9267736abbcfb70ca1e06121a0bfe93f667a8ab35492b04bd575f03ba4f74;
controlb37d9b164d5a8c130f27a964b31064c1c90be82bb7d91065ccae11143c21290e;
restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28;
host8cd9d4f087118c9ad8644b790312565f471c40e85240be51075665e23f404834;
payload457df3ac5ed4ed167f2c10d7cc97eb485cca07c66bc48b24bc8e4ab06b967ed8;
downloader5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896.
Mesma A/Observe3/Ready/B uma vez/C, sem pausa longa; chamadas separadas com
exits conferidos, pins/origem/estado reais antes de A. Root substitui as
anteriores no roteiro. Sem D/novos RPMs, rede/limites/caps adicionais, retry
ou override. Oito NOT_PASSED preservados, nenhuma imagem final pronta.

Revisão pré-ação 24136 sem bloqueador.139 testes direcionados finais
passaram; Ruff/mypy dos quatro testes e format dos sete arquivos passaram.
Escolha sob delegação: manter também igualdade dev/ino do diretório alvo
antes/depois; copy-up pode causar recusa ambiental, não aceitar override.
Pins/origem/estado reais conferidos antes de A; A terminal0, Observe em
andamento. O risco não é fechamento de domínio ou gateway.


## v15 — identidade por metadados da imagem, antes da ação

v14 falhou no parsing de stdout de commit, mesmo com exit0 e imagem
criada; texto179bytes não preservado, sem atribuir causa. Não é falha de
conteúdo: o payload e diff passaram. Imagem da rodada permanece em
quarentena, sem usar como base/reexecutar/retag. Native final probe não rodou.

Mudança só host: salvar stdout exato de commit/fsync para diagnóstico,
exigir rc0, e inspecionar o próprio tag único que estava ausente antes de
commit. JSON exato de uma imagem, IDsha256 válido, plataformaLinux/amd64,
RepoTags exatamente próprio, tasklabel, baseDiffID+uma camada, USER/ENV/
ENTRYPOINT/WORKDIR/CMD sem saúde/ports/volumes extras exigidos antes de
usar o **ID inspecionado** na sonda. Texto de commit nunca escolhe ID nem
vira comando; qualquer metadata divergente recusa. Sem afrouxar conteúdo.
154 testes direcionados passaram, incluindo15 provas/negativos novos de
identidade; Ruff/mypy dos quatro testes e format dos sete arquivos verdes.

Nova6c872481/task4f1d385b3e18464792773488386438dd, estado inicial.
Mesmo manifesto02b6c7164ea6ace8e0de65114221b3e0d7f74facce3bf3ce3abe564f90ddce6b;
mesmo payload457df3ac5ed4ed167f2c10d7cc97eb485cca07c66bc48b24bc8e4ab06b967ed8.
Cópia `docs/poc/evidence/oracle9-python-procedure-v15-20261023.json`, SHA
645e0803e49fd4a50e7dca337e152006203ae99873e653a5394af7bf66f5bcfb.
start6db94c8c21c0f440bdfa2192ca6168494c9cab76934e7ee0a74fa80386f690e6;
controlc500fb5ee2e833057e4ed3363359460aed8819db58d47b5420e30dba47926a14;
restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28;
host0b0bb1719834bdc9ccaa4a2ffd4c8da23824d92320e05bf1218af734d2ede1b5;
downloader5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896.
Mesma A/Observe3/Ready/B uma vez/C sem pausas, exits/pins conferidos,
sem D/rede no builder/retry/override/limites ou caps novos. Após B, não
editar fontes até Off terminal e registro completo. Revisão do delta antes
A; nove NOT_PASSED preservados, B-1/B-2/D-090 abertos.
