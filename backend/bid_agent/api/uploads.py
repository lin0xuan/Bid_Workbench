"""Bounded uploads shared by sync and streaming endpoints."""
from bid_agent.core.errors import ApiError
from bid_agent.core.settings import ALLOW_SERVER_PATHS, MAX_UPLOAD_BYTES


def validate_output_dir(output_dir: str | None) -> None:
    if output_dir and not ALLOW_SERVER_PATHS:
        raise ApiError(status_code=422, detail='Server output paths are disabled; omit output_dir.')


def read_upload(file) -> bytes:
    return _validate_content(file.file.read(MAX_UPLOAD_BYTES + 1))


async def read_upload_async(file) -> bytes:
    return _validate_content(await file.read(MAX_UPLOAD_BYTES + 1))


def _validate_content(content: bytes) -> bytes:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ApiError(status_code=413, detail='File exceeds BID_MAX_UPLOAD_MB')
    if not content:
        raise ApiError(status_code=422, detail='The uploaded file is empty')
    return content
