"""Tests for DPS series values."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError
from nfse_br.dps import DpsSeries


class SeriesString(str):
    """A string subclass that must not override lexical validation."""


class StringConvertible:
    """An object that must not be coerced into a DPS series."""

    def __str__(self) -> str:
        return "123"


@pytest.mark.parametrize(
    ("value", "component"),
    [
        ("0", "00000"),
        ("1", "00001"),
        ("123", "00123"),
        ("9999", "09999"),
        ("0001", "00001"),
        ("00000", "00000"),
        ("89999", "89999"),
    ],
)
def test_series_accepts_working_boundaries(value: str, component: str) -> None:
    series = DpsSeries(value)

    assert series.value == value
    assert str(series) == value
    assert series.identity_component == component


@pytest.mark.parametrize(
    "value",
    [
        "",
        "90000",
        "90001",
        "99999",
        "123456",
        "-1",
        "12A",
        "12.3",
        "１２３",
        " 123",
        "123 ",
    ],
)
def test_series_rejects_values_outside_working_contract(value: str) -> None:
    with pytest.raises(DomainValidationError, match="working numeric series"):
        DpsSeries(value)


@pytest.mark.parametrize("value", [None, 123, True, 1.0, b"123", StringConvertible()])
def test_series_rejects_non_string_values(value: object) -> None:
    with pytest.raises(DomainValidationError, match="string"):
        DpsSeries(cast(str, value))


def test_series_rejects_string_subclasses() -> None:
    with pytest.raises(DomainValidationError, match="string"):
        DpsSeries(SeriesString("123"))


def test_series_value_semantics_preserve_lexical_form() -> None:
    short = DpsSeries("123")
    padded = DpsSeries("00123")

    assert short != padded
    assert hash(short) != hash(padded)
    assert short.identity_component == padded.identity_component == "00123"


def test_series_is_immutable() -> None:
    series = DpsSeries("123")

    with pytest.raises(FrozenInstanceError):
        series.__setattr__("value", "124")
