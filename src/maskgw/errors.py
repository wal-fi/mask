"""Erros do Gateway.

Nenhuma mensagem de erro deste modulo pode conter valores de dados, chaves ou
segredos. Apenas metadata: nomes de regra, nomes de transformer, nomes de
parametro.
"""

from __future__ import annotations


class MaskGatewayError(Exception):
    """Erro base do Gateway."""


class ConfigError(MaskGatewayError):
    """Configuracao invalida.

    Sempre fatal: impede a inicializacao do processo (fail-closed).
    """


class TransformerError(MaskGatewayError):
    """Falha na construcao ou execucao de um transformer."""
