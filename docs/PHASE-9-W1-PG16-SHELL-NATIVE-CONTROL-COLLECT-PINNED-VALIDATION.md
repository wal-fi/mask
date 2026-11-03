# Composição pinada de coleta — validação com fakes

Data: 2026-11-03, America/Sao_Paulo. Incremento privado sob delegação,
sem aprovação individual inventada ou ativação nativa. Claude2 foi o único
programador: sessão51ea0d85-05bb-4d24-ba9a-c9627c3f832f,
claude-opus-5-5, esforço medium. O assistente principal revisou código,
testes e desenho, executou os gates e escreveu os registros de revisão.
Base publicada2ef95a2, conferida HEAD/origin e0/0 antes da rodada.

## Escopo e fontes

- Composição: `docs/poc/pg16_shell_native_control_collect_pinned.py`,
  **4291 bytes**, SHA-256
  `109ab960d35be1a2ee93f71eb96baf146cc80a8574e159b6ea89daae75cb76c0`.
- Testes congelados antes do módulo:
  `tests/test_pg16_shell_native_control_collect_pinned.py`,
  **21009 bytes**, SHA-256
  `a3ebf78bb3f9169bc846be54c1a7c1816fd3c5388e63471b6789fe5114fa1c8a`.
- Coletor fixo:20571 bytes,
  `1972ec74d96f93d824dfe18da0e0288a7fc21b7f2997e28d5afe497b782c9f52`.
- Backend fixo:22315 bytes,
  `ccb3f74af75be04bbe685bc195c84d17e0457efe15732ed6cdbe9f9f057c3b3a`.

A função privada recebe os próprios objetos bytes imutáveis. Confere os
dois tamanhos/hashes antes de compilar qualquer fonte. Executa só esses
bytes em dois dicts novos, sem importar checkout mutável ou instalar
módulos globais. Reutiliza as classes DTO, `_ACTIVE` e `_POISON` da cópia
executada. O único provedor instalado fica no seam privado dessa cópia.
As fábricas públicas anteriores continuam devolvendo None.

O registro de tentativa referencia namespaces e API antes do primeiro
exec; a instância do backend é guardada antes de chamar a política. O
registro é retido mesmo em retorno limpo, erro ou controle; não se limpa o
ledger nem se repete fechamento. Uma tentativa serial por namespace,
sem promessa de concorrência. Retenção não é limpeza nem garantia contra
término do processo. Os pins conferem conteúdo, sem autenticar origem da
captura, stdlib, API injetada ou chamador privado.

O retorno tem forma fechada: tupla exata de quatro itens, strings exatas,
pares label/motivo válidos, dois hashes minúsculos de64 caracteres somente
para VERIFIED_APPROVED/VERIFIED_REJECTED com OK; INVALID com motivo
permitido não OK e hashes None. O bloco protegido sanitiza exceções
ordinárias de compilação/execução/construtor/política e controles propagam
com identidade. Não se afirma operação sob exaustão de memória nem que as
reservas anteriores à publicação do registro sejam infalíveis.

## Histórico medido e correções antes da implementação

1. CLI92065 terminou0: plano só leitura. Detectou a necessidade de usar
   explicitamente o seam de teste numa cópia; aceito sob delegação apenas
   para este laboratório simulado, sem ativação nativa.
2. CLI29253 terminou0: escreveu só desenho e testes515b7243/18629bytes.
   Root mediu52 coletados,51erros+1falha, todosFileNotFoundError,0,926s,
   saída1: módulo ausente, não regressão de produto. A contagem preliminar
   de41 do programador estava errada. Ruff3erros, format1fora do padrão,
   mypy do teste limpo. A revisão ainda encontrou uma contradição: ban AST
   de atributo/string backend apesar de o contrato exigir record.backend.
3. CLI49898 terminou0: corrigiu esse ban específico mantendo proibição de
   funções/classes backend, código público, loaders e efeitos. Corrigiu
   estilo sem suppressions, manteve comportamentos anteriores e acrescentou
   dez tipos/formatos de saída e uma interrupção antes do primeiro exec.
   Root mediu63 coletados,62erros+1falha, todosFileNotFoundError,0,907s,
   saída1. Ruff/format/mypy do teste aprovados. Testes congelados a partir
   dessa medição, antes de criar o módulo.
4. A auditoria AST do root esperava duas funções alteradas, mas eram três.
   A terceira só extraía tuplas de pins para variáveis temporárias; a
   equivalência das asserções foi conferida por substituição AST. O prompt
   da implementação havia descrito duas prematuramente. Falha dessa
   verificação de revisão e correção registradas, sem ocultar ou tratar
   como resultado de teste do produto.
5. CLI49063 terminou0: escreveu só módulo e desenho. Testesa3ebf78b e
   fontes anteriores intactos. O revisor leu o módulo inteiro antes de
   importá-lo/executar os gates. Nenhum novo finding bloqueante de código.

Cada chamada foi na mesma sessão/modelo/esforço; o terminal anterior foi
recuperado antes da seguinte, e não houve escritor duplicado. O revisor
escreveu somente registros/evidência e sondas independentes de QA, não a
implementação ou os testes de produto/PoC.

## Gates finais

Ambiente de runtime somente Windows CPython3.11.3. Alvos mypy3.11/3.14 são
checagens estáticas, não execução3.14. Nenhum efeito de API nativa foi
exercitado; os helpers escrevem apenas bytes sintéticos em objetos ctypes.

| Gate | Resultado |
|---|---|
| Próprios | **63 passed**,6,175s/saída0 |
| Relacionados | **719 passed**,27,137s/saída0 |
| Sondas independentes | 2 conferidas, reentrância e controle tardio |
| Ruff src/tests | aprovado |
| Lint PoC novo, E9/F63/F7/F82 | aprovado |
| Format src/tests + PoC novo | **350 arquivos conformes** |
| mypy strict src/tests, alvo3.11 | **349 arquivos sem erros** |
| mypy strict src/tests, alvo3.14 | **349 arquivos sem erros** |

Zero falhas, erros ou skips nas suítes verdes. Relacionados: os cinco
arquivos de testes de composição pinada, backend Win32, coletor, verificador
e entrada. PoC fora do mypy. Confirmados15 pins anteriores, incluindo
coletor/backend e testes, core/testes, entrada/runner/adapter, admission
backend/host, prepare/probe/run/export. Uma primeira consulta usou nome
inexistente para adapter; o inventário confirmou native_control_win32.py e
seu hash foi conferido na lista final. Estado16 não alterado.

Sonda independente1: um fake reentra durante a abertura da âncora. A chamada
interna recebe COLLECT_POISONED, a externa termina VERIFIED_APPROVED,
permanece só uma tentativa e todos os handles fake fecham uma vez. Isso
não é prova de segurança de threads ou API privada hostil.

Sonda independente2: controle injetado depois da política e antes da
revalidação do retorno propaga com a mesma identidade. O registro/backend
continuam retidos, os handles fake já fechados não são fechados novamente
e outra chamada é recusada. Nenhum controle real do SO foi enviado.

Suíte integral de produto/PG, frontend, pacotes, Docker e nativo não foram
reexecutados nem declarados aprovados neste incremento. Não houve mudança
de src, UI ou dependências. Depois dos gates só houve fechamento documental
e arquivamento dos resultados como dados.

## Arquivo e coordenação

`docs/poc/evidence/native-collect-pinned-review-20261103` guarda a primeira
versão dos testes, os testes congelados e os dois relatórios de ausência,
os erros históricos, a correção AST do revisor, a sonda independente como
py.txt e o relatório final. Não é novo chamador operacional. Sonda1728bytes:
`f507bf17c7d59a86390234e752f5f15b5e33021d4c89809a6a1393203e7052c3`.

Zero Claude2 ativo após terminal49063, reconferido antes do fechamento.
Tarefa histórica Maskgw-Claude2-Resume-01a05804 relida Disabled, sem próximo
disparo, último03/11 às16h35Z/result0. Não houve nova cota/reset/job nem
outro escritor/conta/modelo. Arquivos pessoais não rastreados preservados.

## Pendências e fronteiras

Nenhuma ligação real ou loader foi ativado/invocado. Captura externa dos
bytes, conversão ctypes de chamadas nativas, suporte/semântica das APIs,
âncora/perfil/identidade Windows e procedimento concreto ainda exigem
desenho e revisão próprios antes de efeitos. Sem leitura explícita de
runtime/config/binário, DLL/job/process/control real, Docker/PG/SQL,
root/nonce/comando operacional ou deploy novo. Importar bibliotecas Python
no processo de testes não prova nem promete ausência de DLLs do runtime.

Native3s NOT_MEASURED; entry_gate NOT_EVALUATED; identidade
LIVENESS_SAMPLED_TRANSPORT_UNVERIFIED; Gateway/B1/B2/D090gate2/C1/SQL/
produção abertos. Destino final Docker Oracle Linux9.8 nesta máquina,
sem nova instância pronta para o usuário neste lote.
