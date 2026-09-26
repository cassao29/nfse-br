"""Offline transport, conversion and filesystem tests with independent XML."""

from __future__ import annotations

import ast
import json
import os
import socket
import stat
import subprocess
import sys
import traceback
from decimal import Inexact, Rounded, localcontext
from pathlib import Path
from typing import NoReturn, cast

import pytest

from examples import build_unsigned_dps_from_json as consumer
from nfse_br.dps import inspect_unsigned_dps, parse_unsigned_dps
from nfse_br.dps.builder import build_unsigned_dps

_SCRIPT = Path(consumer.__file__).resolve()
_SUCCESS = (
    "CODE = ok\nXML_UNSIGNED = YES\nXSD_VALIDATION_PERFORMED = NO\n"
    "FISCAL_AUTHORIZATION = NOT_PERFORMED\nTRANSMISSION_READY = NO\n"
)
_BASE = """{
  "issuer_tax_id": {"kind": "CNPJ", "value": "12ABC6780001Z0"},
  "issue_municipality": "2927408", "service_municipality": "3550308",
  "series": "00123", "number": 42,
  "issued_at": "2026-09-17T12:00:00-03:00", "competence": "2026-09-17",
  "application_version": "json-reference", "national_service_code": "010101",
  "service_description": "Servico sintetico de integracao", "service_amount": "100.10",
  "op_simp_nac": "1", "reg_esp_trib": "0", "trib_issqn": "1",
  "tp_ret_issqn": "1", "ind_tot_trib": "0"
}"""
_TAKER = """{
  "tax_id": {"kind": "CPF", "value": "01234567890"},
  "name": "Tomador & Sintetico",
  "address": {"municipality": "3550308", "postal_code": "01234567",
    "street": "Rua Sintetica", "number": "0", "neighborhood": "Centro",
    "complement": "Sala A"}
}"""
# Independent literal XML, not serialized using either consumer or builder.
_BEFORE = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<DPS xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">'
    '<infDPS Id="DPS2927408212ABC6780001Z000123000000000000042">'
    "<tpAmb>2</tpAmb><dhEmi>2026-09-17T12:00:00-03:00</dhEmi>"
    "<verAplic>json-reference</verAplic><serie>00123</serie><nDPS>42</nDPS>"
    "<dCompet>2026-09-17</dCompet><tpEmit>1</tpEmit><cLocEmi>2927408</cLocEmi>"
    "<prest><CNPJ>12ABC6780001Z0</CNPJ><regTrib><opSimpNac>1</opSimpNac>"
    "<regEspTrib>0</regEspTrib></regTrib></prest>"
)
_AFTER = (
    "<serv><locPrest><cLocPrestacao>3550308</cLocPrestacao></locPrest><cServ>"
    "<cTribNac>010101</cTribNac><xDescServ>Servico sintetico de integracao"
    "</xDescServ></cServ></serv><valores><vServPrest><vServ>100.10</vServ>"
    "</vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN>"
    "</tribMun><totTrib><indTotTrib>0</indTotTrib></totTrib></trib></valores>"
    "</infDPS></DPS>"
)
_ADDRESS = (
    "<xNome>Tomador &amp; Sintetico</xNome><end><endNac><cMun>3550308</cMun>"
    "<CEP>01234567</CEP></endNac><xLgr>Rua Sintetica</xLgr><nro>0</nro>"
)


def _payload(taker: bool = False) -> dict[str, object]:
    value = cast(dict[str, object], json.loads(_BASE))
    if taker:
        value["taker"] = json.loads(_TAKER)
    return value


def _bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True).encode("utf-8")


def _at(value: dict[str, object], path: str) -> dict[str, object]:
    for part in path.split(".") if path else []:
        value = cast(dict[str, object], value[part])
    return value


def _reject(data: bytes, code: str) -> consumer._Failure:
    with pytest.raises(consumer._Failure) as caught:
        consumer._document(data)
    assert str(caught.value) == code
    return caught.value


@pytest.mark.parametrize(
    "kind,identifier,complement",
    [
        (None, None, None),
        ("CPF", "01234567890", "Sala A"),
        ("CNPJ", "12345678000199", None),
        ("CNPJ", "98ABC6780001Z0", None),
    ],
)
def test_independent_oracles_and_recovered_fields(
    kind: str | None,
    identifier: str | None,
    complement: str | None,
) -> None:
    value = _payload(kind is not None)
    block = ""
    if kind is not None:
        taker = _at(value, "taker")
        taker["tax_id"] = {"kind": kind, "value": identifier}
        _at(taker, "address")["complement"] = complement
        block = f"<toma><{kind}>{identifier}</{kind}>" + _ADDRESS
        if complement is not None:
            block += "<xCpl>Sala A</xCpl>"
        block += "<xBairro>Centro</xBairro></end></toma>"
    xml = consumer._document(_bytes(value))
    assert xml == (_BEFORE + block + _AFTER).encode()
    draft = parse_unsigned_dps(xml)
    assert draft.issuer_tax_id.value == "12ABC6780001Z0"
    assert draft.issue_municipality.value == "2927408"
    assert draft.service_municipality.value == "3550308"
    assert draft.series.value == "00123"
    assert draft.number.value == 42
    assert draft.issued_at.isoformat() == "2026-09-17T12:00:00-03:00"
    assert draft.competence.value.isoformat() == "2026-09-17"
    assert draft.application_version == "json-reference"
    assert draft.national_service_code == "010101"
    assert draft.service_description == "Servico sintetico de integracao"
    assert str(draft.service_amount) == "100.10"
    assert (
        draft.op_simp_nac,
        draft.reg_esp_trib,
        draft.trib_issqn,
        draft.tp_ret_issqn,
        draft.ind_tot_trib,
    ) == ("1", "0", "1", "1", "0")
    if kind is None:
        assert draft.taker is None
    else:
        assert draft.taker is not None
        assert draft.taker.tax_id.kind.value == kind
        assert draft.taker.tax_id.value == identifier
        assert draft.taker.name == "Tomador & Sintetico"
        address = draft.taker.address
        assert address.municipality.value == "3550308"
        assert address.postal_code == "01234567"
        assert (address.street, address.number, address.neighborhood) == (
            "Rua Sintetica",
            "0",
            "Centro",
        )
        assert address.complement == complement
    assert build_unsigned_dps(draft) == xml
    assert inspect_unsigned_dps(xml).value == (
        "DPS2927408212ABC6780001Z000123000000000000042"
    )


@pytest.mark.parametrize(
    "path", ["", "issuer_tax_id", "taker", "taker.tax_id", "taker.address"]
)
def test_closed_objects_missing_unknown_duplicate_and_equivalent_escapes(
    path: str,
) -> None:
    original = _payload(True)
    fields = _at(original, path)
    for key in list(fields):
        if key in {"complement", "taker"}:
            continue
        value = _payload(True)
        del _at(value, path)[key]
        _reject(_bytes(value), "invalid_input_structure")
    fields["unknown-private-field"] = "private-value"
    _reject(_bytes(original), "invalid_input_structure")
    # Duplicate the first field of the selected object, including escape aliases.
    value = _payload(True)
    fields = _at(value, path)
    key = next(iter(fields))
    needle = json.dumps(fields)
    for alias in (json.dumps(key), f'"\\u{ord(key[0]):04x}{key[1:]}"'):
        replacement = "{" + alias + ": null, " + needle[1:]
        encoded = json.dumps(value).replace(needle, replacement, 1).encode()
        _reject(encoded, "invalid_input_structure")


@pytest.mark.parametrize(
    "path", ["", "issuer_tax_id", "taker", "taker.tax_id", "taker.address"]
)
@pytest.mark.parametrize("bad", [None, [], "", True, 3])
def test_object_types(path: str, bad: object) -> None:
    value = _payload(True)
    if not path:
        _reject(_bytes(bad), "invalid_input_structure")
        return
    if path == "taker" and bad is None:
        return  # The optional None case is checked separately.
    parent, _, field = path.rpartition(".")
    _at(value, parent)[field] = bad
    _reject(_bytes(value), "invalid_input_structure")


def test_every_scalar_rejects_wrong_types_and_null() -> None:
    for path in ("", "issuer_tax_id", "taker", "taker.tax_id", "taker.address"):
        for field, good in _at(_payload(True), path).items():
            if isinstance(good, dict):
                continue
            bad_values: tuple[object, ...] = (
                None,
                [],
                {},
                True,
                9 if isinstance(good, str) else "42",
            )
            for bad in bad_values:
                if field == "complement" and bad is None:
                    continue
                value = _payload(True)
                _at(value, path)[field] = bad
                code = (
                    "input_limit_exceeded"
                    if path.count(".") == 1 and isinstance(bad, (list, dict))
                    else "invalid_input_structure"
                )
                _reject(_bytes(value), code)


def test_optional_absence_null_reordering_and_normalization() -> None:
    value = _payload()
    plain = consumer._document(_bytes(value))
    value["taker"] = None
    assert consumer._document(_bytes(value)) == plain
    value = _payload(True)
    address = _at(value, "taker.address")
    del address["complement"]
    omitted = consumer._document(_bytes(value))
    address["complement"] = None
    assert consumer._document(_bytes(value)) == omitted
    address["complement"] = ""
    _reject(_bytes(value), "domain_rejected")
    value = _payload(True)
    _at(value, "issuer_tax_id")["value"] = "12abc6780001z0"
    _at(value, "taker.tax_id").update(kind="CNPJ", value="98abc6780001z0")
    draft = parse_unsigned_dps(
        consumer._document(_bytes(dict(reversed(list(value.items())))))
    )
    assert draft.issuer_tax_id.value == "12ABC6780001Z0"
    assert draft.taker is not None and draft.taker.tax_id.value == "98ABC6780001Z0"
    escaped = _BASE.replace('"number"', '"\\u006eumber"')
    assert consumer._document(escaped.encode()) == plain


@pytest.mark.parametrize(
    "bad,code",
    [
        (b"", "invalid_json"),
        (b"{} {}", "invalid_json"),
        (b"{", "invalid_json"),
        (b"}", "invalid_json"),
        (b'{"x":1,}', "invalid_json"),
        (b"/*comment*/{}", "invalid_json"),
        (b"\xff", "invalid_encoding"),
        (b"\xef\xbb\xbf{}", "invalid_encoding"),
        (b"\xff\xfe{\x00}\x00", "invalid_encoding"),
        (b'{"x":NaN}', "invalid_json"),
        (b'{"x":Infinity}', "invalid_json"),
        (b'{"x":-Infinity}', "invalid_json"),
        (b'{"x":1.0}', "invalid_input_representation"),
        (b'{"x":1e999999}', "invalid_input_representation"),
        (b'{"\\ud800":0}', "invalid_input_representation"),
        (b'{"x":"\\udfff"}', "invalid_input_representation"),
        (b'{"x":["\\ud800"]}', "invalid_input_representation"),
        (b"[" * 10000, "input_limit_exceeded"),
    ],
)
def test_decoder_rejections(bad: bytes, code: str) -> None:
    _reject(bad, code)


def test_resource_boundaries_and_escaped_delimiters() -> None:
    data = _BASE.encode()
    exact = data + b" " * (65536 - len(data))
    assert consumer._document(exact) == consumer._document(data)
    _reject(exact + b" ", "input_limit_exceeded")
    value = _payload(True)
    value["service_description"] = '[[[[ {{{{ \\ \\" "]]]}}} texto'
    assert (
        parse_unsigned_dps(consumer._document(_bytes(value))).service_description
        == value["service_description"]
    )
    consumer._check_depth('{"a":[{}]}')
    _reject(b'{"a":[[{}]]}', "input_limit_exceeded")
    for digits, code in ((64, "domain_rejected"), (65, "input_limit_exceeded")):
        _reject(
            _BASE.replace('"number": 42', '"number": ' + "9" * digits).encode(), code
        )
        _reject(
            _BASE.replace('"number": 42', '"number": -' + "9" * digits).encode(), code
        )
    value["service_description"] = "Texto \U0001f600"
    assert (
        parse_unsigned_dps(consumer._document(_bytes(value))).service_description
        == "Texto \U0001f600"
    )


@pytest.mark.parametrize(
    "field,bad,code",
    [
        *[
            ("service_amount", v, "invalid_input_representation")
            for v in (
                "1",
                "1.0",
                "1.000",
                "01.00",
                "+1.00",
                "-0.00",
                "1e2",
                "NaN",
                "1,00",
                "1.00\n",
                "１.00",
            )
        ],
        ("service_amount", "1000000000000000.00", "domain_rejected"),
        *[
            ("issued_at", v, "invalid_input_representation")
            for v in (
                "2026-09-17T12:00:00Z",
                "2026-09-17T12:00:00-00:00",
                "2026-09-17 12:00:00-03:00",
                "2026-09-17T12:00:00.1-03:00",
                "2026-09-17T12:00:00",
                "2026-09-17T12:00:00+03:30",
                "2026-02-30T12:00:00+00:00",
                "2026-09-17T12:00:00+24:00",
                "2026-09-17T12:00:00-03:00\n",
            )
        ],
        ("issued_at", "1999-12-31T12:00:00+00:00", "domain_rejected"),
        ("issued_at", "2026-09-17T12:00:00+13:00", "domain_rejected"),
        ("competence", "2026-02-30", "domain_rejected"),
        ("competence", "20260917", "domain_rejected"),
        ("competence", "2100-01-01", "domain_rejected"),
        ("number", 0, "domain_rejected"),
        ("number", -1, "domain_rejected"),
        ("op_simp_nac", "9", "domain_rejected"),
        ("reg_esp_trib", "7", "domain_rejected"),
        ("trib_issqn", "0", "domain_rejected"),
        ("tp_ret_issqn", "9", "domain_rejected"),
        ("ind_tot_trib", "1", "domain_rejected"),
        ("service_description", "\r", "domain_rejected"),
        ("service_description", "\x00", "domain_rejected"),
    ],
)
def test_transport_versus_domain(field: str, bad: object, code: str) -> None:
    value = _payload()
    value[field] = bad
    _reject(_bytes(value), code)


def test_delegated_text_and_identifier_rules() -> None:
    for path, field, bad, code in (
        ("issuer_tax_id", "kind", "NIF", "invalid_input_representation"),
        ("issuer_tax_id", "value", "short", "domain_rejected"),
        ("taker", "name", "x" * 151, "domain_rejected"),
        ("taker.address", "street", " leading", "domain_rejected"),
        ("taker.address", "street", "e\u0301", "domain_rejected"),
        ("taker.address", "postal_code", "123", "domain_rejected"),
    ):
        value = _payload(True)
        _at(value, path)[field] = bad
        _reject(_bytes(value), code)
    value = _payload()
    value["issuer_tax_id"] = {"kind": "CPF", "value": "01234567890"}
    _reject(_bytes(value), "domain_rejected")
    value = _payload(True)
    _at(value, "taker")["name"] = ' <Nome> & "Sintetico"\t\n '
    recovered = parse_unsigned_dps(consumer._document(_bytes(value)))
    assert recovered.taker is not None
    assert recovered.taker.name == ' <Nome> & "Sintetico"\t\n '


@pytest.mark.parametrize("amount", ["0.00", "0.01", "100.10", "999999999999999.99"])
def test_exact_decimal_and_date_boundaries(amount: str) -> None:
    value = _payload()
    value.update(service_amount=amount, competence="2000-02-29")
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = context.traps[Rounded] = True
        for stamp in (
            "2000-01-01T00:00:00-11:00",
            "2099-12-31T23:59:59+12:00",
            "2026-09-17T12:00:00+00:00",
        ):
            value["issued_at"] = stamp
            draft = parse_unsigned_dps(consumer._document(_bytes(value)))
            assert str(draft.service_amount) == amount
            assert draft.issued_at.isoformat() == stamp


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "\x00input",
        "file\nname",
        "file\x85name",
        "https://example.invalid/x",
        "file:///tmp/x",
        "//server/share",
        r"\\server\share",
        r"\\?\C:\file",
        r"\\.\NUL",
        r"\??\C:\file",
        "output.xml:stream",
        "C:relative",
        "NUL",
        "nul.txt",
        "aux.json",
        "dir/CON.xml",
        "COM1",
        "LPT9.log",
        "COM¹.txt",
        "CONIN$",
        "CONOUT$",
        "NUL .json",
        "file.",
        "file ",
        "wild*card",
        "file?x",
        'file"x',
        "a|b",
        "a<b",
    ],
)
@pytest.mark.parametrize("windows", [False, True])
def test_raw_path_rejections(raw: str, windows: bool) -> None:
    with pytest.raises(consumer._Failure, match="invalid_file_location"):
        consumer._location(raw, windows=windows)


def test_native_paths() -> None:
    for raw in ("input.json", "dir with spaces/ação.json", "/tmp/a", "./a", "../a"):
        assert consumer._location(raw, windows=False) == Path(raw)
    for raw in (r"C:\dir\a.json", "C:/dir/a.json", r"dir\a.json"):
        assert consumer._location(raw, windows=True) == Path(raw)
    with pytest.raises(consumer._Failure):
        consumer._location(r"dir\a.json", windows=False)


def test_command_success_rejection_and_then_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, output = tmp_path / "entrada.json", tmp_path / "saida.xml"
    source.write_text(_BASE, encoding="utf-8")
    args = ["--input", str(source), "--output", str(output)]
    assert consumer.main(args) == 0
    assert capsys.readouterr() == ("", _SUCCESS)
    assert output.read_bytes() == (_BEFORE + _AFTER).encode()
    assert consumer.main(args) == 2
    assert capsys.readouterr() == ("", "CODE = output_exists\n")
    assert output.read_bytes() == (_BEFORE + _AFTER).encode()
    original = source.read_bytes()
    assert consumer.main(["--input", str(source), "--output", str(source)]) == 2
    assert source.read_bytes() == original
    capsys.readouterr()
    output.unlink()
    source.write_bytes(b'{"private":NaN}')
    assert consumer.main(args) == 1
    assert capsys.readouterr() == ("", "CODE = invalid_json\n")
    assert not output.exists()
    source.write_text(_BASE, encoding="utf-8")
    assert consumer.main(args) == 0
    assert capsys.readouterr() == ("", _SUCCESS)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--input", "sensitive"],
        ["--in", "sensitive", "--output", "x"],
        ["--input", "a", "--input", "b", "--output", "c"],
        ["--input", "a", "--output", "b", "--output", "c"],
        ["--input", "a", "--output", "b", "--unknown", "private"],
        ["@private"],
    ],
)
def test_usage_never_echoes_arguments(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert consumer.main(args) == 2
    assert capsys.readouterr() == ("", "CODE = invalid_arguments\n")


def test_help_and_fixed_failure_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert consumer.main(["--help"]) == 0
    out = capsys.readouterr()
    assert "usage: build_unsigned_dps_from_json.py" in out.out
    assert out.err == ""
    assert str(consumer._Failure("private-value")) == "internal_error"
    with pytest.raises(consumer._Failure, match="invalid_arguments"):
        consumer._Parser().exit(2, "private")


def test_command_faults_are_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sensitive.json"
    source.write_text(_BASE, encoding="utf-8")
    destination = tmp_path / "private.xml"

    def failure(data: bytes) -> NoReturn:
        try:
            raise ValueError("CPF nome endereco JSON sensitive")
        except ValueError as exc:
            raise RuntimeError("private XML") from exc

    monkeypatch.setattr(consumer, "_document", failure)
    assert consumer.main(["--input", str(source), "--output", str(destination)]) == 2
    assert capsys.readouterr() == ("", "CODE = internal_error\n")
    assert not destination.exists()
    for data, code in (
        (b'{"SENSITIVE_SENTINEL_90210":', "invalid_json"),
        (b"\xffSENSITIVE_SENTINEL_90210", "invalid_encoding"),
    ):
        with pytest.raises(consumer._Failure) as exc:
            consumer._decode(data)
        rendered = "".join(traceback.format_exception(exc.value))
        assert code in rendered and "SENSITIVE_SENTINEL_90210" not in rendered
        assert exc.value.__cause__ is None


def test_read_short_chunks_limit_flags_and_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "input"
    path.write_bytes(b"a" * 65536)
    real_read, real_open, real_close = os.read, os.open, os.close
    flags_seen: list[int] = []
    closed: list[int] = []

    def opened(path: Path, flags: int) -> int:
        flags_seen.append(flags)
        return real_open(path, flags)

    def read(fd: int, size: int) -> bytes:
        return real_read(fd, min(size, 701))

    def close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "close", close)
    assert consumer._read_input(path) == b"a" * 65536
    assert len(closed) == 1
    if hasattr(os, "O_BINARY"):
        assert flags_seen[0] & os.O_BINARY
    path.write_bytes(b"a" * 65537)
    with pytest.raises(consumer._Failure, match="input_limit_exceeded"):
        consumer._read_input(path)
    assert len(closed) == 2


def test_input_failures_and_descriptor_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(consumer._Failure, match="input_read_failed"):
        consumer._read_input(tmp_path / "missing")
    with pytest.raises(consumer._Failure, match="input_read_failed"):
        consumer._read_input(tmp_path)
    path = tmp_path / "input"
    path.write_bytes(b"content")
    real_close = os.close
    closed: list[int] = []

    def close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(os, "close", close)
    monkeypatch.setattr(
        os,
        "fstat",
        lambda fd: os.stat_result((stat.S_IFIFO, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
    )
    with pytest.raises(consumer._Failure, match="input_read_failed"):
        consumer._read_input(path)
    assert len(closed) == 1


def test_observable_input_symlink_and_existing_output_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "input"
    path.write_bytes(b"untouched")
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda self: os.stat_result((stat.S_IFLNK, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
    )
    with pytest.raises(consumer._Failure, match="input_read_failed"):
        consumer._read_input(path)
    with pytest.raises(consumer._Failure, match="output_exists"):
        consumer._write_output(path, b"new")
    assert path.read_bytes() == b"untouched"


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX symlink/FIFO mechanisms; descriptor policies also simulated portably",
)
def test_real_symlink_and_fifo_do_not_overwrite_or_block(tmp_path: Path) -> None:
    source, link = tmp_path / "source", tmp_path / "link"
    source.write_text(_BASE, encoding="utf-8")
    link.symlink_to(source)
    with pytest.raises(consumer._Failure, match="input_read_failed"):
        consumer._read_input(link)
    with pytest.raises(consumer._Failure, match="output_exists"):
        consumer._write_output(link, b"new")
    assert source.read_text(encoding="utf-8") == _BASE
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(_SCRIPT),
            "--input",
            str(fifo),
            "--output",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2 and result.stderr == b"CODE = input_read_failed\n"


@pytest.mark.parametrize("failure", ["none", "zero", "negative", "write", "close"])
def test_short_writes_partial_files_close_and_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    output = tmp_path / "new.xml"
    real_open, real_write, real_close = os.open, os.write, os.close
    flags_seen: list[int] = []
    closes: list[int] = []
    calls = 0

    def opened(path: Path, flags: int, mode: int) -> int:
        flags_seen.append(flags)
        assert mode == 0o600
        return real_open(path, flags, mode)

    def write(fd: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            if failure in {"zero", "negative"}:
                return 0 if failure == "zero" else -1
            if failure == "write":
                raise OSError("disk full private path")
        return real_write(fd, data[:3])

    def close(fd: int) -> None:
        closes.append(fd)
        real_close(fd)
        if failure == "close":
            raise OSError("private close error")

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "close", close)
    if failure == "none":
        consumer._write_output(output, b"complete document")
    else:
        with pytest.raises(consumer._Failure, match="output_write_failed"):
            consumer._write_output(output, b"complete document")
    assert len(closes) == 1
    assert output.exists()  # Failed writes are never auto-deleted.
    assert output.read_bytes() == (
        b"complete document" if failure in {"none", "close"} else b"com"
    )
    assert flags_seen[0] & os.O_EXCL and not flags_seen[0] & os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        assert flags_seen[0] & os.O_BINARY
    if os.name != "nt":
        assert stat.S_IMODE(output.stat().st_mode) & 0o077 == 0


def test_create_failure_and_success_only_after_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(consumer._Failure, match="output_write_failed"):
        consumer._write_output(tmp_path / "missing" / "out", b"data")
    source = tmp_path / "input"
    source.write_text(_BASE, encoding="utf-8")
    real_write_output = consumer._write_output

    def write(path: Path, data: bytes) -> None:
        assert capsys.readouterr() == ("", "")
        real_write_output(path, data)
        assert capsys.readouterr() == ("", "")
        raise consumer._Failure("output_write_failed")

    monkeypatch.setattr(consumer, "_write_output", write)
    assert (
        consumer.main(["--input", str(source), "--output", str(tmp_path / "out")]) == 2
    )
    assert capsys.readouterr() == ("", "CODE = output_write_failed\n")


@pytest.mark.parametrize("optimized", [False, True])
def test_subprocess_success_and_failure_optimized(
    tmp_path: Path, optimized: bool
) -> None:
    source, output = tmp_path / "input", tmp_path / "out"
    source.write_text(_BASE, encoding="utf-8")
    command = [sys.executable, "-I"] + (["-O"] if optimized else [])
    command += [str(_SCRIPT), "--input", str(source), "--output", str(output)]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, timeout=15)
    assert result.returncode == 0 and result.stdout == b""
    assert result.stderr.decode() == _SUCCESS
    assert output.read_bytes() == (_BEFORE + _AFTER).encode()
    source.write_text('{"private":NaN}', encoding="utf-8")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, timeout=15)
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr == b"CODE = invalid_json\n"
    assert output.read_bytes() == (_BEFORE + _AFTER).encode()


def test_public_imports_no_assert_no_parser_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(node.module and "._" in node.module for node in imports)
    assert not any(
        alias.name == "parse_unsigned_dps" for node in imports for alias in node.names
    )

    def denied(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Unexpected network")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    assert consumer._document(_BASE.encode()) == (_BEFORE + _AFTER).encode()


@pytest.mark.parametrize("fault", ["open", "read", "close", "growth"])
def test_reader_operational_faults_and_growth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    path = tmp_path / "input"
    path.write_bytes(b"a")
    real_open, real_read, real_close = os.open, os.read, os.close
    closes: list[int] = []

    def opened(path: Path, flags: int) -> int:
        if fault == "open":
            raise PermissionError("private path")
        descriptor = real_open(path, flags)
        if fault == "growth":
            path.write_bytes(b"a" * 65537)
        return descriptor

    def read(descriptor: int, size: int) -> bytes:
        if fault == "read":
            raise OSError("private read failure")
        return real_read(descriptor, size)

    def close(descriptor: int) -> None:
        closes.append(descriptor)
        real_close(descriptor)
        if fault == "close":
            raise OSError("private close failure")

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "close", close)
    code = "input_limit_exceeded" if fault == "growth" else "input_read_failed"
    with pytest.raises(consumer._Failure, match=code):
        consumer._read_input(path)
    assert len(closes) == (0 if fault == "open" else 1)


def test_path_checks_precede_io_and_failures_do_not_create_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def denied(path: Path) -> NoReturn:
        raise AssertionError("Must not reach I/O")

    with monkeypatch.context() as guarded:
        guarded.setattr(consumer, "_read_input", denied)
        assert consumer.main(["--input", "ordinary", "--output", "NUL.xml"]) == 2
        assert capsys.readouterr() == ("", "CODE = invalid_file_location\n")
    output = tmp_path / "out"
    source = tmp_path / "input"
    assert consumer.main(["--input", str(source), "--output", str(output)]) == 2
    assert capsys.readouterr() == ("", "CODE = input_read_failed\n")
    assert not output.exists()
    for data in (b"\xff", b"[]", b"{}", b"{}{}", b"[" * 4, b'{"x":1.5}'):
        source.write_bytes(data)
        assert consumer.main(["--input", str(source), "--output", str(output)]) == 1
        assert capsys.readouterr().out == ""
        assert not output.exists()


def test_help_through_real_entrypoint(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), "--help"],
        cwd=tmp_path,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0 and result.stderr == b""
    assert b"usage: build_unsigned_dps_from_json.py" in result.stdout


def test_readme_input_matches_independent_oracle() -> None:
    readme = (_SCRIPT.parents[1] / "README.md").read_text(encoding="utf-8")
    section = readme.split("## JSON to unsigned DPS: reference consumer\n", 1)[1]
    example = section.split("```json\n", 1)[1].split("\n```", 1)[0]
    expected = (
        _BEFORE
        + "<toma><CPF>01234567890</CPF>"
        + _ADDRESS
        + "<xCpl>Sala A</xCpl><xBairro>Centro</xBairro></end></toma>"
        + _AFTER
    ).encode()
    assert consumer._document(example.encode()) == expected
