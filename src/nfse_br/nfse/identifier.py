"""Lexical NFS-e identifiers from the frozen restricted schema."""

import re
from dataclasses import dataclass

from nfse_br.domain.errors import DomainValidationError

_NFSE_ID_LENGTH = 53
_NFSE_ID_PATTERN_TEXT = r"NFS[0-9]{9}[0-9A-Z]{14}[0-9]{27}"
_NFSE_ID_PATTERN = re.compile(_NFSE_ID_PATTERN_TEXT)


@dataclass(frozen=True, slots=True)
class NfseId:
    """An immutable, exact lexical ``TSIdNFSe`` value."""

    value: str

    def __post_init__(self) -> None:
        """Validate without coercion, case conversion, or whitespace changes."""
        if type(self.value) is not str:
            raise DomainValidationError(
                "NFS-e identifier must be provided as a string."
            )
        if (
            len(self.value) != _NFSE_ID_LENGTH
            or _NFSE_ID_PATTERN.fullmatch(self.value) is None
        ):
            raise DomainValidationError(
                "NFS-e identifier must match the 53-position ASCII XSD format."
            )

    def __str__(self) -> str:
        """Return the complete identifier value explicitly."""
        return self.value

    def __repr__(self) -> str:
        """Return a representation that does not disclose the identifier."""
        return "NfseId(value=<redacted>)"
