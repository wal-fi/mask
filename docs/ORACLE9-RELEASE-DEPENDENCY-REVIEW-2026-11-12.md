# Oracle9: triagem das bibliotecas da candidata antes da release

2026-11-12. Revisão independente do root para R13 do mapa de entrega.
Não é teste de exploração, inspeção atual da imagem ou aprovação de release.
Nenhum pacote/pin, código, teste, imagem ou ambiente foi alterado/executado.
O próximo lote do programador continua somente o desenho Proactor.

## Evidência local e canais de atualização

`PHASE-9-ORACLE9-OFFLINE-INSTALL-VALIDATION.md` registrou separadamente em
26/10 as três cópias abaixo; não as inferiu da versão do RPM. A imagem atual
não foi aberta nesta revisão e não se revalidou sua retenção no Docker.

| Consumidor na candidata histórica | Versão medida | Canal que precisa ser auditado |
|---|---|---|
| Python/SSL do sistema | OpenSSL3.5.8 | RPM/NEVRA e errata Oracle efetivamente instalados; banner sozinho não comprova ausência ou presença de backport. |
| `cryptography==50.0.1` | OpenSSL4.0.2 | Wheel e sua proveniência/build; a PyCA distribui wheels com OpenSSL estático. |
| `psycopg-binary==3.3.4` | libpq180000 e OpenSSL3.5.4 | Wheel e bibliotecas empacotadas, não apenas o RPM do sistema. |

A separação importa: a documentação do Psycopg descreve o extra binary
como autocontido; sua alternativa C ligada às bibliotecas do sistema é
outra modalidade de instalação. A PyCA documenta seus wheels estáticos
para Linux, macOS e Windows. Atualizar só o sistema não certifica as cópias
empacotadas. [Psycopg — instalação](https://www.psycopg.org/psycopg3/docs/basic/install.html),
[PyCA — static wheels](https://cryptography.io/en/50.0.1/installation/#static-wheels).

`deploy/constraints-tested.txt` se declara seed de resolução, não lock Linux
ou atestado de segurança. `pyproject.toml` fixa cryptography50.0.1; nenhum
desses arquivos foi editado. Preservar os artefatos antigos e seus resultados.

## Avisos oficiais confrontados com essas versões

Esta é uma amostra dirigida, não inventário exaustivo de CVEs ou SBOM.
Estar numa faixa upstream não prova explorabilidade, nem identifica
backports ou opções de build de um binário que não foi inspecionado.

| Referência | Fato do aviso | Relação com a candidata; conclusão limitada |
|---|---|---|
| CVE-2025-15467 | O aviso de27/01/2026 classifica como High o overflow no parser CMS; indica correção na linha3.5 em3.5.5. | A cópia3.5.4 exige triagem de build/correção e alcance da API. Não foi demonstrado parsing CMS hostil no Gateway. [Aviso oficial](https://openssl-library.org/news/secadv/20260127.txt). |
| CVE-2026-35189 | O aviso de29/09 descreve pressão de memória por CRLDP em certificados; classifica Low e indica3.5.9/4.0.3 nas linhas correspondentes. | As versões-base3.5.8/3.5.4 e4.0.2 antecedem essas correções. Requer examinar backports e verificação de certificados no caminho real, sem assumir que teto de tamanho do certificado limita a alocação. [Aviso oficial](https://openssl-library.org/news/secadv/20260929.txt). |
| CVE-2026-88823 e CVE-2026-95692 | O aviso de10/11 trata de caminhos específicos de AES-GCM-SIV. As releases com os fixes estão previstas para01/12/2026. | Não confundir AES-GCM-SIV com AESGCM usado pelo catálogo. Não inventar um pin baixável só porque o aviso cita3.5.10/4.0.4; examinar também correções/backports e alcance. [Aviso oficial](https://openssl-library.org/news/secadv/20261110.txt). |

O código consultado em `datasource/crypto.py` usa `AESGCM`, não `AESGCMSIV`.
Os trechos PGWire consultados usam TLS sobre o transporte TCP, não QUIC.
Esses fatos limitam inferências automáticas sobre advisories de outra
primitiva/protocolo; não são prova geral de que todas as bibliotecas e
entradas transitivas são imunes. Não classificar uma falha como corrigida
por ausência de exploração neste exame estático.

## Atualização disponível não equivale a aceite

A PyCA publicou cryptography50.0.2 em30/09, com wheels OpenSSL4.0.3; o
changelog também confirma4.0.2 para50.0.1. Isso fornece uma candidata a
revisão, sem comprovar cobertura de todos os avisos posteriores, ABI,
runtime Oracle, custo de bootstrap ou invariantes deste projeto.
[Changelog oficial50.0.2](https://cryptography.io/en/50.0.2/changelog/).

A página atual do Psycopg lista3.3.9 e correções de cancelamento/memória;
isso não informa por si a versão SSL de cada wheel Linux. Não deduzir que
um número de pacote novo significa libssl corrigida, nem selecionar pacote
a partir de snippet de busca antigo. [Release notes](https://www.psycopg.org/psycopg3/docs/news.html).

Trocar para psycopg C/dinâmico, compilar bibliotecas próprias ou adotar
outra família de OpenSSL não são alterações implícitas desta revisão.
Qualquer opção deve preservar o fechamento offline/hashado e os requisitos
de runtime/reprodutibilidade, sem instalar toolchain no container final
por conveniência ou modificar o host.

## Critério de fechamento para a release

Antes do aceite da imagem final, a revisão de R13 deve ligar:

1. Artefatos exatos de release, versões/NEVRAs, origem/hashes e bibliotecas
   efetivamente carregadas por cada consumidor, separando as três cópias.
2. Avisos aplicáveis, evidência de backport/patch ou decisão de alcance
   fundamentada nas APIs/entradas reais. Não basta comparar banners.
3. Escolha de pacotes/builds e fechamento Linux revistos antes de qualquer
   instalação; novas imagens/contextos, sem alterar attempts consumidos.
4. Revalidação proporcional de catálogo/AEAD, chaves/rotação, TLS/SCRAM,
   conexão PostgreSQL, packaging/imports, worker e custos do domínio.
   Mudança de dependência não herda automaticamente o B-2 medido antes.
5. Gate final instalado e evidência negativa de sigilo/read-only/masking,
   mantendo as medições antigas como históricas, sem rebatizá-las PASS.

Não existe finding explorável reproduzido por este documento, nem foi
atribuída severidade própria ao Gateway. A aprovação de release de R13
continua pendente da triagem e dos artefatos reais. Isso não transforma
automaticamente a candidata secretless de laboratório em inválida para
o procedimento W1 já delimitado; esse uso continua sujeito aos seus
guards/revisão e não foi executado aqui.

O agendamento existente de20h05SP e as restrições de quota permanecem
inalterados. Não houve chamada nova de programador, pacote enviado a
outro modelo, Docker, SQL, carga, leitura de binário/runtime ou deploy.
