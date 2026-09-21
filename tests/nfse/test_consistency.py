"""Tests for local NFS-e and embedded-DPS consistency validation."""

from __future__ import annotations

import traceback
from typing import cast

import pytest

import nfse_br.nfse
from nfse_br.nfse import (
    NfseConsistencyError,
    validate_nfse_document_consistency,
)

_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_MUNICIPALITY = "2927408"
_CNPJ = "12ABC6780001Z0"
_CPF = "12345678901"
_NFSE_NUMBER = "42"
_SERIES = "123"
_DPS_NUMBER = "42"


def _federal_component(kind: str, value: str) -> str:
    return value if kind == "CNPJ" else value.zfill(14)


def _inscription_type(kind: str) -> str:
    return "2" if kind == "CNPJ" else "1"


def _dps_id(
    *,
    municipality: str = _MUNICIPALITY,
    kind: str = "CNPJ",
    federal_value: str = _CNPJ,
    series: str = _SERIES,
    number: str = _DPS_NUMBER,
) -> str:
    return (
        "DPS"
        + municipality
        + _inscription_type(kind)
        + _federal_component(kind, federal_value)
        + series.zfill(5)
        + number.zfill(15)
    )


def _nfse_id(
    *,
    municipality: str = _MUNICIPALITY,
    kind: str = "CNPJ",
    federal_value: str = _CNPJ,
) -> str:
    return (
        "NFS"
        + municipality
        + "2"
        + _inscription_type(kind)
        + _federal_component(kind, federal_value)
        + _NFSE_NUMBER.zfill(13)
        + "2609"
        + "000000001"
        + "0"
    )


def _document(
    *,
    tp_emit: str = "1",
    emitter_name: str | None = None,
    kind: str = "CNPJ",
    federal_value: str | None = None,
    municipality: str = _MUNICIPALITY,
    nfse_id: str | None = None,
    dps_id: str | None = None,
    series: str = _SERIES,
    dps_number: str = _DPS_NUMBER,
    nfse_number: str = _NFSE_NUMBER,
    extra: str = "",
) -> bytes:
    if emitter_name is None:
        emitter_name = {"1": "prest", "2": "toma", "3": "interm"}.get(tp_emit, "prest")
    if federal_value is None:
        federal_value = _CNPJ if kind == "CNPJ" else _CPF
    if nfse_id is None:
        nfse_id = _nfse_id(kind=kind, federal_value=federal_value)
    if dps_id is None:
        dps_id = _dps_id(
            municipality=municipality,
            kind=kind,
            federal_value=federal_value,
            series=series,
            number=dps_number,
        )
    return (
        f'<NFSe xmlns="{_NAMESPACE}">'
        f'<infNFSe Id="{nfse_id}">'
        f"<nNFSe>{nfse_number}</nNFSe>"
        f'<DPS><infDPS Id="{dps_id}">'
        f"<tpEmit>{tp_emit}</tpEmit>"
        f"<cLocEmi>{municipality}</cLocEmi>"
        f"<serie>{series}</serie>"
        f"<nDPS>{dps_number}</nDPS>"
        f"<{emitter_name}><{kind}>{federal_value}</{kind}></{emitter_name}>"
        f"{extra}"
        "</infDPS></DPS>"
        "</infNFSe>"
        "</NFSe>"
    ).encode()


def _assert_rejected(xml: object, code: str) -> NfseConsistencyError:
    with pytest.raises(NfseConsistencyError) as exc_info:
        validate_nfse_document_consistency(cast(bytes, xml))
    error = exc_info.value
    assert error.code == code
    assert str(error) == f"NFS-e consistency validation failed ({code})."
    assert repr(error) == f"NfseConsistencyError(code={code!r})"
    return error


@pytest.mark.parametrize(
    ("tp_emit", "kind", "federal_value"),
    [
        ("1", "CNPJ", _CNPJ),
        ("1", "CPF", _CPF),
        ("2", "CNPJ", _CNPJ),
        ("3", "CPF", _CPF),
    ],
)
def test_accepts_each_confirmed_issuer_path(
    tp_emit: str,
    kind: str,
    federal_value: str,
) -> None:
    validate_nfse_document_consistency(
        _document(tp_emit=tp_emit, kind=kind, federal_value=federal_value)
    )


def test_rejects_embedded_dps_identity_mismatch() -> None:
    mismatched = _dps_id(series="124")
    _assert_rejected(_document(dps_id=mismatched), "embedded_dps_identity_mismatch")


def test_rejects_confirmed_municipality_mismatch_only() -> None:
    other = "3550308"
    _assert_rejected(
        _document(municipality=other, dps_id=_dps_id(municipality=other)),
        "municipality_mismatch",
    )


def test_rejects_confirmed_federal_registration_mismatch_only() -> None:
    other = "98XYZ6540001W0"
    _assert_rejected(
        _document(
            federal_value=other,
            nfse_id=_nfse_id(),
            dps_id=_dps_id(federal_value=other),
        ),
        "federal_registration_mismatch",
    )


@pytest.mark.parametrize(
    "xml",
    [
        "not-bytes",
        b"<NFSe",
        b'<!DOCTYPE NFSe [<!ENTITY x "secret">]><NFSe>&x;</NFSe>',
        b'<DPS xmlns="http://www.sped.fazenda.gov.br/nfse"/>',
        _document(tp_emit="4"),
        _document(series="90000"),
        _document(dps_number="0"),
        _document(municipality="123"),
        _document(emitter_name="prest")
        .replace(b"<prest>", b'<other:prest xmlns:other="urn:wrong">', 1)
        .replace(b"</prest>", b"</other:prest>", 1),
    ],
)
def test_maps_unsafe_or_unusable_documents_to_one_controlled_error(xml: object) -> None:
    _assert_rejected(xml, "unsafe_or_malformed_document")


def test_rejects_missing_duplicate_or_non_leaf_confirmed_fields() -> None:
    valid = _document()
    cases = (
        valid.replace(b"<tpEmit>1</tpEmit>", b"", 1),
        valid.replace(
            b"<tpEmit>1</tpEmit>", b"<tpEmit>1</tpEmit><tpEmit>1</tpEmit>", 1
        ),
        valid.replace(b"<serie>123</serie>", b"<serie><nested/></serie>", 1),
        valid.replace(b"<CNPJ>12ABC6780001Z0</CNPJ>", b"", 1),
        valid.replace(
            b"<CNPJ>12ABC6780001Z0</CNPJ>",
            b"<CNPJ>12ABC6780001Z0</CNPJ><CPF>12345678901</CPF>",
            1,
        ),
        valid.replace(b"<CNPJ>12ABC6780001Z0</CNPJ>", b"<CNPJ><nested/></CNPJ>", 1),
        valid.replace(
            b"<CNPJ>12ABC6780001Z0</CNPJ>",
            b'<wrong:CNPJ xmlns:wrong="urn:wrong">12ABC6780001Z0</wrong:CNPJ>',
            1,
        ),
        valid.replace(b"12ABC6780001Z0</CNPJ>", b"12abc6780001z0</CNPJ>", 1),
    )
    for case in cases:
        _assert_rejected(case, "unsafe_or_malformed_document")


def test_unconfirmed_number_relations_are_not_enforced() -> None:
    validate_nfse_document_consistency(_document(nfse_number=" 42 "))
    validate_nfse_document_consistency(
        _document(dps_number="43", dps_id=_dps_id(number="43"))
    )


def test_environment_like_elements_and_non_selected_party_are_not_compared() -> None:
    extra = "<tpAmb>1</tpAmb><ambGer>9</ambGer><prest><CPF>00000000000</CPF></prest>"
    validate_nfse_document_consistency(_document(tp_emit="2", extra=extra))


def test_signature_and_schema_location_do_not_expand_consistency_scope() -> None:
    xml = (
        _document()
        .replace(
            b"<NFSe ",
            b'<NFSe xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            b'xsi:schemaLocation="urn:any https://example.invalid/attacker.xsd" ',
            1,
        )
        .replace(
            b"</NFSe>",
            b'<Signature xmlns="http://www.w3.org/2000/09/xmldsig#"><SignatureValue>AA==</SignatureValue></Signature></NFSe>',
            1,
        )
    )
    validate_nfse_document_consistency(xml)


def test_errors_never_disclose_fiscal_values() -> None:
    sensitive = "98XYZ6540001W0"
    xml = _document(
        federal_value=sensitive,
        nfse_id=_nfse_id(),
        dps_id=_dps_id(federal_value=sensitive),
    )
    try:
        validate_nfse_document_consistency(xml)
    except NfseConsistencyError as error:
        rendered = "".join(traceback.format_exception(error))
        for value in (sensitive, _MUNICIPALITY, _NFSE_NUMBER):
            assert value not in str(error)
            assert value not in repr(error)
            assert value not in rendered
    else:
        raise AssertionError("Inconsistent synthetic document was accepted")


def test_error_constructor_accepts_only_stable_controlled_codes() -> None:
    error = NfseConsistencyError("municipality_mismatch")
    assert error.code == "municipality_mismatch"

    sensitive = "synthetic-sensitive-identifier"
    with pytest.raises(ValueError) as string_error:
        NfseConsistencyError(sensitive)
    with pytest.raises(ValueError):
        NfseConsistencyError(cast(str, 42))
    assert sensitive not in str(string_error.value)
    assert sensitive not in repr(string_error.value)


def test_public_surface_has_no_access_key_derivation() -> None:
    assert not hasattr(nfse_br.nfse, "validate_nfse_access_key_consistency")
    assert not hasattr(nfse_br.nfse, "derive_nfse_access_key")
    assert nfse_br.nfse.__all__ == [
        "NfseAccessKey",
        "NfseConsistencyError",
        "NfseDocumentError",
        "NfseDocumentInfo",
        "NfseId",
        "extract_nfse_document_info",
        "validate_nfse_document_consistency",
    ]
