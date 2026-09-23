# Release procedure

This checklist is for the `0.3.0` release. A release operator must run it from
a clean, protected `main`; completing release preparation alone does not
authorize a tag, GitHub Release, TestPyPI upload, or PyPI upload.

## Release contract

| Classification | 0.3.0 surface |
| --- | --- |
| Public and supported | `CompetenceDate`, `DomainValidationError`, `FederalTaxId`, `FederalTaxIdKind`, `MunicipalityCode`, `NfseEnvironment`; opt-in CPF/CNPJ validators in their documented submodules; `DpsSeries`, `DpsNumber`, `DpsIdentity`, `DpsDocumentError`, `inspect_unsigned_dps`; `RestrictedDpsDraft`, `build_unsigned_dps`; `NfseAccessKey`, `NfseId`, `NfseDocumentError`, `NfseDocumentInfo`, `extract_nfse_document_info`, `NfseConsistencyError`, `validate_nfse_document_consistency`; optional `RestrictedDpsChecker`, `RestrictedDpsXsdValidator`, `RecoveredNfseChecker`, `RecoveredNfseValidator`, `XsdValidationError`; `nfse-br check-unsigned`; `nfse-br check-nfse` |
| Private or experimental | `nfse_br._f0`, `nfse_br._xmlsig`, freeze tooling, schema-contract tooling |
| Not supported | issuance/transmission, HTTP/SEFIN, XMLDSig signer/verifier, certificate/private-key handling, production, complete fiscal modeling, allocation/persistence |

## Development addition after 0.3.0 (not released)

`nfse_br.dps.parse_unsigned_dps(bytes) -> RestrictedDpsDraft` is a development
API for the builder's restricted subset only, not an addition to the historical
0.3.0 release contract above. The package version remains 0.3.0 until separately
authorized release preparation. No tag, publication, or dependency change is
authorized by this feature.

For a future release, verify `build(parse(build(draft))) == build(draft)`,
all draft fields, fail-closed unknown-field handling, and privacy-safe errors.
Draft equality holds for ordinary fixed-offset timestamps, but must not be
promised for ambiguous regional datetimes: XML preserves wall time and offset,
not timezone identity or `fold`. Test both repeated-hour variants offline.

The optional `RestrictedDpsChecker.parse(bytes) -> RestrictedDpsDraft` composes
pinned XSD validation with the same parser. It preserves same-object bytes,
stage order, short-circuiting and exception identity. Its existing `check()`
continues to use identity-only inspection, not the stricter semantic parser.
For a future release, verify mixed sequential reuse and both independent paths.
The new composition inherits the datetime/round-trip limitation above unchanged.

Standalone parsing is stdlib-only and provides no XSD assurance; the checker
requires the optional XSD extra and adds schema validation. Neither performs
I/O, signature verification, fiscal authorization or transmission.
Existing POST-response/XMLDSig blockers
remain unchanged. See [DPS_DOCUMENT_PARSER.md](../contracts/restricted/DPS_DOCUMENT_PARSER.md).

## Checklist

- [ ] Confirm protected local and remote `main` are identical and the working
  tree is clean.
- [ ] Confirm all required Python 3.12/3.13 Linux and Windows checks pass on
  the exact release commit.
- [ ] Confirm `pyproject.toml`, `nfse_br.__version__`, and `uv.lock` all report
  `0.3.0`.
- [ ] Review the `0.3.0` changelog and public/private/unsupported contract.
- [ ] Confirm `v0.3.0` does not exist locally or remotely and that PyPI does
  not already expose `nfse-br 0.3.0`.
- [ ] Confirm the protected `pypi` environment and Trusted Publisher remain
  configured without modification. The publisher identity must be owner
  `cassao29`, repository `nfse-br`, workflow `release.yml`, environment
  `pypi`.
- [ ] Build wheel and sdist twice from clean checkouts and compare their logical
  contents, metadata, and unpacked file hashes.
- [ ] Inspect wheel and sdist for generated XML, official ZIP/XSD/XLSX/PDF
  files, `.f0/`, coverage data, agent state, credentials, certificates, and
  keys.
- [ ] Install the base wheel without dependencies outside the checkout and run
  public imports, CPF/CNPJ checks, the builder, CLI help/version, and the
  controlled missing-extra path.
- [ ] Install the wheel with the `xsd` extra outside the checkout and verify the
  pinned `lxml` version, XSD imports, and validator behavior without any
  automatic bundle download.
- [ ] Execute the README quickstart from a clean checkout.
- [ ] Run both official pinned-bundle local integrations for DPS and recovered
  NFS-e XML; these checks remain intentionally outside CI.
- [ ] Run the repository's secret scan over every new commit and the final
  release tree.
- [x] GitHub Private Vulnerability Reporting is configured and was verified
  through the repository API on 2026-09-19.
- [ ] Obtain explicit authorization immediately before creating or pushing the
  `v0.3.0` tag. Tag creation is the action that starts publication.
- [ ] After successful OIDC publication and public PyPI verification, obtain
  deliberate authorization before creating the GitHub Release.

## Trusted Publisher identity

The existing Trusted Publisher must retain this exact identity:

| Field | Value |
| --- | --- |
| PyPI project | `nfse-br` |
| Owner | `cassao29` |
| Repository | `nfse-br` |
| Workflow | `release.yml` |
| Environment | `pypi` |

Do not recreate or modify the publisher or environment during release
preparation. The `pypi` environment must continue to require manual approval,
deny administrative bypass, restrict deployments to release tags, and contain
no PyPI secret.

The dedicated `Release` workflow runs only for `vMAJOR.MINOR.PATCH` tag pushes.
Its `build` job has read-only repository access and no OIDC permission. The
`publish-pypi` job has no checkout, receives only the verified distribution
artifact from `build`, and has only `actions: read` plus `id-token: write`.
The official PyPA action uses Trusted Publishing, uploads attestations, and is
configured to fail rather than hide an already-published version.

The release order is: validate `main`; reconfirm the tag and PyPI version are
absent; obtain explicit authorization; create and push the explicit tag; allow
the build to finish; manually approve the protected `pypi` deployment; publish
through OIDC; verify public files, hashes, provenance, and clean installation;
then create a deliberate GitHub Release. The workflow does not create or move
tags, create GitHub Releases, or write repository contents.

The official restricted bundle integration remains a local gate:
`OFFICIAL_BUNDLE_E2E_IN_CI = NOT_RUN_BY_DESIGN`. Passing package and schema
checks is not fiscal authorization and does not enable transmission.
