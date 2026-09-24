"""Admin API v2 de datasources (Fase 9, Etapa 4, spec §8; D-092 a D-096).

Subpacote importado SOMENTE pelo composition root quando ha catalogo de
datasources e fronteira HTTP: sem eles, nenhum modulo daqui — nem de
`maskgw.datasource` — e carregado, e o app administrativo e a v1 byte a byte.

Vocabulario de erro, schemas e auditoria sao proprios e separados da v1
(D-095): a v1 e o seu gerador de UI nao mudam.
"""
