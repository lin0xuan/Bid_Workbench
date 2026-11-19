"""Permission classes for session, legacy admin, and project membership."""
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from bid_agent.repositories.platform import ForbiddenError, NotFoundError, transaction
from bid_agent.repositories.workspace import check_access
from bid_agent.server.runtime import principal_of

_READ_METHODS = {'GET', 'HEAD', 'OPTIONS'}


class IsLegacyAdmin(BasePermission):
    """Old analysis and knowledge routes stay limited to administrators."""

    message = '旧版接口仅供管理员使用，请使用文档工作台'

    def has_permission(self, request, view):
        principal = principal_of(request.user)
        return bool(principal and principal.is_admin)


class ProjectObjectPermission(BasePermission):
    """Filter project routes before the handler reads or writes."""

    def has_permission(self, request, view):
        project_id = view.kwargs.get('project_id')
        if not project_id:
            return True
        principal = principal_of(request.user)
        if principal is None:
            return False
        write = request.method not in _READ_METHODS
        try:
            with transaction() as conn:
                check_access(conn, project_id, principal, write=write)
        except NotFoundError as exc:
            raise NotFound(str(exc)) from exc
        except ForbiddenError as exc:
            raise PermissionDenied(str(exc)) from exc
        return True
