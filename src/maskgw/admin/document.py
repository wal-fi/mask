"""Serializacao do documento administrativo persistido.

A fonte administrativa e o modelo validado do arquivo, nunca os objetos
runtime compilados (D-047). Este modulo faz a unica conversao que a Etapa 6
precisa: `MaskingFileConfig` -> bytes YAML, e a volta.

Duas consequencias declaradas, ambas ja aceitas na especificacao:

- **comentarios se perdem.** Uma volta por Pydantic e PyYAML destroi os
  comentarios do arquivo. A adocao da Etapa 9 e quem grava o backup dos bytes
  originais (secao 5.4); aqui nao ha bytes originais a preservar, porque o
  documento ja e um modelo;
- **nao se promete preservacao byte a byte.** Aspas, indentacao e quebras de
  linha podem mudar. O que se garante e o VALOR validado — e e por isso que a
  serializacao e conferida por round-trip antes de qualquer escrita.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from maskgw.config.loader import validate_file_config
from maskgw.config.models import MaskingFileConfig
from maskgw.errors import ConfigError

#: Codificacao unica do arquivo de configuracao, na leitura e na escrita.
ENCODING = "utf-8"


@dataclass(frozen=True, slots=True, repr=False)
class RenderedDocument:
    """Os bytes que serao persistidos E o documento que eles produzem.

    Os dois viajam juntos de proposito. `document` NAO e o modelo que entrou em
    `render_document`: e o resultado de reparsear `data`. Isso torna literal a
    afirmacao de D-055 — o runtime candidato e construido a partir dos bytes
    que vao para o disco — em vez de apenas equivalente a ela.

    O efeito colateral util e o isolamento: um documento reparseado de YAML nao
    compartilha lista, dicionario nem submodelo com ninguem.
    """

    data: bytes
    document: MaskingFileConfig

    def __repr__(self) -> str:
        return "RenderedDocument(<redacted>)"


def decode_document(data: bytes) -> str:
    """Bytes exatos -> texto. Nunca propaga o conteudo na mensagem de erro."""
    failed = False
    text = ""
    try:
        text = data.decode(ENCODING)
    except UnicodeDecodeError:
        failed = True
    if failed:
        msg = f"masking.yaml nao esta em {ENCODING}"
        raise ConfigError(msg)
    return text


def render_document(document: MaskingFileConfig) -> RenderedDocument:
    """Serializa o documento validado, confere o round-trip e devolve os dois.

    A conferencia nao e zelo excessivo: os bytes devolvidos aqui sao os mesmos
    que serao escritos no disco E os mesmos a partir dos quais o runtime
    candidato e construido. Se a reserializacao nao voltasse ao mesmo modelo, o
    arquivo persistido descreveria uma configuracao diferente da que foi
    validada, compilada e comprovada conectavel — e o proximo start subiria com
    ela. Falhar aqui, antes de qualquer escrita, e a unica resposta correta.

    O documento devolvido e o REPARSEADO, nunca o de entrada. Sao iguais em
    valor — a igualdade acabou de ser verificada — mas o reparseado nao
    compartilha objeto algum com quem chamou.
    """
    payload: dict[str, Any] = document.model_dump(mode="json", exclude_none=True)

    failed = False
    text = ""
    try:
        text = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    except yaml.YAMLError:
        failed = True
    if failed:
        msg = "configuracao candidata nao e serializavel em YAML"
        raise ConfigError(msg)

    data = text.encode(ENCODING)
    reparsed = parse_document(data)
    if reparsed != document:
        msg = "a serializacao da configuracao candidata nao preservou o documento validado"
        raise ConfigError(msg)
    return RenderedDocument(data=data, document=reparsed)


def parse_document(data: bytes) -> MaskingFileConfig:
    """Bytes exatos -> modelo validado. Nao compila transformer algum."""
    raw: Any = None
    failed = False
    try:
        raw = yaml.safe_load(decode_document(data))
    except yaml.YAMLError:
        # A mensagem do PyYAML cita trechos do arquivo; so o fato sai daqui.
        failed = True
    if failed:
        msg = "masking.yaml malformado"
        raise ConfigError(msg)
    return validate_file_config(raw)
