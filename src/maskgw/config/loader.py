"""Config Loader.

Carrega e valida o `masking.yaml`, constroi os transformers e produz uma
`MaskingPolicy` imutavel.

Fail-closed: qualquer problema levanta `ConfigError` e impede a inicializacao.
Sao fatais, entre outros:

- YAML malformado ou que nao seja um mapa
- chave desconhecida em qualquer nivel
- `mode` invalido
- transformer inexistente
- regex invalida (pattern ou replacement)
- parametro obrigatorio de transformer ausente
- regra `hmac_sha256` sem chave disponivel no ambiente
- tentativa de declarar segredo dentro do YAML

Nenhuma mensagem de erro contem valores de dados ou segredos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from maskgw.config.models import MaskingFileConfig, MatchConfig
from maskgw.errors import ConfigError
from maskgw.masking.rules import (
    MaskingException,
    MaskingPolicy,
    MaskingRule,
    MatchSpec,
)
from maskgw.masking.transformers.registry import TransformerRegistry, build_default_registry
from maskgw.secretsource import EnvSecretProvider, SecretProvider


def _spec(item: MatchConfig) -> MatchSpec:
    return MatchSpec(
        pattern=item.match,
        mode=item.mode,
        case_sensitive=item.case_sensitive,
    )


def _format_validation_error(exc: ValidationError) -> str:
    """Resume erros do Pydantic sem ecoar valores de entrada."""
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "<raiz>"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_config(
    raw: object,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> MaskingPolicy:
    """Valida uma estrutura ja desserializada e compila a politica."""
    secrets = secrets if secrets is not None else EnvSecretProvider()
    registry = registry if registry is not None else build_default_registry()

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        msg = f"masking.yaml deve conter um mapa no topo, e nao {type(raw).__name__}"
        raise ConfigError(msg)

    try:
        parsed = MaskingFileConfig.model_validate(raw)
    except ValidationError as exc:
        msg = f"configuracao invalida: {_format_validation_error(exc)}"
        raise ConfigError(msg) from exc

    exceptions = tuple(
        MaskingException(spec=_spec(item), index=index)
        for index, item in enumerate(parsed.exceptions)
    )

    rules: list[MaskingRule] = []
    for index, item in enumerate(parsed.masking):
        try:
            transformer = registry.build(item.transformer, item.config, secrets)
        except ConfigError as exc:
            # Identifica a regra pelo indice e pelo padrao (metadata, nao dado).
            msg = f"regra #{index} (match={item.match!r}): {exc}"
            raise ConfigError(msg) from exc
        rules.append(
            MaskingRule(
                spec=_spec(item),
                transformer=transformer,
                transformer_name=item.transformer,
                index=index,
            )
        )

    return MaskingPolicy(exceptions=exceptions, rules=tuple(rules))


def load_config_text(
    text: str,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> MaskingPolicy:
    """Carrega a politica a partir de texto YAML."""
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # `exc` pode citar trechos do arquivo; o arquivo e de regras, nao de
        # dados, mas ainda assim so o resumo posicional e propagado.
        detail = getattr(exc, "problem", None) or "estrutura invalida"
        mark = getattr(exc, "problem_mark", None)
        where = f" (linha {mark.line + 1}, coluna {mark.column + 1})" if mark else ""
        msg = f"masking.yaml malformado: {detail}{where}"
        raise ConfigError(msg) from exc

    return parse_config(raw, secrets=secrets, registry=registry)


def load_config(
    path: str | Path,
    *,
    secrets: SecretProvider | None = None,
    registry: TransformerRegistry | None = None,
) -> MaskingPolicy:
    """Carrega a politica a partir de um arquivo."""
    config_path = Path(path)
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"nao foi possivel ler a configuracao em {config_path}: {exc.strerror}"
        raise ConfigError(msg) from exc

    return load_config_text(text, secrets=secrets, registry=registry)
