# W1 Oracle: revisão dos primeiros testes do host

2026-11-10. Root revisor, sob delegação; não é aprovação individual inventada.
Lidos os 1721 linhas de teste V1 ae47c084/61435 bytes e o contrato aed85ad4.
CLI77325 terminou0, resultado recuperado, zero escritor confirmado. Módulo ausente.

## Medição V1, preservada

228 coletados: 3 sanidades passaram, 225 falharam por FileNotFoundError,
0 erros/skips; 46,422 s no runner Windows3.11.3, pilha64MiB. Ausência da
fonte não é evidência comportamental. Dados/log/JUnit brutos preservados.
Ruff: 4 diagnósticos (prefix com6 args; teste de mapa com7 args/posicionais;
token literal de carrier). Formato: 7 trechos. Mypy3.11/3.14:1teste limpo.
Não executar nem criar a fonte antes do teste final revisto/RED congelado.

## Precisões para os oráculos, antes da implementação

Estas decisões fecham ambiguidades do desenho sob a delegação vigente;
não alteram pins, produto, SDK, estado16 ou autoridade nativa.

1. Precedência: INPUT e TIME primeiro; depois, com contador56, qualquer Line
   dá LINE antes de ORDER/parse. Essa exceção global do teto é explícita.
   Sem teto atingido, Line mal enquadrada/não parseável durante pendência dá
   ORDER; apenas eventos ABORT/TERMINAL reconhecíveis seguem sua validação
   própria. READY com case int exato1..25 fora da ordem dá SEQUENCE, não
   EVENT; tipo/domínio fora desse intervalo dá EVENT.
2. Prazo STOP/NOSTOP: mesmo prazo original da observação, ARMED23.at+
   t4_window_s; não criar nova janela após ActDone. ZERO_BACKENDS25 vence
   em Exited.at+act_s. Política exige act_s < min(go_s, ack_s, fatal_ack_s),
   coerente com a restrição textual §4.5; testar ACK/fatalACK <= act_s.
3. Kill FAILED/UNKNOWN/tardio devolve Wait e conserva falhaT6; espera Exited,
   sem novos efeitos. Exited após killOK com eof/reaped falso dá exatamente
   ENDED_UNKNOWN, retidoTrue e T6FAIL; jamais ZERO/CANDIDATE.
4. OOM/kill não confirmado declarado como OK é RECEIPT conforme a tabela de
   facts, não FAIL legítimo. FactsNone com FAILED/UNKNOWN é efeito legítimo.
5. Política é carrier validada pelo HostReactor; inputDTOs/facts carriers
   também são frozen/slots sem recusa no construtor. Status.orphan conserva
   o objeto original depois de Done e recusa; a imutabilidade não o libera.
6. Qualquer linha após ARMED25 invalida T6. Não usar só code69 como evidência
   disso: testar veredictoFAIL imediatamente após terminal válido, e caminho
   ABORT/TERMINAL ABORTED/EXIT68 que jamais vira CANDIDATE. Parse/protocolo
   inválido ainda recusa, nunca aprova.

## Lacunas a fechar no MESMO arquivo de testes

- H7: observar as chamadas reais do ControlMachine delegado por um core clone
  local confiável; entrega NOT_SENT/UNKNOWN/tardia não pode accept/join nem
  avançar accepted, inclusive ACK e STOP. Não basta proibir uma linha posterior
  enquanto DRAINING. Não alterar globals SDK/stdlib.
- H13/H15: fechar frozen/slots e campos públicos dos DTOs de entrada, facts,
  saídas, HostStatus/HostPolicy, assim como enums do contrato. Não exigir nomes
  de atributos privados. Observar tokens exatos contíguos para TODOS Send/Act
  no caminho completo, não só os dois primeiros sends.
- Tipos/domínios: tempos inválidos de Delivered.pre/post, ActDone.at, Exited.at;
  Delivery/ActStatus/ExitStatus estrangeiros, Exited.code bool/float/fora0..255
  e code nãoNone para NO_EXIT/UNKNOWN, eof/reaped não-bool. Carrier deve construir
  e feed recusar, antes de qualquer atualização. TIME precede RECEIPT/EXIT;
  tokens/status/facts inválidos são RECEIPT, shape/campos do Exited são EXIT.
- Exatidão: pack_control recusa subclasses int; core constantes não aceitam
  bool/float iguais; RESULT rows/bytes como float (igual numericamente) recusam
  EVENT. Acrescentar Infinity/-Infinity em parser canônico. Nenhuma coerção.
- Cobrir todos phase/reason válidos de ABORT sem cross-product inútil;
  manter domínio exato e coerência retained/terminal. SUMMARY fora de fase
  ORDER; todas as asserções existentes não ambíguas ficam preservadas.

V1 é dado, ainda NÃO congelada para fonte. Pequenos ajustes/refactors de harness
para Ruff são permitidos, mantendo valores/asserções: agrupar overrides em vez
6args, cenário tuple em vez7args, carrier str em variável neutra. Corrigir só os
7 trechos de formato indicados, sem executar formatter ou outro comando.

Próximo C2 mesma sessão/modelo/medium só edita tests/test_oracle9_w1_host_reactor.py
com Read/Edit/Write. Root relê todo delta, mede estáticos/RED e congela antes da
fonte. Sem módulo, SDK, Docker/PG/SQL/OS/nativo/runtime/config/privado/root/nonce/
command/deploy. Todos gates nativos/produto permanecem abertos.

## V2 relida e RED335 congelado

CLI56251 terminou0, recuperada antes de gates; zero escritor confirmado. Root
leu todo delta V2 sobre as1721linhas V1: teste c595c426/73515bytes/2031linhas.
Todos335 coletados:3sanidades PASS e332falhas FileNotFoundError,0erros/skips,
64,156s. Ruff/format e mypy1teste3.11/3.14 limpos. RuntimeWindows3.11.3,
não prova3.14/Linux. Não houve mock do reator nem ajuste de SDK.

Teste congelado como oráculo antes da fonte. V1/RED228 e falhas de estilo
preservadas, não apagadas nem rebatizadas como sucesso. Valores/asserções
antigos foram preservados salvo os oráculos ambíguos explicitamente fechados.
Oito upstream eapp124 conferidos intactos; estado16/attempt não tocados.

Sob delegação, próximo incremento é somente implementação privada em
docs/poc/oracle9_w1_host_reactor.py pelo mesmo Claude2/modelo/medium, após
guarda0. Teste/SDK/app imutáveis. Root lerá toda fonte e medirá335+relacionados,
com regressões RED adicionais antes de corrigir findings comportamentais.
Não publicar código não verificado. Nenhum efeito nativo/Docker/PG/SQL/
privado/runtime/config/binary/operationalroot/nonce/comando/deploy. Modelo
puro não fecha B1/B2/D090/C1/T5 físico/ingressos/produção. Gateway indisponível.
