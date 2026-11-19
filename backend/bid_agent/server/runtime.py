"""Request adapters shared by authentication and the HTTP boundary."""
from types import SimpleNamespace

from bid_agent.core.identity import Principal
from bid_agent.core.settings import ROOT_PATH


class SessionUser:
    """Authenticated workspace principal exposed to the HTTP layer."""

    is_authenticated = True
    is_active = True

    def __init__(self, principal):
        self.principal = principal
        self.id = principal.id
        self.username = principal.username
        self.is_admin = principal.is_admin
        self.pk = principal.id

    @property
    def is_staff(self):
        return self.is_admin

    def __str__(self):
        return self.username


class AdaptedRequest:
    """Small request view used by the existing session checks."""

    def __init__(self, request):
        source = getattr(request, '_request', request)
        self.method = source.method
        self.headers = source.headers
        self.cookies = source.COOKIES
        self.META = source.META
        host = source.META.get('REMOTE_ADDR') or '127.0.0.1'
        self.client = SimpleNamespace(host=host)
        self.scope = {'root_path': ROOT_PATH}

    async def is_disconnected(self):
        return False


def principal_of(user):
    """Return a workspace principal from a session user, if present."""
    if isinstance(user, SessionUser):
        return user.principal
    if isinstance(user, Principal):
        return user
    return getattr(user, 'principal', None)
