"""Tests for the composed restricted unsigned DPS checker."""

from __future__ import annotations

import traceback
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Never

import pytest

from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsDocumentError, DpsIdentity, DpsNumber, DpsSeries
from nfse_br.dps.builder import (
    RestrictedDpsDraft,
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
    build_unsigned_dps,
)
from nfse_br.xsd import RestrictedDpsChecker, XsdValidationError
from nfse_br.xsd import dps_checker as checker_module

_IDENTITY = DpsIdentity.build(
    municipality=MunicipalityCode("2927408"),
    federal_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
    series=DpsSeries("123"),
    number=DpsNumber(42),
)


def _draft() -> RestrictedDpsDraft:
    return RestrictedDpsDraft(
        issuer_tax_id=_IDENTITY.federal_tax_id,
        issue_municipality=_IDENTITY.municipality,
        service_municipality=MunicipalityCode("3550308"),
        series=_IDENTITY.series,
        number=_IDENTITY.number,
        issued_at=datetime(
            2026, 9, 17, 12, 34, 56, tzinfo=timezone(timedelta(hours=-3))
        ),
        competence=CompetenceDate(date(2026, 9, 17)),
        application_version="synthetic-checker",
        national_service_code="010101",
        service_description="Descrição sintética & <texto>\nsegunda linha",
        service_amount=Decimal("0.01"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )


def _unexpected_stage(_xml_bytes: bytes) -> Never:
    pytest.fail("Independent checker stage must not be called")


def test_constructor_passes_exact_bundle_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = bytes(bytearray(b"synthetic bundle"))
    observed: list[bytes] = []

    class Validator:
        def __init__(self, bundle_bytes: bytes) -> None:
            observed.append(bundle_bytes)

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    RestrictedDpsChecker(bundle)

    assert len(observed) == 1
    assert observed[0] is bundle


def test_constructor_propagates_same_xsd_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = XsdValidationError(phase="bundle", code="digest_mismatch")

    def reject(_bundle_bytes: bytes) -> Never:
        raise failure

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", reject)

    with pytest.raises(XsdValidationError) as caught:
        RestrictedDpsChecker(b"bundle")

    assert caught.value is failure


def test_check_orders_stages_reuses_exact_bytes_and_returns_exact_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, bytes]] = []

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            observed.append(("xsd", xml_bytes))

    def inspect(xml_bytes: bytes) -> DpsIdentity:
        observed.append(("inspection", xml_bytes))
        return _IDENTITY

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", inspect)
    monkeypatch.setattr(checker_module, "parse_unsigned_dps", _unexpected_stage)
    xml_bytes = bytes(bytearray(b"synthetic XML"))

    result = RestrictedDpsChecker(b"bundle").check(xml_bytes)

    assert result is _IDENTITY
    assert [stage for stage, _ in observed] == ["xsd", "inspection"]
    assert all(value is xml_bytes for _, value in observed)


@pytest.mark.parametrize(
    ("stage", "failure"),
    [
        ("xsd", XsdValidationError(phase="schema", code="document_invalid")),
        ("inspection", DpsDocumentError("identity_mismatch")),
    ],
)
def test_failure_short_circuits_and_propagates_same_error(
    stage: str,
    failure: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            calls.append("xsd")
            if stage == "xsd":
                raise failure

    def inspect(_xml_bytes: bytes) -> DpsIdentity:
        calls.append("inspection")
        if stage == "inspection":
            raise failure
        return _IDENTITY

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", inspect)

    with pytest.raises(type(failure)) as caught:
        RestrictedDpsChecker(b"bundle").check(b"synthetic XML")

    assert caught.value is failure
    assert calls == (["xsd"] if stage == "xsd" else ["xsd", "inspection"])


def test_checker_is_reusable_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            if xml_bytes == b"bad":
                raise XsdValidationError(phase="schema", code="document_invalid")

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", lambda _xml: _IDENTITY)
    checker = RestrictedDpsChecker(b"bundle")

    assert checker.check(b"good") is _IDENTITY
    with pytest.raises(XsdValidationError, match="document_invalid"):
        checker.check(b"bad")
    assert checker.check(b"good again") is _IDENTITY


def test_propagated_error_is_privacy_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive = "SYNTHETIC-PRIVATE-DPS-ID"
    failure = DpsDocumentError("identity_mismatch")

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    def reject(_xml_bytes: bytes) -> Never:
        raise failure

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", reject)

    with pytest.raises(DpsDocumentError) as caught:
        RestrictedDpsChecker(b"bundle").check(sensitive.encode())

    assert caught.value is failure
    rendered = "".join(traceback.format_exception(caught.value))
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in rendered


def test_parse_orders_xsd_then_parser_and_returns_exact_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, bytes]] = []
    expected_draft = _draft()

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            observed.append(("xsd", xml_bytes))

    def parse(xml_bytes: bytes) -> RestrictedDpsDraft:
        observed.append(("parse", xml_bytes))
        return expected_draft

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "parse_unsigned_dps", parse)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", _unexpected_stage)
    xml_bytes = bytes(bytearray(b"synthetic XML"))

    result = RestrictedDpsChecker(b"bundle").parse(xml_bytes)

    assert result is expected_draft
    assert [stage for stage, _ in observed] == ["xsd", "parse"]
    assert observed[0][1] is xml_bytes
    assert observed[1][1] is xml_bytes


@pytest.mark.parametrize(
    ("stage", "failure"),
    [
        ("xsd", XsdValidationError(phase="schema", code="document_invalid")),
        ("parse", DpsDocumentError("unsupported_document_structure")),
    ],
)
def test_parse_short_circuits_and_propagates_exact_privacy_safe_error(
    stage: str,
    failure: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sensitive = "SYNTHETIC-PRIVATE-DPS-PAYLOAD"

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            calls.append("xsd")
            if stage == "xsd":
                raise failure

    def parse(_xml_bytes: bytes) -> Never:
        calls.append("parse")
        raise failure

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "parse_unsigned_dps", parse)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", _unexpected_stage)

    with pytest.raises(type(failure)) as caught:
        RestrictedDpsChecker(b"bundle").parse(sensitive.encode())

    assert caught.value is failure
    assert calls == (["xsd"] if stage == "xsd" else ["xsd", "parse"])
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("failure_stage", ["xsd", "parse"])
def test_mixed_check_parse_reuse_after_controlled_failure(
    failure_stage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bytes]] = []
    bundles: list[bytes] = []
    draft = _draft()
    bad = b"bad"
    bundle = bytes(bytearray(b"synthetic bundle"))
    failure = (
        XsdValidationError(phase="schema", code="document_invalid")
        if failure_stage == "xsd"
        else DpsDocumentError("invalid_document_fields")
    )

    class Validator:
        def __init__(self, bundle_bytes: bytes) -> None:
            bundles.append(bundle_bytes)

        def validate(self, xml_bytes: bytes) -> None:
            calls.append(("xsd", xml_bytes))
            if xml_bytes is bad and failure_stage == "xsd":
                raise failure

    def inspect(xml_bytes: bytes) -> DpsIdentity:
        calls.append(("inspection", xml_bytes))
        return _IDENTITY

    def parse(xml_bytes: bytes) -> RestrictedDpsDraft:
        calls.append(("parse", xml_bytes))
        if xml_bytes is bad:
            raise failure
        return draft

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    monkeypatch.setattr(checker_module, "inspect_unsigned_dps", inspect)
    monkeypatch.setattr(checker_module, "parse_unsigned_dps", parse)
    checker = RestrictedDpsChecker(bundle)
    first, second, third, fourth = (b"first", b"second", b"third", b"fourth")
    assert checker.parse(first) is draft
    assert checker.check(second) is _IDENTITY
    with pytest.raises(type(failure)) as caught:
        checker.parse(bad)
    assert caught.value is failure
    assert checker.check(third) is _IDENTITY
    assert checker.parse(fourth) is draft
    expected = [
        ("xsd", first),
        ("parse", first),
        ("xsd", second),
        ("inspection", second),
        ("xsd", bad),
    ]
    if failure_stage == "parse":
        expected.append(("parse", bad))
    expected.extend(
        [
            ("xsd", third),
            ("inspection", third),
            ("xsd", fourth),
            ("parse", fourth),
        ]
    )
    assert calls == expected
    assert len(bundles) == 1
    assert bundles[0] is bundle
    assert RestrictedDpsChecker.__slots__ == ("_validator",)


def test_builder_round_trip_through_real_parser_with_mocked_xsd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real parsing, not official schema conformance (no bundle in CI)."""
    validated: list[bytes] = []

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            validated.append(xml_bytes)

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    draft = _draft()
    xml = build_unsigned_dps(draft)
    parsed = RestrictedDpsChecker(b"bundle").parse(xml)
    assert parsed == draft
    assert build_unsigned_dps(parsed) == xml
    assert len(validated) == 1
    assert validated[0] is xml


def test_real_inspector_accepts_extra_branch_but_real_parser_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock only XSD: this test makes no schema-conformance assertion."""

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    draft = _draft()
    original = build_unsigned_dps(draft)
    # Identified taker without address: inspection does not certify the subset.
    xml = original.replace(
        b"</prest>",
        b"</prest><toma><CPF>12345678901</CPF><xNome>Synthetic</xNome></toma>",
    )
    checker = RestrictedDpsChecker(b"bundle")
    assert checker.check(xml) == _IDENTITY
    with pytest.raises(DpsDocumentError) as caught:
        checker.parse(xml)
    assert caught.value.code == "unsupported_document_structure"
    rendered = str(caught.value) + repr(caught.value)
    rendered += "".join(traceback.format_exception(caught.value))
    for value in (
        draft.issuer_tax_id.value,
        _IDENTITY.value,
        draft.service_description,
        str(draft.service_amount),
    ):
        assert value not in rendered
    assert checker.check(xml) == _IDENTITY
    assert build_unsigned_dps(checker.parse(original)) == original


@pytest.mark.parametrize("outside_subset", ["long-name", "missing-address"])
def test_taker_check_parse_remain_independent_and_reusable(
    outside_subset: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real runtime stages; official XSD conformance is tested locally separately."""
    observed: list[bytes] = []

    class Validator:
        def __init__(self, _bundle: bytes) -> None:
            pass

        def validate(self, xml: bytes) -> None:
            observed.append(xml)

    monkeypatch.setattr(checker_module, "RestrictedDpsXsdValidator", Validator)
    taker = RestrictedDpsTaker(
        tax_id=FederalTaxId.cnpj("98ABC6780001Z0"),
        name="Synthetic",
        address=RestrictedDpsNationalAddress(
            municipality=MunicipalityCode("3550308"),
            postal_code="01234567",
            street="Rua A",
            number="1",
            neighborhood="Centro",
        ),
    )
    draft = replace(_draft(), taker=taker)
    xml = build_unsigned_dps(draft)
    if outside_subset == "long-name":
        invalid = xml.replace(b"Synthetic", b"X" * 151)
    else:
        start, end = xml.index(b"<end>"), xml.index(b"</end>") + len(b"</end>")
        invalid = xml[:start] + xml[end:]
    checker = RestrictedDpsChecker(b"mock")
    assert checker.parse(xml) == draft
    assert checker.check(invalid) == _IDENTITY
    with pytest.raises(DpsDocumentError):
        checker.parse(invalid)
    assert checker.check(xml) == _IDENTITY
    assert checker.parse(xml) == draft
    assert all(
        a is b for a, b in zip(observed, [xml, invalid, invalid, xml, xml], strict=True)
    )
