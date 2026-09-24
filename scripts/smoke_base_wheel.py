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
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

assert importlib.util.find_spec("lxml") is None

import nfse_br
import nfse_br.cli
import nfse_br.domain
import nfse_br.domain.cnpj
import nfse_br.domain.cpf
import nfse_br.dps
import nfse_br.dps.builder
import nfse_br.nfse
import nfse_br._xmlsig.preflight
from nfse_br._xmlsig.preflight import (
    inspect_unsigned_dps as private_inspect_unsigned_dps,
)
from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    MunicipalityCode,
)
from nfse_br.domain.cnpj import validate_cnpj_check_digits
from nfse_br.domain.cpf import validate_cpf_check_digits
from nfse_br.dps import (
    DpsDocumentError,
    DpsIdentity,
    DpsNumber,
    DpsSeries,
    inspect_unsigned_dps,
    parse_unsigned_dps,
)
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps
from nfse_br.nfse import (
    NfseAccessKey,
    NfseConsistencyError,
    NfseDocumentInfo,
    NfseId,
    extract_nfse_document_info,
    validate_nfse_document_consistency,
)

for module in (
    nfse_br,
    nfse_br.cli,
    nfse_br.domain,
    nfse_br.domain.cnpj,
    nfse_br.domain.cpf,
    nfse_br.dps,
    nfse_br.dps.builder,
    nfse_br.nfse,
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

synthetic_access_key = "000000SYNTHETIC00000" + "0" * 30
access_key = NfseAccessKey(synthetic_access_key)
assert str(access_key) == synthetic_access_key
assert synthetic_access_key not in repr(access_key)
try:
    NfseAccessKey(synthetic_access_key[:-1] + "!")
except DomainValidationError:
    pass
else:
    raise AssertionError("Invalid NFS-e access key was unexpectedly accepted")

synthetic_nfse_id = "NFS" + "0" * 9 + "SYNTHETIC00000" + "0" * 27
nfse_id = NfseId(synthetic_nfse_id)
assert str(nfse_id) == synthetic_nfse_id
assert synthetic_nfse_id not in repr(nfse_id)
assert not hasattr(nfse_id, "access_key")
assert not hasattr(nfse_id, "to_access_key")
try:
    NfseId(synthetic_nfse_id[:-1] + "!")
except DomainValidationError:
    pass
else:
    raise AssertionError("Invalid NFS-e identifier was unexpectedly accepted")

synthetic_embedded_dps_id = (
    "DPS" + "2927408" + "2" + "SYNTHETIC00000" + "0" * 20
)
synthetic_nfse_xml = (
    '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">'
    f'<infNFSe Id="{synthetic_nfse_id}">'
    '<nNFSe>42</nNFSe>'
    f'<DPS><infDPS Id="{synthetic_embedded_dps_id}"/></DPS>'
    '</infNFSe>'
    '</NFSe>'
).encode()
document_info = extract_nfse_document_info(synthetic_nfse_xml)
assert type(document_info) is NfseDocumentInfo
assert type(document_info.nfse_id) is NfseId
assert document_info.nfse_id.value == synthetic_nfse_id
assert document_info.nfse_number == "42"
assert document_info.embedded_dps_id == synthetic_embedded_dps_id
assert not hasattr(document_info, "access_key")
for sensitive_value in (
    synthetic_nfse_id,
    document_info.nfse_number,
    synthetic_embedded_dps_id,
):
    assert sensitive_value not in repr(document_info)

synthetic_consistent_nfse_xml = (
    '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">'
    '<infNFSe Id="NFS29274082212ABC6780001Z0000000000004226090000000010">'
    '<nNFSe>42</nNFSe>'
    '<DPS><infDPS Id="DPS2927408212ABC6780001Z000123000000000000042">'
    '<tpEmit>1</tpEmit><cLocEmi>2927408</cLocEmi><serie>123</serie>'
    '<nDPS>42</nDPS><prest><CNPJ>12ABC6780001Z0</CNPJ></prest>'
    '</infDPS></DPS></infNFSe></NFSe>'
).encode()
assert validate_nfse_document_consistency(synthetic_consistent_nfse_xml) is None
try:
    validate_nfse_document_consistency(
        synthetic_consistent_nfse_xml.replace(b"<cLocEmi>2927408", b"<cLocEmi>3550308")
    )
except NfseConsistencyError as error:
    assert error.code == "embedded_dps_identity_mismatch"
else:
    raise AssertionError("Inconsistent embedded DPS was unexpectedly accepted")

validate_cnpj_check_digits(FederalTaxId.cnpj("12ABC34501DE35"))
try:
    validate_cnpj_check_digits(FederalTaxId.cnpj("12ABC6780001Z0"))
except DomainValidationError:
    pass
else:
    raise AssertionError("Invalid CNPJ check digits were unexpectedly accepted")

validate_cpf_check_digits(FederalTaxId.cpf("11144477735"))
try:
    validate_cpf_check_digits(FederalTaxId.cpf("12345678901"))
except DomainValidationError:
    pass
else:
    raise AssertionError("Invalid CPF check digits were unexpectedly accepted")

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
parsed = parse_unsigned_dps(xml)
assert type(parsed) is RestrictedDpsDraft
assert parsed == draft
assert build_unsigned_dps(parsed) == xml
root = ElementTree.fromstring(xml)
assert root.tag == "{http://www.sped.fazenda.gov.br/nfse}DPS"
namespace = "{http://www.sped.fazenda.gov.br/nfse}"
assert root.findtext(f"{namespace}infDPS/{namespace}nDPS") == "42"
public_identity = inspect_unsigned_dps(xml)
assert type(public_identity) is DpsIdentity
assert public_identity.value == root.find(f"{namespace}infDPS").get("Id")
assert private_inspect_unsigned_dps(xml) == public_identity.value
try:
    inspect_unsigned_dps(b"<DPS>")
except DpsDocumentError as error:
    assert error.code == "unsafe_or_malformed_xml"
else:
    raise AssertionError("Malformed DPS was unexpectedly accepted")

console = Path(sys.executable).with_name("nfse-br")
for command in (
    [str(console), "--help"],
    [str(console), "check-nfse", "--help"],
    [str(console), "--version"],
    [sys.executable, "-I", "-m", "nfse_br", "--help"],
    [sys.executable, "-I", "-m", "nfse_br", "check-nfse", "--help"],
    [sys.executable, "-I", "-m", "nfse_br", "--version"],
):
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed
    assert completed.stdout
    assert completed.stderr == ""

sensitive_document = "documento sigiloso á <CPF>.xml"
sensitive_bundle = "bundle sigiloso ç <TOKEN>.zip"
entry_points = (
    [str(console)],
    [sys.executable, "-I", "-m", "nfse_br"],
)
invalid_argument_cases = (
    ["subcomando-sigiloso"],
    ["check-unsigned"],
    ["check-unsigned", sensitive_document, "--bundle"],
    [
        "check-unsigned",
        sensitive_document,
        "--bundle",
        sensitive_bundle,
        "--opcao-sigilosa",
    ],
    [
        "check-unsigned",
        sensitive_document,
        "--bundle",
        sensitive_bundle,
        "argumento-excedente-sigiloso",
    ],
    ["check-nfse"],
    ["check-nfse", sensitive_document, "--bundle"],
    [
        "check-nfse",
        sensitive_document,
        "--bundle",
        sensitive_bundle,
        "--opcao-sigilosa",
    ],
    [
        "check-nfse",
        sensitive_document,
        "--bundle",
        sensitive_bundle,
        "argumento-excedente-sigiloso",
    ],
)
for entry_point in entry_points:
    for arguments in invalid_argument_cases:
        completed = subprocess.run(
            [*entry_point, *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2, completed
        assert completed.stderr == ""
        assert completed.stdout.count("\n") == 1
        assert json.loads(completed.stdout) == {
            "status": "error",
            "stage": "usage",
            "code": "invalid_arguments",
            "transmission_ready": False,
        }
        assert sensitive_document not in completed.stdout
        assert sensitive_bundle not in completed.stdout

bundle_path = Path("bundle.zip")
document_path = Path("document.xml")
bundle_path.write_bytes(b"bundle")
document_path.write_bytes(xml)
for command in (
    [
        str(console),
        "check-unsigned",
        str(document_path),
        "--bundle",
        str(bundle_path),
    ],
    [
        sys.executable,
        "-I",
        "-m",
        "nfse_br",
        "check-unsigned",
        str(document_path),
        "--bundle",
        str(bundle_path),
    ],
    [
        str(console),
        "check-nfse",
        str(document_path),
        "--bundle",
        str(bundle_path),
    ],
    [
        sys.executable,
        "-I",
        "-m",
        "nfse_br",
        "check-nfse",
        str(document_path),
        "--bundle",
        str(bundle_path),
    ],
):
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 2, completed
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "status": "error",
        "stage": "dependency",
        "code": "xsd_extra_missing",
        "transmission_ready": False,
    }

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
