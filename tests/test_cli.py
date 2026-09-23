"""Tests for the local NFS-e and unsigned-DPS command-line interface."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import BinaryIO, Never, cast

import pytest

from nfse_br import cli
from nfse_br.dps import DpsDocumentError
from nfse_br.nfse import NfseConsistencyError, NfseDocumentError


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
    help_output = capsys.readouterr().out
    assert "check-unsigned" in help_output
    assert "check-nfse" in help_output

    assert cli.main(["check-nfse", "--help"]) == 0
    assert "already-recovered NFS-e XML" in capsys.readouterr().out

    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out == "nfse-br 0.4.0\n"

    project_root = Path(__file__).resolve().parents[1]
    program = (
        "import sys; "
        f"sys.path.insert(0, {str(project_root / 'src')!r}); "
        "sys.modules['lxml'] = None; "
        "import nfse_br.cli; "
        "assert 'nfse_br._xmlsig.preflight' not in sys.modules; "
        "assert 'nfse_br.xsd' not in sys.modules; "
        "raise SystemExit(nfse_br.cli.main(['--version']))"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == "nfse-br 0.4.0\n"
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
        ["check-nfse"],
        ["check-nfse", "secret-document.xml"],
        ["check-nfse", "secret-document.xml", "--bundle"],
        ["check-nfse", "document.xml", "--unknown", "secret-value"],
        ["check-nfse", "document.xml", "--bundle", "bundle.zip", "extra"],
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
    directory_error = "file_unreadable" if os.name == "nt" else "not_regular_file"
    with pytest.raises(cli._OperationalError, match=directory_error):
        cli._read_regular_file(tmp_path, limit=4)
    with pytest.raises(cli._OperationalError, match="file_unreadable"):
        cli._read_regular_file(tmp_path / "missing", limit=4)
    with pytest.raises(cli._OperationalError, match="invalid_file_location"):
        cli._read_regular_file(Path("https://example.invalid/input"), limit=4)

    link = tmp_path / "link"
    link.symlink_to(regular)
    if hasattr(os, "O_NOFOLLOW"):
        with pytest.raises(cli._OperationalError, match="file_unreadable"):
            cli._read_regular_file(link, limit=4)
    else:
        assert cli._read_regular_file(link, limit=4) == b"1234"

    if hasattr(os, "mkfifo"):
        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        with pytest.raises(cli._OperationalError, match="not_regular_file"):
            cli._read_regular_file(fifo, limit=4)


def test_file_reader_preserves_binary_bytes(tmp_path: Path) -> None:
    payload = b"first\r\nsecond\x1a\x00\x80\xff"
    regular = tmp_path / "dados binarios acentuados á.bin"
    regular.write_bytes(payload)

    assert cli._read_regular_file(regular, limit=len(payload)) == payload


def test_reader_classifies_the_descriptor_after_a_controlled_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    original = tmp_path / "original"
    target.write_bytes(b"safe")
    real_open = os.open
    swapped = False

    def swap_then_open(path: os.PathLike[str] | str, flags: int) -> int:
        nonlocal swapped
        if not swapped and Path(path) == target:
            target.rename(original)
            target.mkdir()
            swapped = True
        return real_open(path, flags)

    monkeypatch.setattr(os, "open", swap_then_open)

    directory_error = "file_unreadable" if os.name == "nt" else "not_regular_file"
    with pytest.raises(cli._OperationalError, match=directory_error):
        cli._read_regular_file(target, limit=4)
    assert swapped


def test_reader_detects_growth_after_the_descriptor_is_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "growing"
    target.write_bytes(b"1234")
    real_fdopen = os.fdopen

    def grow_then_fdopen(descriptor: int, mode: str) -> BinaryIO:
        with target.open("ab") as growing:
            growing.write(b"5")
        return cast(BinaryIO, real_fdopen(descriptor, mode))

    monkeypatch.setattr(os, "fdopen", grow_then_fdopen)

    with pytest.raises(cli._OperationalError, match="file_too_large"):
        cli._read_regular_file(target, limit=4)


def test_reader_closes_descriptors_on_success_and_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    regular = tmp_path / "regular"
    regular.write_bytes(b"data")
    real_open = os.open
    descriptors: list[int] = []

    def track_open(path: os.PathLike[str] | str, flags: int) -> int:
        descriptor = real_open(path, flags)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", track_open)

    assert cli._read_regular_file(regular, limit=4) == b"data"
    with pytest.raises(OSError):
        os.fstat(descriptors[-1])

    descriptor_count = len(descriptors)
    directory_error = "file_unreadable" if os.name == "nt" else "not_regular_file"
    with pytest.raises(cli._OperationalError, match=directory_error):
        cli._read_regular_file(tmp_path, limit=4)
    if os.name == "nt":
        assert len(descriptors) == descriptor_count
    else:
        assert len(descriptors) == descriptor_count + 1
        with pytest.raises(OSError):
            os.fstat(descriptors[-1])


def test_reader_rejects_and_closes_an_open_non_regular_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_descriptor, write_descriptor = os.pipe()
    os.close(write_descriptor)

    def open_pipe(_path: os.PathLike[str] | str, _flags: int) -> int:
        return read_descriptor

    monkeypatch.setattr(os, "open", open_pipe)

    with pytest.raises(cli._OperationalError, match="not_regular_file"):
        cli._read_regular_file(tmp_path / "synthetic-pipe", limit=4)
    with pytest.raises(OSError):
        os.fstat(read_descriptor)


def test_windows_drive_path_is_not_misclassified_as_a_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[Path] = []

    def unavailable(path: os.PathLike[str] | str, _flags: int) -> Never:
        observed.append(Path(path))
        raise OSError

    monkeypatch.setattr(os, "open", unavailable)

    with pytest.raises(cli._OperationalError, match="file_unreadable"):
        cli._read_regular_file(Path(r"C:\dados\DPS.xml"), limit=4)
    assert observed == [Path(r"C:\dados\DPS.xml")]


@pytest.mark.parametrize(
    "malformed_location",
    [
        "//[sigiloso",
        "//[sigiloso]",
        "//sigiloso／host/bundle.zip",
    ],
)
def test_malformed_file_locations_are_rejected_before_open(
    malformed_location: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_open(_path: os.PathLike[str] | str, _flags: int) -> Never:
        raise AssertionError("malformed locations must be rejected before open")

    monkeypatch.setattr(os, "open", unexpected_open)

    with pytest.raises(cli._OperationalError, match="invalid_file_location"):
        cli._read_regular_file(Path(malformed_location), limit=4)


@pytest.mark.parametrize(
    "malformed_location",
    [
        "//[sigiloso",
        "//[sigiloso]",
        "//sigiloso／host/bundle.zip",
    ],
)
@pytest.mark.parametrize("command", ["check-unsigned", "check-nfse"])
def test_real_entry_points_control_malformed_file_locations(
    command: str,
    malformed_location: str,
) -> None:
    console = Path(sys.executable).with_name("nfse-br")
    entry_points = (
        [str(console)],
        [sys.executable, "-I", "-m", "nfse_br"],
    )

    for entry_point in entry_points:
        completed = subprocess.run(
            [
                *entry_point,
                command,
                "documento.xml",
                "--bundle",
                malformed_location,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        assert completed.returncode == 2
        assert completed.stdout == (
            '{"status":"error","stage":"bundle_read",'
            '"code":"invalid_file_location","transmission_ready":false}\n'
        )
        assert completed.stderr == ""
        assert "sigiloso" not in completed.stdout
        assert "sigiloso" not in completed.stderr


@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="POSIX FIFO and non-blocking open are required",
)
@pytest.mark.parametrize("command", ["check-unsigned", "check-nfse"])
def test_fifo_is_rejected_by_a_real_entry_point_without_blocking(
    command: str,
    tmp_path: Path,
) -> None:
    fifo = tmp_path / "sensitive fifo"
    document = tmp_path / "document.xml"
    mkfifo = getattr(os, "mkfifo", None)
    assert mkfifo is not None
    mkfifo(fifo)
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "nfse_br",
            command,
            str(document),
            "--bundle",
            str(fifo),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=3,
    )

    assert completed.returncode == 2
    assert _payload(completed.stdout) == {
        "status": "error",
        "stage": "bundle_read",
        "code": "not_regular_file",
        "transmission_ready": False,
    }
    assert completed.stderr == ""
    assert str(fifo) not in completed.stdout


def test_real_entry_points_suppress_argparse_values_and_usage() -> None:
    sensitive_document = "documento sigiloso á <CPF>.xml"
    sensitive_bundle = "bundle sigiloso ç <TOKEN>.zip"
    console = Path(sys.executable).with_name("nfse-br")
    entry_points = (
        [str(console)],
        [sys.executable, "-I", "-m", "nfse_br"],
    )
    cases = (
        ["subcomando-sigiloso"],
        ["check-unsigned"],
        ["check-unsigned", sensitive_document, "--bundle"],
        [
            "check-unsigned",
            sensitive_document,
            "--bundle",
            sensitive_bundle,
            "--opcao-sigilosa",
        ],
        [
            "check-unsigned",
            sensitive_document,
            "--bundle",
            sensitive_bundle,
            "argumento-excedente-sigiloso",
        ],
        ["check-nfse"],
        ["check-nfse", sensitive_document, "--bundle"],
        [
            "check-nfse",
            sensitive_document,
            "--bundle",
            sensitive_bundle,
            "--opcao-sigilosa",
        ],
        [
            "check-nfse",
            sensitive_document,
            "--bundle",
            sensitive_bundle,
            "argumento-excedente-sigiloso",
        ],
    )

    for entry_point in entry_points:
        for arguments in cases:
            completed = subprocess.run(
                [*entry_point, *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            assert completed.returncode == 2
            assert _payload(completed.stdout) == {
                "status": "error",
                "stage": "usage",
                "code": "invalid_arguments",
                "transmission_ready": False,
            }
            assert completed.stderr == ""
            assert sensitive_document not in completed.stdout
            assert sensitive_bundle not in completed.stdout


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


def test_broken_optional_import_is_not_reported_as_a_missing_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    def broken_import() -> Never:
        raise ModuleNotFoundError("synthetic broken dependency", name="other")

    monkeypatch.setattr(cli, "_import_xsd_components", broken_import)

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "dependency",
        "code": "xsd_import_failed",
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


def test_public_checker_rejects_an_unpinned_bundle(
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


def test_success_passes_the_once_read_document_to_checker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    observed: dict[str, bytes] = {}

    class Checker:
        def __init__(self, bundle_bytes: bytes) -> None:
            observed["bundle"] = bundle_bytes

        def check(self, xml_bytes: bytes) -> object:
            observed["check"] = xml_bytes
            document.write_bytes(b"changed after the one bounded read")
            return object()

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 0
    assert _payload(capsys.readouterr().out) == {
        "status": "ok",
        "stage": "complete",
        "code": None,
        "transmission_ready": False,
    }
    assert observed["bundle"] == b"bundle"
    assert observed["check"] == b"<DPS/>"
    assert document.read_bytes() == b"changed after the one bounded read"


@pytest.mark.parametrize("phase", ["parse", "schema"])
def test_xsd_rejection_keeps_the_existing_stage_mapping(
    phase: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> Never:
            raise _FakeXsdError(phase, "controlled_xsd_rejection")

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

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

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> Never:
            raise _FakeXsdError("bundle", "engine_failure")

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-unsigned", str(document), "--bundle", str(bundle)]) == 2
    result = _payload(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["stage"] == "xsd_bundle"


def test_inspection_rejection_and_following_success_are_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    calls = 0

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> object:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise DpsDocumentError("unsupported_local_profile")
            return object()

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

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

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> object:
            return object()

    monkeypatch.setattr(
        cli,
        "_load_xsd_components",
        lambda: (Checker, _FakeXsdError),
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


def test_nfse_missing_extra_is_controlled_before_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    document.unlink()
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "dependency",
        "code": "xsd_extra_missing",
        "transmission_ready": False,
    }


def test_nfse_oversized_bundle_stops_before_dependency_and_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "oversized-private-bundle.zip"
    document = tmp_path / "missing-private-document.xml"
    bundle.write_bytes(b"x" * (cli._RESTRICTED_BUNDLE_BYTES + 1))

    def unexpected_load() -> Never:
        raise AssertionError("optional dependency must not load")

    monkeypatch.setattr(cli, "_load_nfse_xsd_components", unexpected_load)

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    output = capsys.readouterr().out
    assert _payload(output) == {
        "status": "error",
        "stage": "bundle_read",
        "code": "file_too_large",
        "transmission_ready": False,
    }
    assert str(bundle) not in output
    assert str(document) not in output


def test_nfse_broken_optional_import_is_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    def broken_import() -> Never:
        raise ModuleNotFoundError("synthetic broken dependency", name="other")

    monkeypatch.setattr(cli, "_import_nfse_xsd_components", broken_import)

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "dependency",
        "code": "xsd_import_failed",
        "transmission_ready": False,
    }


def test_nfse_public_validator_rejects_an_unpinned_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "bundle",
        "code": "size_mismatch",
        "transmission_ready": False,
    }


def test_nfse_checker_receives_the_single_bounded_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    document.write_bytes(b"<NFSe>synthetic-sensitive-value</NFSe>")
    observed: list[bytes] = []

    class Checker:
        def __init__(self, bundle_bytes: bytes) -> None:
            assert bundle_bytes == b"bundle"

        def check(self, xml_bytes: bytes) -> object:
            observed.append(xml_bytes)
            document.write_bytes(b"changed after the one bounded read")
            return object()

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 0
    assert _payload(capsys.readouterr().out) == {
        "status": "ok",
        "stage": "complete",
        "code": None,
        "transmission_ready": False,
    }
    assert observed == [b"<NFSe>synthetic-sensitive-value</NFSe>"]
    assert document.read_bytes() == b"changed after the one bounded read"


@pytest.mark.parametrize(
    ("phase", "status", "exit_code"),
    [
        ("parse", "rejected", 1),
        ("schema", "rejected", 1),
        ("engine", "error", 2),
    ],
)
def test_nfse_xsd_failures_short_circuit_pipeline(
    phase: str,
    status: str,
    exit_code: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> Never:
            raise _FakeXsdError(phase, "controlled_xsd_failure")

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == exit_code
    assert _payload(capsys.readouterr().out) == {
        "status": status,
        "stage": f"xsd_{phase}",
        "code": "controlled_xsd_failure",
        "transmission_ready": False,
    }


def test_nfse_structure_rejection_short_circuits_consistency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> Never:
            raise NfseDocumentError("invalid_nfse_id")

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 1
    assert _payload(capsys.readouterr().out) == {
        "status": "rejected",
        "stage": "structure",
        "code": "invalid_nfse_id",
        "transmission_ready": False,
    }


def test_nfse_consistency_rejection_is_privacy_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sensitive = "NFS-SYNTHETIC-PRIVATE-IDENTIFIER"
    bundle = tmp_path / "private bundle TOKEN.zip"
    document = tmp_path / "private document CPF.xml"
    bundle.write_bytes(b"bundle")
    document.write_bytes(sensitive.encode())

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> Never:
            raise NfseConsistencyError("federal_registration_mismatch")

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 1
    captured = capsys.readouterr()
    assert _payload(captured.out) == {
        "status": "rejected",
        "stage": "consistency",
        "code": "federal_registration_mismatch",
        "transmission_ready": False,
    }
    combined = captured.out + captured.err
    assert sensitive not in combined
    assert str(document) not in combined
    assert str(bundle) not in combined


def test_nfse_bundle_failure_stops_before_document_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    document.unlink()

    def reject_bundle(_bundle: bytes) -> Never:
        raise _FakeXsdError("bundle", "digest_mismatch")

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (reject_bundle, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    assert _payload(capsys.readouterr().out) == {
        "status": "error",
        "stage": "bundle",
        "code": "digest_mismatch",
        "transmission_ready": False,
    }


def test_nfse_missing_document_is_controlled_without_disclosing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, document = _paths(tmp_path)
    document.unlink()

    class Checker:
        def __init__(self, _bundle_bytes: bytes) -> None:
            pass

        def check(self, _xml_bytes: bytes) -> None:
            pass

    monkeypatch.setattr(
        cli,
        "_load_nfse_xsd_components",
        lambda: (Checker, _FakeXsdError),
    )

    assert cli.main(["check-nfse", str(document), "--bundle", str(bundle)]) == 2
    output = capsys.readouterr().out
    assert _payload(output) == {
        "status": "error",
        "stage": "xml_read",
        "code": "file_unreadable",
        "transmission_ready": False,
    }
    assert str(document) not in output
