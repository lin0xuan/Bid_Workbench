"""A migration must reserve its report before any database change."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def migration_cli(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/migrate_sqlite_to_postgres.py'
    spec = importlib.util.spec_from_file_location('migration_cli', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / 'source.db'
    source.write_bytes(b'preserve source')
    report = tmp_path / 'report.json'
    monkeypatch.setattr(sys, 'argv', [str(path), '--source', str(source),
                                    '--objects-root', str(tmp_path / 'objects'), '--report', str(report)])
    return module, source, report


def test_existing_report_rejected_before_transfer(migration_cli, monkeypatch):
    cli, source, report = migration_cli
    report.write_text('previous evidence', encoding='utf-8')
    monkeypatch.setattr(cli, 'transfer', lambda *a, **kw: pytest.fail('Must reject before writing database'))
    with pytest.raises(FileExistsError):
        cli.main()
    assert report.read_text(encoding='utf-8') == 'previous evidence'
    assert source.read_bytes() == b'preserve source'


def test_connection_loss_report_does_not_claim_rollback(migration_cli, monkeypatch):
    cli, _, report = migration_cli
    def lost_connection(*args, **kwargs):
        assert json.loads(report.read_text(encoding='utf-8'))['applied'] is None
        raise RuntimeError('secret DSN or business values')
    monkeypatch.setattr(cli, 'transfer', lost_connection)
    assert cli.main() == 1
    recorded = json.loads(report.read_text(encoding='utf-8'))
    assert recorded['applied'] is None
    assert 'secret' not in str(recorded)
    assert 'rolled back' not in str(recorded)
