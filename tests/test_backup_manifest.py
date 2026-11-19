"""Backup validation must not call a partial or unrelated dump complete."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['valid', 'missing_dump', 'outside_path'])
def test_postgres_backup_manifest(tmp_path, mode):
    backup = tmp_path / 'backup'
    (backup / 'storage').mkdir(parents=True)
    dump = b'PGDMP-test-fixture'
    hashes = {'postgres.dump': hashlib.sha256(dump).hexdigest()}
    if mode != 'missing_dump':
        (backup / 'postgres.dump').write_bytes(dump)
    if mode == 'outside_path':
        (tmp_path / 'outside').write_bytes(dump)
        hashes['../outside'] = hashlib.sha256(dump).hexdigest()
    (backup / 'manifest.json').write_text(json.dumps({'database': 'postgresql', 'files_sha256': hashes}), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/drill_recovery.py'),
         '--backup-dir', str(backup), '--expect-db'],
        capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'},
    )
    assert (result.returncode == 0) == (mode == 'valid')
    assert json.loads(result.stdout)['ok'] == (mode == 'valid')
