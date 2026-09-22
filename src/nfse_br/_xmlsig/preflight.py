"""Compatibility adapter for the former unsigned-DPS signature preflight."""

from __future__ import annotations

from nfse_br.dps.document import (
    _MAX_XML_BYTES,
    DpsDocumentError,
)
from nfse_br.dps.document import (
    inspect_unsigned_dps as _inspect_unsigned_dps,
)

MAX_XML_BYTES = _MAX_XML_BYTES


class SignaturePreflightError(ValueError):
    """A privacy-safe rejection before any signature operation."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"DPS signature preflight failed ({code}).")

    def __repr__(self) -> str:
        """Return only the controlled diagnostic code."""
        return f"SignaturePreflightError(code={self.code!r})"


def inspect_unsigned_dps(xml_bytes: bytes) -> str:
    """Return the verified ``infDPS`` Id using the public structural inspector."""
    try:
        identity = _inspect_unsigned_dps(xml_bytes)
    except DpsDocumentError as exc:
        raise SignaturePreflightError(exc.code) from None
    return identity.value
