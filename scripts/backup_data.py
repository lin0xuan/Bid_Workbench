"""Stop this Compose application, copy its data, then restore its running state."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = []


def compose(*args, capture=False):
    return subprocess.run(['docker', 'compose', *COMPOSE_FILES, *args], cwd=ROOT, check=True,
                          text=True, encoding='utf-8', capture_output=capture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'backups')
    parser.add_argument('-f', '--compose-file', action='append', default=[])
    parser.add_argument('--env-file')
    parser.add_argument('-p', '--project-name')
    args = parser.parse_args()
    COMPOSE_FILES.extend(value for path in args.compose_file for value in ('-f', path))
    if args.env_file:
        COMPOSE_FILES.extend(['--env-file', args.env_file])
    if args.project_name:
        COMPOSE_FILES.extend(['-p', args.project_name])
    config = json.loads(compose('config', '--format', 'json', capture=True).stdout)
    services = config['services']
    database_url = services['api'].get('environment', {}).get('DATABASE_URL') or ''
    postgres = bool(database_url)
    pg_env = services.get('postgres', {}).get('environment', {})
    if postgres:
        parsed = urlsplit(database_url)
        if parsed.hostname != 'postgres' or unquote(parsed.path.lstrip('/')) != pg_env.get('POSTGRES_DB'):
            raise RuntimeError('External PostgreSQL needs a coordinated pg_dump + objects backup; this script only backs up the Compose postgres service')
        for service in ('worker', 'dispatcher'):
            if services[service].get('environment', {}).get('DATABASE_URL') != database_url:
                raise RuntimeError('API/worker/dispatcher DATABASE_URL mismatch; refusing incomplete backup')
    destination = args.output_dir.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    running = compose('ps', '--status', 'running', '--services', capture=True).stdout.splitlines()
    owned_running = [service for service in ('web', 'dispatcher', 'worker', 'api') if service in running]
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'storage').mkdir()
    dump_path = f'/tmp/bid-backup-{uuid4().hex}.dump'
    try:
        if owned_running:
            compose('stop', *owned_running)
        if postgres:
            compose('exec', '-T', 'postgres', 'pg_dump', '--format=custom', '--no-owner', '--no-acl',
                    '--username', pg_env['POSTGRES_USER'], '--dbname', pg_env['POSTGRES_DB'], '--file', dump_path)
            compose('cp', f'postgres:{dump_path}', str(destination / 'postgres.dump'))
        compose('cp', 'api:/app/storage/.', str(destination / 'storage'))
        hashes = {}
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                with path.open('rb') as stream:
                    hashes[path.relative_to(destination).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
        (destination / 'manifest.json').write_text(json.dumps({
            'created_at': datetime.now(timezone.utc).isoformat(),
            'files_sha256': hashes,
            'database': 'postgresql' if postgres else 'sqlite',
            'notes': 'Cold backup. Environment secrets and model cache are excluded.',
        }, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if postgres:
            try:
                compose('exec', '-T', 'postgres', 'rm', '-f', '--', dump_path)
            except subprocess.CalledProcessError:
                pass
        if owned_running:
            compose('start', *reversed(owned_running))
    print(destination)


if __name__ == '__main__':
    main()
