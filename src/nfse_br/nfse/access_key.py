"""Lexical NFS-e access keys from the frozen restricted schema."""

import re
from dataclasses import dataclass

from nfse_br.domain.errors import DomainValidationError

_ACCESS_KEY_LENGTH = 50
_ACCESS_KEY_PATTERN_TEXT = r"[0-9]{6}([0-9A-Z]{14})[0-9]{30}"
_ACCESS_KEY_PATTERN = re.compile(_ACCESS_KEY_PATTERN_TEXT)


@dataclass(frozen=True, slots=True)
class NfseAccessKey:
    """An immutable, exact lexical ``TSChaveNFSe`` value."""

    value: str

    def __post_init__(self) -> None:
        """Validate without coercion, case conversion, or whitespace changes."""
        if type(self.value) is not str:
            raise DomainValidationError(
                "NFS-e access key must be provided as a string."
            )
        if (
            len(self.value) != _ACCESS_KEY_LENGTH
            or _ACCESS_KEY_PATTERN.fullmatch(self.value) is None
        ):
            raise DomainValidationError(
                "NFS-e access key must match the 50-position ASCII XSD format."
            )

    def __str__(self) -> str:
        """Return the complete access key value explicitly."""
        return self.value

    def __repr__(self) -> str:
        """Return a representation that does not disclose the access key."""
        return "NfseAccessKey(value=<redacted>)"
