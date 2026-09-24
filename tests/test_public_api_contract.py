"""Intentional, independent public Python API oracle for the 0.4.0 contract.

Change these literals only after an explicit public-contract/versioning decision.
Introspection supplies observations, never the expected API. No schema bundle or
document is needed; the XSD extra is installed by the normal test environment.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from dataclasses import MISSING, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self, get_type_hints

import pytest

from nfse_br.domain import (
    CompetenceDate,
    FederalTaxId,
    FederalTaxIdKind,
    MunicipalityCode,
    NfseEnvironment,
)
from nfse_br.domain.cnpj import validate_cnpj_check_digits
from nfse_br.domain.cpf import validate_cpf_check_digits
from nfse_br.dps import (
    DpsIdentity,
    DpsNumber,
    DpsSeries,
    inspect_unsigned_dps,
    parse_unsigned_dps,
)
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps
from nfse_br.nfse import (
    NfseDocumentInfo,
    NfseId,
    extract_nfse_document_info,
    validate_nfse_document_consistency,
)
from nfse_br.xsd import (
    RecoveredNfseChecker,
    RecoveredNfseValidator,
    RestrictedDpsChecker,
    RestrictedDpsXsdValidator,
)

_POSITIONAL = inspect.Parameter.POSITIONAL_OR_KEYWORD
_KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
_REQUIRED = inspect.Parameter.empty
_UNANNOTATED = inspect.Signature.empty
_ParameterContract = tuple[str, object, object, object]

# Export order is not a caller contract. Sorted lists still detect duplicates,
# additions and removals, unlike a set-only comparison.
_EXPORTS = {
    "nfse_br": ("__version__",),
    "nfse_br.domain": (
        "CompetenceDate",
        "DomainValidationError",
        "FederalTaxId",
        "FederalTaxIdKind",
        "MunicipalityCode",
        "NfseEnvironment",
    ),
    "nfse_br.dps": (
        "DpsDocumentError",
        "DpsIdentity",
        "DpsNumber",
        "DpsSeries",
        "inspect_unsigned_dps",
        "parse_unsigned_dps",
    ),
    "nfse_br.dps.builder": ("RestrictedDpsDraft", "build_unsigned_dps"),
    "nfse_br.nfse": (
        "NfseAccessKey",
        "NfseConsistencyError",
        "NfseDocumentError",
        "NfseDocumentInfo",
        "NfseId",
        "extract_nfse_document_info",
        "validate_nfse_document_consistency",
    ),
    "nfse_br.xsd": (
        "RecoveredNfseChecker",
        "RecoveredNfseValidator",
        "RestrictedDpsChecker",
        "RestrictedDpsXsdValidator",
        "XsdValidationError",
    ),
    "nfse_br.domain.cpf": ("validate_cpf_check_digits",),
    "nfse_br.domain.cnpj": ("validate_cnpj_check_digits",),
}


@pytest.mark.parametrize("module_name, expected", _EXPORTS.items(), ids=_EXPORTS)
def test_public_exports(module_name: str, expected: tuple[str, ...]) -> None:
    module = importlib.import_module(module_name)
    actual = module.__all__
    assert sorted(actual) == sorted(expected), (
        f"public API contract mismatch: {module_name} exports; "
        f"expected={expected!r}, actual={actual!r}"
    )
    for name in expected:
        assert getattr(module, name) is not None, (
            f"missing export: {module_name}.{name}"
        )


def _assert_callable_contract(
    target: Callable[..., object],
    expected: tuple[_ParameterContract, ...],
    returns: object,
) -> None:
    signature = inspect.signature(target)
    hints = get_type_hints(target)
    observed = tuple(
        (
            parameter.name,
            parameter.kind,
            parameter.default,
            hints.get(parameter.name, _UNANNOTATED),
        )
        for parameter in signature.parameters.values()
    )
    label = f"{target.__module__}.{target.__qualname__}"
    assert observed == expected, (
        f"public API contract mismatch: {label} parameters; "
        f"expected={expected!r}, actual={observed!r}"
    )
    actual_return = hints.get("return", _UNANNOTATED)
    assert actual_return == returns, (
        f"public API contract mismatch: {label} return; "
        f"expected={returns!r}, actual={actual_return!r}"
    )


@pytest.mark.parametrize(
    "target, name, annotation, returns",
    [
        (build_unsigned_dps, "draft", RestrictedDpsDraft, bytes),
        (parse_unsigned_dps, "xml_bytes", bytes, RestrictedDpsDraft),
        (inspect_unsigned_dps, "xml_bytes", bytes, DpsIdentity),
        (extract_nfse_document_info, "xml_bytes", bytes, NfseDocumentInfo),
        (validate_nfse_document_consistency, "xml_bytes", bytes, type(None)),
        (validate_cpf_check_digits, "identifier", FederalTaxId, type(None)),
        (validate_cnpj_check_digits, "identifier", FederalTaxId, type(None)),
    ],
    ids=["build", "parse", "inspect", "extract", "consistency", "cpf", "cnpj"],
)
def test_public_functions(
    target: Callable[..., object], name: str, annotation: object, returns: object
) -> None:
    _assert_callable_contract(
        target, ((name, _POSITIONAL, _REQUIRED, annotation),), returns
    )


@pytest.mark.parametrize(
    "owner, name, expected",
    [
        (FederalTaxId, "cpf", (("value", _POSITIONAL, _REQUIRED, str),)),
        (FederalTaxId, "cnpj", (("value", _POSITIONAL, _REQUIRED, str),)),
        (CompetenceDate, "from_iso", (("value", _POSITIONAL, _REQUIRED, str),)),
        (NfseEnvironment, "from_code", (("code", _POSITIONAL, _REQUIRED, int),)),
        (
            DpsIdentity,
            "build",
            (
                ("municipality", _KEYWORD_ONLY, _REQUIRED, MunicipalityCode),
                ("federal_tax_id", _KEYWORD_ONLY, _REQUIRED, FederalTaxId),
                ("series", _KEYWORD_ONLY, _REQUIRED, DpsSeries),
                ("number", _KEYWORD_ONLY, _REQUIRED, DpsNumber),
            ),
        ),
    ],
    ids=["cpf", "cnpj", "competence", "environment", "identity"],
)
def test_public_factories(
    owner: type[object], name: str, expected: tuple[_ParameterContract, ...]
) -> None:
    assert isinstance(inspect.getattr_static(owner, name), classmethod)
    _assert_callable_contract(getattr(owner, name), expected, Self)


@pytest.mark.parametrize(
    "target, returns",
    [
        (RestrictedDpsChecker.check, DpsIdentity),
        (RestrictedDpsChecker.parse, RestrictedDpsDraft),
        (RestrictedDpsXsdValidator.validate, type(None)),
        (RecoveredNfseChecker.check, NfseDocumentInfo),
        (RecoveredNfseValidator.validate, type(None)),
    ],
    ids=["dps-check", "dps-parse", "dps-validate", "nfse-check", "nfse-validate"],
)
def test_xsd_public_methods(target: Callable[..., object], returns: object) -> None:
    _assert_callable_contract(
        target,
        (
            ("self", _POSITIONAL, _REQUIRED, _UNANNOTATED),
            ("xml_bytes", _POSITIONAL, _REQUIRED, bytes),
        ),
        returns,
    )


@pytest.mark.parametrize(
    "model, expected, kind",
    [
        (
            RestrictedDpsDraft,
            (
                ("issuer_tax_id", FederalTaxId),
                ("issue_municipality", MunicipalityCode),
                ("service_municipality", MunicipalityCode),
                ("series", DpsSeries),
                ("number", DpsNumber),
                ("issued_at", datetime),
                ("competence", CompetenceDate),
                ("application_version", str),
                ("national_service_code", str),
                ("service_description", str),
                ("service_amount", Decimal),
                ("op_simp_nac", Literal["1", "2", "3"]),
                ("reg_esp_trib", Literal["0", "1", "2", "3", "4", "5", "6", "9"]),
                ("trib_issqn", Literal["1", "2", "3", "4"]),
                ("tp_ret_issqn", Literal["1", "2", "3"]),
                ("ind_tot_trib", Literal["0"]),
            ),
            _KEYWORD_ONLY,
        ),
        (
            NfseDocumentInfo,
            (
                ("nfse_id", NfseId),
                ("nfse_number", str),
                ("embedded_dps_id", str),
            ),
            _POSITIONAL,
        ),
        (CompetenceDate, (("value", date),), _POSITIONAL),
        (FederalTaxId, (("kind", FederalTaxIdKind), ("value", str)), _POSITIONAL),
        (MunicipalityCode, (("value", str),), _POSITIONAL),
        (DpsNumber, (("value", int),), _POSITIONAL),
        (DpsSeries, (("value", str),), _POSITIONAL),
    ],
    ids=[
        "draft",
        "nfse-info",
        "competence",
        "tax-id",
        "municipality",
        "number",
        "series",
    ],
)
def test_public_dataclass_construction(
    model: type[object], expected: tuple[tuple[str, object], ...], kind: object
) -> None:
    assert is_dataclass(model)
    public_fields = [item for item in fields(model) if item.init]
    hints = get_type_hints(model)
    observed = tuple((item.name, hints[item.name]) for item in public_fields)
    assert observed == expected, (
        f"public API contract mismatch: {model.__name__} fields; "
        f"expected={expected!r}, actual={observed!r}"
    )
    for item in public_fields:
        assert item.default is MISSING, (
            f"{model.__name__}.{item.name}: unexpected default"
        )
        assert item.default_factory is MISSING, (
            f"{model.__name__}.{item.name}: unexpected default factory"
        )
        assert item.kw_only == (kind == _KEYWORD_ONLY)
    # Expected constructor parameters come only from the literal oracle above,
    # never from dataclasses.fields() or the observed signature.
    _assert_callable_contract(
        model.__init__,
        (("self", _POSITIONAL, _REQUIRED, _UNANNOTATED),)
        + tuple((name, kind, _REQUIRED, annotation) for name, annotation in expected),
        type(None),
    )
