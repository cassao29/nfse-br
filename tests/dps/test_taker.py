"""Independent synthetic oracles and adversarial tests for the taker subset."""

from __future__ import annotations

import builtins
import copy
import socket
import subprocess
import sys
import traceback
from dataclasses import FrozenInstanceError, asdict, fields, replace
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

import pytest

from nfse_br._xmlsig.preflight import SignaturePreflightError
from nfse_br._xmlsig.preflight import inspect_unsigned_dps as private_inspect
from nfse_br.domain import DomainValidationError, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsDocumentError, inspect_unsigned_dps, parse_unsigned_dps
from nfse_br.dps.builder import (
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
    build_unsigned_dps,
)

from .test_builder import _GOLDEN_XML, _draft

_Q = "{http://www.sped.fazenda.gov.br/nfse}"
# Written from the reviewed contract, not serialized with the builder.
_ADDRESS_XML = (
    b"<end><endNac><cMun>3550308</cMun><CEP>01234567</CEP></endNac>"
    b"<xLgr>Rua Sintetica</xLgr><nro>0</nro><xCpl>Sala A</xCpl>"
    b"<xBairro>Centro</xBairro></end>"
)
_IDENTIFIERS = [
    ("CPF", "12345678901"),
    ("CNPJ", "12345678000199"),
    ("CNPJ", "98ABC6780001Z0"),
]


def _oracle(kind: str = "CNPJ", identifier: str = "98ABC6780001Z0") -> bytes:
    block = (
        f"<toma><{kind}>{identifier}</{kind}>".encode()
        + b"<xNome>Nome &amp; Sintetico</xNome>"
        + _ADDRESS_XML
        + b"</toma>"
    )
    return _GOLDEN_XML.replace(b"</prest>", b"</prest>" + block)


def _address(**changes: Any) -> RestrictedDpsNationalAddress:
    values: dict[str, Any] = dict(
        municipality=MunicipalityCode("3550308"),
        postal_code="01234567",
        street="Rua Sintetica",
        number="0",
        neighborhood="Centro",
        complement="Sala A",
    )
    return RestrictedDpsNationalAddress(**(values | changes))


def _taker(**changes: Any) -> RestrictedDpsTaker:
    values: dict[str, Any] = dict(
        tax_id=FederalTaxId.cnpj("98ABC6780001Z0"),
        name="Nome & Sintetico",
        address=_address(),
    )
    return RestrictedDpsTaker(**(values | changes))


def _serialize(root: ET.Element) -> bytes:
    return cast(bytes, ET.tostring(root, encoding="utf-8"))


@pytest.mark.parametrize("kind,identifier", _IDENTIFIERS)
def test_independent_oracles_and_all_fields(kind: str, identifier: str) -> None:
    tax_id = (
        FederalTaxId.cpf(identifier) if kind == "CPF" else FederalTaxId.cnpj(identifier)
    )
    draft = _draft(taker=_taker(tax_id=tax_id))
    expected = _oracle(kind, identifier)
    assert build_unsigned_dps(draft) == expected
    parsed = parse_unsigned_dps(expected)
    assert parsed == draft
    assert asdict(parsed) == asdict(draft)
    assert build_unsigned_dps(parsed) == expected
    assert inspect_unsigned_dps(expected) == inspect_unsigned_dps(_GOLDEN_XML)
    assert private_inspect(expected) == inspect_unsigned_dps(expected).value


def test_old_bytes_none_identity_and_same_provider() -> None:
    assert build_unsigned_dps(_draft(taker=None)) == _GOLDEN_XML
    assert parse_unsigned_dps(_GOLDEN_XML).taker is None
    for taker in (
        _taker(),
        _taker(tax_id=_draft().issuer_tax_id),
        _taker(name="Other"),
    ):
        xml = build_unsigned_dps(_draft(taker=taker))
        assert inspect_unsigned_dps(xml) == inspect_unsigned_dps(_GOLDEN_XML)
        assert parse_unsigned_dps(xml).taker == taker


def test_dataclass_behavior_and_explicit_privacy_boundary() -> None:
    address, taker = _address(), _taker()
    for value in (address, taker):
        assert not hasattr(value, "__dict__")
        assert value == replace(value)
        assert hash(value) == hash(replace(value))
        assert str(value) == repr(value)
        assert "<redacted>" in str(value)
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    assert [f.name for f in fields(address)] == [
        "municipality",
        "postal_code",
        "street",
        "number",
        "neighborhood",
        "complement",
    ]
    assert [f.name for f in fields(taker)] == ["tax_id", "name", "address"]
    assert replace(taker, name="Other") != taker
    assert replace(address, complement=None) != address
    assert asdict(taker)["address"]["postal_code"] == "01234567"
    assert asdict(taker)["tax_id"]["value"] == taker.tax_id.value
    assert str(taker.tax_id) == taker.tax_id.value  # Existing, intentionally unmasked.
    draft = _draft(taker=taker)
    assert replace(draft).taker == taker
    assert draft != replace(draft, taker=None)
    with pytest.raises(DomainValidationError):
        replace(address, complement="")
    with pytest.raises(TypeError):
        RestrictedDpsTaker(taker.tax_id, taker.name, address)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        RestrictedDpsNationalAddress(address.municipality, "01234567", "R", "1", "B")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "field,maximum",
    [("street", 255), ("number", 60), ("neighborhood", 60), ("complement", 156)],
)
def test_address_lengths(field: str, maximum: int) -> None:
    for value in ("X", "X" * maximum):
        address = _address(**{field: value})
        draft = _draft(taker=_taker(address=address))
        assert parse_unsigned_dps(build_unsigned_dps(draft)) == draft
    for invalid in (
        "",
        "X" * (maximum + 1),
        1,
        None if field != "complement" else False,
    ):
        with pytest.raises(DomainValidationError):
            _address(**{field: invalid})


@pytest.mark.parametrize(
    "value",
    [
        " leading",
        "trailing ",
        " ",
        "A\tB",
        "A\nB",
        "A\rB",
        "Ā",
        "e\u0301",
        "😀",
        "\x1f",
        "\ud800",
    ],
)
@pytest.mark.parametrize("field", ["street", "number", "neighborhood", "complement"])
def test_address_tsstring_is_not_generic_text(field: str, value: str) -> None:
    with pytest.raises(DomainValidationError):
        _address(**{field: value})


@pytest.mark.parametrize("value", ["!", "ÿ", "é", "A B", "\x7f", "\u0085", "\u00a0"])
def test_exact_tsstring_ranges_without_printability_cleanup(value: str) -> None:
    draft = _draft(taker=_taker(address=_address(street=value)))
    assert parse_unsigned_dps(build_unsigned_dps(draft)) == draft


@pytest.mark.parametrize(
    "field,value",
    [
        ("postal_code", "1234567"),
        ("postal_code", "123456789"),
        ("postal_code", "１２３４５６７８"),
        ("postal_code", "1234567A"),
        ("postal_code", 12345678),
        ("municipality", "3550308"),
        ("municipality", {}),
    ],
)
def test_address_runtime_and_lexical_rejections(field: str, value: object) -> None:
    with pytest.raises(DomainValidationError):
        _address(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("tax_id", "12345678901"),
        ("tax_id", {}),
        ("address", {}),
        ("address", None),
        ("name", 123),
    ],
)
def test_taker_exact_types(field: str, value: object) -> None:
    with pytest.raises(DomainValidationError):
        _taker(**{field: value})


def test_draft_rejects_dict_taker() -> None:
    with pytest.raises(DomainValidationError):
        _draft(taker=asdict(_taker()))


@pytest.mark.parametrize(
    "name",
    [
        "N",
        "N" * 150,
        " Nome \t\n",
        "é",
        "e\u0301",
        "😀",
        "\u00a0",
        "<Signature>& texto",
    ],
)
def test_name_preserved_not_address_tsstring(name: str) -> None:
    draft = _draft(taker=_taker(name=name))
    xml = build_unsigned_dps(draft)
    assert parse_unsigned_dps(xml) == draft
    assert build_unsigned_dps(parse_unsigned_dps(xml)) == xml
    assert inspect_unsigned_dps(xml) == inspect_unsigned_dps(_GOLDEN_XML)


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "\t\n",
        "\r",
        "N\rN",
        "N" * 151,
        "N" * 300,
        "N" * 301,
        "\x00",
        "\ud800",
        "\ufffe",
    ],
)
def test_name_policy_rejects_without_payload(name: str) -> None:
    with pytest.raises(DomainValidationError):
        _taker(name=name)


def test_optional_complement_omitted_not_empty() -> None:
    xml = build_unsigned_dps(_draft(taker=_taker(address=_address(complement=None))))
    assert xml == _oracle().replace(b"<xCpl>Sala A</xCpl>", b"")
    parsed = parse_unsigned_dps(xml)
    assert parsed.taker is not None and parsed.taker.address.complement is None
    with pytest.raises(DpsDocumentError, match="invalid_document_fields"):
        parse_unsigned_dps(_oracle().replace(b"Sala A", b""))


@pytest.mark.parametrize(
    "old,new,code",
    [
        (b"Nome &amp; Sintetico", b"X" * 151, "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b"X" * 300, "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b"X" * 301, "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b"", "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b" \t\n", "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b"X&#13;X", "invalid_document_fields"),
        (b"Nome &amp; Sintetico", b"X\rX", "unsupported_document_structure"),
        (b"98ABC6780001Z0", b"98abc6780001z0", "invalid_document_fields"),
        (b"01234567", b"0000000A", "invalid_document_fields"),
        (_ADDRESS_XML, b"", "unsupported_document_structure"),
        (b"<xNome>Nome &amp; Sintetico</xNome>", b"", "unsupported_document_structure"),
    ],
)
def test_parser_local_rejections_do_not_become_inspector_policies(
    old: bytes, new: bytes, code: str
) -> None:
    xml = _oracle().replace(old, new)
    assert inspect_unsigned_dps(xml) == inspect_unsigned_dps(_GOLDEN_XML)
    with pytest.raises(DpsDocumentError, match=code):
        parse_unsigned_dps(xml)


_TAKER_PATHS = [
    "toma",
    "toma/CNPJ",
    "toma/xNome",
    "toma/end",
    "toma/end/endNac",
    "toma/end/endNac/cMun",
    "toma/end/endNac/CEP",
    "toma/end/xLgr",
    "toma/end/nro",
    "toma/end/xCpl",
    "toma/end/xBairro",
]


@pytest.mark.parametrize("path", _TAKER_PATHS)
@pytest.mark.parametrize(
    "mutation", ["duplicate", "namespace", "attribute", "child", "mixed_tail"]
)
def test_closed_taker_grammar_at_every_level(path: str, mutation: str) -> None:
    root = ET.fromstring(_oracle())
    element = root.find("/".join(_Q + n for n in ["infDPS", *path.split("/")]))
    assert element is not None
    parent = next(p for p in root.iter() if element in list(p))
    if mutation == "duplicate":
        parent.append(copy.deepcopy(element))
    elif mutation == "namespace":
        element.tag = "{urn:fake}" + path.split("/")[-1]
    elif mutation == "attribute":
        element.set("unexpected", "payload")
    elif mutation == "child":
        ET.SubElement(element, _Q + "extra")
    else:
        element.tail = "unexpected content"
    with pytest.raises(DpsDocumentError):
        parse_unsigned_dps(_serialize(root))


@pytest.mark.parametrize(
    "path", [p for p in _TAKER_PATHS if p not in ("toma", "toma/end/xCpl")]
)
def test_missing_required_field(path: str) -> None:
    root = ET.fromstring(_oracle())
    element = root.find("/".join(_Q + n for n in ["infDPS", *path.split("/")]))
    assert element is not None
    next(p for p in root.iter() if element in list(p)).remove(element)
    with pytest.raises(DpsDocumentError):
        parse_unsigned_dps(_serialize(root))


@pytest.mark.parametrize(
    "attack",
    [
        "duplicate_group",
        "nested_group",
        "wrong_group_ns",
        "wrong_id_ns",
        "duplicate_id",
        "conflicting_cpf",
        "conflicting_nif",
        "wrapped_id",
        "moved_id",
        "extra_cnpj",
        "extra_cpf",
        "id_child",
        "extra_id",
        "xml_id",
    ],
)
@pytest.mark.parametrize("kind,identifier_value", _IDENTIFIERS)
def test_role_aware_identity_and_private_adapter_reject_attacks(
    attack: str,
    kind: str,
    identifier_value: str,
) -> None:
    root = ET.fromstring(_oracle(kind, identifier_value))
    info = root[0]
    taker = next(e for e in info if e.tag == _Q + "toma")
    identifier = taker[0]
    service = next(e for e in info if e.tag == _Q + "serv")
    if attack == "duplicate_group":
        info.append(copy.deepcopy(taker))
    elif attack == "nested_group":
        info.remove(taker)
        service.append(taker)
    elif attack == "wrong_group_ns":
        taker.tag = "{urn:fake}toma"
    elif attack == "wrong_id_ns":
        identifier.tag = "{urn:fake}CNPJ"
    elif attack == "duplicate_id":
        taker.append(copy.deepcopy(identifier))
    elif attack in ("conflicting_cpf", "conflicting_nif"):
        ET.SubElement(
            taker, _Q + ("CPF" if attack.endswith("cpf") else "NIF")
        ).text = "12345678901"
    elif attack == "wrapped_id":
        taker.remove(identifier)
        ET.SubElement(taker, _Q + "wrapper").append(identifier)
    elif attack == "moved_id":
        taker.remove(identifier)
        service.append(identifier)
    elif attack in ("extra_cnpj", "extra_cpf"):
        ET.SubElement(
            service, _Q + ("CPF" if attack.endswith("cpf") else "CNPJ")
        ).text = "12345678901"
    elif attack == "id_child":
        ET.SubElement(identifier, _Q + "child")
    else:
        taker.set(
            "Id"
            if attack == "extra_id"
            else "{http://www.w3.org/XML/1998/namespace}id",
            "shadow",
        )
    xml = _serialize(root)
    with pytest.raises(DpsDocumentError) as public:
        inspect_unsigned_dps(xml)
    with pytest.raises(SignaturePreflightError) as private:
        private_inspect(xml)
    assert private.value.code == public.value.code
    assert private.value.__cause__ is None
    assert private_inspect(_oracle()) == inspect_unsigned_dps(_GOLDEN_XML).value


@pytest.mark.parametrize(
    "addition",
    [
        b"<CAEPF>12345678901234</CAEPF>",
        b"<IM>1</IM>",
        b"<fone>123456</fone>",
        b"<email>a@b.test</email>",
        b"<UF>SP</UF>",
        b"<endExt/>",
    ],
)
def test_no_silent_loss_of_additional_fields(addition: bytes) -> None:
    xml = _oracle().replace(b"</toma>", addition + b"</toma>")
    with pytest.raises(DpsDocumentError, match="unsupported_document_structure"):
        parse_unsigned_dps(xml)


@pytest.mark.parametrize("path", ["toma", "toma/end", "toma/end/endNac"])
def test_order_and_mixed_content(path: str) -> None:
    for mixed in (False, True):
        root = ET.fromstring(_oracle())
        element = root.find("/".join(_Q + n for n in ["infDPS", *path.split("/")]))
        assert element is not None
        if mixed:
            element.text = "unexpected"
        else:
            element[:] = list(reversed(element))
        with pytest.raises(DpsDocumentError, match="unsupported_document_structure"):
            parse_unsigned_dps(_serialize(root))


def test_privacy_including_suppressed_exception_context() -> None:
    sensitive = "synthetic-sensitive-payload"
    xml = _oracle().replace(b"01234567", sensitive.encode())
    with pytest.raises(DpsDocumentError) as caught:
        parse_unsigned_dps(xml)
    error = caught.value
    rendered = str(error) + repr(error) + "".join(traceback.format_exception(error))
    rendered += str(_taker()) + repr(_address()) + repr(_draft(taker=_taker()))
    for value in (
        sensitive,
        "98ABC6780001Z0",
        "Nome & Sintetico",
        "Rua Sintetica",
        "01234567",
        "Sala A",
    ):
        assert value not in rendered
    assert error.__cause__ is None and error.__suppress_context__


def test_base_operations_without_io(monkeypatch: pytest.MonkeyPatch) -> None:
    # Warm the existing safe parser import before disabling all file operations.
    parse_unsigned_dps(_oracle())

    def reject(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected I/O")

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", reject)
        m.setattr(Path, "open", reject)
        m.setattr(socket, "socket", reject)
        draft = _draft(taker=_taker())
        assert build_unsigned_dps(draft) == _oracle()
        assert parse_unsigned_dps(_oracle()) == draft
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['lxml'] = None; "
            "from nfse_br.dps import parse_unsigned_dps; "
            "from nfse_br.dps.builder import build_unsigned_dps; "
            "xml=bytes.fromhex(sys.argv[1]); "
            "assert build_unsigned_dps(parse_unsigned_dps(xml)) == xml",
            _oracle().hex(),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind,identifier", _IDENTIFIERS)
def test_renamed_group_cannot_hide_displaced_identifier(
    kind: str, identifier: str
) -> None:
    xml = (
        _oracle(kind, identifier)
        .replace(b"<toma>", b"<wrapper>")
        .replace(b"</toma>", b"</wrapper>")
    )
    with pytest.raises(DpsDocumentError, match="ambiguous_identity_field"):
        inspect_unsigned_dps(xml)


@pytest.mark.parametrize("tag,value", [("NIF", "SYNTHETIC"), ("cNaoNIF", "1")])
def test_inspection_does_not_promote_foreign_choice_to_subset(
    tag: str, value: str
) -> None:
    xml = _oracle().replace(
        b"<CNPJ>98ABC6780001Z0</CNPJ>", f"<{tag}>{value}</{tag}>".encode()
    )
    assert inspect_unsigned_dps(xml) == inspect_unsigned_dps(_GOLDEN_XML)
    with pytest.raises(DpsDocumentError, match="unsupported_document_structure"):
        parse_unsigned_dps(xml)


def test_construction_normalization_and_exact_model_types() -> None:
    identifier = FederalTaxId.cnpj("98abc6780001z0")
    assert _taker(tax_id=identifier).tax_id.value == "98ABC6780001Z0"

    class AddressSubclass(RestrictedDpsNationalAddress):
        pass

    class TakerSubclass(RestrictedDpsTaker):
        pass

    class StringSubclass(str):
        pass

    subclass_address = AddressSubclass(
        **cast(
            Any,
            {
                "municipality": MunicipalityCode("3550308"),
                "postal_code": "01234567",
                "street": "Rua",
                "number": "1",
                "neighborhood": "Centro",
            },
        )
    )
    with pytest.raises(DomainValidationError):
        _taker(address=subclass_address)
    with pytest.raises(DomainValidationError):
        _draft(
            taker=TakerSubclass(tax_id=identifier, name="Synthetic", address=_address())
        )
    for field in ("postal_code", "street", "number", "neighborhood", "complement"):
        with pytest.raises(DomainValidationError):
            _address(**{field: StringSubclass("01234567")})
    with pytest.raises(DomainValidationError):
        _taker(name=StringSubclass("Synthetic"))


@pytest.mark.parametrize(
    "target", ["name", "postal_code", "street", "complement", "tax_id", "address"]
)
def test_constructor_errors_do_not_echo_sensitive_values(target: str) -> None:
    sensitive = "synthetic-secret-payload\r"
    with pytest.raises(DomainValidationError) as caught:
        if target in ("name", "tax_id", "address"):
            _taker(**{target: sensitive})
        else:
            _address(**{target: sensitive})
    rendered = (
        str(caught.value)
        + repr(caught.value)
        + "".join(traceback.format_exception(caught.value))
    )
    assert sensitive not in rendered
    assert "98ABC6780001Z0" not in rendered
