"""Tests for structural DPS number values."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from typing import cast

import pytest

from nfse_br.domain import DomainValidationError
from nfse_br.dps import DpsNumber


class NumberInt(int):
    """An integer subclass that must not override numeric boundaries."""


class IndexConvertible:
    """An object that must not be coerced into a DPS number."""

    def __index__(self) -> int:
        return 42


@pytest.mark.parametrize(
    ("value", "component"),
    [
        (1, "000000000000001"),
        (42, "000000000000042"),
        (999_999_999_999_999, "999999999999999"),
    ],
)
def test_number_accepts_structural_boundaries(value: int, component: str) -> None:
    number = DpsNumber(value)

    assert number.value == value
    assert str(number) == str(value)
    assert number.identity_component == component
    assert len(number.identity_component) == 15


@pytest.mark.parametrize("value", [-1, 0, 1_000_000_000_000_000])
def test_number_rejects_values_outside_structural_range(value: int) -> None:
    with pytest.raises(DomainValidationError, match="between 1 and"):
        DpsNumber(value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        42.0,
        "42",
        b"42",
        Decimal("42"),
        NumberInt(42),
        IndexConvertible(),
    ],
)
def test_number_rejects_non_builtin_integers(value: object) -> None:
    with pytest.raises(DomainValidationError, match="integer"):
        DpsNumber(cast(int, value))


def test_number_has_immutable_value_semantics() -> None:
    number = DpsNumber(42)

    assert number == DpsNumber(42)
    assert hash(number) == hash(DpsNumber(42))

    with pytest.raises(FrozenInstanceError):
        number.__setattr__("value", 43)
