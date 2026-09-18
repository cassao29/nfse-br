"""Structural preflight for an unsigned restricted DPS document."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from nfse_br._f0 import restricted_contract as _restricted
from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.identity import DpsIdentity

MAX_XML_BYTES = 1024 * 1024

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_DPS = f"{{{_NFSE_NAMESPACE}}}DPS"
_INF_DPS = f"{{{_NFSE_NAMESPACE}}}infDPS"
_XML_ID = f"{{{_XML_NAMESPACE}}}id"
_DPS_ID_PATTERN = re.compile(r"DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}")
_DPS_NUMBER_PATTERN = re.compile(r"[1-9][0-9]{0,14}")


class SignaturePreflightError(ValueError):
    """A privacy-safe rejection before any signature operation."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"DPS signature preflight failed ({code}).")

    def __repr__(self) -> str:
        """Return only the controlled diagnostic code."""
        return f"SignaturePreflightError(code={self.code!r})"


def inspect_unsigned_dps(xml_bytes: bytes) -> str:
    """Return the unique verified ``infDPS`` Id from unsigned DPS bytes."""
    root = _parse_input(xml_bytes)
    information = _locate_information(root)
    _verify_local_profile(information)
    identity = _target_identity(root, information)
    _verify_identity_fields(information, identity)
    return identity


def _parse_input(xml_bytes: bytes) -> ElementTree.Element:
    if type(xml_bytes) is not bytes:
        raise SignaturePreflightError("invalid_runtime_type")
    if not xml_bytes:
        raise SignaturePreflightError("empty_document")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise SignaturePreflightError("document_too_large")
    try:
        return _restricted._parse_safe_xml(
            xml_bytes,
            source="DPS signature preflight input",
        )
    except _restricted.ContractFreezeError:
        raise SignaturePreflightError("unsafe_or_malformed_xml") from None


def _locate_information(root: ElementTree.Element) -> ElementTree.Element:
    if root.tag != _DPS:
        raise SignaturePreflightError("unexpected_root")
    if root.get("versao") != "1.01":
        raise SignaturePreflightError("unexpected_version")

    elements = tuple(root.iter())
    if any(_local_name(element.tag) == "Signature" for element in elements):
        raise SignaturePreflightError("signature_already_present")

    information_nodes = [
        element for element in elements if _local_name(element.tag) == "infDPS"
    ]
    if len(information_nodes) != 1 or information_nodes[0].tag != _INF_DPS:
        raise SignaturePreflightError("ambiguous_information_element")

    children = list(root)
    information = information_nodes[0]
    if children != [information]:
        raise SignaturePreflightError("unexpected_root_structure")
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
        raise SignaturePreflightError("unsupported_local_profile")


def _target_identity(
    root: ElementTree.Element,
    information: ElementTree.Element,
) -> str:
    identity = information.get("Id")
    if identity is None or _DPS_ID_PATTERN.fullmatch(identity) is None:
        raise SignaturePreflightError("invalid_target_id")

    for element in root.iter():
        for name in element.attrib:
            if name == "Id" and element is information:
                continue
            if name == _XML_ID or _local_name(name).casefold() == "id":
                raise SignaturePreflightError("ambiguous_identifier")
    return identity


def _verify_identity_fields(
    information: ElementTree.Element,
    identity: str,
) -> None:
    municipality_text = _unique_text(information, ("cLocEmi",))
    cnpj_text = _unique_text(information, ("prest", "CNPJ"))
    series_text = _unique_text(information, ("serie",))
    number_text = _unique_text(information, ("nDPS",))
    if _DPS_NUMBER_PATTERN.fullmatch(number_text) is None:
        raise SignaturePreflightError("invalid_identity_fields")

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
        raise SignaturePreflightError("invalid_identity_fields") from None
    if derived.value != identity:
        raise SignaturePreflightError("identity_mismatch")


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
        raise SignaturePreflightError(error_code)

    current = information
    for name in path:
        children = [child for child in current if child.tag == _qualified(name)]
        if len(children) != 1:
            raise SignaturePreflightError(error_code)
        current = children[0]
    if current is not matching[0] or list(current):
        raise SignaturePreflightError(error_code)
    return current.text or ""


def _qualified(local_name: str) -> str:
    return f"{{{_NFSE_NAMESPACE}}}{local_name}"


def _local_name(name: object) -> str:
    if type(name) is not str:
        return ""
    return name.rsplit("}", 1)[-1]
