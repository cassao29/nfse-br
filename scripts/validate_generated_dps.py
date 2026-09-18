"""Build unsigned synthetic DPS documents and validate them with the frozen ZIP."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps
from nfse_br.xsd import RestrictedDpsXsdValidator, XsdValidationError


class GeneratedMutationError(ValueError):
    """Raised when a generated fixture cannot be mutated unambiguously."""


def _base_draft() -> RestrictedDpsDraft:
    return RestrictedDpsDraft(
        issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        issue_municipality=MunicipalityCode("2927408"),
        service_municipality=MunicipalityCode("3550308"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
        issued_at=datetime(
            2026,
            9,
            17,
            12,
            0,
            0,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        competence=CompetenceDate(date(2026, 9, 17)),
        application_version="nfse-br-test",
        national_service_code="010101",
        service_description='Servico sintetico com acao & <teste> "local"',
        service_amount=Decimal("1.23"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )


def _valid_drafts() -> tuple[tuple[str, RestrictedDpsDraft], ...]:
    base = _base_draft()
    return (
        ("alphanumeric CNPJ and cents", base),
        (
            "numeric CNPJ, leading-zero series, and zero",
            replace(
                base,
                issuer_tax_id=FederalTaxId.cnpj("12345678000190"),
                series=DpsSeries("00123"),
                number=DpsNumber(1),
                service_amount=Decimal("0"),
                issued_at=datetime(2000, 2, 29, tzinfo=UTC),
                competence=CompetenceDate(date(2000, 2, 29)),
            ),
        ),
        (
            "maximum amount and positive offset",
            replace(
                base,
                number=DpsNumber(999_999_999_999_999),
                service_amount=Decimal("999999999999999.99"),
                issued_at=datetime(
                    2099,
                    12,
                    31,
                    23,
                    59,
                    59,
                    tzinfo=timezone(timedelta(hours=12)),
                ),
                competence=CompetenceDate(date(2099, 12, 31)),
            ),
        ),
        ("non-breaking-space description", replace(base, service_description="\u00a0")),
        ("opSimpNac 2", replace(base, op_simp_nac="2")),
        ("opSimpNac 3", replace(base, op_simp_nac="3")),
        ("regEspTrib 1", replace(base, reg_esp_trib="1")),
        ("regEspTrib 2", replace(base, reg_esp_trib="2")),
        ("regEspTrib 3", replace(base, reg_esp_trib="3")),
        ("regEspTrib 4", replace(base, reg_esp_trib="4")),
        ("regEspTrib 5", replace(base, reg_esp_trib="5")),
        ("regEspTrib 6", replace(base, reg_esp_trib="6")),
        ("regEspTrib 9", replace(base, reg_esp_trib="9")),
        ("tribISSQN 2", replace(base, trib_issqn="2")),
        ("tribISSQN 3", replace(base, trib_issqn="3")),
        ("tribISSQN 4", replace(base, trib_issqn="4")),
        ("tpRetISSQN 2", replace(base, tp_ret_issqn="2")),
        ("tpRetISSQN 3", replace(base, tp_ret_issqn="3")),
    )


def _replace_once(source: bytes, target: bytes, replacement: bytes) -> bytes:
    count = source.count(target)
    if count != 1:
        raise GeneratedMutationError(
            f"generated mutation expected one target, observed {count}"
        )
    mutated = source.replace(target, replacement, 1)
    if mutated == source:
        raise GeneratedMutationError("generated mutation made no change")
    return mutated


def _invalid_documents(valid: bytes) -> tuple[tuple[str, bytes], ...]:
    return (
        (
            "nDPS zero",
            _replace_once(valid, b"<nDPS>42</nDPS>", b"<nDPS>0</nDPS>"),
        ),
        (
            "required field removed",
            _replace_once(valid, b"<tpAmb>2</tpAmb>", b""),
        ),
        (
            "field order changed",
            _replace_once(
                valid,
                b"<serie>123</serie><nDPS>42</nDPS>",
                b"<nDPS>42</nDPS><serie>123</serie>",
            ),
        ),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Frozen restricted XSD ZIP")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run explicit local builder-to-validator integration without network I/O."""
    args = _parse_args(argv)
    try:
        bundle = args.bundle.read_bytes()
    except OSError:
        print("Generated DPS integration: bundle could not be read.")
        return 2

    try:
        validator = RestrictedDpsXsdValidator(bundle)
        documents: list[tuple[str, bytes]] = []
        for label, draft in _valid_drafts():
            document = build_unsigned_dps(draft)
            validator.validate(document)
            documents.append((label, document))

        base = documents[0][1]
        invalid_documents = _invalid_documents(base)
        for label, document in invalid_documents:
            validator.validate(base)
            try:
                validator.validate(document)
            except XsdValidationError as exc:
                if exc.phase != "schema" or exc.code != "document_invalid":
                    raise
            else:
                print(f"Generated DPS integration: {label} was accepted.")
                return 1
        validator.validate(base)
    except GeneratedMutationError:
        print("Generated DPS integration: mutation preparation failed.")
        return 2
    except XsdValidationError as exc:
        print(f"Generated DPS integration: {exc}")
        return 1

    for label, _document in documents:
        print(f"Generated valid case {label}: PASS")
    for label, _document in invalid_documents:
        print(f"Generated negative case {label}: REJECTED")
    print("Generated sequential valid-invalid-valid state: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
