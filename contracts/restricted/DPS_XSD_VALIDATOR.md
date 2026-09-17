# Restricted DPS local XSD validator

The optional `nfse_br.xsd` package compiles the official restricted DPS schema
entirely from the already frozen local ZIP. It accepts only the bundle with:

```text
size:   34933 bytes
sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
```

The entrypoint is `DPS_v1.01.xsd`. Its global root is
`{http://www.sped.fazenda.gov.br/nfse}DPS`, typed as `TCDPS`.

The exact compilation closure is:

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `DPS_v1.01.xsd` | 678 | `c7dab363d8cf7c83fc2b3b21e72cf669a51bd30947a5690685ea96c4b3e39dcd` |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |
| `xmldsig-core-schema.xsd` | 10003 | `bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11` |

Dependency edges are:

```text
DPS_v1.01.xsd
├── include tiposComplexos_v1.01.xsd
└── import  xmldsig-core-schema.xsd

tiposComplexos_v1.01.xsd
├── include tiposSimples_v1.01.xsd
└── import  xmldsig-core-schema.xsd
```

All members are supplied by an exact in-memory resolver. Unknown locations,
external protocols, filesystem paths, traversal, absent members, and namespace
mismatches are rejected without fallback to catalogs, files, or the network.
The XMLDSig schema is compiled only as grammar needed by the official DPS XSD;
no cryptographic signature or certificate verification is performed.

The implementation uses `lxml 6.1.3`; the local V0.6.1 integration loaded
`libxml2 2.14.6`. Reproduce compilation and validation with the ignored local
artifact:

```console
uv run --frozen --extra xsd python scripts/validate_official_dps_xsd.py \
  .f0/restricted/restricted-xsd.zip
```

The command validates one complete synthetic DPS and proves rejection after
isolated changes to the DPS number, required fields, field order, and root
namespace. The sample is structural test data, not an authorized or fiscally
valid document.

Input is limited to 1 MiB of UTF-8/UTF-8-BOM XML. DTDs and entity declarations
are forbidden. Validation neither changes the XML nor proves fiscal semantics,
signature validity, authorization, SEFIN acceptance, or transmission readiness.
`transmission_ready` remains `false`.
