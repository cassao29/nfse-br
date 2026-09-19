"""Tests for explicit CPF check-digit validation."""

from __future__ import annotations

import traceback
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, FederalTaxId
from nfse_br.domain.cpf import validate_cpf_check_digits


@pytest.mark.parametrize(
    ("value", "first_sum", "first_remainder", "second_sum", "second_remainder"),
    [
        ("11144477735", 162, 8, 204, 6),
        ("12345678909", 210, 1, 255, 2),
        ("00000000191", 2, 2, 21, 10),
        ("00000000604", 12, 1, 18, 7),
        ("00000001406", 11, 0, 16, 5),
        ("00000001830", 19, 8, 34, 1),
        ("00000001910", 21, 10, 33, 0),
    ],
)
def test_accepts_independently_calculated_vectors(
    value: str,
    first_sum: int,
    first_remainder: int,
    second_sum: int,
    second_remainder: int,
) -> None:
    # Fixed sums and remainders make the expectations independent and auditable.
    assert first_sum % 11 == first_remainder
    assert second_sum % 11 == second_remainder

    validate_cpf_check_digits(FederalTaxId.cpf(value))


@pytest.mark.parametrize("value", ["11144477745", "11144477736"])
def test_rejects_an_isolated_change_to_each_check_digit(value: str) -> None:
    with pytest.raises(DomainValidationError, match="check digits are invalid"):
        validate_cpf_check_digits(FederalTaxId.cpf(value))


@pytest.mark.parametrize(
    "value",
    [
        "00000000000",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999",
    ],
)
def test_rejects_each_repeated_digit_sequence_as_local_policy(value: str) -> None:
    with pytest.raises(DomainValidationError, match="Repeated-digit"):
        validate_cpf_check_digits(FederalTaxId.cpf(value))


def test_rejects_cnpj_and_runtime_types_without_coercion() -> None:
    with pytest.raises(DomainValidationError, match="CPF identifier"):
        validate_cpf_check_digits(FederalTaxId.cnpj("12ABC34501DE35"))

    for value in ("11144477735", 111_444_777_35, True, None, object()):
        with pytest.raises(DomainValidationError, match="FederalTaxId"):
            validate_cpf_check_digits(cast(FederalTaxId, value))


def test_preserves_identifier_after_success_and_rejection() -> None:
    valid = FederalTaxId.cpf("11144477735")
    invalid = FederalTaxId.cpf("12345678901")
    valid_snapshot = (valid.kind, valid.value, hash(valid))
    invalid_snapshot = (invalid.kind, invalid.value, hash(invalid))

    validate_cpf_check_digits(valid)
    with pytest.raises(DomainValidationError):
        validate_cpf_check_digits(invalid)

    assert (valid.kind, valid.value, hash(valid)) == valid_snapshot
    assert (invalid.kind, invalid.value, hash(invalid)) == invalid_snapshot


def test_lexical_constructor_remains_independent_from_check_digits() -> None:
    identifier = FederalTaxId.cpf("12345678901")

    assert identifier.value == "12345678901"
    with pytest.raises(DomainValidationError):
        validate_cpf_check_digits(identifier)


def test_errors_do_not_disclose_identifier() -> None:
    sensitive_value = "12345678901"
    identifier = FederalTaxId.cpf(sensitive_value)

    try:
        validate_cpf_check_digits(identifier)
    except DomainValidationError as error:
        rendered = "".join(traceback.format_exception(error))
        assert sensitive_value not in str(error)
        assert sensitive_value not in repr(error)
        assert sensitive_value not in rendered
    else:
        raise AssertionError("Invalid CPF check digits were unexpectedly accepted")


def test_calls_are_independent_after_a_rejection() -> None:
    valid = FederalTaxId.cpf("11144477735")
    invalid = FederalTaxId.cpf("11144477736")

    validate_cpf_check_digits(valid)
    with pytest.raises(DomainValidationError):
        validate_cpf_check_digits(invalid)
    validate_cpf_check_digits(valid)
