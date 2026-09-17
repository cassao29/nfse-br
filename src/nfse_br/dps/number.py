"""DPS number values for the working local identity contract."""

from dataclasses import dataclass

from nfse_br.domain import DomainValidationError

_MAX_DPS_NUMBER = 999_999_999_999_999


@dataclass(frozen=True, slots=True)
class DpsNumber:
    """An immutable DPS number matching the frozen restricted schema."""

    value: int

    def __post_init__(self) -> None:
        """Validate the range imposed by the restricted ``TSNumDPS`` type."""
        if type(self.value) is not int:
            raise DomainValidationError("DPS number must be provided as an integer.")
        if not 1 <= self.value <= _MAX_DPS_NUMBER:
            raise DomainValidationError(
                "DPS number must be between 1 and 999999999999999."
            )

    @property
    def identity_component(self) -> str:
        """Return the number as the fifteen-position DPS identity component."""
        return f"{self.value:015d}"

    def __str__(self) -> str:
        """Return the unpadded decimal representation."""
        return str(self.value)
