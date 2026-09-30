# PoC comparativa de SCRAM-SHA-256 servidor (Fase 9, Etapa 7)

**Status:** PoC, não produto. Nenhuma dependência foi adicionada ao produto;
nenhuma autenticação de produção foi incorporada. Este documento e os arquivos
em `docs/poc/` embasam a recomendação para aval; a decisão final é do usuário.
Os arquivos não entram no wheel/sdist e não são importados por `maskgw`.

## Correção de um defeito encontrado na revisão

A versão anterior da PoC calculava o `AuthMessage` com um `c=biws` **assumido**,
em vez do campo `c` realmente enviado pelo cliente, e não validava esse campo.
Resultado: um `c=AAAA` com a mesma prova era aceito. Corrigido: o servidor agora
(1) valida que o `c` do gs2 header `n,,` é `biws` e (2) calcula a assinatura
sobre o `c` enviado. Há regressão para o `c` adulterado.

## O que foi medido (não assumido)

| prova | como | resultado |
|---|---|---|
| handshake correto aceito; senha errada recusada | `scram_poc.py` | **PASS** |
| `c=` adulterado recusado | `scram_poc.py` (`run_with_tampered_channel_binding`) | **PASS** |
| `ClientProof`/`ServerSignature` == vetor RFC 7677 §3 | `scram_vector_check.py` | **PASS** |
| **PoC server × cliente `scramp` real** | `scram_interop.py`, venv temporário | **PASS** |
| **servidor `scramp` real × cliente da PoC** | `scram_interop.py` | **PASS** |
| PoC server recusa **prova adulterada** de um cliente `scramp` | `scram_interop.py` | **PASS** |
| PoC server recusa **channel binding adulterado** | `scram_interop.py` | **PASS** |

A biblioteca comparada é **`scramp==1.4.5`**, instalada num venv temporário
(`$TEMP/scram-poc-venv`), sem tocar as dependências do produto. A interop acima é
**medida** com essa versão identificada.

### O que NÃO foi medido (sem overclaim)

- **Não** há prova de conformidade integral do protocolo: o vetor RFC 7677 cobre
  as primitivas e um handshake; a máquina de estados SASL completa do protocolo
  3.0 (erros uniformes sem oráculo, timing, mensagens fora de ordem) não foi
  implementada nem medida.
- **Não** foi testada interop contra psql/JDBC/DBeaver/DataGrip/pgAdmin — só
  contra `scramp`. A matriz de clientes certificados (§14.1) é trabalho da Etapa 7
  propriamente dita.
- **SASLprep (RFC 4013)** não é aplicado; **channel binding `-PLUS`** não é
  implementado. Ver limitações.

## Comparação: stdlib próprio × `scramp==1.4.5`

| critério | stdlib próprio | `scramp==1.4.5` |
|---|---|---|
| primitivas/handshake | conferidos contra o vetor RFC 7677 e interop com `scramp` (medido) | cobertos pela lib e por seus testes; interop medida aqui |
| superfície adversarial | controle total do parse (nonce, iteração, `c`, tamanho); código de segurança novo a manter | parsing de terceiros; menos controle, superfície externa |
| channel binding `-PLUS` | não implementado | a verificar na lib |
| SASLprep | não implementado | a verificar na lib |
| máquina SASL do protocolo 3.0 | a implementar na Etapa 7 (igual para os dois) | idem |
| manutenção | sem dependência nova | dependência a fixar e acompanhar (CVE) |

## Limitações da PoC (a fechar antes de produção, com aval)

1. **SASLprep (RFC 4013)** não aplicado à senha; o PostgreSQL usa SASLprep.
2. **Channel binding `-PLUS`** não implementado.
3. Só o lado servidor e clientes de teste/`scramp`; a máquina SASL real do
   listener (erros uniformes sem oráculo, timing) é da Etapa 7.
4. A `StoredCredential` deriva da senha em memória; a origem real
   (catálogo/segredo, principal único do Gateway) é da Etapa 7.

## Recomendação (sem escolher mecanismo nem dependência)

A implementação própria em stdlib é pequena, auditável, **conforme ao vetor
normativo** e **interopera com `scramp`** no subconjunto medido; evita dependência.
A biblioteca mantida reduz risco onde a PoC ainda não cobre — **SASLprep** e
**channel binding `-PLUS`**.

As decisões abaixo são **do usuário** e não foram tomadas aqui:

1. **Política de mecanismos** — oferecer só `SCRAM-SHA-256`, ou também `-PLUS`.
2. **SASLprep** — exigir ou não normalização Unicode da senha. (Não foi imposta
   nenhuma restrição de senha a ASCII nesta rodada.)
3. **stdlib vs dependência** — manter stdlib ou adotar `scramp` fixado como
   exceção aprovada à regra "sem dependência nova".

Cada uma depende das outras (p. ex. `-PLUS` e SASLprep pesam a favor da lib).
Nenhuma foi incorporada. Aguardo seu aval antes de escrever a autenticação SCRAM
de produção do listener.

## Como reproduzir a interop

```
python -m venv "$TEMP/scram-poc-venv"
"$TEMP/scram-poc-venv/Scripts/python.exe" -m pip install scramp==1.4.5
"$TEMP/scram-poc-venv/Scripts/python.exe" docs/poc/scram_interop.py
```
