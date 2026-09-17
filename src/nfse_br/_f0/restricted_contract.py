"""Freeze the official restricted-environment DPS identity evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO, BinaryIO, Final, NoReturn, cast
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from nfse_br.domain import FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsIdentity, DpsNumber, DpsSeries

PORTAL_URL: Final = (
    "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita"
)
EXPECTED_XSD_LABEL: Final = "NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727"
EXPECTED_LAYOUT_LABEL: Final = (
    "ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209"
)
EXPECTED_XSD_URL: Final = f"{PORTAL_URL}/esquemas-nfse-rtc-v1-01-20260727.zip"
EXPECTED_LAYOUT_URL: Final = (
    f"{PORTAL_URL}/anexo_i-sefin_adn-dps_nfse-snnfse-prodrest-v1-01-20260209.xlsx"
)

EXPECTED_IDENTITY_PATTERN: Final = r"DPS[0-9]{7}(1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"
EXPECTED_IDENTITY_MAX_LENGTH: Final = 45
EXPECTED_SERIES_PATTERN: Final = r"[0-9]{1,4}|[0-8][0-9]{4}"

MAX_PORTAL_BYTES: Final = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES: Final = 50 * 1024 * 1024
MAX_FILES: Final = 500
MAX_MEMBER_BYTES: Final = 20 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED: Final = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS: Final = 30.0
_DOWNLOAD_CHUNK_BYTES: Final = 64 * 1024
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_XML_SCHEMA_NAMESPACE: Final = "http://www.w3.org/2001/XMLSchema"
_XML_SIMPLE_TYPE: Final = f"{{{_XML_SCHEMA_NAMESPACE}}}simpleType"
_XML_RESTRICTION: Final = f"{{{_XML_SCHEMA_NAMESPACE}}}restriction"
_XML_PATTERN: Final = f"{{{_XML_SCHEMA_NAMESPACE}}}pattern"
_XML_MAX_LENGTH: Final = f"{{{_XML_SCHEMA_NAMESPACE}}}maxLength"


class ContractFreezeError(RuntimeError):
    """Raised when official evidence cannot be frozen safely."""


@dataclass(frozen=True, slots=True)
class ArtifactLinks:
    """Official artifact URLs discovered from the authority page."""

    xsd_url: str
    layout_url: str


@dataclass(frozen=True, slots=True)
class DownloadedArtifact:
    """Bounded bytes fetched from a validated official URL."""

    url: str
    data: bytes
    content_type: str | None

    @property
    def sha256(self) -> str:
        """Return the SHA-256 digest of the exact downloaded bytes."""
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True, slots=True)
class TypeFacets:
    """Audited facets and provenance for one XSD simple type."""

    type_name: str
    source: str
    source_sha256: str
    pattern: str
    max_length: int | None


@dataclass(frozen=True, slots=True)
class ContractAudit:
    """Identity facets confirmed against the official restricted XSD bundle."""

    identity: TypeFacets
    series: TypeFacets
    alphanumeric_cnpj_vector: str
    synthetic_cpf_vector: str


class _AuthorityPageParser(HTMLParser):
    """Collect anchors without executing or interpreting page scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = next((value for name, value in attrs if name == "href"), None)
        if href is not None:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        label = " ".join("".join(self._text).split())
        self.links.append((label, self._href))
        self._href = None
        self._text = []


class _OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects that leave HTTPS hosts under gov.br."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        target = urljoin(req.full_url, newurl)
        _validate_official_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def discover_artifact_links(page_html: bytes) -> ArtifactLinks:
    """Resolve the expected official labels and fail closed on page drift."""
    try:
        text = page_html.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ContractFreezeError("Official portal is not valid UTF-8.") from exc

    parser = _AuthorityPageParser()
    parser.feed(text)
    parser.close()
    xsd_url = _resolve_unique_label(parser.links, EXPECTED_XSD_LABEL)
    layout_url = _resolve_unique_label(parser.links, EXPECTED_LAYOUT_LABEL)

    if xsd_url != EXPECTED_XSD_URL:
        raise ContractFreezeError(
            "DOCUMENTATION_DRIFT: XSD link changed; "
            f"expected {EXPECTED_XSD_URL!r}, observed {xsd_url!r}."
        )
    if layout_url != EXPECTED_LAYOUT_URL:
        raise ContractFreezeError(
            "DOCUMENTATION_DRIFT: layout link changed; "
            f"expected {EXPECTED_LAYOUT_URL!r}, observed {layout_url!r}."
        )
    return ArtifactLinks(xsd_url=xsd_url, layout_url=layout_url)


def download_official_url(url: str, *, max_bytes: int) -> DownloadedArtifact:
    """Download bounded bytes without environmental proxies or unsafe redirects."""
    _validate_official_url(url)
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ContractFreezeError("Download size limit must be a positive integer.")

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _OfficialRedirectHandler(),
        urllib.request.HTTPSHandler(),
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "nfse-br-contract-freeze/0.1",
        },
        method="GET",
    )
    try:
        response = opener.open(request, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        with response:
            final_url = response.geturl()
            _validate_official_url(final_url)
            content_length = _content_length(response.headers)
            if content_length is not None and content_length > max_bytes:
                raise ContractFreezeError(
                    f"Official download exceeds the {max_bytes}-byte limit."
                )
            body = _read_bounded(response, max_bytes=max_bytes)
            return DownloadedArtifact(
                url=final_url,
                data=body,
                content_type=response.headers.get_content_type(),
            )
    except ContractFreezeError:
        raise
    except (OSError, urllib.error.URLError) as exc:
        raise ContractFreezeError(f"Official download failed for {url!r}.") from exc


def audit_restricted_contract(xsd_zip: bytes) -> ContractAudit:
    """Audit only the official facets needed by the DPS identity contract."""
    members = _read_safe_zip(xsd_zip)
    xsd_members = {
        name: data for name, data in members.items() if name.casefold().endswith(".xsd")
    }
    if not xsd_members:
        raise ContractFreezeError("Official XSD archive contains no XSD files.")
    _reject_duplicate_xsd_basenames(xsd_members)

    identity = _find_type_facets(xsd_members, "TSIdDPS", require_max_length=True)
    series = _find_type_facets(xsd_members, "TSSerieDPS", require_max_length=False)
    _compare_facet(
        "TSIdDPS maxLength",
        EXPECTED_IDENTITY_MAX_LENGTH,
        identity.max_length,
    )
    _compare_facet("TSIdDPS pattern", EXPECTED_IDENTITY_PATTERN, identity.pattern)
    _compare_facet("TSSerieDPS pattern", EXPECTED_SERIES_PATTERN, series.pattern)

    alphanumeric = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
    ).value
    synthetic_cpf = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cpf("12345678901"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
    ).value
    compiled = re.compile(identity.pattern)
    for label, value in (
        ("alphanumeric CNPJ", alphanumeric),
        ("synthetic CPF", synthetic_cpf),
    ):
        if compiled.fullmatch(value) is None:
            raise ContractFreezeError(
                f"OFFICIAL_CONTRACT_DRIFT: {label} regression vector is rejected "
                "by TSIdDPS."
            )
    return ContractAudit(
        identity=identity,
        series=series,
        alphanumeric_cnpj_vector=alphanumeric,
        synthetic_cpf_vector=synthetic_cpf,
    )


def validate_layout_xlsx(layout_xlsx: bytes) -> None:
    """Validate the bounded ZIP structure of the official XLSX artifact."""
    members = _read_safe_zip(layout_xlsx)
    content_types = members.get("[Content_Types].xml")
    if content_types is None:
        raise ContractFreezeError("Official layout is missing [Content_Types].xml.")
    _parse_safe_xml(content_types, source="[Content_Types].xml")


def freeze_restricted_contract(
    *, work_dir: Path, manifest_path: Path
) -> dict[str, object]:
    """Fetch, audit, persist evidence bytes locally, and write the manifest."""
    portal = download_official_url(PORTAL_URL, max_bytes=MAX_PORTAL_BYTES)
    links = discover_artifact_links(portal.data)
    xsd = download_official_url(links.xsd_url, max_bytes=MAX_ARTIFACT_BYTES)
    layout = download_official_url(links.layout_url, max_bytes=MAX_ARTIFACT_BYTES)

    audit = audit_restricted_contract(xsd.data)
    validate_layout_xlsx(layout.data)
    manifest = _build_manifest(links=links, xsd=xsd, layout=layout, audit=audit)
    _validate_manifest(manifest)
    manifest_bytes = _serialize_manifest(manifest)
    _validate_existing_manifest(manifest_path, expected=manifest_bytes)

    _write_fixed_artifact(work_dir, "restricted-xsd.zip", xsd.data)
    _write_fixed_artifact(work_dir, "restricted-layout.xlsx", layout.data)
    _atomic_write(manifest_path, manifest_bytes)
    return manifest


def _resolve_unique_label(links: list[tuple[str, str]], label: str) -> str:
    matches = [urljoin(PORTAL_URL, href) for text, href in links if text == label]
    if len(matches) != 1:
        raise ContractFreezeError(
            f"DOCUMENTATION_DRIFT: expected exactly one {label!r} link; "
            f"observed {len(matches)}."
        )
    resolved = matches[0]
    _validate_official_url(resolved)
    return resolved


def _validate_official_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ContractFreezeError("Official URL is malformed.") from exc
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or hostname is None
        or not _is_official_host(hostname)
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or bool(parsed.fragment)
    ):
        raise ContractFreezeError(
            "Official URL must use HTTPS on a gov.br host without credentials."
        )


def _is_official_host(hostname: str) -> bool:
    normalized = hostname.rstrip(".").casefold()
    return normalized == "gov.br" or normalized.endswith(".gov.br")


def _content_length(headers: HTTPMessage) -> int | None:
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ContractFreezeError(
            "Official response has invalid Content-Length."
        ) from exc
    if value < 0:
        raise ContractFreezeError("Official response has invalid Content-Length.")
    return value


def _read_bounded(response: BinaryIO, *, max_bytes: int) -> bytes:
    body = bytearray()
    while True:
        remaining = max_bytes - len(body)
        chunk = response.read(min(_DOWNLOAD_CHUNK_BYTES, remaining + 1))
        if not chunk:
            return bytes(body)
        body.extend(chunk)
        if len(body) > max_bytes:
            raise ContractFreezeError(
                f"Official download exceeds the {max_bytes}-byte limit."
            )


def _read_safe_zip(data: bytes) -> dict[str, bytes]:
    if not data.startswith(b"PK") or not zipfile.is_zipfile(BytesIO(data)):
        raise ContractFreezeError("Official artifact is not a valid ZIP container.")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise ContractFreezeError("Official archive contains too many members.")
            total = 0
            seen: set[str] = set()
            for info in infos:
                _validate_zip_member(info)
                normalized = info.filename.replace("\\", "/")
                if normalized in seen:
                    raise ContractFreezeError(
                        f"Official archive repeats member {normalized!r}."
                    )
                seen.add(normalized)
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise ContractFreezeError(
                        "Official archive exceeds the total uncompressed limit."
                    )

            members: dict[str, bytes] = {}
            for info in infos:
                if info.is_dir():
                    continue
                content = archive.read(info)
                if len(content) != info.file_size:
                    raise ContractFreezeError(
                        f"Official archive member {info.filename!r} changed size."
                    )
                members[info.filename.replace("\\", "/")] = content
            return members
    except ContractFreezeError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ContractFreezeError("Official ZIP container is malformed.") from exc


def _validate_zip_member(info: zipfile.ZipInfo) -> None:
    normalized = info.filename.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(info.filename)
    if (
        not normalized
        or "\x00" in info.filename
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
    ):
        raise ContractFreezeError(
            f"Official archive contains unsafe member {info.filename!r}."
        )
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ContractFreezeError(
            f"Official archive contains symlink member {info.filename!r}."
        )
    if info.flag_bits & 0x1:
        raise ContractFreezeError(
            f"Official archive contains encrypted member {info.filename!r}."
        )
    if info.file_size > MAX_MEMBER_BYTES:
        raise ContractFreezeError(
            f"Official archive member {info.filename!r} exceeds the size limit."
        )


def _find_type_facets(
    xsd_members: dict[str, bytes], type_name: str, *, require_max_length: bool
) -> TypeFacets:
    matches: list[tuple[str, ElementTree.Element]] = []
    for name, data in sorted(xsd_members.items()):
        root = _parse_safe_xml(data, source=name)
        matches.extend(
            (name, element)
            for element in root.iter(_XML_SIMPLE_TYPE)
            if element.get("name") == type_name
        )
    if len(matches) != 1:
        raise ContractFreezeError(
            f"Official XSD must define {type_name} exactly once; "
            f"observed {len(matches)} definitions."
        )

    source, simple_type = matches[0]
    restrictions = simple_type.findall(_XML_RESTRICTION)
    if len(restrictions) != 1:
        raise ContractFreezeError(
            f"Official XSD type {type_name} must have one direct restriction."
        )
    restriction = restrictions[0]
    patterns = restriction.findall(_XML_PATTERN)
    if len(patterns) != 1:
        raise ContractFreezeError(
            f"Official XSD type {type_name} must have one pattern facet."
        )
    pattern = patterns[0].get("value")
    if pattern is None:
        raise ContractFreezeError(
            f"Official XSD type {type_name} has an empty pattern facet."
        )

    max_lengths = restriction.findall(_XML_MAX_LENGTH)
    if require_max_length and len(max_lengths) != 1:
        raise ContractFreezeError(
            f"Official XSD type {type_name} must have one maxLength facet."
        )
    if len(max_lengths) > 1:
        raise ContractFreezeError(
            f"Official XSD type {type_name} repeats maxLength facets."
        )
    max_length: int | None = None
    if max_lengths:
        raw = max_lengths[0].get("value")
        try:
            max_length = int(raw) if raw is not None else None
        except ValueError as exc:
            raise ContractFreezeError(
                f"Official XSD type {type_name} has invalid maxLength."
            ) from exc
        if max_length is None or max_length < 0:
            raise ContractFreezeError(
                f"Official XSD type {type_name} has invalid maxLength."
            )

    return TypeFacets(
        type_name=type_name,
        source=source,
        source_sha256=hashlib.sha256(xsd_members[source]).hexdigest(),
        pattern=pattern,
        max_length=max_length,
    )


def _reject_duplicate_xsd_basenames(xsd_members: dict[str, bytes]) -> None:
    seen: dict[str, str] = {}
    for path in sorted(xsd_members):
        basename = PurePosixPath(path).name.casefold()
        previous = seen.get(basename)
        if previous is not None:
            raise ContractFreezeError(
                "Official XSD archive has ambiguous basename "
                f"{PurePosixPath(path).name!r} in {previous!r} and {path!r}."
            )
        seen[basename] = path


def _parse_safe_xml(data: bytes, *, source: str) -> ElementTree.Element:
    if b"\x00" in data:
        raise ContractFreezeError(
            f"Unsupported XML encoding in {source!r}; UTF-8 bytes are required."
        )
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ContractFreezeError(f"XML declarations are forbidden in {source!r}.")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise ContractFreezeError(f"Malformed XML in {source!r}.") from exc


def _compare_facet(name: str, expected: object, observed: object) -> None:
    if observed != expected:
        raise ContractFreezeError(
            f"OFFICIAL_CONTRACT_DRIFT: {name} differs; "
            f"expected {_bounded_repr(expected)}, "
            f"observed {_bounded_repr(observed)}."
        )


def _bounded_repr(value: object, *, limit: int = 240) -> str:
    rendered = repr(value)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[:limit]}... <{len(rendered)} chars>"


def _build_manifest(
    *,
    links: ArtifactLinks,
    xsd: DownloadedArtifact,
    layout: DownloadedArtifact,
    audit: ContractAudit,
) -> dict[str, object]:
    audited_schemas = {
        facet.source: facet.source_sha256 for facet in (audit.identity, audit.series)
    }
    return {
        "authority": "official_frozen",
        "environment": "restricted",
        "layout": {
            "sha256": layout.sha256,
            "size": len(layout.data),
            "url": links.layout_url,
        },
        "portal": {
            "layout_label": EXPECTED_LAYOUT_LABEL,
            "url": PORTAL_URL,
            "xsd_label": EXPECTED_XSD_LABEL,
        },
        "regression_vectors": {
            "alphanumeric_cnpj": audit.alphanumeric_cnpj_vector,
            "synthetic_cpf": audit.synthetic_cpf_vector,
        },
        "scope": "dps_identity",
        "transmission_ready": False,
        "xsd": {
            "audited_schema_files": [
                {"path": path, "sha256": sha256}
                for path, sha256 in sorted(audited_schemas.items())
            ],
            "identity_contract": {
                "max_length": audit.identity.max_length,
                "pattern": audit.identity.pattern,
                "source": audit.identity.source,
                "type": audit.identity.type_name,
            },
            "series_contract": {
                "pattern": audit.series.pattern,
                "source": audit.series.source,
                "type": audit.series.type_name,
            },
            "sha256": xsd.sha256,
            "size": len(xsd.data),
            "url": links.xsd_url,
        },
    }


def _serialize_manifest(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _validate_existing_manifest(path: Path, *, expected: bytes) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise ContractFreezeError("Existing manifest must not be a symlink.")
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise ContractFreezeError("Could not read existing frozen manifest.") from exc
    manifest = _deserialize_manifest(current)
    _validate_manifest(manifest)
    if current != _serialize_manifest(manifest):
        raise ContractFreezeError(
            "Existing frozen manifest is not in canonical deterministic form."
        )
    if current != expected:
        raise ContractFreezeError(
            "OFFICIAL_ARTIFACT_CHANGED: official evidence differs from the "
            "existing frozen manifest; manual review is required."
        )


def _deserialize_manifest(data: bytes) -> dict[str, object]:
    try:
        parsed: object = json.loads(data, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractFreezeError("Existing frozen manifest is invalid JSON.") from exc
    if type(parsed) is not dict:
        raise ContractFreezeError("Existing frozen manifest must be a JSON object.")
    return cast(dict[str, object], parsed)


def _reject_json_constant(value: str) -> NoReturn:
    raise ContractFreezeError(
        f"Existing frozen manifest contains forbidden constant {value!r}."
    )


def _validate_manifest(manifest: Mapping[str, object]) -> None:
    _expect_keys(
        manifest,
        {
            "authority",
            "environment",
            "layout",
            "portal",
            "regression_vectors",
            "scope",
            "transmission_ready",
            "xsd",
        },
        context="manifest",
    )
    _expect_exact(manifest, "authority", "official_frozen")
    _expect_exact(manifest, "environment", "restricted")
    _expect_exact(manifest, "scope", "dps_identity")
    _expect_exact(manifest, "transmission_ready", False)

    portal = _expect_mapping(manifest, "portal")
    _expect_keys(
        portal,
        {"layout_label", "url", "xsd_label"},
        context="portal",
    )
    _expect_exact(portal, "url", PORTAL_URL)
    _expect_exact(portal, "xsd_label", EXPECTED_XSD_LABEL)
    _expect_exact(portal, "layout_label", EXPECTED_LAYOUT_LABEL)

    layout = _expect_mapping(manifest, "layout")
    _expect_keys(layout, {"sha256", "size", "url"}, context="layout")
    _validate_manifest_artifact(layout, expected_url=EXPECTED_LAYOUT_URL)

    vectors = _expect_mapping(manifest, "regression_vectors")
    _expect_keys(
        vectors,
        {"alphanumeric_cnpj", "synthetic_cpf"},
        context="regression_vectors",
    )
    _expect_exact(
        vectors,
        "alphanumeric_cnpj",
        "DPS2927408212ABC6780001Z000123000000000000042",
    )
    _expect_exact(
        vectors,
        "synthetic_cpf",
        "DPS292740810001234567890100123000000000000042",
    )

    xsd = _expect_mapping(manifest, "xsd")
    _expect_keys(
        xsd,
        {
            "audited_schema_files",
            "identity_contract",
            "series_contract",
            "sha256",
            "size",
            "url",
        },
        context="xsd",
    )
    _validate_manifest_artifact(xsd, expected_url=EXPECTED_XSD_URL)
    identity = _expect_mapping(xsd, "identity_contract")
    _expect_keys(
        identity,
        {"max_length", "pattern", "source", "type"},
        context="identity_contract",
    )
    _expect_exact(identity, "type", "TSIdDPS")
    _expect_exact(identity, "max_length", EXPECTED_IDENTITY_MAX_LENGTH)
    _expect_exact(identity, "pattern", EXPECTED_IDENTITY_PATTERN)
    identity_source = _expect_string(identity, "source")
    series = _expect_mapping(xsd, "series_contract")
    _expect_keys(
        series,
        {"pattern", "source", "type"},
        context="series_contract",
    )
    _expect_exact(series, "type", "TSSerieDPS")
    _expect_exact(series, "pattern", EXPECTED_SERIES_PATTERN)
    series_source = _expect_string(series, "source")

    audited = xsd.get("audited_schema_files")
    if type(audited) is not list or not audited:
        raise ContractFreezeError(
            "Frozen manifest audited_schema_files must be a non-empty list."
        )
    audited_paths: set[str] = set()
    audited_basenames: set[str] = set()
    for raw_entry in cast(list[object], audited):
        if type(raw_entry) is not dict:
            raise ContractFreezeError(
                "Frozen manifest audited schema entry must be an object."
            )
        entry = cast(dict[str, object], raw_entry)
        _expect_keys(entry, {"path", "sha256"}, context="audited_schema_file")
        path = _expect_string(entry, "path")
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or ".." in pure_path.parts or not pure_path.name:
            raise ContractFreezeError(
                "Frozen manifest contains unsafe audited schema path."
            )
        basename = pure_path.name.casefold()
        if path in audited_paths or basename in audited_basenames:
            raise ContractFreezeError(
                "Frozen manifest contains ambiguous audited schema paths."
            )
        audited_paths.add(path)
        audited_basenames.add(basename)
        _expect_sha256(entry, "sha256")
    if identity_source not in audited_paths or series_source not in audited_paths:
        raise ContractFreezeError(
            "Frozen manifest facet sources must reference audited schema files."
        )


def _validate_manifest_artifact(
    artifact: Mapping[str, object], *, expected_url: str
) -> None:
    _expect_exact(artifact, "url", expected_url)
    _validate_official_url(_expect_string(artifact, "url"))
    _expect_sha256(artifact, "sha256")
    size = artifact.get("size")
    if type(size) is not int or size <= 0:
        raise ContractFreezeError(
            "Frozen manifest artifact size must be a positive integer."
        )


def _expect_mapping(mapping: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = mapping.get(field)
    if type(value) is not dict:
        raise ContractFreezeError(f"Frozen manifest field {field!r} must be an object.")
    return cast(dict[str, object], value)


def _expect_keys(
    mapping: Mapping[str, object], expected: set[str], *, context: str
) -> None:
    observed = set(mapping)
    if observed != expected:
        raise ContractFreezeError(
            f"Frozen manifest {context} fields differ; "
            f"expected {sorted(expected)!r}, observed {sorted(observed)!r}."
        )


def _expect_string(mapping: Mapping[str, object], field: str) -> str:
    value = mapping.get(field)
    if type(value) is not str:
        raise ContractFreezeError(f"Frozen manifest field {field!r} must be a string.")
    return value


def _expect_exact(mapping: Mapping[str, object], field: str, expected: object) -> None:
    observed = mapping.get(field)
    if type(observed) is not type(expected) or observed != expected:
        raise ContractFreezeError(
            f"Frozen manifest field {field!r} differs; "
            f"expected {_bounded_repr(expected)}, "
            f"observed {_bounded_repr(observed)}."
        )


def _expect_sha256(mapping: Mapping[str, object], field: str) -> str:
    value = _expect_string(mapping, field)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ContractFreezeError(
            f"Frozen manifest field {field!r} must be lowercase SHA-256 hex."
        )
    return value


def _write_fixed_artifact(work_dir: Path, filename: str, data: bytes) -> None:
    if work_dir.exists() and work_dir.is_symlink():
        raise ContractFreezeError("Work directory must not be a symlink.")
    work_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(work_dir / filename, data)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ContractFreezeError(f"Refusing to overwrite symlink {path!s}.")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ContractFreezeError(f"Could not write evidence file {path!s}.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


__all__ = [
    "ContractFreezeError",
    "freeze_restricted_contract",
]
