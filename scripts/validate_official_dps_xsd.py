"""Compile the local frozen bundle and validate a synthetic complete DPS."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from nfse_br.dps import DpsDocumentError, inspect_unsigned_dps
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
