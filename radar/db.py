import sqlite3

from . import config

TABELAS = """
CREATE TABLE IF NOT EXISTS vagas (
    id            TEXT PRIMARY KEY,   -- "<fonte>:<id na fonte>"
    fonte         TEXT NOT NULL,
    titulo        TEXT NOT NULL,
    empresa       TEXT NOT NULL,
    logo          TEXT,
    url           TEXT NOT NULL,
    local         TEXT,
    publicada_em  INTEGER NOT NULL,
    vista_em      INTEGER NOT NULL,   -- primeira vez que o radar viu a vaga
    resumo        TEXT,
    stacks        TEXT NOT NULL,      -- lista JSON
    tags          TEXT NOT NULL,      -- lista JSON
    senioridade   TEXT,
    tecnologia    INTEGER NOT NULL,
    tipo          TEXT,
    sal_min       REAL,
    sal_max       REAL,
    moeda         TEXT,
    periodo       TEXT,
    sal_min_usd   INTEGER,            -- já convertido para USD por ano
    sal_max_usd   INTEGER,
    fuso_tipo     TEXT NOT NULL,      -- global | informado | estimado | desconhecido
    fusos         TEXT NOT NULL       -- lista JSON de offsets UTC
);
CREATE INDEX IF NOT EXISTS idx_vagas_publicada ON vagas(publicada_em);

CREATE TABLE IF NOT EXISTS coletas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte      TEXT NOT NULL,
    em         INTEGER NOT NULL,
    ok         INTEGER NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 0,
    erro       TEXT
);
"""


def conecta():
    conn = sqlite3.connect(config.BANCO, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def cria_tabelas():
    with conecta() as conn:
        conn.executescript(TABELAS)
