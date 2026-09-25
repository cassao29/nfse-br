"""Offline, closed-subset semantic round trips and hostile document rejection."""

from __future__ import annotations

import subprocess
import sys
import traceback
from dataclasses import fields, replace
from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal, Inexact, Rounded, localcontext
from typing import Any, cast
from xml.etree import ElementTree as ET

import pytest

from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import (
    DpsDocumentError,
    DpsIdentity,
    DpsNumber,
    DpsSeries,
    inspect_unsigned_dps,
    parse_unsigned_dps,
)
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

_Q = "{http://www.sped.fazenda.gov.br/nfse}"


def _draft(**changes: Any) -> RestrictedDpsDraft:
    return replace(
        RestrictedDpsDraft(
            issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
            issue_municipality=MunicipalityCode("2927408"),
            service_municipality=MunicipalityCode("3550308"),
            series=DpsSeries("00123"),
            number=DpsNumber(42),
            issued_at=datetime(
                2026, 9, 17, 12, 34, 56, tzinfo=timezone(timedelta(hours=-3))
            ),
            competence=CompetenceDate(date(2026, 9, 16)),
            application_version="nfse-test-1",
            national_service_code="010101",
            service_description="Descrição sintética",
            service_amount=Decimal("123.45"),
            op_simp_nac="1",
            reg_esp_trib="0",
            trib_issqn="1",
            tp_ret_issqn="1",
            ind_tot_trib="0",
        ),
        **changes,
    )


def _xml() -> bytes:
    return build_unsigned_dps(_draft())


def _serialize(root: ET.Element) -> bytes:
    return cast(bytes, ET.tostring(root, encoding="utf-8"))


def _element(root: ET.Element, name: str) -> ET.Element:
    return next(root.iter(_Q + name))


def _reject(xml: object, code: str | None = None) -> DpsDocumentError:
    with pytest.raises(DpsDocumentError) as caught:
        parse_unsigned_dps(cast(bytes, xml))
    if code is not None:
        assert caught.value.code == code
    return caught.value


def _round_trip(draft: RestrictedDpsDraft) -> None:
    xml = build_unsigned_dps(draft)
    parsed = parse_unsigned_dps(xml)
    assert type(parsed) is RestrictedDpsDraft
    assert parsed == draft
    # Field-by-field catches omissions even if dataclass equality ever changes.
    for field in fields(draft):
        assert getattr(parsed, field.name) == getattr(draft, field.name)
    assert parsed.issued_at.utcoffset() == draft.issued_at.utcoffset()
    assert build_unsigned_dps(parsed) == xml
    identity = inspect_unsigned_dps(xml)
    assert type(identity) is DpsIdentity
    assert identity.series == draft.series
    assert identity.number == draft.number


def test_all_fields_round_trip() -> None:
    _round_trip(_draft())


@pytest.mark.parametrize(
    "field,value",
    [
        ("number", DpsNumber(1)),
        ("number", DpsNumber(999999999999999)),
        ("series", DpsSeries("1")),
        ("series", DpsSeries("00001")),
        ("series", DpsSeries("49999")),
        ("issuer_tax_id", FederalTaxId.cnpj("12345678000199")),
        ("application_version", "A"),
        ("application_version", "V" * 20),
        ("national_service_code", "000000"),
        ("national_service_code", "999999"),
        ("competence", CompetenceDate(date(2000, 1, 1))),
        ("competence", CompetenceDate(date(2099, 12, 31))),
        ("service_amount", Decimal("0.00")),
        ("service_amount", Decimal("0E-999")),
        ("service_amount", Decimal("1.2300")),
        ("service_amount", Decimal("999999999999999.99")),
        ("service_description", "a"),
        ("service_description", "a" * 2000),
        ("service_description", "& < > ação\nlinha\t\u00a0😀"),
        ("service_description", "\u00a0"),
        ("service_description", "literal <?pi?> <!--comment--> <Signature/>"),
        *[("op_simp_nac", code) for code in ("1", "2", "3")],
        *[("reg_esp_trib", code) for code in ("0", "1", "2", "3", "4", "5", "6", "9")],
        *[("trib_issqn", code) for code in ("1", "2", "3", "4")],
        *[("tp_ret_issqn", code) for code in ("1", "2", "3")],
        ("ind_tot_trib", "0"),
    ],
)
def test_deterministic_equivalence_classes(field: str, value: object) -> None:
    _round_trip(_draft(**{field: value}))


@pytest.mark.parametrize("offset", range(-11, 13))
@pytest.mark.parametrize("year", [2000, 2099])
def test_timestamp_preserves_components_and_each_supported_offset(
    offset: int, year: int
) -> None:
    _round_trip(
        _draft(
            issued_at=datetime(
                year, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=offset))
            )
        )
    )


def test_decimal_context_cannot_round_parsed_amount() -> None:
    draft = _draft(service_amount=Decimal("999999999999999.99"))
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        _round_trip(draft)


@pytest.mark.parametrize("fold", [0, 1])
def test_ambiguous_timezone_preserves_wall_time_offset_and_xml_not_zone(
    fold: int,
) -> None:
    # Model a regional clock's repeated hour without an OS tzdata dependency.
    class RepeatedHour(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            return timedelta(hours=-5 if dt is not None and dt.fold else -4)

        def dst(self, dt: datetime | None) -> timedelta:
            return timedelta(0)

        def tzname(self, dt: datetime | None) -> str:
            return "synthetic-repeated-hour"

    original = datetime(2026, 11, 1, 1, 30, tzinfo=RepeatedHour(), fold=fold)
    draft = _draft(issued_at=original)
    xml = build_unsigned_dps(draft)
    parsed = parse_unsigned_dps(xml)
    assert parsed.issued_at.replace(tzinfo=None) == original.replace(tzinfo=None)
    assert parsed.issued_at.utcoffset() == original.utcoffset()
    assert parsed.issued_at.isoformat() == original.isoformat()
    assert parsed.issued_at.timestamp() == original.timestamp()
    assert type(parsed.issued_at.tzinfo) is timezone
    # Inter-zone Python equality intentionally rejects ambiguous timestamps.
    assert parsed != draft
    for field in fields(draft):
        if field.name != "issued_at":
            assert getattr(parsed, field.name) == getattr(draft, field.name)
    assert build_unsigned_dps(parsed) == xml


@pytest.mark.parametrize("value", [None, "xml", bytearray(b"xml"), memoryview(b"xml")])
def test_requires_exact_bytes(value: object) -> None:
    _reject(value, "invalid_runtime_type")


def test_bytes_subclass_is_rejected() -> None:
    class BytesSubclass(bytes):
        pass

    _reject(BytesSubclass(_xml()), "invalid_runtime_type")


@pytest.mark.parametrize(
    "value,code",
    [
        (b"", "empty_document"),
        (b"a" * (1024 * 1024 + 1), "document_too_large"),
        (b"<DPS", "unsafe_or_malformed_xml"),
        (b"<!DOCTYPE DPS><DPS/>", "unsafe_or_malformed_xml"),
        (
            b'<!DOCTYPE DPS [<!ENTITY x SYSTEM "file:///secret">]><DPS>&x;</DPS>',
            "unsafe_or_malformed_xml",
        ),
        (b"\xff", "unsafe_or_malformed_xml"),
    ],
    # Pytest stores node IDs in PYTEST_CURRENT_TEST; never put a 1 MiB payload
    # into that environment variable (notably bounded on Windows).
    ids=["empty", "oversize", "malformed", "doctype", "external-entity", "encoding"],
)
def test_safe_input_boundary(value: bytes, code: str) -> None:
    _reject(value, code)


@pytest.mark.parametrize(
    "old,new,code",
    [
        (b"<DPS ", b"<OTHER ", "unsafe_or_malformed_xml"),
        (b'versao="1.01"', b'versao="1.00"', "unexpected_version"),
        (b"<tpAmb>2</tpAmb>", b"<tpAmb>1</tpAmb>", "unsupported_local_profile"),
        (b"<tpEmit>1</tpEmit>", b"<tpEmit>2</tpEmit>", "unsupported_local_profile"),
        (b"</DPS>", b"<Signature/></DPS>", "signature_already_present"),
        (b"<nDPS>42</nDPS>", b"<nDPS>43</nDPS>", "identity_mismatch"),
    ],
)
def test_existing_inspector_rejections_preserved(
    old: bytes, new: bytes, code: str
) -> None:
    xml = _xml().replace(old, new)
    _reject(xml, code)
    with pytest.raises(DpsDocumentError) as caught:
        inspect_unsigned_dps(xml)
    assert caught.value.code == code


def test_wrong_root() -> None:
    root = ET.fromstring(_xml())
    root.tag = _Q + "NFSe"
    _reject(_serialize(root), "unexpected_root")


# Exercise every supported element, not only representative leaf fields.
_NAMES = [element.tag.removeprefix(_Q) for element in ET.fromstring(_xml()).iter()]


@pytest.mark.parametrize("name", _NAMES)
def test_unknown_attribute_rejected_at_every_level(name: str) -> None:
    root = ET.fromstring(_xml())
    _element(root, name).set("unsupported", "synthetic")
    _reject(_serialize(root), "unsupported_document_structure")


@pytest.mark.parametrize("name", _NAMES[1:])
@pytest.mark.parametrize("operation", ["missing", "duplicate", "unknown_child"])
def test_closed_structure_every_element(name: str, operation: str) -> None:
    root = ET.fromstring(_xml())
    element = _element(root, name)
    parent = next(p for p in root.iter() if element in list(p))
    if operation == "missing":
        parent.remove(element)
    elif operation == "duplicate":
        parent.append(element)
    else:
        ET.SubElement(element, _Q + "unsupported")
    _reject(_serialize(root))


@pytest.mark.parametrize("name", ["toma", "interm", "subst", "IBSCBS"])
def test_additional_fiscal_branch_is_not_silently_lost(name: str) -> None:
    root = ET.fromstring(_xml())
    ET.SubElement(_element(root, "infDPS"), _Q + name)
    xml = _serialize(root)
    if name == "toma":
        # The authorized role-aware inspector now rejects an unidentified taker.
        with pytest.raises(DpsDocumentError, match="ambiguous_identity_field"):
            inspect_unsigned_dps(xml)
        _reject(xml, "ambiguous_identity_field")
        return
    assert isinstance(inspect_unsigned_dps(xml), DpsIdentity)
    _reject(xml, "unsupported_document_structure")


@pytest.mark.parametrize(
    "operation", ["moved", "reordered", "namespace", "mixed", "tail"]
)
def test_structure_namespace_and_mixed_content(operation: str) -> None:
    root = ET.fromstring(_xml())
    element = _element(root, "vServ")
    if operation == "moved":
        _element(root, "vServPrest").remove(element)
        _element(root, "tribMun").append(element)
    elif operation == "reordered":
        parent = _element(root, "cServ")
        parent[:] = list(reversed(list(parent)))
    elif operation == "namespace":
        element.tag = "{urn:unexpected}vServ"
    elif operation == "mixed":
        _element(root, "valores").text = "synthetic payload"
    else:
        element.tail = "synthetic payload"
    _reject(_serialize(root), "unsupported_document_structure")


@pytest.mark.parametrize("markup", [b"<!--comment-->", b"<?instruction data?>", b"\r"])
def test_no_silent_loss_of_comments_pi_or_raw_cr(markup: bytes) -> None:
    _reject(
        _xml().replace(b"<prest>", markup + b"<prest>"),
        "unsupported_document_structure",
    )


def test_indentation_and_namespace_prefix_do_not_change_values() -> None:
    root = ET.fromstring(_xml())
    ET.indent(root)
    parsed = parse_unsigned_dps(_serialize(root))
    assert parsed == _draft()
    assert build_unsigned_dps(parsed) == _xml()


@pytest.mark.parametrize(
    "name,value",
    [
        ("dhEmi", "2026-09-17 12:34:56-03:00"),
        ("dhEmi", "2026-09-17T12:34:56.000-03:00"),
        ("dhEmi", "2026-09-17T12:34:56Z"),
        ("dhEmi", "2026-09-17T12:34:56-00:00"),
        ("dhEmi", "2026-09-17T12:34:56+00:30"),
        ("dhEmi", "2026-09-17T12:34:56+13:00"),
        ("dhEmi", "2026-09-17T12:34:56-12:00"),
        ("dhEmi", "1999-09-17T12:34:56-03:00"),
        ("dhEmi", "2100-09-17T12:34:56-03:00"),
        ("dhEmi", "2026-02-30T12:34:56-03:00"),
        ("dhEmi", "2026-09-17T24:34:56-03:00"),
        ("vServ", "-0.00"),
        ("vServ", "+1.00"),
        ("vServ", "01.00"),
        ("vServ", "1"),
        ("vServ", "1.0"),
        ("vServ", "1.001"),
        ("vServ", "1E2"),
        ("vServ", "NaN"),
        ("vServ", "Infinity"),
        ("vServ", "1000000000000000.00"),
        ("vServ", " 1.00"),
        ("vServ", "١.00"),
        ("vServ", ""),
        ("dCompet", "20260917"),
        ("dCompet", "2026-02-30"),
        ("dCompet", "1999-12-31"),
        ("dCompet", "2100-01-01"),
        ("cLocPrestacao", "123"),
        ("cLocPrestacao", " 3550308"),
        ("verAplic", ""),
        ("verAplic", " app"),
        ("verAplic", "a" * 21),
        ("cTribNac", "12345"),
        ("cTribNac", "12345A"),
        ("xDescServ", ""),
        ("xDescServ", " \n\t"),
        ("xDescServ", "a" * 2001),
        ("xDescServ", "literal\rreturn"),
        ("opSimpNac", "0"),
        ("regEspTrib", "7"),
        ("tribISSQN", "5"),
        ("tpRetISSQN", "4"),
        ("indTotTrib", "1"),
    ],
)
def test_invalid_lexical_values_and_draft_invariants(name: str, value: str) -> None:
    root = ET.fromstring(_xml())
    _element(root, name).text = value
    xml = _serialize(root).replace(b"\r", b"&#13;")
    _reject(xml, "invalid_document_fields")


def test_valid_invalid_valid_has_no_state_leakage() -> None:
    _round_trip(_draft())
    _reject(_xml().replace(b"123.45", b"-123.45"))
    _round_trip(_draft(number=DpsNumber(1)))


@pytest.mark.parametrize(
    "field", ["verAplic", "dhEmi", "vServ", "dCompet", "cLocPrestacao"]
)
def test_errors_are_privacy_safe_including_calendar_exception_chain(field: str) -> None:
    root = ET.fromstring(_xml())
    secret = "synthetic-sensitive-value-not-for-diagnostics"
    _element(root, field).text = secret
    _element(root, "xDescServ").text = "synthetic-private-description"
    xml = _serialize(root)
    error = _reject(xml, "invalid_document_fields")
    rendered = str(error) + repr(error) + "".join(traceback.format_exception(error))
    for value in (
        secret,
        "12ABC6780001Z0",
        "synthetic-private-description",
        _element(root, "infDPS").attrib["Id"],
        "123.45",
    ):
        assert value not in rendered
    assert error.__cause__ is None


def test_base_api_import_and_round_trip_without_lxml() -> None:
    code = """
import importlib.abc
import sys
class NoLxml(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "lxml" or fullname.startswith("lxml."):
            raise ModuleNotFoundError("blocked optional extra", name="lxml")
sys.meta_path.insert(0, NoLxml())
from nfse_br.dps import parse_unsigned_dps
from nfse_br.dps.builder import build_unsigned_dps
xml = bytes.fromhex(sys.argv[1])
assert build_unsigned_dps(parse_unsigned_dps(xml)) == xml
assert "lxml" not in sys.modules
assert "nfse_br.xsd" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code, _xml().hex()],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
