# W1 app-only update — host e ciclo fresco, proposta antes dos efeitos

2026-10-27, sob delegação. Payload566c46a8 congelado após revisão, contexto
d4d4b29b/ready5e908fa3 materializado, wheel6b63f239. Este documento concretiza
o coordenador host para uma única instalação pública/sonda. Sem executar
DockerCLI, Desktop, pip, SQL, imagem ou serviço até código/testes e comandos
serem revisados. Não reutilizar controles consumidos da rodada D-120.

## Um programa host específico, um escritor, sem fila de comandos

O coordenador específico docs/poc/oracle9_w1_run.py fará A→nove observações→
preflight→READY→B e restauração. Os builders puros já revisados ficam
congelados em oracle9_w1_prepare.py, capturados por SHA pelo coordenador.
Uma invocação -I-B no Python nativo do Windows3.11.3, raiz
própria só attempt.json no início, sentinel antes da ação A. Sem modo para
rodar comando de usuário, callback de backend ou contexto remoto. Estado
e observações públicas serão persistidos por exclusivo/flush/fsync e replace
somente no próprio attempt; falha parcial não é liberação para retry.
Sem credencial/DSN/env de produto, nenhuma pasta de aplicação/DB existente.

Bibliotecas capturadas por hash:
- foundation0b0bb171, apenas pins/save/ENV/ENTRY/identidade do runtime;
- policy401afa8c, só create_args/validate_container/identity/report_line/
  validate_candidate_image, em namespaces separados para origem e candidato;
- bounded58c692a7, CLI por --context desktop-linux, sem trocar contexto;
- context94cfa911, só admissão/check_delta da entrada imutável;
- clock sampler6bcbdbe5 e freshnessd2b485c2, sem duplicar clock/estado.
Não chamar main/context_inputs dos programas históricos. Na policy nova,
rebind **somente** metadados globais PAYLOAD_SHA566c e MANIFEST_SHAd4 para
labels/identidade do CID/candidato; policy da imagem de origem fica intacta.
Cada efeito valida os bytes capturados diretamente contra os pins do estado,
não apenas relê um arquivo e presume ser o mesmo código já capturado.

## A e observações com idade em código

Preflight offline: helper/payload/contexto/CLI/Desktop/shell/config/context
hashados e diretório/contexto/endpoint locais confirmados; controles e comando
já revistos. A amostra cheia de boot/tick/UTC ancora A na chamada efetiva,
antes da descoberta/start; sentinel impede segunda A no mesmo attempt.
Consultar processos Docker via PowerShell fixado, sem commandlines/env.
Se já ativo, registrar active/preservar e nunca iniciar/parar por esta rodada.
Se off, registrar START_RESERVED antes de Start-Process Hidden, sob allowlist
Windows pública já revisada, e capturar PID+FILETIME decimal como string.
Não recuperar ownership pelo nome se esse PID sumir; abortar sem retry.

Nove observações exatas e fonte de identidade de aplicativo a cada ponto.
Para esperar o mínimo10s sem presumir quanto custa CIM, usar a mesma função
kernel32 do sampler apenas para calcular espera, limitada a10s; a admissão
só usa a amostra completa posterior (boot/app→tick→UTC). Sem segundo clock
ou P/Invoke no PowerShell. Se ticks de espera voltarem/idade já estourar,
falhar, nunca dormir tempo ilimitado. Wait/helper não é observação aceita.
Counter que inclui suspensão/UTC secundário/boot exato e estados terminais
seguem freshnessd2. Gravar também amostra recusada e motivo separadamente.
Logs curtos de progresso por fase, sem deixar root sem notícia por60s.

Entre O8 e O9: preflight Docker com exits conferidos:
version/info linuxamd64/cgroupv2/kernel6.18.54.1-microsoft-standard-WSL2,
memória≥2GiB, inventário vazio, imagem87871290 e três layers exatos da evidência,
tag de destino livre. Se kernel/profile mudar, registrar novo fato e abortar
este attempt antes de B; não estender prova D-120 silenciosamente.
READY exige amostra cheia até30s do O9; após O9 há só inventário fresco,
check-app e sampler. Antes de O9 o preflight ocorre antes de calcular qualquer
espera residual mínima; não somar10s desnecessários aos15s de CLIs e ao sampler.
Timeouts dos subprocessos não incluem custo de hashing/admissão e filesystem;
esse custo também entra na idade efetiva, e qualquer excesso real aborta.
Entrada real B tem outra amostra cheia, até30s de READY e300s de A. Persistir
B_CONSUMED **antes** de primeiro create/cp/start. Nenhum estado resetável,
pause longa ou retry. Lentidão pode abortar; não aumentar teto para obter verde.

## B: atualização e sonda em CIDs próprios

Imagem base exata87871290, label de origem c23dd3df e layers conhecidos.
Novo CID install não-running/root, perfil anterior512MiB/swap0/pids32/CPU1/
nofile128/core0/caps0/NNP/seccomp/networknone/tmp64MiB/shm8MiB, sem volumes,
mounts, healthcheck/restart ou host namespaces. Nome/task/source566c e
manifestd4 registrados antes de create; stdouthex e inspect conferidos.

Comando nativo usa payload comprimido capturado/hash566c e bootstrap que
confere SHA descomprimido antes de compile. Medir antes de A a **linha inteira**
do CreateProcess no Windows (subprocess.list2cmdline), CLI/context/args,
--entrypoint/ENTRYpython-I-B e paths/digests incluídos, exigir≤26000caracteres
(limite OS32767). Recusa antes de Docker se exceder; nenhuma adaptação durante B.
Perfil e comando exatos admitidos antes de start.

docker cp copia conteúdo `context/.` ao path novo
/opt/maskgw/w1-inputs-<task>, não diretório aninhado. Sem -L e sem -a: dono
default0:0 no container, confirmado pelo payload. Não copia raiz do checkout.
Pre/postadmissão do contexto host, inspect de identidade antes do cp/start.
start --attach captura stdout diretamente (log-driver none), não depender
de docker logs. Cada execução ativa tem limite300s/saída1,5MiB e watchdog
independente600s, rearmado somente após recolher a thread da execução anterior.
Não há teto global600s para toda a fase B. Sem prometer teto absoluto de
syscall; CLI metadata10s/2MiB, cp/commit60s. O start usa exatamente as34chaves
públicas Windows do procedimento HELD revisado, nunca a allowlist curta da
CLI. Gravar só nomes presentes, nunca valores ou variáveis de ferramentas.

Só exit0, PID0/nonrunning/semOOM/Dead, resultado W1_APP_UPDATE_VERIFIED com
managed_inputs_removedtrue e SHA de atestação bem formado permitem continuar.
Qualquer refusal/timeout/forma inválida impede commit mesmo que atestação
exista. Copiar apenas /opt/maskgw/oracle9-w1-installed.json, conferir SHA/
tamanho≤4MiB com o resultado, manifesto/ref origem e snapshots/delta L1.
Old atestação não é usada como fallback de sucesso.

L3 de docker diff: A/C sob ancestrais necessários/package/dist-info e A da
atestação nova; cinco módulos A e RECORD A/C obrigatórios. D somente de
diretório de M presente e idêntico no scan final. Sem D de arquivo/fora de M,
path estranho/traversal/duplicata. Duas formas com/sem D opaco testadas;
terceira forma aborta para revisão. Scan L1 é autoridade dos bytes.

Commit Docker só de CID parado verificado, tag nova/task própria, USER10001,
WORKDIR/ENTRY-I-B/CMDvazio/ENV da origem. Nova imagem exatamente4layers,
origem+um delta; labels task/source/manifest novos. Nenhum push de imagem.
Sonda em outro CID dessa nova imagem, UID10001/RO/networknone/tmp16MiB e
demais limites iguais. Mesmos checks de exit/profile/atestado, prefix3337,
Native/versões e W1 hashes/preloaded; diff da sonda vazio. Sem SQL/worker.

## Ownership e restauração, inclusive pré-B

Registrar intenção de create antes da CLI. Cleanup resolve só nome+task/
source/image que escreveu, mesmo se create retornou erro sem CID; nunca
apagar por nome parcial. Reinspecionar antes de kill/remove. Kill KILL só
se próprio running; provar nonrunning/PID0, rm sem force e ausência por CID,
reverso dos CIDs. Contexto/imagens antigas e recursos de terceiros preservados.
Watchdog usa só CID já identificado, nenhuma operação por nome coletivo.
Se SO/engine impedir prova, ownership retido, sem retry/sucesso/restauração falsa.

Inventário global vazio fresco e exit0 exigidos antes de stop do Desktop.
Se foi iniciado por esta rodada: mesmo boot e PID/FILETIME ainda exatos;
docker desktop stop com exit0 e ausência de processos Docker observada.
Cleanup pré-B não exige idade fresca, mas exige esses fatos independentes.
Boot/app diferente, sampler indisponível, CLI sem resposta ou inventário não
vazio impede stop: preservar e registrar pendência, sem matar por nome/prune.
Se inicialmente ativo, preservar ativo em sucesso/falha. Uma thread watchdog
própria recolhida/join confirmado; falha não vira cleanup completo.

Resultado só passa com atualização+sonda verificadas, CIDs removidos,
inventário restaurado, fontes/contexto intactos e Desktop restaurado ou
preservado conforme estado inicial. Host/controles/fakes e comando/estado
de rodada única serão revisados antes de A. Este desenho não executa nada,
não qualifica C1/W1 SQL/PG16 ou produção, nem cria job/segundo escritor.

## H1–H6 incorporados antes do código

Revisão do desenho sem bloqueador, com precisões obrigatórias nos fakes:

- H1: preflight completo fica **entre O8 e O9**, cinco CLIs com timeout3s
  cada (soma15s), mais check-app≤3s e sampler≤8s:26s de orçamento de sucesso,
  mantendo30s sem aumentar limite. Falha/cleanup não ganha promessa desse teto.
  Após O9, só recontagem fresca de inventário≤3s, check-app≤3s e READY≤8s;
  B tem nova amostra completa na entrada. Atraso real acima do teto aborta.
  Matriz simula todos os tetos, sampler lento e total300s vencendo.
- H2: construtor novo mede docker **create inteiro** com list2cmdline,
  instalação e sonda separadas. Medição offline preliminar do566c46a8,
 32598bytes/zlib17100/bootstrap23019chars:23988chars install e23957probe,
  margem2012/2043 até26000, sem Docker. ENTRY-I-B herdado é validado na imagem,
  não inventado como argumento extra de Windows. Medição será refeita com
  nomes/args reais antes de A. Se ultrapassar: ABORTAR antes de A. Alternativa
  previamente definida é transporte por arquivo público hashado fora de
  w1-inputs, com ciclo/cleanup/sonda RO próprios, a implementar/revisar em novo
  preparo; não escolher variante improvisada durante a rodada. Só argv é
  executável neste lote, pois medido com margem; não ampliar superfície sem
  necessidade implementando a outra variante agora.
- H3: namespaces completos ficam privados. Facade exporta só create_args,
  validate_container, identity, validate_candidate_image e report_line.
  Provar que rebind troca só PAYLOAD_SHA e MANIFEST_SHA; native_command e
  validate_diff antigos não fazem parte da facade. Não é sandbox Python
  contra introspecção/RCE, é contrato de arquitetura do chamador confiável.
- H4: Config inteiro da imagem nova deve ser igual ao da origem com somente
  labels modificados nas três chaves (conjunto exato). Registro histórico da
  origem contém6chaves de Config e4labels (inclui desktop ports.schemev2);
  conferir dados vivos pelo ID87871290, sem presumir normalização de chaves.
  O preflight exige exatamente esse Config esperado de6chaves/4labels antes
  de B; fixtures não são prova da forma viva. Hostname/Domainname/Cmd ou label
  inesperado aborta antes de criar. Registrar versão do Desktop/CLI e daemon
  junto com kernel; mudança de versão/label é fato novo, não normalização.
- H5: ancestrais C exatos são /opt,/opt/maskgw,/opt/maskgw/venv,
  /opt/maskgw/venv/lib,/opt/maskgw/venv/lib/python3.11 e seu site-packages.
  Sem w1-inputs/stash/tmp no diff, mesmo que pareçam arquivo inofensivo.
  D só diretório de M comprovadamente presente com linha esperada no scan.
- H6: stop Desktop≤45s; depois até10consultas de processos≤3s cada, com1s
  entre elas, cada resultado registrado. Ausência não comprovada conserva
  pendência, sem matar por nome nem declarar off por retorno do stop.

Se houve commit Docker mas a sonda/integração falhou, depois de remover os
CIDs próprios conferir novamente o ID e labels da **tag própria** e remover
somente essa tag com image rm sem force. Nunca remover por ID se houver
aliases de terceiros, nem apagar imagem antiga. Tag/cleanup incertos ficam
registrados sem sucesso. Em sucesso, imagem/tag verificadas ficam locais.

Precisão da revisão do código: ID retornado por commit é gravado antes da
validação. Rollback exige posse da tag (nome/RepoTags/ID conhecido/3labels/
três layers de origem+um), sem exigir Config exato da candidata recusada.
Config exato continua obrigatório para aceitar a imagem, não para apagar
somente a própria tag. Nunca remover tag de terceiro ou ID genérico.
