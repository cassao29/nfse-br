"""Privacy-safe structural extraction from local NFS-e XML bytes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree

from nfse_br._f0 import restricted_contract as _restricted
from nfse_br.domain import DomainValidationError
from nfse_br.nfse.identifier import NfseId

MAX_XML_BYTES = 1024 * 1024

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_NFSE_ROOT_QNAME = f"{{{_NFSE_NAMESPACE}}}NFSe"
_INF_NFSE_QNAME = f"{{{_NFSE_NAMESPACE}}}infNFSe"
_NFSE_NUMBER_QNAME = f"{{{_NFSE_NAMESPACE}}}nNFSe"
_DPS_QNAME = f"{{{_NFSE_NAMESPACE}}}DPS"
_INF_DPS_QNAME = f"{{{_NFSE_NAMESPACE}}}infDPS"
_DPS_ID_PATTERN_TEXT = r"DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"
_DPS_ID_PATTERN = re.compile(_DPS_ID_PATTERN_TEXT)

_ERROR_CODES = frozenset(
    {
        "invalid_runtime_type",
        "empty_document",
        "document_too_large",
        "unsafe_or_malformed_xml",
        "unexpected_root",
        "ambiguous_information_element",
        "invalid_nfse_id",
        "ambiguous_nfse_number",
        "invalid_nfse_number",
        "ambiguous_embedded_dps",
        "invalid_embedded_dps_id",
    }
)


class NfseDocumentError(ValueError):
    """A controlled failure while extracting local NFS-e structure."""

    __slots__ = ("code",)

    code: str

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError("Unsupported NFS-e document extraction error code.")
        self.code = code
        super().__init__(f"NFS-e document extraction failed ({code}).")

    def __repr__(self) -> str:
        """Return only the controlled error code."""
        return f"NfseDocumentError(code={self.code!r})"


@dataclass(frozen=True, slots=True)
class NfseDocumentInfo:
    """Directly observed identifiers from one local NFS-e XML document."""

    nfse_id: NfseId
    nfse_number: str
    embedded_dps_id: str

    def __repr__(self) -> str:
        """Redact every fiscal value from the representation."""
        return (
            "NfseDocumentInfo("
            "nfse_id=<redacted>, "
            "nfse_number=<redacted>, "
            "embedded_dps_id=<redacted>)"
        )


def extract_nfse_document_info(xml_bytes: bytes) -> NfseDocumentInfo:
    """Extract exact direct-path values without implying XSD validity."""
    if type(xml_bytes) is not bytes:
        raise NfseDocumentError("invalid_runtime_type")
    if not xml_bytes:
        raise NfseDocumentError("empty_document")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise NfseDocumentError("document_too_large")

    try:
        root = _restricted._parse_safe_xml(xml_bytes, source="NFS-e XML input")
    except _restricted.ContractFreezeError:
        raise NfseDocumentError("unsafe_or_malformed_xml") from None

    if root.tag != _NFSE_ROOT_QNAME:
        raise NfseDocumentError("unexpected_root")

    inf_nfse = _unique_direct_child(
        root,
        qname=_INF_NFSE_QNAME,
        local_name="infNFSe",
        error_code="ambiguous_information_element",
    )
    raw_nfse_id = _required_exact_id(inf_nfse, error_code="invalid_nfse_id")
    try:
        nfse_id = NfseId(raw_nfse_id)
    except DomainValidationError:
        raise NfseDocumentError("invalid_nfse_id") from None

    number_element = _unique_direct_child(
        inf_nfse,
        qname=_NFSE_NUMBER_QNAME,
        local_name="nNFSe",
        error_code="ambiguous_nfse_number",
    )
    if len(number_element) != 0 or number_element.text in (None, ""):
        raise NfseDocumentError("invalid_nfse_number")
    nfse_number = number_element.text

    dps = _unique_direct_child(
        inf_nfse,
        qname=_DPS_QNAME,
        local_name="DPS",
        error_code="ambiguous_embedded_dps",
    )
    inf_dps = _unique_direct_child(
        dps,
        qname=_INF_DPS_QNAME,
        local_name="infDPS",
        error_code="ambiguous_embedded_dps",
    )
    embedded_dps_id = _required_exact_id(
        inf_dps,
        error_code="invalid_embedded_dps_id",
    )
    if _DPS_ID_PATTERN.fullmatch(embedded_dps_id) is None:
        raise NfseDocumentError("invalid_embedded_dps_id")

    return NfseDocumentInfo(
        nfse_id=nfse_id,
        nfse_number=nfse_number,
        embedded_dps_id=embedded_dps_id,
    )


def _unique_direct_child(
    parent: ElementTree.Element,
    *,
    qname: str,
    local_name: str,
    error_code: str,
) -> ElementTree.Element:
    candidates = [
        child
        for child in parent
        if _local_name(child.tag).casefold() == local_name.casefold()
    ]
    if len(candidates) != 1 or candidates[0].tag != qname:
        raise NfseDocumentError(error_code)
    return candidates[0]


def _required_exact_id(element: ElementTree.Element, *, error_code: str) -> str:
    candidates = [
        (name, value)
        for name, value in element.attrib.items()
        if _local_name(name).casefold() == "id"
    ]
    if len(candidates) != 1 or candidates[0][0] != "Id":
        raise NfseDocumentError(error_code)
    return candidates[0][1]


def _local_name(qname: str) -> str:
    return qname.rpartition("}")[2]
