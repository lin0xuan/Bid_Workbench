"""Session authentication backed by the existing cookie and CSRF checks."""
from fastapi import HTTPException
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from bid_agent.core.security import current_user
from bid_agent.server.runtime import AdaptedRequest, SessionUser


class WorkspaceAuthentication(BaseAuthentication):
    """Accept the workspace session cookie. Missing sessions are unauthorized."""

    def authenticate_header(self, request):
        return 'Cookie realm="workspace"'

    def authenticate(self, request):
        try:
            principal = current_user(AdaptedRequest(request))
        except HTTPException as exc:
            if exc.status_code == 401:
                raise AuthenticationFailed(exc.detail) from exc
            raise PermissionDenied(exc.detail) from exc
        return SessionUser(principal), None
