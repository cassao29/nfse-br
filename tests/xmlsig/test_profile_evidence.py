"""Bindings for the deliberately incomplete restricted XMLDSig profile."""

from __future__ import annotations

import hashlib
import json
import re
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
_PROBE_PATH = _ROOT / "contracts/restricted/prodrest-empirical-probe.json"
_PROBE_DOC_PATH = _ROOT / "contracts/restricted/PRODREST_EMPIRICAL_PROBE.md"

_MANIFEST_SHA256 = "2d8049958e7dcfa5e4e002a45cca8d526df83ab9c42b57eff2320017f85b3b8c"
_CONTRACT_SHA256 = "794c5904c4d81381d73050df63df541de587a08e195b7fb25f553937a43b67b0"
_XMLDSIG_SHA256 = "bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11"

_VALIDATOR_CLASS = "CONFIRMED_BY_OFFICIAL_VALIDATOR"
_INCLUSIVE_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_INCLUSIVE_C14N_WITH_COMMENTS = _INCLUSIVE_C14N + "#WithComments"
_EXCLUSIVE_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
_ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
# CPF (11), CNPJ (14), DPS Id digits (42), access key (50), IBGE code (7).
_STANDALONE_DIGITS = re.compile(
    r"(?<![0-9A-Za-z])(?:[0-9]{7}|[0-9]{11,})(?![0-9A-Za-z])"
)
_DOCUMENT_ID = re.compile(r"\b(?:DPS|NFS|PRE)[0-9]{20,}")
_LONG_BASE64 = re.compile(r"[A-Za-z0-9+/]{200,}")


def _profile() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(_PROFILE_PATH.read_text(encoding="utf-8")),
    )


def _probe() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(_PROBE_PATH.read_text(encoding="utf-8")),
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


def test_historical_profile_stays_historical() -> None:
    profile = _profile()
    observations = cast(
        dict[str, object],
        profile["official_frozen_schema_observations"],
    )
    historical = cast(dict[str, object], profile["historical_profile_only"])
    sources = cast(list[dict[str, object]], profile["sources"])

    assert observations["algorithm_values_fixed_or_enumerated"] is False
    assert set(cast(dict[str, str], observations["algorithm_attributes"]).values()) == {
        "xs:anyURI"
    }
    signature_method = cast(str, historical["signature_method"])
    digest_method = cast(str, historical["digest_method"])
    assert signature_method.endswith("rsa-sha1")
    assert digest_method.endswith("sha1")
    assert historical["canonicalization_method"] == _INCLUSIVE_C14N
    assert any(source["classification"] == "official_historical" for source in sources)


def test_confirmation_is_bound_to_the_official_validator_record() -> None:
    profile = _profile()
    probe = _probe()
    empirical = cast(dict[str, object], profile["empirical_validation"])
    confirmed = cast(dict[str, object], empirical["confirmed_profile"])
    historical = cast(dict[str, object], profile["historical_profile_only"])
    matrix = cast(dict[str, dict[str, str]], empirical["decision_matrix"])

    assert profile["signature_profile_confirmed"] is True
    assert profile["transmission_ready"] is False
    assert empirical["evidence_class"] == _VALIDATOR_CLASS
    assert empirical["record_json_sha256"] == _sha256(_PROBE_PATH)
    assert confirmed == probe["accepted_profile"]
    assert confirmed["canonicalization_method"] == _EXCLUSIVE_C14N
    assert confirmed["canonicalization_method"] != historical["canonicalization_method"]
    assert cast(str, confirmed["signature_method"]).endswith("rsa-sha256")
    assert cast(str, confirmed["digest_method"]).endswith("sha256")
    assert confirmed["transforms_in_order"] == [_ENVELOPED, _EXCLUSIVE_C14N]
    assert matrix["basic_constraints"]["classification"] == "CONFLICTING"
    assert matrix["key_usage"]["classification"] == "CONFLICTING"
    assert profile["unconfirmed_for_current_restricted_profile"] == [
        "Basic Constraints",
        "complete Key Usage",
        "production environment behavior",
    ]


def test_probe_results_support_the_confirmed_profile() -> None:
    probe = _probe()
    rows = {
        cast(str, row["id"]): row
        for row in cast(list[dict[str, object]], probe["results"])
    }
    profile = cast(dict[str, object], probe["accepted_profile"])

    issued = rows["I4"]
    assert issued["http_status"] == 201
    assert issued["codes"] == []
    for row_id in ("I4", "M00"):
        signature = cast(dict[str, object], rows[row_id]["signature"])
        assert (
            signature["canonicalization_method"] == profile["canonicalization_method"]
        )
        assert signature["signature_method"] == profile["signature_method"]
        assert signature["digest_method"] == profile["digest_method"]
        assert signature["transforms"] == profile["transforms_in_order"]
        assert signature["x509_certificates"] == 1
        assert signature["signature_prefixed"] is False
        assert signature["signature_parent"] == "DPS"

    for row_id in cast(list[str], probe["also_accepted"]) + ["I3", "M00"]:
        assert rows[row_id]["codes"] == ["E0712"], row_id
    rejected = cast(dict[str, list[str]], probe["rejected"])
    for row_ids in rejected.values():
        for row_id in row_ids:
            assert rows[row_id]["codes"] not in ([], ["E0712"]), row_id

    for row in rows.values():
        signature = cast(dict[str, object], row["signature"])
        algorithms = [
            signature["canonicalization_method"],
            *cast(list[str], signature["transforms"]),
        ]
        if _INCLUSIVE_C14N in algorithms or _INCLUSIVE_C14N_WITH_COMMENTS in algorithms:
            assert row["codes"] == ["E0714"], row["id"]


def test_probe_records_contain_no_fiscal_identifiers() -> None:
    for path in (_PROBE_PATH, _PROBE_DOC_PATH):
        text = path.read_text(encoding="utf-8")
        assert _STANDALONE_DIGITS.search(text) is None, path.name
        assert _DOCUMENT_ID.search(text) is None, path.name
        assert _LONG_BASE64.search(text) is None, path.name


def test_documentation_states_scope_and_non_authority() -> None:
    document = _PROFILE_DOC_PATH.read_text(encoding="utf-8")
    first_state_block = document.split("```text\n", 1)[1].split("```", 1)[0]

    assert first_state_block == (
        "SIGNATURE_PROFILE_CONFIRMED = YES\n"
        "SIGNING_IMPLEMENTED = NO\n"
        "CRYPTOGRAPHIC_VERIFICATION_IMPLEMENTED = NO\n"
        "TRANSMISSION_READY = NO\n"
    )
    assert _VALIDATOR_CLASS in document
    assert "historical evidence, not promoted" in document
