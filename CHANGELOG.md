# Changelog

## Unreleased

## 0.5.0

### Added

- Public immutable `RestrictedDpsNationalAddress` and `RestrictedDpsTaker`
  aggregates and optional `RestrictedDpsDraft.taker` for the national-taker
  subset of restricted unsigned DPS, integrated in #49.
- Coordinated builder, parser and role-aware identity inspection, with
  independent XML oracles, external-wheel typing/base smokes and local
  pinned-XSD integration evidence from the implementation candidate.

### Compatibility

- Existing constructor calls and XML bytes without taker are preserved;
  the public dataclass shape and parser's accepted language expand explicitly.
  The DPS identity remains independent of the taker.
- Empty or unidentified `toma` groups are now rejected during inspection.
  `check()` and `parse()` remain independent: XSD-valid documents can fail the
  stricter local subset parser, including names of 151–300 characters or a
  missing national address.

### Limitations

- Name/address constraints are explicit local policies; documented official
  CNPJ, name-length and IM conflicts remain unresolved. Published 0.4.1 does
  not contain the taker API. This section describes the 0.5.0 release contract,
  not confirmation of publication.
- No new issuance, signing, transmission, registry lookup, response recovery
  or fiscal calculation capability.

## 0.4.1

### Compatibility

- Added declared Python 3.14 support after Linux and Windows full-suite,
  wheel, typing, lxml/XSD, and local pinned official-bundle integration validation.

### Repository / quality

- Added an independent public Python API contract gate.
- Added external-consumer PEP 561 validation against the installed wheel,
  including positive and expected-negative mypy checks.
- Added structured bug, feature, official-evidence and pull-request templates
  with privacy-safe contribution guidance.

### Documentation

- Added the 60-second synthetic unsigned DPS round-trip demo, with explicit
  checks that remain active under Python optimization.
- Added an exact synthetic DPS XML preview in the README with a byte-level
  anti-drift test, without a standalone generated XML artifact.
- Clarified security-fix support for the latest published minor release line.

## 0.4.0

### Added

- `parse_unsigned_dps`, a public stdlib-only semantic parser for the closed
  restricted DPS subset represented by `RestrictedDpsDraft`.
- `RestrictedDpsChecker.parse`, composing pinned XSD validation with
  `parse_unsigned_dps` while preserving `check()` as the identity-only path.

### Security / hardening

- Semantic DPS parsing fails closed on unknown attributes, fields, namespaces,
  additional fiscal branches, reordered/moved elements, mixed content, and
  unrepresentable structures.
- Parsing preserves exact Decimal values and builder-output byte-exact
  rebuilding, with privacy-safe controlled errors. XML preserves wall-clock
  components and UTC offset, not regional timezone identity or `fold`.
- `RestrictedDpsChecker.parse` preserves stage order, exact input bytes,
  short-circuiting and exception identity.
- `RestrictedDpsChecker.check` remains independent from the stricter semantic
  parser.

### Repository evidence / maintenance

- Added the read-only official evidence WATCH-1 and weekly GitHub Actions
  automation, producing review signals without promoting contract states.
- Hardened SEFIN baseline observation so unchanged responses require final
  URL and redirect-chain equivalence.
- Repaired the relocated official FAQ evidence source without changing frozen
  evidence bytes or blocked runtime contracts.

### Known limitations

- The POST response contract remains unconfirmed; parsing and Base64/GZip
  recovery of POST responses remain unavailable.
- The current DPS XMLDSig algorithm profile remains unconfirmed; signing and
  cryptographic verification remain unavailable.
- Automatic NFS-e Id/access-key conversion remains disabled.
- HTTP/SEFIN transmission remains unavailable.
- Production operation and complete fiscal modeling remain unsupported.
- End-to-end checks with the pinned official bundle remain explicit local
  release gates and are intentionally not run in CI.

## 0.3.0

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

### Security / hardening

- `check-nfse` and `check-unsigned` delegate to their respective composed
  checkers, which pass the same input bytes through each stage.
- The CLI no longer depends on the private XMLSig compatibility adapter.
  The former private structural preflight now delegates to the public DPS
  inspector, and a fail-closed coverage invariant requires it to remain
  branchless.
- Public unsigned DPS inspection retains bounded safe XML parsing and
  privacy-safe controlled errors.

### Known limitations

- The POST response contract remains unconfirmed; POST parsing and Base64/GZip
  recovery are not implemented.
- Automatic NFS-e Id/access-key conversion remains disabled.
- The current XMLDSig algorithm profile remains unconfirmed; signing and
  cryptographic verification are not implemented.
- HTTP/SEFIN integration and transmission remain unavailable.
- Production-environment operation remains unsupported.
- End-to-end checks with the pinned official bundle remain explicit local
  release gates and are intentionally not run in CI.

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
