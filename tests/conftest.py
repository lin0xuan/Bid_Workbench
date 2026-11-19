import os
import tempfile
from pathlib import Path

import pytest

# Set configuration before application imports; never touch a user's data/models.
_storage = tempfile.TemporaryDirectory(prefix='bid-agent-tests-')
os.environ['BID_STORAGE_DIR'] = _storage.name
os.environ['BID_DB_PATH'] = str(Path(_storage.name) / 'data' / 'test.db')
os.environ['CHROMA_PERSIST_DIR'] = str(Path(_storage.name) / 'chroma')
os.environ['BID_VECTOR_STORE_ENABLED'] = 'false'
os.environ['RERANKER_ENABLED'] = 'false'
os.environ['BID_ALLOW_SERVER_PATHS'] = 'false'
os.environ['LLM_API_KEY'] = ''
os.environ['MINERU_API_TOKEN'] = ''
# Never inherit a developer's production DATABASE_URL from their shell/.env.
# PostgreSQL regression requires an explicitly selected disposable database.
os.environ['DATABASE_URL'] = os.getenv('BID_TEST_DATABASE_URL', '')


@pytest.fixture(scope='session')
def client():
    if os.environ['DATABASE_URL']:
        from bid_agent.infrastructure.db_migrations import upgrade
        upgrade()
    from fastapi.testclient import TestClient
    from bid_agent.main import app
    with TestClient(app) as client:
        yield client
    _storage.cleanup()
