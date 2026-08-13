"""Regression tests for bounded multipart upload reads."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest
from starlette.formparsers import MultiPartParser

from app.core.exceptions import ValidationAppError
from app.core import uploads
from app.core.uploads import UploadBodyLimitMiddleware, read_limited_upload
from app.main import create_app
from app.services import drive_service
from tests.conftest import API


class _RecordingUpload:
    def __init__(self, payload: bytes) -> None:
        self._stream = io.BytesIO(payload)
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self._stream.read(size)

    @property
    def consumed(self) -> int:
        return self._stream.tell()


def test_limited_upload_reader_uses_only_bounded_reads_at_exact_limit():
    upload = _RecordingUpload(b"0123456789")

    data = asyncio.run(
        read_limited_upload(
            upload,  # type: ignore[arg-type] - minimal UploadFile test double
            max_bytes=10,
            chunk_bytes=4,
            too_large_message="too large",
        )
    )

    assert data == b"0123456789"
    assert upload.read_sizes
    assert all(0 < size <= 4 for size in upload.read_sizes)


def test_limited_upload_reader_stops_after_one_byte_over_limit():
    upload = _RecordingUpload(b"x" * 100)

    with pytest.raises(ValidationAppError, match="too large"):
        asyncio.run(
            read_limited_upload(
                upload,  # type: ignore[arg-type] - minimal UploadFile test double
                max_bytes=10,
                chunk_bytes=4,
                too_large_message="too large",
            )
        )

    assert upload.consumed == 11
    assert upload.read_sizes == [4, 4, 3]


def test_drive_router_streams_chunks_without_limited_reader(auth_client, monkeypatch, tmp_path):
    monkeypatch.setattr(drive_service, "MAX_FILE_BYTES", 10)
    # If the old materializing helper is accidentally wired back in, fail loudly.
    import app.core.uploads as uploads
    monkeypatch.setattr(
        uploads,
        "read_limited_upload",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must stream")),
    )

    response = auth_client.post(
        f"{API}/drive/files",
        files={"file": ("streamed.txt", b"0123456789", "text/plain")},
    )

    assert response.status_code == 200, response.text
    row = response.json()["data"]
    assert row["size_bytes"] == 10


def test_drive_oversize_stream_removes_partial_temp_file(auth_client, monkeypatch, tmp_path):
    monkeypatch.setattr(drive_service, "MAX_FILE_BYTES", 10)
    monkeypatch.setattr(drive_service.settings, "DRIVE_STORAGE_DIR", str(tmp_path))

    response = auth_client.post(
        f"{API}/drive/files",
        files={"file": ("too-large.bin", b"x" * 100, "application/octet-stream")},
    )

    assert response.status_code == 422, response.text
    assert list(Path(tmp_path).rglob("*.uploading")) == []
    assert auth_client.get(f"{API}/drive/files").json()["data"] == []


def test_declared_oversize_is_rejected_before_multipart_parser(auth_client, monkeypatch):
    """A large file must never reach Starlette's disk-spooling parser."""
    monkeypatch.setattr(uploads.settings, "KNOWLEDGE_MAX_UPLOAD_MB", 1)
    parser_called = False

    async def forbidden_parse(_self):
        nonlocal parser_called
        parser_called = True
        raise AssertionError("multipart parser must not run")

    monkeypatch.setattr(MultiPartParser, "parse", forbidden_parse)
    response = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("oversize.bin", b"x" * (2 * 1024 * 1024), "application/octet-stream")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert parser_called is False


def test_chunked_oversize_stops_receiving_before_complete_body(monkeypatch):
    """Omitting Content-Length must not bypass the pre-parser request ceiling."""
    monkeypatch.setattr(uploads.settings, "KNOWLEDGE_MAX_UPLOAD_MB", 1)
    chunk = b"x" * (256 * 1024)
    request_messages = [
        {"type": "http.request", "body": chunk, "more_body": index < 7}
        for index in range(8)
    ]
    receive_calls = 0
    sent: list[dict] = []

    async def inner(_scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def run_request():
        nonlocal receive_calls

        async def receive():
            nonlocal receive_calls
            message = request_messages[receive_calls]
            receive_calls += 1
            return message

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": f"{API}/ai/knowledge/documents",
            "raw_path": f"{API}/ai/knowledge/documents".encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
        await UploadBodyLimitMiddleware(inner)(scope, receive, send)

    asyncio.run(run_request())

    assert receive_calls < len(request_messages)
    assert sent[0]["status"] == 413


def test_chunked_oversize_through_fastapi_returns_413_and_stops_early(monkeypatch):
    """FastAPI must not translate the receive guard into its generic body-parser 400."""
    monkeypatch.setattr(uploads.settings, "KNOWLEDGE_MAX_UPLOAD_MB", 1)
    boundary = b"allhaven-gate-boundary"
    body = (
        b"--" + boundary
        + b'\r\nContent-Disposition: form-data; name="file"; filename="oversize.bin"'
        + b"\r\nContent-Type: application/octet-stream\r\n\r\n"
        + b"x" * (2 * 1024 * 1024)
        + b"\r\n--" + boundary + b"--\r\n"
    )
    chunks = [body[index:index + 256 * 1024] for index in range(0, len(body), 256 * 1024)]
    receive_calls = 0
    sent: list[dict] = []

    async def run_request():
        nonlocal receive_calls

        async def receive():
            nonlocal receive_calls
            if receive_calls >= len(chunks):
                return {"type": "http.disconnect"}
            index = receive_calls
            receive_calls += 1
            return {
                "type": "http.request",
                "body": chunks[index],
                "more_body": index < len(chunks) - 1,
            }

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": f"{API}/ai/knowledge/documents",
            "raw_path": f"{API}/ai/knowledge/documents".encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"multipart/form-data; boundary=" + boundary),
            ],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
            "state": {},
        }
        await create_app()(scope, receive, send)

    asyncio.run(run_request())

    starts = [message for message in sent if message["type"] == "http.response.start"]
    assert len(starts) == 1
    assert starts[0]["status"] == 413
    headers = {key.decode().lower(): value.decode() for key, value in starts[0]["headers"]}
    assert headers["x-content-type-options"] == "nosniff"
    payload = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    assert json.loads(payload)["error_code"] == "PAYLOAD_TOO_LARGE"
    assert receive_calls < len(chunks)
