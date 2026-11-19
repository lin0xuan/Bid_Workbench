"""Domain errors raised by services and translated at the HTTP boundary."""


class ApiError(Exception):
    """Status and detail carried to the client without a web-framework type."""

    def __init__(self, status_code, detail=None, **kwargs):
        if detail is None and 'detail' in kwargs:
            detail = kwargs.pop('detail')
        if kwargs:
            unknown = ', '.join(kwargs)
            raise TypeError(f'Unexpected arguments: {unknown}')
        self.status_code = status_code
        self.detail = detail
        message = detail if isinstance(detail, str) else str(status_code)
        super().__init__(message)
