# Changelog

## Unreleased

### Added

- `RestrictedDpsChecker`, a composed optional-XSD API that validates an unsigned
  restricted DPS against the pinned schema, then performs public structural
  inspection and returns `DpsIdentity`.
- `RecoveredNfseChecker`, a composed local API for already-recovered NFS-e XML
  that runs pinned XSD validation, structural extraction, and confirmed
  NFS-e/DPS consistency checks and returns `NfseDocumentInfo`.
- `DpsDocumentError` and public `inspect_unsigned_dps`, moving unsigned DPS
  structural inspection out of the private XMLDSig surface while preserving
  the existing CLI and private compatibility adapter.

## 0.2.0

### Added

- `NfseAccessKey`, an exact lexical primitive for the frozen `TSChaveNFSe`
  contract.
- `NfseId`, an exact lexical primitive for the frozen `TSIdNFSe` contract.
- `RecoveredNfseValidator` for already-recovered NFS-e XML using the pinned
  restricted XSD bundle.
- `NfseDocumentInfo`, `NfseDocumentError`, and
  `extract_nfse_document_info` for local structural extraction.
- `NfseConsistencyError` and `validate_nfse_document_consistency` for the
  officially confirmed NFS-e/embedded-DPS consistency rules.
- The `nfse-br check-nfse DOCUMENT --bundle BUNDLE` command.
- Frozen evidence for NFS-e identity, access keys, document paths, and
  NFS-e/DPS consistency.

### Security / hardening

- Structural extraction is limited to 1 MiB and uses the existing safe XML
  parser policy.
- Exact QNames and direct paths are required, with ambiguous structures
  rejected fail-closed.
- Public errors and representations redact fiscal identifiers and payloads.
- Consistency enforcement is restricted to invariants classified
  `CURRENT_CONFIRMED` by the frozen evidence.
- `check-nfse` reads the document once with a fixed bound and passes the same
  bytes through XSD validation, structural extraction, and consistency checks.
- Automatic conversion between `NfseId` and `NfseAccessKey` remains blocked
  because the current official XSD lexical contracts conflict.

### Known limitations

- The POST response contract is not confirmed; no POST parser or Base64/GZip
  recovery is implemented.
- Automatic access-key conversion is not implemented.
- The current XMLDSig profile remains unconfirmed; signing and cryptographic
  verification are not implemented.
- HTTP/SEFIN integration and transmission are unavailable.
- The production environment remains outside the supported scope.
- End-to-end validation with the pinned official bundle remains a local
  release gate and is not executed in CI by design.

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
