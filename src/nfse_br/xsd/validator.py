"""Fail-closed local validation against the frozen restricted DPS schema."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from xml.etree import ElementTree

from lxml import etree

if TYPE_CHECKING:
    from lxml.etree._docloader import _InputDocument

from nfse_br._f0 import restricted_contract as _restricted

RESTRICTED_XSD_BUNDLE_SIZE = 34_933
RESTRICTED_XSD_BUNDLE_SHA256 = (
    "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
)
MAX_XML_BYTES = 1024 * 1024

_XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema"
_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_XMLDSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"
_SCHEMA = f"{{{_XSD_NAMESPACE}}}schema"
_ELEMENT = f"{{{_XSD_NAMESPACE}}}element"
_INCLUDE = f"{{{_XSD_NAMESPACE}}}include"
_IMPORT = f"{{{_XSD_NAMESPACE}}}import"
_MEMORY_ROOT = "memory://nfse-br/restricted/"

_EXPECTED_ENTRYPOINT = "DPS_v1.01.xsd"
_EXPECTED_ROOT_QNAME = f"{{{_NFSE_NAMESPACE}}}DPS"
_EXPECTED_SCHEMA_MEMBERS = {
    "DPS_v1.01.xsd": "c7dab363d8cf7c83fc2b3b21e72cf669a51bd30947a5690685ea96c4b3e39dcd",
    "tiposComplexos_v1.01.xsd": (
        "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
    ),
    "tiposSimples_v1.01.xsd": (
        "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
    ),
    "xmldsig-core-schema.xsd": (
        "bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11"
    ),
}


class XsdValidationError(ValueError):
    """A privacy-safe failure while preparing or validating restricted DPS XML."""

    def __init__(
        self,
        *,
        phase: str,
        code: str,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.phase = phase
        self.code = code
        self.line = line
        self.column = column
        position = ""
        if line is not None:
            position = f" at line {line}"
            if column is not None:
                position += f", column {column}"
        super().__init__(f"XSD {phase} failure ({code}){position}.")

    def __repr__(self) -> str:
        """Return only controlled diagnostic fields."""
        return (
            "XsdValidationError("
            f"phase={self.phase!r}, code={self.code!r}, "
            f"line={self.line!r}, column={self.column!r})"
        )


@dataclass(frozen=True, slots=True)
class _SchemaProfile:
    entrypoint: str
    root_qname: str
    members: Mapping[str, bytes]


class _DenyByDefaultResolver(etree.Resolver):
    """Resolve only exact in-memory URIs belonging to the approved schema set."""

    def __init__(self, resources: Mapping[str, bytes]) -> None:
        super().__init__()
        self._resources = dict(resources)

    def resolve(
        self,
        url: str | None,
        pubid: str | None,
        context: object,
        /,
    ) -> _InputDocument:
        del pubid
        data = self._resources.get(url) if url is not None else None
        if data is None:
            raise OSError("schema resource is not in the approved in-memory set")
        return self.resolve_string(data, context, base_url=url)


class RestrictedDpsXsdValidator:
    """Compile once and validate sequentially against the pinned restricted DPS XSD."""

    __slots__ = ("_root_qname", "_schema")

    def __init__(self, bundle_bytes: bytes) -> None:
        """Verify and compile the exact frozen restricted schema bundle."""
        _verify_bundle_pin(
            bundle_bytes,
            expected_size=RESTRICTED_XSD_BUNDLE_SIZE,
            expected_sha256=RESTRICTED_XSD_BUNDLE_SHA256,
        )

        try:
            archive_members = _restricted._read_safe_zip(bundle_bytes)
            profile = _official_schema_profile(archive_members)
            self._schema = _compile_schema(profile.members, profile.entrypoint)
            self._root_qname = profile.root_qname
        except _restricted.ContractFreezeError:
            raise _error("bundle", "unsafe_archive") from None
        except XsdValidationError:
            raise
        except (OSError, etree.LxmlError):
            raise _error("bundle", "schema_compile_failed") from None

    def validate(self, xml_bytes: bytes) -> None:
        """Validate one XML byte string, returning ``None`` only when it passes."""
        _validate_xml(self._schema, xml_bytes, expected_root=self._root_qname)


def _verify_bundle_pin(
    bundle_bytes: bytes, *, expected_size: int, expected_sha256: str
) -> None:
    if type(bundle_bytes) is not bytes:
        raise _error("bundle", "invalid_runtime_type")
    if len(bundle_bytes) != expected_size:
        raise _error("bundle", "size_mismatch")
    if hashlib.sha256(bundle_bytes).hexdigest() != expected_sha256:
        raise _error("bundle", "digest_mismatch")


def _validate_xml(
    schema: etree.XMLSchema,
    xml_bytes: bytes,
    *,
    expected_root: str,
) -> None:
    """Apply the exact input policy and a precompiled schema."""
    if type(xml_bytes) is not bytes:
        raise _error("parse", "invalid_runtime_type")
    if not xml_bytes:
        raise _error("parse", "empty_document")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise _error("parse", "document_too_large")

    try:
        _restricted._parse_safe_xml(xml_bytes, source="DPS input")
    except _restricted.ContractFreezeError:
        raise _error("parse", "unsafe_or_malformed_xml") from None

    parser = _xml_parser(resources={})
    try:
        document = etree.fromstring(xml_bytes, parser=parser)
    except (OSError, etree.XMLSyntaxError) as exc:
        line, column = _exception_position(exc)
        raise _error(
            "parse",
            "malformed_xml",
            line=line,
            column=column,
        ) from None

    if document.tag != expected_root:
        raise _error("schema", "unexpected_root")

    if not schema.validate(document):
        last_error = schema.error_log.last_error
        raise _error(
            "schema",
            "document_invalid",
            line=last_error.line if last_error is not None else None,
            column=last_error.column if last_error is not None else None,
        )


def _official_schema_profile(members: Mapping[str, bytes]) -> _SchemaProfile:
    xsd_members = {
        name: data for name, data in members.items() if name.casefold().endswith(".xsd")
    }
    entrypoint, root_qname = _discover_dps_entrypoint(xsd_members)
    closure = _schema_closure(xsd_members, entrypoint=entrypoint)
    observed = {
        name: hashlib.sha256(data).hexdigest() for name, data in closure.items()
    }
    if (
        entrypoint != _EXPECTED_ENTRYPOINT
        or root_qname != _EXPECTED_ROOT_QNAME
        or observed != _EXPECTED_SCHEMA_MEMBERS
    ):
        raise _error("bundle", "schema_profile_mismatch")
    return _SchemaProfile(
        entrypoint=entrypoint,
        root_qname=root_qname,
        members=closure,
    )


def _discover_dps_entrypoint(members: Mapping[str, bytes]) -> tuple[str, str]:
    matches: list[tuple[str, str]] = []
    for name, data in sorted(members.items()):
        root = _safe_schema_root(data, source=name)
        target_namespace = root.get("targetNamespace")
        if target_namespace is None:
            continue
        for element in root.findall(_ELEMENT):
            if element.get("name") == "DPS" and element.get("type") == "TCDPS":
                matches.append((name, f"{{{target_namespace}}}DPS"))
    if len(matches) != 1:
        raise _error("bundle", "entrypoint_not_unique")
    return matches[0]


def _schema_closure(
    members: Mapping[str, bytes], *, entrypoint: str
) -> dict[str, bytes]:
    if entrypoint not in members:
        raise _error("bundle", "entrypoint_missing")

    closure: dict[str, bytes] = {}
    pending = [entrypoint]
    while pending:
        current = pending.pop()
        if current in closure:
            continue
        data = members.get(current)
        if data is None:
            raise _error("bundle", "schema_dependency_missing")
        root = _safe_schema_root(data, source=current)
        closure[current] = data
        current_namespace = root.get("targetNamespace")
        for dependency in list(root.findall(_INCLUDE)) + list(root.findall(_IMPORT)):
            location = dependency.get("schemaLocation")
            if location is None:
                raise _error("bundle", "schema_location_missing")
            resolved = _resolve_member_location(current, location)
            dependency_data = members.get(resolved)
            if dependency_data is None:
                raise _error("bundle", "schema_dependency_missing")
            dependency_root = _safe_schema_root(dependency_data, source=resolved)
            dependency_namespace = dependency_root.get("targetNamespace")
            if dependency.tag == _INCLUDE:
                if dependency_namespace != current_namespace:
                    raise _error("bundle", "include_namespace_mismatch")
            elif dependency.get("namespace") != dependency_namespace:
                raise _error("bundle", "import_namespace_mismatch")
            pending.append(resolved)
    return dict(sorted(closure.items()))


def _resolve_member_location(current: str, location: str) -> str:
    if not location or "\\" in location or "\x00" in location:
        raise _error("bundle", "unsafe_schema_location")
    parsed = urlsplit(location)
    windows = PureWindowsPath(location)
    path = PurePosixPath(location)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or path.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in path.parts
    ):
        raise _error("bundle", "unsafe_schema_location")
    resolved = PurePosixPath(current).parent / path
    return resolved.as_posix()


def _safe_schema_root(data: bytes, *, source: str) -> ElementTree.Element:
    try:
        root = _restricted._parse_safe_xml(data, source=source)
    except _restricted.ContractFreezeError:
        raise _error("bundle", "unsafe_schema_xml") from None
    if root.tag != _SCHEMA:
        raise _error("bundle", "not_an_xsd_schema")
    return root


def _compile_schema(members: Mapping[str, bytes], entrypoint: str) -> etree.XMLSchema:
    resources = {_member_uri(name): data for name, data in members.items()}
    entry_uri = _member_uri(entrypoint)
    entry_bytes = resources.get(entry_uri)
    if entry_bytes is None:
        raise _error("bundle", "entrypoint_missing")
    parser = _xml_parser(resources=resources)
    try:
        document = etree.fromstring(entry_bytes, parser=parser, base_url=entry_uri)
        return etree.XMLSchema(document)
    except (OSError, etree.LxmlError):
        raise _error("bundle", "schema_compile_failed") from None


def _xml_parser(*, resources: Mapping[str, bytes]) -> etree.XMLParser:
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        dtd_validation=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        attribute_defaults=False,
    )
    parser.resolvers.add(_DenyByDefaultResolver(resources))
    return parser


def _member_uri(name: str) -> str:
    return f"{_MEMORY_ROOT}{name}"


def _exception_position(exc: BaseException) -> tuple[int | None, int | None]:
    position = getattr(exc, "position", None)
    if (
        type(position) is tuple
        and len(position) == 2
        and type(position[0]) is int
        and type(position[1]) is int
    ):
        return position[0], position[1]
    return None, None


def _error(
    phase: str,
    code: str,
    *,
    line: int | None = None,
    column: int | None = None,
) -> XsdValidationError:
    return XsdValidationError(
        phase=phase,
        code=code,
        line=line,
        column=column,
    )
