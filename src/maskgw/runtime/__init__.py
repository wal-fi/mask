"""Ciclo de vida dos runtimes do Gateway.

Este pacote fica ABAIXO dos dois planos e nao conhece nenhum deles: o data
plane (`gateway/`) adquire e libera; o admin plane (`admin/`) troca. Por isso
`runtime/` nao importa `gateway/`, `admin/` nem `mcp/` — a dependencia aponta
sempre para ca, nunca daqui para la.

Ver docs/DECISIONS.md (D-054) e a spec da Fase 7, secao 8.
"""

from maskgw.runtime.registry import (
    MAX_RETIRED_RUNTIMES,
    RetiredRuntimeInUseError,
    Runtime,
    RuntimeRegistry,
)

__all__ = [
    "MAX_RETIRED_RUNTIMES",
    "RetiredRuntimeInUseError",
    "Runtime",
    "RuntimeRegistry",
]
