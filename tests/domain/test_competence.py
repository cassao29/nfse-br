"""Tests for competence date values."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from typing import cast

import pytest

from nfse_br.domain import CompetenceDate, DomainValidationError


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
        "17-09-2026",
        "2026-9-17",
        "2026-09-17 ",
        "２０２６-０９-１７",
    ],
)
def test_competence_date_rejects_invalid_iso_values(value: str) -> None:
    with pytest.raises(DomainValidationError):
        CompetenceDate.from_iso(value)


def test_competence_date_rejects_non_string_iso_value() -> None:
    with pytest.raises(DomainValidationError, match="ISO date string"):
        CompetenceDate.from_iso(cast(str, date(2026, 9, 17)))


def test_competence_date_rejects_datetime() -> None:
    with pytest.raises(DomainValidationError, match="without time"):
        CompetenceDate(datetime(2026, 9, 17, 12, 30))


def test_competence_date_rejects_non_date_value() -> None:
    with pytest.raises(DomainValidationError, match="without time"):
        CompetenceDate(cast(date, "2026-09-17"))


def test_competence_date_is_immutable() -> None:
    competence = CompetenceDate(date(2026, 9, 17))

    with pytest.raises(FrozenInstanceError):
        competence.__setattr__("value", date(2026, 9, 18))
