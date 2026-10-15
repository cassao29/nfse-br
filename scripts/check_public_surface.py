"""Fail when a tracked file carries material that must stay private.

The repository is public. Certificates, keys, signed fiscal XML, real CPF or
CNPJ values and absolute home directories stay in ignored local evidence.
Findings name the file, line and rule only, never the matched value, because
CI logs are public too.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from nfse_br.domain import DomainValidationError, FederalTaxId
from nfse_br.domain.cnpj import validate_cnpj_check_digits
from nfse_br.domain.cpf import validate_cpf_check_digits

# Published examples. Check-digit vectors with seven or more leading zeros are
# accepted by rule.
SYNTHETIC_TAX_IDS = frozenset(
    {
        "01234567890",
        "11144477735",
        "12345678909",
        "11222333000181",
        "12ABC34501DE35",
    }
)
_VECTOR_PREFIX = "0" * 7

_FORBIDDEN_SUFFIX = re.compile(
    r"\.(?:pfx|p12|pem|key|cer|crt|der|p7b|p7c|jks|keystore)$", re.IGNORECASE
)
_ENV_FILE = re.compile(r"(?:^|/)\.env(?:\.(?!example$)[^/]+)?$")
_TEXT_RULES = (
    (
        "x509-certificate",
        re.compile(r"<(?:\w+:)?X509Certificate>\s*[A-Za-z0-9+/=\s]{40,}"),
    ),
    (
        "pem-block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*(?:CERTIFICATE|PRIVATE KEY)[A-Z ]*-----"),
    ),
    ("der-base64", re.compile(r"MII[A-Za-z0-9+/]{60,}")),
    (
        "home-path",
        re.compile(
            r"/home/(?!runner/)[a-z_][a-z0-9_-]*/"
            r"|/Users/[A-Za-z][^/\s]*/"
            r"|[A-Za-z]:\\Users\\(?!runneradmin\\)[^\\\s]+\\"
        ),
    ),
)
_DIGIT_RUN = re.compile(r"(?<![0-9A-Za-z])([0-9]{11}|[0-9]{14})(?![0-9A-Za-z])")
_FORMATTED_CPF = re.compile(
    r"(?<![0-9])([0-9]{3})\.([0-9]{3})\.([0-9]{3})-([0-9]{2})(?![0-9])"
)
_FORMATTED_CNPJ = re.compile(
    r"(?<![0-9A-Z])([0-9A-Z]{2})\.([0-9A-Z]{3})\.([0-9A-Z]{3})/([0-9A-Z]{4})"
    r"-([0-9]{2})(?![0-9])"
)
# DPS/NFS Id: municipality (7), registration kind (1: CPF, 2: CNPJ) and the
# registration padded to 14 characters.
_DOCUMENT_ID = re.compile(r"(?:DPS|NFS)[0-9]{7}([12])([0-9A-Z]{14})")


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule violation, located without its value."""

    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        """Return the location and rule only."""
        return f"{self.path}:{self.line}: {self.rule}"


def scan(root: Path, paths: Sequence[str]) -> list[Finding]:
    """Check each repository-relative path under ``root``."""
    findings: list[Finding] = []
    for path in paths:
        if _FORBIDDEN_SUFFIX.search(path) or _ENV_FILE.search(path):
            findings.append(Finding(path, 0, "forbidden-file"))
            continue
        if path == ".f0" or path.startswith(".f0/"):
            findings.append(Finding(path, 0, "local-evidence"))
            continue
        try:
            text = (root / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(Finding(path, 0, "non-text-file"))
            continue
        findings.extend(_scan_text(path, text))
    return findings


def _scan_text(path: str, text: str) -> Iterator[Finding]:
    for rule, pattern in _TEXT_RULES:
        for match in pattern.finditer(text):
            yield Finding(path, _line(text, match.start()), rule)
    for match in _DIGIT_RUN.finditer(text):
        value = match.group(1)
        if len(value) == 11 and _is_real(value, _valid_cpf):
            yield Finding(path, _line(text, match.start()), "cpf")
        elif len(value) == 14 and _is_real(value, _valid_cnpj):
            yield Finding(path, _line(text, match.start()), "cnpj")
    for match in _FORMATTED_CPF.finditer(text):
        if _is_real("".join(match.groups()), _valid_cpf):
            yield Finding(path, _line(text, match.start()), "cpf")
    for match in _FORMATTED_CNPJ.finditer(text):
        if _is_real("".join(match.groups()), _valid_cnpj):
            yield Finding(path, _line(text, match.start()), "cnpj")
    for match in _DOCUMENT_ID.finditer(text):
        kind, registration = match.groups()
        if kind == "1":
            real = registration[:3] == "000" and _is_real(registration[3:], _valid_cpf)
        else:
            real = _is_real(registration, _valid_cnpj)
        if real:
            yield Finding(path, _line(text, match.start()), "document-id")


def _is_real(value: str, valid: Callable[[str], bool]) -> bool:
    if value in SYNTHETIC_TAX_IDS or value.startswith(_VECTOR_PREFIX):
        return False
    return valid(value)


def _valid_cpf(value: str) -> bool:
    try:
        validate_cpf_check_digits(FederalTaxId.cpf(value))
    except DomainValidationError:
        return False
    return True


def _valid_cnpj(value: str) -> bool:
    try:
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
