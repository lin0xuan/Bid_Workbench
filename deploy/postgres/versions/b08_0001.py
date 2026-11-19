"""Full legacy + platform v9 baseline, preserving existing IDs and value types."""
from pathlib import Path
from alembic import op

revision = 'b08_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = conn.exec_driver_sql(
        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name != 'alembic_version'"
    ).fetchall()
    if existing:
        raise RuntimeError('Baseline requires an empty PostgreSQL schema; never stamp a draft or occupied database')
    schema = (Path(__file__).resolve().parents[1] / 'schema_v1.sql').read_text(encoding='utf-8')
    for statement in schema.split(';'):
        if statement.strip():
            conn.exec_driver_sql(statement)


def downgrade():
    raise RuntimeError('Destructive downgrade is disabled. Restore the verified pre-cutover backup instead.')
