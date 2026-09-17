"""Tests for Brazilian federal tax identifier values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, FederalTaxId, FederalTaxIdKind


class StringConvertible:
    """An object that must not be coerced into an identifier."""

    def __str__(self) -> str:
        return "12345678901"


class TaxIdString(str):
    """A string subclass that must not override lexical validation."""


def test_cpf_preserves_kind_value_and_string_representation() -> None:
    tax_id = FederalTaxId.cpf("12345678901")

    assert tax_id.kind is FederalTaxIdKind.CPF
    assert tax_id.value == "12345678901"
    assert str(tax_id) == "12345678901"


@pytest.mark.parametrize(
    "value",
    [
        "1234567890",
        "123456789012",
        "1234567890A",
        "123.4567890",
        "1234567890 ",
        "１２３４５６７８９０１",
    ],
)
def test_cpf_rejects_invalid_lexical_values(value: str) -> None:
    with pytest.raises(DomainValidationError, match="11 ASCII digits"):
        FederalTaxId.cpf(value)


@pytest.mark.parametrize(
    "value",
    [None, b"12345678901", 12345678901, 12345678901.0, True, StringConvertible()],
)
def test_cpf_rejects_non_string_value(value: object) -> None:
    with pytest.raises(DomainValidationError, match="string"):
        FederalTaxId.cpf(cast(str, value))


def test_numeric_cnpj_is_accepted() -> None:
    tax_id = FederalTaxId.cnpj("12345678000199")

    assert tax_id.kind is FederalTaxIdKind.CNPJ
    assert tax_id.value == "12345678000199"
    assert str(tax_id) == "12345678000199"


def test_alphanumeric_cnpj_is_normalized_to_uppercase() -> None:
    tax_id = FederalTaxId.cnpj("12abc345678901")

    assert tax_id.value == "12ABC345678901"
    assert tax_id == FederalTaxId.cnpj("12ABC345678901")


@pytest.mark.parametrize(
    "value",
    [
        "12ABC34567890",
        "12ABC3456789012",
        "12.ABC34567890",
        "12 ABC34567890",
        "12ÁBC345678901",
        "１２ABC345678901",
    ],
)
def test_cnpj_rejects_invalid_lexical_values(value: str) -> None:
    with pytest.raises(DomainValidationError, match="14 ASCII alphanumeric"):
        FederalTaxId.cnpj(value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        b"12345678000199",
        12345678000199,
        12345678000199.0,
        False,
        StringConvertible(),
    ],
)
def test_cnpj_rejects_non_string_value(value: object) -> None:
    with pytest.raises(DomainValidationError, match="string"):
        FederalTaxId.cnpj(cast(str, value))


@pytest.mark.parametrize(
    ("factory", "value"),
    [
        (FederalTaxId.cpf, TaxIdString("12345678901")),
        (FederalTaxId.cnpj, TaxIdString("12345678000199")),
    ],
)
def test_federal_tax_id_rejects_string_subclasses(
    factory: Callable[[str], FederalTaxId], value: str
) -> None:
    with pytest.raises(DomainValidationError, match="string"):
        factory(value)


@pytest.mark.parametrize(
    ("factory", "invalid_value"),
    [
        (FederalTaxId.cpf, "1234567890A"),
        (FederalTaxId.cnpj, "12ABC34567890-"),
    ],
)
def test_validation_errors_do_not_disclose_federal_tax_ids(
    factory: Callable[[str], FederalTaxId], invalid_value: str
) -> None:
    with pytest.raises(DomainValidationError) as exc_info:
        factory(invalid_value)

    assert invalid_value not in str(exc_info.value)


@pytest.mark.parametrize(
    "tax_id",
    [
        FederalTaxId.cpf("12345678901"),
        FederalTaxId.cnpj("12ABC345678901"),
    ],
)
def test_federal_tax_id_repr_redacts_the_full_value(tax_id: FederalTaxId) -> None:
    assert tax_id.value not in repr(tax_id)
    assert "<redacted>" in repr(tax_id)


def test_federal_tax_id_rejects_unknown_kind() -> None:
    with pytest.raises(DomainValidationError, match="Unsupported"):
        FederalTaxId(
            kind=cast(FederalTaxIdKind, "OTHER"),
            value="12345678901",
        )


def test_federal_tax_id_is_immutable() -> None:
    tax_id = FederalTaxId.cpf("12345678901")

    with pytest.raises(FrozenInstanceError):
        tax_id.__setattr__("value", "10987654321")
