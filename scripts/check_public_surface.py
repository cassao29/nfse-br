"""Fail when a tracked file carries material that must stay private.

The repository is public. Certificates, keys, signed fiscal XML, real CPF or
CNPJ values (alone or inside DPS Ids, NFS-e Ids and access keys) and absolute
home directories stay in ignored local evidence. The repository tracks text
only, so a binary file is a finding too.

Findings name the file, line and rule, never the matched value, because CI logs
are public. Long digit runs in a reported path are masked for the same reason.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from nfse_br.domain import DomainValidationError, FederalTaxId
from nfse_br.domain.cnpj import validate_cnpj_check_digits
from nfse_br.domain.cpf import validate_cpf_check_digits

# Published examples and the check-digit vectors of tests/domain.
SYNTHETIC_TAX_IDS = frozenset(
    {
        "01234567890",
        "11144477735",
        "12345678909",
        "00000000191",
        "00000000604",
        "00000001406",
        "00000001830",
        "00000001910",
        "11222333000181",
        "12ABC34501DE35",
        "AB000000000162",
        "00000000000191",
        "00000000000604",
        "00000000001406",
        "00000000001830",
        "00000000001910",
    }
)

_FORBIDDEN_SUFFIX = re.compile(
    r"\.(?:pfx|p12|pkcs12|pem|key|p8|pkcs8|cer|crt|der|p7b|p7c|p7s|jks|keystore)$",
    re.IGNORECASE,
)
_FORBIDDEN_NAME = re.compile(
    r"(?:^|/)(?:\.env(?:\.(?!example$)[^/]+)?|\.envrc|\.netrc|\.pypirc)$"
)
_LOCAL_EVIDENCE = re.compile(r"(?:^|/)\.f0(?:/|$)")
_BASE64_BODY = r"\s*(?:<!\[CDATA\[)?\s*[A-Za-z0-9+/=\s]{40,}"
_TEXT_RULES = (
    (
        "x509-certificate",
        re.compile(r"<(?:\w+:)?X509Certificate\b[^>]*>" + _BASE64_BODY),
    ),
    ("xml-signature", re.compile(r"<(?:\w+:)?SignatureValue\b[^>]*>" + _BASE64_BODY)),
    (
        "pem-block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*(?:CERTIFICATE|PRIVATE KEY)[A-Z ]*-----"),
    ),
    # DER SEQUENCE in base64: MI (long form), MH/MG (short form, e.g. EC keys).
    ("der-base64", re.compile(r"(?<![A-Za-z0-9+/])M[GHI][A-Za-z0-9+/]{60,}")),
    ("long-base64", re.compile(r"[A-Za-z0-9+/]{200,}")),
    # An absolute path starts the token: "example.com/users/x" is a URL path.
    (
        "home-path",
        re.compile(
            r"(?<![\w.:/~-])(?:/home|/Users)/(?!runner(?:/|\b))[^/\s\"'`<>()\[\]{}|,;]+"
            r"|(?<![\w.:/~-])/(?:root)/"
            r"|(?i:[a-z]:\\users\\)(?!(?:runneradmin|public|default)\\)[^\\\s\"'<>]+"
        ),
    ),
)
_BOUNDARY_BEFORE = r"(?<![0-9A-Za-z])"
_BOUNDARY_AFTER = r"(?![0-9A-Za-z])"
_DIGIT_RUN = re.compile(_BOUNDARY_BEFORE + r"([0-9]{11}|[0-9]{14})" + _BOUNDARY_AFTER)
# Alphanumeric CNPJ without punctuation: at least one letter in the base.
_PLAIN_ALNUM_CNPJ = re.compile(
    _BOUNDARY_BEFORE + r"((?=[0-9]*[A-Z])[0-9A-Z]{12}[0-9]{2})" + _BOUNDARY_AFTER
)
_FORMATTED_CPF = re.compile(
    r"(?<![0-9])([0-9]{3})\.([0-9]{3})\.([0-9]{3})-([0-9]{2})(?![0-9])"
)
_FORMATTED_CNPJ = re.compile(
    r"(?<![0-9A-Z])([0-9A-Z]{2})\.([0-9A-Z]{3})\.([0-9A-Z]{3})/([0-9A-Z]{4})"
    r"-([0-9]{2})(?![0-9])",
    re.IGNORECASE,
)
# Registrations embedded in fiscal identifiers, as (kind, registration):
# kind 1 is a CPF padded to 14 positions with "000", kind 2 a CNPJ.
# DPS Id: DPS + municipality (7) + kind (1) + registration (14) + 20 digits.
_DPS_ID = re.compile(r"DPS[0-9]{7}([12])([0-9A-Z]{14})[0-9]{20}")
# NFS-e access key (50), bare or after NFS: municipality (7) + environment (1)
# + kind (1) + registration (14) + 27 digits.
_NFSE_KEY = re.compile(
    r"(?:(?<=NFS)|"
    + _BOUNDARY_BEFORE
    + r")[0-9]{8}([12])([0-9A-Z]{14})[0-9]{27}"
    + _BOUNDARY_AFTER
)
# NF-e/NFC-e access key (44), bare or after NFe: UF (2) + year-month (4) +
# CNPJ, or CPF padded with "000" (14) + 24 digits.
_NFE_KEY = re.compile(
    r"(?:(?<=NFe)|"
    + _BOUNDARY_BEFORE
    + r")[0-9]{6}([0-9A-Z]{14})[0-9]{24}"
    + _BOUNDARY_AFTER
)
_PATH_TOKEN = re.compile(r"[0-9A-Z]{11,}")


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule violation, located without its value."""

    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        """Return the location and rule, with identifier-like path tokens masked."""
        shown = _PATH_TOKEN.sub(
            lambda m: (
                "***" if sum(c.isdigit() for c in m.group(0)) >= 8 else m.group(0)
            ),
            self.path,
        )
        return f"{shown}:{self.line}: {self.rule}"


def scan(root: Path, paths: Sequence[str]) -> list[Finding]:
    """Check each repository-relative path under ``root``."""
    findings: list[Finding] = []
    for path in paths:
        if _FORBIDDEN_SUFFIX.search(path) or _FORBIDDEN_NAME.search(path):
            findings.append(Finding(path, 0, "forbidden-file"))
            continue
        if _LOCAL_EVIDENCE.search(path):
            findings.append(Finding(path, 0, "local-evidence"))
            continue
        findings.extend(
            Finding(path, 0, f"{rule}-in-path") for rule in _tax_id_rules(path)
        )
        try:
            text = (root / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(Finding(path, 0, "non-text-file"))
            continue
        except OSError:
            findings.append(Finding(path, 0, "unreadable-file"))
            continue
        findings.extend(_scan_text(path, text))
    return findings


def _scan_text(path: str, text: str) -> Iterator[Finding]:
    for rule, pattern in _TEXT_RULES:
        for match in pattern.finditer(text):
            yield Finding(path, _line(text, match.start()), rule)
    for offset, rule in _tax_id_matches(text):
        yield Finding(path, _line(text, offset), rule)


def _tax_id_rules(text: str) -> list[str]:
    return sorted({rule for _, rule in _tax_id_matches(text)})


def _tax_id_matches(text: str) -> Iterator[tuple[int, str]]:
    for match in _DIGIT_RUN.finditer(text):
        value = match.group(1)
        kind = "cpf" if len(value) == 11 else "cnpj"
        if _is_real(kind, value):
            yield match.start(), kind
    for match in _PLAIN_ALNUM_CNPJ.finditer(text):
        if _is_real("cnpj", match.group(1)):
            yield match.start(), "cnpj"
    for match in _FORMATTED_CPF.finditer(text):
        if _is_real("cpf", "".join(match.groups())):
            yield match.start(), "cpf"
    for match in _FORMATTED_CNPJ.finditer(text):
        if _is_real("cnpj", "".join(match.groups()).upper()):
            yield match.start(), "cnpj"
    for pattern in (_DPS_ID, _NFSE_KEY):
        for match in pattern.finditer(text):
            kind, registration = match.groups()
            if _registration_is_real(kind == "1", registration):
                yield match.start(), "fiscal-identifier"
    for match in _NFE_KEY.finditer(text):
        registration = match.group(1)
        if _registration_is_real(False, registration) or _registration_is_real(
            True, registration
        ):
            yield match.start(), "fiscal-identifier"


def _registration_is_real(is_cpf: bool, registration: str) -> bool:
    if is_cpf:
        return registration[:3] == "000" and _is_real("cpf", registration[3:])
    return _is_real("cnpj", registration)


def _is_real(kind: str, value: str) -> bool:
    if value in SYNTHETIC_TAX_IDS:
        return False
    try:
        if kind == "cpf":
            validate_cpf_check_digits(FederalTaxId.cpf(value))
        else:
            validate_cnpj_check_digits(FederalTaxId.cnpj(value))
    except DomainValidationError:
        return False
    return True


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _tracked_files(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [path for path in output.split("\0") if path]


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: this checkout)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Scan the tracked files and report findings without values."""
    root = _parse_args(argv).root
    findings = scan(root, _tracked_files(root))
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        print(f"Public surface check: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print("Public surface check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
