# NFS-e identity evidence

This evidence freeze traces `NFSe/infNFSe/@Id` in the official frozen
Produção Restrita artifacts and keeps its lexical contract separate from
`TSChaveNFSe`. The project synthetic fixture in
`scripts/validate_official_nfse_xsd.py` is only an XSD-valid test document; it
is not normative evidence.

## Sources

The frozen restricted artifacts are:

```text
XSD bundle size:   34933 bytes
XSD bundle sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
Annex I size:      215056 bytes
Annex I sha256:    2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9
```

The official [Produção Restrita documentation
page](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita)
lists these sources as
`NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727` and
`ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209`.

The XSD members used by this audit are:

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `NFSe_v1.01.xsd` | 738 | `1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0` |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |

The current official semantic source is [Nota Técnica SE/CGNFS-e nº 008,
version 1.0, dated 2026-05-05](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/nt-008-se-cgnfse-danfse-20260505.pdf/@@download/file),
section 2.4.5, document page 16 (PDF page index 15), retrieved on 2026-09-20.
The captured PDF was 1,194,919 bytes with SHA-256
`3d1dd84ec118f8c732af2f8ec874a9df0399a5cf08a8a97fd83ef19a9e823bf5`.
The row named `CHAVE DE ACESSO DA NFS-E` points to the published path
`NFSe/infNFSe/id` and instructs: “Informar o id da NFS-e sem o prefixo
"NFS".” The XSD spelling remains the case-sensitive attribute `Id`.

## XSD type chain

The complete direct chain is:

```text
NFSe_v1.01.xsd
└── global element NFSe: TCNFSe
    └── tiposComplexos_v1.01.xsd / TCNFSe
        └── element infNFSe: TCInfNFSe
            └── tiposComplexos_v1.01.xsd / TCInfNFSe
                └── required attribute Id: TSIdNFSe
                    └── tiposSimples_v1.01.xsd / TSIdNFSe
                        └── restriction of xs:string
```

`TSIdNFSe` has no further project-relevant type inheritance. Its explicit
facets are:

| Facet | Value |
| --- | --- |
| Base | `xs:string` |
| `whiteSpace` | `preserve` |
| `maxLength` | `53` |
| `pattern` | `NFS[0-9]{9}[0-9A-Z]{14}[0-9]{27}` |

The fixed-width pattern makes the effective length exactly 53 positions. Its
annotation and Annex I describe the composition as:

```text
NFS
+ municipality code (7)
+ generator environment (1)
+ federal-registration type (1)
+ federal registration (14)
+ NFS-e number (13)
+ emission year/month (4)
+ numeric code (9)
+ check digit (1)
```

Annex I independently records the layout at `LEIAUTE DPS_NFS-e!A5:I5` (the
raw worksheet name has one trailing space) and the corresponding business
rule at `RN DPS_NFS-e!A7:O7`. No relevant identity/access-key text was found
in workbook comments.

## `TSChaveNFSe`

The same `tiposSimples_v1.01.xsd` member defines:

| Facet | Value |
| --- | --- |
| Base | `xs:string` |
| `whiteSpace` | `preserve` |
| `maxLength` | `50` |
| `pattern` | `[0-9]{6}([0-9A-Z]{14})[0-9]{30}` |

The pattern makes its effective length exactly 50 positions.

## Lexical and semantic relationship

The official current DANFSe specification establishes the semantic rule that
the access key is `infNFSe/@Id` without the `NFS` prefix. Annex I also requires
an NFS-e identifier to correspond to an access key in the replacement-event
rule at `RN DPS_NFS-e!A185:O185`.

The two frozen XSD lexical languages nevertheless conflict after the prefix is
removed:

| Positions | `TSIdNFSe` without `NFS` | `TSChaveNFSe` |
| --- | --- | --- |
| 1–6 | digits | digits |
| 7–9 | digits | digits or uppercase letters |
| 10–20 | digits or uppercase letters | digits or uppercase letters |
| 21–23 | digits or uppercase letters | digits |
| 24–50 | digits | digits |

Neither language contains the other. The semantic mapping is therefore
current and explicit, but it does not define a total type-safe conversion
between every XSD-valid `TSIdNFSe` and every XSD-valid `TSChaveNFSe` value.
Automatic conversion remains disallowed until the official lexical conflict
is resolved.

There are two additional documentary inconsistencies which are not silently
corrected here:

- Annex I `LEIAUTE DPS_NFS-e!H5` first says the identifier is preceded by
  literal `ID`, while the same cell's formula, its business rule, the XSD, and
  the DANFSe specification use `NFS`.
- Annex I and the DANFSe table print the field as lowercase `id`; the XSD
  attribute is case-sensitive `Id`.

## Decision matrix

| Requirement | Result |
| --- | --- |
| `NFSe` element / `TCNFSe` | `CURRENT_CONFIRMED` |
| `infNFSe` element / `TCInfNFSe` | `CURRENT_CONFIRMED` |
| `Id` attribute required | `CURRENT_CONFIRMED` |
| `Id` lexical type and exact pattern | `CURRENT_CONFIRMED` |
| `TSChaveNFSe` lexical pattern | `CURRENT_CONFIRMED` |
| Relationship between the two lexical languages | `CONFLICTING` |
| Semantic access-key relationship | `CURRENT_CONFIRMED` |
| Lexical prefix required by XSD | `CURRENT_CONFIRMED` (`NFS`) |
| Prefix prose across all documents | `CONFLICTING` |
| Conversion `Id` → access key | `CONFLICTING`; not allowed |
| Conversion access key → `Id` | `CONFLICTING`; not allowed |

```text
PROJECT_SYNTHETIC_FIXTURE_IS_NORMATIVE_EVIDENCE = NO
NFSE_ID_CONTRACT_CONFIRMED = YES
ID_ACCESS_KEY_LEXICAL_RELATION_CONFIRMED = NO
ID_ACCESS_KEY_SEMANTIC_RELATION_CONFIRMED = YES
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
NFSE_ACCESS_KEY_IMPLEMENTED = YES
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
TECHNICAL_QUERY_RESPONSE = PENDING
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```
