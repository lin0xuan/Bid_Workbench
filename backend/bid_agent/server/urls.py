"""HTTP routes. Operation bodies stay in the existing route modules."""
from django.contrib.staticfiles.views import serve
from django.http import HttpResponse, JsonResponse
from django.urls import path, re_path

from bid_agent.api.routes import (
    assets,
    auth,
    bids,
    documents,
    health,
    integrations,
    knowledge,
    projects,
    requirements,
    responses,
    retrieval,
    reviews,
    stages,
    workspace,
)
from bid_agent.core.settings import BUILD_VERSION
from bid_agent.server.admin import site
from bid_agent.server.dispatch import iter_routes, patterns_for

_ROUTERS = (
    (health.router, 'public'),
    (auth.router, 'public'),
    (workspace.router, 'user'),
    (requirements.router, 'user'),
    (stages.router, 'user'),
    (bids.router, 'user'),
    (responses.router, 'user'),
    (reviews.router, 'user'),
    (assets.router, 'user'),
    (retrieval.router, 'user'),
    (integrations.router, 'user'),
    (documents.router, 'legacy'),
    (projects.router, 'legacy'),
    (knowledge.router, 'legacy'),
)


def openapi_document():
    """Path inventory used by the existing contract test."""
    paths = {}
    for router, _access in _ROUTERS:
        for route in iter_routes(router):
            methods = paths.setdefault(route.path, {})
            for method in route.methods:
                if method not in {'HEAD', 'OPTIONS'}:
                    methods[method.lower()] = {
                        'operationId': route.endpoint.__name__,
                    }
    return {
        'openapi': '3.1.0',
        'info': {'title': 'Bid Agent', 'version': BUILD_VERSION},
        'paths': paths,
    }


def schema_view(_request):
    return JsonResponse(openapi_document())


def static_file(request, path):
    return serve(request, path, insecure=True)


def docs_view(_request):
    body = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<title>接口说明</title></head><body>'
        '<h1>接口说明</h1>'
        '<p>机器可读清单见 <a href="openapi.json">openapi.json</a>。</p>'
        '</body></html>'
    )
    return HttpResponse(body)


urlpatterns = [
    path('admin/', site.urls),
    path('openapi.json', schema_view, name='openapi'),
    path('docs', docs_view, name='docs'),
]
for router, access in _ROUTERS:
    urlpatterns.extend(patterns_for(router, access))
urlpatterns.append(re_path(r'^static/(?P<path>.*)$', static_file, name='static'))
