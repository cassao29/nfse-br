"""Show the published national-taker API with fixed synthetic data, offline."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from nfse_br import __version__
from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries, inspect_unsigned_dps, parse_unsigned_dps
from nfse_br.dps.builder import (
    RestrictedDpsDraft,
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
    build_unsigned_dps,
)


def _report() -> str:
    # Fixed offset and Decimal inputs keep the example's round-trip unambiguous.
    base = RestrictedDpsDraft(
        issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        issue_municipality=MunicipalityCode("2927408"),
        service_municipality=MunicipalityCode("3550308"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
        issued_at=datetime(2026, 9, 17, 12, tzinfo=timezone(timedelta(hours=-3))),
        competence=CompetenceDate(date(2026, 9, 17)),
        application_version="nfse-br-demo-taker",
        national_service_code="010101",
        service_description="Servico sintetico de demonstracao",
        service_amount=Decimal("100.00"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )
    identity_without_taker = inspect_unsigned_dps(build_unsigned_dps(base))
    cases = (
        ("CPF", FederalTaxId.cpf("12345678901"), "Sala A"),
        ("CNPJ_NUMERIC", FederalTaxId.cnpj("12345678000199"), None),
        ("CNPJ_ALPHANUMERIC", FederalTaxId.cnpj("98ABC6780001Z0"), "Sala A"),
    )
    sections = [
        f"nfse-br {__version__} - national taker round-trip demo",
        "Local demonstration; synthetic data only. No signing or transmission.",
    ]
    for label, tax_id, complement in cases:
        address = RestrictedDpsNationalAddress(
            municipality=MunicipalityCode("3550308"),
            postal_code="01234567",
            street="Rua Sintetica",
            number="0",
            neighborhood="Centro",
            complement=complement,
        )
        taker = RestrictedDpsTaker(
            tax_id=tax_id, name="Tomador & Sintetico", address=address
        )
        draft = replace(base, taker=taker)
        xml = build_unsigned_dps(draft)
        recovered = parse_unsigned_dps(xml)
        if recovered.taker is None:
            raise RuntimeError("Missing recovered taker")
        # Equality includes all draft, identification and address fields.
        if recovered != draft:
            raise RuntimeError("Recovered fields differ")
        if build_unsigned_dps(recovered) != xml:
            raise RuntimeError("Byte-exact round-trip failed")
        if inspect_unsigned_dps(xml) != identity_without_taker:
            raise RuntimeError("Taker changed DPS identity")

        recovered_taker = recovered.taker
        recovered_address = recovered_taker.address
        # Explicit field access is intentional: aggregate repr/str are redacted.
        sections.extend(
            [
                f"\nCASE = {label}",
                "UNSIGNED DPS XML",
                xml.decode("utf-8"),
                "\nRECOVERED FIELDS",
                f"issuer_tax_id: {recovered.issuer_tax_id.value}",
                f"issue_municipality: {recovered.issue_municipality.value}",
                f"service_municipality: {recovered.service_municipality.value}",
                f"series: {recovered.series.value}",
                f"number: {recovered.number.value}",
                f"issued_at: {recovered.issued_at.isoformat()}",
                f"competence: {recovered.competence.value.isoformat()}",
                f"application_version: {recovered.application_version}",
                f"national_service_code: {recovered.national_service_code}",
                f"service_description: {recovered.service_description}",
                f"service_amount: {recovered.service_amount}",
                f"op_simp_nac: {recovered.op_simp_nac}",
                f"reg_esp_trib: {recovered.reg_esp_trib}",
                f"trib_issqn: {recovered.trib_issqn}",
                f"tp_ret_issqn: {recovered.tp_ret_issqn}",
                f"ind_tot_trib: {recovered.ind_tot_trib}",
                f"taker_tax_id: {recovered_taker.tax_id.value}",
                f"taker_name: {recovered_taker.name}",
                f"taker_municipality: {recovered_address.municipality.value}",
                f"taker_postal_code: {recovered_address.postal_code}",
                f"taker_street: {recovered_address.street}",
                f"taker_number: {recovered_address.number}",
                f"taker_neighborhood: {recovered_address.neighborhood}",
                f"taker_complement: {recovered_address.complement}",
            ]
        )
    sections.extend(
        [
            "\nROUND_TRIP = PASS (3 cases)",
            "TAKER_IDENTITY_PRESERVED = YES",
            "XML_UNSIGNED = YES",
            "XSD_VALIDATION_PERFORMED = NO",
            "FISCAL_AUTHORIZATION = NOT_PERFORMED",
            "TRANSMISSION_READY = NO",
        ]
    )
    return "\n".join(sections)


def main() -> int:
    """Check every case before printing any successful result or payload."""
    try:
        report = _report()
    except Exception:
        # Even unexpected library failures must not print payloads or chaining.
        print("National taker demo failed; no result reported.", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
