"""Compile the local frozen bundle and validate a synthetic complete DPS."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from lxml import etree

from nfse_br.domain import CompetenceDate, FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsDocumentError, DpsNumber, DpsSeries, inspect_unsigned_dps
from nfse_br.dps.builder import (
    RestrictedDpsDraft,
    RestrictedDpsNationalAddress,
    RestrictedDpsTaker,
    build_unsigned_dps,
)
from nfse_br.xsd import (
    RestrictedDpsChecker,
    RestrictedDpsXsdValidator,
    XsdValidationError,
)

_VALID_DPS = b"""<?xml version="1.0" encoding="UTF-8"?>
<DPS xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
  <infDPS Id="DPS2927408212ABC6780001Z000123000000000000042">
    <tpAmb>2</tpAmb>
    <dhEmi>2026-09-17T12:00:00-03:00</dhEmi>
    <verAplic>nfse-br-test</verAplic>
    <serie>123</serie>
    <nDPS>42</nDPS>
    <dCompet>2026-09-17</dCompet>
    <tpEmit>1</tpEmit>
    <cLocEmi>2927408</cLocEmi>
    <prest>
      <CNPJ>12ABC6780001Z0</CNPJ>
      <regTrib><opSimpNac>1</opSimpNac><regEspTrib>0</regEspTrib></regTrib>
    </prest>
    <serv>
      <locPrest><cLocPrestacao>2927408</cLocPrestacao></locPrest>
      <cServ>
        <cTribNac>010101</cTribNac>
        <xDescServ>Servico sintetico</xDescServ>
      </cServ>
    </serv>
    <valores>
      <vServPrest><vServ>1.00</vServ></vServPrest>
      <trib>
        <tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun>
        <totTrib><indTotTrib>0</indTotTrib></totTrib>
      </trib>
    </valores>
  </infDPS>
</DPS>
"""

_VALID_XMLDSIG_ROOT = b"""<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
  <SignedInfo>
    <CanonicalizationMethod Algorithm="urn:synthetic"/>
    <SignatureMethod Algorithm="urn:synthetic"/>
    <Reference URI="">
      <DigestMethod Algorithm="urn:synthetic"/>
      <DigestValue>AA==</DigestValue>
    </Reference>
  </SignedInfo>
  <SignatureValue>AA==</SignatureValue>
</Signature>
"""


class FixtureMutationError(ValueError):
    """Raised when an integration fixture cannot be changed unambiguously."""


@dataclass(frozen=True, slots=True)
class _NegativeCase:
    label: str
    xml: bytes
    expected_code: str


def _replace_exactly_once(
    source: bytes,
    target: bytes,
    replacement: bytes,
    *,
    label: str,
) -> bytes:
    count = source.count(target)
    if count != 1:
        raise FixtureMutationError(
            f"fixture mutation {label!r} expected one target, observed {count}"
        )
    mutated = source.replace(target, replacement, 1)
    if mutated == source:
        raise FixtureMutationError(f"fixture mutation {label!r} made no change")
    return mutated


def _negative_cases() -> tuple[_NegativeCase, ...]:
    return (
        _NegativeCase(
            "nDPS zero",
            _replace_exactly_once(
                _VALID_DPS,
                b"<nDPS>42</nDPS>",
                b"<nDPS>0</nDPS>",
                label="nDPS zero",
            ),
            "document_invalid",
        ),
        _NegativeCase(
            "required field removed",
            _replace_exactly_once(
                _VALID_DPS,
                b"    <tpAmb>2</tpAmb>\n",
                b"",
                label="required field removed",
            ),
            "document_invalid",
        ),
        _NegativeCase(
            "field order changed",
            _replace_exactly_once(
                _VALID_DPS,
                b"    <serie>123</serie>\n    <nDPS>42</nDPS>",
                b"    <nDPS>42</nDPS>\n    <serie>123</serie>",
                label="field order changed",
            ),
            "document_invalid",
        ),
        _NegativeCase(
            "root namespace changed",
            _replace_exactly_once(
                _VALID_DPS,
                b"http://www.sped.fazenda.gov.br/nfse",
                b"urn:wrong",
                label="root namespace changed",
            ),
            "unexpected_root",
        ),
        _NegativeCase(
            "isolated XMLDSig root",
            _VALID_XMLDSIG_ROOT,
            "unexpected_root",
        ),
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Frozen restricted XSD ZIP")
    return parser.parse_args(argv)


_TAKER_ADDRESS = (
    b"<end><endNac><cMun>3550308</cMun><CEP>01234567</CEP></endNac>"
    b"<xLgr>Rua Sintetica</xLgr><nro>1</nro><xCpl>Sala A</xCpl>"
    b"<xBairro>Centro</xBairro></end>"
)


def _taker_vectors() -> tuple[tuple[bytes, RestrictedDpsDraft], ...]:
    """Independent literal XML and independently constructed model inputs."""
    vectors = []
    for kind, value in (
        ("CPF", "12345678901"),
        ("CNPJ", "12345678000199"),
        ("CNPJ", "98ABC6780001Z0"),
    ):
        taker_xml = (
            f"<toma><{kind}>{value}</{kind}><xNome>Synthetic taker</xNome>".encode()
            + _TAKER_ADDRESS
            + b"</toma>"
        )
        xml = _replace_exactly_once(
            _VALID_DPS, b"    <serv>", taker_xml + b"\n    <serv>", label="taker"
        )
        draft = RestrictedDpsDraft(
            issuer_tax_id=FederalTaxId.cnpj("12ABC6780001Z0"),
            issue_municipality=MunicipalityCode("2927408"),
            service_municipality=MunicipalityCode("2927408"),
            series=DpsSeries("123"),
            number=DpsNumber(42),
            issued_at=datetime(2026, 9, 17, 12, tzinfo=timezone(timedelta(hours=-3))),
            competence=CompetenceDate(date(2026, 9, 17)),
            application_version="nfse-br-test",
            national_service_code="010101",
            service_description="Servico sintetico",
            service_amount=Decimal("1.00"),
            op_simp_nac="1",
            reg_esp_trib="0",
            trib_issqn="1",
            tp_ret_issqn="1",
            ind_tot_trib="0",
            taker=RestrictedDpsTaker(
                tax_id=FederalTaxId.cpf(value)
                if kind == "CPF"
                else FederalTaxId.cnpj(value),
                name="Synthetic taker",
                address=RestrictedDpsNationalAddress(
                    municipality=MunicipalityCode("3550308"),
                    postal_code="01234567",
                    street="Rua Sintetica",
                    number="1",
                    complement="Sala A",
                    neighborhood="Centro",
                ),
            ),
        )
        vectors.append((xml, draft))
    return tuple(vectors)


def _validate_takers(checker: RestrictedDpsChecker) -> None:
    for oracle, draft in _taker_vectors():
        built = build_unsigned_dps(draft)
        if checker.parse(oracle) != draft or checker.parse(built) != draft:
            raise FixtureMutationError("taker field recovery drifted")
        if build_unsigned_dps(checker.parse(built)) != built:
            raise FixtureMutationError("taker rebuild drifted")
        if checker.check(oracle) != checker.check(_VALID_DPS):
            raise FixtureMutationError("taker altered DPS identity")
        for replacement in (b"X" * 150,):
            boundary = oracle.replace(b"Synthetic taker", replacement)
            checker.parse(boundary)
        # XSD-valid documents that intentionally exceed the local subset.
        for outside in (
            oracle.replace(b"Synthetic taker", b"X" * 151),
            oracle.replace(b"Synthetic taker", b"X" * 300),
            oracle.replace(_TAKER_ADDRESS, b""),
        ):
            checker.check(outside)
            try:
                checker.parse(outside)
            except DpsDocumentError as exc:
                if exc.code not in {
                    "invalid_document_fields",
                    "unsupported_document_structure",
                }:
                    raise
            else:
                raise FixtureMutationError("outside-subset taker was parsed")
            checker.parse(built)
        for invalid in (
            oracle.replace(b"Synthetic taker", b"X" * 301),
            oracle.replace(b"<xNome>Synthetic taker</xNome>", b""),
            oracle.replace(b"<CEP>01234567</CEP>", b""),
            oracle.replace(b"Sala A", b""),
            oracle.replace(b"</endNac>", b"<UF>SP</UF></endNac>"),
            oracle.replace(b"<xNome>", b"<CPF>12345678901</CPF><xNome>"),
            oracle.replace(b"<toma>", b'<toma xmlns="urn:wrong">'),
        ):
            try:
                checker.check(invalid)
            except XsdValidationError as exc:
                if exc.phase != "schema" or exc.code != "document_invalid":
                    raise
            else:
                raise FixtureMutationError("invalid taker passed XSD")
            checker.check(built)
    print(
        "National taker independent oracles and builder outputs: PASS (CPF/CNPJ/alpha)"
    )
    print("National taker XSD/check/parse boundaries and valid-invalid-valid: PASS")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the explicit local integration without downloading anything."""
    args = _parse_args(argv)
    try:
        bundle = args.bundle.read_bytes()
    except OSError:
        print("Official integration: bundle could not be read.")
        return 2

    try:
        validator = RestrictedDpsXsdValidator(bundle)
        validator.validate(_VALID_DPS)
        _validate_takers(RestrictedDpsChecker(bundle))
        identity = inspect_unsigned_dps(_VALID_DPS)
        if identity.value != "DPS2927408212ABC6780001Z000123000000000000042":
            print("Official integration: unsigned DPS inspection drifted.")
            return 1
        checked_identity = RestrictedDpsChecker(bundle).check(_VALID_DPS)
        if checked_identity != identity or checked_identity.value != identity.value:
            print("Official integration: composed DPS check drifted.")
            return 1
        negative_cases = _negative_cases()
        for case in negative_cases:
            try:
                validator.validate(case.xml)
            except XsdValidationError as exc:
                if exc.phase != "schema" or exc.code != case.expected_code:
                    raise
            else:
                print(f"Official integration: {case.label} was unexpectedly accepted.")
                return 1
        validator.validate(_VALID_DPS)
    except FixtureMutationError:
        print("Official integration: fixture preparation failed.")
        return 2
    except (DpsDocumentError, XsdValidationError) as exc:
        print(f"Official integration: {exc}")
        return 1

    print(f"Bundle SHA-256: {hashlib.sha256(bundle).hexdigest()}")
    print(f"lxml: {'.'.join(map(str, etree.LXML_VERSION[:3]))}")
    print(f"libxml2: {'.'.join(map(str, etree.LIBXML_VERSION))}")
    print("Synthetic complete DPS: PASS")
    print("Synthetic unsigned DPS inspection: PASS")
    print("Synthetic composed restricted DPS check: PASS")
    for case in negative_cases:
        print(f"Negative case {case.label}: REJECTED")
    print("Sequential valid-invalid-valid state: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
