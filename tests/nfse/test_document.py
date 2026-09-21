"""Tests for privacy-safe structural NFS-e document extraction."""

from __future__ import annotations

import json
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest

import nfse_br.nfse
from nfse_br.nfse import (
    NfseAccessKey,
    NfseDocumentError,
    NfseDocumentInfo,
    NfseId,
    extract_nfse_document_info,
)
from nfse_br.nfse import document as document_module

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_NFSE_ID = "NFS" + "0" * 9 + "SYNTHETIC00000" + "0" * 27
_DPS_ID = "DPS" + "2927408" + "2" + "SYNTHETIC00000" + "0" * 20
_NFSE_NUMBER = "42"
_DEFAULT = object()


def _qname(local_name: str, prefix: str) -> str:
    return f"{prefix}:{local_name}" if prefix else local_name


def _default_information(prefix: str = "") -> str:
    inf_nfse = _qname("infNFSe", prefix)
    number = _qname("nNFSe", prefix)
    dps = _qname("DPS", prefix)
    inf_dps = _qname("infDPS", prefix)
    return (
        f'<{inf_nfse} Id="{_NFSE_ID}">'
        f"<{number}>{_NFSE_NUMBER}</{number}>"
        f'<{dps}><{inf_dps} Id="{_DPS_ID}"/></{dps}>'
        f"</{inf_nfse}>"
    )


def _document(
    *,
    information: object = _DEFAULT,
    root_name: str = "NFSe",
    namespace: str = _NAMESPACE,
    prefix: str = "",
    root_attributes: str = "",
    suffix: str = "",
) -> bytes:
    root = _qname(root_name, prefix)
    declaration = f'xmlns:{prefix}="{namespace}"' if prefix else f'xmlns="{namespace}"'
    body = _default_information(prefix) if information is _DEFAULT else information
    assert type(body) is str
    return (f"<{root} {declaration}{root_attributes}>{body}{suffix}</{root}>").encode()


def _replace_once(source: bytes, target: bytes, replacement: bytes) -> bytes:
    assert source.count(target) == 1
    return source.replace(target, replacement, 1)


def _assert_rejected(xml: object, code: str) -> NfseDocumentError:
    with pytest.raises(NfseDocumentError) as exc_info:
        extract_nfse_document_info(cast(bytes, xml))
    error = exc_info.value
    assert error.code == code
    assert str(error) == f"NFS-e document extraction failed ({code})."
    assert repr(error) == f"NfseDocumentError(code={code!r})"
    return error


def test_extracts_exact_direct_values_into_immutable_typed_information() -> None:
    info = extract_nfse_document_info(_document())

    assert type(info) is NfseDocumentInfo
    assert info.nfse_id == NfseId(_NFSE_ID)
    assert type(info.nfse_id) is NfseId
    assert info.nfse_number == _NFSE_NUMBER
    assert info.embedded_dps_id == _DPS_ID
    with pytest.raises(FrozenInstanceError):
        info.__setattr__("nfse_number", "43")


def test_namespace_prefix_does_not_change_expanded_names() -> None:
    assert extract_nfse_document_info(_document(prefix="national")) == (
        extract_nfse_document_info(_document())
    )


class BytesSubclass(bytes):
    """A bytes subclass that must not cross the exact runtime boundary."""


@pytest.mark.parametrize(
    "value",
    [
        "<NFSe/>",
        bytearray(b"<NFSe/>"),
        memoryview(b"<NFSe/>"),
        BytesSubclass(_document()),
    ],
)
def test_requires_exact_bytes_without_coercion(value: object) -> None:
    _assert_rejected(value, "invalid_runtime_type")


def test_rejects_empty_and_oversized_documents() -> None:
    _assert_rejected(b"", "empty_document")
    _assert_rejected(b"x" * (document_module.MAX_XML_BYTES + 1), "document_too_large")


@pytest.mark.parametrize(
    "xml",
    [
        b"<NFSe>",
        b"\xff<NFSe/>",
        "<NFSe/>".encode("utf-16"),
        b'<!DOCTYPE NFSe SYSTEM "https://example.invalid/nfse.dtd"><NFSe/>',
        b'<!DOCTYPE NFSe [<!ENTITY sensitive "secret">]><NFSe>&sensitive;</NFSe>',
    ],
)
def test_rejects_unsafe_malformed_or_non_utf8_xml(xml: bytes) -> None:
    _assert_rejected(xml, "unsafe_or_malformed_xml")


def test_accepts_utf8_bom_under_the_shared_safe_parser_policy() -> None:
    info = extract_nfse_document_info(b"\xef\xbb\xbf" + _document())

    assert info.nfse_number == _NFSE_NUMBER


@pytest.mark.parametrize(
    "xml",
    [
        _document(root_name="Other"),
        _document(namespace="urn:wrong"),
    ],
)
def test_requires_the_exact_nfse_root_qname(xml: bytes) -> None:
    _assert_rejected(xml, "unexpected_root")


def test_requires_one_exact_direct_information_element() -> None:
    valid_information = _default_information()
    wrong_namespace = (
        '<wrong:infNFSe xmlns:wrong="urn:wrong" Id="'
        + _NFSE_ID
        + '"><wrong:nNFSe>42</wrong:nNFSe></wrong:infNFSe>'
    )

    for xml in (
        _document(information=""),
        _document(information=valid_information + valid_information),
        _document(information=wrong_namespace),
        _document(information=valid_information + wrong_namespace),
    ):
        _assert_rejected(xml, "ambiguous_information_element")


def test_requires_one_exact_direct_leaf_nfse_number() -> None:
    valid = _default_information()
    missing = _replace_once(valid.encode(), b"<nNFSe>42</nNFSe>", b"")
    duplicate = _replace_once(
        valid.encode(),
        b"<nNFSe>42</nNFSe>",
        b"<nNFSe>42</nNFSe><nNFSe>43</nNFSe>",
    )
    nested = _replace_once(
        valid.encode(),
        b"<nNFSe>42</nNFSe>",
        b"<wrapper><nNFSe>42</nNFSe></wrapper>",
    )
    wrong_namespace = _replace_once(
        valid.encode(),
        b"<nNFSe>42</nNFSe>",
        b'<wrong:nNFSe xmlns:wrong="urn:wrong">42</wrong:nNFSe>',
    )
    with_child = _replace_once(
        valid.encode(),
        b"<nNFSe>42</nNFSe>",
        b"<nNFSe><value>42</value></nNFSe>",
    )
    empty = _replace_once(
        valid.encode(),
        b"<nNFSe>42</nNFSe>",
        b"<nNFSe/>",
    )

    for information in (missing, duplicate, nested, wrong_namespace):
        _assert_rejected(
            _document(information=information.decode()),
            "ambiguous_nfse_number",
        )
    for information in (with_child, empty):
        _assert_rejected(
            _document(information=information.decode()),
            "invalid_nfse_number",
        )


def test_preserves_nfse_number_text_without_normalization() -> None:
    information = _default_information().replace(
        "<nNFSe>42</nNFSe>",
        "<nNFSe> 42 </nNFSe>",
    )

    assert (
        extract_nfse_document_info(_document(information=information)).nfse_number
        == " 42 "
    )


def test_requires_one_exact_embedded_dps_path() -> None:
    valid = _default_information().encode()
    dps = f'<DPS><infDPS Id="{_DPS_ID}"/></DPS>'.encode()
    inf_dps = f'<infDPS Id="{_DPS_ID}"/>'.encode()
    cases = (
        _replace_once(valid, dps, b""),
        _replace_once(valid, dps, dps + dps),
        _replace_once(
            valid,
            dps,
            b'<wrong:DPS xmlns:wrong="urn:wrong"><wrong:infDPS/></wrong:DPS>',
        ),
        _replace_once(valid, inf_dps, b""),
        _replace_once(valid, inf_dps, inf_dps + inf_dps),
        _replace_once(
            valid,
            inf_dps,
            f'<wrong:infDPS xmlns:wrong="urn:wrong" Id="{_DPS_ID}"/>'.encode(),
        ),
    )

    for information in cases:
        _assert_rejected(
            _document(information=information.decode()),
            "ambiguous_embedded_dps",
        )


@pytest.mark.parametrize("attribute_name", ["id", "ID"])
def test_nfse_id_attribute_is_case_sensitive(attribute_name: str) -> None:
    information = _default_information().replace(' Id="', f' {attribute_name}="', 1)

    _assert_rejected(_document(information=information), "invalid_nfse_id")


def test_nfse_id_must_be_present_unambiguous_and_lexically_valid() -> None:
    valid = _default_information()
    missing = valid.replace(f' Id="{_NFSE_ID}"', "", 1)
    invalid = valid.replace(_NFSE_ID, _NFSE_ID[:-1] + "!", 1)
    xml_id = valid.replace(
        f' Id="{_NFSE_ID}"',
        f' Id="{_NFSE_ID}" xml:id="synthetic-shadow"',
        1,
    )

    for information in (missing, invalid, xml_id):
        _assert_rejected(_document(information=information), "invalid_nfse_id")


@pytest.mark.parametrize("attribute_name", ["id", "ID"])
def test_embedded_dps_id_attribute_is_case_sensitive(attribute_name: str) -> None:
    information = _default_information().replace(
        f' Id="{_DPS_ID}"',
        f' {attribute_name}="{_DPS_ID}"',
        1,
    )

    _assert_rejected(_document(information=information), "invalid_embedded_dps_id")


def test_embedded_dps_id_must_be_present_unambiguous_and_lexically_valid() -> None:
    valid = _default_information()
    missing = valid.replace(f' Id="{_DPS_ID}"', "", 1)
    invalid = valid.replace(_DPS_ID, _DPS_ID[:-1] + "!", 1)
    xml_id = valid.replace(
        f' Id="{_DPS_ID}"',
        f' Id="{_DPS_ID}" xml:id="synthetic-shadow"',
        1,
    )

    for information in (missing, invalid, xml_id):
        _assert_rejected(
            _document(information=information),
            "invalid_embedded_dps_id",
        )


def test_extra_elements_signature_and_schema_location_do_not_expand_scope() -> None:
    signature = (
        '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        "<unverified>synthetic</unverified>"
        "</Signature>"
    )
    xml = _document(
        root_attributes=(
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xsi:schemaLocation="http://www.sped.fazenda.gov.br/nfse '
            'https://example.invalid/attacker.xsd"'
        ),
        suffix="<extra>ignored</extra>" + signature,
    )

    info = extract_nfse_document_info(xml)

    assert info.nfse_number == _NFSE_NUMBER
    assert not hasattr(info, "signature_valid")


def test_information_surface_never_derives_or_returns_an_access_key() -> None:
    info = extract_nfse_document_info(_document())

    assert not hasattr(info, "access_key")
    assert not hasattr(info, "nfse_access_key")
    assert not hasattr(info, "key")
    assert not hasattr(info, "to_access_key")
    assert all(
        not isinstance(value, NfseAccessKey)
        for value in (info.nfse_id, info.nfse_number, info.embedded_dps_id)
    )


def test_representations_and_failures_do_not_disclose_fiscal_values() -> None:
    info = extract_nfse_document_info(_document())
    representation = repr(info)
    assert representation == (
        "NfseDocumentInfo(nfse_id=<redacted>, nfse_number=<redacted>, "
        "embedded_dps_id=<redacted>)"
    )
    for sensitive in (_NFSE_ID, _NFSE_NUMBER, _DPS_ID):
        assert sensitive not in representation

    sensitive_invalid = _NFSE_ID[:-1] + "!"
    invalid = _document(
        information=_default_information().replace(_NFSE_ID, sensitive_invalid, 1)
    )
    try:
        extract_nfse_document_info(invalid)
    except NfseDocumentError as error:
        rendered = "".join(traceback.format_exception(error))
        for sensitive in (sensitive_invalid, _NFSE_NUMBER, _DPS_ID):
            assert sensitive not in str(error)
            assert sensitive not in repr(error)
            assert sensitive not in rendered
    else:
        raise AssertionError("Invalid synthetic identifier was unexpectedly accepted")


def test_error_constructor_accepts_only_the_stable_controlled_codes() -> None:
    error = NfseDocumentError("unexpected_root")
    assert error.code == "unexpected_root"

    sensitive = "secret-value-from-payload"
    with pytest.raises(ValueError) as string_error:
        NfseDocumentError(sensitive)
    with pytest.raises(ValueError):
        NfseDocumentError(cast(str, 42))
    assert sensitive not in str(string_error.value)
    assert sensitive not in repr(string_error.value)


def test_public_subpackage_exports_document_information_api() -> None:
    assert nfse_br.nfse.__all__ == [
        "NfseAccessKey",
        "NfseConsistencyError",
        "NfseDocumentError",
        "NfseDocumentInfo",
        "NfseId",
        "extract_nfse_document_info",
        "validate_nfse_document_consistency",
    ]


def test_frozen_contract_matches_runtime_paths_and_source_pins() -> None:
    contract_path = (
        _REPOSITORY_ROOT
        / "contracts"
        / "restricted"
        / "nfse-document-info-contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract["bundle"] == {
        "sha256": "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc",
        "size": 34933,
    }
    assert contract["source_members"] == {
        "NFSe_v1.01.xsd": {
            "sha256": (
                "1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0"
            ),
            "size": 738,
        },
        "tiposComplexos_v1.01.xsd": {
            "sha256": (
                "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
            ),
            "size": 114148,
        },
        "tiposSimples_v1.01.xsd": {
            "sha256": (
                "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
            ),
            "size": 69488,
        },
    }
    paths = contract["extractor_contract"]
    assert paths["root"] == {
        "element": "NFSe",
        "qname": document_module._NFSE_ROOT_QNAME,
        "type": "TCNFSe",
    }
    assert paths["information"] == {
        "element": "infNFSe",
        "max_occurs": 1,
        "min_occurs": 1,
        "path": "NFSe/infNFSe",
        "type": "TCInfNFSe",
    }
    assert paths["nfse_id"]["path"] == "NFSe/infNFSe/@Id"
    assert paths["nfse_id"]["type"] == "TSIdNFSe"
    assert paths["nfse_number"] == {
        "base": "xs:string",
        "element": "nNFSe",
        "facets": {
            "maxLength": 13,
            "pattern": "[1-9]{1}[0-9]{0,12}",
            "whiteSpace": "preserve",
        },
        "max_occurs": 1,
        "min_occurs": 1,
        "path": "NFSe/infNFSe/nNFSe",
        "type": "TSNNFSe",
    }
    assert paths["embedded_dps"]["path"] == "NFSe/infNFSe/DPS"
    assert paths["embedded_dps_information"]["path"] == ("NFSe/infNFSe/DPS/infDPS")
    assert paths["embedded_dps_id"]["path"] == ("NFSe/infNFSe/DPS/infDPS/@Id")
    assert paths["embedded_dps_id"]["facets"]["pattern"] == (
        "DPS[0-9]{7}(1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"
    )
    assert document_module._DPS_ID_PATTERN_TEXT == (
        "DPS[0-9]{7}(?:1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"
    )
    assert contract["policy"]["xsd_validation_implied"] is False
    assert contract["policy"]["access_key_derivation"] is False
    assert contract["transmission_ready"] is False
