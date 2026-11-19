"""Verified offline transfer into an empty Alembic-managed PostgreSQL database."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from sqlalchemy import inspect, text

from bid_agent.infrastructure.db_connection import Connection, SCHEMA_REVISION, WRITE_LOCK, postgres_engine
from bid_agent.infrastructure.object_store import LocalObjectStore

FTS_TABLES = {'document_chunks_fts' + suffix for suffix in ('', '_config', '_content', '_data', '_docsize', '_idx')}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def _digest(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        # SQLite may return an integer for a REAL column; compare numeric values.
        values = [int(value) if isinstance(value, float) and value.is_integer() else value for value in row]
        digest.update(json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))
        digest.update(b'\n')
        count += 1
    return count, digest.hexdigest()


def _check_objects(source, objects_root):
    store = LocalObjectStore(Path(objects_root))
    seen = {}
    for table in ('document_versions', 'enterprise_asset_versions', 'export_artifacts'):
        for row in source.execute(f'SELECT object_key,sha256,size_bytes FROM {quote(table)}'):
            key, expected, size = row
            if key not in seen:
                path = store.path(key)
                with path.open('rb') as stream:
                    seen[key] = (hashlib.file_digest(stream, 'sha256').hexdigest(), path.stat().st_size)
            if seen[key] != (expected, size):
                raise ValueError(f'Object checksum/size mismatch in {table}')
    return len(seen)


class _DryRunRollback(Exception):
    pass


def transfer(source_path: Path, objects_root: Path, *, apply=False, writers_stopped=False, url=None):
    if apply and not writers_stopped:
        raise ValueError('Apply requires --writers-stopped after stopping all SQLite and PostgreSQL writers')
    report = {'ok': False, 'applied': False, 'tables': [], 'objects_verified': 0}
    engine = postgres_engine(url)
    with closing(sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('PRAGMA query_only=ON')
        source.execute('BEGIN')
        if source.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity_check failed')
        if source.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('SQLite foreign_key_check failed')
        if source.execute('SELECT MAX(version) FROM platform_migrations').fetchone()[0] != 9:
            raise ValueError('Source must be upgraded to SQLite platform v9 before transfer')
        if source.execute("SELECT 1 FROM jobs WHERE status IN ('running','cancelling') LIMIT 1").fetchone():
            raise ValueError('Source still has running/cancelling jobs; drain or recover them before taking the final backup')
        tables = [row[0] for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ) if row[0] not in FTS_TABLES]
        report['objects_verified'] = _check_objects(source, objects_root)
        try:
            with engine.begin() as target:
                target.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,))
                # The offline import may take longer than normal API queries.
                target.exec_driver_sql('SET LOCAL statement_timeout=0')
                if target.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() != SCHEMA_REVISION:
                    raise ValueError('Target Alembic revision does not match this importer')
                inspector = inspect(target)
                target_tables = set(inspector.get_table_names()) - {'alembic_version', 'document_chunks_fts'}
                if set(tables) != target_tables:
                    raise ValueError('Source/target table inventory mismatch; no tables will be silently skipped')
                target.exec_driver_sql('LOCK TABLE ' + ','.join(quote(t) for t in [*tables, 'document_chunks_fts']) + ' IN ACCESS EXCLUSIVE MODE')
                for table in [*tables, 'document_chunks_fts']:
                    if target.exec_driver_sql(f'SELECT 1 FROM {quote(table)} LIMIT 1').first():
                        raise ValueError('Target must be empty; use a new database, never overwrite existing business data')
                target.exec_driver_sql('SET CONSTRAINTS ALL DEFERRED')
                for table in tables:
                    columns = source.execute(f'PRAGMA table_info({quote(table)})').fetchall()
                    names = [row[1] for row in columns]
                    if names != [row['name'] for row in inspector.get_columns(table)]:
                        raise ValueError(f'Column inventory mismatch: {table}')
                    primary = sorted((row for row in columns if row[5]), key=lambda row: row[5])
                    if not primary:
                        raise ValueError(f'Missing primary key: {table}')
                    source_order = ','.join(quote(row[1]) + (' COLLATE BINARY' if row[2].upper() == 'TEXT' else '') for row in primary)
                    target_order = ','.join(quote(row[1]) + (' COLLATE "C"' if row[2].upper() == 'TEXT' else '') for row in primary)
                    selected = ','.join(quote(name) for name in names)
                    query = f'SELECT {selected} FROM {quote(table)}'
                    cursor = source.execute(query + ' ORDER BY ' + source_order)
                    insert = text(f'INSERT INTO {quote(table)} ({selected}) VALUES (' + ','.join(f':p{i}' for i in range(len(names))) + ')')
                    while batch := cursor.fetchmany(500):
                        target.execute(insert, [{f'p{i}': value for i, value in enumerate(row)} for row in batch])
                    source_count, source_hash = _digest(source.execute(query + ' ORDER BY ' + source_order))
                    target_count, target_hash = _digest(target.execution_options(stream_results=True).exec_driver_sql(query + ' ORDER BY ' + target_order))
                    target.execution_options(stream_results=False)
                    if (source_count, source_hash) != (target_count, target_hash):
                        raise ValueError(f'Row checksum mismatch: {table}')
                    report['tables'].append({'table': table, 'rows': source_count, 'sha256': source_hash})
                from bid_agent.infrastructure.database import _upsert_document_chunk_fts
                adapter = Connection(target)
                for row in source.execute('SELECT * FROM document_chunks'):
                    names = [col[1] for col in source.execute('PRAGMA table_info(document_chunks)')]
                    _upsert_document_chunk_fts(adapter, dict(zip(names, row)))
                target.exec_driver_sql('SET CONSTRAINTS ALL IMMEDIATE')
                if not apply:
                    raise _DryRunRollback()
                # Sequence values must advance past imported event cursors.
                target.exec_driver_sql("SELECT setval(pg_get_serial_sequence('job_events','sequence'), COALESCE(MAX(sequence),1), COUNT(*)>0) FROM job_events")
                report['applied'] = True
        except _DryRunRollback:
            pass
    report['ok'] = True
    return report
