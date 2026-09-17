"""Municipality domain values."""

from dataclasses import dataclass

from nfse_br.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class MunicipalityCode:
    """An immutable seven-digit IBGE municipality code."""

    value: str

    def __post_init__(self) -> None:
        """Validate the lexical representation without performing a lookup."""
        if type(self.value) is not str:
            raise DomainValidationError(
                "Municipality code must be provided as a string."
            )
        if (
            len(self.value) != 7
            or not self.value.isascii()
            or not self.value.isdecimal()
        ):
            raise DomainValidationError(
                "Municipality code must contain exactly 7 ASCII digits."
            )

    def __str__(self) -> str:
        """Return the municipality code with leading zeros preserved."""
        return self.value
