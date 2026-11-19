#!/usr/bin/env python
"""Management commands for the workspace service."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'backend'))


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bid_agent.server.settings')
    os.environ.setdefault('BID_PROCESS_ROLE', 'manage')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
