"""Real PostgreSQL import/dry-run verification using databases owned by this test."""
from contextlib import closing
import io
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from bid_agent.infrastructure import db_connection
from bid_agent.infrastructure.db_migrations import upgrade
from bid_agent.infrastructure.postgres_transfer import transfer

pytestmark = pytest.mark.skipif(not db_connection.is_postgres(), reason='Set BID_TEST_DATABASE_URL for PostgreSQL integration')


@pytest.fixture
def target_url():
    # Requires CREATEDB only for tests; no existing database/schema is deleted.
    name = 'bid_test_transfer_' + uuid4().hex
    engine = db_connection.postgres_engine()
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = make_url(db_connection.DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    try:
        upgrade(url)
        yield url
    finally:
        db_connection.postgres_engine(url).dispose()
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            conn.exec_driver_sql(f'DROP DATABASE "{name}"')


@pytest.fixture
def source(tmp_path, monkeypatch):
    from docx import Document
    from bid_agent.infrastructure.database import init_database, save_analysis_result
    from bid_agent.parsing.document_parser import split_bid_markdown_sections
    from bid_agent.infrastructure.object_store import LocalObjectStore
    from bid_agent.repositories.platform import init_platform_schema
    path = tmp_path / 'source.db'
    with monkeypatch.context() as context:
        context.setattr(db_connection, 'DATABASE_URL', '')
        init_database(path)
        init_platform_schema(path)
        save_analysis_result(
            split_bid_markdown_sections('# 技术要求\n提供软件开发和部署服务。'),
            {'project_overview': '项目名称：迁库旧分析项目'}, db_path=path,
        )
    store = LocalObjectStore(tmp_path / 'objects')
    document = Document()
    document.add_paragraph('迁库原件中文 50% ?')
    stream = io.BytesIO()
    document.save(stream)
    stored = store.put(io.BytesIO(stream.getvalue()), 'source.docx')
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("INSERT INTO users VALUES('local','__local__','disabled',1,'2026-11-18')")
        conn.execute("INSERT INTO projects(id,project_name,created_at,updated_at) VALUES('project','迁库项目','2026-11-18','2026-11-18')")
        conn.execute("INSERT INTO project_members VALUES('project','local','owner')")
        conn.execute("INSERT INTO documents VALUES('doc','project','原件','tender',NULL,'2026-11-18')")
        conn.execute('INSERT INTO document_versions VALUES(?,?,?,?,?,?,?,?,?,?)',
                     ('version','doc',1,'source.docx',stored['media_type'],stored['object_key'],stored['sha256'],stored['size_bytes'],'local','2026-11-18'))
        conn.execute("INSERT INTO jobs(id,project_id,document_version_id,status,options_json,idempotency_key,request_hash,created_by,created_at,updated_at) VALUES('job','project','version','queued','{}','key','hash','local','2026-11-18','2026-11-18')")
        conn.execute("INSERT INTO job_events VALUES(100,'job','queued','{}','2026-11-18')")
        conn.execute("INSERT INTO outbox_events(id,job_id,created_at) VALUES('outbox','job','2026-11-18')")
    return path, store


def test_dry_run_apply_checksums_sequence_and_nonempty_refusal(source, target_url):
    path, store = source
    before = path.read_bytes()
    report = transfer(path, store.root, url=target_url)
    assert report['ok'] and not report['applied'] and report['objects_verified'] == 1
    engine = db_connection.postgres_engine(target_url)
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM projects').scalar_one() == 0
    applied = transfer(path, store.root, url=target_url, apply=True, writers_stopped=True)
    assert applied['tables'] == report['tables']
    assert path.read_bytes() == before
    with engine.begin() as conn:
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM document_chunks_fts').scalar_one() > 0
        sequence = conn.exec_driver_sql("INSERT INTO job_events(job_id,event_type,payload_json,created_at) VALUES('job','test','{}','now') RETURNING sequence").scalar_one()
        assert sequence == 101
    with pytest.raises(ValueError, match='empty'):
        transfer(path, store.root, url=target_url, apply=True, writers_stopped=True)


def test_corrupt_object_or_unstopped_writers_cannot_migrate(source, target_url):
    path, store = source
    with pytest.raises(ValueError, match='writers-stopped'):
        transfer(path, store.root, url=target_url, apply=True)
    next(store.root.rglob('*.docx')).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='checksum'):
        transfer(path, store.root, url=target_url, apply=True, writers_stopped=True)
    with db_connection.postgres_engine(target_url).connect() as conn:
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM projects').scalar_one() == 0


def test_column_drift_rolls_back_partial_import(source, target_url):
    path, store = source
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('ALTER TABLE users ADD COLUMN unexpected TEXT')
    with pytest.raises(ValueError, match='Column inventory'):
        transfer(path, store.root, url=target_url, apply=True, writers_stopped=True)
    with db_connection.postgres_engine(target_url).connect() as conn:
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM projects').scalar_one() == 0


def test_runtime_role_can_write_business_but_not_schema(target_url, monkeypatch):
    from bid_agent.infrastructure.db_migrations import provision_runtime
    from sqlalchemy.exc import ProgrammingError
    role = 'bid_test_app_' + uuid4().hex
    runtime_url = make_url(target_url).set(username=role, password='test-runtime-only').render_as_string(hide_password=False)
    owner = db_connection.postgres_engine(target_url)
    try:
        provision_runtime(runtime_url, target_url)
        with monkeypatch.context() as context:
            context.setattr(db_connection, 'DATABASE_URL', runtime_url)
            with db_connection.transaction(immediate=True) as conn:
                conn.execute("INSERT INTO users VALUES('local','__local__','disabled',1,'now')")
            with pytest.raises(ProgrammingError):
                with db_connection.transaction() as conn:
                    conn.execute('CREATE TABLE forbidden_table(id TEXT)')
            with pytest.raises(ProgrammingError):
                with db_connection.transaction() as conn:
                    conn.execute("UPDATE alembic_version SET version_num='wrong'")
        with owner.connect() as conn:
            flags = conn.exec_driver_sql('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=%s', (role,)).one()
            assert not any(flags)
        provision_runtime(runtime_url, target_url)  # Normal restarts remain idempotent.
        with owner.begin() as conn:
            conn.exec_driver_sql(f'GRANT CREATE ON SCHEMA public TO "{role}"')
        with pytest.raises(ValueError, match='DDL privileges'):
            provision_runtime(runtime_url, target_url)
        with owner.begin() as conn:
            conn.exec_driver_sql(f'REVOKE CREATE ON SCHEMA public FROM "{role}"')
            conn.exec_driver_sql(f'GRANT UPDATE ON alembic_version TO "{role}"')
        with pytest.raises(ValueError, match='version tables'):
            provision_runtime(runtime_url, target_url)
    finally:
        db_connection.postgres_engine(runtime_url).dispose()
        with owner.begin() as conn:
            conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
            conn.exec_driver_sql(f'DROP ROLE "{role}"')
