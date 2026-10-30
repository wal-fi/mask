# Oracle9 — três restaurações de diretório observadas

2026-10-23 local. Decisão técnica proposta sob delegação, **antes de código
ou ação**. Não é aprovação individual do usuário, C1 pronto ou produção.
Diagnóstico v10 terminou NOT_PASSED conforme esperado, sem waiver:
baseline normalizada2598 linhas, depois2595; zero erros adicionados e
somente estes três `missing` removidos:

- `/usr/share/man`
- `/usr/share/man/man1`
- `/var/cache/ldconfig`

Isso mostra restauração de presença segundo RPM, não ainda prova de
tipo/permissões/dono: esses fatos serão exigidos, não inventados. Original
e três versões anteriores continuam reprovados; nenhuma retroatividade.
Artefato6 conserva saídas/exits; cleanup e Desktop off confirmados.

## Regra estreita a implementar após revisão

Manter comparação exata de todos os demais metadados. Se antes/depois
forem iguais, aceite original segue. Se diferirem, aceitar **somente**:
zero linhas adicionadas e exatamente as três linhas `missing` acima
removidas, cada uma uma vez, sem perder multiplicidade ou suprimir outro
erro. Isso é adição de diretórios antes ausentes, não alteração arbitrária
de arquivo preexistente ou aceite genérico de diferenças que "melhoraram".

Para cada um dos três: lstat confirma diretório real, não symlink, UID/GID0,
modo inteiro sem setuid/setgid/sticky nem escrita de grupo/outros, com
leitura/execução do dono. A saída `rpm -Va` sem novo erro também precisa
confirmar os atributos esperados pelos headers RPM. Qualquer outra linha,
arquivo, dono/modo inadequado ou prova ausente continua recusando. Todos
os NEVRAs/bytes OS, hashes antigos /etc, chaves/assinaturas, novos RPMs,
modo/xattr/diff e gates de commit continuam obrigatórios.

Registrar `base_verify_unchanged=false` quando as três restaurações forem
aceitas, com lista e fatos medidos, e `base_verify_accepted=true` para a
política identificada. Host/probe devem exigir aceite coerente com a lista;
não continuar alegando que a baseline foi idêntica. Sem restauração,
unchangedtrue e lista vazia. Schema é privado de preparação, não API nova.

## Cache auxiliar, sem outro arquivo inesperado na imagem

`ldconfig` tem cache auxiliar opcional; o loader usa o cache principal.
Não mudar `/etc/ld.so.cache` nem desabilitar linker. Referência:
https://man7.org/linux/man-pages/man8/ldconfig.8.html (`-i`).
Se a baseline atestar `/var/cache/ldconfig` ausente, depois de lstat e
dos fatos do diretório, permitir apenas zero entradas ou `aux-cache`.
Se existir, exigir regular/não symlink, root:root, sem bits especiais ou
escrita de grupo/outros, tamanho<=16MiB, calcular tamanho/hash e removê-lo
seletivamente **antes** da verificação final. É arquivo novo no container
próprio, dentro de diretório antes ausente; nunca apagar preexistente,
desconhecido, árvore ou dado de cliente. Não remover o diretório restaurado.
Recusar qualquer entrada extra/erro. Conferência RPM final após cleanup
mantém a prova de que nenhum arquivo requerido novo foi perdido.

Diff aceitará somente o diretório restaurado `/var/cache/ldconfig` junto
às outras duas pastas já cobertas por /usr, após seus fatos validados.
Não liberar prefixo genérico /var/cache nem novos arquivos de cache.
Sem remoção do cache se a baseline não comprovar a ausência do diretório.
Testes negativos para todos os outros deltas/tipos/modos/owners e verdade
do campo unchanged, além de manter diagnósticos públicos limitados.

Após código/testes, fontes/pins e novo roteiro de execução terão revisão
antes de ação. Mesmos nove RPMs originais/cópia local verificada, sem novo
download; mesmos caps7 só builder sem rede/2GiB, tempos e sonda final
128MiB/nonroot/RO/capdropALL. Não ampliar limite ou exceção em execução.
Sem produto, cliente SQL, DB, worker, B-1/B-2/D-090 fechado, commit/push/deploy.

## Implementação local sob delegação, antes da ação (v11)

Desenho aceito37030 com três precisões incorporadas: literais exatos com
cinco espaços e multiplicidade1; fatos/cache antes do `rpm -Va`; esquema
coerente compartilhado por host/sonda. Nenhuma ampliação em execução.

Escolha determinística do cache, conforme revisão: consultar `rpm -qf`
literal e registrar rc/saída pública. Se dono for **somente glibc x86_64
preexistente** com NEVRA já conferido, manter e liberar no diff só o caminho
exato do aux-cache; ele passa por stat/xattr e verificação final RPM. Se
rc1/saída exata confirmar sem dono, remover seletivamente após provas de
arquivo novo/regular/root/seguro/limitado. Outro dono, erro ou conteúdo
desconhecido recusam, sem fallback. Marcador físico antes de instalar
comprova diretório ausente, além da linha missing da baseline. Nenhum fato
de owner/modo foi declarado medido em Linux ainda.

Flag unchangedfalse/acceptedtrue, lista exata e fatos reais são obrigatórios
na restauração; unchangedtrue exige lista/fatos vazios. PolicyId explícito;
host usa o mesmo validador puro do payload pinado, que importa só stdlib
sem IO no import. AUX_PATH é string POSIX canônica no contrato, independente
do Path Windows do host. Nenhum RPM é executado no Windows por isso.

92 testes puros/fake-stat, Ruff/format/mypy de três testes passaram. Casos
negativos: outros missing/linhas/duplicados/spacing/config marker; symlink,
uid/gid/mode inválidos; flags incoerentes; outro owner/erro/arquivo extra
ou diretório preexistente nunca apagados. Não são prova de permissões POSIX
no Windows nem certificado do runtime; isso depende da rodada Linux.

Novo root `C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053`,
task9c3010f036094abb98ecd763187091ca. Cópia byte-idêntica dos nove RPMs
originais e probe novo; origem completa conferida. Sem download ou Docker.
Estado unobserved/invokedfalse/readytrue/downloadfalse/copyorigin/sem phase.
Manifesto2cd26833ee99e026092767d363d16a7beeb943b3c4a3573e05ed416bccf46bdc.
Fontes: `docs/poc/evidence/oracle9-python-procedure-v11-20261023.json`, SHA256
`b6ce92fe2a025c4f3d638af9da6798aa76de90047ad680afb659b8ac45635b23`.
- start860fdd58e0cdbbda26674d621f1fc4b8ec4d71ff636a6c4d13b3b80141893a38
- control7620f69a192453e9cccb369f3077870b82fe8347b6bc6bf8976b297c082077a1
- restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28
- hosteb20562e976cfb5405b24174db9d3c40abae9068817ae4de77626d6cb1067356
- payload23851a8a7c2947f2900c083aae42d1981ca869a19a3fa463545b373a75acf382
- biblioteca5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896

Após revisão/pins/exits, chamadas separadas, **uma vez e sem D**:
```powershell
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\start_desktop.ps1'
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\state_control.ps1' Observe
# Mais duas Observe após cada terminal0, depois:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\state_control.ps1' Ready
& '.\.venv\Scripts\python.exe' -I -B 'docs\poc\oracle9_python_prepare.py' 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053'
exit $LASTEXITCODE
# B terminal/cleanup/ps/identidade próprios confirmados:
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\state_control.ps1' AllowStop
& '.\.venv\Scripts\python.exe' -I -B 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\restore_desktop.py'
exit $LASTEXITCODE
& 'C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-0b9ae053\state_control.ps1' Off
```
Caps7/networknone/2GiB/tempos/saída máximos iguais; sonda128MiB/rootfsRO/
nonroot/capdropALL. Falha aborta/sem override/replay ou outro writer. C só
ownership/cleanup/ps conferidos; diagnóstico read-only próprio predeclarado.
Não converter seis NOT_PASSED anteriores ou B-1/B-2/D-090 em PASS.


## Delta revisado antes da ação — v12

Revisão somente leitura 22961 aceitou o v11 sem bloqueador, com três
melhorias incorporadas antes da execução: coleta de diretórios ausentes sem
falhar antes do diagnóstico RPM; cache valida somente seu próprio diretório;
remoção da antiga permissão /var/cache/dnf e carregamento do validador dos
bytes do payload já hashados (compile/exec do código próprio, sem reabrir a
fonte para executá-la). Sem ampliar aceitação da verificação RPM.

98 testes direcionados passaram (6 casos novos: três negativos DNF e três de
diagnóstico/cache). Ruff completo dos três testes, mypy strict dos testes,
format dos seis arquivos e Ruff E9/F63/F7/F82 dos scripts passaram. Uma
invocação adicional de Ruff completo nos três scripts encontrou 143
avisos de estilo/tipagem/literal/subprocesso, não corrigidos neste lote;
não declarar que esses scripts passaram no lint completo. Nenhum produto
mudou e nenhuma execução Linux foi feita com este delta ainda.

v11 permanece preparada e não executada, com fontes preservadas na cópia.
**Só v12 será candidata**, após a revisão curta deste delta. Nova raiz:
`C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-python-20261023-f683aa16`.
Task `ecbf0315d8704df69e726c741e618615`.
Manifesto `516eca4cab4ace315eb48bd131ebdfa3851391f7e9a3a3d870d4a3f66b017c67`.
Cópia de fontes/estado `docs/poc/evidence/oracle9-python-procedure-v12-20261023.json`,
SHA256 `8832b0a8b095f9c6ef4c4278732b6fa0804d9d898051dcf0837f24a8832d7031`.
Pins novos:
- start `2fd12a13d385f433743af55b460e68db511253ed1043e9a3e33fa10d97269874`
- control `e94b8bdba44e4727614fc214fb6c27411b0219d355408a4306b48a4f4087ee4d`
- restore `51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28`
- host `c07b770bbce636742a8fed4fc02ac019aea6b0625c4715c184949d6a8c88f484`
- payload `0f5a286b8117b226327cf579009e0b52ba7070b89fcc213c1db94717e8888580`
- biblioteca `5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896`

Mesma sequência acima, substituindo somente a raiz por f683aa16: conferir
pins/origem/estado; A uma vez; três Observe separadas, Ready; B uma vez;
AllowStop/restore/Off somente com cleanup/ps/ownership comprovados. Cada
chamada confere terminal e exit antes da seguinte. Sem D, rede de builder,
novos limites, fallback ou retry. Diagnóstico dos diretórios não é previsão
de aprovação: qualquer delta diferente recusa. Não há imagem Python ou
Gateway disponível ainda; B-1/B-2/D-090/SQL/produção continuam abertos.

Revisão curta 45624 terminou sem bloqueador antes de A. Pins, origem e
estado Temp reais conferidos pelo operador do procedimento. A terminal0;
observações em andamento, nenhum B executado até Ready terminal0.


## v13 — somente diagnóstico público de ownership, antes da ação

v12 consumida uma vez: NOT_PASSED por caminho novo sem owner comprovado;
nenhuma imagem commitada, cleanup/off medidos (PYTHON-VALIDATION). Agora
registrar antes da recusa todos os caminhos novos não provados: count,
SHA da lista ordenada e até40 prefixos512 caracteres. Recusa permanece;
nenhum arquivo passa sem owner, nenhuma exceção/cache/limite novo. Registrar
também o ramo de verificação RPM aceito antes de outras conferências.
Não interpretar lista truncada como inventário completo nem diagnóstico
como origem/causa.99 testes puros direcionados; Ruff/mypy dos testes e
format dos seis arquivos verdes. Mesma ressalva do lint completo de scripts.

Nova raiz6bdaacb4/taskf87ad0fbe8cc49d19e66341438ccd048, v13 sem ações ainda.
Manifestoca0e0787a1569c3e98e102d4a28239e31f661d91f45cd0c7b423815f4c81e29e.
Cópia `docs/poc/evidence/oracle9-python-procedure-v13-20261023.json`,
SHA99a8868a60fb10a5cbfa110c750dcc2e642709bc552d26ab7a3460163715cd1d.
start490edd1618c6e54fb7abedd5c5a8c45c89e3d45c14b36b45ddfa31e9b2355462;
control5f93a36dc812f98ce2fe914969cdf998c4250c3f5ed6d73496a751bc03e8fcee;
restore51f619a8d4abcaf61918ec484c19529c13bba553e7353ce0b13c724496f5fc28;
hostc07b770bbce636742a8fed4fc02ac019aea6b0625c4715c184949d6a8c88f484;
payload1962eac5f3b2ec369aab55b099f64be00656479e001d208de1e7fcbd7a04ef2e;
downloader5471e1f61fb6f782055c3695746a2786f223bdf88112e3fe7edf3b42fed8c896.
Mesma A/Observe3/Ready/B uma vez/C, raiz nova substituída no roteiro; sem D,
retry, override, novos limites/caps/rede. Próxima revisão somente leitura
antes de A, sete NOT_PASSED preservados; não altera gates do produto.

Revisão62117 sem bloqueador, antes de A; recomenda A/Observe3/Ready/B
sem pausa longa. Regra do operador incorporada: interrupção aborta sem B,
registro próprio antes de retomar. Pins/estado reais conferidos.
