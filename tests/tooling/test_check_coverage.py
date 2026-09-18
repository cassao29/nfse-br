"""Tests for the exact repository coverage gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from scripts import check_coverage

_SCHEMA = "src/nfse_br/_f0/dps_schema_contract.py"
_RESTRICTED = "src/nfse_br/_f0/restricted_contract.py"
_F0_INIT = "src/nfse_br/_f0/__init__.py"
_F0_PATHS = frozenset({_SCHEMA, _RESTRICTED, _F0_INIT})
_XSD_INIT = "src/nfse_br/xsd/__init__.py"
_XSD_VALIDATOR = "src/nfse_br/xsd/validator.py"
_XSD_PATHS = frozenset({_XSD_INIT, _XSD_VALIDATOR})


def _summary(*, covered: int, total: int) -> dict[str, object]:
    return {
        "covered_lines": 10,
        "num_statements": 10,
        "covered_branches": covered,
        "num_branches": total,
        "percent_branches_covered_display": "90",
    }


def _report(
    *,
    module: tuple[int, int] = (204, 226),
    restricted: tuple[int, int] = (100, 100),
    global_lines: tuple[int, int] = (800, 900),
    global_branches: tuple[int, int] = (80, 100),
    xsd: tuple[int, int] = (90, 100),
    branch_coverage: bool = True,
) -> dict[str, object]:
    return {
        "meta": {"branch_coverage": branch_coverage},
        "totals": {
            "covered_lines": global_lines[0],
            "num_statements": global_lines[1],
            "covered_branches": global_branches[0],
            "num_branches": global_branches[1],
        },
        "files": {
            _F0_INIT: {"summary": _summary(covered=0, total=0)},
            _SCHEMA: {"summary": _summary(covered=module[0], total=module[1])},
            _RESTRICTED: {
                "summary": _summary(
                    covered=restricted[0],
                    total=restricted[1],
                )
            },
            _XSD_INIT: {"summary": _summary(covered=0, total=0)},
            _XSD_VALIDATOR: {"summary": _summary(covered=xsd[0], total=xsd[1])},
        },
    }


def _results(report: dict[str, object]) -> tuple[check_coverage.GateResult, ...]:
    return check_coverage.evaluate_report(
        report,
        expected_f0_paths=_F0_PATHS,
        expected_xsd_paths=_XSD_PATHS,
    )


def test_module_203_of_226_fails_even_with_rounded_display() -> None:
    results = _results(_report(module=(203, 226)))

    assert [result.passed for result in results] == [True, True, False, True]
    assert results[2].percentage == pytest.approx(89.82300884955752)


def test_module_204_of_226_passes() -> None:
    results = _results(_report(module=(204, 226)))

    assert all(result.passed for result in results)


def test_exactly_ninety_percent_passes() -> None:
    results = _results(_report(module=(9, 10), restricted=(9, 10)))

    assert results[1].passed
    assert results[2].passed


def test_xsd_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(xsd=(9, 10)))
    failing = _results(_report(xsd=(89, 100)))

    assert passing[3].passed
    assert not failing[3].passed
    assert all(result.passed for result in failing[:3])


def test_aggregate_f0_below_ninety_percent_fails() -> None:
    results = _results(_report(module=(90, 100), restricted=(8, 10)))

    assert results[1].covered == 98
    assert results[1].total == 110
    assert not results[1].passed
    assert results[2].passed
    assert results[3].passed


def test_global_combined_below_eighty_percent_fails() -> None:
    results = _results(
        _report(
            global_lines=(600, 900),
            global_branches=(100, 100),
        )
    )

    assert not results[0].passed
    assert results[1].passed
    assert results[2].passed
    assert results[3].passed


def test_missing_module_and_disabled_branch_measurement_are_rejected() -> None:
    missing = _report()
    files = cast(dict[str, object], missing["files"])
    del files[_SCHEMA]

    with pytest.raises(check_coverage.CoverageGateError, match="missing F0 files"):
        _results(missing)
    with pytest.raises(check_coverage.CoverageGateError, match="not enabled"):
        _results(_report(branch_coverage=False))


def test_missing_xsd_file_is_rejected() -> None:
    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_XSD_VALIDATOR]

    with pytest.raises(check_coverage.CoverageGateError, match="missing XSD files"):
        _results(report)


def test_xsd_scope_must_explicitly_include_validator() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=frozenset({_XSD_INIT}),
        )


def test_xsd_source_tree_without_validator_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    xsd_root = project_root / "src/nfse_br/xsd"
    xsd_root.mkdir(parents=True)
    (xsd_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)
    monkeypatch.setattr(check_coverage, "_XSD_ROOT", xsd_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_xsd_paths()


@pytest.mark.parametrize(
    ("covered", "total", "error"),
    [
        (-1, 10, "invalid counter"),
        (11, 10, "greater than"),
        (0, 0, "zero denominator"),
    ],
)
def test_invalid_module_counters_are_rejected(
    covered: int,
    total: int,
    error: str,
) -> None:
    with pytest.raises(check_coverage.CoverageGateError, match=error):
        _results(_report(module=(covered, total)))


def test_windows_paths_are_normalized_and_duplicates_are_rejected() -> None:
    report = _report()
    files = cast(dict[str, object], report["files"])
    files[_SCHEMA.replace("/", "\\")] = files.pop(_SCHEMA)

    assert all(result.passed for result in _results(report))

    duplicate = _report()
    duplicate_files = cast(dict[str, object], duplicate["files"])
    duplicate_files[_SCHEMA.replace("/", "\\")] = duplicate_files[_SCHEMA]
    with pytest.raises(check_coverage.CoverageGateError, match="duplicate file path"):
        _results(duplicate)


def test_cli_returns_zero_and_prints_all_passing_gates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")

    assert check_coverage.main([str(path)]) == 0
    output = capsys.readouterr().out
    assert "Library combined" in output
    assert "F0 branches" in output
    assert "DPS schema branches" in output
    assert "XSD validator branches" in output
    assert output.count("PASS") == 4


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        '{"meta": {"branch_coverage": NaN}}',
        "[]",
    ],
)
def test_cli_rejects_invalid_json_reports(
    contents: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(contents, encoding="utf-8")

    assert check_coverage.main([str(path)]) == 2
    assert "Coverage gate error" in capsys.readouterr().err


def test_cli_rejects_invalid_utf8_and_missing_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff")

    assert check_coverage.main([str(invalid_utf8)]) == 2
    assert "Coverage gate error" in capsys.readouterr().err

    assert check_coverage.main([str(tmp_path / "missing.json")]) == 2
    assert "Coverage gate error" in capsys.readouterr().err


def test_cli_returns_one_when_a_valid_gate_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_report(module=(203, 226))), encoding="utf-8")

    assert check_coverage.main([str(path)]) == 1
    output = capsys.readouterr().out
    assert "203/226 (89.82%) minimum 90% FAIL" in output


def test_unsafe_or_incomplete_f0_paths_are_rejected() -> None:
    unsafe = _report()
    files = cast(dict[str, object], unsafe["files"])
    files["../src/nfse_br/_f0/other.py"] = {"summary": _summary(covered=1, total=1)}

    with pytest.raises(check_coverage.CoverageGateError, match="unsafe"):
        _results(unsafe)

    with pytest.raises(check_coverage.CoverageGateError, match="missing F0 files"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS | {"src/nfse_br/_f0/future.py"},
            expected_xsd_paths=_XSD_PATHS,
        )
