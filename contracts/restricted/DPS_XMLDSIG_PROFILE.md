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

## Diligência adicional V0.9.1

The frozen restricted Annex I workbook remains byte-identical to the file
linked by the Produção Restrita portal on 18 September 2026: 215,056 bytes,
SHA-256
`2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9`.
It was inspected as OOXML in memory, including its rule sheets and comments;
no official artifact was extracted into or added to the repository.

The workbook adds current, applicable evidence about the DPS signature, but
not about its algorithms:

- `RN DPS_NFS-e!B642:K646` (rules 639–643, errors E0714–E0718) requires a
  valid signature for DPS sent through the Web Service, validates certificate
  dates, chain and revocation status, requires an ICP-Brasil root and version
  3 certificate with the documented CPF/CNPJ `OtherName`, and binds the
  signing certificate to the DPS issuer.
- `LEIAUTE DPS_NFS-e` cells B416:H416 call the DPS signature XMLDSig and make it
  mandatory for API submission, but its path places `Signature` below
  `infDPS`. That path conflicts with both frozen `TCDPS` (where `Signature` is
  a direct DPS child after `infDPS`) and `RN DPS_NFS-e!B642:C642`, whose path is
  `NFSe/infNFSe/DPS/Signature`. The schema therefore remains the structural
  authority; the layout path discrepancy should be clarified before a signer
  is specified.
- No cell or comment in the five worksheets names RSA, SHA, C14N,
  `Reference`, `Transform`, `DigestMethod`, or `KeyInfo`. A generic “valid
  signature” rejection does not select those values.
- `RN_RECEPCAO_DPS!B2:G9` concerns the *transmission* certificate. Those rules
  must not be used as the XML-signature certificate profile.

Additional current official material was checked without using operational
API methods:

| Source inspected | Location and result | Bytes / SHA-256 captured on 2026-09-18 |
| --- | --- | --- |
| [Contributor API manual v1.2 (October 2025)](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf) | Sections 1.3.1–1.3.2 delegate DPS schemas, layout, and business rules to Annex I; no XMLDSig algorithm profile | 188,158 / `ac2f36e34ff565cc36d67c5d67415c33cc09f27b2dea006e8da9bcd2ddce5581` |
| [Nota Técnica SE/CGNFS-e 004 v2.0](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita/nt-004-se-cgnfse-novo-layout-rtc-v2-00-20251210.pdf) | No signature, RSA, SHA, or canonicalization requirement | 666,084 / `707524b2110a3af55a232110ead632abe14d745a60307f8dcc062ec220d4058f` |
| [Perguntas e Respostas v1.00 (8 September 2026)](https://www.gov.br/nfse/pt-br/perguntas-frequentes/perguntas-e-respostas-nfse-v1-00-20260908.pdf) | Sections 17.1–17.3 confirm an enveloped signature on the element carrying the identifier and discuss E0717/E0718 and certificate checks; they name no signature, digest, or C14N algorithm | 1,140,924 / `aa45e008842f1c94e7e175f96df3f6354a23b45b6136db8ed87706d318b462f7` |

The FAQ also creates a current-source conflict in certificate details. Section
17.2 says `Basic Constraint = false`, while the literal text in
`RN DPS_NFS-e!D644` says it must be `true` while simultaneously saying that
the certificate cannot be a CA certificate. Section 17.1 adds Client
Authentication to the key usages, whereas `D644` lists Digital Signature and
Non Repudiation for the signature certificate. These differences cannot be
silently reconciled by implementation.

The result by requirement is therefore:

| Requirement | V0.9.1 classification |
| --- | --- |
| signed element and `Id` | `HISTORICAL_ONLY` for exact `infDPS` targeting; the frozen XSD and local preflight establish structure, not the cryptographic reference policy |
| exact `Reference/@URI` | `HISTORICAL_ONLY` |
| canonicalization method, comments, and exclusivity | `HISTORICAL_ONLY` |
| signature method | `HISTORICAL_ONLY` |
| digest method | `HISTORICAL_ONLY` |
| transforms and order | `UNCONFIRMED`; current FAQ confirms only the enveloped form |
| `KeyInfo/X509Data` and chain composition | `HISTORICAL_ONLY` |
| certificate validity, ICP-Brasil root, issuer binding, and CPF/CNPJ `OtherName` | `CONFIRMED_BY_APPLICABLE_OFFICIAL_SOURCE` |
| Basic Constraints and complete Key Usage | `CONFLICTING` |

No complete current signer profile is proposed. In particular, neither the
RSA-SHA1/SHA-1 historical profile nor the RSA-SHA256/SHA-256 profile published
for NFS-e Via is imported into the restricted DPS profile.

## Diligência adicional V0.20.2 (20 de setembro de 2026)

The current Production and Produção Restrita catalogues, their linked v1.01
artifacts, the current contributor API manual, the current FAQ, and the
official API catalogue were checked again. No current applicable source was
found that completes the XMLDSig algorithm profile.

| Current official source | Version/location | Result |
| --- | --- | --- |
| [Documentação Atual](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual) | Page updated 15 August 2026; `NFSe-ESQUEMAS_XSD-v1.01-20260209`; `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-v1.01-20260209` | The current Production artifacts were inspected in full. The v1.01 schema leaves algorithm URIs open, and the Annex I does not name them. |
| [Produção Restrita](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita) | Page updated 28 July 2026; `NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727`; `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209` | The downloaded files remain byte-identical to the frozen restricted evidence. No algorithm requirement was added. |
| [Contributor API manual](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf) | Portal filename: v1.2, October 2025; internal history: v1.0, 17 March 2025; sections 1.3.1–1.3.2 | Delegates DPS schemas, layout, and rules to Annex I. It does not specify the XMLDSig algorithms or representation. |
| [Perguntas e Respostas](https://www.gov.br/nfse/pt-br/perguntas-frequentes/perguntas-e-respostas-nfse-v1-00-20260908.pdf) | v1.00, 8 September 2026; sections 17.1–17.3, PDF pp. 77–78 | Confirms an enveloped signature on the element carrying the identifier and gives certificate rules, but no algorithm URIs, complete transform list, reference form, or `KeyInfo` representation. |
| [APIs de Produção Restrita e Produção](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao) | Page updated 20 August 2026 | Identifies the current ADN and SEFIN documentation endpoints. Their documentation content could not be retrieved from this environment (TLS failure for ADN and HTTP 403 for SEFIN); no operational API method was called and no requirement is attributed to an inaccessible document. |

The downloaded current Production artifacts were recorded without adding
their raw bytes to the repository:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `NFSe-ESQUEMAS_XSD-v1.01-20260209` | 65,640 | `e7935cbd9470527c6cc32984c1b2263e614183bf0139ce2733eaaed2de9a8072` |
| `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-v1.01-20260209` | 215,196 | `de5bc492959eadc8bfa7540e16939995924f2188f743648eaf84d3b31e9eeb7c` |

The Production ZIP contains separate `Schemas/1.00` and `Schemas/1.01`
closures. Its 3,406-byte `Schemas/1.00/xmldsig-core-schema.xsd` (SHA-256
`d87432c5f6ebb2bd61a1de357797401c203f14daefde834b73946f25f926a216`)
fixes C14N 1.0, RSA-SHA1, SHA-1, and exactly two transforms. That file does
not govern DPS v1.01. `Schemas/1.01/tiposComplexos_v1.01.xsd` imports the
10,610-byte `Schemas/1.01/xmldsig-core-schema.xsd` (SHA-256
`49848f732663aecb618d72ad6130c5c3240f0a10f3a1a8544b7d48a6c726046f`),
whose algorithm attributes are open `xs:anyURI` values. The frozen restricted
v1.01 schema behaves the same way. The colocated v1.00 profile therefore
cannot be treated as the current v1.01 profile.

The Production Annex I repeats the same material findings as the restricted
workbook. `LEIAUTE DPS_NFS-e` row 416 (printed item 415) places `Signature`
below `infDPS`, while `RN DPS_NFS-e` row 645 (printed rule 642, E0714) and the
v1.01 `TCDPS` schema place it directly below `DPS`. Rows 646–649 (printed
rules 643–646) contain certificate checks but no XMLDSig algorithm or
representation. The full Production and restricted workbooks contain no cell
or comment naming `SignatureMethod`, `DigestMethod`,
`CanonicalizationMethod`, `Reference`, `Transform`, `X509Data`,
`X509Certificate`, RSA, SHA, C14N, or `EndCertOnly`.

The official integrated manuals v1.00.02 and v1.01.00 Homologação are dated
2022 and remain historical evidence. Their RSA-SHA1/SHA-1/C14N 1.0 profile is
not promoted merely because the current Production ZIP retains a separate
v1.00 schema closure. The inspected 6,582,639-byte v1.01.00 Homologação PDF,
dated 14 October 2022, has SHA-256
`3babab9ae2882ffd9a2471152d470a96a51d3cc013a05e6830f30ef89578eb41`;
sections 6.1.3–6.1.5 (printed pp. 27–30) contain the historical profile.

### Evidence matrix after the refresh

| Requirement | Classification | Current evidence and remaining gap |
| --- | --- | --- |
| signed target | `CURRENT_PARTIAL` | The FAQ requires signing the element carrying the identifier, but does not name `infDPS`; the exact target is historical only. |
| exact `Reference/@URI` | `HISTORICAL_ONLY` | No current source fixes `#` plus the unqualified `Id`. |
| `CanonicalizationMethod` | `HISTORICAL_ONLY` | The applicable v1.01 schemas use open `xs:anyURI`; no current source selects comments or exclusivity behavior. |
| `SignatureMethod` | `HISTORICAL_ONLY` | The applicable v1.01 schemas use open `xs:anyURI`; RSA-SHA1 is fixed only in historical/v1.00 material. |
| `DigestMethod` | `HISTORICAL_ONLY` | The applicable v1.01 schemas use open `xs:anyURI`; SHA-1 is fixed only in historical/v1.00 material. |
| transforms and order | `CURRENT_PARTIAL` | The FAQ confirms the enveloped form, but not the complete ordered transform list. |
| `KeyInfo/X509Data` representation | `HISTORICAL_ONLY` | Current sources impose certificate checks but do not define whether or how the end certificate or chain is embedded. |
| certificate chain embedding | `UNCONFIRMED` | Current chain validation rules do not define the XML-embedded chain composition. |
| Basic Constraints | `CONFLICTING` | FAQ section 17.2 says `false`; Annex I says `true` while also saying the certificate must not be a CA. |
| Key Usage | `CONFLICTING` | Annex I lists Digital Signature and Non Repudiation; FAQ section 17.1 additionally lists Client Authentication. |
| `Signature` position | `CONFLICTING` | v1.01 XSD and signature rule place it directly below `DPS`; the layout row prints it below `infDPS`. |
| certificate validity, ICP-Brasil root, issuer binding, and CPF/CNPJ `OtherName` | `CURRENT_CONFIRMED` | Annex I rules 643–646 in Production (640–643 restricted) and FAQ sections 17.1–17.2 currently support these checks. |

Because the target, reference, algorithms, complete ordered transforms, and
`KeyInfo` representation are not all confirmed by an applicable current
official source, the decision remains fail-closed:

```text
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```

### Final technical inquiry (ready, not sent)

```text
Assunto: Confirmação do perfil XMLDSig da DPS v1.01 no ambiente nacional

Para implementar de forma interoperável a assinatura da DPS v1.01, pedimos
a confirmação do perfil XMLDSig aplicável ao bundle de Produção Restrita
NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727 e ao Anexo I
ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209.

Favor confirmar expressamente:

1. a URI de SignatureMethod;
2. a URI de DigestMethod;
3. a URI de CanonicalizationMethod, inclusive uso de comentários e forma
   exclusiva ou inclusiva;
4. a lista ordenada de Transform/@Algorithm;
5. o elemento assinado e a forma exata de Reference/@URI, inclusive se deve
   ser "#" seguido do Id não qualificado de infDPS;
6. a composição obrigatória de KeyInfo/X509Data: somente o certificado final
   em X509Certificate ou também a cadeia;
7. os requisitos de Basic Constraints e Key Usage, diante da diferença entre
   o Anexo I e as seções 17.1–17.2 do Perguntas e Respostas v1.00 de
   08/09/2026; e
8. a posição correta de Signature, pois o XSD v1.01 e a regra E0714 a colocam
   como filha direta de DPS após infDPS, enquanto a linha de leiaute a imprime
   abaixo de infDPS.

Esta consulta trata apenas do perfil nacional da DPS v1.01; não pressupõe
regras de NF-e, ABRASF municipal ou NFS-e Via e não contém dados fiscais,
certificado ou chave privada.
```

The current official [attendance page](https://www.gov.br/nfse/pt-br/canais-de-atendimento),
updated 16 September 2026, disables the former direct support email and
directs contributors to their municipality, which may contact Receita
Federal. That is the identified current route. The inquiry above has not been
sent.

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
