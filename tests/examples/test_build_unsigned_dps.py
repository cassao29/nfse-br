"""Tests for the executable unsigned-DPS quickstart."""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import pytest

from examples import build_unsigned_dps as quickstart
from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _PROJECT_ROOT / "examples/build_unsigned_dps.py"
_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_NS = {"n": _NAMESPACE}
_EXPECTED_ID = "DPS2927408212ABC6780001Z000123000000000000042"


def _expected_document() -> bytes:
    draft = RestrictedDpsDraft(
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
    return build_unsigned_dps(draft)


def test_import_has_no_file_system_side_effect(tmp_path: Path) -> None:
    program = (
        "import runpy; "
        f"runpy.run_path({_SCRIPT.as_posix()!r}, run_name='quickstart_import')"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_main_writes_exact_builder_bytes_and_expected_structure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "dps.xml"

    assert quickstart.main(["--output", str(output)]) == 0
    captured = capsys.readouterr()

    assert captured.out == "Unsigned synthetic DPS written.\n"
    assert captured.err == ""
    document = output.read_bytes()
    assert document == _expected_document()

    root = ElementTree.fromstring(document)
    assert root.tag == f"{{{_NAMESPACE}}}DPS"
    assert root.attrib == {"versao": "1.01"}
    information = root.find("n:infDPS", _NS)
    assert information is not None
    assert information.get("Id") == _EXPECTED_ID
    assert information.findtext("n:tpAmb", namespaces=_NS) == "2"
    assert information.findtext("n:dhEmi", namespaces=_NS) == (
        "2026-09-17T12:00:00-03:00"
    )
    assert information.findtext("n:verAplic", namespaces=_NS) == ("nfse-br-quickstart")
    assert information.findtext("n:prest/n:CNPJ", namespaces=_NS) == ("12ABC6780001Z0")
    assert information.findtext(
        "n:serv/n:locPrest/n:cLocPrestacao", namespaces=_NS
    ) == ("3550308")
    assert (
        information.findtext("n:valores/n:vServPrest/n:vServ", namespaces=_NS) == "1.00"
    )
    assert root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is None


def test_two_destinations_receive_identical_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"

    assert quickstart.main(["--output", str(first)]) == 0
    assert quickstart.main(["--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()


def test_existing_file_is_preserved(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "existing.xml"
    original = b"do not replace"
    output.write_bytes(original)

    assert quickstart.main(["--output", str(output)]) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == "Output file already exists.\n"
    assert output.read_bytes() == original


def test_missing_parent_is_a_controlled_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "missing" / "dps.xml"

    assert quickstart.main(["--output", str(output)]) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == "Could not create output file.\n"
    assert not output.exists()


def test_real_script_accepts_spaces_and_accents(tmp_path: Path) -> None:
    directory = tmp_path / "saida rápida com espaços"
    directory.mkdir()
    output = directory / "dps sintética.xml"

    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--output", str(output)],
        cwd=_PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "Unsigned synthetic DPS written.\n"
    assert completed.stderr == ""
    assert output.read_bytes() == _expected_document()


def test_generation_does_not_require_lxml(tmp_path: Path) -> None:
    output = tmp_path / "without-lxml.xml"
    program = (
        "import sys; "
        f"sys.path.insert(0, {_PROJECT_ROOT.as_posix()!r}); "
        "sys.modules['lxml'] = None; "
        "from examples import build_unsigned_dps as example; "
        f"raise SystemExit(example.main(['--output', {str(output)!r}]))"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=_PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "Unsigned synthetic DPS written.\n"
    assert completed.stderr == ""
    assert output.read_bytes() == _expected_document()
