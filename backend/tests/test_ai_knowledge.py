"""AI Knowledge ingestion/search and related AI workspace plumbing."""

import io
import uuid
import zlib
import zipfile

import pytest

from app.core.principal import Principal
from app.domain.ai import AiToolCall
from app.services import ai_tools_registry, knowledge_service
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_ai_knowledge_upload_indexes_txt_and_searches(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("allhaven.txt", b"AllHaven is a private AI workspace created for desktop-first users.", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"
    assert doc["chunk_count"] >= 1

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "private AI workspace"})
    assert search.status_code == 200, search.text
    results = search.json()["data"]["results"]
    assert results
    assert "private AI workspace" in results[0]["content"]


def test_ai_knowledge_rejects_oversized_upload_before_ingestion(auth_client, monkeypatch):
    monkeypatch.setattr(knowledge_service, "upload_limit_bytes", lambda: 10)

    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("too-large.txt", b"0123456789ABCDEF", "text/plain")},
    )

    assert resp.status_code == 422, resp.text
    assert "upload limit" in resp.json()["message"]
    listed = auth_client.get(f"{API}/ai/knowledge/documents")
    assert listed.status_code == 200
    assert listed.json()["data"] == []


def test_ai_knowledge_stores_unsupported_file_as_metadata_only(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("source.bin", b"\x00\x01", "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    assert doc["chunk_count"] == 1
    assert doc["meta"]["metadata_only"] is True
    assert doc["meta"]["indexable"] is False
    assert doc["error_message"]

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "source.bin"})
    assert search.status_code == 200, search.text
    results = search.json()["data"]["results"]
    assert results
    assert results[0]["document_filename"] == "source.bin"


def test_ai_knowledge_upload_indexes_simple_pdf(auth_client):
    pdf = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Contents 4 0 R>> endobj
4 0 obj <</Length 64>> stream
BT /F1 12 Tf 72 720 Td (AllHaven PDF routine finance knowledge) Tj ET
endstream endobj
trailer <</Root 1 0 R>>
%%EOF
"""
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("planning.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "routine finance knowledge"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


def test_ai_knowledge_upload_indexes_docx(auth_client):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>AllHaven DOCX schedule and coding plan</w:t></w:r></w:p></w:body>
            </w:document>
            """,
        )
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={
            "file": (
                "plan.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "schedule coding plan"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


def test_pypdf_valid_page_tree_still_extracts_text(monkeypatch):
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 12 Tf 10 100 Td (bounded pypdf extraction works) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(contents)
    output = io.BytesIO()
    writer.write(output)

    def unexpected_fallback(_data):
        pytest.fail("a valid PDF should be extracted by pypdf, not the fallback")

    monkeypatch.setattr(knowledge_service, "_simple_pdf_extract", unexpected_fallback)
    text, note = knowledge_service._extract_pdf(output.getvalue())

    assert note is None
    assert "bounded pypdf extraction works" in (text or "")


def test_pdf_page_tree_preflight_rejects_compact_repeated_kids_with_bounded_work(
    monkeypatch,
):
    """A tiny graph representing 2**80 paths must be rejected before flattening."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    child = writer._add_object(
        DictionaryObject({NameObject("/Type"): NameObject("/Page")})
    )
    for _ in range(80):
        child = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Pages"),
                    NameObject("/Kids"): ArrayObject([child, child]),
                    # Deliberately lie so /Count cannot be the only defense.
                    NameObject("/Count"): NumberObject(1),
                }
            )
        )
    writer._root_object[NameObject("/Pages")] = child
    output = io.BytesIO()
    writer.write(output)
    payload = output.getvalue()
    assert len(payload) < 10_000

    reader = PdfReader(io.BytesIO(payload))
    object_resolutions = 0
    original_get_object = reader.get_object

    def counted_get_object(indirect_reference):
        nonlocal object_resolutions
        object_resolutions += 1
        return original_get_object(indirect_reference)

    monkeypatch.setattr(reader, "get_object", counted_get_object)
    with pytest.raises(knowledge_service._UnsafePdfError, match="cyclic or shared"):
        knowledge_service._bounded_pdf_page_count(reader)

    # The duplicate references are identified without resolving every branch,
    # and pypdf's recursively populated page list is never created.
    assert object_resolutions <= 8
    assert reader.flattened_pages is None

    text, note = knowledge_service._extract_pdf(payload)
    assert text is None
    assert "page-tree traversal limits" in (note or "")


def test_pdf_page_tree_preflight_caps_depth_without_flattening():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    child = writer._add_object(
        DictionaryObject({NameObject("/Type"): NameObject("/Page")})
    )
    for _ in range(knowledge_service.PDF_MAX_PAGE_TREE_DEPTH + 1):
        child = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Pages"),
                    NameObject("/Kids"): ArrayObject([child]),
                    NameObject("/Count"): NumberObject(1),
                }
            )
        )
    writer._root_object[NameObject("/Pages")] = child
    output = io.BytesIO()
    writer.write(output)
    reader = PdfReader(io.BytesIO(output.getvalue()))

    with pytest.raises(knowledge_service._UnsafePdfError, match="depth"):
        knowledge_service._bounded_pdf_page_count(reader)
    assert reader.flattened_pages is None


def test_pdf_page_tree_preflight_caps_kids_before_flattening(monkeypatch):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    reader = PdfReader(io.BytesIO(output.getvalue()))
    monkeypatch.setattr(knowledge_service, "PDF_MAX_PAGE_TREE_KIDS", 4)

    with pytest.raises(knowledge_service._UnsafePdfError, match="fan-out"):
        knowledge_service._bounded_pdf_page_count(reader)
    assert reader.flattened_pages is None


def test_pdf_parser_caps_direct_kids_array_before_materializing_it(monkeypatch):
    """The parser itself must stop a huge direct array before page preflight."""
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, NameObject, NumberObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    page_ref = page.indirect_reference
    pages = writer._root_object.raw_get("/Pages").get_object()
    pages[NameObject("/Kids")] = ArrayObject([page_ref] * 50_000)
    # Deliberately lie so `/Count` alone cannot reject the object before `/Kids`
    # is parsed. The generated PDF has a valid xref/trailer.
    pages[NameObject("/Count")] = NumberObject(1)
    output = io.BytesIO()
    writer.write(output)
    payload = output.getvalue()
    monkeypatch.setattr(knowledge_service, "PDF_MAX_PARSED_ARRAY_ITEMS", 64)

    text, note = knowledge_service._extract_pdf(payload)

    assert text is None
    assert "page-tree traversal limits" in (note or "")


def test_pdf_parser_caps_array_items_across_nested_arrays(monkeypatch):
    """Many sub-limit arrays must still share one bounded parse budget."""
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    page_ref = page.indirect_reference
    pages = writer._root_object.raw_get("/Pages").get_object()
    pages[NameObject("/Junk")] = ArrayObject(
        [ArrayObject([page_ref] * 25) for _ in range(5)]
    )
    output = io.BytesIO()
    writer.write(output)
    monkeypatch.setattr(knowledge_service, "PDF_MAX_PARSED_ARRAY_ITEMS", 64)
    monkeypatch.setattr(knowledge_service, "PDF_MAX_TOTAL_PARSED_ARRAY_ITEMS", 100)

    text, note = knowledge_service._extract_pdf(output.getvalue())

    assert text is None
    assert "structural parsing" in (note or "")


def test_pypdf_enforces_aggregate_decoded_stream_budget(monkeypatch):
    """Individually safe streams must still share one document-wide ceiling."""
    from pypdf import PdfWriter
    from pypdf.generic import (
        DictionaryObject,
        EncodedStreamObject,
        NameObject,
    )

    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    expanded = b"BT /F1 12 Tf 10 10 Td (x) Tj ET %" + (b"A" * 768) + b"\n"
    packed = zlib.compress(expanded, 9)
    for _ in range(3):
        page = writer.add_blank_page(width=100, height=100)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_ref}
                )
            }
        )
        contents = EncodedStreamObject()
        # A PDF comment is harmless content but must still be decoded.
        contents._data = packed
        contents[NameObject("/Filter")] = NameObject("/FlateDecode")
        page[NameObject("/Contents")] = writer._add_object(contents)
    output = io.BytesIO()
    writer.write(output)
    monkeypatch.setattr(knowledge_service, "PDF_MAX_STREAM_EXPANDED_BYTES", 1024)
    monkeypatch.setattr(knowledge_service, "PDF_MAX_TOTAL_EXPANDED_BYTES", 1024)
    from pypdf import filters as pypdf_filters

    original_decode = pypdf_filters.decode_stream_data
    decode_calls = 0

    def counted_decode(stream):
        nonlocal decode_calls
        decode_calls += 1
        return original_decode(stream)

    monkeypatch.setattr(pypdf_filters, "decode_stream_data", counted_decode)

    text, note = knowledge_service._extract_pdf(output.getvalue())

    assert text is None
    assert "structural parsing" in (note or "")
    assert decode_calls == 2


@pytest.mark.parametrize(
    "limit_name",
    [
        "DOCX_MAX_XML_ENTRY_COMPRESSED_BYTES",
        "DOCX_MAX_XML_ENTRY_EXPANDED_BYTES",
    ],
)
def test_docx_extraction_enforces_per_entry_size_limits(monkeypatch, limit_name):
    xml = b"""
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>bounded DOCX content</w:t></w:r></w:p></w:body>
        </w:document>
    """
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", xml)
    monkeypatch.setattr(knowledge_service, limit_name, len(xml) - 1)

    text, note = knowledge_service._extract_docx(data.getvalue())

    assert text is None
    assert "safe extraction limits" in (note or "")


def test_docx_extraction_enforces_aggregate_expanded_size_limit(monkeypatch):
    document = b"""
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>document text</w:t></w:r></w:p></w:body>
        </w:document>
    """
    header = b"""
        <w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:p><w:r><w:t>header text</w:t></w:r></w:p>
        </w:hdr>
    """
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/header1.xml", header)
    monkeypatch.setattr(
        knowledge_service,
        "DOCX_MAX_XML_TOTAL_EXPANDED_BYTES",
        len(document) + len(header) - 1,
    )

    text, note = knowledge_service._extract_docx(data.getvalue())

    assert text is None
    assert "safe extraction limits" in (note or "")


def test_pdf_fallback_rejects_oversized_deflate_stream(monkeypatch):
    """The fallback must not inflate an attacker-controlled stream without a cap."""
    expanded = b"(should-not-be-expanded) Tj\n" * 10_000
    payload = b"%PDF-1.4\nstream\n" + zlib.compress(expanded) + b"\nendstream\n%%EOF"
    monkeypatch.setattr(knowledge_service, "PDF_MAX_STREAM_EXPANDED_BYTES", 1024)
    monkeypatch.setattr(knowledge_service, "PDF_MAX_TOTAL_EXPANDED_BYTES", 2048)

    with pytest.raises(knowledge_service._UnsafePdfError, match="stream limit"):
        knowledge_service._simple_pdf_extract(payload)


def test_pypdf_all_expanding_decoders_share_application_limit(monkeypatch):
    """RunLength/LZW/JBIG2 must not retain pypdf's much larger defaults."""
    from pypdf import filters as pypdf_filters
    from pypdf.errors import LimitReachedError

    monkeypatch.setattr(knowledge_service, "PDF_MAX_STREAM_EXPANDED_BYTES", 1024)
    # A malformed but parseable PDF is enough to execute the pypdf limit setup;
    # extraction then safely falls back to metadata-only handling.
    knowledge_service._extract_pdf(b"%PDF-1.4\n%%EOF")

    for limit_name in (
        "ZLIB_MAX_OUTPUT_LENGTH",
        "RUN_LENGTH_MAX_OUTPUT_LENGTH",
        "LZW_MAX_OUTPUT_LENGTH",
        "JBIG2_MAX_OUTPUT_LENGTH",
        "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
        "MAX_DECLARED_STREAM_LENGTH",
        "FLATE_MAX_BUFFER_SIZE",
    ):
        assert getattr(pypdf_filters, limit_name) == 1024

    # Nine 128-byte runs expand past the 1 KiB application ceiling.
    encoded = (bytes([129, ord("A")]) * 9) + bytes([128])
    with pytest.raises(LimitReachedError):
        pypdf_filters.RunLengthDecode.decode(encoded)


def test_ai_knowledge_stores_high_ratio_docx_as_metadata_only(auth_client, monkeypatch):
    xml = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body><w:p><w:r><w:t>"
        + (b"repeated-content " * 4096)
        + b"</w:t></w:r></w:p></w:body></w:document>"
    )
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    monkeypatch.setattr(knowledge_service, "DOCX_MAX_XML_COMPRESSION_RATIO", 2.0)

    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={
            "file": (
                "high-ratio.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    assert doc["meta"]["metadata_only"] is True
    assert "safe extraction limits" in doc["error_message"]


def test_ai_knowledge_rejects_malicious_docx_entity_expansion(auth_client):
    # A DOCX whose document.xml declares a DTD with an entity. defusedxml must
    # refuse the entity instead of expanding it (XXE / billion-laughs), so the
    # upload falls back to safe metadata-only storage rather than crashing.
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0"?>
            <!DOCTYPE w:document [
              <!ENTITY xxe SYSTEM "file:///etc/passwd">
              <!ENTITY lol "lololololololololol">
            ]>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>&xxe;&lol;</w:t></w:r></w:p></w:body>
            </w:document>
            """,
        )
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={
            "file": (
                "evil.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["meta"]["metadata_only"] is True
    assert doc["meta"]["indexable"] is False
    assert doc["error_message"]


def test_ai_knowledge_upload_indexes_legacy_doc_best_effort(auth_client):
    body = b"\xd0\xcf\x11\xe0" + b"\x00" * 20 + b"AllHaven legacy DOC finance routine readable text"
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("legacy.doc", body, "application/msword")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "legacy finance routine"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


def test_ai_knowledge_protects_secret_like_text_as_metadata_only(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("secrets.env", b"OPENAI_API_KEY=sk-abc123DEF456ghi789", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    assert doc["chunk_count"] == 1
    assert doc["meta"]["metadata_only"] is True
    assert "Secret-like content" in doc["error_message"]

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "OPENAI_API_KEY"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"] == []


def test_drive_config_exposes_higher_upload_limit(auth_client):
    resp = auth_client.get(f"{API}/drive/config")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["max_upload_mb"] >= 100
    assert data["max_upload_bytes"] == data["max_upload_mb"] * 1024 * 1024


def test_tool_calls_are_logged_to_ai_tool_calls(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "get_current_time", {})
    db_session.commit()
    assert outcome["status"] == "executed"
    row = db_session.query(AiToolCall).filter_by(tool_name="get_current_time").one()
    assert row.status == "executed"
    assert row.access == "read"


def test_school_memory_is_auto_extracted_from_chat(auth_client):
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "saya sekolah di Tzu Chi."})
    assert resp.status_code == 200, resp.text
    memories = auth_client.get(f"{API}/ai/memory/search", params={"q": "Tzu Chi"}).json()["data"]
    assert any("Tzu Chi" in m["content"] for m in memories)
