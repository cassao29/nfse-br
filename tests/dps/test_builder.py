"""Tests for deterministic unsigned restricted DPS construction."""

from __future__ import annotations

import json
import traceback
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    MunicipalityCode,
)
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_NS = {"n": _NAMESPACE}
_CONTRACT = Path("contracts/restricted/dps-schema-contract.json")

_GOLDEN_XML = (
    b"<?xml version='1.0' encoding='utf-8'?>\n"
    b'<DPS xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">'
    b'<infDPS Id="DPS2927408212ABC6780001Z000123000000000000042">'
    b"<tpAmb>2</tpAmb>"
    b"<dhEmi>2026-09-17T12:00:00-03:00</dhEmi>"
    b"<verAplic>nfse-br-test</verAplic>"
    b"<serie>123</serie>"
    b"<nDPS>42</nDPS>"
    b"<dCompet>2026-09-17</dCompet>"
    b"<tpEmit>1</tpEmit>"
    b"<cLocEmi>2927408</cLocEmi>"
    b"<prest><CNPJ>12ABC6780001Z0</CNPJ>"
    b"<regTrib><opSimpNac>1</opSimpNac><regEspTrib>0</regEspTrib></regTrib>"
    b"</prest>"
    b"<serv><locPrest><cLocPrestacao>3550308</cLocPrestacao></locPrest>"
    b"<cServ><cTribNac>010101</cTribNac>"
    b"<xDescServ>Servico sintetico</xDescServ></cServ></serv>"
    b"<valores><vServPrest><vServ>1.00</vServ></vServPrest>"
    b"<trib><tribMun><tribISSQN>1</tribISSQN>"
    b"<tpRetISSQN>1</tpRetISSQN></tribMun>"
    b"<totTrib><indTotTrib>0</indTotTrib></totTrib></trib></valores>"
    b"</infDPS></DPS>"
)


def _draft(**changes: Any) -> RestrictedDpsDraft:
    values: dict[str, Any] = {
        "issuer_tax_id": FederalTaxId.cnpj("12ABC6780001Z0"),
        "issue_municipality": MunicipalityCode("2927408"),
        "service_municipality": MunicipalityCode("3550308"),
        "series": DpsSeries("123"),
        "number": DpsNumber(42),
        "issued_at": datetime(
            2026,
            9,
            17,
            12,
            0,
            0,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        "competence": CompetenceDate(date(2026, 9, 17)),
        "application_version": "nfse-br-test",
        "national_service_code": "010101",
        "service_description": "Servico sintetico",
        "service_amount": Decimal("1.00"),
        "op_simp_nac": "1",
        "reg_esp_trib": "0",
        "trib_issqn": "1",
        "tp_ret_issqn": "1",
        "ind_tot_trib": "0",
    }
    values.update(changes)
    return RestrictedDpsDraft(**values)


def _root(draft: RestrictedDpsDraft | None = None) -> ElementTree.Element:
    return ElementTree.fromstring(build_unsigned_dps(draft or _draft()))


def _local_names(element: ElementTree.Element) -> list[str]:
    return [child.tag.rsplit("}", 1)[-1] for child in element]


def test_golden_xml_is_manually_fixed_and_deterministic() -> None:
    draft = _draft()

    first = build_unsigned_dps(draft)
    second = build_unsigned_dps(draft)

    assert first == _GOLDEN_XML
    assert second == first
    assert draft == _draft()


def test_root_identity_namespace_and_order_are_exact() -> None:
    root = _root()
    information = root.find("n:infDPS", _NS)

    assert root.tag == f"{{{_NAMESPACE}}}DPS"
    assert root.attrib == {"versao": "1.01"}
    assert information is not None
    assert information.attrib == {"Id": "DPS2927408212ABC6780001Z000123000000000000042"}
    assert _local_names(information) == [
        "tpAmb",
        "dhEmi",
        "verAplic",
        "serie",
        "nDPS",
        "dCompet",
        "tpEmit",
        "cLocEmi",
        "prest",
        "serv",
        "valores",
    ]
    assert information.findtext("n:tpAmb", namespaces=_NS) == "2"
    assert information.findtext("n:tpEmit", namespaces=_NS) == "1"
    assert root.find(".//n:Signature", _NS) is None
    assert root.find(".//n:toma", _NS) is None
    assert root.find(".//n:interm", _NS) is None
    assert root.find(".//n:IBSCBS", _NS) is None


def test_identity_uses_issue_values_while_service_location_is_distinct() -> None:
    root = _root()
    information = root.find("n:infDPS", _NS)
    assert information is not None

    assert information.attrib["Id"].startswith("DPS2927408")
    assert information.findtext("n:cLocEmi", namespaces=_NS) == "2927408"
    assert (
        information.findtext("n:serv/n:locPrest/n:cLocPrestacao", namespaces=_NS)
        == "3550308"
    )
    assert information.findtext("n:prest/n:CNPJ", namespaces=_NS) == ("12ABC6780001Z0")
    assert information.findtext("n:serie", namespaces=_NS) == "123"
    assert information.findtext("n:nDPS", namespaces=_NS) == "42"


def test_series_aliases_preserve_xml_lexemes_but_share_identity_component() -> None:
    short = _root(_draft(series=DpsSeries("123")))
    padded = _root(_draft(series=DpsSeries("00123")))
    short_information = short.find("n:infDPS", _NS)
    padded_information = padded.find("n:infDPS", _NS)
    assert short_information is not None
    assert padded_information is not None

    assert short_information.attrib["Id"] == padded_information.attrib["Id"]
    assert short_information.findtext("n:serie", namespaces=_NS) == "123"
    assert padded_information.findtext("n:serie", namespaces=_NS) == "00123"
    assert build_unsigned_dps(_draft(series=DpsSeries("123"))) != (
        build_unsigned_dps(_draft(series=DpsSeries("00123")))
    )


def test_text_is_escaped_as_data_and_never_becomes_markup() -> None:
    description = 'Acentuacao: acao & <item attr="x"> > fim\nsegunda linha'
    xml = build_unsigned_dps(_draft(service_description=description))
    root = ElementTree.fromstring(xml)

    assert b"&amp;" in xml
    assert b"&lt;item attr=" in xml
    assert root.findtext(".//n:xDescServ", namespaces=_NS) == description
    assert root.find(".//item") is None


def test_builder_does_not_use_or_change_the_global_namespace_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace_map = ElementTree._namespace_map  # type: ignore[attr-defined]
    before = dict(namespace_map)

    def unexpected_registration(prefix: str, uri: str) -> None:
        raise AssertionError(f"unexpected namespace registration: {prefix!r} {uri!r}")

    monkeypatch.setattr(ElementTree, "register_namespace", unexpected_registration)
    build_unsigned_dps(_draft())

    assert namespace_map == before


def test_draft_is_keyword_only_frozen_and_redacted() -> None:
    draft = _draft()

    with pytest.raises(FrozenInstanceError):
        draft.service_description = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        RestrictedDpsDraft()  # type: ignore[call-arg]

    representation = repr(draft)
    assert str(draft) == "RestrictedDpsDraft(<redacted>)"
    assert "12ABC6780001Z0" not in representation
    assert "Servico sintetico" not in representation
    assert "<redacted>" in representation


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("issuer_tax_id", object(), "FederalTaxId"),
        ("issue_municipality", object(), "MunicipalityCode"),
        ("service_municipality", object(), "MunicipalityCode"),
        ("series", object(), "DpsSeries"),
        ("number", object(), "DpsNumber"),
        ("competence", object(), "CompetenceDate"),
    ],
)
def test_value_object_runtime_types_are_enforced(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(DomainValidationError, match=message):
        _draft(**{field: value})


def test_only_cnpj_issuers_are_supported() -> None:
    with pytest.raises(DomainValidationError, match="CNPJ"):
        _draft(issuer_tax_id=FederalTaxId.cpf("12345678901"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("op_simp_nac", "0"),
        ("op_simp_nac", 1),
        ("reg_esp_trib", "7"),
        ("trib_issqn", "0"),
        ("tp_ret_issqn", "4"),
        ("ind_tot_trib", "1"),
    ],
)
def test_tax_codes_are_explicit_closed_sets(field: str, value: object) -> None:
    with pytest.raises(DomainValidationError, match="unsupported"):
        _draft(**{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"op_simp_nac": "3"},
        {"reg_esp_trib": "9"},
        {"trib_issqn": "4"},
        {"tp_ret_issqn": "3"},
    ],
)
def test_all_upper_code_boundaries_are_serialized(changes: dict[str, str]) -> None:
    xml = build_unsigned_dps(_draft(**changes))
    assert next(iter(changes.values())).encode() in xml


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * 21,
        " leading",
        "trailing ",
        "line\nbreak",
        "version-Ā",
    ],
)
def test_application_version_rejects_values_outside_tsstring(value: str) -> None:
    with pytest.raises(DomainValidationError, match="Application version"):
        _draft(application_version=value)


def test_application_version_requires_a_string() -> None:
    with pytest.raises(DomainValidationError, match="string"):
        _draft(application_version=1)


@pytest.mark.parametrize("value", ["01010", "0101010", "01A101", "٠١٠١٠١", 10101])
def test_national_service_code_is_exactly_six_ascii_digits(value: object) -> None:
    with pytest.raises(DomainValidationError, match="6 ASCII digits"):
        _draft(national_service_code=value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "x" * 2001,
        "line\rbreak",
        "line\r\nbreak",
        "nul\x00value",
        "surrogate\ud800value",
    ],
)
def test_service_description_rejects_invalid_text(value: str) -> None:
    with pytest.raises(DomainValidationError, match="Service description"):
        _draft(service_description=value)


def test_service_description_requires_a_string_and_accepts_lf() -> None:
    with pytest.raises(DomainValidationError, match="string"):
        _draft(service_description=object())

    assert (
        _root(_draft(service_description="linha um\nlinha dois")).findtext(
            ".//n:xDescServ", namespaces=_NS
        )
        == "linha um\nlinha dois"
    )


@pytest.mark.parametrize(
    "issued_at",
    [
        datetime(2026, 9, 17, 12),
        datetime(2026, 9, 17, 12, 0, 0, 1, tzinfo=UTC),
        datetime(1999, 12, 31, 23, tzinfo=UTC),
        datetime(2100, 1, 1, 0, tzinfo=UTC),
        datetime(2026, 9, 17, 12, tzinfo=timezone(timedelta(minutes=30))),
        datetime(2026, 9, 17, 12, tzinfo=timezone(timedelta(hours=-12))),
        datetime(2026, 9, 17, 12, tzinfo=timezone(timedelta(hours=13))),
    ],
)
def test_timestamp_rejects_values_outside_frozen_profile(
    issued_at: datetime,
) -> None:
    with pytest.raises(DomainValidationError, match="Issue timestamp"):
        _draft(issued_at=issued_at)


def test_timestamp_requires_exact_datetime_and_accepts_offset_boundaries() -> None:
    with pytest.raises(DomainValidationError, match="datetime"):
        _draft(issued_at=date(2026, 9, 17))

    lower = _root(
        _draft(issued_at=datetime(2000, 1, 1, tzinfo=timezone(timedelta(hours=-11))))
    )
    upper = _root(
        _draft(
            issued_at=datetime(
                2099,
                12,
                31,
                23,
                59,
                59,
                tzinfo=timezone(timedelta(hours=12)),
            )
        )
    )
    assert lower.findtext(".//n:dhEmi", namespaces=_NS) == ("2000-01-01T00:00:00-11:00")
    assert upper.findtext(".//n:dhEmi", namespaces=_NS) == ("2099-12-31T23:59:59+12:00")


class _MissingOffset(tzinfo):
    def utcoffset(self, value: datetime | None) -> None:
        return None

    def dst(self, value: datetime | None) -> None:
        return None

    def tzname(self, value: datetime | None) -> None:
        return None


class _MutableOffset(tzinfo):
    def __init__(self, hours: int) -> None:
        self.hours = hours

    def utcoffset(self, value: datetime | None) -> timedelta:
        return timedelta(hours=self.hours)

    def dst(self, value: datetime | None) -> None:
        return None

    def tzname(self, value: datetime | None) -> str:
        return "synthetic"


def test_timestamp_rejects_tzinfo_without_an_offset() -> None:
    with pytest.raises(DomainValidationError, match="UTC offset"):
        _draft(issued_at=datetime(2026, 9, 17, tzinfo=_MissingOffset()))


def test_timestamp_lexeme_is_frozen_when_the_draft_is_created() -> None:
    zone = _MutableOffset(-3)
    draft = _draft(issued_at=datetime(2026, 9, 17, 12, tzinfo=zone))
    zone.hours = 2

    first = build_unsigned_dps(draft)
    second = build_unsigned_dps(draft)

    assert first == second
    assert (
        ElementTree.fromstring(first).findtext(".//n:dhEmi", namespaces=_NS)
        == "2026-09-17T12:00:00-03:00"
    )


@pytest.mark.parametrize("year", [1999, 2100])
def test_competence_year_matches_tsdata(year: int) -> None:
    with pytest.raises(DomainValidationError, match="Competence year"):
        _draft(competence=CompetenceDate(date(year, 1, 1)))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0"), "0.00"),
        (Decimal("0E+999999"), "0.00"),
        (Decimal("1"), "1.00"),
        (Decimal("1.2"), "1.20"),
        (Decimal("1.2300"), "1.23"),
        (Decimal("1E-2"), "0.01"),
        (Decimal("1E+2"), "100.00"),
        (Decimal("999999999999999.99"), "999999999999999.99"),
    ],
)
def test_amount_serialization_is_exact(value: Decimal, expected: str) -> None:
    assert (
        _root(_draft(service_amount=value)).findtext(".//n:vServ", namespaces=_NS)
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        True,
        "1.00",
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-0"),
        Decimal("-1"),
        Decimal("0.001"),
        Decimal("1.239"),
        Decimal("1E-999999"),
        Decimal("1000000000000000"),
        Decimal("1E+999999"),
    ],
)
def test_amount_rejects_unsupported_values(value: object) -> None:
    with pytest.raises(DomainValidationError, match="Service amount"):
        _draft(service_amount=value)


def test_amount_formatting_is_independent_of_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 2
        context.rounding = "ROUND_UP"
        context.traps[InvalidOperation] = True
        context.traps[DivisionByZero] = True
        before = (
            context.prec,
            context.rounding,
            context.traps.copy(),
            context.flags.copy(),
        )

        xml = build_unsigned_dps(_draft(service_amount=Decimal("123456789.2300")))

        assert (
            context.prec,
            context.rounding,
            context.traps.copy(),
            context.flags.copy(),
        ) == before
        assert (
            ElementTree.fromstring(xml).findtext(".//n:vServ", namespaces=_NS)
            == "123456789.23"
        )


def test_build_rejects_non_draft_without_leaking_input() -> None:
    sensitive = "12ABC6780001Z0 Servico secreto"
    with pytest.raises(DomainValidationError) as caught:
        build_unsigned_dps(sensitive)  # type: ignore[arg-type]

    formatted = "".join(traceback.format_exception(caught.value))
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in formatted


def test_frozen_contract_binds_builder_profile_to_official_evidence() -> None:
    contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    simple = contract["simple_types"]

    def facets(name: str, kind: str) -> list[str]:
        return [
            facet["value"] for facet in simple[name]["facets"] if facet["name"] == kind
        ]

    assert contract["authority"] == "official_frozen"
    assert contract["environment"] == "restricted"
    assert contract["transmission_ready"] is False
    assert facets("TSDec15V2", "pattern") == [
        r"0|0\.[0-9]{2}|[1-9]{1}[0-9]{0,14}(\.[0-9]{2})?"
    ]
    assert facets("TSTipoAmbiente", "enumeration") == ["1", "2"]
    assert facets("TSEmitenteDPS", "enumeration") == ["1", "2", "3"]
    assert facets("TVerNFSe", "pattern") == [r"1\.00|1\.01"]
    assert facets("TVerNFSe", "maxLength") == ["4"]
    assert facets("TSVerAplic", "minLength") == ["1"]
    assert facets("TSVerAplic", "maxLength") == ["20"]
    assert facets("TSDesc2000", "minLength") == ["1"]
    assert facets("TSDesc2000", "maxLength") == ["2000"]
    assert facets("TSCodTribNac", "pattern") == [r"[0-9]{6}"]
    assert facets("TSOpSimpNac", "enumeration") == ["1", "2", "3"]
    assert facets("TSRegEspTrib", "enumeration") == [
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "9",
    ]
    assert facets("TSTribISSQN", "enumeration") == ["1", "2", "3", "4"]
    assert facets("TSTipoRetISSQN", "enumeration") == ["1", "2", "3"]
    assert facets("TSTipoIndTotTrib", "enumeration") == ["0"]
    assert facets("TSCNPJ", "pattern") == [r"[0-9A-Z]{14}"]
    assert facets("TSNumDPS", "pattern") == [r"[1-9]{1}[0-9]{0,14}"]
    assert facets("TSSerieDPS", "pattern") == [r"[0-9]{1,4}|[0-8][0-9]{4}"]

    information = contract["complex_types"]["TCInfDPS"]["content"]
    assert [particle["name"] for particle in information["particles"]] == [
        "tpAmb",
        "dhEmi",
        "verAplic",
        "serie",
        "nDPS",
        "dCompet",
        "tpEmit",
        "cMotivoEmisTI",
        "chNFSeRej",
        "cLocEmi",
        "subst",
        "prest",
        "toma",
        "interm",
        "serv",
        "valores",
        "IBSCBS",
    ]

    complex_types = contract["complex_types"]
    provider = complex_types["TCInfoPrestador"]["content"]["particles"]
    assert provider[0]["kind"] == "choice"
    assert provider[0]["particles"][0] == {
        "kind": "element",
        "max_occurs": "1",
        "min_occurs": "1",
        "name": "CNPJ",
        "type": "TSCNPJ",
    }
    assert provider[-1]["name"] == "regTrib"
    assert provider[-1]["type"] == "TCRegTrib"

    expected_sequences = {
        "TCRegTrib": ["opSimpNac", "regApTribSN", "regEspTrib"],
        "TCServ": ["locPrest", "cServ", "comExt", "obra", "atvEvento", "infoCompl"],
        "TCCServ": ["cTribNac", "cTribMun", "xDescServ", "cNBS", "cIntContrib"],
        "TCInfoValores": ["vServPrest", "vDescCondIncond", "vDedRed", "trib"],
        "TCVServPrest": ["vReceb", "vServ"],
        "TCInfoTributacao": ["tribMun", "tribFed", "totTrib"],
        "TCTribMunicipal": [
            "tribISSQN",
            "cPaisResult",
            "tpImunidade",
            "exigSusp",
            "BM",
            "tpRetISSQN",
            "pAliq",
        ],
    }
    for type_name, expected in expected_sequences.items():
        content = complex_types[type_name]["content"]
        assert content["kind"] == "sequence"
        assert [particle["name"] for particle in content["particles"]] == expected

    service_location = complex_types["TCLocPrest"]["content"]
    assert service_location["kind"] == "choice"
    assert service_location["particles"][0]["name"] == "cLocPrestacao"
    total_tax = complex_types["TCTribTotal"]["content"]["particles"][0]
    assert total_tax["kind"] == "choice"
    assert [particle["name"] for particle in total_tax["particles"]] == [
        "vTotTrib",
        "pTotTrib",
        "indTotTrib",
        "pTotTribSN",
    ]


def test_replace_revalidates_and_keeps_original_immutable() -> None:
    original = _draft()
    changed = replace(original, number=DpsNumber(43))

    assert original.number.value == 42
    assert changed.number.value == 43
    assert build_unsigned_dps(original) != build_unsigned_dps(changed)
