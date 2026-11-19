"""WSGI entry for process managers that do not speak ASGI."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bid_agent.server.settings')

application = get_wsgi_application()
