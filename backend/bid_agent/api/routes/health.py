"""Liveness and database readiness probes; never call external models."""
import sqlite3
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter, HTTPException
from bid_agent.core.settings import BUILD_VERSION, env_bool
from bid_agent.infrastructure.db_connection import transaction, verify_schema, is_postgres

router = APIRouter(tags=['health'])


@router.get('/health')
def health() -> dict:
    return {'status': 'ok', 'build': BUILD_VERSION, 'features': {
        'project_library': True, 'project_delete': True,
        'request_scoped_model_selection': True,
        'chroma_vector_store': env_bool('BID_VECTOR_STORE_ENABLED'),
    }}


@router.get('/ready')
def ready() -> dict:
    try:
        verify_schema()
        with transaction() as conn:
            conn.execute('SELECT id FROM projects LIMIT 1').fetchall()
    except (sqlite3.Error, SQLAlchemyError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail='Database is not ready') from exc
    return {'status': 'ready', 'database': 'postgresql' if is_postgres() else 'sqlite'}
