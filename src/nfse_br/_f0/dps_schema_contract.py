"""Freeze a reviewed structural subset of the restricted DPS XSD contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, NoReturn, cast
from xml.etree import ElementTree

from nfse_br._f0.restricted_contract import (
    EXPECTED_XSD_URL,
    MAX_ARTIFACT_BYTES,
    ContractFreezeError,
    _atomic_write,
    _deserialize_manifest,
    _parse_safe_xml,
    _read_safe_zip,
    _reject_duplicate_xsd_basenames,
    _validate_manifest,
    _write_fixed_artifact,
    download_official_url,
)

IDENTITY_MANIFEST_SHA256: Final = (
    "2d8049958e7dcfa5e4e002a45cca8d526df83ab9c42b57eff2320017f85b3b8c"
)
XSD_ZIP_SHA256: Final = (
    "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc"
)
XSD_ZIP_SIZE: Final = 34_933

_COMPLEX_SCHEMA_PATH: Final = "tiposComplexos_v1.01.xsd"
_COMPLEX_SCHEMA_SIZE: Final = 114_148
_COMPLEX_SCHEMA_SHA256: Final = (
    "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
)
_SIMPLE_SCHEMA_PATH: Final = "tiposSimples_v1.01.xsd"
_SIMPLE_SCHEMA_SIZE: Final = 69_488
_SIMPLE_SCHEMA_SHA256: Final = (
    "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
)

_ROOT_COMPLEX_TYPE_NAME: Final = "TCDPS"
_COMPLEX_TYPE_NAMES: Final = (
    "TCAtvEvento",
    "TCBeneficioMunicipal",
    "TCCServ",
    "TCComExterior",
    "TCDPS",
    "TCDocDedRed",
    "TCDocNFNFS",
    "TCDocOutNFSe",
    "TCEnderExt",
    "TCEnderExtSimples",
    "TCEnderNac",
    "TCEnderObraEvento",
    "TCEndereco",
    "TCEnderecoSimples",
    "TCExigSuspensa",
    "TCInfDPS",
    "TCInfoCompl",
    "TCInfoDedRed",
    "TCInfoItemPed",
    "TCInfoObra",
    "TCInfoPessoa",
    "TCInfoPrestador",
    "TCInfoRefNFSe",
    "TCInfoTributacao",
    "TCInfoValores",
    "TCListaDocDedRed",
    "TCLocPrest",
    "TCRTCInfoDest",
    "TCRTCInfoIBSCBS",
    "TCRTCInfoImovel",
    "TCRTCInfoReeRepRes",
    "TCRTCInfoTributosDif",
    "TCRTCInfoTributosIBSCBS",
    "TCRTCInfoTributosSitClas",
    "TCRTCInfoTributosTribRegular",
    "TCRTCInfoValoresIBSCBS",
    "TCRTCListaDoc",
    "TCRTCListaDocDFe",
    "TCRTCListaDocFiscalOutro",
    "TCRTCListaDocFornec",
    "TCRTCListaDocOutro",
    "TCRegTrib",
    "TCServ",
    "TCSubstituicao",
    "TCTribFederal",
    "TCVServPrest",
    "TCTribMunicipal",
    "TCTribOutrosPisCofins",
    "TCTribTotal",
    "TCTribTotalMonet",
    "TCTribTotalPercent",
    "TCVDescCondIncond",
)
_SIMPLE_TYPE_NAMES: Final = (
    "TCCodTribMun",
    "TSBairro",
    "TSCAEPF",
    "TSCEP",
    "TSCNPJ",
    "TSCPF",
    "TSChaveNFSe",
    "TSChaveNFe",
    "TSCidade",
    "TSCodCIB",
    "TSCodJustSubst",
    "TSCodMoeda",
    "TSCodMunIBGE",
    "TSCodNBS",
    "TSCodNaoNIF",
    "TSCodObra",
    "TSCodPaisISO",
    "TSCodTribNac",
    "TSCodVerificacao",
    "TSCodigoEndPostal",
    "TSCodigoInternoContribuinte",
    "TSComplementoEndereco",
    "TSDRT",
    "TSData",
    "TSDateTimeUTC",
    "TSDec15V2",
    "TSDec1V2",
    "TSDec2V2",
    "TSDec3V2",
    "TSDesc150",
    "TSDesc2000",
    "TSDesc255",
    "TSDescInfCompl",
    "TSDescOutDedRed",
    "TSEmail",
    "TSEmitenteDPS",
    "TSEnvMDIC",
    "TSEstadoProvRegiao",
    "TSIdDPS",
    "TSIdeDedRed",
    "TSIdeEvento",
    "TSInscImobFisc",
    "TSInscMun",
    "TSLogradouro",
    "TSMecAFComExPrest",
    "TSMecAFComExToma",
    "TSModoPrestacao",
    "TSMotivo",
    "TSMotivoEmisTI",
    "TSMovTempBens",
    "TSNIF",
    "TSNomeRazaoSocial",
    "TSNum15Dig",
    "TSNum7Dig",
    "TSNumBeneficioMunicipal",
    "TSNumDPS",
    "TSNumDocImport",
    "TSNumProcExigSuspensa",
    "TSNumRegExport",
    "TSNumeroEndereco",
    "TSOpExigSuspensa",
    "TSOpSimpNac",
    "TSRTCChaveDFe",
    "TSRTCCodClassTrib",
    "TSRTCCodCredPres",
    "TSRTCCodIndOp",
    "TSRTCCodSitTrib",
    "TSRTCFinNFSe",
    "TSRTCIndDest",
    "TSRTCIndFinal",
    "TSRTCTipoChaveDFe",
    "TSRTCTpEnteGov",
    "TSRTCTpOper",
    "TSRTCTpReeRepRes",
    "TSRegEspTrib",
    "TSRegimeApuracaoSimpNac",
    "TSSerieDPS",
    "TSSerieNFNFS",
    "TSString",
    "TSStringComQuebraDeLinha",
    "TSTelefone",
    "TSTipoAmbiente",
    "TSTipoCST",
    "TSTipoImunidadeISSQN",
    "TSTipoIndTotTrib",
    "TSTipoRetISSQN",
    "TSTipoRetPISCofins",
    "TSTribISSQN",
    "TSVerAplic",
    "TSVincPrest",
    "TVerNFSe",
)

_EXPECTED_STRUCTURE_SHA256: Final = (
    "d5dcb8ac8c4f50a5b6fb9e035f2930b487c77e3642db903527a5a020e915dc4f"
)
_EXPECTED_CONTRACT_SHA256: Final = (
    "794c5904c4d81381d73050df63df541de587a08e195b7fb25f553937a43b67b0"
)

_XSD_NAMESPACE: Final = "http://www.w3.org/2001/XMLSchema"
_XSD: Final = f"{{{_XSD_NAMESPACE}}}"
_SCHEMA: Final = f"{_XSD}schema"
_ANNOTATION: Final = f"{_XSD}annotation"
_IMPORT: Final = f"{_XSD}import"
_INCLUDE: Final = f"{_XSD}include"
_COMPLEX_TYPE: Final = f"{_XSD}complexType"
_SIMPLE_TYPE: Final = f"{_XSD}simpleType"
_RESTRICTION: Final = f"{_XSD}restriction"
_SEQUENCE: Final = f"{_XSD}sequence"
_CHOICE: Final = f"{_XSD}choice"
_ELEMENT: Final = f"{_XSD}element"
_ATTRIBUTE: Final = f"{_XSD}attribute"
_SUPPORTED_FACETS: Final = frozenset(
    {
        "enumeration",
        "fractionDigits",
        "length",
        "maxInclusive",
        "maxLength",
        "minInclusive",
        "minLength",
        "pattern",
        "totalDigits",
        "whiteSpace",
    }
)
_EXPECTED_COMPLEX_SCHEMA_LINKS: Final = (
    (
        "import",
        "http://www.w3.org/2000/09/xmldsig#",
        "xmldsig-core-schema.xsd",
    ),
    ("include", None, "tiposSimples_v1.01.xsd"),
)
_EXPECTED_SIMPLE_SCHEMA_LINKS: Final[tuple[tuple[str, str | None, str], ...]] = ()
_EXPECTED_EXTERNAL_REFS: Final = frozenset({"ds:Signature"})

SchemaObject = dict[str, object]


def freeze_restricted_dps_schema_contract(
    *, identity_manifest_path: Path, work_dir: Path, contract_path: Path
) -> SchemaObject:
    """Download pinned bytes and freeze the reviewed structural DPS subset."""
    identity_manifest = _load_identity_manifest(identity_manifest_path)
    artifact = download_official_url(EXPECTED_XSD_URL, max_bytes=MAX_ARTIFACT_BYTES)
    _validate_xsd_zip_artifact(artifact.url, artifact.data)

    contract = _build_contract(
        xsd_zip=artifact.data,
        identity_manifest=identity_manifest,
    )
    serialized = _serialize_contract(contract)
    _assert_digest(
        serialized,
        expected=_EXPECTED_CONTRACT_SHA256,
        subject="DPS schema contract",
    )
    _validate_existing_contract(contract_path, expected=serialized)

    _write_fixed_artifact(work_dir, "restricted-xsd.zip", artifact.data)
    _atomic_write(contract_path, serialized)
    return contract


def _load_identity_manifest(path: Path) -> SchemaObject:
    if path.is_symlink():
        raise ContractFreezeError("Identity manifest must not be a symlink.")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ContractFreezeError(
            "Could not read the frozen identity manifest."
        ) from exc
    _assert_digest(
        data,
        expected=IDENTITY_MANIFEST_SHA256,
        subject="identity manifest",
    )
    manifest = _deserialize_manifest(data)
    _validate_manifest(manifest)
    xsd = _expect_mapping(manifest, "xsd")
    if xsd.get("sha256") != XSD_ZIP_SHA256 or xsd.get("size") != XSD_ZIP_SIZE:
        _drift("identity manifest does not bind the expected restricted XSD ZIP")
    return manifest


def _validate_xsd_zip_artifact(url: str, data: bytes) -> None:
    if url != EXPECTED_XSD_URL:
        raise ContractFreezeError(
            "OFFICIAL_ARTIFACT_CHANGED: restricted XSD URL differs from evidence."
        )
    if len(data) != XSD_ZIP_SIZE or _sha256(data) != XSD_ZIP_SHA256:
        raise ContractFreezeError(
            "OFFICIAL_ARTIFACT_CHANGED: restricted XSD bytes differ from evidence."
        )


def _build_contract(
    *, xsd_zip: bytes, identity_manifest: Mapping[str, object]
) -> SchemaObject:
    members = _read_safe_zip(xsd_zip)
    xsd_members = {
        path: data for path, data in members.items() if path.casefold().endswith(".xsd")
    }
    _reject_duplicate_xsd_basenames(xsd_members)
    complex_xsd = _require_source_member(
        members,
        path=_COMPLEX_SCHEMA_PATH,
        size=_COMPLEX_SCHEMA_SIZE,
        sha256=_COMPLEX_SCHEMA_SHA256,
    )
    simple_xsd = _require_source_member(
        members,
        path=_SIMPLE_SCHEMA_PATH,
        size=_SIMPLE_SCHEMA_SIZE,
        sha256=_SIMPLE_SCHEMA_SHA256,
    )

    structure = _extract_schema_subset(
        complex_xsd=complex_xsd,
        simple_xsd=simple_xsd,
        complex_type_names=_COMPLEX_TYPE_NAMES,
        simple_type_names=_SIMPLE_TYPE_NAMES,
    )
    _assert_schema_links(complex_xsd=complex_xsd, simple_xsd=simple_xsd)
    _assert_complex_dependency_closure(structure, complex_xsd=complex_xsd)
    _assert_simple_dependency_closure(structure, simple_xsd=simple_xsd)
    _assert_qname_dependency_closure(structure)
    _assert_digest(
        _serialize_contract(structure),
        expected=_EXPECTED_STRUCTURE_SHA256,
        subject="DPS schema structure",
    )

    xsd = _expect_mapping(identity_manifest, "xsd")
    identity_contract = _expect_mapping(xsd, "identity_contract")
    series_contract = _expect_mapping(xsd, "series_contract")
    simple_types = _expect_mapping(structure, "simple_types")
    _assert_identity_binding(
        identity_contract=identity_contract,
        series_contract=series_contract,
        simple_types=simple_types,
    )

    return {
        "authority": "official_frozen",
        "complex_types": structure["complex_types"],
        "environment": "restricted",
        "schemas": [
            {
                "path": _COMPLEX_SCHEMA_PATH,
                "sha256": _COMPLEX_SCHEMA_SHA256,
                "size": _COMPLEX_SCHEMA_SIZE,
            },
            {
                "path": _SIMPLE_SCHEMA_PATH,
                "sha256": _SIMPLE_SCHEMA_SHA256,
                "size": _SIMPLE_SCHEMA_SIZE,
            },
        ],
        "scope": "dps_structural_subset",
        "simple_types": structure["simple_types"],
        "source": {
            "identity_manifest_sha256": IDENTITY_MANIFEST_SHA256,
            "xsd_zip_sha256": XSD_ZIP_SHA256,
            "xsd_zip_size": XSD_ZIP_SIZE,
            "xsd_zip_url": EXPECTED_XSD_URL,
        },
        "transmission_ready": False,
    }


def _require_source_member(
    members: Mapping[str, bytes], *, path: str, size: int, sha256: str
) -> bytes:
    data = members.get(path)
    if data is None:
        _drift(f"required source schema {path!r} is missing")
    if len(data) != size or _sha256(data) != sha256:
        raise ContractFreezeError(
            f"OFFICIAL_ARTIFACT_CHANGED: source schema {path!r} differs from evidence."
        )
    return data


def _extract_schema_subset(
    *,
    complex_xsd: bytes,
    simple_xsd: bytes,
    complex_type_names: Iterable[str],
    simple_type_names: Iterable[str],
) -> SchemaObject:
    complex_root = _parse_schema(complex_xsd, source="complex schema")
    simple_root = _parse_schema(simple_xsd, source="simple schema")
    complex_types = {
        name: _parse_complex_type(
            _find_unique_definition(complex_root, _COMPLEX_TYPE, name),
            name=name,
        )
        for name in sorted(complex_type_names)
    }
    simple_types = {
        name: _parse_simple_type(
            _find_unique_definition(simple_root, _SIMPLE_TYPE, name),
            name=name,
        )
        for name in sorted(simple_type_names)
    }
    return {"complex_types": complex_types, "simple_types": simple_types}


def _parse_schema(data: bytes, *, source: str) -> ElementTree.Element:
    root = _parse_safe_xml(data, source=source)
    if root.tag != _SCHEMA:
        _drift(f"{source} root is not xs:schema")
    return root


def _assert_schema_links(*, complex_xsd: bytes, simple_xsd: bytes) -> None:
    observed_complex = _schema_links(
        _parse_schema(complex_xsd, source="complex schema")
    )
    observed_simple = _schema_links(_parse_schema(simple_xsd, source="simple schema"))
    if observed_complex != _EXPECTED_COMPLEX_SCHEMA_LINKS:
        _drift(
            "complex schema include/import declarations differ; "
            f"expected {_EXPECTED_COMPLEX_SCHEMA_LINKS!r}, "
            f"observed {observed_complex!r}"
        )
    if observed_simple != _EXPECTED_SIMPLE_SCHEMA_LINKS:
        _drift(
            "simple schema include/import declarations differ; "
            f"expected {_EXPECTED_SIMPLE_SCHEMA_LINKS!r}, "
            f"observed {observed_simple!r}"
        )


def _schema_links(
    root: ElementTree.Element,
) -> tuple[tuple[str, str | None, str], ...]:
    links: list[tuple[str, str | None, str]] = []
    for child in root:
        if child.tag not in {_IMPORT, _INCLUDE}:
            continue
        location = child.get("schemaLocation")
        if not location:
            _drift("schema include/import must declare schemaLocation")
        links.append((_tag_name(child.tag), child.get("namespace"), location))
    return tuple(links)


def _find_unique_definition(
    root: ElementTree.Element, tag: str, name: str
) -> ElementTree.Element:
    matches = [child for child in root.findall(tag) if child.get("name") == name]
    if len(matches) != 1:
        _drift(f"{name} must be defined exactly once; observed {len(matches)}")
    return matches[0]


def _parse_complex_type(element: ElementTree.Element, *, name: str) -> SchemaObject:
    _expect_attributes(element, {"name"}, context=name)
    compositors: list[ElementTree.Element] = []
    attributes: list[SchemaObject] = []
    for child in element:
        if child.tag == _ANNOTATION:
            continue
        if child.tag in {_SEQUENCE, _CHOICE}:
            compositors.append(child)
            continue
        if child.tag == _ATTRIBUTE:
            attributes.append(_parse_attribute(child, context=name))
            continue
        _drift(f"{name} contains unsupported construct {_tag_name(child.tag)!r}")
    if len(compositors) != 1:
        _drift(f"{name} must contain exactly one sequence or choice")
    return {
        "attributes": attributes,
        "content": _parse_compositor(compositors[0], context=name, depth=0),
    }


def _parse_compositor(
    element: ElementTree.Element, *, context: str, depth: int
) -> SchemaObject:
    kind = _tag_name(element.tag)
    if element.tag not in {_SEQUENCE, _CHOICE}:
        _drift(f"{context} uses unsupported compositor {kind!r}")
    _expect_attributes(element, {"minOccurs", "maxOccurs"}, context=context)
    particles: list[SchemaObject] = []
    for child in element:
        if child.tag == _ANNOTATION:
            continue
        if child.tag == _ELEMENT:
            particles.append(_parse_element(child, context=context))
            continue
        if child.tag == _CHOICE and element.tag == _SEQUENCE and depth == 0:
            particles.append(_parse_compositor(child, context=context, depth=1))
            continue
        _drift(
            f"{context} contains unsupported nested compositor {_tag_name(child.tag)!r}"
        )
    if not particles:
        _drift(f"{context} contains an empty {kind}")
    return {
        "kind": kind,
        "max_occurs": _occurs(element, "maxOccurs"),
        "min_occurs": _occurs(element, "minOccurs"),
        "particles": particles,
    }


def _parse_element(element: ElementTree.Element, *, context: str) -> SchemaObject:
    _expect_attributes(
        element,
        {"name", "ref", "type", "minOccurs", "maxOccurs"},
        context=context,
    )
    _expect_annotation_only(element, context=context)
    name = element.get("name")
    reference = element.get("ref")
    if (name is None) == (reference is None):
        _drift(f"{context} element must declare exactly one of name or ref")
    result: SchemaObject = {
        "kind": "element",
        "max_occurs": _occurs(element, "maxOccurs"),
        "min_occurs": _occurs(element, "minOccurs"),
    }
    if name is not None:
        result["name"] = name
    if reference is not None:
        result["ref"] = reference
    type_name = element.get("type")
    if type_name is not None:
        result["type"] = type_name
    return result


def _parse_attribute(element: ElementTree.Element, *, context: str) -> SchemaObject:
    _expect_attributes(
        element,
        {"name", "ref", "type", "use", "fixed", "default"},
        context=context,
    )
    _expect_annotation_only(element, context=context)
    name = element.get("name")
    reference = element.get("ref")
    if (name is None) == (reference is None):
        _drift(f"{context} attribute must declare exactly one of name or ref")
    if element.get("fixed") is not None and element.get("default") is not None:
        _drift(f"{context} attribute cannot declare both fixed and default")
    use = element.get("use", "optional")
    if use not in {"optional", "prohibited", "required"}:
        _drift(f"{context} attribute has unsupported use {use!r}")
    result: SchemaObject = {"use": use}
    for field, value in (
        ("name", name),
        ("ref", reference),
        ("type", element.get("type")),
        ("fixed", element.get("fixed")),
        ("default", element.get("default")),
    ):
        if value is not None:
            result[field] = value
    return result


def _parse_simple_type(element: ElementTree.Element, *, name: str) -> SchemaObject:
    _expect_attributes(element, {"name"}, context=name)
    restrictions = [child for child in element if child.tag == _RESTRICTION]
    unsupported = [
        child for child in element if child.tag not in {_ANNOTATION, _RESTRICTION}
    ]
    if unsupported:
        _drift(f"{name} contains unsupported simple type construct")
    if len(restrictions) != 1:
        _drift(f"{name} must contain exactly one restriction")
    restriction = restrictions[0]
    _expect_attributes(restriction, {"base"}, context=name)
    base = restriction.get("base")
    if not base:
        _drift(f"{name} restriction must declare a base")

    facets: list[SchemaObject] = []
    for child in restriction:
        if child.tag == _ANNOTATION:
            continue
        facet_name = _tag_name(child.tag)
        if not child.tag.startswith(_XSD) or facet_name not in _SUPPORTED_FACETS:
            _drift(f"{name} contains unsupported facet {facet_name!r}")
        _expect_attributes(child, {"value", "fixed"}, context=name)
        _expect_annotation_only(child, context=name)
        value = child.get("value")
        if value is None:
            _drift(f"{name} facet {facet_name!r} has no value")
        facet: SchemaObject = {"name": facet_name, "value": value}
        fixed = child.get("fixed")
        if fixed is not None:
            facet["fixed"] = fixed
        facets.append(facet)
    if not facets:
        _drift(f"{name} restriction contains no supported facets")
    return {"base": base, "facets": facets}


def _expect_attributes(
    element: ElementTree.Element, allowed: set[str], *, context: str
) -> None:
    unexpected = set(element.attrib) - allowed
    if unexpected:
        _drift(f"{context} has unsupported attributes {sorted(unexpected)!r}")


def _expect_annotation_only(element: ElementTree.Element, *, context: str) -> None:
    unsupported = [child for child in element if child.tag != _ANNOTATION]
    if unsupported:
        _drift(f"{context} contains unsupported inline schema content")


def _occurs(element: ElementTree.Element, attribute: str) -> str:
    value = element.get(attribute, "1")
    valid = value.isascii() and value.isdecimal()
    if attribute == "maxOccurs":
        valid = valid or value == "unbounded"
    if not valid:
        _drift(f"invalid {attribute} value {value!r}")
    return value


def _assert_simple_dependency_closure(
    structure: Mapping[str, object], *, simple_xsd: bytes
) -> None:
    simple_root = _parse_schema(simple_xsd, source="simple schema")
    defined_simple_types = {
        child.get("name")
        for child in simple_root.findall(_SIMPLE_TYPE)
        if child.get("name") is not None
    }
    complex_types = _expect_mapping(structure, "complex_types")
    simple_types = _expect_mapping(structure, "simple_types")
    observed = set(_iter_type_references(complex_types)) & cast(
        set[str], defined_simple_types
    )
    pending = list(observed)
    while pending:
        current = pending.pop()
        current_type = _expect_mapping(simple_types, current)
        base = current_type.get("base")
        if type(base) is str and base in defined_simple_types and base not in observed:
            observed.add(base)
            pending.append(base)
    expected = set(_SIMPLE_TYPE_NAMES)
    if observed != expected:
        _drift(
            "simple type dependency closure differs; "
            f"expected {sorted(expected)!r}, observed {sorted(observed)!r}"
        )


def _assert_complex_dependency_closure(
    structure: Mapping[str, object], *, complex_xsd: bytes
) -> None:
    complex_root = _parse_schema(complex_xsd, source="complex schema")
    defined_complex_types = {
        child.get("name")
        for child in complex_root.findall(_COMPLEX_TYPE)
        if child.get("name") is not None
    }
    complex_types = _expect_mapping(structure, "complex_types")
    referenced = set(_iter_type_references(complex_types))
    observed = referenced & cast(set[str], defined_complex_types)
    observed.add(_ROOT_COMPLEX_TYPE_NAME)
    expected = set(_COMPLEX_TYPE_NAMES)
    if observed != expected:
        _drift(
            "complex type dependency closure differs; "
            f"expected {sorted(expected)!r}, observed {sorted(observed)!r}"
        )


def _assert_qname_dependency_closure(structure: Mapping[str, object]) -> None:
    complex_types = _expect_mapping(structure, "complex_types")
    simple_types = _expect_mapping(structure, "simple_types")
    local_types = set(complex_types) | set(simple_types)

    for field in ("type", "base"):
        for reference in _iter_field_references(structure, field=field):
            prefix, separator, local_name = reference.partition(":")
            if separator:
                if prefix == "xs" and local_name and ":" not in local_name:
                    continue
                _drift(f"unresolved local {field} QName {reference!r}")
            if not reference or reference not in local_types:
                _drift(f"unresolved local {field} QName {reference!r}")

    external_refs = frozenset(_iter_field_references(structure, field="ref"))
    if external_refs != _EXPECTED_EXTERNAL_REFS:
        _drift(
            "external element/attribute refs differ; "
            f"expected {sorted(_EXPECTED_EXTERNAL_REFS)!r}, "
            f"observed {sorted(external_refs)!r}"
        )


def _iter_type_references(value: object) -> Iterable[str]:
    if type(value) is dict:
        mapping = cast(dict[str, object], value)
        type_name = mapping.get("type")
        if type(type_name) is str:
            yield type_name
        for nested in mapping.values():
            yield from _iter_type_references(nested)
    elif type(value) is list:
        for nested in cast(list[object], value):
            yield from _iter_type_references(nested)


def _iter_field_references(value: object, *, field: str) -> Iterable[str]:
    if type(value) is dict:
        mapping = cast(dict[str, object], value)
        reference = mapping.get(field)
        if type(reference) is str:
            yield reference
        for nested in mapping.values():
            yield from _iter_field_references(nested, field=field)
    elif type(value) is list:
        for nested in cast(list[object], value):
            yield from _iter_field_references(nested, field=field)


def _assert_identity_binding(
    *,
    identity_contract: Mapping[str, object],
    series_contract: Mapping[str, object],
    simple_types: Mapping[str, object],
) -> None:
    identity = _expect_mapping(simple_types, "TSIdDPS")
    series = _expect_mapping(simple_types, "TSSerieDPS")
    if not _has_facet(
        identity,
        name="maxLength",
        value=str(identity_contract.get("max_length")),
    ) or not _has_facet(
        identity,
        name="pattern",
        value=cast(str, identity_contract.get("pattern")),
    ):
        _drift("TSIdDPS contradicts the frozen identity manifest")
    if not _has_facet(
        series,
        name="pattern",
        value=cast(str, series_contract.get("pattern")),
    ):
        _drift("TSSerieDPS contradicts the frozen identity manifest")


def _has_facet(simple_type: Mapping[str, object], *, name: str, value: str) -> bool:
    facets = simple_type.get("facets")
    if type(facets) is not list:
        _drift("simple type facets are malformed")
    return any(
        type(facet) is dict
        and cast(dict[str, object], facet).get("name") == name
        and cast(dict[str, object], facet).get("value") == value
        for facet in cast(list[object], facets)
    )


def _assert_expected_structure(
    observed: Mapping[str, object], expected: Mapping[str, object]
) -> None:
    if observed != expected:
        _drift("observed schema structure differs from the reviewed contract")


def _serialize_contract(contract: Mapping[str, object]) -> bytes:
    return (
        json.dumps(contract, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _validate_existing_contract(path: Path, *, expected: bytes) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise ContractFreezeError("DPS schema contract must not be a symlink.")
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise ContractFreezeError(
            "Could not read existing DPS schema contract."
        ) from exc
    if current != expected:
        _drift("existing DPS schema contract differs from official derivation")


def _assert_digest(data: bytes, *, expected: str, subject: str) -> None:
    observed = _sha256(data)
    if observed != expected:
        _drift(f"{subject} SHA-256 differs; expected {expected}, observed {observed}")


def _expect_mapping(mapping: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = mapping.get(field)
    if type(value) is not dict:
        _drift(f"field {field!r} must be an object")
    return cast(dict[str, object], value)


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _drift(message: str) -> NoReturn:
    raise ContractFreezeError(f"OFFICIAL_DPS_SCHEMA_DRIFT: {message}.")


__all__: list[str] = []
