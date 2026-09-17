"""DPS number values for the working local identity contract."""

from dataclasses import dataclass

from nfse_br.domain import DomainValidationError

_MAX_DPS_NUMBER = 999_999_999_999_999


@dataclass(frozen=True, slots=True)
class DpsNumber:
    """An immutable structural DPS number without allocation policy."""

    value: int

    def __post_init__(self) -> None:
        """Validate the structural range reserved by the identity contract."""
        if type(self.value) is not int:
            raise DomainValidationError("DPS number must be provided as an integer.")
        if not 0 <= self.value <= _MAX_DPS_NUMBER:
            raise DomainValidationError(
                "DPS number must fit the 15-position identity component."
            )

    @property
    def identity_component(self) -> str:
        """Return the number as the fifteen-position DPS identity component."""
        return f"{self.value:015d}"

    def __str__(self) -> str:
        """Return the unpadded decimal representation."""
        return str(self.value)
