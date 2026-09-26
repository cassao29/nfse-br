"""Reference JSON consumer of the published API, not a public nfse-br command."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, NoReturn, cast

from nfse_br.domain import (
    CompetenceDate,
    DomainValidationError,
    FederalTaxId,
    MunicipalityCode,
)
from nfse_br.dps import DpsNumber, DpsSeries
from nfse_br.dps.builder import (
    RestrictedDpsDraft,
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
    build_unsigned_dps,
)

MAX_INPUT_BYTES = 65536
MAX_CONTAINER_DEPTH = 3
MAX_INTEGER_TOKEN_DIGITS = 64

_REJECTIONS = frozenset(
    {
        "invalid_encoding",
        "invalid_json",
        "input_limit_exceeded",
        "invalid_input_structure",
        "invalid_input_representation",
        "domain_rejected",
    }
)
_OPERATIONS = frozenset(
    {
        "invalid_arguments",
        "invalid_file_location",
        "input_read_failed",
        "output_exists",
        "output_write_failed",
        "internal_error",
    }
)
_ROOT_FIELDS = frozenset(
    {
        "issuer_tax_id",
        "issue_municipality",
        "service_municipality",
        "series",
        "number",
        "issued_at",
        "competence",
        "application_version",
        "national_service_code",
        "service_description",
        "service_amount",
        "op_simp_nac",
        "reg_esp_trib",
        "trib_issqn",
        "tp_ret_issqn",
        "ind_tot_trib",
    }
)
_ADDRESS_FIELDS = frozenset(
    {
        "municipality",
        "postal_code",
        "street",
        "number",
        "neighborhood",
    }
)
_SUCCESS = (
    "CODE = ok\nXML_UNSIGNED = YES\nXSD_VALIDATION_PERFORMED = NO\n"
    "FISCAL_AUTHORIZATION = NOT_PERFORMED\nTRANSMISSION_READY = NO\n"
)


class _Failure(Exception):
    """Keep only a closed diagnostic code, never caller data."""

    def __init__(self, code: str) -> None:
        if code not in _REJECTIONS | _OPERATIONS:
            code = "internal_error"
        self.code = code
        super().__init__(code)


class _HelpRequested(Exception):
    """Return normally from main after argparse's static help."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _Failure("invalid_arguments")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status:
            raise _Failure("invalid_arguments")
        raise _HelpRequested


def _arguments(argv: Sequence[str] | None) -> tuple[str, str]:
    parser = _Parser(
        prog="build_unsigned_dps_from_json.py",
        allow_abbrev=False,
        description="Build local unsigned DPS from JSON; no fiscal authorization.",
    )
    parser.add_argument(
        "--input", required=True, action="append", help="Local JSON file."
    )
    parser.add_argument(
        "--output", required=True, action="append", help="New XML file."
    )
    args = parser.parse_args(argv)
    inputs = cast(list[str], args.input)
    outputs = cast(list[str], args.output)
    if len(inputs) != 1 or len(outputs) != 1:
        raise _Failure("invalid_arguments")
    return inputs[0], outputs[0]


def _location(raw: str, *, windows: bool | None = None) -> Path:
    """Validate original spelling, before any Path normalization or opening."""
    if windows is None:
        windows = os.name == "nt"
    if (
        not raw
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in raw)
        or raw.startswith(("//", "\\"))
        or any(c in raw for c in '<>"|?*')
        or (not windows and "\\" in raw)
    ):
        raise _Failure("invalid_file_location")
    tail = raw
    if windows and re.match(r"[A-Za-z]:[/\\]", raw):
        tail = raw[3:]
    if ":" in tail:
        raise _Failure("invalid_file_location")
    for part in re.split(r"[/\\]", tail):
        if part in {"", ".", ".."}:
            continue
        stem = part.split(".", 1)[0].rstrip(" ").upper()
        if (
            part.endswith((".", " "))
            or stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", stem)
        ):
            raise _Failure("invalid_file_location")
    return Path(raw)


def _read_input(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        if stat.S_ISLNK(path.lstat().st_mode):
            raise _Failure("input_read_failed")
        descriptor = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise _Failure("input_read_failed")
            result = bytearray()
            while len(result) <= MAX_INPUT_BYTES:
                chunk = os.read(descriptor, MAX_INPUT_BYTES + 1 - len(result))
                if not chunk:
                    break
                result.extend(chunk)
            if len(result) > MAX_INPUT_BYTES:
                raise _Failure("input_limit_exceeded")
            return bytes(result)
        finally:
            # Exactly one close attempt; a failed close must not be retried.
            os.close(descriptor)
    except OSError:
        raise _Failure("input_read_failed") from None


def _check_depth(text: str) -> None:
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_CONTAINER_DEPTH:
                raise _Failure("input_limit_exceeded")
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise _Failure("invalid_json")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _Failure("invalid_input_structure")
        result[key] = value
    return result


def _integer(token: str) -> int:
    if len(token.removeprefix("-")) > MAX_INTEGER_TOKEN_DIGITS:
        raise _Failure("input_limit_exceeded")
    return int(token)


def _fraction(token: str) -> NoReturn:
    raise _Failure("invalid_input_representation")


def _constant(token: str) -> NoReturn:
    raise _Failure("invalid_json")


def _check_unicode(value: object) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise _Failure("invalid_input_representation")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_unicode(key)
            _check_unicode(item)
    elif isinstance(value, list):
        for item in value:
            _check_unicode(item)


def _object(
    value: object,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, object]:
    if type(value) is not dict:
        raise _Failure("invalid_input_structure")
    result = cast(dict[str, object], value)
    if not required <= result.keys() or result.keys() - required - optional:
        raise _Failure("invalid_input_structure")
    return result


def _string(value: object) -> str:
    if type(value) is not str:
        raise _Failure("invalid_input_structure")
    return value


def _decode(data: bytes) -> dict[str, object]:
    if len(data) > MAX_INPUT_BYTES:
        raise _Failure("input_limit_exceeded")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _Failure("invalid_encoding") from None
    if text.startswith("\ufeff"):
        raise _Failure("invalid_encoding")
    _check_depth(text)
    try:
        value: object = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_fraction,
            parse_constant=_constant,
            strict=True,
        )
    except json.JSONDecodeError:
        raise _Failure("invalid_json") from None
    _check_unicode(value)
    return _object(value, _ROOT_FIELDS, frozenset({"taker"}))


def _tax_id(value: object) -> FederalTaxId:
    fields = _object(value, frozenset({"kind", "value"}))
    kind = _string(fields["kind"])
    identifier = _string(fields["value"])
    if kind == "CPF":
        return FederalTaxId.cpf(identifier)
    if kind == "CNPJ":
        return FederalTaxId.cnpj(identifier)
    raise _Failure("invalid_input_representation")


def _taker(value: object) -> RestrictedDpsTaker | None:
    if value is None:
        return None
    taker = _object(value, frozenset({"tax_id", "name", "address"}))
    address = _object(taker["address"], _ADDRESS_FIELDS, frozenset({"complement"}))
    complement = address.get("complement")
    return RestrictedDpsTaker(
        tax_id=_tax_id(taker["tax_id"]),
        name=_string(taker["name"]),
        address=RestrictedDpsNationalAddress(
            municipality=MunicipalityCode(_string(address["municipality"])),
            postal_code=_string(address["postal_code"]),
            street=_string(address["street"]),
            number=_string(address["number"]),
            neighborhood=_string(address["neighborhood"]),
            complement=None if complement is None else _string(complement),
        ),
    )


def _draft(fields: dict[str, object]) -> RestrictedDpsDraft:
    number = fields["number"]
    if type(number) is not int:
        raise _Failure("invalid_input_structure")
    amount = _string(fields["service_amount"])
    if re.fullmatch(r"(0|[1-9][0-9]*)\.[0-9]{2}", amount) is None:
        raise _Failure("invalid_input_representation")
    issued = _string(fields["issued_at"])
    if re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:00", issued
    ) is None or issued.endswith("-00:00"):
        raise _Failure("invalid_input_representation")
    try:
        issued_at = datetime.fromisoformat(issued)
    except ValueError:
        raise _Failure("invalid_input_representation") from None
    # Casts describe the signature only. The draft validates the actual codes.
    return RestrictedDpsDraft(
        issuer_tax_id=_tax_id(fields["issuer_tax_id"]),
        issue_municipality=MunicipalityCode(_string(fields["issue_municipality"])),
        service_municipality=MunicipalityCode(_string(fields["service_municipality"])),
        series=DpsSeries(_string(fields["series"])),
        number=DpsNumber(number),
        issued_at=issued_at,
        competence=CompetenceDate.from_iso(_string(fields["competence"])),
        application_version=_string(fields["application_version"]),
        national_service_code=_string(fields["national_service_code"]),
        service_description=_string(fields["service_description"]),
        service_amount=Decimal(amount),
        op_simp_nac=cast(Literal["1", "2", "3"], _string(fields["op_simp_nac"])),
        reg_esp_trib=cast(
            Literal["0", "1", "2", "3", "4", "5", "6", "9"],
            _string(fields["reg_esp_trib"]),
        ),
        trib_issqn=cast(Literal["1", "2", "3", "4"], _string(fields["trib_issqn"])),
        tp_ret_issqn=cast(Literal["1", "2", "3"], _string(fields["tp_ret_issqn"])),
        ind_tot_trib=cast(Literal["0"], _string(fields["ind_tot_trib"])),
        taker=_taker(fields.get("taker")),
    )


def _document(data: bytes) -> bytes:
    try:
        return build_unsigned_dps(_draft(_decode(data)))
    except DomainValidationError:
        raise _Failure("domain_rejected") from None


def _write_output(path: Path, document: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise _Failure("output_exists") from None
    except OSError:
        raise _Failure("output_write_failed") from None
    try:
        try:
            pending = memoryview(document)
            while pending:
                written = os.write(descriptor, pending)
                if written <= 0:
                    raise _Failure("output_write_failed")
                pending = pending[written:]
        finally:
            os.close(descriptor)
    except OSError:
        # A new partial file can remain. Never unlink or overwrite it on error.
        raise _Failure("output_write_failed") from None


def main(argv: Sequence[str] | None = None) -> int:
    """Keep data and exception chains out of command diagnostics."""
    try:
        source, destination = _arguments(argv)
        input_path = _location(source)
        output_path = _location(destination)
        document = _document(_read_input(input_path))
        _write_output(output_path, document)
    except _HelpRequested:
        return 0
    except _Failure as exc:
        print(f"CODE = {exc.code}", file=sys.stderr)
        return 1 if exc.code in _REJECTIONS else 2
    except Exception:
        print("CODE = internal_error", file=sys.stderr)
        return 2
    print(_SUCCESS, end="", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
