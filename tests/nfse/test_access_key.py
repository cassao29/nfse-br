"""Tests for the frozen ``TSChaveNFSe`` lexical primitive."""

from __future__ import annotations

import json
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest

import nfse_br.nfse
from nfse_br.domain import DomainValidationError
from nfse_br.nfse import NfseAccessKey
from nfse_br.nfse import access_key as access_key_module

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SYNTHETIC_ALPHANUMERIC = "000000SYNTHETIC00000" + "0" * 30
_SYNTHETIC_NUMERIC = "1" * 50


@pytest.mark.parametrize("value", [_SYNTHETIC_ALPHANUMERIC, _SYNTHETIC_NUMERIC])
def test_accepts_exact_synthetic_xsd_values(value: str) -> None:
    key = NfseAccessKey(value)

    assert key.value == value
    assert str(key) == value


def test_accepts_uppercase_alphanumeric_middle_segment() -> None:
    value = "123456ABCDEF12345678" + "9" * 30

    assert NfseAccessKey(value).value == value


@pytest.mark.parametrize(
    "value",
    [
        _SYNTHETIC_NUMERIC[:-1],
        _SYNTHETIC_NUMERIC + "0",
        _SYNTHETIC_ALPHANUMERIC.replace("S", "s", 1),
        " " + _SYNTHETIC_NUMERIC[1:],
        _SYNTHETIC_NUMERIC[:-1] + " ",
        _SYNTHETIC_NUMERIC[:20] + " " + _SYNTHETIC_NUMERIC[21:],
        _SYNTHETIC_NUMERIC[:20] + "-" + _SYNTHETIC_NUMERIC[21:],
        _SYNTHETIC_NUMERIC[:20] + "_" + _SYNTHETIC_NUMERIC[21:],
        _SYNTHETIC_NUMERIC[:20] + "Á" + _SYNTHETIC_NUMERIC[21:],
        _SYNTHETIC_NUMERIC[:20] + "１" + _SYNTHETIC_NUMERIC[21:],
    ],
)
def test_rejects_values_outside_the_exact_preserved_xsd_lexical_space(
    value: str,
) -> None:
    with pytest.raises(DomainValidationError, match="50-position ASCII XSD"):
        NfseAccessKey(value)


class AccessKeyString(str):
    """A string subclass that must not cross the exact runtime boundary."""


@pytest.mark.parametrize(
    "value",
    [
        b"1" * 50,
        int("1" * 50),
        True,
        None,
        AccessKeyString(_SYNTHETIC_NUMERIC),
    ],
)
def test_rejects_runtime_types_without_coercion(value: object) -> None:
    with pytest.raises(DomainValidationError, match="provided as a string"):
        NfseAccessKey(cast(str, value))


def test_equality_hash_and_immutability_use_the_exact_value() -> None:
    first = NfseAccessKey(_SYNTHETIC_ALPHANUMERIC)
    equal = NfseAccessKey(_SYNTHETIC_ALPHANUMERIC)
    different = NfseAccessKey(_SYNTHETIC_NUMERIC)

    assert first == equal
    assert hash(first) == hash(equal)
    assert first != different
    with pytest.raises(FrozenInstanceError):
        first.__setattr__("value", _SYNTHETIC_NUMERIC)


def test_repr_and_validation_errors_do_not_disclose_the_value() -> None:
    valid = NfseAccessKey(_SYNTHETIC_ALPHANUMERIC)
    sensitive_invalid = _SYNTHETIC_ALPHANUMERIC[:-1] + "!"

    assert repr(valid) == "NfseAccessKey(value=<redacted>)"
    assert valid.value not in repr(valid)

    try:
        NfseAccessKey(sensitive_invalid)
    except DomainValidationError as error:
        rendered = "".join(traceback.format_exception(error))
        assert sensitive_invalid not in str(error)
        assert sensitive_invalid not in repr(error)
        assert sensitive_invalid not in rendered
    else:
        raise AssertionError("Invalid NFS-e access key was unexpectedly accepted")


def test_public_subpackage_exports_access_key_and_identifier() -> None:
    assert nfse_br.nfse.__all__ == ["NfseAccessKey", "NfseId"]


def test_frozen_contract_matches_runtime_and_source_pins() -> None:
    contract_directory = _REPOSITORY_ROOT / "contracts" / "restricted"
    contract_path = contract_directory / "nfse-access-key-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract == {
        "authority": "official_frozen",
        "base": "xs:string",
        "bundle": {
            "sha256": (
                "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
            ),
            "size": 34_933,
        },
        "environment": "restricted",
        "facets": {
            "maxLength": 50,
            "pattern": "[0-9]{6}([0-9A-Z]{14})[0-9]{30}",
            "whiteSpace": "preserve",
        },
        "source_member": {
            "path": "tiposSimples_v1.01.xsd",
            "sha256": (
                "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
            ),
            "size": 69_488,
        },
        "transmission_ready": False,
        "type": "TSChaveNFSe",
    }
    assert access_key_module._ACCESS_KEY_LENGTH == contract["facets"]["maxLength"]
    assert access_key_module._ACCESS_KEY_PATTERN_TEXT == contract["facets"]["pattern"]
