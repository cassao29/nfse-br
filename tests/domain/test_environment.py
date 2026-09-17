"""Tests for NFS-e environment values."""

from typing import cast

import pytest

from nfse_br.domain import DomainValidationError, NfseEnvironment


def test_environment_codes_match_the_national_contract() -> None:
    assert NfseEnvironment.PRODUCTION.code == 1
    assert NfseEnvironment.RESTRICTED_PRODUCTION.code == 2


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, NfseEnvironment.PRODUCTION),
        (2, NfseEnvironment.RESTRICTED_PRODUCTION),
    ],
)
def test_environment_can_be_created_from_a_code(
    code: int, expected: NfseEnvironment
) -> None:
    assert NfseEnvironment.from_code(code) is expected


@pytest.mark.parametrize("code", [-1, 0, 3])
def test_environment_rejects_an_unsupported_code(code: int) -> None:
    with pytest.raises(DomainValidationError, match="Unsupported"):
        NfseEnvironment.from_code(code)


@pytest.mark.parametrize("code", [True, False, 1.0, 2.0, "1"])
def test_environment_rejects_non_integer_code(code: object) -> None:
    with pytest.raises(DomainValidationError, match="integer"):
        NfseEnvironment.from_code(cast(int, code))


def test_domain_validation_error_is_a_value_error() -> None:
    assert issubclass(DomainValidationError, ValueError)
