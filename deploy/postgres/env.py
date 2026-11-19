"""Connections are provided by the migration command; no credentials in config."""
from alembic import context

connection = context.config.attributes.get('connection')
if connection is None:
    raise RuntimeError('Use python -m bid_agent.infrastructure.db_migrations upgrade')
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
