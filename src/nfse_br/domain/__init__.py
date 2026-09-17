"""Public domain primitives for nfse-br."""

from nfse_br.domain.competence import CompetenceDate
from nfse_br.domain.environment import NfseEnvironment
from nfse_br.domain.errors import DomainValidationError
from nfse_br.domain.federal_tax_id import FederalTaxId, FederalTaxIdKind
from nfse_br.domain.municipality import MunicipalityCode

__all__ = [
    "CompetenceDate",
    "DomainValidationError",
    "FederalTaxId",
    "FederalTaxIdKind",
    "MunicipalityCode",
    "NfseEnvironment",
]
