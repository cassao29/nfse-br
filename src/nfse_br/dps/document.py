"""Safe structural inspection for unsigned restricted DPS documents."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast
from xml.etree import ElementTree

from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    MunicipalityCode,
)
from nfse_br.dps.builder import (
    RestrictedDpsDraft,
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
)
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
_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:00"
)
_AMOUNT_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,14})\.[0-9]{2}")
# Ordered, closed grammar of the builder's subset, not the complete DPS XSD.
_SUBSET_CHILDREN = {
    "DPS": ("infDPS",),
    "infDPS": (
        "tpAmb",
        "dhEmi",
        "verAplic",
        "serie",
        "nDPS",
        "dCompet",
        "tpEmit",
        "cLocEmi",
        "prest",
        "toma",
        "serv",
        "valores",
    ),
    "prest": ("CNPJ", "regTrib"),
    "toma": ("CNPJ", "xNome", "end"),
    "end": ("endNac", "xLgr", "nro", "xCpl", "xBairro"),
    "endNac": ("cMun", "CEP"),
    "regTrib": ("opSimpNac", "regEspTrib"),
    "serv": ("locPrest", "cServ"),
    "locPrest": ("cLocPrestacao",),
    "cServ": ("cTribNac", "xDescServ"),
    "valores": ("vServPrest", "trib"),
    "vServPrest": ("vServ",),
    "trib": ("tribMun", "totTrib"),
    "tribMun": ("tribISSQN", "tpRetISSQN"),
    "totTrib": ("indTotTrib",),
}
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
        "unsupported_document_structure",
        "invalid_document_fields",
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
    return _inspect_document(xml_bytes)[2]


def _inspect_document(
    xml_bytes: bytes,
) -> tuple[ElementTree.Element, ElementTree.Element, DpsIdentity]:
    root = _parse_input(xml_bytes)
    information = _locate_information(root)
    _verify_local_profile(information)
    observed_identity = _target_identity(root, information)
    return root, information, _identity_from_fields(information, observed_identity)


def parse_unsigned_dps(xml_bytes: bytes) -> RestrictedDpsDraft:
    """Parse only the builder's unsigned restricted subset, without XSD assurance.

    Unknown fields/attributes and unrepresentable content fail closed. Builder
    output rebuilds byte-for-byte; arbitrary XML formatting is not preserved.
    Timestamps retain wall time and offset, not a regional timezone or fold;
    Python draft equality is not guaranteed for ambiguous regional timestamps.
    """
    root, _, identity = _inspect_document(xml_bytes)
    # The shared safe parser discards comments/PIs and normalizes raw CR. Do not
    # silently lose such input in this stricter API; leave inspection unchanged.
    if (
        b"<!--" in xml_bytes
        or re.search(rb"<\?(?!xml[ \t\r\n])", xml_bytes) is not None
        or b"\r" in xml_bytes
    ):
        raise DpsDocumentError("unsupported_document_structure")
    fields: dict[tuple[str, ...], str] = {}
    _collect_subset(root, ("DPS",), fields)

    def text(path: str) -> str:
        return fields[("DPS", "infDPS", *path.split("/"))]

    timestamp = text("dhEmi")
    if (
        _TIMESTAMP_PATTERN.fullmatch(timestamp) is None
        or timestamp.endswith("-00:00")
        or _AMOUNT_PATTERN.fullmatch(text("valores/vServPrest/vServ")) is None
    ):
        raise DpsDocumentError("invalid_document_fields")
    try:
        return RestrictedDpsDraft(
            issuer_tax_id=identity.federal_tax_id,
            issue_municipality=identity.municipality,
            service_municipality=MunicipalityCode(text("serv/locPrest/cLocPrestacao")),
            series=identity.series,
            number=identity.number,
            issued_at=datetime.fromisoformat(timestamp),
            competence=CompetenceDate.from_iso(text("dCompet")),
            application_version=text("verAplic"),
            national_service_code=text("serv/cServ/cTribNac"),
            service_description=text("serv/cServ/xDescServ"),
            service_amount=Decimal(text("valores/vServPrest/vServ")),
            op_simp_nac=cast(Literal["1", "2", "3"], text("prest/regTrib/opSimpNac")),
            reg_esp_trib=cast(
                Literal["0", "1", "2", "3", "4", "5", "6", "9"],
                text("prest/regTrib/regEspTrib"),
            ),
            trib_issqn=cast(
                Literal["1", "2", "3", "4"], text("valores/trib/tribMun/tribISSQN")
            ),
            tp_ret_issqn=cast(
                Literal["1", "2", "3"], text("valores/trib/tribMun/tpRetISSQN")
            ),
            ind_tot_trib=cast(Literal["0"], text("valores/trib/totTrib/indTotTrib")),
            taker=_parse_taker(fields),
        )
    except ValueError:
        # Includes DomainValidationError and calendar/timestamp failures.
        raise DpsDocumentError("invalid_document_fields") from None


def _parse_taker(fields: dict[tuple[str, ...], str]) -> RestrictedDpsTaker | None:
    prefix = ("DPS", "infDPS", "toma")
    if (*prefix, "xNome") not in fields:
        return None
    cpf = fields.get((*prefix, "CPF"))
    raw = fields[(*prefix, "CNPJ")] if cpf is None else cpf
    identifier = FederalTaxId.cnpj(raw) if cpf is None else FederalTaxId.cpf(raw)
    if identifier.value != raw:
        raise DomainValidationError("Taker identifier normalization is not allowed.")
    address = (*prefix, "end")
    return RestrictedDpsTaker(
        tax_id=identifier,
        name=fields[(*prefix, "xNome")],
        address=RestrictedDpsNationalAddress(
            municipality=MunicipalityCode(fields[(*address, "endNac", "cMun")]),
            postal_code=fields[(*address, "endNac", "CEP")],
            street=fields[(*address, "xLgr")],
            number=fields[(*address, "nro")],
            neighborhood=fields[(*address, "xBairro")],
            complement=fields.get((*address, "xCpl")),
        ),
    )


def _collect_subset(
    element: ElementTree.Element,
    path: tuple[str, ...],
    fields: dict[tuple[str, ...], str],
) -> None:
    name = path[-1]
    attributes = {"DPS": {"versao"}, "infDPS": {"Id"}}.get(name, set())
    children = _SUBSET_CHILDREN.get(name, ())
    # Only these two particles are optional in this closed local grammar.
    optional = {"infDPS": "toma", "end": "xCpl"}.get(name)
    if optional is not None and not any(c.tag == _qualified(optional) for c in element):
        children = tuple(c for c in children if c != optional)
    if name == "toma" and any(c.tag == _qualified("CPF") for c in element):
        children = ("CPF", "xNome", "end")
    if (
        set(element.attrib) != attributes
        or [child.tag for child in element] != [_qualified(n) for n in children]
        or (element.tail or "").strip(" \t\n\r")
    ):
        raise DpsDocumentError("unsupported_document_structure")
    if children:
        if (element.text or "").strip(" \t\n\r"):
            raise DpsDocumentError("unsupported_document_structure")
        for child, child_name in zip(element, children, strict=True):
            _collect_subset(child, (*path, child_name), fields)
    else:
        fields[path] = element.text or ""


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
    taker_identifier = _taker_identifier(information)
    cnpj_text = _unique_text(information, ("prest", "CNPJ"), excluded=taker_identifier)
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


def _taker_identifier(information: ElementTree.Element) -> ElementTree.Element | None:
    """Identify a legitimate additional role, not a second arbitrary tax ID."""
    groups = [e for e in information.iter() if _local_name(e.tag) == "toma"]
    if not groups:
        if any(_local_name(e.tag) == "CPF" for e in information.iter()):
            raise DpsDocumentError("ambiguous_identity_field")
        return None
    if (
        len(groups) != 1
        or groups[0].tag != _qualified("toma")
        or groups[0] not in list(information)
    ):
        raise DpsDocumentError("ambiguous_identity_field")
    group = groups[0]
    # Keep inspection structural: do not validate name/address or fiscal rules.
    # The full schema has NIF/cNaoNIF alternatives, excluded by the subset parser.
    choices = {"CPF", "CNPJ", "NIF", "cNaoNIF"}
    identifiers = [e for e in group.iter() if _local_name(e.tag) in choices]
    if len(identifiers) != 1:
        raise DpsDocumentError("ambiguous_identity_field")
    identifier = identifiers[0]
    if (
        identifier not in list(group)
        or identifier.tag != _qualified(_local_name(identifier.tag))
        or list(identifier)
    ):
        raise DpsDocumentError("ambiguous_identity_field")
    # A CPF elsewhere cannot borrow the taker's role (CNPJ is checked below).
    if any(
        _local_name(e.tag) == "CPF" and e is not identifier for e in information.iter()
    ):
        raise DpsDocumentError("ambiguous_identity_field")
    return identifier


def _unique_text(
    information: ElementTree.Element,
    path: tuple[str, ...],
    *,
    error_code: str = "ambiguous_identity_field",
    excluded: ElementTree.Element | None = None,
) -> str:
    final_name = path[-1]
    matching = [
        element
        for element in information.iter()
        if _local_name(element.tag) == final_name and element is not excluded
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
