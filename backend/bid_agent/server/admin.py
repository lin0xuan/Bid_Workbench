"""Maintenance screens. Records are visible, not edited here."""
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.html import escape
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.responses import Response as SideResponse

from bid_agent.api.routes.auth import Credentials
from bid_agent.api.routes.auth import login as login_account
from bid_agent.apps.accounts.models import User
from bid_agent.apps.bids.models import BidSection, BidVersion
from bid_agent.apps.documents.models import Document, DocumentVersion
from bid_agent.apps.jobs.models import Job, OutboxEvent
from bid_agent.apps.knowledge.models import KnowledgeEntry
from bid_agent.apps.projects.models import Project
from bid_agent.core.security import current_user
from bid_agent.core.settings import env_bool
from bid_agent.server.dispatch import _copy_side_effects
from bid_agent.server.runtime import AdaptedRequest

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>登录</title></head>
<body>
<h1>工作台维护</h1>
<p>{message}</p>
<form method="post">
<label>用户名 <input name="username" autocomplete="username"></label>
<label>密码 <input name="password" type="password"
 autocomplete="current-password"></label>
<button type="submit">登录</button>
</form>
</body>
</html>
"""


class ReadOnlyAdmin(admin.ModelAdmin):
    """Block changes that would skip the business services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UserAdmin(ReadOnlyAdmin):
    list_display = ('username', 'is_admin', 'created_at')
    search_fields = ('username',)
    exclude = ('password_hash',)


class ProjectAdmin(ReadOnlyAdmin):
    list_display = ('project_name', 'status', 'buyer_name', 'updated_at')
    search_fields = ('project_name', 'project_code', 'buyer_name')


class DocumentAdmin(ReadOnlyAdmin):
    list_display = ('title', 'kind', 'project_id', 'created_at')
    search_fields = ('title',)


class DocumentVersionAdmin(ReadOnlyAdmin):
    list_display = ('file_name', 'version', 'size_bytes', 'created_at')
    search_fields = ('file_name', 'sha256')
    exclude = ('object_key',)


class JobAdmin(ReadOnlyAdmin):
    list_display = ('id', 'kind', 'status', 'stage', 'progress', 'updated_at')
    list_filter = ('status', 'kind')
    exclude = ('lease_token', 'options_json', 'request_hash')


class OutboxAdmin(ReadOnlyAdmin):
    list_display = ('id', 'job_id', 'status', 'attempts', 'created_at')
    exclude = ('lease_token',)


class KnowledgeAdmin(ReadOnlyAdmin):
    list_display = ('title', 'type', 'updated_at')
    search_fields = ('title', 'content')


class BidVersionAdmin(ReadOnlyAdmin):
    list_display = ('title', 'project_id', 'created_at')
    search_fields = ('title',)


class BidSectionAdmin(ReadOnlyAdmin):
    list_display = ('title', 'level', 'sort_order', 'bid_version_id')
    search_fields = ('title',)


class WorkspaceAdminSite(AdminSite):
    """Admin access follows the workspace session, not a second account table."""

    site_header = '投标工作台'
    site_title = '投标工作台'
    index_title = '业务记录'

    def has_permission(self, request):
        if not env_bool('BID_AUTH_ENABLED'):
            return True
        try:
            principal = current_user(AdaptedRequest(request))
        except HTTPException:
            return False
        return bool(principal.is_admin)

    def login(self, request, extra_context=None):
        if not env_bool('BID_AUTH_ENABLED'):
            return redirect('admin:index')
        message = ''
        if request.method == 'POST':
            side = SideResponse()
            try:
                login_account(
                    Credentials(
                        username=request.POST.get('username', ''),
                        password=request.POST.get('password', ''),
                    ),
                    AdaptedRequest(request),
                    side,
                )
            except (HTTPException, ValidationError) as exc:
                detail = getattr(exc, 'detail', '登录失败')
                message = escape(detail if isinstance(detail, str) else '登录失败')
            else:
                response = redirect('admin:index')
                _copy_side_effects(response, side)
                return response
        page = _LOGIN_PAGE.format(message=message)
        return HttpResponse(page)


site = WorkspaceAdminSite(name='workspace_admin')
site.register(User, UserAdmin)
site.register(Project, ProjectAdmin)
site.register(Document, DocumentAdmin)
site.register(DocumentVersion, DocumentVersionAdmin)
site.register(Job, JobAdmin)
site.register(OutboxEvent, OutboxAdmin)
site.register(KnowledgeEntry, KnowledgeAdmin)
site.register(BidVersion, BidVersionAdmin)
site.register(BidSection, BidSectionAdmin)
