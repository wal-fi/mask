# Primeiros oráculos N-S: revisão antes de congelar RED

## Fechamento da revisão congelada37a — 2026-11-16

Reabertura R1 concluída na ordem registrada: short de MEMBERS mínimo−1, fault padded e duas regressões positivas; AST de todos os outros nós igual ao7601. Teste37a757ad69b8d032e44e59d008a183149f9bb1f6fd0f46901553e0b00fbc9224 congelado após100casos/98PASS/2FAIL contra fonte86d INALTERADA. RED98 e RED100 preservados; nenhum assert antigo relaxado.

Depois da correção fonteONLY465, o mesmo teste mediu100/100PASS. Matriz21arquivos2.321PASS,sem falhas/erros/skips/deseleções;estáticos377PASS. Fonte e teste entram juntos. Ver EXTERNAL-JOB-ADOPTION-VALIDATION e external-job-adoption-final-validation-20261116.json. Aceite só de oráculos e comportamento com SDK falso; todas as provas físicas e gates de produto continuam OPEN. Histórico abaixo.

## Reabertura estreita após prova independente R1

Fonte86d passou98/98, mas Root encontrou um erro no dado de short para MEMBERS: sizeof−1 ainda está no intervalo válido da lista variável admitido pelos leitores pinados. Ver TODO external-job-adoption-source-review-20261115.md R1 e a sonda de compatibilidade. O RED98/7601 original NÃO é apagado nem reclassificado como teste de produto completo.

Somente o fake short de MEMBERS (mínimo requerido−1) e DUAS regressões positivas de padding serão acrescentados, em teste primeiro. Nenhuma asserção antiga é afrouxada. Fonte86d fica READONLY até medir o novo RED com fonte presente, depois nova revisão congelada. Essa é correção motivada por contrato independente, não autorização genérica para mudar oráculo para obter verde. Outros nós do teste devem permanecer idênticos em AST. Demais regras de revisão e sigilo permanecem.

## V3: oráculos revistos e RED98 congelado localmente

40367 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODO delta das três mudanças sobre as952linhas V2: apenas _control preserva o PRIMEIRO snapshot, uma sanidade nova e a formatação pedida. AST de TODOS os demais nós comprovadamente idêntica à V2. Final7601d8a8637e5899a3107fa1975ed13a189c2d53cbd3fa013d559df447b8e4b8,40.677bytes/966linhas.

Sonda do helper real: segunda consulta/controle NÃO substitui primeiro snapshot; o predicado real agora REPROVA a chamada extra. Oráculo de import aceita corpo inocente e recusa corpo com stat, com traps restauradas. Nenhum fonte real foi criado por essas sondagens. Sanidades identificadas só como prova do fake.

Ruff/format PASS, mypy strict win32 alvos3.11 e3.14 PASS em1arquivo (3.14 somente estático). Pytest completo deste teste:98casos,4sanidadesPASS,94FAIL SOMENTE com a mensagem exata de fonte ausente,0erros/skips/deseleções,6.871s em JUnit. Root conferiu CADA motivo de falha, não apenas o total. Recibo external-job-adoption-frozen-red-20261115.json e cópia raw local preservam bytes; não publicar o teste RED sozinho na suíte.

Teste congelado LOCALMENTE nesse SHA. Próximo único lote: mesmo C2 escreve somente docs/poc/oracle9_w1_external_job_adoption.py, Read/Edit/Write restritos, sem comandos/execução. Não mudar oráculos, referência, contrato, backend/adaptador/C0 ou pins para obter verde. Root lerá TODA fonte e fará QA falso antes de integrar fonte+teste juntos. Atenção à compilação de bytes: não herdar flags future do carregador que alterem a semântica do backend dataclass em namespace isolado. Nenhum registro de owner/módulo vivo novo.

Continuam não admitidos os direitos reais, N-H/N-C, transferência, kernel, S/G e gates nativos/produto. Nenhuma execução de DLL/job/processo/thread/loop real pelo lote N-S; os únicos processos são as ferramentas de desenvolvimento/QA autorizadas. Sem Docker/PG/SQL/runtime/config/privado/binário/estado16/tentativa/deploy. O objetivo continua o Gateway funcional em produção, não a substituição por fakes. Histórico abaixo.

## V2: contenção corrigida; snapshot ainda substituível

66781 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root leu TODAS952linhas da V2d05d87122d2dbaee92e81a73b237312f393468161f11ec235dd98a9cf5152d05,39.984bytes; fonte AUSENTE. Ruff PASS; mypy311 e314 PASS;3sanidades só do fake PASS. Format ainda pede APENAS colapsar a assinatura de test_malformed_internal_shape_is_refused_internal_and_held em UMA linha (não quebrar em várias). Não mudar pyproject nem usar supressão.

A nova asserção de contenção rejeita lista vazia, medido pelo predicado real; falhas agora são injetadas depois da criação e exigem terminação positiva do OUTER. As lacunas de categoria/AST/erro ordinário e os tipos foram tratadas na V2. Resta um defeito do próprio fake, reproduzido SEM fonte: _control substitui snapshot em TODO controle. Duas consultas roteirizadas ao mesmo controle deixam calls1→2 e snapshot trocado; o predicado REAL snapshot is not None and kernel.trace()==snapshot AINDA passa. Recibo external-job-adoption-v2-oracle-probes-20261115.json. Não é finding de produção nem prova nativa.

Corrigir SOMENTE:
1. Preservar o PRIMEIRO snapshot: depois de inicializado, nenhum controle posterior pode trocá-lo. O traço vivo continua registrando todas as operações; segunda consulta/controle deve divergir desse primeiro snapshot.
2. Acrescentar uma sanidade do próprio fake que dispara o controle, guarda primeiro snapshot, força nova chamada/controle e demonstra identidade do primeiro snapshot preservada mais trace diferente. O oráculo do adopter permanece comparando com o primeiro snapshot, sem atualizar expected após efeito.
3. Colapsar a assinatura exatamente como format --check solicitou. Preservar todos os demais oráculos e tipos. Não executar comandos pelo programador.

Root lê TODO delta e verifica que AST dos demais nós é igual à V2, repete sondagem, sanidades e gates. Só então mede/fixa RED completo. Nenhuma fonte antes disso; não publicar testes parciais como produto verde. Histórico abaixo.

53214 TERMINAL0/service success/is_errorFalse, sem denials, recuperada. Root confirmou zero escritores e leu TODAS815linhas finais do teste bef17b03b430fe8fb04f9f27d91e7ada86fefd94df99254329b2c03ce06a521a,33.687bytes. Fonte continua AUSENTE; nenhum RED foi congelado. Kernel/contratos/fontes anteriores não mudaram.

Medições iniciais:3sanidades só do fake PASS,0falhas/erros/skips; Ruff2diagnósticos B010/B009 na linha95; format uma assinatura; mypy311/314 um erro cada na linha742 (reuso da variável arguments com tuplas de aridades diferentes). São gates do TESTE, não produto. O oráculo de pureza aceitou um módulo inocente sintético em arquivo .py.txt separado; o fonte real não foi criado. As sondagens dos predicados abaixo usaram AST das asserções reais sobre dados sintéticos, nunca um adopter substituto ou efeito nativo. Recibo external-job-adoption-initial-oracle-probes-20261115.json.

## Corrigir somente o mesmo teste

1. **Efeito depois do primeiro controle pode passar.** A asserção kernel.calls[-1]==QueryInformationJobObject aceita uma consulta EXTRA do mesmo nome depois do controle; a sondagem a avaliou como True. Registrar no fake um snapshot exato de calls/roles/query_kinds quando o controle é disparado e exigir igualdade depois de adopt, antes e depois das recusas seguintes. Não basta comparar o último nome. Preservar identidade do controle/estado HELD e nenhuma coerção opaca.

2. **Contenção vazia pode passar.** set(terminated)<={outer} aceita lista vazia, confirmado pela sondagem. Os quatro casos de falha PRÉ-RESUME precisam materializar criação suspensa e confirmar positivamente que o OUTER foi terminado, sem resume e sem uso indevido de C. Injetar a falha de C SOMENTE DEPOIS da criação, por papel/job/classe de informação, para que uma checagem legal anterior não faça o teste aceitar/recusar o cenário errado. Exigir o efeito de contenção pertinente, não apenas ausência de alvo estrangeiro. Preferir esse endereçamento físico às contagens globais frágeis de QueryInformationJobObject.

3. **Domínios/categorias fracos.** No máximo permitido2^64−2, o fake não conhece tal job: exigir REFUSED_QUERY e consulta observada, C retido e seguro; result em RESULTS diferente de INPUT ainda aceita ADOPTED indevido. Adicionar valores built-in inválidos de handle nas formas internas (por exemplo0/INVALID e bool em quarentena), cobrindo a exigência de intervalo válido além do tipo exato. Não sondar opacos.

4. **Ramos do contrato ainda sem oráculo direto.** Acrescentar: (a) backend Python válido, pin sintético deliberadamente ajustado SÓ no namespace privado do módulo novo, mas com premissa AST de despacho quebrada; marcador NÃO executado e ADOPT_SOURCE; (b) erro Python inesperado da lógica da adoção, além de forma interna corrompida. Para(b), está autorizado um fault SCOPED do port stdlib ctypes.byref após setup, por exemplo ValueError/MemoryError, sem patch de método/função do produto: REFUSED_INTERNAL, C retido, estado READY, e close normal só depois de restaurar o port. Para consultas, cobrir comprimentos/estruturas inválidos também antes de members e o ramo de members não vazio sem confundi-lo com accounting não vazio. Não executar código adulterado só para obter uma falha.

5. **Lint/tipagem/formatação.** Resolver B010/B009 sem noqa/ignore/cast ou mudança de pyproject. O problema da linha742 pede variáveis distintas ou tipo de tupla apropriado, sem enfraquecer assert. Respeitar os nomes do SDK no fake, mas usar adaptação legível de ports. Deixar Ruff/format/mypy estritos.

6. **Escopo das armadilhas de pureza.** A sonda inocente passou. Entretanto Path.stat/open/lstat/resolve globais devem ficar em monkeypatch.context limitado ao corpo carregado e restaurar antes de propagar eventual erro ao pytest, para não bloquear o próprio diagnóstico do framework. Preservar a distinção correta entre carregar o teste/harness e executar o corpo do novo módulo.

Não é correção de finding de produção: ainda não existe implementação N-S. Não escrever fonte, modificar referência/frozen tests/backend/C0/pins, executar comandos ou enfraquecer asserções. Mesmo C2/sessão51ea0d85/Opus5.5/medium, Read/Edit/Write SÓ o teste. Root lê TODO delta e repete checks proporcionais antes de medir e congelar RED. Todas as restrições de efeitos nativos/Docker/PG/SQL/runtime/config/privado/binário/estado16/tentativa/deploy continuam; gates agregados/produto OPEN.
