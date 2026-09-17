"""Offline tests for the restricted DPS structural contract freeze."""

from __future__ import annotations

import hashlib
import importlib
import json
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest

import nfse_br._f0.dps_schema_contract as schema
from nfse_br._f0.restricted_contract import (
    EXPECTED_XSD_URL,
    ContractFreezeError,
    DownloadedArtifact,
)

_XSD_OPEN = '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
_XSD_CLOSE = "</xs:schema>"


def _complex_document(
    *,
    first: str = '<xs:element name="first" type="Code" minOccurs="0"/>',
    choice: str = (
        '<xs:choice minOccurs="0" maxOccurs="2">'
        '<xs:element name="alpha" type="Code"/>'
        '<xs:element name="beta" type="Code"/>'
        "</xs:choice>"
    ),
    second: str = '<xs:element name="second" type="Code" maxOccurs="unbounded"/>',
    attribute: str = '<xs:attribute name="Id" type="Code" use="required"/>',
    extra_definition: str = "",
) -> bytes:
    return (
        _XSD_OPEN
        + '<xs:complexType name="Root"><xs:sequence>'
        + first
        + choice
        + second
        + "</xs:sequence>"
        + attribute
        + "</xs:complexType>"
        + extra_definition
        + _XSD_CLOSE
    ).encode()


def _simple_document(
    *,
    pattern: str = "[A-Z]",
    enumerations: tuple[str, ...] = ("A", "B"),
    extra_definition: str = "",
) -> bytes:
    facets = '<xs:whiteSpace value="preserve"/>'
    facets += f'<xs:pattern value="{pattern}"/>'
    facets += "".join(f'<xs:enumeration value="{value}"/>' for value in enumerations)
    return (
        _XSD_OPEN
        + '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
        + facets
        + "</xs:restriction></xs:simpleType>"
        + extra_definition
        + _XSD_CLOSE
    ).encode()


def _freeze_simple_document() -> bytes:
    return (
        _XSD_OPEN
        + '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
        + '<xs:pattern value="[A-Z]"/>'
        + "</xs:restriction></xs:simpleType>"
        + '<xs:simpleType name="TSIdDPS"><xs:restriction base="xs:string">'
        + '<xs:maxLength value="45"/>'
        + '<xs:pattern value="DPS[0-9]{7}(1[0-9]{14}|2[0-9A-Z]{14})[0-9]{20}"/>'
        + "</xs:restriction></xs:simpleType>"
        + '<xs:simpleType name="TSSerieDPS"><xs:restriction base="xs:string">'
        + '<xs:pattern value="[0-9]{1,4}|[0-8][0-9]{4}"/>'
        + "</xs:restriction></xs:simpleType>"
        + _XSD_CLOSE
    ).encode()


def _freeze_complex_document() -> bytes:
    return (
        _XSD_OPEN
        + '<xs:complexType name="Root"><xs:sequence>'
        + '<xs:element name="code" type="Code"/>'
        + '<xs:element name="identity" type="TSIdDPS"/>'
        + '<xs:element name="series" type="TSSerieDPS"/>'
        + "</xs:sequence></xs:complexType>"
        + _XSD_CLOSE
    ).encode()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in members.items():
            archive.writestr(path, data)
    return output.getvalue()


def _extract(
    *, complex_xsd: bytes | None = None, simple_xsd: bytes | None = None
) -> schema.SchemaObject:
    return schema._extract_schema_subset(
        complex_xsd=complex_xsd or _complex_document(),
        simple_xsd=simple_xsd or _simple_document(),
        complex_type_names=("Root",),
        simple_type_names=("Code",),
    )


def _expect_drift(observed: schema.SchemaObject, expected: schema.SchemaObject) -> None:
    with pytest.raises(ContractFreezeError, match="OFFICIAL_DPS_SCHEMA_DRIFT"):
        schema._assert_expected_structure(observed, expected)


def test_extracts_sequence_choice_attributes_and_facets() -> None:
    contract = _extract()

    root = cast(dict[str, object], contract["complex_types"])["Root"]
    root_mapping = cast(dict[str, object], root)
    content = cast(dict[str, object], root_mapping["content"])
    particles = cast(list[object], content["particles"])
    choice = cast(dict[str, object], particles[1])
    simple = cast(dict[str, object], contract["simple_types"])["Code"]

    assert content["kind"] == "sequence"
    assert content["min_occurs"] == "1"
    assert content["max_occurs"] == "1"
    assert choice["kind"] == "choice"
    assert choice["min_occurs"] == "0"
    assert choice["max_occurs"] == "2"
    assert root_mapping["attributes"] == [
        {"name": "Id", "type": "Code", "use": "required"}
    ]
    assert simple == {
        "base": "xs:string",
        "facets": [
            {"name": "whiteSpace", "value": "preserve"},
            {"name": "pattern", "value": "[A-Z]"},
            {"name": "enumeration", "value": "A"},
            {"name": "enumeration", "value": "B"},
        ],
    }


@pytest.mark.parametrize(
    ("complex_xsd", "simple_xsd"),
    [
        (_complex_document(first=""), _simple_document()),
        (
            _complex_document(
                first=(
                    '<xs:element name="first" type="Code" minOccurs="0"/>'
                    '<xs:element name="added" type="Code"/>'
                )
            ),
            _simple_document(),
        ),
        (
            _complex_document(
                first='<xs:element name="second" type="Code" maxOccurs="unbounded"/>',
                second='<xs:element name="first" type="Code" minOccurs="0"/>',
            ),
            _simple_document(),
        ),
        (
            _complex_document(
                first='<xs:element name="first" type="Code" minOccurs="1"/>'
            ),
            _simple_document(),
        ),
        (
            _complex_document(
                second='<xs:element name="second" type="Code" maxOccurs="2"/>'
            ),
            _simple_document(),
        ),
        (
            _complex_document(
                choice=(
                    '<xs:choice minOccurs="0" maxOccurs="2">'
                    '<xs:element name="alpha" type="Code"/>'
                    "</xs:choice>"
                )
            ),
            _simple_document(),
        ),
        (
            _complex_document(
                choice=(
                    '<xs:choice minOccurs="1" maxOccurs="2">'
                    '<xs:element name="alpha" type="Code"/>'
                    '<xs:element name="beta" type="Code"/>'
                    "</xs:choice>"
                )
            ),
            _simple_document(),
        ),
        (_complex_document(attribute=""), _simple_document()),
        (
            _complex_document(
                attribute='<xs:attribute name="Id" type="xs:string" use="required"/>'
            ),
            _simple_document(),
        ),
        (_complex_document(), _simple_document(pattern="[0-9]")),
        (_complex_document(), _simple_document(enumerations=("A",))),
    ],
    ids=(
        "sequence-field-removed",
        "sequence-field-added",
        "sequence-reordered",
        "min-occurs-changed",
        "max-occurs-changed",
        "choice-alternative-removed",
        "choice-cardinality-changed",
        "attribute-removed",
        "attribute-type-changed",
        "simple-pattern-changed",
        "enumeration-changed",
    ),
)
def test_structural_drift_is_fail_closed(complex_xsd: bytes, simple_xsd: bytes) -> None:
    _expect_drift(
        _extract(complex_xsd=complex_xsd, simple_xsd=simple_xsd),
        _extract(),
    )


def test_rejects_duplicate_complex_type() -> None:
    duplicate = (
        '<xs:complexType name="Root">'
        '<xs:sequence><xs:element name="other" type="Code"/></xs:sequence>'
        "</xs:complexType>"
    )

    with pytest.raises(ContractFreezeError, match="observed 2"):
        _extract(complex_xsd=_complex_document(extra_definition=duplicate))


def test_rejects_duplicate_simple_type() -> None:
    duplicate = (
        '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
        '<xs:pattern value="[0-9]"/>'
        "</xs:restriction></xs:simpleType>"
    )

    with pytest.raises(ContractFreezeError, match="observed 2"):
        _extract(simple_xsd=_simple_document(extra_definition=duplicate))


def test_rejects_unsupported_nested_compositor() -> None:
    nested = (
        "<xs:choice><xs:sequence>"
        '<xs:element name="nested" type="Code"/>'
        "</xs:sequence></xs:choice>"
    )

    with pytest.raises(ContractFreezeError, match="unsupported nested compositor"):
        _extract(complex_xsd=_complex_document(choice=nested))


@pytest.mark.parametrize(
    "complex_xsd",
    [
        (
            _XSD_OPEN
            + '<xs:complexType name="Root"><xs:sequence minOccurs="unbounded">'
            + '<xs:element name="first" type="Code"/>'
            + "</xs:sequence></xs:complexType>"
            + _XSD_CLOSE
        ).encode(),
        _complex_document(first='<xs:element name="first" ref="other"/>'),
        _complex_document(
            attribute='<xs:attribute name="Id" ref="other" use="required"/>'
        ),
        _complex_document(
            attribute=('<xs:attribute name="Id" type="Code" fixed="A" default="B"/>')
        ),
        _complex_document(
            attribute='<xs:attribute name="Id" type="Code" use="sometimes"/>'
        ),
        _complex_document(
            choice=(
                '<xs:choice><xs:element name="alpha" type="Code" '
                'unexpected="yes"/></xs:choice>'
            )
        ),
    ],
)
def test_rejects_ambiguous_or_unsupported_complex_structures(
    complex_xsd: bytes,
) -> None:
    with pytest.raises(ContractFreezeError, match="OFFICIAL_DPS_SCHEMA_DRIFT"):
        _extract(complex_xsd=complex_xsd)


@pytest.mark.parametrize(
    "simple_xsd",
    [
        (
            _XSD_OPEN
            + '<xs:simpleType name="Code"><xs:list itemType="xs:string"/>'
            + "</xs:simpleType>"
            + _XSD_CLOSE
        ).encode(),
        (
            _XSD_OPEN
            + '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
            + '<xs:assertion value="true()"/>'
            + "</xs:restriction></xs:simpleType>"
            + _XSD_CLOSE
        ).encode(),
        (
            _XSD_OPEN
            + '<xs:simpleType name="Code"><xs:restriction base="xs:string"/>'
            + "</xs:simpleType>"
            + _XSD_CLOSE
        ).encode(),
    ],
)
def test_rejects_unsupported_or_empty_simple_types(simple_xsd: bytes) -> None:
    with pytest.raises(ContractFreezeError, match="OFFICIAL_DPS_SCHEMA_DRIFT"):
        _extract(simple_xsd=simple_xsd)


def test_committed_contract_is_canonical_and_bound_to_v04_manifest() -> None:
    contract_path = Path("contracts/restricted/dps-schema-contract.json")
    identity_path = Path("contracts/restricted/manifest.json")
    contract_bytes = contract_path.read_bytes()
    contract = cast(dict[str, object], json.loads(contract_bytes))
    source = cast(dict[str, object], contract["source"])
    schemas = cast(list[dict[str, object]], contract["schemas"])
    complex_types = cast(dict[str, object], contract["complex_types"])
    simple_types = cast(dict[str, object], contract["simple_types"])

    assert hashlib.sha256(identity_path.read_bytes()).hexdigest() == (
        schema.IDENTITY_MANIFEST_SHA256
    )
    assert hashlib.sha256(contract_bytes).hexdigest() == (
        schema._EXPECTED_CONTRACT_SHA256
    )
    assert contract["authority"] == "official_frozen"
    assert contract["environment"] == "restricted"
    assert contract["scope"] == "dps_structural_subset"
    assert contract["transmission_ready"] is False
    assert source == {
        "identity_manifest_sha256": schema.IDENTITY_MANIFEST_SHA256,
        "xsd_zip_sha256": schema.XSD_ZIP_SHA256,
        "xsd_zip_size": schema.XSD_ZIP_SIZE,
        "xsd_zip_url": EXPECTED_XSD_URL,
    }
    assert schemas == [
        {
            "path": schema._COMPLEX_SCHEMA_PATH,
            "sha256": schema._COMPLEX_SCHEMA_SHA256,
            "size": schema._COMPLEX_SCHEMA_SIZE,
        },
        {
            "path": schema._SIMPLE_SCHEMA_PATH,
            "sha256": schema._SIMPLE_SCHEMA_SHA256,
            "size": schema._SIMPLE_SCHEMA_SIZE,
        },
    ]
    assert set(complex_types) == set(schema._COMPLEX_TYPE_NAMES)
    assert set(simple_types) == set(schema._SIMPLE_TYPE_NAMES)

    number = cast(dict[str, object], simple_types["TSNumDPS"])
    assert number["facets"] == [
        {"name": "whiteSpace", "value": "preserve"},
        {"name": "maxLength", "value": "15"},
        {"name": "pattern", "value": "[1-9]{1}[0-9]{0,14}"},
    ]


def test_committed_contract_preserves_v04_identity_facets() -> None:
    identity = cast(
        dict[str, object],
        json.loads(Path("contracts/restricted/manifest.json").read_bytes()),
    )
    contract = cast(
        dict[str, object],
        json.loads(Path("contracts/restricted/dps-schema-contract.json").read_bytes()),
    )
    xsd = cast(dict[str, object], identity["xsd"])
    identity_facets = cast(dict[str, object], xsd["identity_contract"])
    series_facets = cast(dict[str, object], xsd["series_contract"])
    simple_types = cast(dict[str, object], contract["simple_types"])

    schema._assert_identity_binding(
        identity_contract=identity_facets,
        series_contract=series_facets,
        simple_types=simple_types,
    )


def test_identity_manifest_hash_drift_is_rejected(tmp_path: Path) -> None:
    changed = tmp_path / "manifest.json"
    changed.write_bytes(Path("contracts/restricted/manifest.json").read_bytes() + b" ")

    with pytest.raises(ContractFreezeError, match="identity manifest SHA-256"):
        schema._load_identity_manifest(changed)


def test_identity_manifest_symlink_and_unreadable_path_are_rejected(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    symlink = tmp_path / "manifest-link.json"
    symlink.symlink_to(missing)

    with pytest.raises(ContractFreezeError, match="must not be a symlink"):
        schema._load_identity_manifest(symlink)
    with pytest.raises(ContractFreezeError, match="Could not read"):
        schema._load_identity_manifest(missing)


def test_changed_official_artifact_is_rejected() -> None:
    with pytest.raises(ContractFreezeError, match="OFFICIAL_ARTIFACT_CHANGED"):
        schema._validate_xsd_zip_artifact(EXPECTED_XSD_URL, b"changed")

    with pytest.raises(ContractFreezeError, match="URL differs"):
        schema._validate_xsd_zip_artifact(
            "https://www.gov.br/nfse/changed.zip",
            b"changed",
        )


def test_required_schema_member_is_exactly_bound() -> None:
    with pytest.raises(ContractFreezeError, match="required source schema"):
        schema._require_source_member({}, path="required.xsd", size=1, sha256="0")
    with pytest.raises(ContractFreezeError, match="OFFICIAL_ARTIFACT_CHANGED"):
        schema._require_source_member(
            {"required.xsd": b"x"},
            path="required.xsd",
            size=1,
            sha256="0" * 64,
        )


def test_rejects_non_schema_root_and_empty_or_unsupported_complex_types() -> None:
    with pytest.raises(ContractFreezeError, match="root is not xs:schema"):
        schema._parse_schema(b"<root/>", source="fixture")

    for definition in (
        '<xs:complexType name="Root"><xs:any/></xs:complexType>',
        '<xs:complexType name="Root"/>',
        '<xs:complexType name="Root"><xs:sequence/></xs:complexType>',
        ('<xs:complexType name="Root"><xs:sequence/><xs:choice/></xs:complexType>'),
    ):
        document = (_XSD_OPEN + definition + _XSD_CLOSE).encode()
        with pytest.raises(ContractFreezeError, match="OFFICIAL_DPS_SCHEMA_DRIFT"):
            _extract(complex_xsd=document)


def test_preserves_refs_defaults_fixed_facets_and_annotations() -> None:
    complex_xsd = (
        _XSD_OPEN
        + '<xs:complexType name="Root"><xs:annotation/>'
        + '<xs:choice><xs:annotation/><xs:element ref="external"><xs:annotation/>'
        + "</xs:element></xs:choice>"
        + '<xs:attribute ref="externalAttr" default="A"/>'
        + '<xs:attribute name="fixedAttr" fixed="B" use="prohibited"/>'
        + "</xs:complexType>"
        + _XSD_CLOSE
    ).encode()
    simple_xsd = (
        _XSD_OPEN
        + '<xs:simpleType name="Code"><xs:annotation/>'
        + '<xs:restriction base="xs:string"><xs:annotation/>'
        + '<xs:pattern value="[A-Z]" fixed="true"><xs:annotation/>'
        + "</xs:pattern></xs:restriction></xs:simpleType>"
        + _XSD_CLOSE
    ).encode()

    observed = _extract(complex_xsd=complex_xsd, simple_xsd=simple_xsd)
    root = cast(dict[str, object], observed["complex_types"])["Root"]
    root_mapping = cast(dict[str, object], root)
    content = cast(dict[str, object], root_mapping["content"])

    assert content["particles"] == [
        {
            "kind": "element",
            "max_occurs": "1",
            "min_occurs": "1",
            "ref": "external",
        }
    ]
    assert root_mapping["attributes"] == [
        {"default": "A", "ref": "externalAttr", "use": "optional"},
        {"fixed": "B", "name": "fixedAttr", "use": "prohibited"},
    ]
    simple = cast(dict[str, object], observed["simple_types"])["Code"]
    assert simple == {
        "base": "xs:string",
        "facets": [{"fixed": "true", "name": "pattern", "value": "[A-Z]"}],
    }


def test_rejects_invalid_simple_restriction_details() -> None:
    definitions = (
        '<xs:simpleType name="Code"><xs:restriction><xs:pattern value="x"/>'
        "</xs:restriction></xs:simpleType>",
        '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
        "<xs:pattern/></xs:restriction></xs:simpleType>",
        '<xs:simpleType name="Code"><xs:restriction base="xs:string">'
        '<xs:pattern value="x"><xs:element name="nested"/></xs:pattern>'
        "</xs:restriction></xs:simpleType>",
    )
    for definition in definitions:
        with pytest.raises(ContractFreezeError, match="OFFICIAL_DPS_SCHEMA_DRIFT"):
            _extract(simple_xsd=(_XSD_OPEN + definition + _XSD_CLOSE).encode())


def test_direct_simple_reference_and_identity_binding_drift_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    structure = _extract()
    monkeypatch.setattr(schema, "_SIMPLE_TYPE_NAMES", ("Missing",))
    with pytest.raises(ContractFreezeError, match="direct simple type references"):
        schema._assert_direct_simple_references(
            structure,
            simple_xsd=_simple_document(),
        )

    with pytest.raises(ContractFreezeError, match="TSIdDPS contradicts"):
        schema._assert_identity_binding(
            identity_contract={"max_length": 45, "pattern": "expected"},
            series_contract={"pattern": "series"},
            simple_types={
                "TSIdDPS": {"facets": []},
                "TSSerieDPS": {"facets": []},
            },
        )
    with pytest.raises(ContractFreezeError, match="TSSerieDPS contradicts"):
        schema._assert_identity_binding(
            identity_contract={"max_length": 45, "pattern": "identity"},
            series_contract={"pattern": "expected"},
            simple_types={
                "TSIdDPS": {
                    "facets": [
                        {"name": "maxLength", "value": "45"},
                        {"name": "pattern", "value": "identity"},
                    ]
                },
                "TSSerieDPS": {"facets": []},
            },
        )
    with pytest.raises(ContractFreezeError, match="facets are malformed"):
        schema._has_facet({}, name="pattern", value="x")


def test_existing_contract_is_never_replaced_silently(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_bytes(b"stale\n")

    with pytest.raises(ContractFreezeError, match="existing DPS schema contract"):
        schema._validate_existing_contract(contract, expected=b"fresh\n")
    assert contract.read_bytes() == b"stale\n"


def test_existing_contract_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"safe\n")
    link = tmp_path / "contract.json"
    link.symlink_to(target)

    with pytest.raises(ContractFreezeError, match="must not be a symlink"):
        schema._validate_existing_contract(link, expected=b"safe\n")
    assert target.read_bytes() == b"safe\n"


def test_mapping_contract_is_fail_closed() -> None:
    with pytest.raises(ContractFreezeError, match="must be an object"):
        schema._expect_mapping({"field": []}, "field")


def test_contract_serialization_is_byte_deterministic() -> None:
    contract = _extract()

    assert schema._serialize_contract(contract) == schema._serialize_contract(contract)
    assert schema._serialize_contract(contract).endswith(b"\n")


def test_offline_freeze_builds_and_writes_only_reviewed_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    complex_xsd = _freeze_complex_document()
    simple_xsd = _freeze_simple_document()
    archive = _zip_bytes(
        {
            "complex.xsd": complex_xsd,
            "simple.xsd": simple_xsd,
        }
    )
    identity_manifest = cast(
        dict[str, object],
        json.loads(Path("contracts/restricted/manifest.json").read_bytes()),
    )
    monkeypatch.setattr(schema, "XSD_ZIP_SHA256", schema._sha256(archive))
    monkeypatch.setattr(schema, "XSD_ZIP_SIZE", len(archive))
    monkeypatch.setattr(schema, "_COMPLEX_SCHEMA_PATH", "complex.xsd")
    monkeypatch.setattr(schema, "_COMPLEX_SCHEMA_SIZE", len(complex_xsd))
    monkeypatch.setattr(schema, "_COMPLEX_SCHEMA_SHA256", schema._sha256(complex_xsd))
    monkeypatch.setattr(schema, "_SIMPLE_SCHEMA_PATH", "simple.xsd")
    monkeypatch.setattr(schema, "_SIMPLE_SCHEMA_SIZE", len(simple_xsd))
    monkeypatch.setattr(schema, "_SIMPLE_SCHEMA_SHA256", schema._sha256(simple_xsd))
    monkeypatch.setattr(schema, "_COMPLEX_TYPE_NAMES", ("Root",))
    monkeypatch.setattr(schema, "_ROOT_COMPLEX_TYPE_NAME", "Root")
    monkeypatch.setattr(schema, "_SIMPLE_TYPE_NAMES", ("Code", "TSIdDPS", "TSSerieDPS"))
    structure = schema._extract_schema_subset(
        complex_xsd=complex_xsd,
        simple_xsd=simple_xsd,
        complex_type_names=schema._COMPLEX_TYPE_NAMES,
        simple_type_names=schema._SIMPLE_TYPE_NAMES,
    )
    monkeypatch.setattr(
        schema,
        "_EXPECTED_STRUCTURE_SHA256",
        schema._sha256(schema._serialize_contract(structure)),
    )
    contract = schema._build_contract(
        xsd_zip=archive,
        identity_manifest=identity_manifest,
    )
    monkeypatch.setattr(
        schema,
        "_EXPECTED_CONTRACT_SHA256",
        schema._sha256(schema._serialize_contract(contract)),
    )
    monkeypatch.setattr(
        schema,
        "_load_identity_manifest",
        lambda path: identity_manifest,
    )
    monkeypatch.setattr(
        schema,
        "download_official_url",
        lambda url, max_bytes: DownloadedArtifact(
            url=url,
            data=archive,
            content_type="application/zip",
        ),
    )
    work_dir = tmp_path / "work"
    contract_path = tmp_path / "contract.json"

    observed = schema.freeze_restricted_dps_schema_contract(
        identity_manifest_path=tmp_path / "identity.json",
        work_dir=work_dir,
        contract_path=contract_path,
    )

    assert observed == contract
    assert contract_path.read_bytes() == schema._serialize_contract(contract)
    assert (work_dir / "restricted-xsd.zip").read_bytes() == archive


def test_import_has_no_network_or_filesystem_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(urllib.request, "build_opener", forbidden)

    importlib.reload(schema)

    assert list(tmp_path.iterdir()) == []
