"""JSON error bodies that keep the existing status-code contract."""
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Render framework errors as ``{"detail": ...}``."""
    if isinstance(exc, ParseError):
        return Response({'detail': 'JSON 无法解析'}, status=422)
    if isinstance(exc, ValidationError):
        return Response({'detail': exc.detail}, status=422)
    response = exception_handler(exc, context)
    if response is None:
        return None
    detail = response.data.get('detail', response.data)
    return Response({'detail': detail}, status=response.status_code)
