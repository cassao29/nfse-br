"""Tests for explicit CNPJ check-digit validation."""

from __future__ import annotations

import traceback
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, FederalTaxId
from nfse_br.domain.cnpj import validate_cnpj_check_digits


def test_accepts_the_official_alphanumeric_vector() -> None:
    # Receita manual pp. 3-4: sums 459 and 424, remainders 8 and 6, DVs 3 and 5.
    identifier = FederalTaxId.cnpj("12ABC34501DE35")

    validate_cnpj_check_digits(identifier)


@pytest.mark.parametrize(
    "value",
    [
        # Independently calculated: sums 102/120, remainders 3/10, DVs 8/1.
        "11222333000181",
        # Independently calculated: sums 159/207, remainders 5/9, DVs 6/2.
        "AB000000000162",
        # Leading-zero base: sums 2/21, remainders 2/10, DVs 9/1.
        "00000000000191",
    ],
)
def test_accepts_independently_calculated_vectors(value: str) -> None:
    validate_cnpj_check_digits(FederalTaxId.cnpj(value))


@pytest.mark.parametrize(
    ("value", "first_sum", "first_remainder", "second_sum", "second_remainder"),
    [
        ("00000000001406", 11, 0, 16, 5),
        ("00000000000604", 12, 1, 18, 7),
        ("00000000001910", 21, 10, 33, 0),
        ("00000000001830", 19, 8, 34, 1),
    ],
)
def test_covers_modulo_remainder_boundaries(
    value: str,
    first_sum: int,
    first_remainder: int,
    second_sum: int,
    second_remainder: int,
) -> None:
    # The explicit sums/remainders make these fixed vectors auditable independently.
    assert first_sum % 11 == first_remainder
    assert second_sum % 11 == second_remainder

    validate_cnpj_check_digits(FederalTaxId.cnpj(value))


@pytest.mark.parametrize("value", ["12ABC34501DE45", "12ABC34501DE36"])
def test_rejects_an_isolated_change_to_each_check_digit(value: str) -> None:
    with pytest.raises(DomainValidationError, match="check digits are invalid"):
        validate_cnpj_check_digits(FederalTaxId.cnpj(value))


def test_rejects_alphabetic_check_digit_after_lexical_acceptance() -> None:
    identifier = FederalTaxId.cnpj("12ABC34501DE3A")

    with pytest.raises(DomainValidationError, match="ASCII digits"):
        validate_cnpj_check_digits(identifier)


def test_rejects_all_zero_cnpj_as_an_explicit_additional_rule() -> None:
    identifier = FederalTaxId.cnpj("00000000000000")

    with pytest.raises(DomainValidationError, match="all-zero"):
        validate_cnpj_check_digits(identifier)


@pytest.mark.parametrize(
    "value",
    ["12ABC34501DE35", "12abc34501de35"],
)
def test_uses_the_primitive_normalized_value(value: str) -> None:
    identifier = FederalTaxId.cnpj(value)

    validate_cnpj_check_digits(identifier)
    assert identifier.value == "12ABC34501DE35"


def test_rejects_cpf_and_runtime_types_without_coercion() -> None:
    with pytest.raises(DomainValidationError, match="CNPJ identifier"):
        validate_cnpj_check_digits(FederalTaxId.cpf("12345678901"))

    for value in ("12ABC34501DE35", 12_345, True, None, object()):
        with pytest.raises(DomainValidationError, match="FederalTaxId"):
            validate_cnpj_check_digits(cast(FederalTaxId, value))


def test_preserves_identifier_after_success_and_rejection() -> None:
    valid = FederalTaxId.cnpj("12ABC34501DE35")
    invalid = FederalTaxId.cnpj("12ABC6780001Z0")
    valid_snapshot = (valid.kind, valid.value, hash(valid))
    invalid_snapshot = (invalid.kind, invalid.value, hash(invalid))

    validate_cnpj_check_digits(valid)
    with pytest.raises(DomainValidationError):
        validate_cnpj_check_digits(invalid)

    assert (valid.kind, valid.value, hash(valid)) == valid_snapshot
    assert (invalid.kind, invalid.value, hash(invalid)) == invalid_snapshot


def test_lexical_constructor_remains_independent_from_check_digits() -> None:
    identifier = FederalTaxId.cnpj("12ABC6780001Z0")

    assert identifier.value == "12ABC6780001Z0"
    with pytest.raises(DomainValidationError):
        validate_cnpj_check_digits(identifier)


def test_errors_do_not_disclose_identifier() -> None:
    sensitive_value = "12ABC6780001Z0"
    identifier = FederalTaxId.cnpj(sensitive_value)

    try:
        validate_cnpj_check_digits(identifier)
    except DomainValidationError as error:
        rendered = "".join(traceback.format_exception(error))
        assert sensitive_value not in str(error)
        assert sensitive_value not in repr(error)
        assert sensitive_value not in rendered
    else:
        raise AssertionError("Invalid CNPJ check digits were unexpectedly accepted")


def test_calls_are_independent_after_a_rejection() -> None:
    valid = FederalTaxId.cnpj("12ABC34501DE35")
    invalid = FederalTaxId.cnpj("12ABC34501DE36")

    validate_cnpj_check_digits(valid)
    with pytest.raises(DomainValidationError):
        validate_cnpj_check_digits(invalid)
    validate_cnpj_check_digits(valid)
