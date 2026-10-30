# Oracle9 — contexto offline37 medido em2026-10-26

Resultado: OFFLINE_CONTEXT_VERIFIED/exit0, uma execução só de cópia no
Windows, sem Docker/pip/import de wheel.37wheels/22.643.029bytes e dois
arquivos auxiliares:39arquivos/22.898.364bytes no contexto final. Códigos,
wheelhouses e fontes de origem preservados. Ainda não existe imagem com
a aplicação instalada nem serviço disponível.

Raiz C:\Users\w.filho\AppData\Local\Temp\maskgw-oracle9-install-context-20261026-4efda1b2,
taskf5d8480ea8e44fc5b37b37eee1ecf871. Programa
46108ce61026c09c1beb1c562ece6cad427a393d4d8e9e49f19853cc193f1907,
estado4f1b648d/snapshotv2ff4718ee. O estado inicial imutável conserva
invokedfalse; **invoked.json exclusivo** registra o consumo, ready.json
registra sucesso, e a raiz já não pode ser admitida como fresca.

Revisão pré-ação do Claude2 aceitou o comando único sem bloqueador.
Precisão local menor sobre alinhamento de linhas de tamanho registrada no
plano; programa não alterado, admissãoD já valida as identidades por linha.
Conferidos pins/estado fresco antes da chamada; nenhuma fonte mudou até
o fim.24testes novos e190relacionados:189pass/1skip de symlink anterior;
Ruff/mypy do teste, format2 e sintaxe do helper nos escopos declarados.
Mypy inicial de fixture corrigido só por anotação de lista, sem comportamento.

Antes/depois da cópia: D/I, dois wheels próprios e source_manifest do
projeto conferidos novamente. Bytehashs de todas as cópias/lock/manifesto
conferidos no fechamento e de novo depois do terminal. Manifesto descreve
1.382arquivos regulares de instalação e oito wrappers esperados; nenhuma
colisão de caminho, .data ou .pth nos37wheels. Base pip/setuptools e
artefatos gerados pelo pip ainda serão medidos na instalação futura.

Pins para o próximo lote:
- context/manifest.json:251.688bytes, SHA
  359a055ccbd7689dce453f7979f5d0ac137cd5963f599d462400abe7f1d87c22.
- context/requirements.lock:3.647bytes, SHA
  31cc18e69827dd1558fc421c6980d5484e3322700d0a6372508129be2da27c07.
- ready.json: SHA
  3c7959cb6f5a0d89cf827e4dbc85216195be7e62a7415da0081292a195cea92e.
- docs/poc/evidence/oracle9-install-context-result-20261026.json:
  277.170bytes, SHA
  6c70217fe14d9f85b5a91d02e44c461a08c50b5a22a01c744bb25cf4c331eb90;
  preserva bytesUTF8/tamanho/hash de estado/marcador/ready/manifesto/lock.

Wheels continuam somente no Temp, sem binários no Git. Perda/mutação
bloqueia o próximo lote até nova montagem revisada, sem redownload ou
fallback silencioso. Host/payload da instalação ainda não implementados;
desenho e precisões em PHASE-9-ORACLE9-OFFLINE-INSTALL-PLAN.md. Próximo
código/comando/recursos/ownership/cleanup/restauração terão revisão própria
antes de Docker. B-1/B-2/D-090 gate2, SQL e produção continuam abertos.
Nenhum banco/container existente, secret, produto/src, commit/push alterado.

Revisão final do Claude2 aceitou contexto/registro como entrada fixa sem
bloqueador. Confirmou somas, pins/consumo do estado e garantia de alinhamento
herdada da admissãoD. Implementação de host/payloadLinux pode prosseguir
segundo o desenho, mas passa por revisão antes de qualquer ação Docker.
