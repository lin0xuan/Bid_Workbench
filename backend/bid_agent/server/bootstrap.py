"""Prepare the shared database before the HTTP service accepts traffic."""
import os

from bid_agent.core.settings import DB_PATH
from bid_agent.infrastructure.database import init_database
from bid_agent.infrastructure.db_connection import is_postgres, verify_schema
from bid_agent.repositories.platform import init_platform_schema


def assert_database_ready():
    """Workers and the dispatcher must not create schema themselves."""
    if is_postgres():
        verify_schema()
        return
    if not DB_PATH.exists():
        raise RuntimeError('Initialize the API database before starting workers')
    verify_schema()


def bootstrap():
    """Create business tables on the API process, then framework tables."""
    role = os.getenv('BID_PROCESS_ROLE', 'api')
    if role in {'worker', 'dispatcher'}:
        assert_database_ready()
        return
    init_database()
    init_platform_schema()
    from bid_agent.core.security import bootstrap_identity
    bootstrap_identity()
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)
