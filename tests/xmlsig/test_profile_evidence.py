"""Bindings for the deliberately incomplete restricted XMLDSig profile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from nfse_br.xsd.validator import (
    _EXPECTED_SCHEMA_MEMBERS,
    RESTRICTED_XSD_BUNDLE_SHA256,
    RESTRICTED_XSD_BUNDLE_SIZE,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_PATH = _ROOT / "contracts/restricted/dps-xmldsig-profile.json"
_PROFILE_DOC_PATH = _ROOT / "contracts/restricted/DPS_XMLDSIG_PROFILE.md"
_MANIFEST_PATH = _ROOT / "contracts/restricted/manifest.json"
_CONTRACT_PATH = _ROOT / "contracts/restricted/dps-schema-contract.json"
_VALIDATOR_DOC_PATH = _ROOT / "contracts/restricted/DPS_XSD_VALIDATOR.md"

_MANIFEST_SHA256 = "2d8049958e7dcfa5e4e002a45cca8d526df83ab9c42b57eff2320017f85b3b8c"
_CONTRACT_SHA256 = "794c5904c4d81381d73050df63df541de587a08e195b7fb25f553937a43b67b0"
_XMLDSIG_SHA256 = "bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11"


def _profile() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(_PROFILE_PATH.read_text(encoding="utf-8")),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_profile_binds_independently_frozen_evidence() -> None:
    profile = _profile()
    bindings = cast(dict[str, object], profile["evidence_bindings"])
    bundle = cast(dict[str, object], bindings["restricted_bundle"])
    schema_members = cast(dict[str, dict[str, object]], bindings["schema_members"])

    assert _sha256(_MANIFEST_PATH) == _MANIFEST_SHA256
    assert _sha256(_CONTRACT_PATH) == _CONTRACT_SHA256
    assert bindings["v0_4_manifest_sha256"] == _MANIFEST_SHA256
    assert bindings["v0_5_contract_sha256"] == _CONTRACT_SHA256
    assert bundle == {
        "sha256": RESTRICTED_XSD_BUNDLE_SHA256,
        "size": RESTRICTED_XSD_BUNDLE_SIZE,
    }
    assert schema_members["xmldsig-core-schema.xsd"] == {
        "sha256": _XMLDSIG_SHA256,
        "size": 10003,
    }
    assert {
        name: member["sha256"] for name, member in schema_members.items()
    } == _EXPECTED_SCHEMA_MEMBERS
    assert _XMLDSIG_SHA256 in _VALIDATOR_DOC_PATH.read_text(encoding="utf-8")


def test_profile_does_not_promote_historical_algorithms() -> None:
    profile = _profile()
    observations = cast(
        dict[str, object],
        profile["official_frozen_schema_observations"],
    )
    historical = cast(dict[str, object], profile["historical_profile_only"])
    sources = cast(list[dict[str, object]], profile["sources"])
    unconfirmed = cast(list[str], profile["unconfirmed_for_current_restricted_profile"])

    assert profile["signature_profile_confirmed"] is False
    assert profile["transmission_ready"] is False
    assert observations["algorithm_values_fixed_or_enumerated"] is False
    assert set(cast(dict[str, str], observations["algorithm_attributes"]).values()) == {
        "xs:anyURI"
    }
    signature_method = cast(str, historical["signature_method"])
    digest_method = cast(str, historical["digest_method"])
    assert signature_method.endswith("rsa-sha1")
    assert digest_method.endswith("sha1")
    assert any(source["classification"] == "official_historical" for source in sources)
    assert "signature algorithm" in unconfirmed
    assert "digest algorithm" in unconfirmed
    assert "canonicalization algorithm" in unconfirmed


def test_documentation_states_scope_and_non_authority() -> None:
    document = _PROFILE_DOC_PATH.read_text(encoding="utf-8")

    assert "SIGNATURE_PROFILE_CONFIRMED = NO" in document
    assert "SIGNING_IMPLEMENTED = NO" in document
    assert "CRYPTOGRAPHIC_VERIFICATION_IMPLEMENTED = NO" in document
    assert "TRANSMISSION_READY = NO" in document
    assert "historical evidence, not promoted" in document
