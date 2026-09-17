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

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_F0_ROOT = _PROJECT_ROOT / "src/nfse_br/_f0"
_SCHEMA_MODULE = "src/nfse_br/_f0/dps_schema_contract.py"


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
) -> tuple[GateResult, GateResult, GateResult]:
    """Validate a Coverage.py report and calculate the three required gates."""
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
