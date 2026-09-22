"""Tests for the composed recovered NFS-e checker."""

from __future__ import annotations

import traceback
from typing import Never

import pytest

from nfse_br.nfse import (
    NfseConsistencyError,
    NfseDocumentError,
    NfseDocumentInfo,
    NfseId,
)
from nfse_br.xsd import RecoveredNfseChecker, XsdValidationError
from nfse_br.xsd import nfse_checker as checker_module

_INFO = NfseDocumentInfo(
    nfse_id=NfseId("NFS" + "1" * 50),
    nfse_number="42",
    embedded_dps_id="synthetic-embedded-dps-id",
)


def test_constructor_passes_the_exact_bundle_to_recovered_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = bytes(bytearray(b"synthetic bundle"))
    observed: list[bytes] = []

    class Validator:
        def __init__(self, bundle_bytes: bytes) -> None:
            observed.append(bundle_bytes)

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", Validator)

    RecoveredNfseChecker(bundle)

    assert observed == [bundle]
    assert observed[0] is bundle


def test_constructor_propagates_the_same_xsd_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = XsdValidationError(phase="bundle", code="digest_mismatch")

    def reject(_bundle_bytes: bytes) -> Never:
        raise failure

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", reject)

    with pytest.raises(XsdValidationError) as caught:
        RecoveredNfseChecker(b"synthetic bundle")

    assert caught.value is failure


def test_check_orders_stages_reuses_exact_bytes_and_returns_exact_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, bytes]] = []

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            observed.append(("xsd", xml_bytes))

    def extract(xml_bytes: bytes) -> NfseDocumentInfo:
        observed.append(("structure", xml_bytes))
        return _INFO

    def consistency(xml_bytes: bytes) -> None:
        observed.append(("consistency", xml_bytes))

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", Validator)
    monkeypatch.setattr(checker_module, "extract_nfse_document_info", extract)
    monkeypatch.setattr(
        checker_module,
        "validate_nfse_document_consistency",
        consistency,
    )
    xml_bytes = bytes(bytearray(b"synthetic XML bytes"))

    result = RecoveredNfseChecker(b"bundle").check(xml_bytes)

    assert result is _INFO
    assert [stage for stage, _xml in observed] == ["xsd", "structure", "consistency"]
    assert all(observed_xml is xml_bytes for _stage, observed_xml in observed)


@pytest.mark.parametrize(
    ("stage", "failure"),
    [
        ("xsd", XsdValidationError(phase="schema", code="document_invalid")),
        ("structure", NfseDocumentError("invalid_nfse_id")),
        ("consistency", NfseConsistencyError("municipality_mismatch")),
    ],
)
def test_check_short_circuits_and_propagates_the_same_stage_error(
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

    def extract(_xml_bytes: bytes) -> NfseDocumentInfo:
        calls.append("structure")
        if stage == "structure":
            raise failure
        return _INFO

    def consistency(_xml_bytes: bytes) -> None:
        calls.append("consistency")
        if stage == "consistency":
            raise failure

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", Validator)
    monkeypatch.setattr(checker_module, "extract_nfse_document_info", extract)
    monkeypatch.setattr(
        checker_module,
        "validate_nfse_document_consistency",
        consistency,
    )

    with pytest.raises(type(failure)) as caught:
        RecoveredNfseChecker(b"bundle").check(b"synthetic XML")

    assert caught.value is failure
    expected_calls = {
        "xsd": ["xsd"],
        "structure": ["xsd", "structure"],
        "consistency": ["xsd", "structure", "consistency"],
    }
    assert calls == expected_calls[stage]


def test_checker_is_reusable_after_a_rejected_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, xml_bytes: bytes) -> None:
            if xml_bytes == b"bad":
                raise XsdValidationError(phase="schema", code="document_invalid")

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", Validator)
    monkeypatch.setattr(
        checker_module,
        "extract_nfse_document_info",
        lambda _xml: _INFO,
    )
    monkeypatch.setattr(
        checker_module,
        "validate_nfse_document_consistency",
        lambda _xml: None,
    )
    checker = RecoveredNfseChecker(b"bundle")

    assert checker.check(b"good") is _INFO
    with pytest.raises(XsdValidationError, match="document_invalid"):
        checker.check(b"bad")
    assert checker.check(b"good again") is _INFO


def test_propagated_errors_remain_privacy_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive = "NFS-SYNTHETIC-PRIVATE-IDENTIFIER"
    failure = NfseDocumentError("invalid_nfse_id")

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    def reject(_xml_bytes: bytes) -> Never:
        raise failure

    monkeypatch.setattr(checker_module, "RecoveredNfseValidator", Validator)
    monkeypatch.setattr(checker_module, "extract_nfse_document_info", reject)
    checker = RecoveredNfseChecker(b"bundle")

    with pytest.raises(NfseDocumentError) as caught:
        checker.check(sensitive.encode())

    rendered = "".join(traceback.format_exception(caught.value))
    assert caught.value is failure
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in rendered
