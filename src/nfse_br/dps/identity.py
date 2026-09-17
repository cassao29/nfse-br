"""Deterministic identity for the working local DPS contract."""

import re
from dataclasses import dataclass, field
from typing import Self

from nfse_br.domain import (
    DomainValidationError,
    FederalTaxId,
    FederalTaxIdKind,
    MunicipalityCode,
)
from nfse_br.dps.number import DpsNumber
from nfse_br.dps.series import DpsSeries

_WORKING_DPS_ID_PATTERN = re.compile(
    r"DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"
)


@dataclass(frozen=True, slots=True, init=False)
class DpsIdentity:
    """An immutable identity composed under the working local DPS contract."""

    municipality: MunicipalityCode = field(compare=False)
    federal_tax_id: FederalTaxId = field(compare=False)
    series: DpsSeries = field(compare=False)
    number: DpsNumber = field(compare=False)
    value: str

    def __init__(self) -> None:
        """Prevent partially initialized identities outside ``build``."""
        raise DomainValidationError(
            "DPS identity must be created with DpsIdentity.build()."
        )

    @classmethod
    def build(
        cls,
        *,
        municipality: MunicipalityCode,
        federal_tax_id: FederalTaxId,
        series: DpsSeries,
        number: DpsNumber,
    ) -> Self:
        """Build a deterministic 45-position DPS identity."""
        cls._validate_component_types(
            municipality=municipality,
            federal_tax_id=federal_tax_id,
            series=series,
            number=number,
        )

        inscription_type = cls._inscription_type(federal_tax_id.kind)
        federal_document = cls._federal_document_component(federal_tax_id)
        value = (
            "DPS"
            + municipality.value
            + inscription_type
            + federal_document
            + series.identity_component
            + number.identity_component
        )
        if len(value) != 45 or _WORKING_DPS_ID_PATTERN.fullmatch(value) is None:
            raise DomainValidationError(
                "Composed DPS identity violates the working local contract."
            )

        identity = object.__new__(cls)
        object.__setattr__(identity, "municipality", municipality)
        object.__setattr__(identity, "federal_tax_id", federal_tax_id)
        object.__setattr__(identity, "series", series)
        object.__setattr__(identity, "number", number)
        object.__setattr__(identity, "value", value)
        return identity

    @property
    def inscription_type(self) -> str:
        """Return the inscription type derived from the federal identifier kind."""
        return self._inscription_type(self.federal_tax_id.kind)

    def __str__(self) -> str:
        """Return the complete DPS identity value explicitly."""
        return self.value

    def __repr__(self) -> str:
        """Return a representation that redacts federal and composed identities."""
        return (
            "DpsIdentity("
            f"municipality={self.municipality}, "
            "federal_tax_id=<redacted>, "
            f"series={self.series}, "
            f"number={self.number}, "
            "value=<redacted>)"
        )

    @staticmethod
    def _validate_component_types(
        *,
        municipality: MunicipalityCode,
        federal_tax_id: FederalTaxId,
        series: DpsSeries,
        number: DpsNumber,
    ) -> None:
        if type(municipality) is not MunicipalityCode:
            raise DomainValidationError(
                "DPS identity municipality must be a MunicipalityCode."
            )
        if type(federal_tax_id) is not FederalTaxId:
            raise DomainValidationError(
                "DPS identity federal identifier must be a FederalTaxId."
            )
        if type(series) is not DpsSeries:
            raise DomainValidationError("DPS identity series must be a DpsSeries.")
        if type(number) is not DpsNumber:
            raise DomainValidationError("DPS identity number must be a DpsNumber.")

    @staticmethod
    def _inscription_type(kind: FederalTaxIdKind) -> str:
        if kind is FederalTaxIdKind.CPF:
            return "1"
        if kind is FederalTaxIdKind.CNPJ:
            return "2"
        raise DomainValidationError(
            "DPS identity federal identifier kind is unsupported."
        )

    @staticmethod
    def _federal_document_component(federal_tax_id: FederalTaxId) -> str:
        if federal_tax_id.kind is FederalTaxIdKind.CPF:
            return federal_tax_id.value.zfill(14)
        if federal_tax_id.kind is FederalTaxIdKind.CNPJ:
            return federal_tax_id.value
        raise DomainValidationError(
            "DPS identity federal identifier kind is unsupported."
        )
