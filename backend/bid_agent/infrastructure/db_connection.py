"""Shared SQLite/PostgreSQL transaction boundary for both repository generations.

Repository SQL uses DB-API qmark parameters. PostgreSQL binds them through
SQLAlchemy's driver API; values are never interpolated into SQL. The first
PostgreSQL release keeps SQLite's serialized write semantics using a transaction
advisory lock, including across API/worker/dispatcher processes.
"""
from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from bid_agent.core.settings import DATABASE_URL, DB_PATH

WRITE_LOCK = 82470801
SCHEMA_REVISION = 'b08_0001'
_SHARED = False


def enable_shared_transactions():
    """After schema setup, repository SQL joins the Django transaction."""
    global _SHARED
    _SHARED = True


def _shared_database(db_path):
    if not _SHARED:
        return False
    if is_postgres():
        return True
    target = DB_PATH if db_path is None else db_path
    try:
        return Path(target).resolve() == Path(DB_PATH).resolve()
    except OSError:
        return False


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


class _DjangoCursor:
    """PostgreSQL cursor results shaped like the existing row dictionaries."""

    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
        description = cursor.description or []
        self.columns = [column[0] for column in description]

    def _row(self, values):
        if values is None:
            return None
        return Row(dict(zip(self.columns, values)))

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(values) for values in self.cursor.fetchall()]

    def __iter__(self):
        return (self._row(values) for values in self.cursor)


class _SqliteConnection:
    """Keep dictionary rows after the ORM has used the same connection."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, parameters=()):
        self.raw.row_factory = sqlite3.Row
        return self.raw.execute(sql, parameters)

    def executescript(self, script):
        self.raw.row_factory = sqlite3.Row
        return self.raw.executescript(script)


class _DjangoConnection:
    def execute(self, sql, parameters=()):
        from django.db import connection

        cursor = connection.cursor()
        if isinstance(parameters, dict):
            statement = _bind_named(sql)
            cursor.execute(statement, parameters)
        else:
            statement, values = bind_qmarks(sql, parameters)
            cursor.execute(statement, values)
        return _DjangoCursor(cursor)


def _bind_named(sql):
    output = []
    quote = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == ':' and index + 1 < len(sql) and (sql[index + 1].isalnum() or sql[index + 1] == '_'):
            end = index + 1
            while end < len(sql) and (sql[end].isalnum() or sql[end] == '_'):
                end += 1
            output.append(f'%({sql[index + 1:end]})s')
            index = end
            continue
        elif char == '%':
            output.append('%%')
        else:
            output.append(char)
        index += 1
    return ''.join(output)


@contextmanager
def _shared_transaction(immediate):
    from django.db import connection, transaction as django_transaction
    from django.db.utils import IntegrityError as DjangoIntegrityError

    try:
        with django_transaction.atomic():
            connection.ensure_connection()
            if is_postgres():
                if immediate:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [WRITE_LOCK])
                yield _DjangoConnection()
            else:
                raw = connection.connection
                raw.row_factory = sqlite3.Row
                raw.execute('PRAGMA foreign_keys=ON')
                yield _SqliteConnection(raw)
    except DjangoIntegrityError as exc:
        raise sqlite3.IntegrityError('Database integrity constraint failed') from exc


@contextmanager
def transaction(db_path=DB_PATH, *, immediate=False):
    if _shared_database(db_path):
        with _shared_transaction(immediate) as conn:
            yield conn
        return
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
