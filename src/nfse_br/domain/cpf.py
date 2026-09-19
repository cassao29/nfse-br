"""Explicit CPF check-digit validation."""

from __future__ import annotations

from collections.abc import Sequence

from nfse_br.domain.errors import DomainValidationError
from nfse_br.domain.federal_tax_id import FederalTaxId, FederalTaxIdKind

__all__ = ["validate_cpf_check_digits"]

_FIRST_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_WEIGHTS = (11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
_REPEATED_DIGIT_CPFS = frozenset(str(digit) * 11 for digit in range(10))


def validate_cpf_check_digits(identifier: FederalTaxId) -> None:
    """Validate the two CPF check digits without changing the value."""
    if type(identifier) is not FederalTaxId:
        raise DomainValidationError(
            "CPF check-digit validation requires a FederalTaxId."
        )
    if identifier.kind is not FederalTaxIdKind.CPF:
        raise DomainValidationError(
            "CPF check-digit validation requires a CPF identifier."
        )

    value = identifier.value
    if value in _REPEATED_DIGIT_CPFS:
        raise DomainValidationError("Repeated-digit CPFs are not accepted.")

    base_values = tuple(int(character) for character in value[:9])
    first_digit = _calculate_digit(base_values, _FIRST_WEIGHTS)
    second_digit = _calculate_digit(
        (*base_values, first_digit),
        _SECOND_WEIGHTS,
    )
    if value[9:] != f"{first_digit}{second_digit}":
        raise DomainValidationError("CPF check digits are invalid.")


def _calculate_digit(values: Sequence[int], weights: Sequence[int]) -> int:
    remainder = (
        sum(value * weight for value, weight in zip(values, weights, strict=True)) % 11
    )
    return 0 if remainder in (0, 1) else 11 - remainder
