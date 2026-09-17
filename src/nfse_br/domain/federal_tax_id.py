"""Brazilian federal tax identifier values."""

from dataclasses import dataclass
from enum import Enum
from typing import Self

from nfse_br.domain.errors import DomainValidationError


class FederalTaxIdKind(Enum):
    """The supported kinds of Brazilian federal tax identifiers."""

    CPF = "CPF"
    CNPJ = "CNPJ"


@dataclass(frozen=True, slots=True)
class FederalTaxId:
    """An immutable, lexically validated CPF or CNPJ."""

    kind: FederalTaxIdKind
    value: str

    def __post_init__(self) -> None:
        """Validate and normalize the identifier value."""
        if self.kind is FederalTaxIdKind.CPF:
            self._validate_cpf(self.value)
            return

        if self.kind is FederalTaxIdKind.CNPJ:
            normalized = self._normalize_cnpj(self.value)
            object.__setattr__(self, "value", normalized)
            return

        raise DomainValidationError("Unsupported federal tax identifier kind.")

    @classmethod
    def cpf(cls, value: str) -> Self:
        """Create a CPF from exactly 11 ASCII digits."""
        return cls(kind=FederalTaxIdKind.CPF, value=value)

    @classmethod
    def cnpj(cls, value: str) -> Self:
        """Create a CNPJ from 14 ASCII alphanumeric characters."""
        return cls(kind=FederalTaxIdKind.CNPJ, value=value)

    def __str__(self) -> str:
        """Return the normalized, unmasked identifier value."""
        return self.value

    def __repr__(self) -> str:
        """Return a representation that does not disclose the identifier."""
        return f"FederalTaxId(kind={self.kind.name}, value=<redacted>)"

    @staticmethod
    def _validate_cpf(value: str) -> None:
        if type(value) is not str:
            raise DomainValidationError("CPF must be provided as a string.")
        if len(value) != 11 or not value.isascii() or not value.isdecimal():
            raise DomainValidationError("CPF must contain exactly 11 ASCII digits.")

    @staticmethod
    def _normalize_cnpj(value: str) -> str:
        if type(value) is not str:
            raise DomainValidationError("CNPJ must be provided as a string.")
        if len(value) != 14 or not value.isascii() or not value.isalnum():
            raise DomainValidationError(
                "CNPJ must contain exactly 14 ASCII alphanumeric characters."
            )
        return value.upper()
