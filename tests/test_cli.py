"""Tests for the local unsigned-DPS command-line interface."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Never

import pytest

from nfse_br import cli
from nfse_br._xmlsig.preflight import SignaturePreflightError


class _FakeXsdError(ValueError):
    def __init__(self, phase: str, code: str) -> None:
        self.phase = phase
        self.code = code
        super().__init__(code)


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle.zip"
    document = tmp_path / "document.xml"
    bundle.write_bytes(b"bundle")
    document.write_bytes(b"<DPS/>")
    return bundle, document


def _payload(output: str) -> dict[str, object]:
    assert output.endswith("\n")
    assert output.count("\n") == 1
    value = json.loads(output)
    assert type(value) is dict
    return value


def test_help_version_and_import_do_not_load_lxml(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["--help"]) == 0
    assert "check-unsigned" in capsys.readouterr().out

    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out == "nfse-br 0.1.0\n"

    project_root = Path(__file__).resolve().parents[1]
    program = (
        "import sys; "
        f"sys.path.insert(0, {str(project_root / 'src')!r}); "
        "sys.modules['lxml'] = None; "
        "import nfse_br.cli; "
        "raise SystemExit(nfse_br.cli.main(['--version']))"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == "nfse-br 0.1.0\n"
    assert completed.stderr == ""


def test_parser_exit_can_emit_only_a_controlled_static_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = cli._ArgumentParser()

    with pytest.raises(cli._ParserExit) as caught:
        parser.exit(2, "controlled parser exit\n")

    assert caught.value.status == 2
    assert capsys.readouterr().err == "controlled parser exit\n"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["unknown-command"],
        ["check-unsigned"],
        ["check-unsigned", "secret-document.xml"],
        ["check-unsigned", "document.xml", "--unknown", "secret-value"],
    ],
)
def test_invalid_arguments_are_controlled_and_do_not_echo_values(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(argv) == 2
    captured = capsys.readouterr()
    assert _payload(captured.out) == {
        "status": "error",
        "stage": "usage",
        "code": "invalid_arguments",
        "transmission_ready": False,
    }
    assert captured.err == ""
    assert "secret" not in captured.out


def test_file_reader_accepts_only_bounded_regular_local_files(tmp_path: Path) -> None:
    regular = tmp_path / "regular"
    regular.write_bytes(b"1234")
    assert cli._read_regular_file(regular, limit=4) == b"1234"

    oversized = tmp_path / "oversized"
    oversized.write_bytes(b"12345")
    with pytest.raises(cli._OperationalError, match="file_too_large"):
        cli._read_regular_file(oversized, limit=4)
    with pytest.raises(cli._OperationalError, match="not_regular_file"):
        cli._read_regular_file(tmp_path, limit=4)
    with pytest.raises(cli._OperationalError, match="file_unreadable"):
        cli._read_regular_file(tmp_path / "missing", limit=4)
    with pytest.raises(cli._OperationalError, match="invalid_file_location"):
        cli._read_regular_file(Path("https://example.invalid/input"), limit=4)

    link = tmp_path / "link"
    link.symlink_to(regular)
    with pytest.raises(cli._OperationalError, match="file_unreadable"):
        cli._read_regular_file(link, limit=4)

    if hasattr(os, "mkfifo"):
        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        with pytest.raises(cli._OperationalError, match="not_regular_file"):
            cli._read_regular_file(fifo, limit=4)


def test_missing_extra_is_a_controlled_operational_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "dependency",
        "code": "xsd_extra_missing",
        "transmission_ready": False,
    }


def test_bundle_is_bounded_and_validated_before_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "bundle.zip"
    document = tmp_path / "private-document.xml"
    bundle.write_bytes(b"x" * (cli._RESTRICTED_BUNDLE_BYTES + 1))

    def unexpected_load() -> Never:
        raise AssertionError("optional dependency must not load")

    monkeypatch.setattr(cli, "_load_xsd_components", unexpected_load)
    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    output = capsys.readouterr().out
    assert _payload(output)["code"] == "file_too_large"
    assert "private-document" not in output


def test_invalid_bundle_stops_before_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    def reject_bundle(_bundle: bytes) -> Never:
        raise _FakeXsdError("bundle", "digest_mismatch")

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (reject_bundle, _FakeXsdError),
    )
    document.unlink()

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "bundle",
        "code": "digest_mismatch",
        "transmission_ready": False,
    }


def test_public_validator_rejects_an_unpinned_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "bundle",
        "code": "size_mismatch",
        "transmission_ready": False,
    }


def test_success_passes_the_same_xml_bytes_to_both_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    observed: dict[str, bytes] = {}

    class Validator:
        def __init__(self, bundle_bytes: bytes) -> None:
            observed["bundle"] = bundle_bytes

        def validate(self, xml_bytes: bytes) -> None:
            observed["xsd"] = xml_bytes

    def preflight(xml_bytes: bytes) -> str:
        observed["preflight"] = xml_bytes
        return "controlled-id"

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Validator, _FakeXsdError),
    )
    monkeypatch.setattr(cli, "inspect_unsigned_dps", preflight)

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 0
    assert _payload(capsys.readouterr().out) == {
        "status": "ok",
        "stage": "complete",
        "code": None,
        "transmission_ready": False,
    }
    assert observed["bundle"] == b"bundle"
    assert observed["xsd"] == b"<DPS/>"
    assert observed["xsd"] is observed["preflight"]


@pytest.mark.parametrize("phase", ["parse", "schema"])
def test_xsd_rejection_stops_before_preflight(
    phase: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> Never:
            raise _FakeXsdError(phase, "controlled_xsd_rejection")

    def unexpected_preflight(_xml_bytes: bytes) -> Never:
        raise AssertionError("preflight must not execute")

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Validator, _FakeXsdError),
    )
    monkeypatch.setattr(cli, "inspect_unsigned_dps", unexpected_preflight)

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 1
    assert _payload(capsys.readouterr().out) == {
        "status": "rejected",
        "stage": f"xsd_{phase}",
        "code": "controlled_xsd_rejection",
        "transmission_ready": False,
    }


def test_non_document_xsd_failure_is_operational(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> Never:
            raise _FakeXsdError("bundle", "engine_failure")

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Validator, _FakeXsdError),
    )

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    result = _payload(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["stage"] == "xsd_bundle"


def test_preflight_rejection_and_following_success_are_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    preflight_calls = 0

    def preflight(_xml_bytes: bytes) -> str:
        nonlocal preflight_calls
        preflight_calls += 1
        if preflight_calls == 1:
            raise SignaturePreflightError("unsupported_local_profile")
        return "controlled-id"

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Validator, _FakeXsdError),
    )
    monkeypatch.setattr(cli, "inspect_unsigned_dps", preflight)

    arguments = ["check-unsigned", str(document), "--bundle", str(bundle)]
    assert cli.main(arguments) == 1
    rejected = _payload(capsys.readouterr().out)
    assert rejected["status"] == "rejected"
    assert rejected["stage"] == "preflight"
    assert rejected["code"] == "unsupported_local_profile"

    assert cli.main(arguments) == 0
    assert _payload(capsys.readouterr().out)["status"] == "ok"


def test_missing_document_is_controlled_without_disclosing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    document.unlink()

    class Validator:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def validate(self, _xml_bytes: bytes) -> None:
            pass

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Validator, _FakeXsdError),
    )

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    output = capsys.readouterr().out
    assert _payload(output)["stage"] == "xml_read"
    assert str(document) not in output


def test_result_emission_is_one_compact_json_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli._Result("ok", "complete", None, 0)
    result.emit()

    assert capsys.readouterr().out == (
        '{"status":"ok","stage":"complete","code":null,"transmission_ready":false}\n'
    )
