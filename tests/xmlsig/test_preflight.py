"""Tests for the private unsigned-DPS signature preflight."""

from __future__ import annotations

import copy
import traceback
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from xml.etree import ElementTree

import pytest

from nfse_br._xmlsig.preflight import (
    MAX_XML_BYTES,
    SignaturePreflightError,
    inspect_unsigned_dps,
)
from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

_NFSE = "http://www.sped.fazenda.gov.br/nfse"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_Q = f"{{{_NFSE}}}"
_EXPECTED_ID = "DPS2927408212ABC6780001Z000123000000000000042"


def _draft(
    *,
    series: str = "123",
    issue_municipality: str = "2927408",
    service_municipality: str = "3550308",
    description: str = "Servico sintetico",
) -> RestrictedDpsDraft:
    return RestrictedDpsDraft(
        issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        issue_municipality=MunicipalityCode(issue_municipality),
        service_municipality=MunicipalityCode(service_municipality),
        series=DpsSeries(series),
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
        service_description=description,
        service_amount=Decimal("1.23"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )


def _xml(**changes: str) -> bytes:
    return build_unsigned_dps(_draft(**changes))


def _root(xml_bytes: bytes | None = None) -> ElementTree.Element:
    return ElementTree.fromstring(xml_bytes if xml_bytes is not None else _xml())


def _serialize(root: ElementTree.Element) -> bytes:
    return cast(
        bytes,
        ElementTree.tostring(root, encoding="utf-8", xml_declaration=True),
    )


def _information(root: ElementTree.Element) -> ElementTree.Element:
    information = root.find(f"{_Q}infDPS")
    assert information is not None
    return information


def _element(root: ElementTree.Element, path: str) -> ElementTree.Element:
    element = root.find(path)
    assert element is not None
    return element


def _reject(xml_bytes: object, code: str) -> SignaturePreflightError:
    with pytest.raises(SignaturePreflightError) as caught:
        inspect_unsigned_dps(cast(bytes, xml_bytes))
    assert caught.value.code == code
    return caught.value


def test_accepts_builder_output_and_returns_exact_id() -> None:
    assert inspect_unsigned_dps(_xml()) == _EXPECTED_ID


def test_accepts_lexical_series_alias_and_distinct_municipalities() -> None:
    regular = _xml(series="123")
    leading_zero = _xml(series="00123")

    assert regular != leading_zero
    assert inspect_unsigned_dps(regular) == inspect_unsigned_dps(leading_zero)
    root = _root(leading_zero)
    assert root.findtext(f"{_Q}infDPS/{_Q}cLocEmi") == "2927408"
    assert (
        root.findtext(f"{_Q}infDPS/{_Q}serv/{_Q}locPrest/{_Q}cLocPrestacao")
        == "3550308"
    )


def test_escaped_signature_like_text_is_not_an_element() -> None:
    description = '<Signature Id="attacker">& data</Signature>'
    xml_bytes = _xml(description=description)

    assert inspect_unsigned_dps(xml_bytes) == _EXPECTED_ID
    root = _root(xml_bytes)
    service_description = _element(
        root,
        f"{_Q}infDPS/{_Q}serv/{_Q}cServ/{_Q}xDescServ",
    )
    assert service_description.text == description
    assert list(service_description) == []


@pytest.mark.parametrize("value", [None, "", bytearray(), b""])
def test_requires_exact_nonempty_bytes(value: object) -> None:
    code = (
        "empty_document"
        if type(value) is bytes and not value
        else "invalid_runtime_type"
    )
    _reject(value, code)


def test_rejects_document_over_local_limit_before_parsing() -> None:
    _reject(b" " * (MAX_XML_BYTES + 1), "document_too_large")


@pytest.mark.parametrize(
    "xml_bytes",
    [
        b"<DPS>",
        b"\xff",
        b'<?xml version="1.0" encoding="ISO-8859-1"?><DPS/>',
        b'<!DOCTYPE DPS [<!ENTITY secret SYSTEM "file:///etc/passwd">]><DPS/>',
        b"\x00<DPS/>",
    ],
)
def test_rejects_unsafe_or_malformed_xml(xml_bytes: bytes) -> None:
    _reject(xml_bytes, "unsafe_or_malformed_xml")


def test_rejects_wrong_root_and_wrapper() -> None:
    root = _root()
    root.tag = f"{{{_NFSE}}}Other"
    _reject(_serialize(root), "unexpected_root")

    wrapper = ElementTree.Element(f"{{{_NFSE}}}wrapper")
    wrapper.append(_root())
    _reject(_serialize(wrapper), "unexpected_root")


@pytest.mark.parametrize("version", [None, "", "1.00", "1.1"])
def test_requires_exact_schema_version(version: str | None) -> None:
    root = _root()
    if version is None:
        del root.attrib["versao"]
    else:
        root.set("versao", version)
    _reject(_serialize(root), "unexpected_version")


def test_rejects_missing_direct_and_nested_information_elements() -> None:
    root = _root()
    root.remove(_information(root))
    _reject(_serialize(root), "ambiguous_information_element")

    root = _root()
    root.append(copy.deepcopy(_information(root)))
    _reject(_serialize(root), "ambiguous_information_element")

    root = _root()
    information = _information(root)
    _element(information, f"{_Q}serv").append(copy.deepcopy(information))
    _reject(_serialize(root), "ambiguous_information_element")


def test_rejects_wrong_namespace_and_unexpected_root_children() -> None:
    root = _root()
    _information(root).tag = "{urn:wrong}infDPS"
    _reject(_serialize(root), "ambiguous_information_element")

    root = _root()
    root.append(ElementTree.Element("{urn:wrong}infDPS"))
    _reject(_serialize(root), "ambiguous_information_element")

    root = _root()
    root.append(ElementTree.Element(f"{_Q}unexpected"))
    _reject(_serialize(root), "unexpected_root_structure")


@pytest.mark.parametrize("nested", [False, True])
def test_rejects_any_preexisting_signature_element(nested: bool) -> None:
    root = _root()
    signature = ElementTree.Element(f"{{{_DS}}}Signature")
    (root if not nested else _information(root)).append(signature)
    _reject(_serialize(root), "signature_already_present")

    root = _root()
    _information(root).append(ElementTree.Element("{urn:other}Signature"))
    _reject(_serialize(root), "signature_already_present")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tpAmb", "1"),
        ("tpAmb", " 2"),
        ("tpEmit", "2"),
        ("tpEmit", "1 "),
    ],
)
def test_rejects_values_outside_the_local_builder_profile(
    field: str,
    value: str,
) -> None:
    root = _root()
    _element(root, f"{_Q}infDPS/{_Q}{field}").text = value
    _reject(_serialize(root), "unsupported_local_profile")


def test_requires_local_profile_fields_to_be_unique_direct_simple_elements() -> None:
    root = _root()
    information = _information(root)
    duplicate = ElementTree.Element(f"{_Q}tpAmb")
    duplicate.text = "2"
    information.append(duplicate)
    _reject(_serialize(root), "ambiguous_profile_field")

    root = _root()
    information = _information(root)
    environment = _element(information, f"{_Q}tpAmb")
    information.remove(environment)
    _element(information, f"{_Q}prest").append(environment)
    _reject(_serialize(root), "ambiguous_profile_field")

    root = _root()
    _element(root, f"{_Q}infDPS/{_Q}tpEmit").tag = "{urn:wrong}tpEmit"
    _reject(_serialize(root), "ambiguous_profile_field")

    root = _root()
    environment = _element(root, f"{_Q}infDPS/{_Q}tpAmb")
    environment.append(ElementTree.Element(f"{_Q}extra"))
    _reject(_serialize(root), "ambiguous_profile_field")


@pytest.mark.parametrize("identity", [None, "", "DPS-not-valid"])
def test_requires_one_lexically_valid_target_id(identity: str | None) -> None:
    root = _root()
    information = _information(root)
    if identity is None:
        del information.attrib["Id"]
    else:
        information.set("Id", identity)
    _reject(_serialize(root), "invalid_target_id")


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("Id", "duplicate"),
        ("id", "duplicate"),
        ("ID", "duplicate"),
        ("{http://www.w3.org/XML/1998/namespace}id", "duplicate"),
        ("{urn:attacker}Id", "duplicate"),
        ("{urn:attacker}id", "duplicate"),
        ("{urn:attacker}ID", "duplicate"),
    ],
)
def test_rejects_alternative_or_duplicate_identifiers(
    attribute: str,
    value: str,
) -> None:
    root = _root()
    _element(root, f"{_Q}infDPS/{_Q}serv").set(attribute, value)
    _reject(_serialize(root), "ambiguous_identifier")


@pytest.mark.parametrize(
    "attribute",
    [
        "{http://www.w3.org/XML/1998/namespace}id",
        "{urn:attacker}Id",
        "{urn:attacker}id",
        "{urn:attacker}ID",
    ],
)
def test_rejects_alternative_identifier_on_target(attribute: str) -> None:
    root = _root()
    _information(root).set(attribute, "duplicate")
    _reject(_serialize(root), "ambiguous_identifier")


def test_rejects_rebound_prefix_identifier_on_target() -> None:
    xml_bytes = _xml()
    marker = b'<infDPS Id="'
    if xml_bytes.count(marker) != 1:
        pytest.fail("the synthetic fixture no longer has one unprefixed infDPS")
    mutated = xml_bytes.replace(
        marker,
        b'<infDPS xmlns:alternate="urn:attacker" alternate:Id="shadow" Id="',
        1,
    )

    _reject(mutated, "ambiguous_identifier")


@pytest.mark.parametrize(
    "path",
    [
        f"{_Q}cLocEmi",
        f"{_Q}prest/{_Q}CNPJ",
        f"{_Q}serie",
        f"{_Q}nDPS",
    ],
)
def test_rejects_duplicate_identity_fields_anywhere(path: str) -> None:
    root = _root()
    information = _information(root)
    duplicate = copy.deepcopy(_element(information, path))
    _element(information, f"{_Q}serv").append(duplicate)
    _reject(_serialize(root), "ambiguous_identity_field")


def test_rejects_identity_field_in_wrong_namespace_or_with_child_content() -> None:
    root = _root()
    series = _element(root, f"{_Q}infDPS/{_Q}serie")
    series.tag = "{urn:wrong}serie"
    _reject(_serialize(root), "ambiguous_identity_field")

    root = _root()
    series = _element(root, f"{_Q}infDPS/{_Q}serie")
    series.append(ElementTree.Element(f"{_Q}nested"))
    _reject(_serialize(root), "ambiguous_identity_field")


def test_rejects_mixed_identity_field_content() -> None:
    root = _root()
    number = _element(root, f"{_Q}infDPS/{_Q}nDPS")
    number.append(ElementTree.Element(f"{_Q}extra"))
    _reject(_serialize(root), "ambiguous_identity_field")


def test_rejects_identity_value_present_only_in_a_descendant() -> None:
    root = _root()
    municipality = _element(root, f"{_Q}infDPS/{_Q}cLocEmi")
    original_text = municipality.text
    municipality.text = None
    child = ElementTree.SubElement(municipality, f"{_Q}extra")
    child.text = original_text
    _reject(_serialize(root), "ambiguous_identity_field")


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (f"{_Q}cLocEmi", "3550308", "identity_mismatch"),
        (f"{_Q}prest/{_Q}CNPJ", "12ABC6780001Z1", "identity_mismatch"),
        (f"{_Q}serie", "124", "identity_mismatch"),
        (f"{_Q}nDPS", "43", "identity_mismatch"),
        (f"{_Q}prest/{_Q}CNPJ", "12abc6780001z0", "invalid_identity_fields"),
        (f"{_Q}cLocEmi", " 2927408", "invalid_identity_fields"),
        (f"{_Q}serie", " 123", "invalid_identity_fields"),
    ],
)
def test_rejects_fields_that_contradict_or_normalize_the_id(
    path: str,
    value: str,
    code: str,
) -> None:
    root = _root()
    _element(root, f"{_Q}infDPS/{path}").text = value
    _reject(_serialize(root), code)


@pytest.mark.parametrize("value", ["0", "+42", "042", "-1", "1.0", "", " 42"])
def test_rejects_invalid_dps_number_lexical_forms(value: str) -> None:
    root = _root()
    _element(root, f"{_Q}infDPS/{_Q}nDPS").text = value
    _reject(_serialize(root), "invalid_identity_fields")


def test_valid_invalid_valid_calls_are_independent() -> None:
    valid = _xml()
    invalid_root = _root(valid)
    _element(invalid_root, f"{_Q}infDPS/{_Q}nDPS").text = "0"

    assert inspect_unsigned_dps(valid) == _EXPECTED_ID
    _reject(_serialize(invalid_root), "invalid_identity_fields")
    assert inspect_unsigned_dps(valid) == _EXPECTED_ID


def test_errors_and_tracebacks_do_not_disclose_fiscal_input() -> None:
    root = _root(_xml(description="private service description"))
    information = _information(root)
    sensitive_id = information.attrib["Id"]
    sensitive_cnpj = _element(information, f"{_Q}prest/{_Q}CNPJ").text
    information.set("xml:id", "malicious-private-value")

    try:
        inspect_unsigned_dps(_serialize(root))
    except SignaturePreflightError as exc:
        rendered = "\n".join(
            (
                str(exc),
                repr(exc),
                "".join(traceback.format_exception(exc)),
            )
        )
    else:
        pytest.fail("ambiguous identifier was accepted")

    assert sensitive_id not in rendered
    assert sensitive_cnpj is not None and sensitive_cnpj not in rendered
    assert "private service description" not in rendered
    assert "malicious-private-value" not in rendered
    assert "xml:id" not in rendered
