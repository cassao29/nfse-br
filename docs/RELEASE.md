# Release procedure

This checklist is for the `0.5.0` release. A release operator must run it from
a clean, protected `main`; completing release preparation alone does not
authorize a tag, GitHub Release, TestPyPI upload, or PyPI upload.
Unchecked items describe future release-audit work, not results obtained during
release preparation. Historical observations below are not substitutes for
verification on the exact candidate.

## Release contract

0.5.0 expands the local Python API and restricted DPS subset with a national
taker, as implemented in #49. It adds no issuance, signing or transmission.
Compared with published 0.4.1, the public shape and local XML acceptance expand;
the release-prep PR introduces no further functional changes.

| Classification | 0.5.0 surface |
| --- | --- |
| Public and supported | `CompetenceDate`, `DomainValidationError`, `FederalTaxId`, `FederalTaxIdKind`, `MunicipalityCode`, `NfseEnvironment`; opt-in CPF/CNPJ validators in their documented submodules; `DpsSeries`, `DpsNumber`, `DpsIdentity`, `DpsDocumentError`, `inspect_unsigned_dps`, `parse_unsigned_dps`; `RestrictedDpsDraft`, `RestrictedDpsNationalAddress`, `RestrictedDpsTaker`, `build_unsigned_dps`; `NfseAccessKey`, `NfseId`, `NfseDocumentError`, `NfseDocumentInfo`, `extract_nfse_document_info`, `NfseConsistencyError`, `validate_nfse_document_consistency`; optional `RestrictedDpsChecker` with `check()` and `parse()`, `RestrictedDpsXsdValidator`, `RecoveredNfseChecker`, `RecoveredNfseValidator`, `XsdValidationError`; `nfse-br check-unsigned`; `nfse-br check-nfse` |
| Private or experimental | `nfse_br._f0`, `nfse_br._xmlsig`, freeze tooling, schema-contract tooling |
| Not supported | issuance/transmission, HTTP/SEFIN, XMLDSig signer/verifier, certificate/private-key handling, production, complete fiscal modeling, allocation/persistence |

### Restricted DPS parsing contract

`nfse_br.dps.parse_unsigned_dps(bytes) -> RestrictedDpsDraft` was introduced in 0.4.0
for the builder's restricted subset only, not a generic DPS Nacional parser.

Verify `build(parse(build(draft))) == build(draft)`,
all draft fields, fail-closed unknown-field handling, and privacy-safe errors.
Draft equality holds for ordinary fixed-offset timestamps, but must not be
promised for ambiguous regional datetimes: XML preserves wall time and offset,
not timezone identity or `fold`. Test both repeated-hour variants offline.

The optional `RestrictedDpsChecker.parse(bytes) -> RestrictedDpsDraft` composes
pinned XSD validation with the same parser. It preserves same-object bytes,
stage order, short-circuiting and exception identity. Its existing `check()`
continues to use identity-only inspection, not the stricter semantic parser.
Verify mixed sequential reuse and both independent paths.
The composition inherits the datetime/round-trip limitation above unchanged.

For the national taker, verify independent CPF, numeric CNPJ and alphanumeric
CNPJ XML vectors against both the builder and parser. Recover every address/name
field, including optional complement. Preserve old golden bytes with taker=None
and verify changing only the taker never changes infDPS@Id. Preserve rejection
of duplicate/displaced/wrapped identifiers and wrong namespaces, including
unidentified empty toma. Verify valid-invalid-valid reuse and privacy-safe
repr/str/errors, without claiming asdict or caller logging are redacted.

Keep local policies distinct from XSD: names of 151–300 characters or missing
addresses may pass check but fail parse. Do not resolve documented official
conflicts by changing classifications during release. See
[DPS_NATIONAL_TAKER.md](../contracts/restricted/DPS_NATIONAL_TAKER.md).

Standalone parsing is stdlib-only and provides no XSD assurance; the checker
requires the optional XSD extra and adds schema validation. Neither performs
I/O, signature verification, fiscal authorization or transmission.
Existing POST-response/XMLDSig blockers
remain unchanged. See [DPS_DOCUMENT_PARSER.md](../contracts/restricted/DPS_DOCUMENT_PARSER.md).

## Checklist

- [ ] Confirm protected local and remote `main` are identical and the working
  tree is clean.
- [ ] Confirm all required Python 3.12/3.13/3.14 Linux and Windows checks pass on
  the exact release commit.
- [ ] Confirm `pyproject.toml`, `nfse_br.__version__`, and `uv.lock` all report
  `0.5.0` (the root package version in `uv.lock`); run pinned uv 0.12.13
  `uv lock --check` and confirm external locked packages remain unchanged.
- [ ] Review the `0.5.0` changelog and public/private/unsupported contract.
- [ ] Immediately before tag creation, confirm `v0.5.0` does not exist locally
  or remotely, GitHub Release v0.5.0 is absent, and the official PyPI version
  JSON returns HTTP 404 for `nfse-br 0.5.0`. Network/auth errors are not absence.
- [ ] Verify the parsing contract above: byte-exact builder-output rebuilding,
  timezone/fold caveat, fail-closed fields, privacy, and independent checker paths.
- [ ] Confirm the protected `pypi` environment and Trusted Publisher remain
  configured without modification. The publisher identity must be owner
  `cassao29`, repository `nfse-br`, workflow `release.yml`, environment
  `pypi`.
- [ ] Build wheel and sdist twice from independent clean checkouts of the exact
  release commit using Python 3.12 and uv 0.12.13, outside the principal checkout.
  Record raw SHA-256 values and compare member sets, logical contents, metadata
  and unpacked file hashes. Investigate any raw-byte difference; never ignore
  internal artifact differences. Require only `nfse_br-0.5.0-py3-none-any.whl`
  and `nfse_br-0.5.0.tar.gz` as distributions.
- [ ] Verify wheel METADATA and sdist PKG-INFO: nfse-br 0.5.0, Python
  `>=3.12,<3.15`, Python 3.12/3.13/3.14 classifiers and Typing :: Typed.
  Require exactly one `nfse_br/py.typed` member in the wheel.
- [ ] Inspect wheel and sdist for generated XML, official ZIP/XSD/XLSX/PDF
  files, `.f0/`, coverage data, agent state, credentials, certificates, and
  keys.
- [ ] Install the base wheel without dependencies outside the checkout and run
  public imports, CPF/CNPJ checks, the builder and parser round-trip, CLI
  help/version, and the controlled missing-extra path. Confirm `lxml` is absent.
- [ ] Run the external-consumer typed-wheel smoke: positive typing passes;
  negative typing fails with assignment x4 and arg-type x2. Confirm no checkout
  leak. Exercise the new aggregates and optional taker using the candidate wheel,
  not historical PyPI 0.4.1 or an editable install.
- [ ] Install the wheel with the `xsd` extra outside the checkout and verify the
  pinned `lxml` version, XSD imports, and validator behavior without any
  automatic bundle download.
- [ ] Execute the README quickstart from a clean checkout.
- [ ] On the exact release commit, run `scripts/validate_official_dps_xsd.py`
  and `scripts/validate_official_nfse_xsd.py` using only the existing local
  `.f0/restricted/restricted-xsd.zip`. Require size `34933` bytes and SHA-256
  `6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc`
  before and after execution. Use scripts from the exact clean release checkout
  and an external Python 3.14 venv containing the candidate wheel and pinned lxml.
  Prove version 0.5.0 and nfse_br.__file__ under that venv's site-packages, not
  checkout/src; record Python/lxml/libxml2 versions and the wheel hash tested.
  Run offline, including independent taker vectors, XSD/check/parse differences,
  negative cases and valid-invalid-valid reuse. Stop if absent or mismatched;
  do not download or refresh evidence automatically. Prior implementation
  results are not execution on the release artifact. These integrations remain
  intentionally outside CI.
- [ ] Run the existing Gitleaks default-rule procedure with redacted output over
  every new commit, the final release tree and unpacked distributions. Do not
  substitute a heuristic search or silently change scanner configuration.
- [x] GitHub Private Vulnerability Reporting is configured and was verified
  through the repository API on 2026-09-19.
- [ ] Obtain explicit authorization immediately before creating or pushing the
  `v0.5.0` tag at the audited SHA. Pushing the tag starts the Release workflow;
  creating a local tag alone does not publish anything.
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

## Separate authorization gates

1. Review and merge the release-prep PR; verify post-merge CI. This does not
   authorize a tag or publication.
2. Audit the exact candidate commit and artifacts using the checklist above.
   Record hashes and confirm the unchanged tree and all publication absences.
3. Obtain explicit authorization to create and push v0.5.0 at that exact SHA,
   rechecking main, tag/Release/PyPI absence immediately beforehand. The tag push
   starts Release; never move/recreate a tag to repair a failure.
4. After its build passes, require separate manual approval of the protected
   pypi environment deployment, then allow OIDC publication.
5. Independently verify public PyPI version, files and hashes against the audited
   artifacts, public provenance/attestations and a clean PyPI install. Do not
   treat upload success as public verification.
6. Obtain separate explicit authorization before creating the GitHub Release
   for the existing tag. Do not attach duplicate wheel/sdist assets manually.

The workflow does not create or move tags, create GitHub Releases, or write
repository contents. Preserve all historical releases, especially v0.4.1 at
`0b4f098da4e51e105ac9055c2da906d1e2217c2e`. Never publish rebuilt development
artifacts under that historical version.

The official restricted bundle integration remains a local gate:
`OFFICIAL_BUNDLE_E2E_IN_CI = NOT_RUN_BY_DESIGN`. Passing package and schema
checks is not fiscal authorization and does not enable transmission.
