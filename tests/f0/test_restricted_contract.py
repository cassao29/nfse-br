"""Offline tests for the restricted contract freeze tooling."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import stat
import urllib.error
import urllib.request
import zipfile
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest

import nfse_br
import nfse_br._f0.restricted_contract as restricted
from nfse_br._f0.restricted_contract import (
    ArtifactLinks,
    ContractFreezeError,
    DownloadedArtifact,
    audit_restricted_contract,
    discover_artifact_links,
    validate_layout_xlsx,
)


def _portal_html(
    *,
    xsd_label: str = restricted.EXPECTED_XSD_LABEL,
    xsd_url: str = restricted.EXPECTED_XSD_URL,
    layout_label: str = restricted.EXPECTED_LAYOUT_LABEL,
    layout_url: str = restricted.EXPECTED_LAYOUT_URL,
) -> bytes:
    return (
        "<html><body>"
        f'<a href="{layout_url}">{layout_label}</a>'
        f'<a href="{xsd_url}">{xsd_label}</a>'
        "</body></html>"
    ).encode()


def _xsd_document(
    *,
    identity_pattern: str = restricted.EXPECTED_IDENTITY_PATTERN,
    series_pattern: str = restricted.EXPECTED_SERIES_PATTERN,
    include_identity: bool = True,
    include_series: bool = True,
    duplicate_identity: bool = False,
    declaration: str = "",
) -> bytes:
    identity = ""
    if include_identity:
        identity = f"""
        <xs:simpleType name="TSIdDPS">
          <xs:restriction base="xs:string">
            <xs:maxLength value="45"/>
            <xs:pattern value="{identity_pattern}"/>
          </xs:restriction>
        </xs:simpleType>
        """
    duplicate = identity if duplicate_identity else ""
    series = ""
    if include_series:
        series = f"""
        <xs:simpleType name="TSSerieDPS">
          <xs:restriction base="xs:string">
            <xs:pattern value="{series_pattern}"/>
          </xs:restriction>
        </xs:simpleType>
        """
    return (
        f'{declaration}<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        f"{identity}{duplicate}{series}</xs:schema>"
    ).encode()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def _valid_xsd_zip() -> bytes:
    return _zip_bytes({"schemas/tipos.xsd": _xsd_document()})


def _valid_xlsx() -> bytes:
    return _zip_bytes(
        {
            "[Content_Types].xml": (
                b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                b'content-types"></Types>'
            ),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


class _FakeResponse(BytesIO):
    def __init__(
        self,
        data: bytes,
        *,
        url: str = restricted.PORTAL_URL,
        content_length: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        super().__init__(data)
        self._url = url
        self.headers = HTTPMessage()
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.headers["Content-Type"] = content_type

    def geturl(self) -> str:
        return self._url


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response

    def open(self, request: urllib.request.Request, *, timeout: float) -> _FakeResponse:
        assert request.full_url.startswith("https://")
        assert timeout == restricted.DOWNLOAD_TIMEOUT_SECONDS
        return self.response


class _FailingOpener:
    def open(self, request: urllib.request.Request, *, timeout: float) -> None:
        raise urllib.error.URLError(f"offline: {request.full_url}, {timeout}")


class _InterruptedResponse(_FakeResponse):
    def __init__(self) -> None:
        super().__init__(b"")
        self._reads = 0

    def read(self, size: int | None = -1, /) -> bytes:
        self._reads += 1
        if self._reads == 1:
            return b"partial"
        raise OSError("connection interrupted")


def _install_fake_opener(
    monkeypatch: pytest.MonkeyPatch,
    opener: _FakeOpener | _FailingOpener,
) -> list[urllib.request.BaseHandler]:
    captured: list[urllib.request.BaseHandler] = []

    def fake_build_opener(
        *handlers: urllib.request.BaseHandler,
    ) -> urllib.request.OpenerDirector:
        captured.extend(handlers)
        return cast(urllib.request.OpenerDirector, opener)

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    return captured


def test_discovers_exact_official_labels_and_urls() -> None:
    links = discover_artifact_links(_portal_html())

    assert links == ArtifactLinks(
        xsd_url=restricted.EXPECTED_XSD_URL,
        layout_url=restricted.EXPECTED_LAYOUT_URL,
    )


def test_rejects_changed_portal_label() -> None:
    with pytest.raises(ContractFreezeError, match="DOCUMENTATION_DRIFT"):
        discover_artifact_links(_portal_html(xsd_label="changed label"))


def test_rejects_changed_portal_link() -> None:
    with pytest.raises(ContractFreezeError, match="XSD link changed"):
        discover_artifact_links(
            _portal_html(xsd_url=f"{restricted.PORTAL_URL}/changed.zip")
        )


def test_rejects_non_utf8_portal() -> None:
    with pytest.raises(ContractFreezeError, match="valid UTF-8"):
        discover_artifact_links(b"\xff")


def test_rejects_duplicate_authority_label() -> None:
    html = (
        _portal_html()
        + (
            f'<a href="{restricted.EXPECTED_XSD_URL}">'
            f"{restricted.EXPECTED_XSD_LABEL}</a>"
        ).encode()
    )

    with pytest.raises(ContractFreezeError, match="observed 2"):
        discover_artifact_links(html)


@pytest.mark.parametrize(
    "url",
    [
        "https://evilgov.br/file.zip",
        "http://www.gov.br/file.zip",
        "https://example.com/file.zip",
        "https://gov.br.example.com/file.zip",
        "https://gov.br@evil.example/file.zip",
        "https://user:password@www.gov.br/file.zip",
        "https://www.gov.br:444/file.zip",
        "https://www.gov.br/file.zip#fragment",
        "https:///missing-host.zip",
        "https://www.gov.br:not-a-port/file.zip",
    ],
)
def test_rejects_non_official_urls(url: str) -> None:
    with pytest.raises(ContractFreezeError, match="HTTPS on a gov.br host|malformed"):
        restricted._validate_official_url(url)


def test_redirect_handler_rejects_external_host() -> None:
    handler = restricted._OfficialRedirectHandler()
    request = urllib.request.Request(restricted.PORTAL_URL)

    with pytest.raises(ContractFreezeError, match="gov.br host"):
        handler.redirect_request(
            request,
            BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            "https://attacker.example/artifact.zip",
        )


def test_redirect_handler_rejects_https_downgrade() -> None:
    handler = restricted._OfficialRedirectHandler()
    request = urllib.request.Request(restricted.PORTAL_URL)

    with pytest.raises(ContractFreezeError, match="HTTPS"):
        handler.redirect_request(
            request,
            BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            "http://www.gov.br/artifact.zip",
        )


def test_download_is_bounded_and_ignores_environmental_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://attacker.example:8080")
    monkeypatch.setenv("HTTPS_PROXY", "https://attacker.example:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://attacker.example:1080")
    response = _FakeResponse(
        b"official",
        content_length="8",
        content_type="application/zip",
    )
    handlers = _install_fake_opener(monkeypatch, _FakeOpener(response))

    artifact = restricted.download_official_url(restricted.PORTAL_URL, max_bytes=8)

    assert artifact.data == b"official"
    assert artifact.content_type == "application/zip"
    assert artifact.sha256 == hashlib.sha256(b"official").hexdigest()
    proxy_handlers = [
        handler
        for handler in handlers
        if isinstance(handler, urllib.request.ProxyHandler)
    ]
    assert len(proxy_handlers) == 1
    assert vars(proxy_handlers[0])["proxies"] == {}


@pytest.mark.parametrize("limit", [0, -1, True, 1.0])
def test_download_rejects_invalid_limits(
    limit: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_opener(monkeypatch, _FakeOpener(_FakeResponse(b"")))

    with pytest.raises(ContractFreezeError, match="positive integer"):
        restricted.download_official_url(
            restricted.PORTAL_URL,
            max_bytes=cast(int, limit),
        )


@pytest.mark.parametrize("content_length", ["9", "-1", "invalid"])
def test_download_rejects_invalid_or_oversized_content_length(
    content_length: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = _FakeResponse(b"", content_length=content_length)
    _install_fake_opener(monkeypatch, _FakeOpener(response))

    with pytest.raises(ContractFreezeError, match="limit|Content-Length"):
        restricted.download_official_url(restricted.PORTAL_URL, max_bytes=8)


def test_download_rejects_external_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(b"", url="https://attacker.example/file")
    _install_fake_opener(monkeypatch, _FakeOpener(response))

    with pytest.raises(ContractFreezeError, match="gov.br host"):
        restricted.download_official_url(restricted.PORTAL_URL, max_bytes=8)


def test_download_wraps_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_opener(monkeypatch, _FailingOpener())

    with pytest.raises(ContractFreezeError, match="Official download failed"):
        restricted.download_official_url(restricted.PORTAL_URL, max_bytes=8)


def test_interrupted_download_never_produces_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_opener(monkeypatch, _FakeOpener(_InterruptedResponse()))

    with pytest.raises(ContractFreezeError, match="Official download failed"):
        restricted.download_official_url(restricted.PORTAL_URL, max_bytes=100)

    assert list(tmp_path.iterdir()) == []


def test_freeze_download_failure_creates_no_evidence_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_after_portal(url: str, *, max_bytes: int) -> DownloadedArtifact:
        assert max_bytes > 0
        if url == restricted.PORTAL_URL:
            return DownloadedArtifact(url=url, data=_portal_html(), content_type=None)
        raise ContractFreezeError("simulated partial artifact download")

    monkeypatch.setattr(restricted, "download_official_url", fail_after_portal)
    work_dir = tmp_path / "work"
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(ContractFreezeError, match="partial artifact"):
        restricted.freeze_restricted_contract(
            work_dir=work_dir,
            manifest_path=manifest_path,
        )

    assert not work_dir.exists()
    assert not manifest_path.exists()


def test_bounded_reader_stops_oversized_body() -> None:
    with pytest.raises(ContractFreezeError, match="4-byte limit"):
        restricted._read_bounded(BytesIO(b"12345"), max_bytes=4)


def test_rejects_malformed_zip() -> None:
    with pytest.raises(ContractFreezeError, match="valid ZIP"):
        audit_restricted_contract(b"not a zip")


def test_rejects_archive_without_xsd_members() -> None:
    with pytest.raises(ContractFreezeError, match="contains no XSD"):
        audit_restricted_contract(_zip_bytes({"README.txt": b"no schema"}))


@pytest.mark.parametrize(
    "name",
    [
        "../escape.xsd",
        "../../evil",
        "/absolute.xsd",
        "\\absolute.xsd",
        "..\\evil.xsd",
        "C:\\evil.xsd",
        "C:evil.xsd",
    ],
)
def test_rejects_unsafe_zip_member_paths(name: str) -> None:
    archive = _zip_bytes({name: _xsd_document()})

    with pytest.raises(ContractFreezeError, match="unsafe member"):
        audit_restricted_contract(archive)


def test_rejects_nul_zip_member_name_metadata() -> None:
    info = zipfile.ZipInfo("safe.xsd")
    info.filename = "unsafe\x00.xsd"

    with pytest.raises(ContractFreezeError, match="unsafe member"):
        restricted._validate_zip_member(info)


def test_rejects_zip_symlink() -> None:
    output = BytesIO()
    info = zipfile.ZipInfo("schema.xsd")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr(info, b"target")

    with pytest.raises(ContractFreezeError, match="symlink"):
        audit_restricted_contract(output.getvalue())


def test_rejects_encrypted_zip_member_metadata() -> None:
    info = zipfile.ZipInfo("schema.xsd")
    info.flag_bits |= 0x1

    with pytest.raises(ContractFreezeError, match="encrypted"):
        restricted._validate_zip_member(info)


def test_rejects_excessive_uncompressed_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(restricted, "MAX_TOTAL_UNCOMPRESSED", 4)

    with pytest.raises(ContractFreezeError, match="total uncompressed"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": b"12345"}))


def test_rejects_excessive_member_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(restricted, "MAX_MEMBER_BYTES", 4)

    with pytest.raises(ContractFreezeError, match="member .* exceeds"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": b"12345"}))


def test_rejects_excessive_member_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(restricted, "MAX_FILES", 1)

    with pytest.raises(ContractFreezeError, match="too many members"):
        restricted._read_safe_zip(_zip_bytes({"a": b"a", "b": b"b"}))


def test_rejects_duplicate_normalized_member_names() -> None:
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("schemas\\types.xsd", b"one")
        archive.writestr("schemas/types.xsd", b"two")

    with pytest.raises(ContractFreezeError, match="repeats member"):
        restricted._read_safe_zip(output.getvalue())


def test_rejects_duplicate_xsd_basenames_in_distinct_directories() -> None:
    archive = _zip_bytes(
        {
            "first/types.xsd": _xsd_document(),
            "second/types.xsd": (
                b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'
            ),
        }
    )

    with pytest.raises(ContractFreezeError, match="ambiguous basename"):
        audit_restricted_contract(archive)


def test_zip_resource_limits_accept_boundary_and_reject_boundary_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = zipfile.ZipInfo("member.bin")
    info.file_size = 5
    monkeypatch.setattr(restricted, "MAX_MEMBER_BYTES", 5)
    restricted._validate_zip_member(info)
    info.file_size = 6
    with pytest.raises(ContractFreezeError, match="exceeds"):
        restricted._validate_zip_member(info)

    monkeypatch.setattr(restricted, "MAX_FILES", 2)
    restricted._read_safe_zip(_zip_bytes({"a": b"a", "b": b"b"}))
    with pytest.raises(ContractFreezeError, match="too many"):
        restricted._read_safe_zip(_zip_bytes({"a": b"a", "b": b"b", "c": b"c"}))

    monkeypatch.setattr(restricted, "MAX_TOTAL_UNCOMPRESSED", 5)
    restricted._read_safe_zip(_zip_bytes({"a": b"aa", "b": b"bbb"}))
    with pytest.raises(ContractFreezeError, match="total uncompressed"):
        restricted._read_safe_zip(_zip_bytes({"a": b"aa", "b": b"bbbb"}))


@pytest.mark.parametrize("declaration", ["<!DOCTYPE schema>", "<!ENTITY x 'y'>"])
def test_rejects_dtd_and_entity_declarations(declaration: str) -> None:
    archive = _zip_bytes({"schema.xsd": _xsd_document(declaration=declaration)})

    with pytest.raises(ContractFreezeError, match="declarations are forbidden"):
        audit_restricted_contract(archive)


@pytest.mark.parametrize(
    "document",
    [
        b"<root/>",
        b'<?xml version="1.0" encoding="UTF-8"?><root/>',
        b'<?xml version="1.0" encoding="utf-8"?><root/>',
        b"<?xml version='1.0' encoding='UTF-8'?><root/>",
        b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><root/>',
    ],
)
def test_accepts_utf8_xml_evidence(document: bytes) -> None:
    assert restricted._parse_safe_xml(document, source="fixture.xml").tag == "root"


@pytest.mark.parametrize(
    "document",
    [
        b'<?xml version="1.0" encoding="ISO-8859-1"?><root>caf\xe9</root>',
        b'<?xml version="1.0" encoding="ISO-8859-1"?><root/>',
        b'<?xml version="1.0" encoding="windows-1252"?><root/>',
        '<?xml version="1.0" encoding="UTF-16"?><root/>'.encode("utf-16-le"),
        '<?xml version="1.0" encoding="UTF-16"?><root/>'.encode("utf-16-be"),
        '<?xml version="1.0" encoding="UTF-32"?><root/>'.encode("utf-32-le"),
        '<?xml version="1.0" encoding="UTF-32"?><root/>'.encode("utf-32-be"),
        b"<root>\xff</root>",
    ],
)
def test_rejects_non_utf8_xml_evidence(document: bytes) -> None:
    with pytest.raises(ContractFreezeError, match="Unsupported XML encoding"):
        restricted._parse_safe_xml(document, source="fixture.xml")


def test_rejects_utf16_xml_that_could_hide_dtd() -> None:
    xsd = _xsd_document(declaration="<!DOCTYPE schema>").decode().encode("utf-16")

    with pytest.raises(ContractFreezeError, match="Unsupported XML encoding"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_utf32_xml_that_could_hide_dtd() -> None:
    xsd = _xsd_document(declaration="<!DOCTYPE schema>").decode().encode("utf-32")

    with pytest.raises(ContractFreezeError, match="Unsupported XML encoding"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_identity_pattern_drift() -> None:
    archive = _zip_bytes({"schema.xsd": _xsd_document(identity_pattern="DPS[0-9]{42}")})

    with pytest.raises(ContractFreezeError) as exc_info:
        audit_restricted_contract(archive)

    message = str(exc_info.value)
    assert "TSIdDPS pattern" in message
    assert repr(restricted.EXPECTED_IDENTITY_PATTERN) in message
    assert repr("DPS[0-9]{42}") in message


def test_drift_error_bounds_large_observed_facet() -> None:
    large_pattern = "A" * 10_000
    archive = _zip_bytes({"schema.xsd": _xsd_document(identity_pattern=large_pattern)})

    with pytest.raises(ContractFreezeError) as exc_info:
        audit_restricted_contract(archive)

    message = str(exc_info.value)
    assert len(message) < 1_000
    assert "10002 chars" in message


def test_rejects_series_pattern_drift() -> None:
    archive = _zip_bytes({"schema.xsd": _xsd_document(series_pattern="[0-9]{1,5}")})

    with pytest.raises(ContractFreezeError) as exc_info:
        audit_restricted_contract(archive)

    message = str(exc_info.value)
    assert "TSSerieDPS pattern" in message
    assert repr(restricted.EXPECTED_SERIES_PATTERN) in message
    assert repr("[0-9]{1,5}") in message


def test_rejects_duplicate_simple_type() -> None:
    archive = _zip_bytes({"schema.xsd": _xsd_document(duplicate_identity=True)})

    with pytest.raises(ContractFreezeError, match="exactly once; observed 2"):
        audit_restricted_contract(archive)


def test_rejects_duplicate_series_simple_type() -> None:
    document = _xsd_document()
    extra_series = _xsd_document(include_identity=False)
    duplicate = document.replace(b"</xs:schema>", extra_series.split(b">", 1)[1])

    with pytest.raises(ContractFreezeError, match="TSSerieDPS exactly once"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": duplicate}))


def test_rejects_missing_simple_type() -> None:
    archive = _zip_bytes({"schema.xsd": _xsd_document(include_identity=False)})

    with pytest.raises(ContractFreezeError, match="TSIdDPS exactly once; observed 0"):
        audit_restricted_contract(archive)


def test_rejects_identity_without_direct_restriction() -> None:
    xsd = (
        b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        b'<xs:simpleType name="TSIdDPS"/>'
        b'<xs:simpleType name="TSSerieDPS"><xs:restriction base="xs:string">'
        b'<xs:pattern value="[0-9]{1,4}|[0-8][0-9]{4}"/>'
        b"</xs:restriction></xs:simpleType></xs:schema>"
    )

    with pytest.raises(ContractFreezeError, match="one direct restriction"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_malformed_xsd() -> None:
    with pytest.raises(ContractFreezeError, match="Malformed XML"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": b"<schema>"}))


def test_rejects_identity_max_length_drift() -> None:
    xsd = _xsd_document().replace(b'maxLength value="45"', b'maxLength value="44"')

    with pytest.raises(ContractFreezeError) as exc_info:
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))

    message = str(exc_info.value)
    assert "TSIdDPS maxLength" in message
    assert "expected 45" in message
    assert "observed 44" in message


@pytest.mark.parametrize("replacement", [b"", b'<xs:maxLength value="invalid"/>'])
def test_rejects_missing_or_invalid_identity_max_length(replacement: bytes) -> None:
    xsd = _xsd_document().replace(b'<xs:maxLength value="45"/>', replacement)

    with pytest.raises(ContractFreezeError, match="maxLength"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_missing_identity_pattern() -> None:
    xsd = _xsd_document().replace(
        f'<xs:pattern value="{restricted.EXPECTED_IDENTITY_PATTERN}"/>'.encode(),
        b"",
    )

    with pytest.raises(ContractFreezeError, match="one pattern facet"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_pattern_facet_without_value() -> None:
    pattern = f'<xs:pattern value="{restricted.EXPECTED_IDENTITY_PATTERN}"/>'.encode()
    xsd = _xsd_document().replace(pattern, b"<xs:pattern/>")

    with pytest.raises(ContractFreezeError, match="empty pattern facet"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))


def test_rejects_duplicate_identity_pattern_and_max_length() -> None:
    pattern = f'<xs:pattern value="{restricted.EXPECTED_IDENTITY_PATTERN}"/>'.encode()
    xsd_with_patterns = _xsd_document().replace(pattern, pattern + pattern)
    with pytest.raises(ContractFreezeError, match="one pattern facet"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd_with_patterns}))

    max_length = b'<xs:maxLength value="45"/>'
    xsd_with_lengths = _xsd_document().replace(max_length, max_length + max_length)
    with pytest.raises(ContractFreezeError, match="one maxLength|repeats maxLength"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd_with_lengths}))


def test_rejects_ambiguous_or_negative_optional_max_length() -> None:
    series_pattern = (
        f'<xs:pattern value="{restricted.EXPECTED_SERIES_PATTERN}"/>'.encode()
    )
    duplicate = b'<xs:maxLength value="5"/><xs:maxLength value="5"/>'
    xsd_with_duplicate = _xsd_document().replace(
        series_pattern, duplicate + series_pattern
    )
    with pytest.raises(ContractFreezeError, match="repeats maxLength"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd_with_duplicate}))

    negative = b'<xs:maxLength value="-1"/>'
    xsd_with_negative = _xsd_document().replace(
        series_pattern, negative + series_pattern
    )
    with pytest.raises(ContractFreezeError, match="invalid maxLength"):
        audit_restricted_contract(_zip_bytes({"schema.xsd": xsd_with_negative}))


def test_audits_expected_facets_and_regression_vectors() -> None:
    audit = audit_restricted_contract(_valid_xsd_zip())

    assert audit.identity.max_length == 45
    assert audit.identity.pattern == restricted.EXPECTED_IDENTITY_PATTERN
    assert audit.series.pattern == restricted.EXPECTED_SERIES_PATTERN
    assert audit.alphanumeric_cnpj_vector == (
        "DPS2927408212ABC6780001Z000123000000000000042"
    )
    assert audit.synthetic_cpf_vector == (
        "DPS292740810001234567890100123000000000000042"
    )


def test_rejects_malformed_xlsx() -> None:
    with pytest.raises(ContractFreezeError, match="valid ZIP"):
        validate_layout_xlsx(b"not an xlsx")


def test_rejects_xlsx_without_content_types() -> None:
    with pytest.raises(ContractFreezeError, match=r"missing \[Content_Types\]"):
        validate_layout_xlsx(_zip_bytes({"xl/workbook.xml": b"<workbook/>"}))


def test_accepts_structurally_valid_xlsx() -> None:
    validate_layout_xlsx(_valid_xlsx())


def test_xlsx_rejects_non_utf8_content_types() -> None:
    content_types = b'<?xml version="1.0" encoding="windows-1252"?><Types/>'
    workbook = _zip_bytes(
        {
            "[Content_Types].xml": content_types,
            "xl/workbook.xml": b"<workbook/>",
        }
    )

    with pytest.raises(ContractFreezeError, match="Unsupported XML encoding"):
        validate_layout_xlsx(workbook)


@pytest.mark.parametrize("name", ["../evil", "..\\evil", "/absolute"])
def test_xlsx_rejects_traversal_members(name: str) -> None:
    members = {
        "[Content_Types].xml": b"<Types/>",
        name: b"unsafe",
    }

    with pytest.raises(ContractFreezeError, match="unsafe member"):
        validate_layout_xlsx(_zip_bytes(members))


def test_xlsx_rejects_symlink_and_duplicate_members() -> None:
    output = BytesIO()
    info = zipfile.ZipInfo("xl/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr(info, b"target")
    with pytest.raises(ContractFreezeError, match="symlink"):
        validate_layout_xlsx(output.getvalue())

    duplicate = BytesIO()
    with zipfile.ZipFile(duplicate, mode="w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl\\workbook.xml", b"one")
        archive.writestr("xl/workbook.xml", b"two")
    with pytest.raises(ContractFreezeError, match="repeats member"):
        validate_layout_xlsx(duplicate.getvalue())


def test_xlsx_rejects_resource_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(restricted, "MAX_TOTAL_UNCOMPRESSED", 5)

    with pytest.raises(ContractFreezeError, match="total uncompressed"):
        validate_layout_xlsx(_valid_xlsx())


def test_manifest_serialization_is_deterministic() -> None:
    xsd_bytes = _valid_xsd_zip()
    layout_bytes = _valid_xlsx()
    audit = audit_restricted_contract(xsd_bytes)
    manifest = restricted._build_manifest(
        links=ArtifactLinks(
            xsd_url=restricted.EXPECTED_XSD_URL,
            layout_url=restricted.EXPECTED_LAYOUT_URL,
        ),
        xsd=DownloadedArtifact(
            url=restricted.EXPECTED_XSD_URL,
            data=xsd_bytes,
            content_type="application/zip",
        ),
        layout=DownloadedArtifact(
            url=restricted.EXPECTED_LAYOUT_URL,
            data=layout_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        ),
        audit=audit,
    )

    first = restricted._serialize_manifest(manifest)
    second = restricted._serialize_manifest(manifest)

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first)["transmission_ready"] is False


def test_offline_freeze_writes_only_fixed_artifacts_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portal = _portal_html()
    xsd = _valid_xsd_zip()
    layout = _valid_xlsx()

    def fake_download(url: str, *, max_bytes: int) -> DownloadedArtifact:
        assert max_bytes > 0
        payloads = {
            restricted.PORTAL_URL: (portal, "text/html"),
            restricted.EXPECTED_XSD_URL: (xsd, "application/zip"),
            restricted.EXPECTED_LAYOUT_URL: (
                layout,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        }
        data, content_type = payloads[url]
        return DownloadedArtifact(url=url, data=data, content_type=content_type)

    monkeypatch.setattr(restricted, "download_official_url", fake_download)
    work_dir = tmp_path / "work"
    manifest_path = tmp_path / "contracts" / "manifest.json"

    manifest = restricted.freeze_restricted_contract(
        work_dir=work_dir,
        manifest_path=manifest_path,
    )

    assert sorted(path.name for path in work_dir.iterdir()) == [
        "restricted-layout.xlsx",
        "restricted-xsd.zip",
    ]
    assert (work_dir / "restricted-xsd.zip").read_bytes() == xsd
    assert (work_dir / "restricted-layout.xlsx").read_bytes() == layout
    assert json.loads(manifest_path.read_bytes()) == manifest
    assert manifest["authority"] == "official_frozen"
    assert manifest["scope"] == "dps_identity"
    assert manifest["transmission_ready"] is False


def test_existing_manifest_blocks_changed_artifact_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portal = _portal_html()
    xsd = _valid_xsd_zip()
    original_layout = _valid_xlsx()
    changed_layout = _zip_bytes(
        {
            "[Content_Types].xml": b"<Types/>",
            "xl/workbook.xml": b"<workbook changed='true'/>",
        }
    )
    active_layout = original_layout

    def fake_download(url: str, *, max_bytes: int) -> DownloadedArtifact:
        assert max_bytes > 0
        payloads = {
            restricted.PORTAL_URL: portal,
            restricted.EXPECTED_XSD_URL: xsd,
            restricted.EXPECTED_LAYOUT_URL: active_layout,
        }
        return DownloadedArtifact(
            url=url,
            data=payloads[url],
            content_type="application/octet-stream",
        )

    monkeypatch.setattr(restricted, "download_official_url", fake_download)
    work_dir = tmp_path / "work"
    manifest_path = tmp_path / "manifest.json"
    restricted.freeze_restricted_contract(
        work_dir=work_dir,
        manifest_path=manifest_path,
    )
    original_manifest = manifest_path.read_bytes()
    original_xsd = (work_dir / "restricted-xsd.zip").read_bytes()
    original_layout_on_disk = (work_dir / "restricted-layout.xlsx").read_bytes()

    active_layout = changed_layout
    with pytest.raises(ContractFreezeError, match="OFFICIAL_ARTIFACT_CHANGED"):
        restricted.freeze_restricted_contract(
            work_dir=work_dir,
            manifest_path=manifest_path,
        )

    assert manifest_path.read_bytes() == original_manifest
    assert (work_dir / "restricted-xsd.zip").read_bytes() == original_xsd
    assert (work_dir / "restricted-layout.xlsx").read_bytes() == (
        original_layout_on_disk
    )


def test_invalid_existing_manifest_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portal = _portal_html()
    xsd = _valid_xsd_zip()
    layout = _valid_xlsx()

    def fake_download(url: str, *, max_bytes: int) -> DownloadedArtifact:
        assert max_bytes > 0
        payloads = {
            restricted.PORTAL_URL: portal,
            restricted.EXPECTED_XSD_URL: xsd,
            restricted.EXPECTED_LAYOUT_URL: layout,
        }
        return DownloadedArtifact(
            url=url,
            data=payloads[url],
            content_type="application/octet-stream",
        )

    monkeypatch.setattr(restricted, "download_official_url", fake_download)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(b"{}\n")

    with pytest.raises(ContractFreezeError, match="manifest fields"):
        restricted.freeze_restricted_contract(
            work_dir=tmp_path / "work",
            manifest_path=manifest_path,
        )

    assert manifest_path.read_bytes() == b"{}\n"
    assert not (tmp_path / "work").exists()


def test_atomic_write_failure_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "artifact.zip"

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(f"cannot replace {source} with {destination}")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(ContractFreezeError, match="Could not write"):
        restricted._atomic_write(target, b"complete bytes")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("payload", [b"NaN", b"Infinity", b"-Infinity"])
def test_manifest_rejects_non_json_constants(payload: bytes) -> None:
    with pytest.raises(ContractFreezeError, match="forbidden constant"):
        restricted._deserialize_manifest(payload)


@pytest.mark.parametrize("payload", [b"not-json", b"[]"])
def test_manifest_rejects_invalid_json_or_non_object(payload: bytes) -> None:
    with pytest.raises(ContractFreezeError, match="invalid JSON|JSON object"):
        restricted._deserialize_manifest(payload)


def test_existing_manifest_must_be_canonical(tmp_path: Path) -> None:
    canonical = Path("contracts/restricted/manifest.json").read_bytes()
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical.rstrip())

    with pytest.raises(ContractFreezeError, match="canonical deterministic"):
        restricted._validate_existing_manifest(path, expected=canonical)


def test_rejects_symlink_manifest_target(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real.json"
    real.write_text("untouched")
    symlink = tmp_path / "manifest.json"
    symlink.symlink_to(real)

    with pytest.raises(ContractFreezeError, match="symlink"):
        restricted._atomic_write(symlink, b"changed")

    assert real.read_text() == "untouched"


def test_rejects_symlink_work_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    symlink = tmp_path / "work"
    symlink.symlink_to(real, target_is_directory=True)

    with pytest.raises(ContractFreezeError, match="Work directory"):
        restricted._write_fixed_artifact(symlink, "artifact.zip", b"PK")

    assert list(real.iterdir()) == []


def test_private_f0_module_is_not_promoted_or_networked_on_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_build_opener(*handlers: object) -> urllib.request.OpenerDirector:
        raise AssertionError(f"network opener created during import: {handlers!r}")

    monkeypatch.setattr(urllib.request, "build_opener", fail_build_opener)
    monkeypatch.chdir(tmp_path)
    module = importlib.reload(restricted)

    assert module.__name__ == "nfse_br._f0.restricted_contract"
    assert nfse_br.__all__ == ["__version__"]
    assert not hasattr(nfse_br, "freeze_restricted_contract")
    assert list(tmp_path.iterdir()) == []


def test_audited_xsd_hash_uses_exact_member_bytes() -> None:
    xsd = _xsd_document()
    audit = audit_restricted_contract(_zip_bytes({"schema.xsd": xsd}))

    assert audit.identity.source_sha256 == hashlib.sha256(xsd).hexdigest()
    assert audit.series.source_sha256 == hashlib.sha256(xsd).hexdigest()
