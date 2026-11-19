"""ASGI entry point: uvicorn bid_agent.main:app."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bid_agent.server.settings')
os.environ.setdefault('BID_PROCESS_ROLE', 'api')

import django

django.setup()

from bid_agent.core.settings import ROOT_PATH  # noqa: E402
from bid_agent.server.bootstrap import bootstrap  # noqa: E402

bootstrap()

from bid_agent.server.asgi import application as _application  # noqa: E402


class _RootPath:
    """Apply the public prefix when the process is mounted behind a proxy."""

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'lifespan':
            await _accept_lifespan(receive, send)
            return
        http_scope = scope.get('type') in {'http', 'websocket'}
        if http_scope and ROOT_PATH and not scope.get('root_path'):
            scope = dict(scope)
            scope['root_path'] = ROOT_PATH
        await self.application(scope, receive, send)


async def _accept_lifespan(receive, send):
    """The business schema is prepared at import, so startup only acknowledges."""
    while True:
        message = await receive()
        if message['type'] == 'lifespan.startup':
            await send({'type': 'lifespan.startup.complete'})
        elif message['type'] == 'lifespan.shutdown':
            await send({'type': 'lifespan.shutdown.complete'})
            return


app = _RootPath(_application)
