"""NFS-e execution environments."""

from enum import Enum
from typing import Self

from nfse_br.domain.errors import DomainValidationError


class NfseEnvironment(Enum):
    """A supported environment in the national NFS-e contract."""

    PRODUCTION = 1
    RESTRICTED_PRODUCTION = 2

    @property
    def code(self) -> int:
        """Return the environment code used by the national contract."""
        return self.value

    @classmethod
    def from_code(cls, code: int) -> Self:
        """Create an environment from its national contract code."""
        if type(code) is not int:
            raise DomainValidationError("NFS-e environment code must be an integer.")

        try:
            return cls(code)
        except ValueError as error:
            raise DomainValidationError(
                f"Unsupported NFS-e environment code: {code}."
            ) from error
