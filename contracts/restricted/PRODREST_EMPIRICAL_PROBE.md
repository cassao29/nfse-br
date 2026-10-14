# Produção Restrita empirical probe (14 October 2026)

This record documents operational requests sent to the official SEFIN Nacional
restricted environment to observe which DPS XMLDSig profiles the validator
accepts. Its machine-readable companion is
[`prodrest-empirical-probe.json`](prodrest-empirical-probe.json).

```text
EVIDENCE_CLASS = CONFIRMED_BY_OFFICIAL_VALIDATOR
SIGNATURE_PROFILE_CONFIRMED = YES
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = YES
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```

## Authorization and evidence class

The technical inquiry in [`XMLDSIG_INQUIRY.md`](XMLDSIG_INQUIRY.md) received no
reply in 24 days. On 14 October 2026 the maintainer authorized a different
route: operational requests to Produção Restrita, authenticated with a
maintainer-controlled ICP-Brasil e-CNPJ A1 certificate. This decision
supersedes the earlier "no client certificate or operational request" limit in
[`NFSE_POST_RESPONSE.md`](NFSE_POST_RESPONSE.md). Documents generated in
Produção Restrita have no fiscal value.

`CONFIRMED_BY_OFFICIAL_VALIDATOR` is a new classification. It means: the
official validator, identified by its reported `versaoAplicativo`, accepted or
rejected exact bytes on the capture date. It is stronger than historical
documentation for the questions it answers. It does not prove that production
behaves identically, that other accepted variants are recommended, or that the
validator will not change.

## Method

- The provider is a Simples Nacional ME/EPP CNPJ (`opSimpNac = 3`,
  `regApTribSN = 1`) in a municipality with an active agreement in Produção
  Restrita. The same certificate authenticated mutual TLS and signed the XML.
- Every DPS was built with the published 0.5.0 builder and then completed with
  `regApTribSN`, which the builder subset does not serialize.
- Before each request, the exact bytes passed the pinned v1.01 XSD (except the
  deliberately invalid variant M18) and an independent local digest and
  `SignatureValue` check.
- The request body was JSON with the UTF-8 XML gzip-compressed and
  Base64-encoded (`dpsXmlGZipB64`, `pedidoRegistroEventoXmlGZipB64`).
- Sentinel: the matrix DPS kept `indTotTrib`, which the validator rejects for
  ME/EPP with `E0712`. Signature failures returned `E0714` or `E0715` alone; accepted
  signatures reached `E0712` alone. `E0712` therefore means "signature
  accepted, no NFS-e generated".
- Each matrix variant changes one dimension of the accepted profile.

The validator reported `versaoAplicativo = SefinNacional_1.6.0` on every
response.

## Accepted profile

The first issuance (I4) returned HTTP 201 with an NFS-e. The same profile
passed the signature stage of the cancellation event (E2).

| Item | Value |
| --- | --- |
| Signed element | `infDPS` (DPS) and `infPedReg` (pedRegEvento) |
| `Reference/@URI` | `#` plus the unqualified `Id` of the signed element |
| `CanonicalizationMethod` | `http://www.w3.org/2001/10/xml-exc-c14n#` |
| `SignatureMethod` | `http://www.w3.org/2001/04/xmldsig-more#rsa-sha256` |
| `DigestMethod` | `http://www.w3.org/2001/04/xmlenc#sha256` |
| Transforms, in order | `…xmldsig#enveloped-signature`, `…xml-exc-c14n#` |
| `KeyInfo` | `X509Data` with exactly one `X509Certificate`: the signer end certificate |
| Namespace | default `xmlns` declaration on `Signature`, no prefix |
| Position | direct child of the root element, after the signed element |

The issued NFS-e carries the SEFIN signature with RSA-SHA256, SHA-256 and
`xml-exc-c14n#WithComments`, and keeps the provider signature inside the
embedded DPS.

## Results

| Id | Variant | Result |
| --- | --- | --- |
| I1 | inclusive C14N, RSA-SHA1, SHA-1 (historical v1.00.02 profile) | `E0714` |
| I2 | inclusive C14N, RSA-SHA256, SHA-256 | `E0714` |
| I3 | exclusive C14N, RSA-SHA256, SHA-256 | `E0712` (signature accepted) |
| I4 | I3 with `pTotTribSN` instead of `indTotTrib` | HTTP 201, NFS-e issued |
| M00 | control, accepted profile | `E0712` |
| M01 | RSA-SHA1 + SHA-1 | `E0712` |
| M02 | RSA-SHA256 + SHA-1 digest | `E0712` |
| M03 | RSA-SHA1 + SHA-256 digest | `E0712` |
| M04 | RSA-SHA512 + SHA-512 | `E0712` |
| M05 | `xml-exc-c14n#WithComments` in both places | `E0712` |
| M06 | inclusive C14N `#WithComments` | `E0714` |
| M07 | C14N 1.1 (`xml-c14n11`) | `E0715` |
| M08 | inclusive `CanonicalizationMethod`, exclusive Reference transform | `E0714` |
| M09 | exclusive `CanonicalizationMethod`, inclusive Reference transform | `E0714` |
| M10 | enveloped transform only (implicit inclusive C14N) | `E0714` |
| M11 | exclusive C14N transform only, without enveloped | `E0712` |
| M12 | exclusive C14N before enveloped | `E0712` |
| M13 | `KeyInfo` with end certificate plus its three chain certificates | `E0714` |
| M14 | no `KeyInfo` | `E0714` |
| M15 | `Reference URI=""` (whole document) | `E0712` |
| M16 | `ds:` prefix | `E1228` "Xml declarado com prefixo de namespace." |
| M17 | Base64 wrapped at 76 characters | `E0712` |
| M18 | `Signature` inside `infDPS` | `E1235` schema failure |
| E1 | cancellation event, inclusive C14N | `E0714` |
| E2, E3 | cancellation event, accepted profile | `E0824` (municipal rule, see below) |

Conclusions for the inquiry questions:

1. Signature algorithm: RSA-SHA256 is accepted and matches the SEFIN
   signature. RSA-SHA1 and RSA-SHA512 were also accepted.
2. Digest algorithm: SHA-256 is accepted; SHA-1 and SHA-512 were also accepted.
3. Canonicalization: exclusive C14N without comments is required in practice.
   Inclusive C14N 1.0, with or without comments, in either position, was
   always rejected; C14N 1.1 returned `E0715`.
4. Transforms: `enveloped-signature` then exclusive C14N is accepted. The
   order and the presence of `enveloped-signature` were not enforced.
5. Reference: `#` plus the `infDPS` Id is accepted; `URI=""` was also accepted.
6. `KeyInfo`: exactly the end certificate. The chain and an absent `KeyInfo`
   were both rejected.
7. Basic Constraints and Key Usage: not tested; only one certificate was
   available. The documentary conflict remains `CONFLICTING`.
8. Position: direct child of `DPS` after `infDPS`; inside `infDPS` fails the
   schema (`E1235`), which resolves the layout-row conflict in favor of the XSD.

The recommended profile is the accepted profile above. Accepted alternatives
are recorded as observations, not as supported options.

## Business rules observed outside the builder subset

- `E0712`: ME/EPP must not send `indTotTrib`; `pTotTribSN` was accepted.
- `regApTribSN` is required in practice for `opSimpNac = 3` and is not part of
  the 0.5.0 builder subset.
- `E0202`: the taker must not be the provider (B1).
- `E0014`: resending an issued DPS returns duplicate series/number.
- `E0824`: the issuing municipality's parametrization forbids cancelling an
  NFS-e without an identified taker. A cancellation was therefore not
  completed; this is municipal configuration, not a signature result.

## Response contract

The official SEFIN OpenAPI, unavailable without a certificate on 20 September
2026, was retrieved with mutual TLS. See
[`NFSE_POST_RESPONSE.md`](NFSE_POST_RESPONSE.md) for the bytes, the observed
response shapes, and the differences between the OpenAPI and the service.

## Limits

- One certificate, one provider, one municipality, one date and one validator
  version. Production was not contacted.
- No CPF issuer, third-party taker, substitution, or completed event.
- The accepted alternatives may be validator leniency; implementations should
  emit only the recommended profile.

## Private evidence

Requests, responses, the issued NFS-e and the probe scripts are stored in the
ignored `.f0/prodrest-2026-10-14/` directory, 93 files listed with SHA-256 in
its `SHA256SUMS` (SHA-256
`589e64f705af74cd3cd5a74b80ee7a10d335e3c3d6da1bd649de599d4f718ec2`). They
are not redistributed: the signed XML embeds the signer certificate and fiscal
identifiers. This record and its JSON companion contain no CNPJ, CPF, access
key, DPS Id, municipality code or certificate.
