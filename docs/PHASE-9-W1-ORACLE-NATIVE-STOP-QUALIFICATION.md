# W1 Oracle: qualificação da primitiva pública de parada do host — validação

2026-11-14. Registro documental. Quem executou e mediu foi o root. Claude2 (sessão 51ea0d85, claude-opus-5-5/medium) escreveu o script e este documento, sem executar nada.

## 1. Autoridade

- **Concedido pelo usuário em 2026-11-14:** implementação local do W1 e testes nativos isolados no Windows, DEPOIS de revisão de contrato e contenção.
- A restrição anterior, só documental e de observação, fica histórica para o W1. Não é mais um bloqueio de autoridade.
- **Continuam excluídos:** Docker, PG/SQL, credenciais, rede externa, tentativa consumida, estado16 e deploy.
- **O que este lote qualificou:** uma primitiva pública do SDK, com um único filho benigno. NÃO executou S nem P, nem o backend nativo do projeto, o pump ou o domínio W1.

## 2. Fontes e oráculos

- **Oráculos de medição prospectivos**, congelados antes do script: `docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112/native-stop-qualification-oracles-20261114.json` (q0–q6).
  - Medem primitivas existentes do SDK. Não são RED de código de produto ausente; não há alegação de RED falso.
- **Script:** `native-stop-qualification-20261114.ps1`, no mesmo diretório. Root conferiu: SHA becc52828b56dffe644e57371759c5943511a96c493a9864643f40ce765d0e9e, 163 linhas, AST com 0 erros, todas as linhas lidas.
- **Superfície usada:** só a API pública `System.Diagnostics.Process`/`ProcessStartInfo`.
  - O `Process` é alocado na custódia do chamador ANTES do `Start`.
  - Executável base direto, sem shell, `CreateNoWindow`, ambiente vazio.
  - Sem redirecionamento, leitores ou threads; sem Add-Type, PInvoke ou criação de job EXPLÍCITOS; sem carregar binding nativo do projeto nem importar o projeto. O SDK público e o filho usam necessariamente componentes internos do SO; não se afirma ausência de toda DLL.
- **Filho fixo:** `-I -B -S`, só `time.sleep` finito, sem saída nem descendentes.
- **Referências públicas do SDK** (contrato candidato, não admissão):
  - CPython v3.11.3 `PC/launcher.c` (VENV_REDIRECT/run_child/CreateProcess): https://github.com/python/cpython/blob/v3.11.3/PC/launcher.c
  - Documentação do `venv` no Python 3.11: https://docs.python.org/3.11/library/venv.html
  - `Process.Kill` (assíncrono): https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.kill?view=netframework-4.8.1
  - `Process.WaitForExit`, mesma versão. Pelo contrato, `WaitForExit`/`HasExited` não provam saída de descendentes.

## 3. Achados no script corrigidos ANTES da execução nativa

São achados de revisão estática, não exploits medidos.

- **Desenho anterior rejeitado:** o guardião proposto sobre `Popen`. A falha no construtor podia perder a custódia, referências locais não definiam retenção, e a thread leitora reabria o ciclo de vida.
- **F1:** um `Start` incerto e NÃO associado era descartado no fim do script.
  - Correção: `StartAttempted` é marcado ANTES do `Start`.
  - Depois disso, a mesma instância fica retida, reconferindo associação e saída em fatias finitas, até haver saída positiva.
  - Sem retry, sem filho novo e sem reabertura por PID.
- **F2:** saída natural antecipada e saída natural de reserva registravam fatos de saída de forma incoerente.
  - Agora registram `exit_observed`/`has_exited`/`exit_code` de forma consistente.
  - Nenhum desses caminhos produz `OBSERVED`.
- **F3:** uma exceção do `Dispose` podia escapar e pular o JSON fechado.
  - Agora vira a categoria fechada `DISPOSE_RAISED`/`UNKNOWN`.
  - `disposed=true` só aparece depois de um `Dispose` bem-sucedido.
- **F4:** o limite do preflight caiu de 256 MiB para 16 MiB.

## 4. Fatos medidos pelo root

**Host:** PowerShell 5.1.26100.9818, CLR 4.0.30319.42000, processo de 64 bits.

**Q0 (preflight):**
- Um hash errado deu `REFUSED`/`PREFLIGHT_DIGEST`.
- Isso aconteceu antes da alocação do `Process` e antes do `Start`.

**Q1 (um filho benigno, interpretador base direto):**

| Fato | Valor observado |
|---|---|
| `WaitForExit(500)` inicial | false |
| Pedidos de `Kill` | exatamente 1 |
| Retorno do `Kill` | true |
| `WaitForExit(5000)` / `HasExited` | true / true |
| `ExitCode` | -1 |
| Do kill até a saída | 6 ms |
| `Dispose` | depois da saída observada |
| Fatias de espera natural de reserva | 0 |
| stderr | 0 bytes |
| Duração total do wrapper | 1254,247 ms |

- Recibo compacto revisado (UTF-8, sem caminho local nem argv, com os fatos de Q0/Q1): `docs/poc/evidence/oracle9-w1-proactor-tests-review-20261112/native-stop-qualification-validation-20261114.json`.
- **Artefato base:** 103192 bytes, SHA ff9b669828a66882f3d43ed2f9192ea9d8a08f80b8ffbc2186ee946823394418.
  - É diferente do lançador do venv.
  - O caminho local do base é privado e não versionado, e não é publicado aqui.
- **Consulta de runtime feita à parte pelo root, sob autoridade explícita do usuário** (`-I -B -S`): observou Python 3.11.3, win32, ponteiro de 8 bytes, `isolated=1`, `dont_write_bytecode=1`, `optimize=0`, saída 0. É um fato limitado e separado. NÃO admite ABI, hooks nem S.

## 5. Limites

- **Alcance:** a qualificação vale só para ESTE filho, neste host e nesta execução.
- **Kill não é limpeza:**
  - O retorno do `Kill` nunca equivale à saída do processo nem à limpeza de descendentes.
  - A saída de S não prova a saída de descendentes.
  - A contagem real de descendentes NÃO foi medida.
- **Lançador do venv:** o `launcher.c` (VENV_REDIRECT) sustenta o risco de o lançador gerar um filho. Por isso, P precisa ser o interpretador base direto, fornecido e pinado pelo chamador.
- **Preflight:**
  - existe uma janela entre conferir o arquivo e usá-lo (TOCTOU);
  - a checagem de reparse point cobre só o arquivo; os diretórios acima dele ficam por conta do chamador, assim como a admissão do caminho.
- **Start incerto:** é retido só enquanto o processo PowerShell host vive. Se o host morrer, não há garantia.
- **Tempo:** não há teto absoluto de parede. Em UNKNOWN, o chamador pode precisar monitorar a sonda.
- **Sem prova de domínio:**
  - nenhuma prova do projeto, do backend 10c9058f, do adaptador eaebedd6, do pump, de S ou de P;
  - nenhum dos N1–N16 foi exercitado.
- **Suítes de produto não foram repetidas,** porque só mudaram documentos e esta sonda. As medições históricas (1.844 relacionados, 60 próprios, 373 estáticos) continuam sendo do código 793473a.

## 6. Estado dos gates

- A qualificação da primitiva NÃO admite G ou S completos, nem limpeza de descendentes.
- Continuam abertos: N1–N16, T5, B1, B2, D-090, C1, D119, TLS, ingressos e produto.
- O objetivo completo de produção continua aberto, e o Gateway segue indisponível.
- **Próximo lote:** mesmo Claude2, somente leitura. Contrato concreto do chamador de prova S/P, ligado à primitiva de parada medida:
  - limites de IO e custódia;
  - perfis e alocação fixos;
  - runtime, ABI e hooks;
  - cobertura de todos os N obrigatórios.

  Tudo isso vem antes de oráculos, código ou execução nativa de S/P. Sem guardião genérico, sem módulo de framing puro e sem repetir testes já concluídos.

Política Senff: código e documentos derivados de IA exigem revisão humana e de segurança antes do merge.
