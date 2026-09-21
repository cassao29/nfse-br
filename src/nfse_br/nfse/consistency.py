"""Fail-closed local consistency checks for NFS-e and its embedded DPS."""

from __future__ import annotations

import re
from xml.etree import ElementTree

import nfse_br.nfse.document as _document
from nfse_br._f0 import restricted_contract as _restricted
from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsIdentity, DpsNumber, DpsSeries
from nfse_br.nfse.document import NfseDocumentError, extract_nfse_document_info

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_TP_EMIT_QNAME = f"{{{_NFSE_NAMESPACE}}}tpEmit"
_SERIES_QNAME = f"{{{_NFSE_NAMESPACE}}}serie"
_DPS_NUMBER_QNAME = f"{{{_NFSE_NAMESPACE}}}nDPS"
_MUNICIPALITY_QNAME = f"{{{_NFSE_NAMESPACE}}}cLocEmi"
_CPF_QNAME = f"{{{_NFSE_NAMESPACE}}}CPF"
_CNPJ_QNAME = f"{{{_NFSE_NAMESPACE}}}CNPJ"
_DPS_NUMBER_PATTERN = re.compile(r"[1-9][0-9]{0,14}")

_ERROR_CODES = frozenset(
    {
        "unsafe_or_malformed_document",
        "embedded_dps_identity_mismatch",
        "municipality_mismatch",
        "federal_registration_mismatch",
    }
)

_EMITTER_ELEMENT_BY_TYPE = {
    "1": "prest",
    "2": "toma",
    "3": "interm",
}


class NfseConsistencyError(ValueError):
    """A controlled NFS-e and embedded-DPS consistency failure."""

    __slots__ = ("code",)

    code: str

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError("Unsupported NFS-e consistency error code.")
        self.code = code
        super().__init__(f"NFS-e consistency validation failed ({code}).")

    def __repr__(self) -> str:
        """Return only the controlled error code."""
        return f"NfseConsistencyError(code={self.code!r})"


def validate_nfse_document_consistency(xml_bytes: bytes) -> None:
    """Validate only officially confirmed NFS-e/DPS consistency rules."""
    try:
        info = extract_nfse_document_info(xml_bytes)
        root = _restricted._parse_safe_xml(
            xml_bytes,
            source="NFS-e consistency XML input",
        )
        inf_nfse = _document._unique_direct_child(
            root,
            qname=_document._INF_NFSE_QNAME,
            local_name="infNFSe",
            error_code="ambiguous_information_element",
        )
        dps = _document._unique_direct_child(
            inf_nfse,
            qname=_document._DPS_QNAME,
            local_name="DPS",
            error_code="ambiguous_embedded_dps",
        )
        inf_dps = _document._unique_direct_child(
            dps,
            qname=_document._INF_DPS_QNAME,
            local_name="infDPS",
            error_code="ambiguous_embedded_dps",
        )
        identity = _compose_embedded_dps_identity(inf_dps)
    except (
        _restricted.ContractFreezeError,
        DomainValidationError,
        NfseDocumentError,
    ):
        raise NfseConsistencyError("unsafe_or_malformed_document") from None

    if identity.value != info.embedded_dps_id:
        raise NfseConsistencyError("embedded_dps_identity_mismatch")
    if info.nfse_id.value[3:10] != identity.municipality.value:
        raise NfseConsistencyError("municipality_mismatch")
    if info.nfse_id.value[11:26] != identity.value[10:25]:
        raise NfseConsistencyError("federal_registration_mismatch")


def _compose_embedded_dps_identity(
    inf_dps: ElementTree.Element,
) -> DpsIdentity:
    tp_emit = _required_leaf(inf_dps, qname=_TP_EMIT_QNAME, local_name="tpEmit")
    emitter_name = _EMITTER_ELEMENT_BY_TYPE.get(tp_emit)
    if emitter_name is None:
        raise DomainValidationError("Unsupported DPS issuer type.")

    emitter = _document._unique_direct_child(
        inf_dps,
        qname=f"{{{_NFSE_NAMESPACE}}}{emitter_name}",
        local_name=emitter_name,
        error_code="ambiguous_embedded_dps",
    )
    federal_tax_id = _required_federal_tax_id(emitter)
    municipality = MunicipalityCode(
        _required_leaf(
            inf_dps,
            qname=_MUNICIPALITY_QNAME,
            local_name="cLocEmi",
        )
    )
    series = DpsSeries(_required_leaf(inf_dps, qname=_SERIES_QNAME, local_name="serie"))
    raw_number = _required_leaf(
        inf_dps,
        qname=_DPS_NUMBER_QNAME,
        local_name="nDPS",
    )
    if _DPS_NUMBER_PATTERN.fullmatch(raw_number) is None:
        raise DomainValidationError("DPS number violates the frozen contract.")
    number = DpsNumber(int(raw_number))
    return DpsIdentity.build(
        municipality=municipality,
        federal_tax_id=federal_tax_id,
        series=series,
        number=number,
    )


def _required_leaf(
    parent: ElementTree.Element,
    *,
    qname: str,
    local_name: str,
) -> str:
    element = _document._unique_direct_child(
        parent,
        qname=qname,
        local_name=local_name,
        error_code="ambiguous_embedded_dps",
    )
    if len(element) != 0 or element.text in (None, ""):
        raise DomainValidationError("Required DPS value is not a leaf value.")
    return element.text


def _required_federal_tax_id(emitter: ElementTree.Element) -> FederalTaxId:
    candidates = [
        child
        for child in emitter
        if _document._local_name(child.tag).casefold() in {"cpf", "cnpj"}
    ]
    if len(candidates) != 1:
        raise DomainValidationError("DPS issuer federal identifier is ambiguous.")

    element = candidates[0]
    if len(element) != 0 or element.text in (None, ""):
        raise DomainValidationError("DPS issuer federal identifier is invalid.")
    if element.tag == _CPF_QNAME:
        identifier = FederalTaxId.cpf(element.text)
    elif element.tag == _CNPJ_QNAME:
        identifier = FederalTaxId.cnpj(element.text)
    else:
        raise DomainValidationError("DPS issuer federal identifier is invalid.")
    if identifier.value != element.text:
        raise DomainValidationError("DPS issuer federal identifier was normalized.")
    return identifier
