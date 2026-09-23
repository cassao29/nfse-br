"""Offline contract and execution tests for the dedicated WATCH-1 workflow."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github/workflows/watch-official-evidence.yml"


def _workflow_parts() -> tuple[str, str]:
    # The workflow deliberately has one final Python run block. Execute that
    # exact block in tests instead of duplicating its status/exit decision.
    configuration, script = _WORKFLOW.read_text(encoding="utf-8").split(
        "        run: |\n"
    )
    return configuration, textwrap.dedent(script)


def test_weekly_schedule_and_manual_dispatch_are_separate_from_ci() -> None:
    configuration, _ = _workflow_parts()
    events = configuration.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
    assert events == '  schedule:\n    - cron: "17 12 * * 1"\n  workflow_dispatch:\n'
    assert 'python-version: "3.12"' in configuration
    assert "runs-on: ubuntu-24.04" in configuration
    assert "timeout-minutes: 20" in configuration
    ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/check_official_evidence.py" not in ci
    assert "watch-official-evidence.yml" not in ci


def test_workflow_has_only_read_permission_and_pinned_actions() -> None:
    configuration, _ = _workflow_parts()
    assert re.findall(r"(?m)^[ \t]*permissions:.*$", configuration) == ["permissions:"]
    permissions = configuration.split("permissions:\n", 1)[1].split("\njobs:", 1)[0]
    assert permissions == "  contents: read\n"
    assert "persist-credentials: false" in configuration
    assert re.findall(r"uses: (\S+)", configuration) == [
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
    ]
    assert "shell: python" in configuration
    for forbidden in (
        "contents: write",
        "issues: write",
        "pull-requests: write",
        "write-all",
        "secrets",
        "continue-on-error",
        "${{",
    ):
        assert forbidden not in _WORKFLOW.read_text(encoding="utf-8")


def _run_workflow(
    tmp_path: Path, stdout: str, exit_code: int, *, stderr: str = ""
) -> tuple[subprocess.CompletedProcess[str], str]:
    _, script = _workflow_parts()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "check_official_evidence.py").write_text(
        f"import sys\nsys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.md"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary_path)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    return result, summary_path.read_text(encoding="utf-8")


def test_unchanged_with_zero_exit_is_green_and_summary_preserves_full_json(
    tmp_path: Path,
) -> None:
    report = {
        "status": "unchanged",
        "checked_sources": 8,
        "signals": [],
        "omitted_signals": 0,
        "post_openapi_candidate": False,
        "xmldsig_review_candidate": False,
        "material_change": False,
    }
    result, summary = _run_workflow(tmp_path, json.dumps(report), 0)
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""
    assert "Watcher exit code: 0" in summary
    rendered = summary.split("<pre>", 1)[1].split("</pre>", 1)[0]
    assert json.loads(html.unescape(rendered)) == report


@pytest.mark.parametrize(
    "status,exit_code",
    [
        ("unchanged", 1),
        ("unchanged", 30),
        ("source_relocated", 10),
        ("material_change", 20),
        ("review_required", 20),
        ("post_openapi_candidate", 21),
        ("xmldsig_review_candidate", 22),
        ("network_error", 30),
        ("review_required", 0),
        ("unexpected_status", 0),
    ],
)
def test_status_and_exit_must_both_indicate_unchanged(
    tmp_path: Path, status: str, exit_code: int
) -> None:
    result, summary = _run_workflow(tmp_path, json.dumps({"status": status}), exit_code)
    assert result.returncode == 1
    assert result.stdout.startswith("::error::WATCH-1 requires manual review.")
    assert result.stderr == ""
    assert status in summary
    assert f"Watcher exit code: {exit_code}" in summary


@pytest.mark.parametrize("stdout", ["", "not JSON", "[]", "null", "{}", "{}\n{}"])
def test_invalid_or_missing_report_fails_closed(tmp_path: Path, stdout: str) -> None:
    result, summary = _run_workflow(tmp_path, stdout, 0)
    assert result.returncode == 1
    assert result.stdout.startswith("::error::WATCH-1 requires manual review.")
    assert result.stderr == ""
    assert "<pre>" in summary


def test_remote_text_cannot_inject_commands_or_summary_markup(tmp_path: Path) -> None:
    hostile = "</pre><script>alert(1)</script>\n::error::remote command\n```"
    report = {"status": "review_required", "signals": [{"label": hostile}]}
    result, summary = _run_workflow(
        tmp_path, json.dumps(report), 20, stderr="::error::untrusted stderr"
    )
    assert result.returncode == 1
    assert result.stdout.count("::error::") == 1
    assert "remote command" not in result.stdout
    assert "untrusted stderr" not in result.stdout
    assert result.stderr == ""
    assert "<script>" not in summary
    rendered = summary.split("<pre>", 1)[1].split("</pre>", 1)[0]
    assert json.loads(html.unescape(rendered)) == report


def test_watcher_timeout_is_red_with_controlled_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, script = _workflow_parts()
    summary_path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    def timeout(*args: object, **kwargs: object) -> None:
        assert kwargs["timeout"] == 900
        raise subprocess.TimeoutExpired("watcher", 900)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(SystemExit) as caught:
        exec(compile(script, str(_WORKFLOW), "exec"), {})
    assert caught.value.code == 1
    assert capsys.readouterr().out.startswith(
        "::error::WATCH-1 requires manual review."
    )
    assert "network_error" in summary_path.read_text(encoding="utf-8")
