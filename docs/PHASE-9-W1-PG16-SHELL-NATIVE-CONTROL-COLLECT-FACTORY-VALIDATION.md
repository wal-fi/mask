# Fábrica privada de coleta — validação com fakes

2026-11-03, America/Sao_Paulo. Trabalho sob delegação geral, sem aprovação
individual inventada nem autorização nativa inferida. Claude2 programou na
única sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f, modelo
claude-opus-5-5, effort medium; o assistente principal revisou e executou os
gates. Base HEAD/origin7af79b8,0/0 e árvore rastreada limpa no início.

## Delta e bytes

Somente a composição privada anterior109ab960 foi estendida; ela permanece
no Git e em accepted-109ab960.source.txt. Não foi copiado um framework,
proxy ou segundo ciclo de limpeza. Todos os pins upstream e estado16
permaneceram intactos.

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| docs/poc/pg16_shell_native_control_collect_pinned.py | 5373 | 37b098cf604099a8aa9e64c4a3569ce06c6fe389188eba9a2b46478b04a8285e |
| tests/test_pg16_shell_native_control_collect_factory.py | 16379 | d6b15ac13c86b9c330ea574e36d2bb965573bad7d0d03d848483b4cd26eebe28 |
| testes antigos da composição, inalterados | 21009 | a3ebf78bb3f9169bc846be54c1a7c1816fd3c5388e63471b6789fe5114fa1c8a |

A assinatura ganhou api_factory=None, exclusivamente keyword-only. Sem
fábrica, a API anterior continua funcionando. Os dois tipos/tamanhos/hashes
de fontes são conferidos antes de qualquer exec ou fábrica. API explícita
junto com fábrica, ou fábrica não chamável, são COLLECT_ARGUMENT sem
consumo. Ausência de ambas continua COLLECT_UNAVAILABLE sem consumo.

O registro publicado antes do primeiro exec ganhou a referência original
factory e factory_started=False. Depois do exec do backend, o latch vira
True antes da única chamada; a fábrica recebe o próprio record.native.
A API retornada entra em record.api antes do construtor. Retorno None é
UNAVAILABLE com tentativa consumida, sem backend nem política. Erro comum
no bloco protegido é INTERNAL fechado; controle propaga com a identidade
original e sem liberar o registro. Os ledgers não são substituídos ou
limpos pelo wrapper.

As fábricas exercitadas são Python fakes. A nova capacidade é um seam
privado, sem autenticação: callback poderia ter efeitos arbitrários, mas
nenhum desses efeitos é autorizado ou comprovado pelos pins. A composição
não referencia nem chama _load_native e não cria fábrica nativa.
factory_started não comprova retorno, ausência de efeitos ou limpeza.
Uma fábrica interrompida pode deixar efeitos próprios que este wrapper
não conhece; não se declara que referências do registro retenham todos
os objetos locais de um callback arbitrário. O futuro chamador deve
estacionar diante de estado não comprovado, sem repetir ou forçar cleanup.

## Sequência e revisão

1. CLI98605 terminou0, plano só leitura. O plano usava memória para parte
   das fontes e dizia incorretamente que a sonda de identidade nunca fora
   feita. O registro consumido de02/11 foi relido: rótulo final
   LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED preservado, sem rerun ou promoção.
2. O revisor confirmou com ctypes.from_param que parâmetros gerados por
   duas execuções independentes do backend têm classes diferentes: a
   própria classe foi aceita, a de outra cópia gerou TypeError. Nenhuma
   função nativa, loader ou convenção de chamada foi exercitada. Decisão
   técnica sob delegação: extensão mínima da composição existente.
3. CLI6989 terminou0 e escreveu primeiro testes, desenho e seção10 do
   PROCEDURE. O prompt chamava esse procedimento de novo por engano, mas
   ele já existia: Claude2 releu e apenas acrescentou a seção10. Root
   preservou o original18054bytes e comprovou prefixo exato das seções1–9.
4. Antes de alterar a fonte109: **29 coletados,29 falhas,0erros**, todas
   TypeError da palavra-chave ainda inexistente;2,487s/saída1. É baseline
   de recurso ausente, não regressão de produto. Ruff/format/mypy do novo
   teste aprovados. Testes d6b15ac1 congelados desde essa medição; os63
   casos antigos a3ebf78b também ficaram byte a byte intactos.
5. Zero escritor antes da CLI52999; ela terminou0, alterando só a
   composição, desenho e seção10. O revisor leu a fonte/diff antes de
   executar os gates. AST confirmou mudanças funcionais apenas em
   _Attempt e _collect_pinned; helpers de pins/retorno/provedor intactos.
   Sem finding bloqueante de código nessa revisão privada.

Cada terminal foi recuperado antes da chamada seguinte, mesma sessão,
modelo e esforço. Sem segundo escritor. Root escreveu registros, arquivos
de evidência como dados e QA independente; não implementou o PoC/testes.

## Gates finais

Runtime somente Windows CPython3.11.3. As metas3.11/3.14 do mypy são
análise estática, não runtime3.14. PoC fora do mypy.

| Gate | Resultado |
|---|---|
| Próprios da fábrica | **29 passed**,2,802s/saída0 |
| Relacionados, seis arquivos | **748 passed**,38,185s/saída0 |
| Sonda de identidade de tipos ctypes | mesma cópia aceita/outra recusada |
| Ponte _NativeApi com delegado Python | parâmetros da cópia aceitos, recusa fechada |
| Contrato keyword-only independente | argumento posicional extra recusado antes de efeitos |
| Ruff src/tests | aprovado |
| Lint PoC E9/F63/F7/F82 | aprovado |
| Format src/tests + composição | **351 arquivos conformes** |
| mypy strict src/tests, alvo3.11 | **350 arquivos sem erros** |
| mypy strict src/tests, alvo3.14 | **350 arquivos sem erros** |

Zero falhas, erros ou skips nas suítes verdes. Relacionados: testes de
fábrica, composição pinada, backend de coleta Win32, coletor, verificador e
entrada privada; inclui os63 casos anteriores sem modificação.

A sonda independente da ponte cria _NativeApi da mesma cópia sobre funções
Python. Um NtCreateFile simulado confere os byref com from_param e retorna
acesso negado sem fornecer handle: resultado INVALID/COLLECT_OPEN, ledgers
vazios. Não testa a chamada real via ctypes, ABI do SO ou suporte de API.
A sonda posicional confere TypeError antes de exec/fábrica/chamada fake.

Não se repetiram nem se declaram aprovados a suíte integral de produto,
PostgreSQL, Docker, frontend, pacotes ou controles nativos. Nenhum src, UI
ou dependência mudou. Depois dos gates só documentos e evidência como
dados foram fechados; código e testes mantiveram os hashes medidos.

## Evidência e procedimento

Pasta docs/poc/evidence/native-collect-factory-review-20261103: fonte109
aceita, procedimento anterior, RED congelado, relatórios e sondas py.txt.
Não são chamadores operacionais.

- Sonda de tipos:617bytes,
  30db87e9689703a937ddc428293958833144789acdb5db1ae04270aac4991400.
- Sondas finais:1966bytes,
  cea2d3cd7ad96fdd4ab901e3c9d4edc392dfc2eb93f16980ff17470062617dc3.
- Procedimento anterior preservado:18054bytes,
  54c0e2c37dcbb0e4195a16f50158c76601879ec13bd8ef7c0052b2314efe39d7.

PROCEDURE seção10 é prospectiva: captura única de bytes por pin,
pré-checagens, controle/coleção e confronto de artefatos; saída somente com
quiescência dos containers originais por identidade, nunca vazios
substituídos ou igualdade hostil. _LIVE do runner não representa os handles
da coleta. O chamador de coleta com retenção pegajosa em primeiro plano
ainda não existe e não foi substituído por uma promessa documental.

## Estado e limites

Zero Claude2 ativo após terminal52999, reconferido durante a revisão. Sem
nova cota/reset/job ou outro escritor/conta/modelo; a tarefa histórica não
recebeu novo disparo. Arquivos pessoais não rastreados preservados.

Sem leitura explícita de runtime/config/binário, DLL/API/job/process/control
real, Docker/PG/SQL, root/nonce/comando operacional ou deploy novo. Importar
bibliotecas Python nos testes não atesta ausência de DLLs implícitas do
runtime. Captura externa, fábrica nativa, suporte de classes/âncora/fechamento
e procedimento exato continuam pendentes de revisão própria antes de efeitos.

Native3s NOT_MEASURED; entry_gate NOT_EVALUATED; identidade
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED. Gateway/B1/B2/D090gate2/C1/SQL/
produção abertos. Destino final Docker Oracle Linux9.8 nesta máquina,
sem nova instância pronta para testar neste lote.
