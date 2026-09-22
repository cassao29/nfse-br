"""Compatibility tests for the private XML signature preflight adapter."""

from __future__ import annotations

import traceback
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Never

import pytest

from nfse_br._xmlsig import preflight
from nfse_br._xmlsig.preflight import (
    MAX_XML_BYTES,
    SignaturePreflightError,
    inspect_unsigned_dps,
)
from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import (
    DpsDocumentError,
    DpsIdentity,
    DpsNumber,
    DpsSeries,
)
from nfse_br.dps import (
    inspect_unsigned_dps as public_inspect_unsigned_dps,
)
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps
from nfse_br.dps.document import _MAX_XML_BYTES

_EXPECTED_ID = "DPS2927408212ABC6780001Z000123000000000000042"


def _xml() -> bytes:
    draft = RestrictedDpsDraft(
        issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        issue_municipality=MunicipalityCode("2927408"),
        service_municipality=MunicipalityCode("3550308"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
        issued_at=datetime(
            2026,
            9,
            17,
            12,
            0,
            0,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        competence=CompetenceDate(date(2026, 9, 17)),
        application_version="nfse-br-test",
        national_service_code="010101",
        service_description="Servico sintetico",
        service_amount=Decimal("1.23"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )
    return build_unsigned_dps(draft)


def test_success_preserves_private_string_contract() -> None:
    xml_bytes = _xml()
    public_identity = public_inspect_unsigned_dps(xml_bytes)
    private_identity = inspect_unsigned_dps(xml_bytes)

    assert type(public_identity) is DpsIdentity
    assert type(private_identity) is str
    assert private_identity == public_identity.value == _EXPECTED_ID


def test_adapter_translates_public_error_with_same_code_and_no_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_error = DpsDocumentError("identity_mismatch")

    def reject(_xml_bytes: bytes) -> Never:
        raise public_error

    monkeypatch.setattr(preflight, "_inspect_unsigned_dps", reject)

    with pytest.raises(SignaturePreflightError) as caught:
        inspect_unsigned_dps(b"synthetic")

    assert caught.value.code == public_error.code
    assert caught.value.__cause__ is None
    assert type(caught.value) is SignaturePreflightError


def test_public_exception_does_not_escape_private_adapter() -> None:
    with pytest.raises(SignaturePreflightError) as caught:
        inspect_unsigned_dps(b"<DPS>")

    assert caught.value.code == "unsafe_or_malformed_xml"
    assert not isinstance(caught.value, DpsDocumentError)


def test_private_adapter_remains_reusable_after_rejection() -> None:
    valid = _xml()

    assert inspect_unsigned_dps(valid) == _EXPECTED_ID
    with pytest.raises(SignaturePreflightError, match="unsafe_or_malformed_xml"):
        inspect_unsigned_dps(b"<DPS>")
    assert inspect_unsigned_dps(valid) == _EXPECTED_ID


def test_private_error_surface_remains_privacy_safe() -> None:
    sensitive = "DPS-SYNTHETIC-PRIVATE-IDENTIFIER"

    try:
        inspect_unsigned_dps(sensitive.encode())
    except SignaturePreflightError as exc:
        rendered = "\n".join(
            (
                str(exc),
                repr(exc),
                "".join(traceback.format_exception(exc)),
            )
        )
        cause = exc.__cause__
    else:
        pytest.fail("malformed private fixture was accepted")

    assert sensitive not in rendered
    assert "DpsDocumentError" not in rendered
    assert cause is None


def test_private_maximum_remains_one_mib_and_matches_public_policy() -> None:
    assert MAX_XML_BYTES == _MAX_XML_BYTES == 1024 * 1024
