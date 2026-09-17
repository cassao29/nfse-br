"""Bind committed restricted evidence to the current DPS implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest

from nfse_br._f0 import restricted_contract as restricted
from nfse_br._f0.restricted_contract import ContractFreezeError
from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsIdentity, DpsNumber, DpsSeries

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPOSITORY_ROOT / "contracts/restricted/manifest.json"


def _load_manifest() -> dict[str, object]:
    raw = _MANIFEST_PATH.read_bytes()
    parsed: object = json.loads(raw)
    assert type(parsed) is dict
    manifest = cast(dict[str, object], parsed)
    restricted._validate_manifest(manifest)
    assert raw == restricted._serialize_manifest(manifest)
    return manifest


def _mapping(mapping: dict[str, object], field: str) -> dict[str, object]:
    value = mapping[field]
    assert type(value) is dict
    return cast(dict[str, object], value)


def _string(mapping: dict[str, object], field: str) -> str:
    value = mapping[field]
    assert type(value) is str
    return value


def test_committed_manifest_has_exact_official_provenance() -> None:
    manifest = _load_manifest()

    assert manifest["authority"] == "official_frozen"
    assert manifest["environment"] == "restricted"
    assert manifest["scope"] == "dps_identity"
    assert manifest["transmission_ready"] is False

    layout = _mapping(manifest, "layout")
    assert layout == {
        "sha256": "2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9",
        "size": 215_056,
        "url": restricted.EXPECTED_LAYOUT_URL,
    }
    xsd = _mapping(manifest, "xsd")
    assert xsd["sha256"] == (
        "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
    )
    assert xsd["size"] == 34_933
    assert xsd["url"] == restricted.EXPECTED_XSD_URL
    assert xsd["audited_schema_files"] == [
        {
            "path": "tiposSimples_v1.01.xsd",
            "sha256": (
                "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
            ),
        }
    ]


def test_committed_manifest_binds_dps_identity_behavior() -> None:
    manifest = _load_manifest()
    xsd = _mapping(manifest, "xsd")
    identity_contract = _mapping(xsd, "identity_contract")
    series_contract = _mapping(xsd, "series_contract")

    assert identity_contract == {
        "max_length": 45,
        "pattern": restricted.EXPECTED_IDENTITY_PATTERN,
        "source": "tiposSimples_v1.01.xsd",
        "type": "TSIdDPS",
    }
    assert series_contract == {
        "pattern": restricted.EXPECTED_SERIES_PATTERN,
        "source": "tiposSimples_v1.01.xsd",
        "type": "TSSerieDPS",
    }

    pattern = re.compile(_string(identity_contract, "pattern"))
    alphanumeric_cnpj = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
    )
    synthetic_cpf = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cpf("12345678901"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
    )

    assert alphanumeric_cnpj.value == ("DPS2927408212ABC6780001Z000123000000000000042")
    assert synthetic_cpf.value == ("DPS292740810001234567890100123000000000000042")
    assert len(alphanumeric_cnpj.value) == identity_contract["max_length"]
    assert pattern.fullmatch(alphanumeric_cnpj.value) is not None
    assert pattern.fullmatch(synthetic_cpf.value) is not None

    assert DpsSeries("89999").value == "89999"
    with pytest.raises(DomainValidationError):
        DpsSeries("90000")
    with pytest.raises(DomainValidationError):
        DpsSeries("90001")


def test_transmission_ready_cannot_be_promoted_in_manifest() -> None:
    manifest = _load_manifest()
    manifest["transmission_ready"] = True

    with pytest.raises(ContractFreezeError, match="transmission_ready"):
        restricted._validate_manifest(manifest)


def test_manifest_validator_rejects_invalid_hash_size_and_extra_fields() -> None:
    manifest = _load_manifest()
    layout = _mapping(manifest, "layout")
    layout["sha256"] = "A" * 64
    with pytest.raises(ContractFreezeError, match="lowercase SHA-256"):
        restricted._validate_manifest(manifest)

    manifest = _load_manifest()
    _mapping(manifest, "layout")["size"] = True
    with pytest.raises(ContractFreezeError, match="positive integer"):
        restricted._validate_manifest(manifest)

    manifest = _load_manifest()
    manifest["unexpected"] = float("inf")
    with pytest.raises(ContractFreezeError, match="manifest fields"):
        restricted._validate_manifest(manifest)


def test_manifest_validator_rejects_ambiguous_or_unbound_schema_sources() -> None:
    manifest = _load_manifest()
    xsd = _mapping(manifest, "xsd")
    audited = xsd["audited_schema_files"]
    assert type(audited) is list
    entries = cast(list[object], audited)
    entries.append(
        {
            "path": "nested/tiposSimples_v1.01.xsd",
            "sha256": "0" * 64,
        }
    )
    with pytest.raises(ContractFreezeError, match="ambiguous"):
        restricted._validate_manifest(manifest)

    manifest = _load_manifest()
    identity = _mapping(_mapping(manifest, "xsd"), "identity_contract")
    identity["source"] = "other.xsd"
    with pytest.raises(ContractFreezeError, match="facet sources"):
        restricted._validate_manifest(manifest)


def test_manifest_validator_rejects_invalid_audited_schema_entries() -> None:
    manifest = _load_manifest()
    xsd = _mapping(manifest, "xsd")
    xsd["audited_schema_files"] = ["not-an-object"]
    with pytest.raises(ContractFreezeError, match="entry must be an object"):
        restricted._validate_manifest(manifest)

    manifest = _load_manifest()
    xsd = _mapping(manifest, "xsd")
    xsd["audited_schema_files"] = [{"path": "../types.xsd", "sha256": "0" * 64}]
    with pytest.raises(ContractFreezeError, match="unsafe audited schema path"):
        restricted._validate_manifest(manifest)


def test_manifest_validator_rejects_non_mapping_contract() -> None:
    manifest = _load_manifest()
    _mapping(manifest, "xsd")["identity_contract"] = "not-an-object"

    with pytest.raises(ContractFreezeError, match="identity_contract.*object"):
        restricted._validate_manifest(manifest)
