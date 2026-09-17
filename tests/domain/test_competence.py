"""Tests for competence date values."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from typing import cast

import pytest

from nfse_br.domain import CompetenceDate, DomainValidationError


class IsoDateString(str):
    """A string subclass that must not override lexical validation."""


class StringConvertible:
    """An object that must not be coerced into an ISO date."""

    def __str__(self) -> str:
        return "2026-09-17"


def test_competence_date_preserves_value_and_uses_iso_string() -> None:
    value = date(2026, 9, 17)
    competence = CompetenceDate(value)

    assert competence.value == value
    assert str(competence) == "2026-09-17"
    assert competence == CompetenceDate(value)


def test_competence_date_can_be_created_from_iso() -> None:
    competence = CompetenceDate.from_iso("2026-09-17")

    assert competence.value == date(2026, 9, 17)


@pytest.mark.parametrize(
    "value",
    [
        "2026-02-30",
        "20260917",
        "2026-W38-4",
        "2026-260",
        "17-09-2026",
        "2026-9-17",
        " 2026-09-17",
        "2026-09-17 ",
        "2026-09-17\n",
        "２０２６-０９-１７",
    ],
)
def test_competence_date_rejects_invalid_iso_values(value: str) -> None:
    with pytest.raises(DomainValidationError):
        CompetenceDate.from_iso(value)


@pytest.mark.parametrize(
    "value",
    [None, b"2026-09-17", 20260917, 2026.0917, True, StringConvertible()],
)
def test_competence_date_rejects_non_string_iso_value(value: object) -> None:
    with pytest.raises(DomainValidationError, match="ISO date string"):
        CompetenceDate.from_iso(cast(str, value))


def test_competence_date_rejects_iso_string_subclasses() -> None:
    with pytest.raises(DomainValidationError, match="ISO date string"):
        CompetenceDate.from_iso(IsoDateString("2026-09-17"))


def test_competence_date_rejects_datetime() -> None:
    with pytest.raises(DomainValidationError, match="without time"):
        CompetenceDate(datetime(2026, 9, 17, 12, 30))


@pytest.mark.parametrize(
    "value", [None, "2026-09-17", b"2026-09-17", 20260917, 2026.0917, True]
)
def test_competence_date_rejects_non_date_value(value: object) -> None:
    with pytest.raises(DomainValidationError, match="without time"):
        CompetenceDate(cast(date, value))


def test_competence_date_is_immutable() -> None:
    competence = CompetenceDate(date(2026, 9, 17))

    with pytest.raises(FrozenInstanceError):
        competence.__setattr__("value", date(2026, 9, 18))
