"""Offline tests of the public, synthetic DPS round-trip demonstration."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from examples import demo_round_trip as demo
from nfse_br.dps import parse_unsigned_dps
from nfse_br.dps.builder import build_unsigned_dps

_SCRIPT = Path(__file__).resolve().parents[2] / "examples/demo_round_trip.py"


def test_main_prints_real_xml_recovered_fields_and_round_trip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert demo.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    output = captured.out
    xml = (
        output.split("UNSIGNED DPS XML\n", 1)[1]
        .split("\n\nRECOVERED FIELDS\n", 1)[0]
        .encode("utf-8")
    )
    parsed = parse_unsigned_dps(xml)
    assert build_unsigned_dps(parsed) == xml
    expected = {
        "issuer_tax_id": "12ABC6780001Z0",
        "issue_municipality": "2927408",
        "service_municipality": "3550308",
        "series": "123",
        "number": "42",
        "issued_at": "2026-09-17T12:00:00-03:00",
        "competence": "2026-09-17",
        "application_version": "nfse-br-demo",
        "service_code": "010101",
        "service_amount": "100.00",
        "service_description": "Servico sintetico de demonstracao",
        "op_simp_nac": "1",
        "reg_esp_trib": "0",
        "trib_issqn": "1",
        "tp_ret_issqn": "1",
        "ind_tot_trib": "0",
    }
    fields = output.split("RECOVERED FIELDS\n", 1)[1].split("\n\n", 1)[0]
    assert dict(line.split(": ", 1) for line in fields.splitlines()) == expected
    assert parsed.issuer_tax_id.value == expected["issuer_tax_id"]
    assert parsed.service_description == expected["service_description"]
    assert str(parsed.service_amount) == expected["service_amount"]
    assert "ROUND_TRIP = PASS\ntransmission_ready = false\n" in output
    assert "synthetic data only" in output
    for forbidden in ("authorized", "transmitted", "signed successfully"):
        assert forbidden not in output.lower()
    assert "RestrictedDpsDraft(" not in output


def test_output_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    assert demo.main() == 0
    first = capsys.readouterr()
    assert demo.main() == 0
    assert capsys.readouterr() == first


def test_main_does_not_depend_on_assert_statements() -> None:
    module = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    main = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(main))


@pytest.mark.parametrize(
    ("execute", "optimized"),
    [(False, False), (True, False), (True, True)],
    ids=["import", "entrypoint", "optimized-entrypoint"],
)
def test_script_without_lxml_network_or_file_output(
    tmp_path: Path, execute: bool, optimized: bool
) -> None:
    program = (
        "import runpy, sys\n"
        "sys.modules['lxml'] = None\n"
        "def deny_network(event, args):\n"
        "    if event.startswith('socket.'):\n"
        "        raise RuntimeError('Unexpected network access')\n"
        "sys.addaudithook(deny_network)\n"
        f"runpy.run_path({_SCRIPT.as_posix()!r}, "
        f"run_name={'__main__' if execute else 'demo_import'!r})"
    )
    command = [sys.executable, "-I"]
    if optimized:
        command.append("-O")
    completed = subprocess.run(
        [*command, "-c", program],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    if execute:
        assert "ROUND_TRIP = PASS" in completed.stdout
        assert "transmission_ready = false" in completed.stdout
    else:
        assert completed.stdout == ""
    assert list(tmp_path.iterdir()) == []
