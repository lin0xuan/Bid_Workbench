"""Offline migration; dry-run imports and verifies every row then rolls back."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from bid_agent.infrastructure.postgres_transfer import transfer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Read-only SQLite cold backup')
    parser.add_argument('--objects-root', type=Path, required=True, help='Matching cold backup objects directory')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true')
    args = parser.parse_args()
    report_path = args.report.resolve()
    if report_path == args.source.resolve() or report_path.is_relative_to(args.objects_root.resolve()):
        parser.error('Report must not overwrite the source or be inside the objects directory')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # Reserve a new, writable report before importing. Never overwrite old evidence.
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump({'ok': False, 'applied': None, 'status': 'started; outcome not yet recorded'}, stream)
        stream.flush()
        os.fsync(stream.fileno())
        try:
            report = transfer(args.source, args.objects_root, apply=args.apply, writers_stopped=args.writers_stopped)
        except Exception as exc:
            # A lost connection during COMMIT can have an unknown outcome.
            # SQL errors may carry business values; never print rows or DSNs.
            report = {'ok': False, 'applied': None, 'error_type': type(exc).__name__,
                      'error': str(exc) if isinstance(exc, ValueError) else 'Migration did not finish normally; verify target state and connectivity before retrying.'}
        print(json.dumps({'ok': report['ok'], 'applied': report['applied'], 'report': str(args.report)}, ensure_ascii=False), flush=True)
        stream.seek(0)
        stream.write(json.dumps(report, ensure_ascii=False, indent=2))
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
