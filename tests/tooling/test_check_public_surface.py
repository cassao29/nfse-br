"""Tests for the public-surface privacy check.

Samples are assembled at run time so this file does not trip the check.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import check_public_surface

_CPF = "529982" + "24725"
_CNPJ = "11444777" + "000161"
_CPF_FORMATTED = f"{_CPF[:3]}.{_CPF[3:6]}.{_CPF[6:9]}-{_CPF[9:]}"
_CNPJ_FORMATTED = f"{_CNPJ[:2]}.{_CNPJ[2:5]}.{_CNPJ[5:8]}/{_CNPJ[8:12]}-{_CNPJ[12:]}"
_BASE64 = "QUJD" * 20


def _rules(tmp_path: Path, name: str, text: str) -> list[str]:
    (tmp_path / name).write_text(text, encoding="utf-8")
    return [f.rule for f in check_public_surface.scan(tmp_path, [name])]


def test_clean_text_passes(tmp_path: Path) -> None:
    text = "\n".join(
        [
            "cpf 12345678909 and 123.456.789-09",
            "cnpj 11222333000181 and 12.ABC.345/01DE-35",
            "vectors 00000000191 00000000000191",
            "sha256 " + "1234567890" * 6 + "abcd",
            "size 12345678901234567",
            "DPS292740820001234567890000100000000000000001",
            "runner /home/runner/work, /Users/runner/work, C:\\Users\\runneradmin\\x",
            "url https://example.com/users/x and https://example.com/home/y",
            "<ds:X509Certificate></ds:X509Certificate>",
            "SHA256SUMS and AB000000000162",
        ]
    )
    assert _rules(tmp_path, "clean.md", text) == []


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (f"<X509Certificate>{_BASE64}</X509Certificate>", "x509-certificate"),
        (f"<ds:X509Certificate>\n{_BASE64}\n</ds:X509Certificate>", "x509-certificate"),
        (f'<X509Certificate Id="c"><![CDATA[{_BASE64}]]>', "x509-certificate"),
        (f"<ds:SignatureValue>{_BASE64}</ds:SignatureValue>", "xml-signature"),
        ("-----BEGIN CERTIFICATE" + "-----", "pem-block"),
        ("-----BEGIN RSA PRIVATE" + " KEY-----", "pem-block"),
        ("MII" + "A" * 60, "der-base64"),
        ("MHc" + "A" * 60, "der-base64"),
        ("QUJD-" + "QUJD" * 60, "long-base64"),
        ("/home" + "/alice/projects", "home-path"),
        ("cd /home" + "/Alice.Smith", "home-path"),
        ("/Users" + "/bob/x", "home-path"),
        ("/ro" + "ot/.ssh", "home-path"),
        ("C:\\" + "Users\\carol\\x", "home-path"),
        ("c:\\" + "users\\dave\\x", "home-path"),
        (f"cpf {_CPF}", "cpf"),
        (f"cpf {_CPF_FORMATTED}", "cpf"),
        (f"cnpj {_CNPJ}", "cnpj"),
        (f"cnpj {_CNPJ_FORMATTED}", "cnpj"),
        ("DPS2927408" + "2" + _CNPJ + "00001" + "0" * 15, "fiscal-identifier"),
        ("DPS2927408" + "1" + "000" + _CPF + "00001" + "0" * 15, "fiscal-identifier"),
        ("NFS2927408" + "1" + "2" + _CNPJ + "0" * 27, "fiscal-identifier"),
        ("key 2927408" + "1" + "1" + "000" + _CPF + "0" * 27, "fiscal-identifier"),
        ("key 29" + "2610" + _CNPJ + "65" + "002" + "0" * 19, "fiscal-identifier"),
        ("NFe29" + "2610" + _CNPJ + "55" + "002" + "0" * 19, "fiscal-identifier"),
    ],
)
def test_each_rule_detects(tmp_path: Path, text: str, rule: str) -> None:
    assert _rules(tmp_path, "sample.txt", text) == [rule]


def test_alphanumeric_cnpj_outside_the_examples_is_detected(tmp_path: Path) -> None:
    cnpj = next(
        value
        for value in (f"AB12CD340001{dv:02d}" for dv in range(100))
        if check_public_surface._is_real("cnpj", value)
    )
    formatted = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

    assert _rules(tmp_path, "a.txt", f"cnpj {formatted}") == ["cnpj"]
    assert _rules(tmp_path, "b.txt", f"cnpj {formatted.lower()}") == ["cnpj"]
    assert _rules(tmp_path, "c.txt", f"cnpj {cnpj}") == ["cnpj"]


def test_findings_report_location_without_value(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(f"ok\n\nid {_CPF}\n", encoding="utf-8")

    findings = check_public_surface.scan(tmp_path, ["a.md"])

    assert [str(f) for f in findings] == ["a.md:3: cpf"]
    assert _CPF not in str(findings[0])


@pytest.mark.parametrize(
    ("path", "rule"),
    [
        ("certs/CERT.PFX", "forbidden-file"),
        ("a.p12", "forbidden-file"),
        ("key.Pem", "forbidden-file"),
        ("x/signer.crt", "forbidden-file"),
        (".env", "forbidden-file"),
        ("sub/.env.local", "forbidden-file"),
        ("." + "netrc", "forbidden-file"),
        ("sub/." + "pypirc", "forbidden-file"),
        ("." + "envrc", "forbidden-file"),
        ("keys/signer.p8", "forbidden-file"),
        (".f0/prodrest/resp.raw", "local-evidence"),
        ("examples/.f0/x.xml", "local-evidence"),
    ],
)
def test_forbidden_paths_are_rejected_without_reading(path: str, rule: str) -> None:
    findings = check_public_surface.scan(Path("/nonexistent"), [path])

    assert [f.rule for f in findings] == [rule]


def test_env_example_and_binary_files(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x30\x82\xff\xfe")

    findings = check_public_surface.scan(tmp_path, [".env.example", "blob.bin"])

    assert [(f.path, f.rule) for f in findings] == [("blob.bin", "non-text-file")]


def test_identifier_in_path_is_found_and_masked(tmp_path: Path) -> None:
    path = f"fixtures/{_CPF}.xml"
    (tmp_path / "fixtures").mkdir()
    (tmp_path / path).write_text("clean\n", encoding="utf-8")

    findings = check_public_surface.scan(tmp_path, [path])

    assert [str(f) for f in findings] == ["fixtures/***.xml:0: cpf-in-path"]


def test_unreadable_tracked_file(tmp_path: Path) -> None:
    findings = check_public_surface.scan(tmp_path, ["missing.md"])

    assert [f.rule for f in findings] == ["unreadable-file"]


def test_main_scans_tracked_files_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "ok.md").write_text("clean\n", encoding="utf-8")
    (tmp_path / "untracked.md").write_text(f"{_CPF}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "ok.md"], check=True)

    assert check_public_surface.main([str(tmp_path)]) == 0
    assert "PASS" in capsys.readouterr().out

    (tmp_path / "leak.md").write_text(f"x\n{_CPF}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "leak.md"], check=True)

    assert check_public_surface.main([str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "leak.md:2: cpf" in err
    assert _CPF not in err


def test_repository_passes() -> None:
    root = Path(__file__).resolve().parents[2]

    assert check_public_surface.main([str(root)]) == 0
