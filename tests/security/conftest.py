"""Ambiente comum da suite adversarial (Fase 6).

Cada teste declara o seu veredito no nome ou no docstring:

- **BLOCKED** — o ataque e recusado antes de tocar o dado
- **MASKED** — o ataque executa, mas o valor sai transformado
- **KNOWN LIMITATION** — o ataque FUNCIONA. O teste fixa o bypass para que ele
  nao passe despercebido e para que uma correcao futura seja notada.

Nenhum bypass conhecido vira `skip`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from maskgw.gateway.factory import build_application
from maskgw.gateway.models import QueryResult
from maskgw.masking.transformers.hashes import HMAC_KEY_ENV
from maskgw.secretsource import MappingSecretProvider
from tests.conftest import TEST_HMAC_KEY

SCHEMA = "maskgw_redteam"
TABLE = f"{SCHEMA}.cliente"
OUTRA = f"{SCHEMA}.outro"

#: Dados ficticios. O CPF e o alvo de todo ataque desta suite.
NOME = "Joao"
CPF = "11122233344"
EMAIL = "joao@example.com"
SENHA = "hunter2-ficticia"

CONFIG = """
masking:
  - match: cpf
    transformer: hmac_sha256
  - match: email
    transformer: regex
    config:
      pattern: "^(.{2}).*(@.*)$"
      replacement: "\\\\1***\\\\2"
  - match: senha
    transformer: fixed
    config:
      value: "[REDACTED]"

exceptions:
  - match: tipo_cpf
    mode: exact

database:
  statement_timeout_ms: 3000
  max_rows: 5
"""

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {TABLE} (
    id integer, nome text, cpf text, email text, tipo_cpf text, senha text
);
CREATE TABLE {OUTRA} (id integer, cpf text, nome text);
CREATE VIEW {SCHEMA}.v1 AS SELECT id, cpf FROM {TABLE};
CREATE VIEW {SCHEMA}.v2 AS SELECT id, cpf AS documento FROM {TABLE};
CREATE VIEW {SCHEMA}.v3 AS SELECT id, substr(cpf, 1, 11) AS documento FROM {TABLE};
CREATE VIEW {SCHEMA}.v4 AS SELECT * FROM {SCHEMA}.v2;
CREATE FUNCTION {SCHEMA}.safe_lookup() RETURNS text LANGUAGE sql STABLE AS
    $$ SELECT cpf FROM {TABLE} LIMIT 1 $$;
CREATE FUNCTION {SCHEMA}.definer_lookup() RETURNS text LANGUAGE plpgsql SECURITY DEFINER AS
    $$ BEGIN RETURN (SELECT cpf FROM {TABLE} LIMIT 1); END $$;
CREATE FUNCTION {SCHEMA}.writer() RETURNS integer LANGUAGE plpgsql AS
    $$ BEGIN INSERT INTO {TABLE} (id) VALUES (99); RETURN 1; END $$;
CREATE FUNCTION {SCHEMA}.dyn(q text) RETURNS text LANGUAGE plpgsql AS
    $$ DECLARE r text; BEGIN EXECUTE q INTO r; RETURN r; END $$;
CREATE FUNCTION {SCHEMA}.boom(v text) RETURNS integer LANGUAGE plpgsql AS
    $$ BEGIN RAISE EXCEPTION 'valor recebido: %', v; END $$;
"""

INSERT_CLIENTE = f"INSERT INTO {TABLE} VALUES (1, %s, %s, %s, 'fisica', %s)"
INSERT_OUTRO = f"INSERT INTO {OUTRA} VALUES (1, %s, 'Maria')"

#: Enchimento. Metade das linhas repete o CPF alvo, para que o PostgreSQL o
#: registre em `most_common_vals` — e o vazamento por `pg_stats` seja real.
#: Com parametros o protocolo estendido recusa multiplos comandos: o ANALYZE
#: vai separado. Medido na Fase 2.
FILL = f"""
INSERT INTO {TABLE}
SELECT i, 'N' || i, CASE WHEN i %% 2 = 0 THEN %s ELSE lpad(i::text, 11, '7') END,
       'e' || i || '@x.com', 'fisica', 'p'
FROM generate_series(2, 60) AS i
"""

ANALYZE = f"ANALYZE {TABLE}"


@pytest.fixture
def database(dsn: str) -> Iterator[str]:
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(DDL)
        setup.execute(INSERT_CLIENTE, [NOME, CPF, EMAIL, SENHA])
        setup.execute(INSERT_OUTRO, [CPF])
        setup.execute(FILL, [CPF])
        setup.execute(ANALYZE)
    yield dsn
    with psycopg.connect(dsn, autocommit=True) as teardown:
        teardown.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "masking.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


@pytest.fixture
def application(database, config_file):
    app = build_application(
        config_path=config_file,
        conninfo=database,
        secrets=MappingSecretProvider({HMAC_KEY_ENV: TEST_HMAC_KEY}),
    )
    yield app
    app.close()


@pytest.fixture
def gateway(application):
    return application.gateway


def dump(result: QueryResult) -> str:
    """Serializacao completa do resultado, para procurar vazamento."""
    return json.dumps(result.model_dump(), ensure_ascii=False, default=str)


def leaks(result: QueryResult, needle: str = CPF) -> bool:
    """True quando o valor sensivel alcanca qualquer parte do resultado."""
    return needle in dump(result)


def first_value(result: QueryResult) -> Any:
    return result.rows[0][0] if result.rows else None
