# Restricted unsigned DPS semantic parser

Development API after 0.3.0; not part of the immutable published 0.3.0 contract:

```python
from nfse_br.dps import parse_unsigned_dps

draft = parse_unsigned_dps(xml_bytes)  # RestrictedDpsDraft
```

This is exclusively the inverse of the supported local restricted
[`build_unsigned_dps`](DPS_UNSIGNED_BUILDER.md) subset, not a generic national
DPS parser. It adds no normative evidence or fiscal rules. The existing
`RestrictedDpsDraft` remains the only draft model and validates recovered
values. The builder and the identity-only `inspect_unsigned_dps` behavior
remain unchanged. `RestrictedDpsChecker.parse` is not implemented here.

## Boundary and closed structure

Input must be exact `bytes`, nonempty, at most 1 MiB, accepted by the existing
safe UTF-8 XML parser. DTDs/entities and malformed XML are rejected. The shared
inspection requires the DPS namespace, root `DPS`, version `1.01`, no
`Signature`, exactly one direct `infDPS`, `tpAmb=2`, `tpEmit=1`, and an identity
recomposed from the observed municipality, CNPJ, series, and number.

The parser additionally requires the exact ordered element tree emitted by
the builder. The only supported attributes are `DPS@versao` and `infDPS@Id`.
All other attributes, missing/duplicate/moved/reordered elements, foreign
namespaces, unknown elements, mixed content, and additional fiscal groups are
rejected. No taker, intermediary, substitution, IBSCBS or other unsupported
branch is silently discarded, even if XSD-valid.

Whitespace-only indentation using XML whitespace is allowed between elements;
leaf text is never stripped. Namespace prefix spelling and equivalent XML
escaping are syntax, not draft fields. Comments, processing instructions, and
raw CR bytes are conservatively rejected instead of silently discarded or
normalized by the shared parser. This restriction also applies to such raw
markup tokens inside CDATA; builder output always escapes text instead.
Character-reference CR in leaf text is subject to the draft's existing rules.

## Field mapping

All sixteen public fields are recovered using the builder's existing mapping:

| Draft field | Path below `DPS/infDPS` |
| --- | --- |
| `issuer_tax_id` | `prest/CNPJ` |
| `issue_municipality` | `cLocEmi` |
| `service_municipality` | `serv/locPrest/cLocPrestacao` |
| `series` | `serie` (lexical alias preserved) |
| `number` | `nDPS` |
| `issued_at` | `dhEmi` |
| `competence` | `dCompet` |
| `application_version` | `verAplic` |
| `national_service_code` | `serv/cServ/cTribNac` |
| `service_description` | `serv/cServ/xDescServ` |
| `service_amount` | `valores/vServPrest/vServ` |
| `op_simp_nac` | `prest/regTrib/opSimpNac` |
| `reg_esp_trib` | `prest/regTrib/regEspTrib` |
| `trib_issqn` | `valores/trib/tribMun/tribISSQN` |
| `tp_ret_issqn` | `valores/trib/tribMun/tpRetISSQN` |
| `ind_tot_trib` | `valores/trib/totTrib/indTotTrib` |

Amounts use only canonical unsigned decimal notation with two fractional
digits and at most fifteen integer digits. The integer part is either a single
`0` (for example `0.00` or `0.01`) or has no leading zeros.
Conversion uses `Decimal`, never float, rounding, or the caller's
decimal precision. Exponents, signs, NaN/infinity and additional fractional
digits are rejected. Existing draft invariants remain authoritative.

Timestamps require `YYYY-MM-DDTHH:MM:SS+HH:00` or its negative-offset form,
whole-hour offsets from -11 through +12 and years 2000 through 2099. `Z`,
`-00:00`, fractional seconds and implicit timezone conversion are not accepted.
Calendar validity and profile constraints reuse the standard date types and
the draft. No microseconds are introduced; competence remains a civil date.

## Round-trip guarantee and datetime equality

For builder-generated XML:

```python
xml = build_unsigned_dps(draft)
parsed = parse_unsigned_dps(xml)
assert build_unsigned_dps(parsed) == xml
```

All represented values are preserved, including escaped `&`, `<`, `>`, Unicode,
LF, lexical series, exact amount, and timestamp year/month/day/hour/minute/second
and UTC offset. The parser reconstructs a fixed-offset `datetime` and does not
normalize it to UTC. With ordinary fixed-offset datetimes, `parsed == draft`.

The builder already accepts regional `tzinfo` objects and ambiguous repeated
hours. XML contains neither the regional zone nor `fold`; Python inter-zone
datetime equality can therefore be false even when wall time, offset and
instant are identical (for example a repeated `01:30:00-05:00`). No universal
Python draft-equality promise is made for these values. The builder is not
restricted or changed to hide this limitation. Byte-exact rebuilding of its
output still holds. Regional zone identity and Decimal exponent metadata are
not recoverable serialization fields.

Arbitrary XML formatting is not preserved byte-for-byte. Successful parsing
never implies generic XSD conformance or support for the full DPS model.

## Errors and privacy

The API uses `DpsDocumentError`, preserving existing inspection codes and
adding only:

- `unsupported_document_structure`: content outside the closed subset;
- `invalid_document_fields`: noncanonical lexical values or draft violations.

Calendar/domain conversion errors are translated without displayed chaining.
Messages, repr and ordinary formatted tracebacks contain controlled codes,
not XML, CNPJ, DPS Id, descriptions or monetary values. As with any Python
call handling data, callers must not log traceback locals or input arguments.

## No external capabilities unlocked

Stdlib only; no network, filesystem I/O, lxml requirement, signature
verification/signing, certificates, fiscal inference/authorization, access-key
conversion, HTTP/SEFIN, persistence or transmission. No evidence contract or
pin changes. The independently permitted local parser does not unblock the
external runtime axes:

```text
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTATION_READY = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
TECHNICAL_QUERY_RESPONSE = PENDING
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
TRANSMISSION_READY = NO
V0_3_0_IMMUTABLE = YES
RUNTIME_DEVELOPMENT_BLOCKED_BY_OFFICIAL_EVIDENCE = YES
```
