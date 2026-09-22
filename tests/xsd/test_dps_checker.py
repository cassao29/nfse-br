"""Tests for the composed restricted unsigned DPS checker."""

from __future__ import annotations

import traceback
from typing import Never

import pytest

from nfse_br.domain import FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsDocumentError, DpsIdentity, DpsNumber, DpsSeries
from nfse_br.xsd import RestrictedDpsChecker, XsdValidationError
from nfse_br.xsd import dps_checker as checker_module

_IDENTITY = DpsIdentity.build(
    municipality=MunicipalityCode("2927408"),
    federal_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
    series=DpsSeries("123"),
    number=DpsNumber(42),
)


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
