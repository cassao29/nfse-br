"""Independent offline checks for the synthetic public-API taker example."""

from __future__ import annotations

import ast
import builtins
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import pytest

from examples import demo_national_taker as demo
from nfse_br.dps import DpsNumber, inspect_unsigned_dps, parse_unsigned_dps
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

_SCRIPT = Path(__file__).resolve().parents[2] / "examples/demo_national_taker.py"
_FAILURE = "National taker demo failed; no result reported.\n"
# Literal XML oracle: no output of the demo/builder is used to construct it.
_BEFORE_TAKER = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<DPS xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">'
    '<infDPS Id="DPS2927408212ABC6780001Z000123000000000000042">'
    "<tpAmb>2</tpAmb><dhEmi>2026-09-17T12:00:00-03:00</dhEmi>"
    "<verAplic>nfse-br-demo-taker</verAplic><serie>123</serie><nDPS>42</nDPS>"
    "<dCompet>2026-09-17</dCompet><tpEmit>1</tpEmit><cLocEmi>2927408</cLocEmi>"
    "<prest><CNPJ>12ABC6780001Z0</CNPJ><regTrib><opSimpNac>1</opSimpNac>"
    "<regEspTrib>0</regEspTrib></regTrib></prest>"
)
_AFTER_TAKER = (
    "<serv><locPrest><cLocPrestacao>3550308</cLocPrestacao></locPrest><cServ>"
    "<cTribNac>010101</cTribNac>"
    "<xDescServ>Servico sintetico de demonstracao</xDescServ></cServ></serv>"
    "<valores><vServPrest><vServ>100.00</vServ></vServPrest><trib><tribMun>"
    "<tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun><totTrib>"
    "<indTotTrib>0</indTotTrib></totTrib></trib></valores></infDPS></DPS>"
)
_ADDRESS_START = (
    "<end><endNac><cMun>3550308</cMun><CEP>01234567</CEP></endNac>"
    "<xLgr>Rua Sintetica</xLgr><nro>0</nro>"
)
_EXPECTED_CASES = (
    ("CPF", "CPF", "12345678901", "Sala A"),
    ("CNPJ_NUMERIC", "CNPJ", "12345678000199", None),
    ("CNPJ_ALPHANUMERIC", "CNPJ", "98ABC6780001Z0", "Sala A"),
)


def test_three_cases_match_independent_xml_and_recovered_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert demo.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    cases = captured.out.split("\nCASE = ")[1:]
    assert len(cases) == 3
    identities = []
    for block, (label, kind, identifier, complement) in zip(
        cases, _EXPECTED_CASES, strict=True
    ):
        assert block.startswith(label + "\nUNSIGNED DPS XML\n")
        xml = block.split("UNSIGNED DPS XML\n", 1)[1].split(
            "\n\nRECOVERED FIELDS\n", 1
        )[0]
        complement_xml = "<xCpl>Sala A</xCpl>" if complement else ""
        expected_xml = (
            _BEFORE_TAKER
            + f"<toma><{kind}>{identifier}</{kind}>"
            + "<xNome>Tomador &amp; Sintetico</xNome>"
            + _ADDRESS_START
            + complement_xml
            + "<xBairro>Centro</xBairro></end></toma>"
            + _AFTER_TAKER
        )
        assert xml == expected_xml
        expected_fields = {
            "issuer_tax_id": "12ABC6780001Z0",
            "issue_municipality": "2927408",
            "service_municipality": "3550308",
            "series": "123",
            "number": "42",
            "issued_at": "2026-09-17T12:00:00-03:00",
            "competence": "2026-09-17",
            "application_version": "nfse-br-demo-taker",
            "national_service_code": "010101",
            "service_description": "Servico sintetico de demonstracao",
            "service_amount": "100.00",
            "op_simp_nac": "1",
            "reg_esp_trib": "0",
            "trib_issqn": "1",
            "tp_ret_issqn": "1",
            "ind_tot_trib": "0",
            "taker_tax_id": identifier,
            "taker_name": "Tomador & Sintetico",
            "taker_municipality": "3550308",
            "taker_postal_code": "01234567",
            "taker_street": "Rua Sintetica",
            "taker_number": "0",
            "taker_neighborhood": "Centro",
            "taker_complement": str(complement),
        }
        fields = block.split("RECOVERED FIELDS\n", 1)[1].split("\n\n", 1)[0]
        assert dict(line.split(": ", 1) for line in fields.strip().splitlines()) == (
            expected_fields
        )
        parsed = parse_unsigned_dps(xml.encode())
        assert parsed.taker is not None
        assert parsed.taker.tax_id.value == identifier
        assert parsed.taker.name == "Tomador & Sintetico"
        assert parsed.taker.address.complement == complement
        assert build_unsigned_dps(parsed) == xml.encode()
        identities.append(inspect_unsigned_dps(xml.encode()).value)
    assert identities == ["DPS2927408212ABC6780001Z000123000000000000042"] * 3
    assert captured.out.endswith(
        "ROUND_TRIP = PASS (3 cases)\n"
        "TAKER_IDENTITY_PRESERVED = YES\n"
        "XML_UNSIGNED = YES\n"
        "XSD_VALIDATION_PERFORMED = NO\n"
        "FISCAL_AUTHORIZATION = NOT_PERFORMED\n"
        "TRANSMISSION_READY = NO\n"
    )
    assert "synthetic data only" in captured.out
    assert "RestrictedDpsTaker(" not in captured.out
    assert "RestrictedDpsDraft(" not in captured.out


@pytest.mark.parametrize("failure", ["missing", "fields", "rebuild", "identity"])
def test_checks_fail_closed_even_on_last_case(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def parse(xml: bytes) -> RestrictedDpsDraft:
        nonlocal calls
        calls += 1
        parsed = parse_unsigned_dps(xml)
        if calls == 3:
            if failure == "missing":
                return replace(parsed, taker=None)
            return replace(parsed, number=DpsNumber(43))
        return parsed

    def build(draft: RestrictedDpsDraft) -> bytes:
        nonlocal calls
        calls += 1
        return b"different bytes" if calls == 7 else build_unsigned_dps(draft)

    def inspect(xml: bytes) -> object:
        nonlocal calls
        calls += 1
        return None if calls == 4 else inspect_unsigned_dps(xml)

    if failure in ("missing", "fields"):
        monkeypatch.setattr(demo, "parse_unsigned_dps", parse)
    elif failure == "rebuild":
        monkeypatch.setattr(demo, "build_unsigned_dps", build)
    else:
        monkeypatch.setattr(demo, "inspect_unsigned_dps", inspect)
    assert demo.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # No earlier case or success escapes the buffer.
    assert captured.err == _FAILURE


def test_exceptions_and_chains_do_not_expose_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_xml: bytes) -> NoReturn:
        try:
            raise ValueError("12345678901 Tomador & Sintetico Rua Sintetica")
        except ValueError as cause:
            raise RuntimeError("<DPS>synthetic private payload</DPS>") from cause

    monkeypatch.setattr(demo, "parse_unsigned_dps", fail)
    assert demo.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == _FAILURE


def test_no_data_files_or_network_and_deterministic_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def denied(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Unexpected I/O")

    with monkeypatch.context() as isolated:
        isolated.setattr(builtins, "open", denied)
        isolated.setattr(Path, "open", denied)
        isolated.setattr(socket, "socket", denied)
        isolated.setattr(socket, "getaddrinfo", denied)
        assert demo.main() == 0
        first = capsys.readouterr()
        assert demo.main() == 0
        assert capsys.readouterr() == first


def test_only_public_package_imports_and_no_assert_validation() -> None:
    module = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(module))
    modules = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("nfse_br")
    }
    assert modules == {
        "nfse_br",
        "nfse_br.domain",
        "nfse_br.dps",
        "nfse_br.dps.builder",
    }


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_isolated_entrypoint_and_failures_under_optimization(
    tmp_path: Path, optimized: bool, failure: bool
) -> None:
    program = (
        "import runpy, sys\n"
        "sys.modules['lxml'] = None\n"
        "def deny_network(event, args):\n"
        "    if event.startswith('socket.'):\n"
        "        raise RuntimeError('Unexpected network access')\n"
        "sys.addaudithook(deny_network)\n"
    )
    if failure:
        program += (
            f"ns = runpy.run_path({_SCRIPT.as_posix()!r})\n"
            "def fail(xml):\n"
            "    raise RuntimeError('PRIVATE-PAYLOAD-12345678901')\n"
            "ns['main'].__globals__['parse_unsigned_dps'] = fail\n"
            "raise SystemExit(ns['main']())\n"
        )
    else:
        program += f"runpy.run_path({_SCRIPT.as_posix()!r}, run_name='__main__')\n"
    command = [sys.executable, "-I"]
    if optimized:
        command.append("-O")
    result = subprocess.run(
        [*command, "-c", program],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if failure:
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == _FAILURE
    else:
        assert result.returncode == 0
        assert result.stderr == ""
        assert "ROUND_TRIP = PASS (3 cases)" in result.stdout
        assert "TRANSMISSION_READY = NO" in result.stdout
    assert list(tmp_path.iterdir()) == []
