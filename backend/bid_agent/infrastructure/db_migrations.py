"""Explicit PostgreSQL migrations: python -m bid_agent.infrastructure.db_migrations upgrade."""
import argparse
import os

from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from bid_agent.core.settings import PROJECT_ROOT
from bid_agent.infrastructure.db_connection import postgres_engine, verify_schema, WRITE_LOCK, is_postgres


def upgrade(url: str | None = None):
    config = Config()
    config.set_main_option('script_location', str(PROJECT_ROOT / 'deploy' / 'postgres'))
    with postgres_engine(url).begin() as conn:
        conn.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,))
        config.attributes['connection'] = conn
        command.upgrade(config, 'head')


def provision_runtime(runtime_url: str, migration_url: str | None = None):
    """Create a separate DML-only login; never weaken an existing privileged role."""
    owner = postgres_engine(migration_url)
    runtime = make_url(runtime_url)
    if (runtime.host, runtime.port or 5432, runtime.database) != (owner.url.host, owner.url.port or 5432, owner.url.database):
        raise ValueError('Runtime and migration URLs must address the same PostgreSQL database')
    if not runtime.username or not runtime.password or runtime.username == owner.url.username:
        raise ValueError('Runtime requires a separate login and password, distinct from the migration owner')
    with owner.begin() as conn:
        conn.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,))
        role = conn.exec_driver_sql(
            'SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication FROM pg_roles WHERE rolname=%s',
            (runtime.username,),
        ).first()
        if role and any(role):
            raise ValueError('Existing runtime role has elevated privileges; refusing to reuse it')
        if conn.exec_driver_sql(
            'SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=%s LIMIT 1',
            (runtime.username,),
        ).first():
            raise ValueError('Runtime role must not inherit other database roles')
        if role:
            # Reusing a login must not preserve old owner/DDL/version-write grants.
            elevated = conn.exec_driver_sql(
                "SELECT has_database_privilege(%s,current_database(),'CREATE'), "
                "has_schema_privilege(%s,'public','CREATE'), "
                "EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' AND r.rolname=%s)",
                (runtime.username,) * 3,
            ).one()
            if any(elevated):
                raise ValueError('Existing runtime role owns objects or has DDL privileges')
            for table in ('alembic_version', 'platform_migrations'):
                if conn.exec_driver_sql(
                    'SELECT has_table_privilege(%s,%s,%s)',
                    (runtime.username, 'public.' + table, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),
                ).scalar_one():
                    raise ValueError('Existing runtime role can modify schema version tables')
        raw = conn.connection.driver_connection
        if not role:
            raw.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(
                sql.Identifier(runtime.username), sql.Literal(runtime.password),
            ))
        raw.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
            sql.Identifier(runtime.database), sql.Identifier(runtime.username),
        ))
        raw.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        raw.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(runtime.username)))
        raw.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(runtime.username)))
        tables = conn.exec_driver_sql(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename NOT IN ('alembic_version','platform_migrations')"
        ).scalars().all()
        for table in tables:
            raw.execute(sql.SQL('GRANT INSERT, UPDATE, DELETE ON TABLE {} TO {}').format(
                sql.Identifier('public', table), sql.Identifier(runtime.username),
            ))
        raw.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(runtime.username)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['upgrade', 'check'])
    args = parser.parse_args()
    if not is_postgres():
        parser.error('Set DATABASE_URL to the intended PostgreSQL database first')
    if args.action == 'upgrade':
        upgrade()
        if runtime_url := os.getenv('BID_RUNTIME_DATABASE_URL', ''):
            provision_runtime(runtime_url)
    else:
        verify_schema()
    print('PostgreSQL schema ready')


if __name__ == '__main__':
    main()
