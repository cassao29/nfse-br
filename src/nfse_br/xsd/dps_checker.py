"""Composed local checks for unsigned restricted DPS XML bytes."""

from __future__ import annotations

from nfse_br.dps import DpsIdentity, inspect_unsigned_dps, parse_unsigned_dps
from nfse_br.dps.builder import RestrictedDpsDraft
from nfse_br.xsd.validator import RestrictedDpsXsdValidator


class RestrictedDpsChecker:
    """Validate the pinned schema, then inspect the unsigned DPS structure."""

    __slots__ = ("_validator",)

    def __init__(self, bundle_bytes: bytes) -> None:
        """Verify and compile the pinned DPS schema bundle once."""
        self._validator = RestrictedDpsXsdValidator(bundle_bytes)

    def check(self, xml_bytes: bytes) -> DpsIdentity:
        """Check one document and return its observed, derived identity."""
        self._validator.validate(xml_bytes)
        return inspect_unsigned_dps(xml_bytes)

    def parse(self, xml_bytes: bytes) -> RestrictedDpsDraft:
        """Validate the pinned schema, then parse the supported restricted subset."""
        self._validator.validate(xml_bytes)
        return parse_unsigned_dps(xml_bytes)
