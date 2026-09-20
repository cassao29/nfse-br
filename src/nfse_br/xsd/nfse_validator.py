"""Fail-closed validation of recovered NFS-e XML against the frozen bundle."""

from __future__ import annotations

from collections.abc import Mapping

from nfse_br.xsd.validator import (
    _ELEMENT,
    _NFSE_NAMESPACE,
    RESTRICTED_XSD_BUNDLE_SHA256,
    RESTRICTED_XSD_BUNDLE_SIZE,
    _compile_bundle_profile,
    _error,
    _pinned_schema_profile,
    _safe_schema_root,
    _SchemaProfile,
    _validate_xml,
    _verify_bundle_pin,
)

EXPECTED_NFSE_ENTRYPOINT = "NFSe_v1.01.xsd"
EXPECTED_NFSE_ROOT_QNAME = f"{{{_NFSE_NAMESPACE}}}NFSe"
EXPECTED_NFSE_SCHEMA_MEMBERS = {
    "NFSe_v1.01.xsd": (
        "1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0"
    ),
    "tiposComplexos_v1.01.xsd": (
        "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
    ),
    "tiposSimples_v1.01.xsd": (
        "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
    ),
    "xmldsig-core-schema.xsd": (
        "bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11"
    ),
}


class RecoveredNfseValidator:
    """Validate recovered NFS-e bytes against the pinned restricted schema."""

    __slots__ = ("_root_qname", "_schema")

    def __init__(self, bundle_bytes: bytes) -> None:
        """Verify and compile the NFS-e closure from the exact frozen bundle."""
        _verify_bundle_pin(
            bundle_bytes,
            expected_size=RESTRICTED_XSD_BUNDLE_SIZE,
            expected_sha256=RESTRICTED_XSD_BUNDLE_SHA256,
        )
        self._schema, self._root_qname = _compile_bundle_profile(
            bundle_bytes,
            profile_builder=_official_nfse_schema_profile,
        )

    def validate(self, xml_bytes: bytes) -> None:
        """Return ``None`` only for an exact-root, XSD-valid NFS-e document."""
        _validate_xml(self._schema, xml_bytes, expected_root=self._root_qname)


def _official_nfse_schema_profile(
    members: Mapping[str, bytes],
) -> _SchemaProfile:
    return _pinned_schema_profile(
        members,
        discover_entrypoint=_discover_nfse_entrypoint,
        expected_entrypoint=EXPECTED_NFSE_ENTRYPOINT,
        expected_root_qname=EXPECTED_NFSE_ROOT_QNAME,
        expected_members=EXPECTED_NFSE_SCHEMA_MEMBERS,
    )


def _discover_nfse_entrypoint(members: Mapping[str, bytes]) -> tuple[str, str]:
    matches: list[tuple[str, str]] = []
    for name, data in sorted(members.items()):
        root = _safe_schema_root(data, source=name)
        if root.get("targetNamespace") != _NFSE_NAMESPACE:
            continue
        if any(element.get("name") == "NFSe" for element in root.findall(_ELEMENT)):
            matches.append((name, EXPECTED_NFSE_ROOT_QNAME))
    if len(matches) != 1:
        raise _error("bundle", "entrypoint_not_unique")
    return matches[0]
