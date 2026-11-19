"""Shared SQLite/PostgreSQL transaction boundary for both repository generations.

Repository SQL uses DB-API qmark parameters. PostgreSQL binds them through
SQLAlchemy's driver API; values are never interpolated into SQL. The first
PostgreSQL release keeps SQLite's serialized write semantics using a transaction
advisory lock, including across API/worker/dispatcher processes.
"""
from contextlib import contextmanager
from functools import lru_cache
import os
import sqlite3

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from bid_agent.core.settings import DATABASE_URL, DB_PATH

WRITE_LOCK = 82470801
SCHEMA_REVISION = 'b08_0001'


def is_postgres() -> bool:
    return bool(DATABASE_URL)


@lru_cache(maxsize=4)
def _engine(url: str, pid: int):
    # Cache by PID so Celery children never reuse a parent's pooled sockets.
    return create_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5,
        pool_timeout=30, hide_parameters=True,
        connect_args={'connect_timeout': 5, 'options': '-c lock_timeout=30000 -c statement_timeout=60000'},
    )


def postgres_engine(url: str | None = None):
    value = url if url is not None else DATABASE_URL
    if value.startswith('postgresql://'):
        value = 'postgresql+psycopg://' + value[len('postgresql://'):]
    if not value.startswith('postgresql+psycopg://'):
        raise ValueError('DATABASE_URL must use postgresql:// or postgresql+psycopg://')
    return _engine(value, os.getpid())


def bind_qmarks(sql: str, parameters) -> tuple[str, tuple]:
    """Translate placeholders outside SQL strings, identifiers and comments."""
    output = []
    quote = None
    count = 0
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif sql[index:index + 2] == '--':
            end = sql.find('\n', index)
            end = len(sql) if end < 0 else end
            output.append(sql[index:end])
            index = end - 1
        elif sql[index:index + 2] == '/*':
            end = sql.find('*/', index + 2)
            if end < 0:
                raise ValueError('Unterminated SQL comment')
            output.append(sql[index:end + 2])
            index = end + 1
        elif char == '?':
            output.append('\x00')
            count += 1
        else:
            output.append(char)
        index += 1
    values = tuple(int(value) if isinstance(value, bool) else value for value in parameters)
    if count != len(values):
        raise ValueError('SQL placeholder count does not match parameters')
    return ''.join(output).replace('%', '%%').replace('\x00', '%s'), values


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, result):
        self.result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self.result.fetchone()
        return Row(row._mapping) if row is not None else None

    def fetchall(self):
        return [Row(row._mapping) for row in self.result.fetchall()]

    def __iter__(self):
        return (Row(row._mapping) for row in self.result)


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql: str, parameters=()):
        if isinstance(parameters, dict):
            return Result(self.connection.execute(text(sql), parameters))
        statement, values = bind_qmarks(sql, parameters)
        return Result(self.connection.exec_driver_sql(statement, values))


@contextmanager
def transaction(db_path=DB_PATH, *, immediate=False):
    if is_postgres():
        try:
            with postgres_engine().begin() as raw:
                if immediate:
                    raw.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,))
                yield Connection(raw)
        except IntegrityError as exc:
            # Preserve the existing repository/auth uniqueness error contract.
            raise sqlite3.IntegrityError('Database integrity constraint failed') from exc
    else:
        connection = sqlite3.connect(db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            if immediate:
                connection.execute('BEGIN IMMEDIATE')
            with connection:
                yield connection
        finally:
            connection.close()


def verify_schema():
    if is_postgres():
        with postgres_engine().connect() as conn:
            version = conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
        if version != SCHEMA_REVISION:
            raise RuntimeError('Database schema mismatch; run the documented Alembic upgrade before starting services')


def table_exists(conn, name: str) -> bool:
    if is_postgres():
        return bool(conn.execute(
            'SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?',
            (name,),
        ).fetchone())
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
