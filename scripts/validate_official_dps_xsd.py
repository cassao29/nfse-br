"""Compile the local frozen bundle and validate a synthetic complete DPS."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from pathlib import Path

from lxml import etree

from nfse_br.xsd import RestrictedDpsXsdValidator, XsdValidationError

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
        mutations = {
            "nDPS zero": _VALID_DPS.replace(b"<nDPS>42</nDPS>", b"<nDPS>0</nDPS>"),
            "required field removed": _VALID_DPS.replace(
                b"    <tpAmb>2</tpAmb>\n", b""
            ),
            "field order changed": _VALID_DPS.replace(
                b"    <serie>123</serie>\n    <nDPS>42</nDPS>",
                b"    <nDPS>42</nDPS>\n    <serie>123</serie>",
            ),
            "root namespace changed": _VALID_DPS.replace(
                b"http://www.sped.fazenda.gov.br/nfse", b"urn:wrong"
            ),
        }
        for label, invalid in mutations.items():
            try:
                validator.validate(invalid)
            except XsdValidationError as exc:
                if exc.phase != "schema" or exc.code != "document_invalid":
                    raise
            else:
                print(f"Official integration: {label} was unexpectedly accepted.")
                return 1
    except XsdValidationError as exc:
        print(f"Official integration: {exc}")
        return 1

    print(f"Bundle SHA-256: {hashlib.sha256(bundle).hexdigest()}")
    print(f"lxml: {'.'.join(map(str, etree.LXML_VERSION[:3]))}")
    print(f"libxml2: {'.'.join(map(str, etree.LIBXML_VERSION))}")
    print("Synthetic complete DPS: PASS")
    for label in mutations:
        print(f"Mutation {label}: REJECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
