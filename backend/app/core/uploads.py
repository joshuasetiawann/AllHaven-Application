"""Bounded helpers and ASGI request limits for multipart uploads."""

from __future__ import annotations

from typing import BinaryIO

from fastapi import UploadFile
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.core.responses import error_response

UPLOAD_READ_CHUNK_BYTES = 64 * 1024
# Multipart boundaries and part headers are small but count toward the HTTP body.
# Keep a fixed allowance while still rejecting oversized files *before* Starlette
# spools the whole part to disk. Chunked requests are stopped at the same ceiling.
MULTIPART_ENVELOPE_BYTES = 64 * 1024


class _RequestBodyTooLarge(Exception):
    """Internal control-flow exception raised by the bounded ASGI receiver."""


def upload_request_limit(path: str) -> tuple[int, str] | None:
    """Return the total multipart-body ceiling for a protected upload route."""
    prefix = settings.API_V1_PREFIX.rstrip("/")
    if path == f"{prefix}/drive/files":
        file_bytes = max(1, int(settings.DRIVE_MAX_UPLOAD_MB)) * 1024 * 1024
        message = f"Drive upload request exceeds the {settings.DRIVE_MAX_UPLOAD_MB} MB file limit."
    elif path == f"{prefix}/ai/knowledge/documents":
        file_bytes = max(1, int(settings.KNOWLEDGE_MAX_UPLOAD_MB)) * 1024 * 1024
        message = (
            "Knowledge upload request exceeds the "
            f"{settings.KNOWLEDGE_MAX_UPLOAD_MB} MB file limit."
        )
    else:
        return None
    return file_bytes + MULTIPART_ENVELOPE_BYTES, message


class UploadBodyLimitMiddleware:
    """Reject oversized upload bodies before multipart parsing/spooling.

    ``UploadFile`` parsing happens before an endpoint is invoked. Endpoint-only
    checks therefore cannot prevent an attacker from making Starlette receive
    and spool the complete request. This pure ASGI middleware rejects declared
    oversized bodies immediately and also wraps ``receive`` so chunked bodies
    cannot bypass the ceiling by omitting ``Content-Length``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, message: str) -> None:
        response = JSONResponse(
            status_code=413,
            content=error_response("PAYLOAD_TOO_LARGE", message),
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        rule = upload_request_limit(scope.get("path", ""))
        if rule is None:
            await self.app(scope, receive, send)
            return
        max_body_bytes, message = rule

        content_length = Headers(scope=scope).get("content-length")
        if content_length:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                declared_bytes = -1
            if declared_bytes > max_body_bytes:
                await self._reject(scope, receive, send, message)
                return

        received_bytes = 0
        response_started = False
        body_too_large = False

        async def limited_receive() -> Message:
            nonlocal received_bytes, body_too_large
            # Once the ceiling is crossed, never pull another chunk from the
            # server.  FastAPI's multipart dependency parser catches ordinary
            # receive exceptions and turns them into a generic 400, so the
            # outer ASGI layer below also uses this flag to replace that
            # swallowed parser response with the intended 413.
            if body_too_large:
                raise _RequestBodyTooLarge
            request_message = await receive()
            if request_message["type"] == "http.request":
                received_bytes += len(request_message.get("body", b""))
                if received_bytes > max_body_bytes:
                    body_too_large = True
                    raise _RequestBodyTooLarge
            return request_message

        async def tracking_send(response_message: Message) -> None:
            nonlocal response_started
            # FastAPI catches exceptions raised while parsing multipart form
            # data and emits a 400 response from inside the router stack.  Do
            # not leak that misleading response after limited_receive has
            # positively identified an oversized body; __call__ emits the
            # canonical 413 once the inner app unwinds.
            if body_too_large:
                return
            if response_message["type"] == "http.response.start":
                response_started = True
            await send(response_message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _RequestBodyTooLarge:
            # Multipart parsing occurs before these endpoints start a response.
            # Keep the guard explicit so a future streaming endpoint cannot emit
            # two response starts if it reads more request data late.
            if response_started:
                raise
            body_too_large = True

        if body_too_large:
            if response_started:
                raise _RequestBodyTooLarge
            await self._reject(scope, receive, send, message)


async def read_limited_upload(
    file: UploadFile,
    *,
    max_bytes: int,
    too_large_message: str,
    chunk_bytes: int = UPLOAD_READ_CHUNK_BYTES,
) -> bytes:
    """Read an upload without ever issuing an unbounded ``read()`` call.

    At most ``max_bytes`` are retained. Once that many bytes have been read, a
    one-byte, still-bounded probe distinguishes an exact-limit upload from an
    oversized one without consuming the rest of the request body into memory.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if chunk_bytes < 1:
        raise ValueError("chunk_bytes must be positive")

    data = bytearray()
    while True:
        read_size = min(chunk_bytes, max_bytes - len(data) + 1)
        chunk = await file.read(read_size)
        if not chunk:
            return bytes(data)
        if len(data) + len(chunk) > max_bytes:
            raise ValidationAppError(too_large_message)
        data.extend(chunk)


def read_limited_fileobj(
    stream: BinaryIO,
    *,
    max_bytes: int,
    too_large_message: str,
    chunk_bytes: int = UPLOAD_READ_CHUNK_BYTES,
) -> bytes:
    """Synchronous bounded reader for endpoints running in a worker thread."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if chunk_bytes < 1:
        raise ValueError("chunk_bytes must be positive")
    data = bytearray()
    while True:
        read_size = min(chunk_bytes, max_bytes - len(data) + 1)
        chunk = stream.read(read_size)
        if not chunk:
            return bytes(data)
        if len(data) + len(chunk) > max_bytes:
            raise ValidationAppError(too_large_message)
        data.extend(chunk)
