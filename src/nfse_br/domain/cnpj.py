"""Explicit CNPJ check-digit validation."""

from __future__ import annotations

from collections.abc import Sequence

from nfse_br.domain.errors import DomainValidationError
from nfse_br.domain.federal_tax_id import FederalTaxId, FederalTaxIdKind

__all__ = ["validate_cnpj_check_digits"]

_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_ALL_ZERO_CNPJ = "0" * 14


def validate_cnpj_check_digits(identifier: FederalTaxId) -> None:
    """Validate the two numeric CNPJ check digits without changing the value."""
    if type(identifier) is not FederalTaxId:
        raise DomainValidationError(
            "CNPJ check-digit validation requires a FederalTaxId."
        )
    if identifier.kind is not FederalTaxIdKind.CNPJ:
        raise DomainValidationError(
            "CNPJ check-digit validation requires a CNPJ identifier."
        )

    value = identifier.value
    base = value[:12]
    provided_digits = value[12:]
    if not all("0" <= character <= "9" for character in provided_digits):
        raise DomainValidationError("CNPJ check digits must be ASCII digits.")
    if value == _ALL_ZERO_CNPJ:
        raise DomainValidationError("The all-zero CNPJ is not accepted.")

    base_values = tuple(_calculation_value(character) for character in base)
    first_digit = _calculate_digit(base_values, _FIRST_WEIGHTS)
    second_digit = _calculate_digit(
        (*base_values, first_digit),
        _SECOND_WEIGHTS,
    )
    if provided_digits != f"{first_digit}{second_digit}":
        raise DomainValidationError("CNPJ check digits are invalid.")


def _calculation_value(character: str) -> int:
    if not (
        "0" <= character <= "9" or "A" <= character <= "Z"
    ):  # defensive against a broken FederalTaxId invariant
        raise DomainValidationError("CNPJ base contains an invalid character.")
    return ord(character) - 48


def _calculate_digit(values: Sequence[int], weights: Sequence[int]) -> int:
    remainder = (
        sum(value * weight for value, weight in zip(values, weights, strict=True)) % 11
    )
    return 0 if remainder in (0, 1) else 11 - remainder
