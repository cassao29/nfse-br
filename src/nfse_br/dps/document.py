"""Safe structural inspection for unsigned restricted DPS documents."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps.identity import DpsIdentity
from nfse_br.dps.number import DpsNumber
from nfse_br.dps.series import DpsSeries

_MAX_XML_BYTES = 1024 * 1024

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_DPS = f"{{{_NFSE_NAMESPACE}}}DPS"
_INF_DPS = f"{{{_NFSE_NAMESPACE}}}infDPS"
_XML_ID = f"{{{_XML_NAMESPACE}}}id"
_DPS_ID_PATTERN = re.compile(r"DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}")
_DPS_NUMBER_PATTERN = re.compile(r"[1-9][0-9]{0,14}")
_ERROR_CODES = frozenset(
    {
        "invalid_runtime_type",
        "empty_document",
        "document_too_large",
        "unsafe_or_malformed_xml",
        "unexpected_root",
        "unexpected_version",
        "signature_already_present",
        "ambiguous_information_element",
        "unexpected_root_structure",
        "ambiguous_profile_field",
        "unsupported_local_profile",
        "invalid_target_id",
        "ambiguous_identifier",
        "ambiguous_identity_field",
        "invalid_identity_fields",
        "identity_mismatch",
    }
)


class DpsDocumentError(ValueError):
    """A privacy-safe rejection while inspecting an unsigned DPS document."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError("Unsupported DPS document inspection error code.")
        self.code = code
        super().__init__(f"DPS document inspection failed ({code}).")

    def __repr__(self) -> str:
        """Return only the controlled diagnostic code."""
        return f"DpsDocumentError(code={self.code!r})"


def inspect_unsigned_dps(xml_bytes: bytes) -> DpsIdentity:
    """Return the identity derived from one structurally valid unsigned DPS."""
    root = _parse_input(xml_bytes)
    information = _locate_information(root)
    _verify_local_profile(information)
    observed_identity = _target_identity(root, information)
    return _identity_from_fields(information, observed_identity)


def _parse_input(xml_bytes: bytes) -> ElementTree.Element:
    from nfse_br._f0 import restricted_contract as _restricted

    if type(xml_bytes) is not bytes:
        raise DpsDocumentError("invalid_runtime_type")
    if not xml_bytes:
        raise DpsDocumentError("empty_document")
    if len(xml_bytes) > _MAX_XML_BYTES:
        raise DpsDocumentError("document_too_large")
    try:
        return _restricted._parse_safe_xml(
            xml_bytes,
            source="DPS document inspection input",
        )
    except _restricted.ContractFreezeError:
        raise DpsDocumentError("unsafe_or_malformed_xml") from None


def _locate_information(root: ElementTree.Element) -> ElementTree.Element:
    if root.tag != _DPS:
        raise DpsDocumentError("unexpected_root")
    if root.get("versao") != "1.01":
        raise DpsDocumentError("unexpected_version")

    elements = tuple(root.iter())
    if any(_local_name(element.tag) == "Signature" for element in elements):
        raise DpsDocumentError("signature_already_present")

    information_nodes = [
        element for element in elements if _local_name(element.tag) == "infDPS"
    ]
    if len(information_nodes) != 1 or information_nodes[0].tag != _INF_DPS:
        raise DpsDocumentError("ambiguous_information_element")

    children = list(root)
    information = information_nodes[0]
    if children != [information]:
        raise DpsDocumentError("unexpected_root_structure")
    return information


def _verify_local_profile(information: ElementTree.Element) -> None:
    environment = _unique_text(
        information,
        ("tpAmb",),
        error_code="ambiguous_profile_field",
    )
    issuer_type = _unique_text(
        information,
        ("tpEmit",),
        error_code="ambiguous_profile_field",
    )
    if environment != "2" or issuer_type != "1":
        raise DpsDocumentError("unsupported_local_profile")


def _target_identity(
    root: ElementTree.Element,
    information: ElementTree.Element,
) -> str:
    identity = information.get("Id")
    if identity is None or _DPS_ID_PATTERN.fullmatch(identity) is None:
        raise DpsDocumentError("invalid_target_id")

    for element in root.iter():
        for name in element.attrib:
            if name == "Id" and element is information:
                continue
            if name == _XML_ID or _local_name(name).casefold() == "id":
                raise DpsDocumentError("ambiguous_identifier")
    return identity


def _identity_from_fields(
    information: ElementTree.Element,
    observed_identity: str,
) -> DpsIdentity:
    municipality_text = _unique_text(information, ("cLocEmi",))
    cnpj_text = _unique_text(information, ("prest", "CNPJ"))
    series_text = _unique_text(information, ("serie",))
    number_text = _unique_text(information, ("nDPS",))
    if _DPS_NUMBER_PATTERN.fullmatch(number_text) is None:
        raise DpsDocumentError("invalid_identity_fields")

    try:
        municipality = MunicipalityCode(municipality_text)
        federal_tax_id = FederalTaxId.cnpj(cnpj_text)
        if federal_tax_id.value != cnpj_text:
            raise DomainValidationError("CNPJ normalization is not allowed here.")
        series = DpsSeries(series_text)
        number = DpsNumber(int(number_text))
        derived = DpsIdentity.build(
            municipality=municipality,
            federal_tax_id=federal_tax_id,
            series=series,
            number=number,
        )
    except DomainValidationError:
        raise DpsDocumentError("invalid_identity_fields") from None
    if derived.value != observed_identity:
        raise DpsDocumentError("identity_mismatch")
    return derived


def _unique_text(
    information: ElementTree.Element,
    path: tuple[str, ...],
    *,
    error_code: str = "ambiguous_identity_field",
) -> str:
    final_name = path[-1]
    matching = [
        element
        for element in information.iter()
        if _local_name(element.tag) == final_name
    ]
    if len(matching) != 1 or matching[0].tag != _qualified(final_name):
        raise DpsDocumentError(error_code)

    current = information
    for name in path:
        children = [child for child in current if child.tag == _qualified(name)]
        if len(children) != 1:
            raise DpsDocumentError(error_code)
        current = children[0]
    if current is not matching[0] or list(current):
        raise DpsDocumentError(error_code)
    return current.text or ""


def _qualified(local_name: str) -> str:
    return f"{{{_NFSE_NAMESPACE}}}{local_name}"


def _local_name(name: object) -> str:
    if type(name) is not str:
        return ""
    return name.rsplit("}", 1)[-1]
