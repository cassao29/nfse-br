"""Tests for the explicit generated-DPS integration helper."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts import validate_generated_dps

from nfse_br.dps.builder import build_unsigned_dps


def test_generated_mutation_requires_one_effective_target() -> None:
    with pytest.raises(
        validate_generated_dps.GeneratedMutationError, match="observed 0"
    ):
        validate_generated_dps._replace_once(b"original", b"absent", b"changed")
    with pytest.raises(
        validate_generated_dps.GeneratedMutationError, match="observed 2"
    ):
        validate_generated_dps._replace_once(b"xx", b"x", b"y")
    with pytest.raises(
        validate_generated_dps.GeneratedMutationError, match="no change"
    ):
        validate_generated_dps._replace_once(b"x", b"x", b"x")

    assert validate_generated_dps._replace_once(b"abc", b"b", b"X") == b"aXc"


def test_negative_generated_documents_are_distinct_and_targeted() -> None:
    valid = build_unsigned_dps(validate_generated_dps._base_draft())
    cases = validate_generated_dps._invalid_documents(valid)

    assert [label for label, _document in cases] == [
        "nDPS zero",
        "required field removed",
        "field order changed",
    ]
    assert all(document != valid for _label, document in cases)
    assert b"<nDPS>0</nDPS>" in cases[0][1]
    assert b"<tpAmb>2</tpAmb>" not in cases[1][1]
    assert b"<nDPS>42</nDPS><serie>123</serie>" in cases[2][1]


def test_generated_integration_reports_unreadable_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert validate_generated_dps.main([str(tmp_path / "missing.zip")]) == 2
    assert "could not be read" in capsys.readouterr().out
