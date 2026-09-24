"""Demonstrate an offline round-trip using only fixed synthetic DPS data."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from nfse_br import __version__
from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries, parse_unsigned_dps
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps


def main() -> int:
    """Build, parse and rebuild one synthetic unsigned restricted DPS locally."""
    draft = RestrictedDpsDraft(
        issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
        issue_municipality=MunicipalityCode("2927408"),
        service_municipality=MunicipalityCode("3550308"),
        series=DpsSeries("123"),
        number=DpsNumber(42),
        issued_at=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=-3))),
        competence=CompetenceDate(date(2026, 9, 17)),
        application_version="nfse-br-demo",
        national_service_code="010101",
        service_description="Servico sintetico de demonstracao",
        service_amount=Decimal("100.00"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )
    xml = build_unsigned_dps(draft)
    parsed = parse_unsigned_dps(xml)
    rebuilt = build_unsigned_dps(parsed)
    if rebuilt != xml:
        raise RuntimeError("byte-exact DPS round-trip failed")
    # This synthetic timestamp uses a fixed UTC offset.
    if parsed != draft:
        raise RuntimeError("fixed-offset draft round-trip failed")

    print(f"nfse-br {__version__} - restricted DPS round-trip demo")
    print("Local demonstration; synthetic data only. No signing or transmission.")
    print("\nUNSIGNED DPS XML")
    print(xml.decode("utf-8"))
    print("\nRECOVERED FIELDS")
    print(f"issuer_tax_id: {parsed.issuer_tax_id.value}")
    print(f"issue_municipality: {parsed.issue_municipality.value}")
    print(f"service_municipality: {parsed.service_municipality.value}")
    print(f"series: {parsed.series.value}")
    print(f"number: {parsed.number.value}")
    print(f"issued_at: {parsed.issued_at.isoformat()}")
    print(f"competence: {parsed.competence.value.isoformat()}")
    print(f"application_version: {parsed.application_version}")
    print(f"service_code: {parsed.national_service_code}")
    print(f"service_amount: {parsed.service_amount}")
    print(f"service_description: {parsed.service_description}")
    print(f"op_simp_nac: {parsed.op_simp_nac}")
    print(f"reg_esp_trib: {parsed.reg_esp_trib}")
    print(f"trib_issqn: {parsed.trib_issqn}")
    print(f"tp_ret_issqn: {parsed.tp_ret_issqn}")
    print(f"ind_tot_trib: {parsed.ind_tot_trib}")
    print("\nROUND_TRIP = PASS")
    print("transmission_ready = false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
