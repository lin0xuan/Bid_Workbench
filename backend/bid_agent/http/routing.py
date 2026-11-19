"""Small routing helpers so operation modules do not import another web framework."""
from bid_agent.core.errors import ApiError


class _Marker:
    def __init__(self, default=..., **options):
        self.default = default
        self.alias = options.get('alias')
        self.convert_underscores = options.get('convert_underscores', True)
        self.ge = options.get('ge')
        self.le = options.get('le')
        self.min_length = options.get('min_length')
        self.max_length = options.get('max_length')


class Depends:
    def __init__(self, dependency=None, *, use_cache=True):
        self.dependency = dependency
        self.use_cache = use_cache


class Form(_Marker):
    """Form field. ``File`` is checked first because it is a form upload."""


class File(Form):
    """Required upload unless a default is given."""


class Query(_Marker):
    """Query-string field."""


class Header(_Marker):
    """Header field. Underscores in the name match hyphens."""


class Path(_Marker):
    """Path field. The URL converter supplies the value."""


class UploadFile:
    """Structural stand-in for an uploaded file annotation."""


class Request:
    """Annotation for the adapted request object."""


class Response:
    """Mutable response side channel for cookies, status and headers."""

    def __init__(self, content=b'', status_code=200, headers=None, media_type=None):
        self.status_code = status_code
        self.media_type = media_type
        self.raw_headers = []
        self.headers = _HeaderMap(self)
        if headers:
            for key, value in headers.items():
                self.headers[key] = value
        self.body = content

    def set_cookie(
        self,
        key,
        value='',
        max_age=None,
        path='/',
        secure=False,
        httponly=False,
        samesite='lax',
    ):
        parts = [f'{key}={value}']
        if max_age is not None:
            parts.append(f'Max-Age={int(max_age)}')
        if path:
            parts.append(f'Path={path}')
        if secure:
            parts.append('Secure')
        if httponly:
            parts.append('HttpOnly')
        if samesite:
            parts.append(f'SameSite={samesite}')
        self.raw_headers.append(('set-cookie'.encode(), '; '.join(parts).encode()))

    def delete_cookie(self, key, path='/'):
        self.set_cookie(key, '', max_age=0, path=path)


class _HeaderMap(dict):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        encoded = str(key).lower().encode('latin-1')
        kept = [item for item in self.owner.raw_headers if item[0].lower() != encoded]
        kept.append((str(key).encode('latin-1'), str(value).encode('latin-1')))
        self.owner.raw_headers = kept


class FileResponse:
    def __init__(self, path, *, filename=None, media_type=None, headers=None):
        self.path = path
        self.filename = filename
        self.media_type = media_type or 'application/octet-stream'
        self.raw_headers = []
        if filename:
            self.raw_headers.append((
                b'content-disposition',
                f'attachment; filename="{filename}"'.encode('latin-1', 'replace'),
            ))
        if headers:
            for key, value in headers.items():
                self.raw_headers.append((str(key).encode('latin-1'), str(value).encode('latin-1')))


class StreamingResponse:
    def __init__(self, content, *, media_type=None, headers=None):
        self.body_iterator = content
        self.media_type = media_type or 'text/plain'
        self.raw_headers = []
        if headers:
            for key, value in headers.items():
                self.raw_headers.append((str(key).encode('latin-1'), str(value).encode('latin-1')))


class Route:
    def __init__(self, path, methods, endpoint, status_code):
        self.path = path
        self.methods = methods
        self.endpoint = endpoint
        self.status_code = status_code


class APIRouter:
    """Collect operation callables. Django URLconf is what serves them."""

    def __init__(self, prefix='', tags=None):
        self.prefix = prefix or ''
        self.tags = tags or []
        self.routes = []

    def get(self, path, **options):
        return self._decorate('GET', path, options)

    def post(self, path, **options):
        return self._decorate('POST', path, options)

    def put(self, path, **options):
        return self._decorate('PUT', path, options)

    def patch(self, path, **options):
        return self._decorate('PATCH', path, options)

    def delete(self, path, **options):
        return self._decorate('DELETE', path, options)

    def _decorate(self, method, path, options):
        status_code = options.get('status_code') or 200

        def decorator(func):
            self.routes.append(Route(_join(self.prefix, path), {method}, func, status_code))
            return func

        return decorator


def _join(prefix, path):
    if not path.startswith('/'):
        path = '/' + path
    prefix = (prefix or '').rstrip('/')
    if prefix and not prefix.startswith('/'):
        prefix = '/' + prefix
    return f'{prefix}{path}' if prefix else path


__all__ = [
    'APIRouter',
    'ApiError',
    'Depends',
    'File',
    'FileResponse',
    'Form',
    'Header',
    'Path',
    'Query',
    'Request',
    'Response',
    'StreamingResponse',
    'UploadFile',
]
