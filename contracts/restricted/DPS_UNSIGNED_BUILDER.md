# Unsigned restricted DPS builder

## Unreleased delta — national taker candidate

The checkout adds `RestrictedDpsNationalAddress`, `RestrictedDpsTaker` and the
optional final `RestrictedDpsDraft.taker=None` parameter under the accepted
[local contract](DPS_NATIONAL_TAKER.md), subject to implementation-PR review.
This is not part of the published 0.4.1 API and requires a separate version bump
before publication. The public shape changes deliberately; old constructor
calls and XML bytes without taker remain unchanged.

When present, toma is inserted after prest and before serv: one CPF/CNPJ,
xNome, then end containing endNac(cMun, CEP), xLgr, nro, optional xCpl, xBairro.
The taker does not contribute to the DPS identity. The local policy requires
name (1–150 characters) and complete national address, allows numeric and
alphanumeric CNPJ, and preserves the documented source conflicts. No implicit
DV, registry, CEP–municipality, provider=taker or tax-rule check is introduced.
The aggregates are frozen/slots/keyword-only with controlled repr/str; fields
and recursive asdict are not redacted. The base remains stdlib-only.

## Published 0.4.1 baseline

`nfse_br.dps.builder` serializes one deliberately small subset of the frozen
restricted `TCDPS` structure. It is not a complete NFS-e model and it performs
no fiscal inference.

The fixed profile constants are:

```text
versao = 1.01
tpAmb  = 2
tpEmit = 1
root   = {http://www.sped.fazenda.gov.br/nfse}DPS
```

The caller supplies all remaining supported values through an immutable
`RestrictedDpsDraft`. `infDPS@Id` is never accepted independently; it is built
from the same issue municipality, CNPJ, series, and DPS number serialized into
the document.

## Supported mapping

| Draft input | XML path |
| --- | --- |
| `issued_at` | `DPS/infDPS/dhEmi` |
| `application_version` | `DPS/infDPS/verAplic` |
| `series` | `DPS/infDPS/serie` |
| `number` | `DPS/infDPS/nDPS` |
| `competence` | `DPS/infDPS/dCompet` |
| `issue_municipality` | `DPS/infDPS/cLocEmi` and `infDPS@Id` |
| `issuer_tax_id` | `DPS/infDPS/prest/CNPJ` and `infDPS@Id` |
| `op_simp_nac` | `DPS/infDPS/prest/regTrib/opSimpNac` |
| `reg_esp_trib` | `DPS/infDPS/prest/regTrib/regEspTrib` |
| `service_municipality` | `DPS/infDPS/serv/locPrest/cLocPrestacao` |
| `national_service_code` | `DPS/infDPS/serv/cServ/cTribNac` |
| `service_description` | `DPS/infDPS/serv/cServ/xDescServ` |
| `service_amount` | `DPS/infDPS/valores/vServPrest/vServ` |
| `trib_issqn` | `DPS/infDPS/valores/trib/tribMun/tribISSQN` |
| `tp_ret_issqn` | `DPS/infDPS/valores/trib/tribMun/tpRetISSQN` |
| `ind_tot_trib` | `DPS/infDPS/valores/trib/totTrib/indTotTrib` |

The builder preserves the lexical series in `<serie>` while the derived ID
uses the existing five-position identity component. The DPS number is emitted
without padding in `<nDPS>` and with its existing fifteen-position component in
the ID.

## Lexical policies

Service amounts must be finite, unsigned `Decimal` values between `0` and
`999999999999999.99`, exactly representable with at most two decimal places.
Serialization always emits two places and never rounds. It is independent of
the caller's decimal precision, rounding mode, flags, and traps.

Issue timestamps require an explicit whole-hour offset from `-11:00` through
`+12:00`, no microseconds, and a year from 2000 through 2099. The supplied
offset is preserved. Competence remains a civil date and must fit the frozen
`TSData` year range.

The description preserves text and LF characters, rejects CR/CRLF and XML 1.0
forbidden characters, and is escaped by the standard-library XML serializer.
No caller value is interpreted as markup. Its non-whitespace requirement uses
the XML Schema whitespace set (space, tab, LF, and CR), rather than Python's
broader Unicode `str.isspace()` classification; accepted characters such as a
non-breaking space are preserved exactly.

## Deliberate boundaries

This first subset excludes CPF/NIF providers, takers, intermediaries,
substitution, foreign trade, construction/events, deductions/discounts,
IBSCBS, federal taxes, optional fiscal groups, and `ds:Signature`. Tax codes
are declarations supplied by the caller; the builder does not determine tax
treatment or calculate values.

`build_unsigned_dps()` is a pure standard-library serialization operation. It
does not read the frozen contract at runtime and does not invoke validation.
Validation remains explicit:

```python
xml_bytes = build_unsigned_dps(draft)
validator.validate(xml_bytes)
```

The local integration against the ignored pinned ZIP is:

```console
uv run --frozen --extra xsd python scripts/validate_generated_dps.py \
  .f0/restricted/restricted-xsd.zip
```

The generated document is unsigned test data. XSD conformance does not prove
signature validity, fiscal correctness, authorization, SEFIN acceptance, or
transmission readiness. The deterministic serialization is not XML C14N and
does not calculate a signature digest. `transmission_ready` remains `false`.
