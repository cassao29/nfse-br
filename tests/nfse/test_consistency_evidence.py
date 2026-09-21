"""Tests for the frozen NFS-e and embedded-DPS consistency evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = (
    _REPOSITORY_ROOT / "contracts" / "restricted" / "nfse-dps-consistency-contract.json"
)


def _contract() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(_CONTRACT_PATH.read_text(encoding="utf-8")),
    )


def test_contract_is_bound_to_the_frozen_official_sources() -> None:
    contract = _contract()

    assert contract["authority"] == "official_frozen"
    assert contract["environment"] == "restricted"
    assert contract["bundle"] == {
        "sha256": "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc",
        "size": 34_933,
    }
    assert contract["annex_i"] == {
        "sha256": "2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9",
        "size": 215_056,
        "sources": [
            {"code": "E1263", "range": "A7:O7", "rule": 4, "sheet": "RN DPS_NFS-e"},
            {"code": "E1282", "range": "A33:O33", "rule": 30, "sheet": "RN DPS_NFS-e"},
            {"code": "E1285", "range": "A35:O35", "rule": 32, "sheet": "RN DPS_NFS-e"},
            {"code": "E1286", "range": "A44:O44", "rule": 41, "sheet": "RN DPS_NFS-e"},
            {
                "code": "E0004",
                "range": "A142:O142",
                "rule": 139,
                "sheet": "RN DPS_NFS-e",
            },
        ],
    }
    assert contract["source_members"] == {
        "tiposComplexos_v1.01.xsd": {
            "sha256": (
                "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
            ),
            "size": 114_148,
        },
        "tiposSimples_v1.01.xsd": {
            "sha256": (
                "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
            ),
            "size": 69_488,
        },
    }


def test_only_currently_confirmed_invariants_are_runtime_enforceable() -> None:
    contract = _contract()
    invariants = contract["invariants"]
    assert isinstance(invariants, dict)

    assert {
        name
        for name, value in invariants.items()
        if isinstance(value, dict) and value["runtime_enforcement_allowed"]
    } == {
        "embedded_dps_self_consistency",
        "federal_registration_cross_consistency",
        "municipality_cross_consistency",
    }
    for invariant in invariants.values():
        assert isinstance(invariant, dict)
        if invariant["classification"] != "CURRENT_CONFIRMED":
            assert invariant["runtime_enforcement_allowed"] is False


def test_negative_controls_and_non_goals_remain_fail_closed() -> None:
    contract = _contract()
    invariants = contract["invariants"]
    assert isinstance(invariants, dict)

    assert invariants["nfse_number_self_consistency"]["classification"] == "CONFLICTING"
    assert invariants["environment_relation"]["classification"] == "UNCONFIRMED"
    assert invariants["nfse_number_vs_dps_number"]["classification"] == "UNCONFIRMED"
    assert (
        invariants["unconditional_prestador_registration_relation"]["classification"]
        == "CONFLICTING"
    )
    assert contract["implementation_ready"] is True
    assert contract["project_synthetic_fixture_is_normative_evidence"] is False
    assert contract["transmission_ready"] is False
    assert contract["policy"] == {
        "access_key_derivation": False,
        "cryptographic_signature_verification": False,
        "fiscal_authorization_asserted": False,
        "speculative_enforcement": False,
        "xsd_validation_implied": False,
    }
