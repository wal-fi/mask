"""Fronteira PostgreSQL (Fase 9, Etapa 7, D-109): pecas PURAS do startup.

Este pacote NAO abre socket, NAO cria `SSLContext`, NAO le ambiente e NAO e
importado pelo composition root. Nada aqui ativa nada. O que existe e
verificavel isolado, sobre bytes:

- `errors`: categorias fechadas com SQLSTATE e texto fixos;
- `framing`: validacao limitada do pacote inicial e das mensagens SASL;
- `credential`: verifier SCRAM-SHA-256 do principal (SASLprep pela `scramp`)
  e o verifier simulado do usuario desconhecido;
- `scram`: a maquina de estados SCRAM-SHA-256 / -PLUS do lado servidor;
- `channel_binding`: o `tls-server-end-point` a partir do DER do certificado.

Settings, driver sobre socket, listener e ativacao sao pendentes futuros.
"""
