"""Tests for municipality code values."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, MunicipalityCode


class MunicipalityString(str):
    """A string subclass that must not override lexical validation."""


class StringConvertible:
    """An object that must not be coerced into a municipality code."""

    def __str__(self) -> str:
        return "2927408"


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


@pytest.mark.parametrize(
    "value", [None, 2927408, True, 2927408.0, b"2927408", StringConvertible()]
)
def test_municipality_code_rejects_non_string_input(value: object) -> None:
    with pytest.raises(DomainValidationError, match="string"):
        MunicipalityCode(cast(str, value))


def test_municipality_code_rejects_string_subclasses() -> None:
    with pytest.raises(DomainValidationError, match="string"):
        MunicipalityCode(MunicipalityString("2927408"))


def test_municipality_code_is_immutable() -> None:
    code = MunicipalityCode("2927408")

    with pytest.raises(FrozenInstanceError):
        code.__setattr__("value", "3550308")
