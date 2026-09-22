"""Composed local checks for already-recovered NFS-e XML bytes."""

from __future__ import annotations

from nfse_br.nfse.consistency import validate_nfse_document_consistency
from nfse_br.nfse.document import NfseDocumentInfo, extract_nfse_document_info
from nfse_br.xsd.nfse_validator import RecoveredNfseValidator


class RecoveredNfseChecker:
    """Run the complete local recovered NFS-e assurance pipeline."""

    __slots__ = ("_validator",)

    def __init__(self, bundle_bytes: bytes) -> None:
        """Verify and compile the pinned NFS-e schema bundle once."""
        self._validator = RecoveredNfseValidator(bundle_bytes)

    def check(self, xml_bytes: bytes) -> NfseDocumentInfo:
        """Validate, extract, check consistency, and return observed information."""
        self._validator.validate(xml_bytes)
        info = extract_nfse_document_info(xml_bytes)
        validate_nfse_document_consistency(xml_bytes)
        return info
