"""Tests for municipality code values."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, MunicipalityCode


def test_municipality_code_preserves_leading_zeros() -> None:
    code = MunicipalityCode("0123456")

    assert code.value == "0123456"
    assert str(code) == "0123456"
    assert code == MunicipalityCode("0123456")


@pytest.mark.parametrize(
    "value",
    [
        "123456",
        "12345678",
        "123A567",
        "123.567",
        "123 567",
        "１２３４５６７",
    ],
)
def test_municipality_code_rejects_invalid_lexical_values(value: str) -> None:
    with pytest.raises(DomainValidationError, match="7 ASCII digits"):
        MunicipalityCode(value)


def test_municipality_code_rejects_integer_input() -> None:
    with pytest.raises(DomainValidationError, match="string"):
        MunicipalityCode(cast(str, 2927408))


def test_municipality_code_is_immutable() -> None:
    code = MunicipalityCode("2927408")

    with pytest.raises(FrozenInstanceError):
        code.__setattr__("value", "3550308")
