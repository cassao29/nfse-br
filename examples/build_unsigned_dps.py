"""Build one synthetic unsigned DPS document for the repository quickstart."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one synthetic unsigned restricted DPS document."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New XML file to create; its parent directory must already exist.",
    )
    return parser.parse_args(argv)


def _synthetic_draft() -> RestrictedDpsDraft:
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
        application_version="nfse-br-quickstart",
        national_service_code="010101",
        service_description="Servico sintetico de demonstracao",
        service_amount=Decimal("1.00"),
        op_simp_nac="1",
        reg_esp_trib="0",
        trib_issqn="1",
        tp_ret_issqn="1",
        ind_tot_trib="0",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    document = build_unsigned_dps(_synthetic_draft())
    try:
        with args.output.open("xb") as output:
            output.write(document)
    except FileExistsError:
        print("Output file already exists.", file=sys.stderr)
        return 2
    except OSError:
        print("Could not create output file.", file=sys.stderr)
        return 2

    print("Unsigned synthetic DPS written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
