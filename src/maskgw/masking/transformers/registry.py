"""Registry extensivel de transformers.

Adicionar um transformer nao exige alteracao no nucleo do Masking Engine:
basta registrar um builder aqui.

O registry e consultado no boot. Referencia a um transformer inexistente e
`ConfigError` — impede a inicializacao.

Cada registro declara tambem os NOMES dos parametros que o builder aceita. Isso
existe porque `GET /admin/v1/transformers` (secao 1.1 da Fase 7) precisa
publicar "nome e parametros aceitos", e a unica fonte disso eram as chamadas a
`require_params` dentro de cada builder — informacao real, mas nao alcancavel
de fora. Declarar aqui mantem UMA fonte: o catalogo administrativo le esta
declaracao, e um teste a confronta com o comportamento efetivo dos builders,
de modo que uma divergencia quebra a suite em vez de virar documentacao falsa.

Nomes, e nada alem de nomes: nenhum default, nenhum exemplo e nenhum valor. Um
default publicado seria conteudo de configuracao atravessando a fronteira sem
necessidade.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from maskgw.errors import ConfigError
from maskgw.masking.transformers.base import Transformer
from maskgw.masking.transformers.hashes import build_hash, build_hmac_sha256
from maskgw.masking.transformers.randomize import build_random
from maskgw.masking.transformers.regex_transformer import build_regex
from maskgw.masking.transformers.simple import build_fixed, build_truncate
from maskgw.secretsource import SecretProvider

TransformerBuilder = Callable[[Mapping[str, Any], SecretProvider], Transformer]


@dataclass(frozen=True, slots=True)
class TransformerSpec:
    """Nome do transformer e os parametros que o builder aceita.

    Imutavel e composta so de strings: atravessa a fronteira administrativa
    como valor, nunca como objeto ou callable.
    """

    name: str
    required_parameters: tuple[str, ...] = ()
    optional_parameters: tuple[str, ...] = ()


class TransformerRegistry:
    """Mapa nome -> builder, com a declaracao de parametros ao lado."""

    def __init__(self) -> None:
        self._builders: dict[str, TransformerBuilder] = {}
        self._specs: dict[str, TransformerSpec] = {}

    def register(
        self,
        name: str,
        builder: TransformerBuilder,
        *,
        required_parameters: tuple[str, ...] = (),
        optional_parameters: tuple[str, ...] = (),
        replace: bool = False,
    ) -> None:
        if not name:
            msg = "nome de transformer vazio"
            raise ConfigError(msg)
        if name in self._builders and not replace:
            msg = f"transformer {name!r} ja registrado"
            raise ConfigError(msg)
        self._builders[name] = builder
        self._specs[name] = TransformerSpec(
            name=name,
            required_parameters=required_parameters,
            optional_parameters=optional_parameters,
        )

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def specs(self) -> tuple[TransformerSpec, ...]:
        """Catalogo fechado, em ordem estavel. Sem builder e sem instancia."""
        return tuple(self._specs[name] for name in self.available())

    def __contains__(self, name: object) -> bool:
        return name in self._builders

    def build(
        self,
        name: str,
        config: Mapping[str, Any] | None,
        secrets: SecretProvider,
    ) -> Transformer:
        """Constroi um transformer. Erros aqui sao fatais no boot."""
        builder = self._builders.get(name)
        if builder is None:
            msg = f"transformer desconhecido: {name!r}; disponiveis: {list(self.available())}"
            raise ConfigError(msg)
        return builder(config or {}, secrets)


def build_default_registry() -> TransformerRegistry:
    """Registry com os transformers do MVP.

    Os parametros declarados aqui espelham exatamente o que cada builder aceita
    em `require_params`. `hmac_sha256` nao tem parametro algum de proposito: a
    chave vem do ambiente e declarar `key` aqui a tornaria um campo do arquivo
    (`FORBIDDEN_PARAMS`, D-006).
    """
    registry = TransformerRegistry()
    registry.register("md5", build_hash("md5"))
    registry.register("sha256", build_hash("sha256"))
    registry.register("sha512", build_hash("sha512"))
    registry.register("hmac_sha256", build_hmac_sha256)
    registry.register(
        "regex",
        build_regex,
        required_parameters=("pattern", "replacement"),
    )
    registry.register(
        "random",
        build_random,
        required_parameters=("strategy",),
        optional_parameters=("preserve_length", "length"),
    )
    registry.register("fixed", build_fixed, required_parameters=("value",))
    registry.register("truncate", build_truncate, required_parameters=("length",))
    return registry
