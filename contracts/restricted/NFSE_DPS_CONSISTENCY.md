# NFS-e and embedded DPS consistency contract

This evidence freeze records the current official rules that can safely support
local consistency checks between one NFS-e and its embedded DPS. It is derived
from the already-frozen Produção Restrita artifacts; synthetic project fixtures
are tests, not normative evidence.

## Source binding

```text
XSD bundle size:   34933 bytes
XSD bundle sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
Annex I size:      215056 bytes
Annex I sha256:    2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9
```

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |

The decisive Annex I sources are in the worksheet `RN DPS_NFS-e`:

- `A7:O7`, rule 4 / `E1263`, defines the NFS-e identifier components and
  binds its municipality and federal-registration components to the NFS-e
  issuer;
- `A33:O33`, rule 30 / `E1282`, and `A35:O35`, rule 32 / `E1285`, bind the
  NFS-e issuer CNPJ or CPF to the DPS entity selected by `tpEmit`;
- `A44:O44`, rule 41 / `E1286`, binds the NFS-e issuer municipality to the
  `cLocEmi` carried by the embedded DPS; and
- `A142:O142`, rule 139 / `E0004`, requires `infDPS/@Id` to equal the
  concatenation of the DPS municipality, selected issuer registration, series,
  and number.

The matching layout rows are `LEIAUTE DPS_NFS-e !A5:I5`, `A8:I8`,
`A15:I15`, `A102:I102`, `A103:I103`, `A106:I107`, `A109:I109`,
`A112:I112`, and `A117:I169`. The raw layout worksheet name ends in one
space.

## Evidence matrix

| Invariant | Classification | Runtime enforcement | Decision |
| --- | --- | --- | --- |
| Embedded DPS identity self-consistency | `CURRENT_CONFIRMED` | yes | Recompose the identifier from `cLocEmi`, the CPF/CNPJ of the entity selected by `tpEmit`, `serie`, and `nDPS`. |
| NFS-e number inside `TSIdNFSe` | `CONFLICTING` | no | Annex I describes a 13-position component and says `nNFSe` must contain 13 digits, while the current XSD type is `[1-9]{1}[0-9]{0,12}`. No authoritative padding algorithm is stated. |
| NFS-e/DPS municipality | `CURRENT_CONFIRMED` | yes | The seven-position municipality component of `infNFSe/@Id` must equal embedded `cLocEmi`. |
| NFS-e/DPS federal registration | `CURRENT_CONFIRMED` | yes | The type plus 14-position federal-registration component of `infNFSe/@Id` must match the DPS entity selected by `tpEmit`: prestador `1`, tomador `2`, intermediário `3`. |
| NFS-e registration always equals `prest` | `CONFLICTING` | no | This is true only when `tpEmit=1`; Annex I explicitly selects tomador or intermediário for `tpEmit=2/3`. |
| Generator/operational environment | `UNCONFIRMED` | no | `ambGer` describes who generated the NFS-e; `tpAmb` describes Produção/Homologação. No source equates them. |
| `nNFSe` equals `nDPS` | `UNCONFIRMED` | no | They are distinct sequential identities and no current rule requires equality. |

## Runtime boundary

`validate_nfse_document_consistency` enforces only the three confirmed rules:

1. embedded DPS identity self-consistency;
2. municipality equality between the NFS-e identity and embedded DPS; and
3. conditional federal-registration equality using `tpEmit`.

The function reuses `extract_nfse_document_info`, then safely parses the same
bytes to observe the additional direct DPS fields. It does not derive an
access key, infer NFS-e-number padding, compare `ambGer` with `tpAmb`, or
compare `nNFSe` with `nDPS`.

This is not XSD validation, signature verification, fiscal authorization, or
proof of transport origin. A stronger local pipeline is:

```python
validator.validate(xml_bytes)
extract_nfse_document_info(xml_bytes)
validate_nfse_document_consistency(xml_bytes)
```

where `validator` is a `RecoveredNfseValidator` constructed from the pinned
restricted bundle.

```text
PROJECT_SYNTHETIC_FIXTURE_IS_NORMATIVE_EVIDENCE = NO
NFSE_DPS_CONSISTENCY_CONTRACT_CONFIRMED = YES
NFSE_DPS_CONSISTENCY_IMPLEMENTATION_READY = YES
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```
