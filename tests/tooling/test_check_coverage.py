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
_NFSE_XSD_VALIDATOR = "src/nfse_br/xsd/nfse_validator.py"
_XSD_PATHS = frozenset({_XSD_INIT, _XSD_VALIDATOR, _NFSE_XSD_VALIDATOR})
_DPS_BUILDER = "src/nfse_br/dps/builder.py"
_BUILDER_PATHS = frozenset({_DPS_BUILDER})
_XMLSIG_PREFLIGHT = "src/nfse_br/_xmlsig/preflight.py"
_XMLSIG_PATHS = frozenset({_XMLSIG_PREFLIGHT})
_CLI = "src/nfse_br/cli.py"
_CLI_PATHS = frozenset({_CLI})
_CNPJ = "src/nfse_br/domain/cnpj.py"
_CNPJ_PATHS = frozenset({_CNPJ})
_CPF = "src/nfse_br/domain/cpf.py"
_CPF_PATHS = frozenset({_CPF})
_NFSE_ACCESS_KEY = "src/nfse_br/nfse/access_key.py"
_NFSE_ACCESS_KEY_PATHS = frozenset({_NFSE_ACCESS_KEY})
_NFSE_ID = "src/nfse_br/nfse/identifier.py"
_NFSE_ID_PATHS = frozenset({_NFSE_ID})
_NFSE_DOCUMENT = "src/nfse_br/nfse/document.py"
_NFSE_DOCUMENT_PATHS = frozenset({_NFSE_DOCUMENT})
_NFSE_CONSISTENCY = "src/nfse_br/nfse/consistency.py"
_NFSE_CONSISTENCY_PATHS = frozenset({_NFSE_CONSISTENCY})


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
    builder: tuple[int, int] = (90, 100),
    xmlsig: tuple[int, int] = (90, 100),
    cli: tuple[int, int] = (90, 100),
    cnpj: tuple[int, int] = (90, 100),
    cpf: tuple[int, int] = (90, 100),
    nfse_access_key: tuple[int, int] = (90, 100),
    nfse_id: tuple[int, int] = (90, 100),
    nfse_document: tuple[int, int] = (90, 100),
    nfse_consistency: tuple[int, int] = (90, 100),
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
            _NFSE_XSD_VALIDATOR: {"summary": _summary(covered=0, total=0)},
            _DPS_BUILDER: {"summary": _summary(covered=builder[0], total=builder[1])},
            _XMLSIG_PREFLIGHT: {
                "summary": _summary(covered=xmlsig[0], total=xmlsig[1])
            },
            _CLI: {"summary": _summary(covered=cli[0], total=cli[1])},
            _CNPJ: {"summary": _summary(covered=cnpj[0], total=cnpj[1])},
            _CPF: {"summary": _summary(covered=cpf[0], total=cpf[1])},
            _NFSE_ACCESS_KEY: {
                "summary": _summary(
                    covered=nfse_access_key[0],
                    total=nfse_access_key[1],
                )
            },
            _NFSE_ID: {
                "summary": _summary(
                    covered=nfse_id[0],
                    total=nfse_id[1],
                )
            },
            _NFSE_DOCUMENT: {
                "summary": _summary(
                    covered=nfse_document[0],
                    total=nfse_document[1],
                )
            },
            _NFSE_CONSISTENCY: {
                "summary": _summary(
                    covered=nfse_consistency[0],
                    total=nfse_consistency[1],
                )
            },
        },
    }


def _results(report: dict[str, object]) -> tuple[check_coverage.GateResult, ...]:
    return check_coverage.evaluate_report(
        report,
        expected_f0_paths=_F0_PATHS,
        expected_xsd_paths=_XSD_PATHS,
        expected_builder_paths=_BUILDER_PATHS,
        expected_xmlsig_paths=_XMLSIG_PATHS,
        expected_cli_paths=_CLI_PATHS,
        expected_cnpj_paths=_CNPJ_PATHS,
        expected_cpf_paths=_CPF_PATHS,
        expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
        expected_nfse_id_paths=_NFSE_ID_PATHS,
        expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
        expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
    )


def test_module_203_of_226_fails_even_with_rounded_display() -> None:
    results = _results(_report(module=(203, 226)))

    assert [result.passed for result in results] == [
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    ]
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


def test_builder_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(builder=(9, 10)))
    failing = _results(_report(builder=(89, 100)))

    assert passing[4].passed
    assert not failing[4].passed
    assert all(result.passed for result in failing[:4])


def test_xmlsig_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(xmlsig=(9, 10)))
    failing = _results(_report(xmlsig=(89, 100)))

    assert passing[5].passed
    assert not failing[5].passed
    assert all(result.passed for result in failing[:5])


def test_cli_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(cli=(9, 10)))
    failing = _results(_report(cli=(89, 100)))

    assert passing[6].passed
    assert not failing[6].passed
    assert all(result.passed for result in failing[:6])


def test_cnpj_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(cnpj=(9, 10)))
    failing = _results(_report(cnpj=(89, 100)))

    assert passing[7].passed
    assert not failing[7].passed
    assert all(result.passed for result in failing[:7])


def test_cpf_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(cpf=(9, 10)))
    failing = _results(_report(cpf=(89, 100)))

    assert passing[8].passed
    assert not failing[8].passed
    assert all(result.passed for result in failing[:8])


def test_nfse_access_key_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(nfse_access_key=(9, 10)))
    failing = _results(_report(nfse_access_key=(89, 100)))

    assert passing[9].passed
    assert not failing[9].passed
    assert all(result.passed for result in failing[:9])


def test_nfse_id_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(nfse_id=(9, 10)))
    failing = _results(_report(nfse_id=(89, 100)))

    assert passing[10].passed
    assert not failing[10].passed
    assert all(result.passed for result in failing[:10])


def test_nfse_document_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(nfse_document=(9, 10)))
    failing = _results(_report(nfse_document=(89, 100)))

    assert passing[11].passed
    assert not failing[11].passed
    assert all(result.passed for result in failing[:11])


def test_nfse_consistency_exactly_ninety_percent_passes_and_below_fails() -> None:
    passing = _results(_report(nfse_consistency=(9, 10)))
    failing = _results(_report(nfse_consistency=(89, 100)))

    assert passing[12].passed
    assert not failing[12].passed
    assert all(result.passed for result in failing[:12])


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


@pytest.mark.parametrize("missing_path", [_XSD_VALIDATOR, _NFSE_XSD_VALIDATOR])
def test_missing_xsd_file_is_rejected(missing_path: str) -> None:
    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[missing_path]

    with pytest.raises(check_coverage.CoverageGateError, match="missing XSD files"):
        _results(report)


def test_xsd_scope_must_explicitly_include_validator() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=frozenset({_XSD_INIT, _NFSE_XSD_VALIDATOR}),
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )


def test_xsd_scope_must_explicitly_include_nfse_validator() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=frozenset({_XSD_INIT, _XSD_VALIDATOR}),
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )


def test_builder_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=frozenset(),
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_DPS_BUILDER]
    with pytest.raises(check_coverage.CoverageGateError, match="missing DPS builder"):
        _results(report)


def test_xmlsig_scope_and_report_must_include_preflight() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=frozenset(),
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_XMLSIG_PREFLIGHT]
    with pytest.raises(
        check_coverage.CoverageGateError,
        match="missing XML signature preflight",
    ):
        _results(report)


def test_cli_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=frozenset(),
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_CLI]
    with pytest.raises(check_coverage.CoverageGateError, match="missing CLI files"):
        _results(report)


def test_cnpj_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=frozenset(),
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_CNPJ]
    with pytest.raises(check_coverage.CoverageGateError, match="missing CNPJ files"):
        _results(report)


def test_cpf_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=frozenset(),
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_CPF]
    with pytest.raises(check_coverage.CoverageGateError, match="missing CPF files"):
        _results(report)


def test_nfse_access_key_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=frozenset(),
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_NFSE_ACCESS_KEY]
    with pytest.raises(
        check_coverage.CoverageGateError,
        match="missing NFS-e access-key files",
    ):
        _results(report)


def test_nfse_id_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=frozenset(),
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_NFSE_ID]
    with pytest.raises(
        check_coverage.CoverageGateError,
        match="missing NFS-e identifier files",
    ):
        _results(report)


def test_nfse_document_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=frozenset(),
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_NFSE_DOCUMENT]
    with pytest.raises(
        check_coverage.CoverageGateError,
        match="missing NFS-e document files",
    ):
        _results(report)


def test_nfse_consistency_scope_and_report_must_include_required_module() -> None:
    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.evaluate_report(
            _report(),
            expected_f0_paths=_F0_PATHS,
            expected_xsd_paths=_XSD_PATHS,
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=frozenset(),
        )

    report = _report()
    files = cast(dict[str, object], report["files"])
    del files[_NFSE_CONSISTENCY]
    with pytest.raises(
        check_coverage.CoverageGateError,
        match="missing NFS-e consistency files",
    ):
        _results(report)


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


def test_builder_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_builder_paths()


def test_xmlsig_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_xmlsig_paths()


def test_cli_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_cli_paths()


def test_cnpj_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_cnpj_paths()


def test_cpf_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required module"):
        check_coverage.expected_cpf_paths()


def test_nfse_access_key_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required access-key"):
        check_coverage.expected_nfse_access_key_paths()


def test_nfse_id_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required identifier"):
        check_coverage.expected_nfse_id_paths()


def test_nfse_document_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required document"):
        check_coverage.expected_nfse_document_paths()


def test_nfse_consistency_source_tree_without_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(check_coverage, "_PROJECT_ROOT", project_root)

    with pytest.raises(check_coverage.CoverageGateError, match="required consistency"):
        check_coverage.expected_nfse_consistency_paths()


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
    assert "DPS builder branches" in output
    assert "XML signature preflight branches" in output
    assert "CLI branches" in output
    assert "CNPJ check-digit branches" in output
    assert "CPF check-digit branches" in output
    assert "NFS-e access-key branches" in output
    assert "NFS-e identifier branches" in output
    assert "NFS-e document branches" in output
    assert "NFS-e consistency branches" in output
    assert output.count("PASS") == 13


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
            expected_builder_paths=_BUILDER_PATHS,
            expected_xmlsig_paths=_XMLSIG_PATHS,
            expected_cli_paths=_CLI_PATHS,
            expected_cnpj_paths=_CNPJ_PATHS,
            expected_cpf_paths=_CPF_PATHS,
            expected_nfse_access_key_paths=_NFSE_ACCESS_KEY_PATHS,
            expected_nfse_id_paths=_NFSE_ID_PATHS,
            expected_nfse_document_paths=_NFSE_DOCUMENT_PATHS,
            expected_nfse_consistency_paths=_NFSE_CONSISTENCY_PATHS,
        )
