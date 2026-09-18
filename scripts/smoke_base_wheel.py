"""Verify the built base wheel in a fresh environment without XSD dependencies."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

_EXPECTED_REQUIREMENT = "lxml==6.1.3; extra == 'xsd'"

_SMOKE_PROGRAM = r"""
import importlib.util
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

assert importlib.util.find_spec("lxml") is None

import nfse_br
import nfse_br.domain
import nfse_br.dps
import nfse_br.dps.builder
import nfse_br._xmlsig.preflight
from nfse_br._xmlsig.preflight import inspect_unsigned_dps
from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    MunicipalityCode,
)
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

for module in (
    nfse_br,
    nfse_br.domain,
    nfse_br.dps,
    nfse_br.dps.builder,
    nfse_br._xmlsig.preflight,
):
    module_path = Path(module.__file__).resolve()
    assert "site-packages" in module_path.parts, module_path

assert DpsNumber(1).identity_component == "000000000000001"
try:
    DpsNumber(0)
except DomainValidationError:
    pass
else:
    raise AssertionError("DpsNumber(0) was unexpectedly accepted")

draft = RestrictedDpsDraft(
    issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
    issue_municipality=MunicipalityCode("2927408"),
    service_municipality=MunicipalityCode("3550308"),
    series=DpsSeries("123"),
    number=DpsNumber(42),
    issued_at=datetime(
        2026, 9, 17, 12, 0, 0,
        tzinfo=timezone(timedelta(hours=-3)),
    ),
    competence=CompetenceDate(date(2026, 9, 17)),
    application_version="nfse-br-test",
    national_service_code="010101",
    service_description="Servico sintetico",
    service_amount=Decimal("1.00"),
    op_simp_nac="1",
    reg_esp_trib="0",
    trib_issqn="1",
    tp_ret_issqn="1",
    ind_tot_trib="0",
)
xml = build_unsigned_dps(draft)
root = ElementTree.fromstring(xml)
assert root.tag == "{http://www.sped.fazenda.gov.br/nfse}DPS"
namespace = "{http://www.sped.fazenda.gov.br/nfse}"
assert root.findtext(f"{namespace}infDPS/{namespace}nDPS") == "42"
assert inspect_unsigned_dps(xml) == root.find(f"{namespace}infDPS").get("Id")

try:
    import nfse_br.xsd
except ModuleNotFoundError as exc:
    assert "nfse-br[xsd]" in str(exc)
else:
    raise AssertionError("nfse_br.xsd imported without the optional extra")

assert importlib.util.find_spec("lxml") is None
print("Base wheel smoke test: PASS")
"""


def _inspect_metadata(wheel: Path) -> None:
    with ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        metadata = Parser().parsestr(
            archive.read(metadata_names[0]).decode("utf-8", errors="strict")
        )

    requirements = metadata.get_all("Requires-Dist", [])
    extras = metadata.get_all("Provides-Extra", [])
    if requirements != [_EXPECTED_REQUIREMENT]:
        raise ValueError("wheel runtime requirements do not match the XSD-only extra")
    if extras != ["xsd"]:
        raise ValueError("wheel must expose exactly the xsd extra")
    if any("types-lxml" in requirement.casefold() for requirement in requirements):
        raise ValueError("types-lxml must not appear in runtime metadata")


def _environment_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts/python.exe"
    return environment / "bin/python"


def smoke_base_wheel(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    _inspect_metadata(wheel)
    with tempfile.TemporaryDirectory(prefix="nfse-br-base-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = _environment_python(environment)
        clean_environment = os.environ.copy()
        clean_environment.pop("PYTHONHOME", None)
        clean_environment.pop("PYTHONPATH", None)
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            check=True,
            cwd=root,
            env=clean_environment,
        )
        subprocess.run(
            [str(python), "-I", "-c", _SMOKE_PROGRAM],
            check=True,
            cwd=root,
            env=clean_environment,
        )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        smoke_base_wheel(args.wheel)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        print(f"Base wheel smoke test failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
