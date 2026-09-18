# Restricted DPS XMLDSig profile and structural preflight

This record separates what the frozen restricted XSD proves from historical
signature instructions and from the fail-closed policy used by the local
preflight. It does not authorize signing or transmission.

```text
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
CRYPTOGRAPHIC_VERIFICATION_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```

## Frozen schema observations

The restricted ZIP is 34,933 bytes with SHA-256
`6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc`.
Its 10,003-byte `xmldsig-core-schema.xsd` member has SHA-256
`bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11`.
The complete schema closure used to establish root, position, and grammar is:

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `DPS_v1.01.xsd` | 678 | `c7dab363d8cf7c83fc2b3b21e72cf669a51bd30947a5690685ea96c4b3e39dcd` |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |
| `xmldsig-core-schema.xsd` | 10003 | `bf43998b2df1fedd9ed7d6914f91ab4d34958e8730c3b500cbe0b21e60335f11` |

The XMLDSig member identifies itself as schema revision 1.2 (16 April 2013)
and carries the schema `version="0.1"` attribute.

In `TCDPS`, `ds:Signature` is an optional direct child after the required
`infDPS`. The imported XMLDSig grammar declares this structure:

```text
Signature
  SignedInfo             1
    CanonicalizationMethod 1
    SignatureMethod        1
    Reference              1..unbounded
      Transforms?          0..1 (Transform children 1..unbounded)
      DigestMethod         1
      DigestValue          1
  SignatureValue         1
  KeyInfo?               0..1
  Object*                0..unbounded
```

`Reference/@URI` is optional in the generic grammar. The `Algorithm`
attributes on `CanonicalizationMethod`, `SignatureMethod`, `Transform`, and
`DigestMethod` are all open `xs:anyURI` values: the frozen XSD fixes or
enumerates none of them. `KeyInfo` is likewise a broad optional choice;
`X509Data/X509Certificate` is permitted and its content is `xs:base64Binary`,
but it is not the only grammar-valid key representation.

Consequently, XSD validity neither chooses an algorithm profile nor proves a
cryptographic signature valid.

## Current and historical documentation

The current Produção Restrita page publishes
`NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727`, the exact source of the frozen
schema above. The current documentation page publishes the contributor API
manual version 1.2 (October 2025). That manual mentions digitally signed XML
documents, but does not specify the canonicalization, signature, digest,
transform, reference, or `KeyInfo` profile needed by a signer.

The official **historical** integrated manual version 1.00.02, dated
14 September 2022, does provide those details in sections 6.1.3–6.1.5,
PDF pages 24–27:

| Decision | Historical value | Location |
| --- | --- | --- |
| signed target | `infDPS` identified by `Id` | PDF p. 26 |
| reference | local fragment matching that Id | PDF p. 26 |
| signature shape | enveloped XML Signature | PDF p. 26 |
| canonicalization | Canonical XML 1.0 | PDF pp. 25–26 |
| signature method | RSA-SHA1 | PDF pp. 25–26 |
| digest method | SHA-1 | PDF pp. 25–26 |
| transforms | enveloped signature, then C14N | PDF pp. 25–26 |
| key information | end certificate in `X509Data/X509Certificate` | PDF pp. 24–26 |

The portal classifies that manual under “Leiaute e esquemas antigos (julho de
2022 a 28/09/2025)”. It also describes version 1.00 identifiers, while the
frozen restricted bundle is version 1.01. These values are therefore retained
as historical evidence, not promoted into a current signer profile.

The missing current evidence is an applicable official source that confirms
the algorithms, transform order, reference form, `KeyInfo` shape, and
certificate policy for the frozen restricted v1.01 DPS. Until then,
`SIGNATURE_PROFILE_CONFIRMED` remains `NO`.

## Local structural preflight

`nfse_br._xmlsig.preflight.inspect_unsigned_dps()` is a private, standard-
library-only preparation check. It accepts at most 1 MiB of UTF-8 or UTF-8-BOM
XML bytes, rejects DTD/entity declarations, and requires an unsigned DPS 1.01
with exactly one direct `infDPS` and no other `infDPS` or `Signature` element.

The returned string is the exact `infDPS@Id` only after these local invariants
hold:

- the root and target are identified by expanded namespace URI and local name;
- the target is unique and in its expected position;
- only the target has an unqualified `Id`; `xml:id` and `Id`/`id`/`ID`
  alternatives elsewhere are rejected;
- `cLocEmi`, `prest/CNPJ`, `serie`, and `nDPS` occur once at their expected
  paths and reproduce the target Id through the existing domain objects;
- the lexical fields are not stripped, case-normalized, or otherwise repaired.

These are deliberately restrictive project policies for the current unsigned
builder subset. They are motivated by XML Signature Best Practices section
3.1.5, which requires checking both the name and position of the referenced
element to mitigate wrapping attacks. They are not claims about every XML form
permitted by the national standard.

The preflight does not validate the XSD, canonicalize XML, calculate a digest,
load a certificate, access a private key, sign, verify, or transmit. A future
signer must rerun the checks against the exact bytes it will sign; the returned
Id is not reusable authorization for different bytes.

## Sources

- [Produção Restrita](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita)
- [Documentação atual](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual)
- [Manual Integrado histórico v1.00.02](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/leiaute-e-esquemas-antigos/manualintegradosnnfse_v1-00-02-producao.pdf)
- [XML Signature Syntax and Processing 1.1](https://www.w3.org/TR/xmldsig-core1/)
- [XML Signature Best Practices](https://www.w3.org/TR/xmldsig-bestpractices/)

The machine-readable companion
[`dps-xmldsig-profile.json`](dps-xmldsig-profile.json) contains the same
classification without timestamps or runtime configuration semantics.
