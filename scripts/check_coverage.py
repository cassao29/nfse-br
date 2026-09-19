"""Enforce exact project-specific coverage gates from Coverage.py JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NoReturn, cast

GLOBAL_COMBINED_MINIMUM = 80
F0_BRANCH_MINIMUM = 90
SCHEMA_BRANCH_MINIMUM = 90
XSD_BRANCH_MINIMUM = 90
BUILDER_BRANCH_MINIMUM = 90
XMLSIG_PREFLIGHT_BRANCH_MINIMUM = 90
CLI_BRANCH_MINIMUM = 90
CNPJ_BRANCH_MINIMUM = 90
CPF_BRANCH_MINIMUM = 90

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_F0_ROOT = _PROJECT_ROOT / "src/nfse_br/_f0"
_XSD_ROOT = _PROJECT_ROOT / "src/nfse_br/xsd"
_SCHEMA_MODULE = "src/nfse_br/_f0/dps_schema_contract.py"
_XSD_VALIDATOR_MODULE = "src/nfse_br/xsd/validator.py"
_DPS_BUILDER_MODULE = "src/nfse_br/dps/builder.py"
_XMLSIG_PREFLIGHT_MODULE = "src/nfse_br/_xmlsig/preflight.py"
_CLI_MODULE = "src/nfse_br/cli.py"
_CNPJ_MODULE = "src/nfse_br/domain/cnpj.py"
_CPF_MODULE = "src/nfse_br/domain/cpf.py"


class CoverageGateError(ValueError):
    """Raised when a coverage report cannot safely support the gates."""


@dataclass(frozen=True, slots=True)
class GateResult:
    """One exact coverage gate result."""

    scope: str
    covered: int
    total: int
    minimum: int

    @property
    def passed(self) -> bool:
        """Return whether the exact integer comparison satisfies the gate."""
        return self.covered * 100 >= self.minimum * self.total

    @property
    def percentage(self) -> float:
        """Return a display-only percentage."""
        return self.covered * 100 / self.total


def evaluate_report(
    report: Mapping[str, object],
    *,
    expected_f0_paths: frozenset[str],
    expected_xsd_paths: frozenset[str],
    expected_builder_paths: frozenset[str],
    expected_xmlsig_paths: frozenset[str],
    expected_cli_paths: frozenset[str],
    expected_cnpj_paths: frozenset[str],
    expected_cpf_paths: frozenset[str],
) -> tuple[
    GateResult,
    GateResult,
    GateResult,
    GateResult,
    GateResult,
    GateResult,
    GateResult,
    GateResult,
    GateResult,
]:
    """Validate a Coverage.py report and calculate the nine required gates."""
    if _XSD_VALIDATOR_MODULE not in expected_xsd_paths:
        raise CoverageGateError(
            f"XSD scope is missing required module {_XSD_VALIDATOR_MODULE!r}"
        )
    if _DPS_BUILDER_MODULE not in expected_builder_paths:
        raise CoverageGateError(
            f"DPS builder scope is missing required module {_DPS_BUILDER_MODULE!r}"
        )
    if _XMLSIG_PREFLIGHT_MODULE not in expected_xmlsig_paths:
        raise CoverageGateError(
            "XML signature preflight scope is missing required module "
            f"{_XMLSIG_PREFLIGHT_MODULE!r}"
        )
    if _CLI_MODULE not in expected_cli_paths:
        raise CoverageGateError(f"CLI scope is missing required module {_CLI_MODULE!r}")
    if _CNPJ_MODULE not in expected_cnpj_paths:
        raise CoverageGateError(
            f"CNPJ scope is missing required module {_CNPJ_MODULE!r}"
        )
    if _CPF_MODULE not in expected_cpf_paths:
        raise CoverageGateError(f"CPF scope is missing required module {_CPF_MODULE!r}")
    meta = _mapping(report.get("meta"), context="meta")
    if meta.get("branch_coverage") is not True:
        raise CoverageGateError("branch measurement is not enabled")

    totals = _mapping(report.get("totals"), context="totals")
    global_lines = _counts(totals, context="global", unit="lines")
    global_branches = _counts(totals, context="global", unit="branches")

    raw_files = _mapping(report.get("files"), context="files")
    files: dict[str, Mapping[str, object]] = {}
    for raw_path, raw_file in raw_files.items():
        normalized = _normalize_path(raw_path)
        if normalized in files:
            raise CoverageGateError(
                f"duplicate file path after normalization: {normalized!r}"
            )
        files[normalized] = _mapping(raw_file, context=f"file {normalized!r}")

    missing_f0 = expected_f0_paths - files.keys()
    if missing_f0:
        raise CoverageGateError(
            f"coverage report is missing F0 files: {sorted(missing_f0)!r}"
        )
    missing_xsd = expected_xsd_paths - files.keys()
    if missing_xsd:
        raise CoverageGateError(
            f"coverage report is missing XSD files: {sorted(missing_xsd)!r}"
        )
    missing_builder = expected_builder_paths - files.keys()
    if missing_builder:
        raise CoverageGateError(
            f"coverage report is missing DPS builder files: {sorted(missing_builder)!r}"
        )
    missing_xmlsig = expected_xmlsig_paths - files.keys()
    if missing_xmlsig:
        raise CoverageGateError(
            "coverage report is missing XML signature preflight files: "
            f"{sorted(missing_xmlsig)!r}"
        )
    missing_cli = expected_cli_paths - files.keys()
    if missing_cli:
        raise CoverageGateError(
            f"coverage report is missing CLI files: {sorted(missing_cli)!r}"
        )
    missing_cnpj = expected_cnpj_paths - files.keys()
    if missing_cnpj:
        raise CoverageGateError(
            f"coverage report is missing CNPJ files: {sorted(missing_cnpj)!r}"
        )
    missing_cpf = expected_cpf_paths - files.keys()
    if missing_cpf:
        raise CoverageGateError(
            f"coverage report is missing CPF files: {sorted(missing_cpf)!r}"
        )

    f0_covered = 0
    f0_total = 0
    for path, file_data in files.items():
        if not path.startswith("src/nfse_br/_f0/"):
            continue
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        f0_covered += covered
        f0_total += total

    schema_file = files.get(_SCHEMA_MODULE)
    if schema_file is None:
        raise CoverageGateError(f"coverage report is missing {_SCHEMA_MODULE!r}")
    schema_summary = _mapping(
        schema_file.get("summary"),
        context=f"summary for {_SCHEMA_MODULE!r}",
    )
    schema_covered, schema_total = _counts(
        schema_summary,
        context=_SCHEMA_MODULE,
        unit="branches",
    )

    xsd_covered = 0
    xsd_total = 0
    for path in expected_xsd_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        xsd_covered += covered
        xsd_total += total

    builder_covered = 0
    builder_total = 0
    for path in expected_builder_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        builder_covered += covered
        builder_total += total

    xmlsig_covered = 0
    xmlsig_total = 0
    for path in expected_xmlsig_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        xmlsig_covered += covered
        xmlsig_total += total

    cli_covered = 0
    cli_total = 0
    for path in expected_cli_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        cli_covered += covered
        cli_total += total

    cnpj_covered = 0
    cnpj_total = 0
    for path in expected_cnpj_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        cnpj_covered += covered
        cnpj_total += total

    cpf_covered = 0
    cpf_total = 0
    for path in expected_cpf_paths:
        file_data = files[path]
        summary = _mapping(file_data.get("summary"), context=f"summary for {path!r}")
        covered, total = _counts(summary, context=path, unit="branches")
        cpf_covered += covered
        cpf_total += total

    return (
        _gate(
            "Library combined",
            covered=global_lines[0] + global_branches[0],
            total=global_lines[1] + global_branches[1],
            minimum=GLOBAL_COMBINED_MINIMUM,
        ),
        _gate(
            "F0 branches",
            covered=f0_covered,
            total=f0_total,
            minimum=F0_BRANCH_MINIMUM,
        ),
        _gate(
            "DPS schema branches",
            covered=schema_covered,
            total=schema_total,
            minimum=SCHEMA_BRANCH_MINIMUM,
        ),
        _gate(
            "XSD validator branches",
            covered=xsd_covered,
            total=xsd_total,
            minimum=XSD_BRANCH_MINIMUM,
        ),
        _gate(
            "DPS builder branches",
            covered=builder_covered,
            total=builder_total,
            minimum=BUILDER_BRANCH_MINIMUM,
        ),
        _gate(
            "XML signature preflight branches",
            covered=xmlsig_covered,
            total=xmlsig_total,
            minimum=XMLSIG_PREFLIGHT_BRANCH_MINIMUM,
        ),
        _gate(
            "CLI branches",
            covered=cli_covered,
            total=cli_total,
            minimum=CLI_BRANCH_MINIMUM,
        ),
        _gate(
            "CNPJ check-digit branches",
            covered=cnpj_covered,
            total=cnpj_total,
            minimum=CNPJ_BRANCH_MINIMUM,
        ),
        _gate(
            "CPF check-digit branches",
            covered=cpf_covered,
            total=cpf_total,
            minimum=CPF_BRANCH_MINIMUM,
        ),
    )


def load_report(path: Path) -> Mapping[str, object]:
    """Load a strict JSON object from disk."""
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CoverageGateError(f"could not read coverage report: {path}") from exc
    try:
        value = json.loads(data, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise CoverageGateError(f"invalid coverage JSON: {path}") from exc
    return _mapping(value, context="coverage report")


def expected_f0_paths() -> frozenset[str]:
    """Return every Python source file currently belonging to the F0 package."""
    return frozenset(
        path.relative_to(_PROJECT_ROOT).as_posix()
        for path in _F0_ROOT.rglob("*.py")
        if path.is_file()
    )


def expected_xsd_paths() -> frozenset[str]:
    """Return every Python source file in the optional XSD package."""
    paths = frozenset(
        path.relative_to(_PROJECT_ROOT).as_posix()
        for path in _XSD_ROOT.rglob("*.py")
        if path.is_file()
    )
    if _XSD_VALIDATOR_MODULE not in paths:
        raise CoverageGateError(
            f"XSD source tree is missing required module {_XSD_VALIDATOR_MODULE!r}"
        )
    return paths


def expected_builder_paths() -> frozenset[str]:
    """Return the explicitly gated DPS builder source module."""
    path = _PROJECT_ROOT / _DPS_BUILDER_MODULE
    if not path.is_file():
        raise CoverageGateError(
            f"DPS source tree is missing required module {_DPS_BUILDER_MODULE!r}"
        )
    return frozenset({_DPS_BUILDER_MODULE})


def expected_xmlsig_paths() -> frozenset[str]:
    """Return the explicitly gated XML signature preflight module."""
    path = _PROJECT_ROOT / _XMLSIG_PREFLIGHT_MODULE
    if not path.is_file():
        raise CoverageGateError(
            "XML signature source tree is missing required module "
            f"{_XMLSIG_PREFLIGHT_MODULE!r}"
        )
    return frozenset({_XMLSIG_PREFLIGHT_MODULE})


def expected_cli_paths() -> frozenset[str]:
    """Return the explicitly gated command-line interface module."""
    path = _PROJECT_ROOT / _CLI_MODULE
    if not path.is_file():
        raise CoverageGateError(
            f"CLI source tree is missing required module {_CLI_MODULE!r}"
        )
    return frozenset({_CLI_MODULE})


def expected_cnpj_paths() -> frozenset[str]:
    """Return the explicitly gated CNPJ check-digit module."""
    path = _PROJECT_ROOT / _CNPJ_MODULE
    if not path.is_file():
        raise CoverageGateError(
            f"CNPJ source tree is missing required module {_CNPJ_MODULE!r}"
        )
    return frozenset({_CNPJ_MODULE})


def expected_cpf_paths() -> frozenset[str]:
    """Return the explicitly gated CPF check-digit module."""
    path = _PROJECT_ROOT / _CPF_MODULE
    if not path.is_file():
        raise CoverageGateError(
            f"CPF source tree is missing required module {_CPF_MODULE!r}"
        )
    return frozenset({_CPF_MODULE})


def _counts(
    summary: Mapping[str, object],
    *,
    context: str,
    unit: str,
) -> tuple[int, int]:
    covered_key = "covered_lines" if unit == "lines" else "covered_branches"
    total_key = "num_statements" if unit == "lines" else "num_branches"
    covered = _counter(summary, covered_key, context=context)
    total = _counter(summary, total_key, context=context)
    if covered > total:
        raise CoverageGateError(f"{context} has {covered_key} greater than {total_key}")
    return covered, total


def _counter(mapping: Mapping[str, object], name: str, *, context: str) -> int:
    value = mapping.get(name)
    if type(value) is not int or value < 0:
        raise CoverageGateError(f"{context} has invalid counter {name!r}")
    return value


def _gate(scope: str, *, covered: int, total: int, minimum: int) -> GateResult:
    if total <= 0:
        raise CoverageGateError(f"{scope} has a zero denominator")
    return GateResult(scope=scope, covered=covered, total=total, minimum=minimum)


def _normalize_path(value: object) -> str:
    if type(value) is not str or not value:
        raise CoverageGateError("coverage file path must be a non-empty string")
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise CoverageGateError(f"unsafe coverage file path: {value!r}")
    return path.as_posix()


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if type(value) is not dict:
        raise CoverageGateError(f"{context} must be a JSON object")
    mapping = cast(dict[object, object], value)
    if any(type(key) is not str for key in mapping):
        raise CoverageGateError(f"{context} must use string keys")
    return cast(dict[str, object], mapping)


def _reject_json_constant(value: str) -> NoReturn:
    raise CoverageGateError(f"invalid JSON constant: {value}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Coverage.py JSON report")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run all gates and return a process exit code."""
    args = _parse_args(argv)
    try:
        results = evaluate_report(
            load_report(args.report),
            expected_f0_paths=expected_f0_paths(),
            expected_xsd_paths=expected_xsd_paths(),
            expected_builder_paths=expected_builder_paths(),
            expected_xmlsig_paths=expected_xmlsig_paths(),
            expected_cli_paths=expected_cli_paths(),
            expected_cnpj_paths=expected_cnpj_paths(),
            expected_cpf_paths=expected_cpf_paths(),
        )
    except CoverageGateError as exc:
        print(f"Coverage gate error: {exc}", file=sys.stderr)
        return 2

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{result.scope}: {result.covered}/{result.total} "
            f"({result.percentage:.2f}%) minimum {result.minimum}% {status}"
        )
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
