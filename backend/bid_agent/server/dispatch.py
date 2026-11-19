"""Call the existing operation functions from HTTP views."""
import inspect
import json
import types
from typing import Union, get_args, get_origin

from bid_agent.core.errors import ApiError
from bid_agent.http.routing import (
    Depends,
    File,
    FileResponse,
    Form,
    Header,
    Path,
    Query,
    Response as SideResponse,
    Route,
    StreamingResponse,
)
from pydantic import BaseModel, ValidationError
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bid_agent.core.security import current_user, legacy_admin
from bid_agent.repositories.platform import ConflictError, ForbiddenError, NotFoundError
from bid_agent.server.authentication import WorkspaceAuthentication
from bid_agent.server.permissions import IsLegacyAdmin, ProjectObjectPermission
from bid_agent.server.runtime import AdaptedRequest, principal_of
from bid_agent.server.serializers import serializer_for

_MISSING_NAMES = {'undefined', 'undefinedtype', 'pydanticundefined', 'unset'}


class UploadedFile:
    """File object accepted by the existing upload helpers."""

    def __init__(self, uploaded):
        self.filename = uploaded.name
        self.file = uploaded
        self._uploaded = uploaded

    async def read(self, size=-1):
        return self._uploaded.read(size)


def iter_routes(router):
    """Yield concrete HTTP routes, skipping automatic head and options."""
    for route in router.routes:
        if isinstance(route, Route):
            yield route


def django_path(path):
    """Convert ``{name}`` path templates to Django converters."""
    parts = path.strip('/').split('/')
    converted = []
    for part in parts:
        if part.startswith('{') and part.endswith('}'):
            converted.append(f'<str:{part[1:-1]}>')
        else:
            converted.append(part)
    return converted


def _is_missing(value):
    if value is inspect.Signature.empty or value is Ellipsis:
        return True
    return type(value).__name__.lower() in _MISSING_NAMES


def _marker_default(marker):
    default = getattr(marker, 'default', inspect.Signature.empty)
    if _is_missing(default):
        return inspect.Signature.empty
    return default


def _alias(marker, name):
    alias = getattr(marker, 'alias', None)
    if isinstance(alias, str) and alias:
        return alias
    if isinstance(marker, Header) and getattr(marker, 'convert_underscores', True):
        return name.replace('_', '-')
    return name


def _model_type(annotation):
    if annotation is inspect.Signature.empty:
        return None, False
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation, False
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [item for item in get_args(annotation) if item is not type(None)]
        optional = len(args) != len(get_args(annotation))
        model = args[0] if len(args) == 1 else None
        if isinstance(model, type) and issubclass(model, BaseModel):
            return model, optional
    return None, False


def _django_http(request):
    return getattr(request, '_request', request)


def _body_present(request):
    return bool(_django_http(request).body)


def _parse_model(model, request, optional):
    if optional and not _body_present(request):
        return None
    data = request.data if request.data not in (None, '') else {}
    serializer = serializer_for(model)(data=data)
    if not serializer.is_valid():
        detail = serializer.errors.get('detail', serializer.errors)
        raise ApiError(422, detail)
    return serializer.validated_data


def _coerce(annotation, value, marker):
    if annotation is bool or _is_optional(annotation, bool):
        if isinstance(value, bool):
            coerced = value
        else:
            text = str(value).strip().lower()
            if text in {'1', 'true', 'yes', 'on'}:
                coerced = True
            elif text in {'0', 'false', 'no', 'off', ''}:
                coerced = False
            else:
                raise ValidationError.from_exception_data(
                    'bool',
                    [{'type': 'bool_parsing', 'loc': (), 'input': value}],
                )
    elif annotation is int or _is_optional(annotation, int):
        coerced = int(value)
    elif annotation is not inspect.Signature.empty:
        from pydantic import TypeAdapter
        coerced = TypeAdapter(annotation).validate_python(value)
    else:
        coerced = value
    _check_bounds(marker, coerced)
    return coerced


def _is_optional(annotation, expected):
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [item for item in get_args(annotation) if item is not type(None)]
        return args == [expected]
    return False


def _check_bounds(marker, value):
    if marker is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    ge_value = getattr(marker, 'ge', None)
    le_value = getattr(marker, 'le', None)
    if ge_value is not None and value < ge_value:
        raise ValidationError.from_exception_data(
            'number',
            [{'type': 'greater_than_equal', 'loc': (), 'input': value}],
        )
    if le_value is not None and value > le_value:
        raise ValidationError.from_exception_data(
            'number',
            [{'type': 'less_than_equal', 'loc': (), 'input': value}],
        )


def _uploaded(request, name):
    uploaded = _django_http(request).FILES.get(name)
    if uploaded is None:
        raise ApiError(422, '缺少上传文件')
    return UploadedFile(uploaded)


def _form_value(request, name, marker, annotation):
    default = _marker_default(marker)
    raw = _django_http(request).POST.get(name)
    if raw is None:
        if default is inspect.Signature.empty:
            raise ApiError(422, f'缺少字段 {name}')
        return default
    return _coerce(annotation, raw, marker)


def _query_value(request, name, marker, annotation):
    default = _marker_default(marker) if marker is not None else inspect.Signature.empty
    raw = request.query_params.get(name)
    if raw is None:
        if default is inspect.Signature.empty:
            return None
        return default
    return _coerce(annotation, raw, marker)


def _header_value(request, name, marker, annotation):
    default = _marker_default(marker)
    raw = request.headers.get(_alias(marker, name))
    if raw in (None, ''):
        if default is inspect.Signature.empty:
            raise ApiError(422, f'缺少请求头 {_alias(marker, name)}')
        return default
    return _coerce(annotation, raw, marker)


def _dependency_value(request, marker):
    dependency = marker.dependency
    if dependency is current_user:
        return principal_of(request.user)
    if dependency is legacy_admin:
        principal = principal_of(request.user)
        if principal is None or not principal.is_admin:
            raise ApiError(403, '旧版接口仅供管理员使用，请使用文档工作台')
        return principal
    return dependency(AdaptedRequest(request))


def call_endpoint(route, request, path_params):
    """Build arguments, call one operation, and return its raw result."""
    side = SideResponse()
    side.status_code = route.status_code or 200
    kwargs = {}
    signature = inspect.signature(route.endpoint)
    for name, param in signature.parameters.items():
        default = param.default
        annotation = param.annotation
        if name in path_params:
            kwargs[name] = path_params[name]
            continue
        model, optional = _model_type(annotation)
        body_marker = (Form, File, Query, Header, Path)
        if model is not None and not isinstance(default, body_marker):
            kwargs[name] = _parse_model(model, request, optional)
            continue
        if name == 'response':
            kwargs[name] = side
            continue
        if name == 'request':
            kwargs[name] = AdaptedRequest(request)
            continue
        if isinstance(default, Depends):
            kwargs[name] = _dependency_value(request, default)
            continue
        upload_name = getattr(annotation, '__name__', '')
        if isinstance(default, File) or upload_name == 'UploadFile':
            kwargs[name] = _uploaded(request, name)
            continue
        if isinstance(default, Form):
            kwargs[name] = _form_value(request, name, default, annotation)
            continue
        if isinstance(default, Header):
            kwargs[name] = _header_value(request, name, default, annotation)
            continue
        if isinstance(default, (Query, Path)) or name in request.query_params:
            marker = default if isinstance(default, Query) else None
            kwargs[name] = _query_value(request, name, marker, annotation)
            continue
        if default is not inspect.Signature.empty:
            kwargs[name] = default
    if inspect.iscoroutinefunction(route.endpoint):
        from asgiref.sync import async_to_sync
        result = async_to_sync(route.endpoint)(**kwargs)
    else:
        result = route.endpoint(**kwargs)
    return result, side


def _copy_side_effects(target, source):
    for key, value in source.raw_headers:
        lowered = key.lower()
        if lowered in {b'content-type', b'content-length'}:
            continue
        if lowered == b'set-cookie':
            _copy_cookie(target, value.decode('latin-1'))
            continue
        target[key.decode('latin-1')] = value.decode('latin-1')


def _cookie_age(max_age):
    if isinstance(max_age, str) and max_age.lstrip('-').isdigit():
        return int(max_age)
    return None


def _copy_cookie(target, raw):
    pieces = [part.strip() for part in raw.split(';')]
    name, value = pieces[0].split('=', 1)
    flags = {}
    for piece in pieces[1:]:
        if '=' in piece:
            flag, flag_value = piece.split('=', 1)
            flags[flag.lower()] = flag_value
        else:
            flags[piece.lower()] = True
    max_age = flags.get('max-age')
    same_site = str(flags.get('samesite') or 'Lax')
    target.set_cookie(
        name,
        value.strip('"'),
        max_age=_cookie_age(max_age),
        path=flags.get('path') or '/',
        secure=bool(flags.get('secure')),
        httponly=bool(flags.get('httponly')),
        samesite=same_site[:1].upper() + same_site[1:].lower(),
    )


def _stream(result):
    from asgiref.sync import async_to_sync
    from django.http import StreamingHttpResponse

    async_iter = result.body_iterator.__aiter__()

    def chunks():
        while True:
            try:
                chunk = async_to_sync(async_iter.__anext__)()
            except StopAsyncIteration:
                break
            yield chunk.encode('utf-8') if isinstance(chunk, str) else chunk

    response = StreamingHttpResponse(chunks(), content_type=result.media_type)
    _copy_side_effects(response, result)
    return response


def _file(result):
    from django.http import HttpResponse

    with open(result.path, 'rb') as handle:
        payload = handle.read()
    response = HttpResponse(payload, content_type=result.media_type)
    _copy_side_effects(response, result)
    return response


def render_result(result, side):
    """Convert an operation result into an HTTP response."""
    if isinstance(result, StreamingResponse):
        return _stream(result)
    if isinstance(result, FileResponse):
        return _file(result)
    if isinstance(result, BaseModel):
        payload = result.model_dump(mode='json')
    else:
        payload = result
    response = Response(payload, status=side.status_code)
    _copy_side_effects(response, side)
    return response


def perform(route, request, path_params):
    """Run one operation and map domain errors onto the public contract."""
    try:
        result, side = call_endpoint(route, request, path_params)
    except ApiError as exc:
        return Response({'detail': exc.detail}, status=exc.status_code)
    except ApiValidationError as exc:
        return Response({'detail': exc.detail}, status=422)
    except ValidationError as exc:
        return Response({'detail': json.loads(exc.json())}, status=422)
    except NotFoundError as exc:
        return Response({'detail': str(exc)}, status=404)
    except ForbiddenError as exc:
        return Response({'detail': str(exc)}, status=403)
    except ConflictError as exc:
        return Response({'detail': str(exc)}, status=409)
    return render_result(result, side)


def _access_rank(route, default):
    for param in inspect.signature(route.endpoint).parameters.values():
        dependency = getattr(param.default, 'dependency', None)
        if dependency is legacy_admin:
            return 'legacy'
        if dependency is current_user:
            return 'user'
    return default


def _view_class(path, routes, access):
    by_method = {}
    for route in routes:
        for method in route.methods:
            if method not in {'HEAD', 'OPTIONS'}:
                by_method[method.lower()] = route
    auth = [] if access == 'public' else [WorkspaceAuthentication]
    if access == 'public':
        permissions = [AllowAny]
    elif access == 'legacy':
        permissions = [IsLegacyAdmin]
    else:
        permissions = [ProjectObjectPermission]

    class BoundView(APIView):
        authentication_classes = auth
        permission_classes = permissions

        def finalize_response(self, request, response, *args, **kwargs):
            from django.http import HttpResponseBase

            plain = isinstance(response, HttpResponseBase)
            if plain and not isinstance(response, Response):
                return response
            return super().finalize_response(request, response, *args, **kwargs)

    label = path.strip('/').replace('/', '_').replace('{', '').replace('}', '')
    BoundView.__name__ = 'View_' + label
    BoundView.__qualname__ = BoundView.__name__
    for method_name, route in by_method.items():
        def handler(self, request, _route=route, **kwargs):
            return perform(_route, request, kwargs)

        handler.__name__ = method_name
        setattr(BoundView, method_name, handler)
    return BoundView


def patterns_for(router, access):
    """Group routes that share a path and return Django URL fragments."""
    from django.urls import path as url_path

    grouped = {}
    order = []
    for route in iter_routes(router):
        if route.path not in grouped:
            grouped[route.path] = []
            order.append(route.path)
        grouped[route.path].append(route)
    patterns = []
    for route_path in order:
        routes = grouped[route_path]
        ranks = [_access_rank(route, access) for route in routes]
        chosen = max(ranks, key=['public', 'user', 'legacy'].index)
        view = _view_class(route_path, routes, chosen)
        route_name = routes[0].endpoint.__name__
        patterns.append(url_path(
            '/'.join(django_path(route_path)),
            view.as_view(),
            name=route_name,
        ))
    return patterns
