"""Offline tests for recovered NFS-e XSD validation."""

from __future__ import annotations

import hashlib
import io
import traceback
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest
from lxml import etree

import nfse_br.xsd
from nfse_br.xsd import RecoveredNfseValidator, XsdValidationError
from nfse_br.xsd import nfse_validator as nfse_module
from nfse_br.xsd import validator as validator_module

_XSD = "http://www.w3.org/2001/XMLSchema"
_NFSE_NS = "http://www.sped.fazenda.gov.br/nfse"
_NFSE_ROOT = f"{{{_NFSE_NS}}}NFSe"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_ROOT_SCHEMA = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="{_XSD}" targetNamespace="{_NFSE_NS}"
 xmlns="{_NFSE_NS}" elementFormDefault="qualified">
  <xs:include schemaLocation="types.xsd"/>
  <xs:element name="NFSe" type="TCNFSe"/>
  <xs:element name="Other" type="xs:string"/>
</xs:schema>
""".encode()

_TYPE_SCHEMA = f"""\
<xs:schema xmlns:xs="{_XSD}" targetNamespace="{_NFSE_NS}"
 xmlns="{_NFSE_NS}" elementFormDefault="qualified">
  <xs:complexType name="TCNFSe">
    <xs:sequence>
      <xs:element name="nNFSe">
        <xs:simpleType><xs:restriction base="xs:string">
          <xs:pattern value="[1-9][0-9]{{0,12}}"/>
        </xs:restriction></xs:simpleType>
      </xs:element>
      <xs:element name="description" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""".encode()

_VALID_XML = (
    f'<NFSe xmlns="{_NFSE_NS}"><nNFSe>42</nNFSe>'
    "<description>synthetic</description></NFSe>"
).encode()


def _members(**updates: bytes) -> dict[str, bytes]:
    values = {"root.xsd": _ROOT_SCHEMA, "types.xsd": _TYPE_SCHEMA}
    values.update(updates)
    return values


def _schema(members: Mapping[str, bytes] | None = None) -> etree.XMLSchema:
    values = dict(_members() if members is None else members)
    closure = validator_module._schema_closure(values, entrypoint="root.xsd")
    return validator_module._compile_schema(closure, "root.xsd")


def _synthetic_validator() -> RecoveredNfseValidator:
    validator = object.__new__(RecoveredNfseValidator)
    object.__setattr__(validator, "_schema", _schema())
    object.__setattr__(validator, "_root_qname", _NFSE_ROOT)
    return validator


def test_public_validator_validates_synthetic_nfse_sequentially() -> None:
    validator = _synthetic_validator()

    validator.validate(_VALID_XML)
    with pytest.raises(XsdValidationError, match="document_invalid"):
        validator.validate(_VALID_XML.replace(b">42<", b">0<"))
    validator.validate(_VALID_XML)


def test_utf8_bom_is_accepted() -> None:
    _synthetic_validator().validate(b"\xef\xbb\xbf" + _VALID_XML)


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        (b"", "empty_document"),
        (b"<NFSe>", "unsafe_or_malformed_xml"),
        (
            b'<?xml version="1.0" encoding="ISO-8859-1"?><NFSe/>',
            "unsafe_or_malformed_xml",
        ),
        (b"<!DOCTYPE NFSe><NFSe/>", "unsafe_or_malformed_xml"),
        (
            b"<!DOCTYPE NFSe [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>"
            b"<NFSe>&x;</NFSe>",
            "unsafe_or_malformed_xml",
        ),
        (b"\xff<NFSe/>", "unsafe_or_malformed_xml"),
    ],
)
def test_input_policy_rejects_unsafe_or_malformed_xml(xml: bytes, code: str) -> None:
    with pytest.raises(XsdValidationError) as caught:
        _synthetic_validator().validate(xml)

    assert caught.value.phase == "parse"
    assert caught.value.code == code


def test_input_requires_exact_bytes_and_enforces_size() -> None:
    validator = _synthetic_validator()
    for value in ("<NFSe/>", bytearray(b"<NFSe/>"), memoryview(b"<NFSe/>"), None):
        with pytest.raises(XsdValidationError, match="invalid_runtime_type"):
            validator.validate(value)  # type: ignore[arg-type]

    oversized = b"<" + b"x" * validator_module.MAX_XML_BYTES
    with pytest.raises(XsdValidationError, match="document_too_large"):
        validator.validate(oversized)


@pytest.mark.parametrize(
    "xml",
    [
        b'<NFSe xmlns="urn:wrong"/>',
        b"<NFSe/>",
        f'<nfse xmlns="{_NFSE_NS}"/>'.encode(),
        f'<DPS xmlns="{_NFSE_NS}"/>'.encode(),
    ],
)
def test_wrong_root_identity_is_rejected(xml: bytes) -> None:
    with pytest.raises(XsdValidationError) as caught:
        _synthetic_validator().validate(xml)

    assert caught.value.phase == "schema"
    assert caught.value.code == "unexpected_root"


def test_root_namespace_is_prefix_independent() -> None:
    xml = (
        f'<n:NFSe xmlns:n="{_NFSE_NS}"><n:nNFSe>42</n:nNFSe>'
        "<n:description>synthetic</n:description></n:NFSe>"
    ).encode()

    _synthetic_validator().validate(xml)


@pytest.mark.parametrize(
    "xml",
    [
        f'<NFSe xmlns="{_NFSE_NS}"><description>x</description></NFSe>'.encode(),
        (
            f'<NFSe xmlns="{_NFSE_NS}"><description>x</description>'
            "<nNFSe>42</nNFSe></NFSe>"
        ).encode(),
    ],
)
def test_schema_rejects_missing_required_field_and_wrong_order(xml: bytes) -> None:
    with pytest.raises(XsdValidationError, match="document_invalid"):
        _synthetic_validator().validate(xml)


def test_instance_schema_location_cannot_replace_pinned_schema() -> None:
    xml = f"""\
<NFSe xmlns="{_NFSE_NS}" xmlns:xsi="{_XSD}-instance"
 xsi:schemaLocation="{_NFSE_NS} https://evil.example/accept-all.xsd">
 <nNFSe>0</nNFSe><description>sensitive</description>
</NFSe>""".encode()

    with pytest.raises(XsdValidationError, match="document_invalid"):
        _synthetic_validator().validate(xml)


def test_xinclude_is_not_processed(tmp_path: Path) -> None:
    fragment = tmp_path / "nNFSe.xml"
    fragment.write_text(f'<nNFSe xmlns="{_NFSE_NS}">42</nNFSe>', encoding="utf-8")
    xml = f"""\
<NFSe xmlns="{_NFSE_NS}" xmlns:xi="http://www.w3.org/2001/XInclude">
 <xi:include href="{fragment.as_uri()}" parse="xml"/>
 <description>synthetic</description>
</NFSe>""".encode()

    parsed = etree.fromstring(xml, parser=validator_module._xml_parser(resources={}))
    assert parsed[0].tag == "{http://www.w3.org/2001/XInclude}include"
    with pytest.raises(XsdValidationError, match="document_invalid"):
        _synthetic_validator().validate(xml)


def test_sensitive_input_is_absent_from_error_surfaces() -> None:
    sensitive = "NFS29274082212ABC6780001Z0000000000004226090000000010"
    xml = _VALID_XML.replace(b">synthetic<", f">{sensitive}<extra/><".encode())

    with pytest.raises(XsdValidationError) as caught:
        _synthetic_validator().validate(xml)

    rendered = "".join(traceback.format_exception(caught.value))
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in rendered
    assert caught.value.__cause__ is None


def test_constructor_rejects_types_size_and_digest_before_archive() -> None:
    for value in (bytearray(), memoryview(b""), None):
        with pytest.raises(XsdValidationError, match="invalid_runtime_type"):
            RecoveredNfseValidator(value)  # type: ignore[arg-type]

    with pytest.raises(XsdValidationError, match="size_mismatch"):
        RecoveredNfseValidator(b"PK")
    with pytest.raises(XsdValidationError, match="digest_mismatch"):
        RecoveredNfseValidator(b"x" * validator_module.RESTRICTED_XSD_BUNDLE_SIZE)


def test_unsafe_archive_is_rejected_by_shared_bundle_engine() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../escape.xsd", _ROOT_SCHEMA)

    with pytest.raises(XsdValidationError, match="unsafe_archive"):
        validator_module._compile_bundle_profile(
            stream.getvalue(),
            profile_builder=nfse_module._official_nfse_schema_profile,
        )


def test_entrypoint_discovery_is_exact_and_unique() -> None:
    assert nfse_module._discover_nfse_entrypoint({"NFSe.xsd": _ROOT_SCHEMA}) == (
        "NFSe.xsd",
        _NFSE_ROOT,
    )

    with pytest.raises(XsdValidationError, match="entrypoint_not_unique"):
        nfse_module._discover_nfse_entrypoint({"types.xsd": _TYPE_SCHEMA})
    with pytest.raises(XsdValidationError, match="entrypoint_not_unique"):
        nfse_module._discover_nfse_entrypoint(
            {"one.xsd": _ROOT_SCHEMA, "two.xsd": _ROOT_SCHEMA}
        )


def test_entrypoint_discovery_ignores_wrong_namespace_and_case() -> None:
    wrong_namespace = _ROOT_SCHEMA.replace(_NFSE_NS.encode(), b"urn:wrong")
    wrong_case = _ROOT_SCHEMA.replace(b'name="NFSe"', b'name="nfse"')

    with pytest.raises(XsdValidationError, match="entrypoint_not_unique"):
        nfse_module._discover_nfse_entrypoint(
            {"wrong-ns.xsd": wrong_namespace, "wrong-case.xsd": wrong_case}
        )


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/types.xsd",
        "../types.xsd",
        "/absolute/types.xsd",
        "C:\\types.xsd",
        "//[sensitive]",
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


def test_missing_dependency_and_namespace_mismatches_are_rejected() -> None:
    with pytest.raises(XsdValidationError, match="schema_dependency_missing"):
        validator_module._schema_closure(
            {"root.xsd": _ROOT_SCHEMA}, entrypoint="root.xsd"
        )

    wrong_include = _TYPE_SCHEMA.replace(_NFSE_NS.encode(), b"urn:wrong")
    with pytest.raises(XsdValidationError, match="include_namespace_mismatch"):
        validator_module._schema_closure(
            _members(**{"types.xsd": wrong_include}), entrypoint="root.xsd"
        )

    imported = _TYPE_SCHEMA.replace(_NFSE_NS.encode(), b"urn:external")
    root = _ROOT_SCHEMA.replace(
        b'<xs:include schemaLocation="types.xsd"/>',
        b'<xs:import namespace="urn:declared" schemaLocation="types.xsd"/>',
    )
    with pytest.raises(XsdValidationError, match="import_namespace_mismatch"):
        validator_module._schema_closure(
            _members(**{"root.xsd": root, "types.xsd": imported}),
            entrypoint="root.xsd",
        )


def test_synthetic_profile_cannot_replace_official_pins() -> None:
    with pytest.raises(XsdValidationError, match="schema_profile_mismatch"):
        nfse_module._official_nfse_schema_profile(_members())


def test_runtime_profile_pins_match_documentation() -> None:
    bundle_hash = "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
    members = {
        "NFSe_v1.01.xsd": (
            738,
            "1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0",
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
    documentation = (
        _REPOSITORY_ROOT / "contracts/restricted/NFSE_RECOVERED_VALIDATOR.md"
    ).read_text(encoding="utf-8")

    assert validator_module.RESTRICTED_XSD_BUNDLE_SIZE == 34_933
    assert validator_module.RESTRICTED_XSD_BUNDLE_SHA256 == bundle_hash
    assert nfse_module.EXPECTED_NFSE_ENTRYPOINT == "NFSe_v1.01.xsd"
    assert nfse_module.EXPECTED_NFSE_ROOT_QNAME == _NFSE_ROOT
    assert nfse_module.EXPECTED_NFSE_SCHEMA_MEMBERS == {
        name: digest for name, (_, digest) in members.items()
    }
    assert "size:   34933 bytes" in documentation
    assert f"sha256: {bundle_hash}" in documentation
    assert "`NFSe_v1.01.xsd`" in documentation
    assert f"`{_NFSE_ROOT}`" in documentation
    for name, (size, digest) in members.items():
        assert f"| `{name}` | {size} | `{digest}` |" in documentation


def test_public_subpackage_exports_recovered_validator() -> None:
    assert nfse_br.xsd.__all__ == [
        "RecoveredNfseChecker",
        "RecoveredNfseValidator",
        "RestrictedDpsChecker",
        "RestrictedDpsXsdValidator",
        "XsdValidationError",
    ]


def test_documented_member_hashes_are_internally_well_formed() -> None:
    assert all(
        len(digest) == 64 and int(digest, 16) >= 0
        for digest in nfse_module.EXPECTED_NFSE_SCHEMA_MEMBERS.values()
    )
    assert hashlib.sha256(b"").hexdigest() not in (
        nfse_module.EXPECTED_NFSE_SCHEMA_MEMBERS.values()
    )
