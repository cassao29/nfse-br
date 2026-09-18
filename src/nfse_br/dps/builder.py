"""Deterministic unsigned DPS construction for a restricted-profile subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from xml.etree import ElementTree

from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    FederalTaxIdKind,
    MunicipalityCode,
)
from nfse_br.dps.identity import DpsIdentity
from nfse_br.dps.number import DpsNumber
from nfse_br.dps.series import DpsSeries

__all__ = ["RestrictedDpsDraft", "build_unsigned_dps"]

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_SCHEMA_VERSION = "1.01"
_RESTRICTED_ENVIRONMENT = "2"
_ISSUER_TYPE_PROVIDER = "1"
_MAX_AMOUNT_INTEGER_DIGITS = 15

_SIMPLE_NATIONAL_OPTIONS = frozenset({"1", "2", "3"})
_SPECIAL_TAX_REGIMES = frozenset({"0", "1", "2", "3", "4", "5", "6", "9"})
_ISSQN_TAXATION_OPTIONS = frozenset({"1", "2", "3", "4"})
_ISSQN_WITHHOLDING_OPTIONS = frozenset({"1", "2", "3"})
_TOTAL_TAX_INDICATORS = frozenset({"0"})
_XSD_WHITESPACE = frozenset({"\t", "\n", "\r", " "})

_SimpleNationalOption = Literal["1", "2", "3"]
_SpecialTaxRegime = Literal["0", "1", "2", "3", "4", "5", "6", "9"]
_IssqnTaxation = Literal["1", "2", "3", "4"]
_IssqnWithholding = Literal["1", "2", "3"]
_TotalTaxIndicator = Literal["0"]


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RestrictedDpsDraft:
    """Immutable inputs for the deliberately small restricted DPS profile."""

    issuer_tax_id: FederalTaxId
    issue_municipality: MunicipalityCode
    service_municipality: MunicipalityCode
    series: DpsSeries
    number: DpsNumber
    issued_at: datetime
    competence: CompetenceDate
    application_version: str
    national_service_code: str
    service_description: str
    service_amount: Decimal
    op_simp_nac: _SimpleNationalOption
    reg_esp_trib: _SpecialTaxRegime
    trib_issqn: _IssqnTaxation
    tp_ret_issqn: _IssqnWithholding
    ind_tot_trib: _TotalTaxIndicator
    _issued_at_text: str = field(init=False, repr=False, compare=False)
    _service_amount_text: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate the supported official structural and lexical subset."""
        _require_exact_type(
            self.issuer_tax_id,
            FederalTaxId,
            "Issuer tax identifier must be a FederalTaxId.",
        )
        if self.issuer_tax_id.kind is not FederalTaxIdKind.CNPJ:
            raise DomainValidationError(
                "Restricted DPS issuer must be identified by CNPJ."
            )
        _require_exact_type(
            self.issue_municipality,
            MunicipalityCode,
            "Issue municipality must be a MunicipalityCode.",
        )
        _require_exact_type(
            self.service_municipality,
            MunicipalityCode,
            "Service municipality must be a MunicipalityCode.",
        )
        _require_exact_type(
            self.series,
            DpsSeries,
            "DPS series must be a DpsSeries.",
        )
        _require_exact_type(
            self.number,
            DpsNumber,
            "DPS number must be a DpsNumber.",
        )
        _require_exact_type(
            self.competence,
            CompetenceDate,
            "Competence must be a CompetenceDate.",
        )

        issued_at_text = _format_issued_at(self.issued_at)
        if not 2000 <= self.competence.value.year <= 2099:
            raise DomainValidationError(
                "Competence year must fit the restricted TSData profile."
            )
        _validate_application_version(self.application_version)
        _validate_service_code(self.national_service_code)
        _validate_service_description(self.service_description)
        service_amount_text = _format_amount(self.service_amount)
        _validate_code(
            self.op_simp_nac,
            _SIMPLE_NATIONAL_OPTIONS,
            "Simple National option",
        )
        _validate_code(
            self.reg_esp_trib,
            _SPECIAL_TAX_REGIMES,
            "Special tax regime",
        )
        _validate_code(
            self.trib_issqn,
            _ISSQN_TAXATION_OPTIONS,
            "ISSQN taxation",
        )
        _validate_code(
            self.tp_ret_issqn,
            _ISSQN_WITHHOLDING_OPTIONS,
            "ISSQN withholding",
        )
        _validate_code(
            self.ind_tot_trib,
            _TOTAL_TAX_INDICATORS,
            "Total tax indicator",
        )
        object.__setattr__(self, "_issued_at_text", issued_at_text)
        object.__setattr__(self, "_service_amount_text", service_amount_text)

    def __repr__(self) -> str:
        """Return a representation that does not disclose fiscal data."""
        return "RestrictedDpsDraft(<redacted>)"

    def __str__(self) -> str:
        """Avoid treating the draft as an implicit document serialization."""
        return "RestrictedDpsDraft(<redacted>)"


def build_unsigned_dps(draft: RestrictedDpsDraft) -> bytes:
    """Serialize a validated draft as deterministic unsigned UTF-8 XML bytes."""
    if type(draft) is not RestrictedDpsDraft:
        raise DomainValidationError("DPS build input must be a RestrictedDpsDraft.")

    identity = DpsIdentity.build(
        municipality=draft.issue_municipality,
        federal_tax_id=draft.issuer_tax_id,
        series=draft.series,
        number=draft.number,
    )
    root = ElementTree.Element(
        "DPS",
        {"xmlns": _NFSE_NAMESPACE, "versao": _SCHEMA_VERSION},
    )
    information = ElementTree.SubElement(root, "infDPS", {"Id": identity.value})
    _add_text(information, "tpAmb", _RESTRICTED_ENVIRONMENT)
    _add_text(information, "dhEmi", draft._issued_at_text)
    _add_text(information, "verAplic", draft.application_version)
    _add_text(information, "serie", draft.series.value)
    _add_text(information, "nDPS", str(draft.number.value))
    _add_text(information, "dCompet", str(draft.competence))
    _add_text(information, "tpEmit", _ISSUER_TYPE_PROVIDER)
    _add_text(information, "cLocEmi", draft.issue_municipality.value)

    provider = ElementTree.SubElement(information, "prest")
    _add_text(provider, "CNPJ", draft.issuer_tax_id.value)
    tax_regime = ElementTree.SubElement(provider, "regTrib")
    _add_text(tax_regime, "opSimpNac", draft.op_simp_nac)
    _add_text(tax_regime, "regEspTrib", draft.reg_esp_trib)

    service = ElementTree.SubElement(information, "serv")
    service_location = ElementTree.SubElement(service, "locPrest")
    _add_text(
        service_location,
        "cLocPrestacao",
        draft.service_municipality.value,
    )
    service_code = ElementTree.SubElement(service, "cServ")
    _add_text(service_code, "cTribNac", draft.national_service_code)
    _add_text(service_code, "xDescServ", draft.service_description)

    values = ElementTree.SubElement(information, "valores")
    provided_service = ElementTree.SubElement(values, "vServPrest")
    _add_text(provided_service, "vServ", draft._service_amount_text)
    taxation = ElementTree.SubElement(values, "trib")
    municipal_tax = ElementTree.SubElement(taxation, "tribMun")
    _add_text(municipal_tax, "tribISSQN", draft.trib_issqn)
    _add_text(municipal_tax, "tpRetISSQN", draft.tp_ret_issqn)
    total_tax = ElementTree.SubElement(taxation, "totTrib")
    _add_text(total_tax, "indTotTrib", draft.ind_tot_trib)

    return cast(
        bytes,
        ElementTree.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        ),
    )


def _require_exact_type(value: object, expected: type[object], message: str) -> None:
    if type(value) is not expected:
        raise DomainValidationError(message)


def _validate_code(value: object, allowed: frozenset[str], label: str) -> None:
    if type(value) is not str or value not in allowed:
        raise DomainValidationError(
            f"{label} is unsupported by the restricted profile."
        )


def _validate_application_version(value: object) -> None:
    if type(value) is not str:
        raise DomainValidationError("Application version must be a string.")
    if not 1 <= len(value) <= 20:
        raise DomainValidationError(
            "Application version must contain 1 to 20 characters."
        )
    if any(not 0x20 <= ord(character) <= 0xFF for character in value):
        raise DomainValidationError(
            "Application version contains characters outside TSString."
        )
    if ord(value[0]) < 0x21 or ord(value[-1]) < 0x21:
        raise DomainValidationError(
            "Application version cannot start or end with whitespace."
        )


def _validate_service_code(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 6
        or not value.isascii()
        or not value.isdecimal()
    ):
        raise DomainValidationError(
            "National service code must contain exactly 6 ASCII digits."
        )


def _validate_service_description(value: object) -> None:
    if type(value) is not str:
        raise DomainValidationError("Service description must be a string.")
    if not 1 <= len(value) <= 2000 or all(
        character in _XSD_WHITESPACE for character in value
    ):
        raise DomainValidationError(
            "Service description must contain 1 to 2000 characters and text."
        )
    if "\r" in value:
        raise DomainValidationError("Service description cannot contain CR characters.")
    if any(not _is_xml_10_character(character) for character in value):
        raise DomainValidationError(
            "Service description contains a character forbidden by XML 1.0."
        )


def _is_xml_10_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint in {0x09, 0x0A, 0x0D}
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def _format_issued_at(value: object) -> str:
    if type(value) is not datetime:
        raise DomainValidationError("Issue timestamp must be a datetime.")
    if value.tzinfo is None:
        raise DomainValidationError("Issue timestamp must include a UTC offset.")
    if value.microsecond != 0:
        raise DomainValidationError("Issue timestamp cannot contain microseconds.")
    if not 2000 <= value.year <= 2099:
        raise DomainValidationError(
            "Issue timestamp year must fit the restricted TSDateTimeUTC profile."
        )

    offset = value.utcoffset()
    if offset is None:
        raise DomainValidationError("Issue timestamp must include a UTC offset.")
    seconds = int(offset.total_seconds())
    if offset != timedelta(seconds=seconds) or seconds % 3600 != 0:
        raise DomainValidationError("Issue timestamp offset must use whole hours.")
    hours = seconds // 3600
    if not -11 <= hours <= 12:
        raise DomainValidationError(
            "Issue timestamp offset is outside the restricted profile."
        )
    sign = "+" if hours >= 0 else "-"
    return f"{value:%Y-%m-%dT%H:%M:%S}{sign}{abs(hours):02d}:00"


def _format_amount(value: object) -> str:
    if type(value) is not Decimal:
        raise DomainValidationError("Service amount must be a Decimal.")
    if not value.is_finite():
        raise DomainValidationError("Service amount must be finite.")
    if value.is_signed():
        raise DomainValidationError("Service amount cannot be negative or signed zero.")

    parts = value.as_tuple()
    digits = list(parts.digits)
    exponent = parts.exponent
    if not isinstance(exponent, int):
        raise DomainValidationError("Service amount must be finite.")
    if not any(digits):
        return "0.00"

    while exponent < -2 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    if exponent < -2:
        raise DomainValidationError(
            "Service amount must be exactly representable with two decimal places."
        )

    integer_digits = max(len(digits) + exponent, 0)
    if integer_digits > _MAX_AMOUNT_INTEGER_DIGITS:
        raise DomainValidationError("Service amount exceeds the restricted maximum.")

    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        integer = coefficient + ("0" * exponent)
        fraction = ""
    else:
        split = len(coefficient) + exponent
        if split > 0:
            integer = coefficient[:split]
            fraction = coefficient[split:]
        else:
            integer = "0"
            fraction = ("0" * -split) + coefficient
    return f"{integer}.{fraction.ljust(2, '0')}"


def _add_text(parent: ElementTree.Element, name: str, value: str) -> None:
    ElementTree.SubElement(parent, name).text = value
