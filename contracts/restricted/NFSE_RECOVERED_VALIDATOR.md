# Recovered NFS-e local XSD validator

`RecoveredNfseValidator` compiles the NFS-e schema entirely from the official
Produção Restrita ZIP already frozen by this repository. It accepts only the
bundle with:

```text
size:   34933 bytes
sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
```

Discovery enumerated only `.xsd` members, parsed each schema with the existing
safe XML policy, and found exactly one schema declaring the global expanded
name `{http://www.sped.fazenda.gov.br/nfse}NFSe`:
`NFSe_v1.01.xsd`. The runtime repeats that discovery and then requires the
exact entrypoint, root expanded name, dependency closure, and member hashes
below.

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `NFSe_v1.01.xsd` | 738 | `1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0` |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |
| `xmldsig-core-schema.xsd` | 10003 | `bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11` |

The deterministic closure is:

```text
NFSe_v1.01.xsd
├── include tiposComplexos_v1.01.xsd
└── import  xmldsig-core-schema.xsd

tiposComplexos_v1.01.xsd
├── include tiposSimples_v1.01.xsd
└── import  xmldsig-core-schema.xsd
```

All dependencies are exact in-memory resources. URL schemes, network
locations, absolute paths, Windows drives, traversal, query strings,
fragments, missing members, and include/import namespace mismatches are
rejected. There is no filesystem or network fallback.

The validator accepts at most 1 MiB of exact `bytes`, using the shared
UTF-8/UTF-8-BOM, no-DTD, no-entity, no-network parser policy. It requires the
exact `NFSe` root before applying the compiled XSD. XInclude processing is not
invoked, and an instance `xsi:schemaLocation` cannot replace the pinned schema.

Reproduce the official local integration with the ignored bundle:

```console
uv run --frozen --extra xsd python scripts/validate_official_nfse_xsd.py \
  .f0/restricted/restricted-xsd.zip
```

The positive fixture is entirely synthetic. Its XMLDSig values use synthetic
algorithm URIs and prove only XSD grammar; they are not cryptographically
valid. Negative cases prove root binding and effective mutations of required
fields, element order, and namespace. No official ZIP or real fiscal document
is distributed or used by CI.

`RecoveredNfseValidator` confirms only safe XML parsing, the expected `NFSe`
root, and XSD conformance against the pinned restricted bundle. It does not
confirm authenticity, XML signature validity, ICP-Brasil certificate status,
HTTP origin, fiscal validity or authorization, correlation with an `idDps` or
access key, SEFIN acceptance, or transmission readiness.

```text
OFFICIAL_BUNDLE_E2E_IN_CI = NOT_RUN_BY_DESIGN
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```
