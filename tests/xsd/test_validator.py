"""Offline tests for the restricted DPS XSD validator."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

import pytest
from lxml import etree
from scripts import validate_official_dps_xsd as official_script

from nfse_br.xsd import RestrictedDpsXsdValidator, XsdValidationError
from nfse_br.xsd import validator as validator_module

_XSD = "http://www.w3.org/2001/XMLSchema"
_TEST_NS = "urn:nfse-br:test"
_TEST_ROOT = f"{{{_TEST_NS}}}DPS"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_ROOT_SCHEMA = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="{_XSD}" targetNamespace="{_TEST_NS}"
 xmlns="{_TEST_NS}" elementFormDefault="qualified">
  <xs:include schemaLocation="types.xsd"/>
  <xs:element name="DPS" type="TCDPS"/>
  <xs:element name="Other" type="xs:string"/>
</xs:schema>
""".encode()

_TYPE_SCHEMA = f"""\
<xs:schema xmlns:xs="{_XSD}" targetNamespace="{_TEST_NS}"
 xmlns="{_TEST_NS}" elementFormDefault="qualified">
  <xs:complexType name="TCDPS">
    <xs:sequence>
      <xs:element name="nDPS">
        <xs:simpleType><xs:restriction base="xs:string">
          <xs:pattern value="[1-9][0-9]{{0,14}}"/>
        </xs:restriction></xs:simpleType>
      </xs:element>
      <xs:element name="description" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""".encode()

_VALID_XML = (
    f'<DPS xmlns="{_TEST_NS}"><nDPS>42</nDPS><description>ok</description></DPS>'
).encode()
_OTHER_XML = f'<Other xmlns="{_TEST_NS}">schema-valid</Other>'.encode()


def _members(**updates: bytes) -> dict[str, bytes]:
    values = {"root.xsd": _ROOT_SCHEMA, "types.xsd": _TYPE_SCHEMA}
    values.update(updates)
    return values


def _schema(members: Mapping[str, bytes] | None = None) -> etree.XMLSchema:
    values = dict(_members() if members is None else members)
    closure = validator_module._schema_closure(values, entrypoint="root.xsd")
    return validator_module._compile_schema(closure, "root.xsd")


def _validate(schema: etree.XMLSchema, xml: bytes) -> None:
    validator_module._validate_xml(schema, xml, expected_root=_TEST_ROOT)


def test_local_include_compiles_and_validates_sequentially() -> None:
    schema = _schema()

    _validate(schema, _VALID_XML)
    with pytest.raises(XsdValidationError, match="document_invalid"):
        _validate(schema, _VALID_XML.replace(b">42<", b">0<"))
    _validate(schema, _VALID_XML)


def test_utf8_bom_input_is_accepted() -> None:
    _validate(_schema(), b"\xef\xbb\xbf" + _VALID_XML)


@pytest.mark.parametrize("number", [b"0", b"1000000000000000"])
def test_number_outside_schema_range_is_rejected(number: bytes) -> None:
    xml = _VALID_XML.replace(b">42<", b">" + number + b"<")

    with pytest.raises(XsdValidationError) as caught:
        _validate(_schema(), xml)

    assert caught.value.phase == "schema"
    assert caught.value.code == "document_invalid"


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        (b"", "empty_document"),
        (b"<DPS>", "unsafe_or_malformed_xml"),
        (
            b'<?xml version="1.0" encoding="ISO-8859-1"?><DPS/>',
            "unsafe_or_malformed_xml",
        ),
        (b"<!DOCTYPE DPS><DPS/>", "unsafe_or_malformed_xml"),
        (
            b"<!DOCTYPE DPS [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><DPS>&x;</DPS>",
            "unsafe_or_malformed_xml",
        ),
        (b"\xff<DPS/>", "unsafe_or_malformed_xml"),
    ],
)
def test_input_policy_rejects_unsafe_or_malformed_xml(xml: bytes, code: str) -> None:
    with pytest.raises(XsdValidationError) as caught:
        _validate(_schema(), xml)

    assert caught.value.phase == "parse"
    assert caught.value.code == code


def test_input_requires_exact_bytes_and_enforces_size_before_parsing() -> None:
    schema = _schema()
    for value in ("<DPS/>", bytearray(b"<DPS/>"), memoryview(b"<DPS/>"), None):
        with pytest.raises(XsdValidationError, match="invalid_runtime_type"):
            validator_module._validate_xml(
                schema,
                value,  # type: ignore[arg-type]
                expected_root=_TEST_ROOT,
            )

    oversized = b"<" + b"x" * validator_module.MAX_XML_BYTES
    with pytest.raises(XsdValidationError, match="document_too_large"):
        _validate(schema, oversized)


def test_validation_is_bound_to_the_expected_root_qname() -> None:
    schema = _schema()
    assert schema.validate(etree.fromstring(_OTHER_XML))

    with pytest.raises(XsdValidationError) as caught:
        _validate(schema, _OTHER_XML)

    assert caught.value.phase == "schema"
    assert caught.value.code == "unexpected_root"


def test_correct_root_namespace_is_prefix_independent() -> None:
    prefixed = (
        f'<nfse:DPS xmlns:nfse="{_TEST_NS}"><nfse:nDPS>42</nfse:nDPS>'
        "<nfse:description>ok</nfse:description></nfse:DPS>"
    ).encode()

    _validate(_schema(), prefixed)


@pytest.mark.parametrize(
    "xml",
    [
        b'<DPS xmlns="urn:wrong"><nDPS>42</nDPS><description>ok</description></DPS>',
        b"<DPS><nDPS>42</nDPS><description>ok</description></DPS>",
        f'<dps xmlns="{_TEST_NS}"/>'.encode(),
        _OTHER_XML,
        f'<Wrapper xmlns="{_TEST_NS}">{_VALID_XML.decode()}</Wrapper>'.encode(),
    ],
)
def test_wrong_root_identity_is_rejected_before_xsd_validation(xml: bytes) -> None:
    with pytest.raises(XsdValidationError) as caught:
        _validate(_schema(), xml)

    assert caught.value.phase == "schema"
    assert caught.value.code == "unexpected_root"


@pytest.mark.parametrize(
    "xml",
    [
        f'<DPS xmlns="{_TEST_NS}"><description>ok</description></DPS>'.encode(),
        (
            f'<DPS xmlns="{_TEST_NS}"><description>ok</description>'
            "<nDPS>42</nDPS></DPS>"
        ).encode(),
    ],
)
def test_schema_rejects_missing_required_field_and_wrong_order(xml: bytes) -> None:
    with pytest.raises(XsdValidationError, match="document_invalid"):
        _validate(_schema(), xml)


def test_instance_schema_location_cannot_replace_compiled_schema() -> None:
    xml = f"""\
<DPS xmlns="{_TEST_NS}" xmlns:xsi="{_XSD}-instance"
 xsi:schemaLocation="{_TEST_NS} https://evil.example/accept-all.xsd">
 <nDPS>0</nDPS><description>secret</description>
</DPS>""".encode()

    with pytest.raises(XsdValidationError, match="document_invalid"):
        _validate(_schema(), xml)


def test_xinclude_is_not_processed(tmp_path: Path) -> None:
    schema = _schema()
    _validate(schema, _VALID_XML)
    fragment = tmp_path / "nDPS.xml"
    fragment.write_text(
        f'<nDPS xmlns="{_TEST_NS}">42</nDPS>',
        encoding="utf-8",
    )
    xml = f"""\
<DPS xmlns="{_TEST_NS}" xmlns:xi="http://www.w3.org/2001/XInclude">
 <xi:include href="{fragment.as_uri()}" parse="xml"/>
 <description>ok</description>
</DPS>""".encode()

    parsed = etree.fromstring(xml, parser=validator_module._xml_parser(resources={}))
    assert parsed[0].tag == "{http://www.w3.org/2001/XInclude}include"
    assert parsed[0].get("href") == fragment.as_uri()

    with pytest.raises(XsdValidationError) as caught:
        _validate(schema, xml)

    assert caught.value.phase == "schema"
    assert caught.value.code == "document_invalid"


def test_sensitive_input_is_absent_from_message_repr_and_traceback() -> None:
    sensitive = "12ABC6780001Z0"
    xml = _VALID_XML.replace(b">ok<", f">{sensitive}<extra/><".encode())

    with pytest.raises(XsdValidationError) as caught:
        _validate(_schema(), xml)

    rendered = "".join(traceback.format_exception(caught.value))
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in rendered
    assert caught.value.__cause__ is None


def test_unexpected_root_error_does_not_expose_received_qname() -> None:
    sensitive = "12ABC6780001Z0"
    xml = f'<Root xmlns="urn:{sensitive}"/>'.encode()

    with pytest.raises(XsdValidationError) as caught:
        _validate(_schema(), xml)

    rendered = "".join(traceback.format_exception(caught.value))
    assert caught.value.code == "unexpected_root"
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in rendered


def test_fixture_mutation_requires_one_target_and_changes_bytes() -> None:
    original = b"before TARGET after"

    assert (
        official_script._replace_exactly_once(
            original,
            b"TARGET",
            b"changed",
            label="valid",
        )
        == b"before changed after"
    )

    with pytest.raises(official_script.FixtureMutationError, match="observed 0"):
        official_script._replace_exactly_once(
            original,
            b"missing",
            b"changed",
            label="missing",
        )
    with pytest.raises(official_script.FixtureMutationError, match="observed 2"):
        official_script._replace_exactly_once(
            b"TARGET TARGET",
            b"TARGET",
            b"changed",
            label="duplicate",
        )


def test_effective_fixture_mutation_is_rejected_by_the_engine() -> None:
    invalid = official_script._replace_exactly_once(
        _VALID_XML,
        b">42<",
        b">0<",
        label="synthetic nDPS zero",
    )
    assert invalid != _VALID_XML
    assert b">0<" in invalid

    with pytest.raises(XsdValidationError, match="document_invalid"):
        _validate(_schema(), invalid)


def test_official_negative_fixtures_are_effective_and_specific() -> None:
    cases = {case.label: case for case in official_script._negative_cases()}

    assert all(case.xml != official_script._VALID_DPS for case in cases.values())
    assert b"<nDPS>0</nDPS>" in cases["nDPS zero"].xml
    assert b"<tpAmb>" not in cases["required field removed"].xml
    assert (
        b"<nDPS>42</nDPS>\n    <serie>123</serie>" in cases["field order changed"].xml
    )
    assert b'xmlns="urn:wrong"' in cases["root namespace changed"].xml
    assert cases["isolated XMLDSig root"].xml.startswith(b"<Signature")
    assert cases["isolated XMLDSig root"].expected_code == "unexpected_root"


def test_runtime_profile_pins_match_frozen_evidence_and_documentation() -> None:
    bundle_hash = "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
    manifest_hash = "2d8049958e7dcfa5e4e002a45cca8d526df83ab9c42b57eff2320017f85b3b8c"
    contract_hash = "794c5904c4d81381d73050df63df541de587a08e195b7fb25f553937a43b67b0"
    members = {
        "DPS_v1.01.xsd": (
            678,
            "c7dab363d8cf7c83fc2b3b21e72cf669a51bd30947a5690685ea96c4b3e39dcd",
        ),
        "tiposComplexos_v1.01.xsd": (
            114_148,
            "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac",
        ),
        "tiposSimples_v1.01.xsd": (
            69_488,
            "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4",
        ),
        "xmldsig-core-schema.xsd": (
            10_003,
            "bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11",
        ),
    }
    manifest_path = _REPOSITORY_ROOT / "contracts/restricted/manifest.json"
    contract_path = _REPOSITORY_ROOT / "contracts/restricted/dps-schema-contract.json"
    documentation = (
        _REPOSITORY_ROOT / "contracts/restricted/DPS_XSD_VALIDATOR.md"
    ).read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == manifest_hash
    assert hashlib.sha256(contract_path.read_bytes()).hexdigest() == contract_hash
    assert validator_module.RESTRICTED_XSD_BUNDLE_SIZE == 34_933
    assert validator_module.RESTRICTED_XSD_BUNDLE_SHA256 == bundle_hash
    assert validator_module._EXPECTED_ENTRYPOINT == "DPS_v1.01.xsd"
    assert validator_module._EXPECTED_ROOT_QNAME == (
        "{http://www.sped.fazenda.gov.br/nfse}DPS"
    )
    assert validator_module._EXPECTED_SCHEMA_MEMBERS == {
        name: digest for name, (_, digest) in members.items()
    }
    assert manifest["xsd"]["size"] == 34_933
    assert manifest["xsd"]["sha256"] == bundle_hash
    assert contract["source"]["xsd_zip_size"] == 34_933
    assert contract["source"]["xsd_zip_sha256"] == bundle_hash
    assert contract["source"]["identity_manifest_sha256"] == manifest_hash
    assert {
        schema["path"]: (schema["size"], schema["sha256"])
        for schema in contract["schemas"]
    } == {
        name: value
        for name, value in members.items()
        if name in {"tiposComplexos_v1.01.xsd", "tiposSimples_v1.01.xsd"}
    }
    assert "size:   34933 bytes" in documentation
    assert f"sha256: {bundle_hash}" in documentation
    for name, (size, digest) in members.items():
        assert f"| `{name}` | {size} | `{digest}` |" in documentation


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/types.xsd",
        "http://www.gov.br/types.xsd",
        "ftp://example.test/types.xsd",
        "file:///tmp/types.xsd",
        "/absolute/types.xsd",
        "../types.xsd",
        "sub\\types.xsd",
        "C:\\types.xsd",
        "types.xsd?query=1",
        "types.xsd#fragment",
    ],
)
def test_external_or_unsafe_schema_locations_are_rejected(location: str) -> None:
    root = _ROOT_SCHEMA.replace(b"types.xsd", location.encode())

    with pytest.raises(XsdValidationError, match="unsafe_schema_location"):
        validator_module._schema_closure(
            _members(**{"root.xsd": root}), entrypoint="root.xsd"
        )


def test_missing_location_and_dependency_are_rejected() -> None:
    missing_location = _ROOT_SCHEMA.replace(b' schemaLocation="types.xsd"', b"")
    with pytest.raises(XsdValidationError, match="schema_location_missing"):
        validator_module._schema_closure(
            _members(**{"root.xsd": missing_location}), entrypoint="root.xsd"
        )

    with pytest.raises(XsdValidationError, match="schema_dependency_missing"):
        validator_module._schema_closure(
            {"root.xsd": _ROOT_SCHEMA}, entrypoint="root.xsd"
        )


def test_include_and_import_namespaces_must_match() -> None:
    wrong_include = _TYPE_SCHEMA.replace(_TEST_NS.encode(), b"urn:wrong")
    with pytest.raises(XsdValidationError, match="include_namespace_mismatch"):
        validator_module._schema_closure(
            _members(**{"types.xsd": wrong_include}), entrypoint="root.xsd"
        )

    imported = _TYPE_SCHEMA.replace(_TEST_NS.encode(), b"urn:external")
    root = _ROOT_SCHEMA.replace(
        b'<xs:include schemaLocation="types.xsd"/>',
        b'<xs:import namespace="urn:declared" schemaLocation="types.xsd"/>',
    )
    with pytest.raises(XsdValidationError, match="import_namespace_mismatch"):
        validator_module._schema_closure(
            _members(**{"root.xsd": root, "types.xsd": imported}),
            entrypoint="root.xsd",
        )


def test_schema_parser_rejects_non_schema_and_unsafe_xml() -> None:
    with pytest.raises(XsdValidationError, match="not_an_xsd_schema"):
        validator_module._schema_closure(
            _members(**{"types.xsd": b"<root/>"}), entrypoint="root.xsd"
        )
    with pytest.raises(XsdValidationError, match="unsafe_schema_xml"):
        validator_module._schema_closure(
            _members(**{"types.xsd": b"<!DOCTYPE schema><schema/>"}),
            entrypoint="root.xsd",
        )


def test_compile_rejects_invalid_schema_and_unknown_resolver_lookup() -> None:
    invalid = _TYPE_SCHEMA.replace(
        b'<xs:complexType name="TCDPS">', b"<xs:complexType>"
    )
    with pytest.raises(XsdValidationError, match="schema_compile_failed"):
        validator_module._compile_schema(_members(**{"types.xsd": invalid}), "root.xsd")

    resolver = validator_module._DenyByDefaultResolver({})
    with pytest.raises(OSError, match="approved in-memory set"):
        resolver.resolve("file:///etc/passwd", None, object())


def test_compiler_uses_deny_by_default_resolver_for_unknown_member() -> None:
    with pytest.raises(XsdValidationError, match="schema_compile_failed"):
        validator_module._compile_schema({"root.xsd": _ROOT_SCHEMA}, "root.xsd")


def test_bundle_constructor_rejects_types_size_and_digest_before_archive() -> None:
    for value in (bytearray(), memoryview(b""), None):
        with pytest.raises(XsdValidationError, match="invalid_runtime_type"):
            RestrictedDpsXsdValidator(value)  # type: ignore[arg-type]

    with pytest.raises(XsdValidationError, match="size_mismatch"):
        RestrictedDpsXsdValidator(b"PK")
    with pytest.raises(XsdValidationError, match="digest_mismatch"):
        RestrictedDpsXsdValidator(b"x" * validator_module.RESTRICTED_XSD_BUNDLE_SIZE)


def test_private_pin_primitive_accepts_matching_synthetic_bytes() -> None:
    data = b"synthetic bundle"

    validator_module._verify_bundle_pin(
        data,
        expected_size=len(data),
        expected_sha256=hashlib.sha256(data).hexdigest(),
    )


def test_entrypoint_discovery_is_exact() -> None:
    official_like = _ROOT_SCHEMA.replace(
        _TEST_NS.encode(), b"http://www.sped.fazenda.gov.br/nfse"
    )
    assert validator_module._discover_dps_entrypoint({"DPS.xsd": official_like}) == (
        "DPS.xsd",
        "{http://www.sped.fazenda.gov.br/nfse}DPS",
    )

    with pytest.raises(XsdValidationError, match="entrypoint_not_unique"):
        validator_module._discover_dps_entrypoint({"types.xsd": _TYPE_SCHEMA})


def test_entrypoint_discovery_ignores_missing_namespace_and_unrelated_elements() -> (
    None
):
    no_namespace = _TYPE_SCHEMA.replace(f' targetNamespace="{_TEST_NS}"'.encode(), b"")
    unrelated = _ROOT_SCHEMA.replace(b'name="DPS"', b'name="Other"')

    with pytest.raises(XsdValidationError, match="entrypoint_not_unique"):
        validator_module._discover_dps_entrypoint(
            {"no-namespace.xsd": no_namespace, "unrelated.xsd": unrelated}
        )


def test_closure_rejects_missing_entrypoint_and_handles_cycles() -> None:
    with pytest.raises(XsdValidationError, match="entrypoint_missing"):
        validator_module._schema_closure(_members(), entrypoint="missing.xsd")

    cyclic_types = _TYPE_SCHEMA.replace(
        b'<xs:complexType name="TCDPS">',
        b'<xs:include schemaLocation="root.xsd"/><xs:complexType name="TCDPS">',
    )
    closure = validator_module._schema_closure(
        _members(**{"types.xsd": cyclic_types}), entrypoint="root.xsd"
    )
    assert set(closure) == {"root.xsd", "types.xsd"}


def test_valid_import_is_kept_in_the_compilation_closure() -> None:
    imported = _TYPE_SCHEMA.replace(_TEST_NS.encode(), b"urn:external")
    root = _ROOT_SCHEMA.replace(
        b'<xs:include schemaLocation="types.xsd"/>',
        b'<xs:import namespace="urn:external" schemaLocation="types.xsd"/>',
    )

    closure = validator_module._schema_closure(
        _members(**{"root.xsd": root, "types.xsd": imported}),
        entrypoint="root.xsd",
    )

    assert set(closure) == {"root.xsd", "types.xsd"}


def test_compile_rejects_missing_entrypoint() -> None:
    with pytest.raises(XsdValidationError, match="entrypoint_missing"):
        validator_module._compile_schema(_members(), "missing.xsd")


def test_exception_position_accepts_only_two_integer_coordinates() -> None:
    class WithPosition(Exception):
        position: object

    valid = WithPosition()
    valid.position = (4, 8)
    invalid = WithPosition()
    invalid.position = (4, "8")

    assert validator_module._exception_position(valid) == (4, 8)
    assert validator_module._exception_position(invalid) == (None, None)
    assert validator_module._exception_position(Exception()) == (None, None)


def test_public_exception_exposes_only_controlled_diagnostics() -> None:
    error = XsdValidationError(
        phase="schema", code="document_invalid", line=3, column=7
    )

    assert str(error) == "XSD schema failure (document_invalid) at line 3, column 7."
    assert repr(error) == (
        "XsdValidationError(phase='schema', code='document_invalid', line=3, column=7)"
    )
    assert str(XsdValidationError(phase="parse", code="failed", line=2)) == (
        "XSD parse failure (failed) at line 2."
    )


def test_subpackage_without_lxml_explains_the_optional_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_xsd = sys.modules.pop("nfse_br.xsd")
    loaded_validator = sys.modules.pop("nfse_br.xsd.validator")
    try:
        with monkeypatch.context() as context:
            context.setitem(sys.modules, "lxml", None)
            with pytest.raises(ModuleNotFoundError, match=r"nfse-br\[xsd\]"):
                importlib.import_module("nfse_br.xsd")
    finally:
        sys.modules["nfse_br.xsd.validator"] = loaded_validator
        sys.modules["nfse_br.xsd"] = loaded_xsd
