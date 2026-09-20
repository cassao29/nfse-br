"""Optional local XSD validation for restricted DPS documents.

Install ``nfse-br[xsd]`` to use this module.
"""

try:
    from nfse_br.xsd.nfse_validator import RecoveredNfseValidator
    from nfse_br.xsd.validator import RestrictedDpsXsdValidator, XsdValidationError
except ModuleNotFoundError as exc:
    if exc.name != "lxml":
        raise
    raise ModuleNotFoundError(
        "nfse_br.xsd requires the optional 'xsd' extra; "
        "install it with `pip install nfse-br[xsd]`."
    ) from None

__all__ = [
    "RecoveredNfseValidator",
    "RestrictedDpsXsdValidator",
    "XsdValidationError",
]
