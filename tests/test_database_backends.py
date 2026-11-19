"""Run the same transaction, queue and access contracts on SQLite and PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import io
import sqlite3
from uuid import uuid4

from docx import Document
import pytest

from bid_agent.core.identity import Principal
from bid_agent.infrastructure.db_connection import bind_qmarks, transaction
from bid_agent.infrastructure.object_store import object_store
from bid_agent.repositories import jobs, workspace
from bid_agent.repositories.platform import ConflictError, ForbiddenError, NotFoundError, now

USER = Principal('local', '__local__', True)


def _version():
    project = workspace.create_project('数据库切流回归', USER)
    document = Document()
    document.add_paragraph('数据库切流验收原件：技术方案。')
    stream = io.BytesIO()
    document.save(stream)
    stored = object_store.put(io.BytesIO(stream.getvalue()), 'database-test.docx')
    version, _ = workspace.save_version(project['id'], USER, stored)
    return project, version


def test_parameter_binding_keeps_literals_and_comments():
    sql, params = bind_qmarks("SELECT '?' AS q, '50%' AS p, ? -- ?\n/* ? */", ["引号' ? %"])
    assert sql == "SELECT '?' AS q, '50%%' AS p, %s -- ?\n/* ? */"
    assert params == ("引号' ? %",)
    with pytest.raises(ValueError):
        bind_qmarks('SELECT ?', [])


def test_database_parameters_and_rollback(client):
    with transaction() as conn:
        assert conn.execute("SELECT '50%' AS value, ? AS supplied", ("文字' ? %",)).fetchone()['supplied'] == "文字' ? %"
        assert conn.execute('SELECT :value AS value', {'value': 'named ? %'}).fetchone()['value'] == 'named ? %'
    user_id = 'rollback_' + uuid4().hex
    with pytest.raises(RuntimeError):
        with transaction(immediate=True) as conn:
            conn.execute('INSERT INTO users VALUES(?,?,?,?,?)', (user_id, user_id, 'disabled', 0, now()))
            raise RuntimeError('simulate failure')
    with transaction() as conn:
        assert conn.execute('SELECT id FROM users WHERE id=?', (user_id,)).fetchone() is None


def test_queue_idempotency_atomic_outbox_and_concurrent_claim(client, monkeypatch):
    project, version = _version()
    key = uuid4().hex
    with ThreadPoolExecutor(max_workers=4) as pool:
        created = list(pool.map(lambda _: jobs.create_job(version['id'], {}, key, USER), range(4)))
    assert sum(is_new for _, is_new in created) == 1
    job_id = created[0][0]['id']
    assert {item['id'] for item, _ in created} == {job_id}
    with pytest.raises(ConflictError):
        jobs.create_job(version['id'], {'parse_method': 'different'}, key, USER)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = [row for row in pool.map(lambda _: jobs.claim_job(job_id), range(4)) if row]
    assert len(claimed) == 1
    lease = claimed[0]['lease_token']
    assert not jobs.complete(job_id, 'old-lease', {'parser_version': 'test'})
    jobs.cancel_job(job_id, USER)
    assert not jobs.complete(job_id, lease, {'parser_version': 'test'})
    assert jobs.get_job(job_id, USER)['status'] == 'cancelled'
    def fail_outbox(*args, **kwargs):
        raise RuntimeError('injected outbox failure')
    monkeypatch.setattr(jobs, '_enqueue', fail_outbox)
    with pytest.raises(RuntimeError):
        jobs.create_job(version['id'], {}, 'rollback-key', USER)
    with transaction() as conn:
        assert conn.execute('SELECT id FROM jobs WHERE project_id=? AND idempotency_key=?', (project['id'], 'rollback-key')).fetchone() is None
        assert conn.execute('SELECT COUNT(*) FROM job_events WHERE job_id=?', (job_id,)).fetchone()[0] == 4


def test_parse_result_and_access_boundaries(client):
    from bid_agent.services.parse_jobs import execute_parse_job
    project, version = _version()
    viewer_id = 'viewer_' + uuid4().hex
    with transaction(immediate=True) as conn:
        conn.execute('INSERT INTO users VALUES(?,?,?,?,?)', (viewer_id, viewer_id, 'disabled', 0, now()))
        conn.execute('INSERT INTO project_members VALUES(?,?,?)', (project['id'], viewer_id, 'viewer'))
    viewer = Principal(viewer_id, viewer_id, False)
    stranger = Principal('stranger', 'stranger', False)
    assert workspace.get_version(version['id'], viewer)['id'] == version['id']
    with pytest.raises(ForbiddenError):
        jobs.create_job(version['id'], {}, uuid4().hex, viewer)
    with pytest.raises(NotFoundError):
        workspace.get_version(version['id'], stranger)
    job, _ = jobs.create_job(version['id'], {'parse_method': 'docx2python'}, uuid4().hex, USER)
    assert execute_parse_job(job['id'])
    assert not execute_parse_job(job['id'])
    result = jobs.get_result(job['id'], viewer)
    assert '切流验收原件' in str(result)
    events = jobs.events(job['id'], viewer, after=0)
    assert events[-1]['event_type'] == 'succeeded'
    assert jobs.events(job['id'], viewer, after=events[-1]['sequence']) == []


def test_auth_sessions_csrf_and_duplicate_users(client, monkeypatch):
    from bid_agent.core.security import hash_password
    username = 'admin_' + uuid4().hex
    password = 'test-only-password-12345'
    with transaction(immediate=True) as conn:
        conn.execute('INSERT INTO users VALUES(?,?,?,?,?)', (username, username, hash_password(password), 1, now()))
    monkeypatch.setenv('BID_AUTH_ENABLED', 'true')
    client.cookies.clear()
    assert client.get('/v1/projects').status_code == 401
    login = client.post('/auth/login', json={'username': username, 'password': password})
    assert login.status_code == 200
    assert client.post('/v1/projects', json={'title': 'must reject missing csrf'}).status_code == 403
    headers = {'X-CSRF-Token': login.json()['csrf_token']}
    payload = {'username': 'user_' + uuid4().hex, 'password': password}
    assert client.post('/auth/users', json=payload, headers=headers).status_code == 201
    assert client.post('/auth/users', json=payload, headers=headers).status_code == 409
    assert client.post('/auth/logout', headers=headers).status_code == 200
    assert client.get('/v1/projects').status_code == 401
    client.cookies.clear()


def test_search_keeps_case_insensitive_contract(client):
    from bid_agent.repositories import assets, knowledge, projects
    marker = 'PgMigration' + uuid4().hex
    entry = knowledge.upsert_knowledge_entry({'type': 'company', 'title': marker, 'content': 'mixed case'})
    project = workspace.create_project(marker, USER)
    asset = assets.create_asset(USER, category='qualification', title=marker)
    for query in (marker.lower(), marker.upper()):
        assert entry['id'] in {row['id'] for row in knowledge.list_knowledge_entries(query=query)}
        assert project['id'] in {row['id'] for row in projects.list_projects(query=query)}
        assert asset['id'] in {row['id'] for row in assets.list_assets(USER, query=query)}
