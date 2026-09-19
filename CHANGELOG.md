# Changelog

## 0.1.0

### Added

- Typed primitives for NFS-e environment, federal tax identifiers,
  municipality codes, competence dates, DPS series, DPS numbers, and DPS
  identity.
- Explicit, opt-in CPF and numeric/alphanumeric CNPJ check-digit validation.
- Frozen provenance for the official restricted-environment evidence and a
  derived restricted DPS schema contract.
- Local validation against the pinned restricted XSD bundle through the
  optional `xsd` extra.
- A deterministic unsigned DPS builder for a deliberately limited restricted
  subset.
- A private structural signature preflight that rejects ambiguous targets;
  this is not signing or cryptographic verification.
- The `nfse-br check-unsigned` CLI with machine-readable results and bounded
  file reads.
- Linux and Windows Server 2022 CI for Python 3.12 and 3.13.
- A tested executable quickstart for generating a synthetic unsigned DPS from
  a checkout.

### Security / hardening

- XML parsing denies DTDs, entities, external resolution, unexpected roots,
  and inputs above the documented size limit.
- Signature preflight requires one unambiguous direct `infDPS`, rejects
  competing identifiers and pre-existing signatures, and reconstructs its
  identity from the document fields.
- CLI diagnostics use controlled JSON error codes without echoing fiscal
  payloads or caller-provided paths.
- Base-wheel smoke tests verify that generation and non-XSD operations remain
  usable without `lxml`.

### Known limitations

- Issuance, authorization, transmission, HTTP/SEFIN integration, certificate
  handling, and private-key handling are not implemented.
- The applicable XMLDSig algorithm profile remains unresolved; signing and
  cryptographic verification are not implemented.
- The builder covers only the documented restricted-environment subset, not a
  complete fiscal model.
- The production environment is unsupported.
- End-to-end validation with the pinned official bundle is a local release
  gate and is not executed in CI by design.

