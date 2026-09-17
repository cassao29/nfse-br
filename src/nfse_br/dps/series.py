"""DPS series values for the working local identity contract."""

from dataclasses import dataclass

from nfse_br.domain import DomainValidationError


@dataclass(frozen=True, slots=True)
class DpsSeries:
    """An immutable DPS series with a separate padded identity component."""

    value: str

    def __post_init__(self) -> None:
        """Validate the working lexical contract without normalizing the value."""
        if type(self.value) is not str:
            raise DomainValidationError("DPS series must be provided as a string.")

        is_short_form = 1 <= len(self.value) <= 4
        is_five_digit_form = len(self.value) == 5 and self.value[0] <= "8"
        if (
            not self.value.isascii()
            or not self.value.isdecimal()
            or not (is_short_form or is_five_digit_form)
        ):
            raise DomainValidationError(
                "DPS series must match the working numeric series contract."
            )

    @property
    def identity_component(self) -> str:
        """Return the series as the five-position DPS identity component."""
        return self.value.zfill(5)

    def __str__(self) -> str:
        """Return the original validated lexical value."""
        return self.value
