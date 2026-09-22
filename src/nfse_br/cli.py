"""Privacy-safe command-line checks for local NFS-e and DPS documents."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, Protocol, cast
from urllib.parse import urlsplit

from nfse_br import __version__
from nfse_br._xmlsig.preflight import MAX_XML_BYTES
from nfse_br.dps import DpsDocumentError, inspect_unsigned_dps
from nfse_br.nfse import (
    NfseConsistencyError,
    NfseDocumentError,
)

_RESTRICTED_BUNDLE_BYTES = 34_933


class _Validator(Protocol):
    def validate(self, xml_bytes: bytes) -> None: ...


class _NfseChecker(Protocol):
    def check(self, xml_bytes: bytes) -> object: ...


class _XsdFailure(Protocol):
    phase: str
    code: str


type _ValidatorFactory = Callable[[bytes], _Validator]
type _NfseCheckerFactory = Callable[[bytes], _NfseChecker]


class _UsageError(ValueError):
    """Signal invalid arguments without retaining their values."""


class _ParserExit(Exception):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__()


class _OperationalError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        raise _UsageError

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        if message:
            self._print_message(message, sys.stderr)
        raise _ParserExit(status)


@dataclass(frozen=True, slots=True)
class _Result:
    status: Literal["ok", "rejected", "error"]
    stage: str
    code: str | None
    exit_code: int

    def emit(self) -> None:
        print(
            json.dumps(
                {
                    "status": self.status,
                    "stage": self.stage,
                    "code": self.code,
                    "transmission_ready": False,
                },
                separators=(",", ":"),
            )
        )


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="nfse-br",
        description="Local checks for restricted NFS-e and DPS documents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check-unsigned",
        help="validate one unsigned DPS against the pinned restricted profile",
    )
    check.add_argument("document", type=Path, metavar="DOCUMENT")
    check.add_argument("--bundle", required=True, type=Path, metavar="BUNDLE")
    check_nfse = commands.add_parser(
        "check-nfse",
        help="validate one already-recovered NFS-e XML document locally",
        description="Validate one already-recovered NFS-e XML document locally.",
    )
    check_nfse.add_argument("document", type=Path, metavar="DOCUMENT")
    check_nfse.add_argument("--bundle", required=True, type=Path, metavar="BUNDLE")
    return parser


def _load_xsd_components() -> tuple[_ValidatorFactory, type[Exception]]:
    if importlib.util.find_spec("lxml") is None:
        raise _OperationalError("xsd_extra_missing")

    try:
        return _import_xsd_components()
    except ImportError:
        raise _OperationalError("xsd_import_failed") from None


def _import_xsd_components() -> tuple[_ValidatorFactory, type[Exception]]:
    """Import the optional validator only after confirming lxml is present."""
    from nfse_br.xsd import RestrictedDpsXsdValidator, XsdValidationError

    return RestrictedDpsXsdValidator, XsdValidationError


def _load_nfse_xsd_components() -> tuple[_NfseCheckerFactory, type[Exception]]:
    if importlib.util.find_spec("lxml") is None:
        raise _OperationalError("xsd_extra_missing")

    try:
        return _import_nfse_xsd_components()
    except ImportError:
        raise _OperationalError("xsd_import_failed") from None


def _import_nfse_xsd_components() -> tuple[_NfseCheckerFactory, type[Exception]]:
    """Import the optional NFS-e checker only when lxml is present."""
    from nfse_br.xsd import RecoveredNfseChecker, XsdValidationError

    return RecoveredNfseChecker, XsdValidationError


def _read_regular_file(path: Path, *, limit: int) -> bytes:
    raw_path = os.fspath(path)
    try:
        parsed = urlsplit(raw_path)
    except ValueError:
        raise _OperationalError("invalid_file_location") from None
    windows_drive = len(parsed.scheme) == 1 and raw_path[1:2] == ":"
    if (
        (parsed.scheme and not windows_drive)
        or parsed.netloc
        or raw_path.startswith(("//", "\\\\"))
    ):
        raise _OperationalError("invalid_file_location")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise _OperationalError("not_regular_file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            data = stream.read(limit + 1)
    except _OperationalError:
        raise
    except OSError:
        raise _OperationalError("file_unreadable") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if len(data) > limit:
        raise _OperationalError("file_too_large")
    return data


def _failure(
    status: Literal["rejected", "error"],
    *,
    stage: str,
    code: str,
) -> _Result:
    return _Result(
        status=status,
        stage=stage,
        code=code,
        exit_code=1 if status == "rejected" else 2,
    )


def _check_unsigned(document_path: Path, bundle_path: Path) -> _Result:
    try:
        bundle_bytes = _read_regular_file(
            bundle_path,
            limit=_RESTRICTED_BUNDLE_BYTES,
        )
    except _OperationalError as exc:
        return _failure("error", stage="bundle_read", code=exc.code)

    try:
        validator_factory, xsd_error_type = _load_xsd_components()
    except _OperationalError as exc:
        return _failure("error", stage="dependency", code=exc.code)

    try:
        validator = validator_factory(bundle_bytes)
    except xsd_error_type as exc:
        failure = cast(_XsdFailure, exc)
        return _failure("error", stage="bundle", code=failure.code)

    try:
        xml_bytes = _read_regular_file(document_path, limit=MAX_XML_BYTES)
    except _OperationalError as exc:
        return _failure("error", stage="xml_read", code=exc.code)

    try:
        validator.validate(xml_bytes)
    except xsd_error_type as exc:
        failure = cast(_XsdFailure, exc)
        status: Literal["rejected", "error"] = (
            "rejected" if failure.phase in {"parse", "schema"} else "error"
        )
        return _failure(status, stage=f"xsd_{failure.phase}", code=failure.code)

    try:
        inspect_unsigned_dps(xml_bytes)
    except DpsDocumentError as exc:
        return _failure("rejected", stage="preflight", code=exc.code)

    return _Result(status="ok", stage="complete", code=None, exit_code=0)


def _check_nfse(document_path: Path, bundle_path: Path) -> _Result:
    try:
        bundle_bytes = _read_regular_file(
            bundle_path,
            limit=_RESTRICTED_BUNDLE_BYTES,
        )
    except _OperationalError as exc:
        return _failure("error", stage="bundle_read", code=exc.code)

    try:
        checker_factory, xsd_error_type = _load_nfse_xsd_components()
    except _OperationalError as exc:
        return _failure("error", stage="dependency", code=exc.code)

    try:
        checker = checker_factory(bundle_bytes)
    except xsd_error_type as exc:
        failure = cast(_XsdFailure, exc)
        return _failure("error", stage="bundle", code=failure.code)

    try:
        xml_bytes = _read_regular_file(document_path, limit=MAX_XML_BYTES)
    except _OperationalError as exc:
        return _failure("error", stage="xml_read", code=exc.code)

    try:
        checker.check(xml_bytes)
    except xsd_error_type as exc:
        failure = cast(_XsdFailure, exc)
        status: Literal["rejected", "error"] = (
            "rejected" if failure.phase in {"parse", "schema"} else "error"
        )
        return _failure(status, stage=f"xsd_{failure.phase}", code=failure.code)

    except NfseDocumentError as exc:
        return _failure("rejected", stage="structure", code=exc.code)
    except NfseConsistencyError as exc:
        return _failure("rejected", stage="consistency", code=exc.code)

    return _Result(status="ok", stage="complete", code=None, exit_code=0)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a stable process exit code."""
    try:
        args = _parser().parse_args(argv)
    except _ParserExit as exc:
        return exc.status
    except _UsageError:
        result = _failure("error", stage="usage", code="invalid_arguments")
        result.emit()
        return result.exit_code

    if args.command == "check-unsigned":
        result = _check_unsigned(args.document, args.bundle)
    else:
        result = _check_nfse(args.document, args.bundle)
    result.emit()
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
