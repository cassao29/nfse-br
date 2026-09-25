# Proposed restricted DPS national taker contract

```text
CONTRACT_STATUS = PROPOSED_FOR_REVIEW
TARGET_RELEASE = 0.5.0 — candidate
IMPLEMENTATION_AUTHORIZED = NO
CURRENT_RELEASE_SUPPORTS_TAKER = NO
OFFICIAL_CONFLICTS_RESOLVED = NO
```

## 1. Status and applicability

This document proposes a closed national-taker subset, not an implemented API
or a confirmation of operational acceptance by SEFIN. The audited base is
`0b4f098da4e51e105ac9055c2da906d1e2217c2e` (nfse-br 0.4.1).
The current [builder](DPS_UNSIGNED_BUILDER.md) and
[parser](DPS_DOCUMENT_PARSER.md) contracts remain unchanged. Implementation,
public-oracle changes and the candidate 0.5.0 release require separate review.

The audit applies only to the local official artifacts pinned in
[manifest.json](manifest.json):

| Source | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| Produção Restrita XSD ZIP, label `NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727` | 34933 | `6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc` |
| Anexo I, label `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209` | 215056 | `2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9` |

Both original files were read locally and their pins checked. The
[structural map](dps-schema-contract.json) and its
[description](DPS_SCHEMA_CONTRACT.md) guided navigation; they did not replace
the original XSD and spreadsheet. No source was downloaded, refreshed or
regenerated for this proposal. No claim is made about later official versions.

Evidence classifications here are `CURRENT_CONFIRMED` (within the pinned
profile), `CURRENT_PARTIAL`, `CONFLICTING`, `HISTORICAL_ONLY` and `UNCONFIRMED`.
Local product policies are explicitly separate from those classifications.
The overall evidence remains **CONFLICTING**, even where a narrower local
policy makes implementation possible.

## 2. Audited evidence matrix

### Reference notation

`XC` means ZIP member `tiposComplexos_v1.01.xsd`; `XS` means
`tiposSimples_v1.01.xsd`. Their audited SHA-256 values are respectively
`6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac`
and `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4`.
`DPS_v1.01.xsd` declares `DPS` with type `TCDPS`.

Every `n:` element below is in `http://www.sped.fazenda.gov.br/nfse`.
`T` expands to the complete standalone path `/n:DPS/n:infDPS/n:toma`;
all suffix components in the tables also carry `n:`. Elements are qualified.
The layout uses the embedded prefix `NFSe/infNFSe/DPS/infDPS/` instead.

`L` refers to the sheet **`LEIAUTE DPS_NFS-e `** (including its trailing space).
`R` refers to **`RN DPS_NFS-e`**. Row numbers are physical Excel row numbers,
not the ordinal values in column A. In L: B=path, C=field, D=element kind,
E=type classification, F=occurrence, G=size, H=description, I=notes.

### Structure and selected lexical types

Occurrences refer to the containing group: a required child of an optional
group is required only when that group occurs. All maxima below are one;
identification and address alternatives are choices, not independent fields.

| Expanded path | XSD member/type, order and occurrence | Lexical evidence | Exact layout cells | Classification / proposed treatment |
| --- | --- | --- | --- | --- |
| `T` | XC `TCInfDPS/toma`, sequence position 13, `0..1`, type `TCInfoPessoa`; after `prest`, before `interm` and `serv` | Complex group | L B144:F144 | `CURRENT_CONFIRMED`; optional draft field, not universal fiscal optionality |
| `T/CNPJ` or `T/CPF` | XC `TCInfoPessoa`, first particle: required choice of CNPJ, CPF, NIF or cNaoNIF; each alternative `1..1` | XS `TSCNPJ`: string, preserve, maxLength 14, `[0-9A-Z]{14}`; `TSCPF`: string, preserve, maxLength 11, `[0-9]{11}` | L B145:G146; E145=`N`, G145=14 | CNPJ `CONFLICTING`; choose XSD lexical space locally. CPF `CURRENT_CONFIRMED` lexically. Exactly one chosen identifier |
| `T/xNome` | XC `TCInfoPessoa`, fourth sequence particle after choice, CAEPF?, IM?; `1..1` | XS `TSNomeRazaoSocial`: string, preserve, minLength 1, maxLength **300**, not TSString | L B151:G151; G151=**150** | `CONFLICTING`; local limit 1–150 |
| `T/end` | XC `TCInfoPessoa`, fifth particle, `0..1`, `TCEndereco` | Complex group | L B152:F152 | `CURRENT_CONFIRMED` structurally; locally required with taker |
| `T/end/endNac` | XC `TCEndereco`, first particle: required choice endNac/endExt; `TCEnderNac` | National address is represented by this branch, not inferred from tax ID alone | L B153:F153, B156:F156 | `CURRENT_CONFIRMED`; require endNac, exclude endExt |
| `T/end/endNac/cMun` | XC `TCEnderNac`, first child, `1..1` | XS `TSCodMunIBGE`: string, preserve, `[0-9]{7}` | L B154:H154 | `CURRENT_CONFIRMED` lexical; no IBGE lookup implied |
| `T/end/endNac/CEP` | XC `TCEnderNac`, second child, `1..1` | XS `TSCEP`: string, preserve, `[0-9]{8}` | L B155:H155 | `CURRENT_CONFIRMED` lexical; no postal lookup implied |
| `T/end/xLgr` | XC `TCEndereco`, second particle, `1..1` | XS `TSLogradouro`, TSString restriction, length 1–255 | L B161:G161 | `CURRENT_CONFIRMED`; required |
| `T/end/nro` | XC `TCEndereco`, third particle, `1..1` | XS `TSNumeroEndereco`, TSString restriction, length 1–60 | L B162:G162 | `CURRENT_CONFIRMED`; string, not integer |
| `T/end/xCpl` | XC `TCEndereco`, fourth particle, `0..1` | XS `TSComplementoEndereco`, TSString restriction, length 1–156 | L B163:G163 | `CURRENT_CONFIRMED`; None absent, empty rejected |
| `T/end/xBairro` | XC `TCEndereco`, fifth particle, `1..1` | XS `TSBairro`, TSString restriction, length 1–60 | L B164:G164 | `CURRENT_CONFIRMED`; required |

XS `TSString` has base `xs:string`, `whiteSpace=preserve`, and pattern
`[!-ÿ]{1}[ -ÿ]{0,}[!-ÿ]{1}|[!-ÿ]{1}`. Preserve its actual ranges and
whole-value semantics; do not substitute `isprintable()` or normalize Unicode.
There is no UF child in XC `TCEnderNac` or this `TCEndereco` sequence.

### Audited alternatives excluded from this proposal

| Path | Exact XSD reference and occurrence | Layout reference | Evidence / boundary |
| --- | --- | --- | --- |
| `T/NIF`, `T/cNaoNIF` | XC `TCInfoPessoa` first choice; XS `TSNIF` string preserve 1–40; `TSCodNaoNIF` string preserve enum 0/1/2 | L B147:I148 | `CURRENT_CONFIRMED` structure; I148 restricts 0 to municipal ADN sharing; excluded |
| `T/CAEPF`, `T/IM` | XC `TCInfoPessoa` particles 2/3, each `0..1`; XS `TSCAEPF` string preserve, max 14, `[0-9]{14}`; `TSInscMun` string preserve 1–15 | L B149:G150 | `CURRENT_CONFIRMED` structure; excluded; IM rule conflict below |
| `T/end/endExt` | XC `TCEndereco` choice, `TCEnderExt` sequence cPais, cEndPost, xCidade, xEstProvReg, all `1..1`; XS `TSCodPaisISO` `[A-Z]{2}`, `TSCodigoEndPostal` 1–11, `TSCidade`/`TSEstadoProvRegiao` 1–60 | L B156:G160 | `CURRENT_CONFIRMED` structure; foreign address excluded |
| `T/fone`, `T/email` | XC `TCInfoPessoa` particles 6/7, each `0..1`; XS `TSTelefone` string preserve `[0-9]{6,20}`; `TSEmail` TSString, preserve, 1–80 | L B165:H166 | `CURRENT_CONFIRMED` structure; email operational semantics `CURRENT_PARTIAL`; both excluded |

### Conditional rules and applicability, not automatic library validators

R D=rule text, F=application obligation, G=effect, H=error code, I=message,
J=validation level. Columns K/L/M/N encode execution applicability (`V`/`X`):
K=national public emitter generation/provider-emitted DPS reception,
L=national public emitter generation under judicial/administrative decision
(`cStat=102`), M=municipal NFS-e sharing with ADN, N=that sharing flow under
judicial/administrative decision (`cStat=102`).
The tuples below preserve all four flags in that order. They are not a promise
that the library implements the rule or that SEFIN will accept a document.

| Rule and exact cells | K/L/M/N | Evidence and scope impact |
| --- | --- | --- |
| R D237, H237=`E0187`, J237=2 | V/X/V/X | toma required for listed cIndOp values; `CURRENT_CONFIRMED` rule text, not universal optionality |
| R D238, H238=`E0188`, J238=1; D244, H244=`E0206`, J244=1 | V/V/V/V | CNPJ/CPF DV checks are distinct from XSD lexical acceptance; no implicit DV in this proposal |
| R D239, H239=`E0190`, J239=2; D245, H245=`E0207`, J245=2 | V/V/X/X | Registration at competence date; external registry state is `UNCONFIRMED`, no lookup |
| R D241, H241=`E0202`, J241=2 | V/X/X/X | Full provider/taker CNPJ equality prohibition is a fiscal rule; deliberately not added to builder/parser |
| R D242, H242=`E0204`, J242=2 | V/X/V/X | tpRetISSQN=2 requires CPF/CNPJ; no new withholding calculation or general fiscal validator |
| R D248, H248=`E0223`, J248=2; D264, H264=`E0242`, J264=1 | V/X/V/X | Foreign-address/foreign-ID dependencies; excluded, not inferred away by selecting CPF/CNPJ |
| R D253/I253, H253=`E0228`, J253=2 | V/X/X/X | IM text conflicts about emitter role; see section 3 |
| R D257, H257=`E0233`, J257=1 | V/X/V/X | NIF implies name; does not permit omission for CPF/CNPJ, because XSD already requires xNome |
| R D258, H258=`E0234`, J258=2 | V/V/V/V | Address required by incidence at taker or listed cIndOp; local policy always requires address with taker |
| R D259, H259=`E0235`, J259=1 | **X/X/V/X** | tpEmit=1 plus CNPJ requires endNac in the stated sharing context; not a universal DPS-reception enforcement claim |
| R D260, H260=`E0236`, J260=1 | V/X/V/X | tpEmit=2 forbids endNac; emitter=2 remains excluded |
| R D261, H261=`E0237`, J261=1 | V/X/V/X | tpRetISSQN=2 requires endNac except emitter=2; not a new calculation rule |
| R D262, H262=`E0238`, J262=1 | V/V/V/V | IBGE existence differs from seven-digit lexical validity |
| R D263, H263=`E0240`, J263=1 | V/X/V/X | CEP existence and municipality relation differ from eight-digit lexical validity |
| R D274, H274=`E0247`, J274=2 | V/X/V/X | Email structure is more than the XSD length/TSString; excluded |

R D237/D258 list cIndOp values 030102, 050102, 100101, 100301, 100501,
030103, 050103, 100102, 100201, 100302, 100401, 100502 and 100601.
L B339:C339 locates cIndOp under IBSCBS, which remains excluded. R D258 also
references `MUN.INCID_INFO.SERV.`: A277=170501 and E277=`X` mark an incidence
case at the taker. These dependencies prevent interpreting an optional Python
field as fiscal permission to omit the taker. This proposal neither adds
IBS/CBS nor claims complete incidence-rule coverage.

## 3. Unresolved discrepancies

| Classification | Sources | Explicit decision, not resolution |
| --- | --- | --- |
| `CONFLICTING` | XS `TSCNPJ` permits uppercase letters; L E145 classifies CNPJ as numeric (`N`) | Admit the frozen XSD lexical space, consistently with the existing domain/provider. No SEFIN acceptance claim |
| `CONFLICTING` | XS `TSNomeRazaoSocial` maxLength 300 versus L G151 size 150 | Limit the proposed subset to 150. Names of 151–300 characters may be XSD-valid but outside the subset |
| `CONFLICTING` | R D253 says provider with tpEmit=2, while L H109 defines 2 as taker and R I253 names the taker emitter | Preserve the contradiction; IM and emitter=2 stay out of scope |
| `CURRENT_PARTIAL` | XS `TSEmail` versus R D274 operational email structure | Do not infer complete operational email validity; exclude contact fields |

No discrepancy is silently resolved by the derived structural JSON. A local
subset choice does not promote conflicting official evidence to
`CURRENT_CONFIRMED`. Operational acceptance, registry status and comprehensive
fiscal validity remain `UNCONFIRMED` by this audit.

## 4. Proposed local policies

The unchanged profile is provider CNPJ, `tpAmb=2`, `tpEmit=1`, unsigned DPS,
and the existing national-service subset. Taker is optional only as a library
compatibility choice. Never emit an empty toma. When present, require exactly
one CPF/CNPJ, name and complete endNac-based address. Do not infer nationality
from CPF/CNPJ alone: the selected address branch is part of this local profile,
not proof of citizenship, residence or registration.

For names, require 1–150 characters, preserve supplied text, and reject a value
consisting exclusively of SP/TAB/LF/CR, any CR, and XML 1.0 forbidden characters.
TAB/LF with content and leading/trailing spaces are preserved. No strip,
uppercase, Unicode normalization or truncation. Length is not UTF-8 byte length;
see [XML Schema string length](https://www.w3.org/TR/xmlschema-2/#rf-length).
Do not apply address TSString restrictions to xNome.

Reject both CR in a Python value and CR recovered from `&#13;`. Keep the
parser's existing raw-CR rejection: XML line-ending normalization and character
references are distinct mechanisms ([XML 1.0](https://www.w3.org/TR/xml/#sec-line-ends)).
Escaped markup in a name remains text, never child elements.

Address values follow the types and limits in section 2. Preserve accents and
the exact accepted code points; no trimming, case conversion, reindentation or
Unicode normalization. Test composed/decomposed strings separately. TSString
excludes edge spaces and characters outside its specified ranges, not whatever
a host-language printability predicate excludes. Translating the expression
requires matching [XSD regex semantics](https://www.w3.org/TR/xmlschema-2/#regexs),
not mechanically copying it into another regex engine. No UF is modeled or
serialized. Complement None means omission; an empty complement is rejected.

`FederalTaxId.cnpj()` retains its existing construction-time uppercase
normalization. Parsing XML must compare the constructed identifier with the
received text and reject normalization, including lowercase CNPJ. No implicit
DV check, registry query, tax calculation or provider=taker rejection is added.
Lexical validity, mathematical DV validity, registry state, fiscal rules and
local policy are different guarantees.

## 5. Proposed public shape — not available in 0.4.1

Proposed module: `nfse_br.dps.builder`. These are declarations for review,
not importable additions made by this document:

```text
RestrictedDpsNationalAddress
  municipality: MunicipalityCode
  postal_code: str
  street: str
  number: str
  neighborhood: str
  complement: str | None = None

RestrictedDpsTaker
  tax_id: FederalTaxId
  name: str
  address: RestrictedDpsNationalAddress

RestrictedDpsDraft
  existing 16 public fields, in their current order
  taker: RestrictedDpsTaker | None = None
```

The two new aggregates would be frozen, slots-based and keyword-only, with
controlled repr/str, equality over their fields, and hashes consistent with
equality. No separate public CEP/street/number/neighborhood value objects,
ExtendedDpsDraft, wrapper or new hierarchy are proposed.

Keep issuer_tax_id, issue_municipality, service_municipality, series, number,
issued_at, competence, application_version, national_service_code,
service_description, service_amount, op_simp_nac, reg_esp_trib, trib_issqn,
tp_ret_issqn and ind_tot_trib unchanged. Append only the optional public taker
parameter; internal init=False fields remain implementation details.

Serialization order is the XSD order, not Python argument convenience:
after prest, emit toma with CPF or CNPJ, then xNome, then end; inside end emit
endNac(cMun, CEP), xLgr, nro, optional xCpl, xBairro. Never emit excluded branches.

## 6. Coordinated inspection, builder and parser evolution

At the audited base, [`document.py`](../../src/nfse_br/dps/document.py)
`_unique_text()` counts local names across all descendants; a legitimate second
CNPJ therefore collides with the issuer. `_collect_subset()` indexes by local
name, without role/path. Merely adding toma serialization would be incorrect.

The proposed inspector must permit the additional identifier only at the exact
namespace-qualified path T/CNPJ (or T/CPF), under one direct toma child of the
single infDPS. Require a single non-conflicting identification alternative in
that group. Reject duplicated groups/identifiers, conflicting choices, wrappers,
displacement into serv, and foreign-namespace lookalikes. Do not implement an
"at most two CNPJs" rule or indiscriminately ignore other CNPJs.

DPS identity remains derived exclusively from the existing DPS/provider fields.
Preserve defenses for additional Id/xml:id attributes, root/infDPS ambiguity,
identity mismatch, unsafe XML and incompatible profiles. Inspection does not
certify all taker name/address semantics or apply the entire local subset.
Regression-test the private
[`_xmlsig.preflight`](../../src/nfse_br/_xmlsig/preflight.py) adapter, which
delegates to the public inspector and maps its controlled errors. This grants
no signing capability and does not make that private adapter public.

The parser collector must distinguish paths/roles, recover all represented
values without overwriting the issuer CNPJ, and reject unrepresentable branches
rather than discard them. Builder and parser must evolve together.

| Operation | Proposed responsibility retained |
| --- | --- |
| `inspect_unsigned_dps()` | Safe identity/profile inspection; not full taker validation |
| `parse_unsigned_dps()` | Closed, ordered, representable subset including local policies |
| `RestrictedDpsChecker.check()` | XSD, then identity inspection |
| `RestrictedDpsChecker.parse()` | XSD, then subset parsing |

The [checker](../../src/nfse_br/xsd/dps_checker.py) pipelines remain independent:
same input bytes object, XSD first, short-circuit on failure, original exception
identity preserved. Do not make check call parse. An XSD-valid document with
name length 151–300 or without the locally required address can pass check
and fail parse. Outside the subset does not mean invalid according to XSD.

For future rejection mapping, use existing DomainValidationError for invalid
construction and DpsDocumentError categories such as invalid_document_fields,
unsupported_document_structure, ambiguous_identity_field and existing identity
codes where appropriate. XsdValidationError remains the XSD-layer error.
Do not preemptively introduce an error family or expose rejected values.

## 7. Compatibility and privacy

Old construction calls remain valid and old drafts serialize to exactly the
same golden bytes with unchanged identity; their parsed result has taker=None.
This is not a blanket claim that an optional field makes every public contract
unchanged. Constructor signatures, exports and dataclasses.fields change;
asdict gains a field and recursive aggregates; replace must preserve/revalidate
the new field; equality distinguishes different takers. Equal objects must
have equal hashes, without promising the same numeric hash across versions.

The parser's accepted language expands deliberately. The
[public oracle](../../tests/test_public_api_contract.py) must remain untouched
in this PR and change only after explicit API/versioning review during a future
implementation. Existing 0.4.1 releases and contracts remain historical truth.
Builder-output build/parse/rebuild remains byte-exact; arbitrary accepted
external XML does not acquire that guarantee. Existing datetime/offset/fold
caveats remain applicable.

Library-generated repr, str and errors must not expose identifiers, names,
addresses or XML payloads. This is not a secret-container guarantee:
[dataclasses.asdict](https://docs.python.org/3.14/library/dataclasses.html#dataclasses.asdict)
recurses into fields, and explicit fields/serialization contain caller data.
Introspection, local-variable capture and external logging are not redacted by
this contract. In particular, existing FederalTaxId.__str__ returns the
identifier and must not change incidentally. Test exception chaining and
diagnostics as well as direct repr; use synthetic data only.

## 8. Future tests and acceptance criteria

The following are intended **future** results, assuming all unrelated profile
fields are valid. They are not results implemented by this documentation PR.
XSD observations from the pinned-source audit must be reproduced in the local
integration tests at implementation time, without downloading the bundle.

| Synthetic case | XSD / checker.check | Model / parser / checker.parse and other assertions |
| --- | --- | --- |
| Existing draft without taker | Accept as before | Old golden bytes and identity unchanged; taker=None |
| CPF, numeric CNPJ, alphanumeric CNPJ with full national address | Accept each independent vector | Recover every field, exact expected XML, then builder-output round-trip |
| Change only taker data | Accept | infDPS@Id unchanged; draft equality reflects changed values |
| Name length 150 | Accept | Accept if other local rules hold |
| Name length 151 or 300 | XSD can accept; check accepts valid identity | Reject local length policy, not described as XSD failure |
| Name length 301 or missing name | XSD rejects; check short-circuits | Reject; distinguish missing structure from invalid fields |
| Identified taker with no address | XSD can accept; check accepts valid identity | Reject required local address |
| Complement None / empty | Omitted is valid; empty violates minLength | Omit None, reject empty; never silently collapse the two |
| Address limits: 1/max/max+1 for street, number, neighborhood, complement | Match respective facets | Match local facets, no truncation |
| Name spaces/TAB/LF with content, or only XML whitespace | XSD name length alone is insufficient | Preserve content-bearing value; reject whitespace-only name |
| CR literal or character reference; forbidden XML characters | XML normalizes literal line endings; CR reference is distinct; malformed XML rejects | Reject raw CR and decoded CR; reject forbidden chars, no silent repair |
| Composed/decomposed characters; TSString range and edge-space boundaries | Compare exact frozen types | Preserve valid name text; address follows TSString, not generic text cleanup |
| Escaped markup in name | Accept as text | Preserve text, not elements |
| Lowercase CNPJ in XML | XSD rejects | Standalone parser rejects without uppercase repair; construction normalization stays unchanged |
| Duplicate toma, duplicate ID, CPF+CNPJ, wrapper, wrong namespace, CNPJ under serv | XSD rejects invalid structure; standalone inspector must retain ambiguity defenses | Reject without overwriting or discarding identifiers |
| Unknown, reordered or additional fields/attributes | XSD rejects where forbidden; some wider schema branches may be valid | Closed subset rejects unsupported branches, including CAEPF/IM/contact/endExt |
| Missing CEP, extra UF, endNac and endExt together | XSD rejects | Reject incomplete/unsupported/conflicting address |
| Provider and taker share CNPJ | XSD/identity do not enforce fiscal equality rule | No new fiscal rejection; no claim of operational acceptance |
| Valid → invalid → valid, across both checker methods | Preserve order, byte-object identity, short-circuit and exception identity | No residual state; check and parse stay independent |

Use hand-specified synthetic XML from the reviewed contract as the primary
oracle, independently compared with builder output. Do not calculate expected
XML using the same builder. Round-trip is an additional proof, not a substitute.
Keep existing [builder goldens](../../tests/dps/test_builder.py),
[parser rejections](../../tests/dps/test_parser.py),
[identity defenses](../../tests/dps/test_document.py),
[checker pipelines](../../tests/xsd/test_dps_checker.py) and
[private preflight regressions](../../tests/xmlsig/test_preflight.py).

Test dataclasses.fields/signatures, replace, asdict, equality/hash and privacy
boundaries explicitly. Confirm base imports, construction and parsing remain
independent of lxml and network/file I/O; optional XSD validation stays optional.
Keep the six canonical Linux/Windows jobs and all 14 coverage gates unchanged.
Extend the existing local [official integration](../../scripts/validate_official_dps_xsd.py)
with independent positive/negative vectors and valid–invalid–valid reuse only
after implementation is authorized. Never redistribute official artifacts.

Future stages: review this contract and API/versioning decision; authorize
coordinated model/builder/parser/inspection work; deliberately update the public
oracle and independent tests; validate local pinned-XSD integration plus CI;
then update implemented-capability docs/demo. This PR performs only stage one.

## 9. Exclusions and preserved blockers

No foreign taker, provider CPF/NIF, intermediary, CAEPF, IM, contacts, foreign
address, additional fiscal groups, deductions/discounts, tax calculation,
IBS/CBS, numbering allocation/persistence, signing, cryptographic verification,
certificate/private-key handling, HTTP, issuance, production operation,
transmission or response recovery is added or authorized.

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
RUNTIME_DEVELOPMENT_BLOCKED_BY_OFFICIAL_EVIDENCE = YES
```

The last flag continues to describe the blocked emission/response/signature
fronts; this proposed structural subset neither clears those blockers nor
authorizes implementation by itself. Evidence submission is not evidence
promotion, and a locally implementable subset is not runtime authorization.
