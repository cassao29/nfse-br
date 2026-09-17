"""Tests for the working local DPS identity contract."""

import re
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

import nfse_br
import nfse_br.domain as domain
import nfse_br.dps as dps
from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsIdentity, DpsNumber, DpsSeries

_WORKING_PATTERN = re.compile(r"DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}")


def _build_alphanumeric_cnpj_identity(
    *, series: str = "123", number: int = 42
) -> DpsIdentity:
    return DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        series=DpsSeries(series),
        number=DpsNumber(number),
    )


def test_identity_rejects_direct_construction() -> None:
    with pytest.raises(DomainValidationError, match=r"DpsIdentity\.build"):
        DpsIdentity()


def test_alphanumeric_cnpj_regression_vector() -> None:
    identity = _build_alphanumeric_cnpj_identity()

    assert identity.value == "DPS2927408212ABC6780001Z000123000000000000042"
    assert str(identity) == identity.value
    assert len(identity.value) == 45
    assert _WORKING_PATTERN.fullmatch(identity.value) is not None


def test_numeric_cnpj_keeps_all_fourteen_positions() -> None:
    identity = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cnpj("12345678000199"),
        series=DpsSeries("1"),
        number=DpsNumber(1),
    )

    assert identity.inscription_type == "2"
    assert identity.value == "DPS292740821234567800019900001000000000000001"


def test_synthetic_cpf_is_left_padded_to_fourteen_positions() -> None:
    identity = DpsIdentity.build(
        municipality=MunicipalityCode("2927408"),
        federal_tax_id=FederalTaxId.cpf("12345678901"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
    )

    assert identity.inscription_type == "1"
    assert identity.value == "DPS292740810001234567890100123000000000000042"
    assert identity.value[11:25] == "00012345678901"
    assert len(identity.value) == 45
    assert _WORKING_PATTERN.fullmatch(identity.value) is not None


def test_identity_preserves_components_and_padding() -> None:
    identity = _build_alphanumeric_cnpj_identity()

    assert identity.municipality == MunicipalityCode("2927408")
    assert identity.federal_tax_id == FederalTaxId.cnpj("12ABC6780001Z0")
    assert identity.series == DpsSeries("123")
    assert identity.number == DpsNumber(42)
    assert identity.value[:3] == "DPS"
    assert identity.value[3:10] == "2927408"
    assert identity.value[10] == "2"
    assert identity.value[25:30] == "00123"
    assert identity.value[30:] == "000000000000042"


def test_identity_construction_is_deterministic_and_hashable() -> None:
    first = _build_alphanumeric_cnpj_identity()
    second = _build_alphanumeric_cnpj_identity()

    assert first == second
    assert hash(first) == hash(second)


def test_lexically_distinct_series_can_produce_the_same_identity_value() -> None:
    short_series = _build_alphanumeric_cnpj_identity(series="123")
    padded_series = _build_alphanumeric_cnpj_identity(series="00123")

    assert short_series.value == padded_series.value
    assert short_series != padded_series


def test_identity_is_immutable() -> None:
    identity = _build_alphanumeric_cnpj_identity()

    with pytest.raises(FrozenInstanceError):
        identity.__setattr__("value", "DPS")


def test_identity_repr_redacts_composed_and_federal_values() -> None:
    identity = _build_alphanumeric_cnpj_identity()
    representation = repr(identity)

    assert identity.value not in representation
    assert identity.federal_tax_id.value not in representation
    assert representation.count("<redacted>") == 2


def test_identity_rejects_primitive_components() -> None:
    municipality = MunicipalityCode("2927408")
    federal_tax_id = FederalTaxId.cnpj("12ABC6780001Z0")
    series = DpsSeries("123")
    number = DpsNumber(42)

    with pytest.raises(DomainValidationError, match="MunicipalityCode"):
        DpsIdentity.build(
            municipality=cast(MunicipalityCode, "2927408"),
            federal_tax_id=federal_tax_id,
            series=series,
            number=number,
        )
    with pytest.raises(DomainValidationError, match="FederalTaxId"):
        DpsIdentity.build(
            municipality=municipality,
            federal_tax_id=cast(FederalTaxId, "12ABC6780001Z0"),
            series=series,
            number=number,
        )
    with pytest.raises(DomainValidationError, match="DpsSeries"):
        DpsIdentity.build(
            municipality=municipality,
            federal_tax_id=federal_tax_id,
            series=cast(DpsSeries, "123"),
            number=number,
        )
    with pytest.raises(DomainValidationError, match="DpsNumber"):
        DpsIdentity.build(
            municipality=municipality,
            federal_tax_id=federal_tax_id,
            series=series,
            number=cast(DpsNumber, 42),
        )


def test_identity_errors_do_not_echo_federal_identifier() -> None:
    sensitive_value = "12ABC6780001Z0"

    with pytest.raises(DomainValidationError) as exc_info:
        DpsIdentity.build(
            municipality=MunicipalityCode("2927408"),
            federal_tax_id=cast(FederalTaxId, sensitive_value),
            series=DpsSeries("123"),
            number=DpsNumber(42),
        )

    assert sensitive_value not in str(exc_info.value)


def test_dps_public_api_is_scoped_to_its_subpackage() -> None:
    assert dps.__all__ == ["DpsIdentity", "DpsNumber", "DpsSeries"]
    assert nfse_br.__all__ == ["__version__"]
    assert domain.__all__ == [
        "CompetenceDate",
        "DomainValidationError",
        "FederalTaxId",
        "FederalTaxIdKind",
        "MunicipalityCode",
        "NfseEnvironment",
    ]
    assert not hasattr(nfse_br, "DpsIdentity")
    assert not hasattr(domain, "DpsIdentity")
