"""Tests for the frozen ``TSIdNFSe`` lexical primitive."""

from __future__ import annotations

import json
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest

import nfse_br.nfse
from nfse_br.domain import DomainValidationError
from nfse_br.nfse import NfseId
from nfse_br.nfse import identifier as identifier_module

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SYNTHETIC_ALPHANUMERIC = "NFS" + "0" * 9 + "SYNTHETIC00000" + "0" * 27
_SYNTHETIC_NUMERIC = "NFS" + "1" * 50


@pytest.mark.parametrize("value", [_SYNTHETIC_ALPHANUMERIC, _SYNTHETIC_NUMERIC])
def test_accepts_exact_synthetic_xsd_values(value: str) -> None:
    identifier = NfseId(value)

    assert identifier.value == value
    assert str(identifier) == value


def test_accepts_uppercase_alphanumeric_middle_segment() -> None:
    value = "NFS" + "123456789" + "ABCDEF12345678" + "9" * 27

    assert NfseId(value).value == value


@pytest.mark.parametrize(
    "value",
    [
        _SYNTHETIC_NUMERIC[:-1],
        _SYNTHETIC_NUMERIC + "0",
        _SYNTHETIC_NUMERIC.removeprefix("NFS"),
        "nfs" + _SYNTHETIC_NUMERIC[3:],
        "NFs" + _SYNTHETIC_NUMERIC[3:],
        _SYNTHETIC_ALPHANUMERIC.replace("SYNTHETIC", "synthetic", 1),
        " " + _SYNTHETIC_NUMERIC[:-1],
        _SYNTHETIC_NUMERIC[:-1] + " ",
        _SYNTHETIC_NUMERIC[:25] + " " + _SYNTHETIC_NUMERIC[26:],
        _SYNTHETIC_NUMERIC[:25] + "-" + _SYNTHETIC_NUMERIC[26:],
        _SYNTHETIC_NUMERIC[:25] + "_" + _SYNTHETIC_NUMERIC[26:],
        _SYNTHETIC_NUMERIC[:25] + "Á" + _SYNTHETIC_NUMERIC[26:],
        _SYNTHETIC_NUMERIC[:25] + "１" + _SYNTHETIC_NUMERIC[26:],
    ],
)
def test_rejects_values_outside_the_exact_preserved_xsd_lexical_space(
    value: str,
) -> None:
    with pytest.raises(DomainValidationError, match="53-position ASCII XSD"):
        NfseId(value)


class IdentifierString(str):
    """A string subclass that must not cross the exact runtime boundary."""


@pytest.mark.parametrize(
    "value",
    [
        b"NFS" + b"1" * 50,
        int("1" * 53),
        True,
        None,
        IdentifierString(_SYNTHETIC_NUMERIC),
    ],
)
def test_rejects_runtime_types_without_coercion(value: object) -> None:
    with pytest.raises(DomainValidationError, match="provided as a string"):
        NfseId(cast(str, value))


def test_equality_hash_and_immutability_use_the_exact_value() -> None:
    first = NfseId(_SYNTHETIC_ALPHANUMERIC)
    equal = NfseId(_SYNTHETIC_ALPHANUMERIC)
    different = NfseId(_SYNTHETIC_NUMERIC)

    assert first == equal
    assert hash(first) == hash(equal)
    assert first != different
    with pytest.raises(FrozenInstanceError):
        first.__setattr__("value", _SYNTHETIC_NUMERIC)


def test_repr_and_validation_errors_do_not_disclose_the_value() -> None:
    valid = NfseId(_SYNTHETIC_ALPHANUMERIC)
    sensitive_invalid = _SYNTHETIC_ALPHANUMERIC[:-1] + "!"

    assert repr(valid) == "NfseId(value=<redacted>)"
    assert valid.value not in repr(valid)

    try:
        NfseId(sensitive_invalid)
    except DomainValidationError as error:
        rendered = "".join(traceback.format_exception(error))
        assert sensitive_invalid not in str(error)
        assert sensitive_invalid not in repr(error)
        assert sensitive_invalid not in rendered
    else:
        raise AssertionError("Invalid NFS-e identifier was unexpectedly accepted")


def test_public_subpackage_exports_access_key_and_identifier() -> None:
    assert nfse_br.nfse.__all__ == [
        "NfseAccessKey",
        "NfseConsistencyError",
        "NfseDocumentError",
        "NfseDocumentInfo",
        "NfseId",
        "extract_nfse_document_info",
        "validate_nfse_document_consistency",
    ]


def test_frozen_contract_matches_runtime_and_keeps_conversion_forbidden() -> None:
    contract_path = (
        _REPOSITORY_ROOT / "contracts" / "restricted" / "nfse-identity-contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    identity = contract["identity_chain"]["id_attribute"]

    assert identity == {
        "base": "xs:string",
        "effective_length": 53,
        "facets": {
            "maxLength": 53,
            "pattern": "NFS[0-9]{9}[0-9A-Z]{14}[0-9]{27}",
            "whiteSpace": "preserve",
        },
        "name": "Id",
        "source": "tiposComplexos_v1.01.xsd",
        "type": "TSIdNFSe",
        "type_source": "tiposSimples_v1.01.xsd",
        "use": "required",
    }
    assert contract["relationships"]["lexical"]["confirmed"] is False
    assert contract["relationships"]["conversion"]["allowed"] is False
    assert identifier_module._NFSE_ID_LENGTH == identity["effective_length"]
    assert identifier_module._NFSE_ID_PATTERN_TEXT == identity["facets"]["pattern"]


def test_public_surface_does_not_offer_access_key_conversion() -> None:
    identifier = NfseId(_SYNTHETIC_ALPHANUMERIC)

    assert not hasattr(identifier, "access_key")
    assert not hasattr(identifier, "to_access_key")
