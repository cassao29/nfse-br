"""Competence date domain values."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Self

from nfse_br.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class CompetenceDate:
    """An immutable civil date used as the NFS-e competence date."""

    value: date

    def __post_init__(self) -> None:
        """Reject datetime values and non-date objects."""
        if isinstance(self.value, datetime) or not isinstance(self.value, date):
            raise DomainValidationError(
                "Competence date must be a date without time information."
            )

    @classmethod
    def from_iso(cls, value: str) -> Self:
        """Create a competence date from an ISO ``YYYY-MM-DD`` string."""
        if not isinstance(value, str):
            raise DomainValidationError("Competence date must be an ISO date string.")

        digits = value.replace("-", "")
        if (
            len(value) != 10
            or value[4:5] != "-"
            or value[7:8] != "-"
            or not digits.isascii()
            or not digits.isdecimal()
            or len(digits) != 8
        ):
            raise DomainValidationError(
                "Competence date must use the YYYY-MM-DD format."
            )

        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise DomainValidationError(
                "Competence date is not a valid date."
            ) from error
        return cls(parsed)

    def __str__(self) -> str:
        """Return the date in ISO ``YYYY-MM-DD`` format."""
        return self.value.isoformat()
