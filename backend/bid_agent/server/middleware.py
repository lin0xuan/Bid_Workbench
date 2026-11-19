"""HTTP middleware that keeps script prefix and workspace identity aligned."""
from django.urls import set_script_prefix
from django.utils.deprecation import MiddlewareMixin

from bid_agent.core.settings import ROOT_PATH
from bid_agent.server.runtime import AdaptedRequest, SessionUser


class ScriptPrefixMiddleware(MiddlewareMixin):
    """Reverse links under the public prefix while matching stripped paths."""

    def process_request(self, request):
        set_script_prefix(ROOT_PATH or '')


class WorkspaceUserMiddleware(MiddlewareMixin):
    """Attach the workspace session when the framework user is anonymous."""

    def process_request(self, request):
        current = getattr(request, 'user', None)
        if current is not None and getattr(current, 'is_authenticated', False):
            return
        from fastapi import HTTPException

        from bid_agent.core.security import current_user

        try:
            request.user = SessionUser(current_user(AdaptedRequest(request)))
        except HTTPException:
            return
