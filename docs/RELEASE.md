# Release procedure

This checklist is for the first `0.1.0` release. A release operator must run it
from a clean, protected `main`; completing documentation alone does not
authorize a tag, GitHub Release, TestPyPI upload, or PyPI upload.

## Release contract

| Classification | 0.1.0 surface |
| --- | --- |
| Public and supported | `nfse_br.domain` primitives; opt-in CPF/CNPJ validators in their documented submodules; `DpsSeries`, `DpsNumber`, `DpsIdentity`; the restricted unsigned draft/builder; optional XSD validator; `nfse-br check-unsigned` |
| Private or experimental | `nfse_br._f0`, `nfse_br._xmlsig`, freeze tooling, schema-contract tooling |
| Not supported | issuance/transmission, HTTP/SEFIN, XMLDSig signer/verifier, certificate/private-key handling, production, complete fiscal modeling, allocation/persistence |

## Checklist

- [ ] Confirm local and remote `main` are identical and the working tree is
  clean.
- [ ] Confirm all required Linux and Windows checks pass on the release commit.
- [ ] Confirm `pyproject.toml` and `nfse_br.__version__` both report `0.1.0`.
- [ ] Review `CHANGELOG.md` and the public/private/unsupported contract.
- [ ] Build wheel and sdist twice from clean checkouts and compare their logical
  contents, metadata, and unpacked file hashes.
- [ ] Inspect wheel and sdist for generated XML, official ZIP/XSD/XLSX/PDF
  files, `.f0/`, coverage data, agent state, credentials, certificates, and
  keys.
- [ ] Install the base wheel without dependencies outside the checkout and run
  public imports, CPF/CNPJ checks, the builder, CLI help/version, and the
  controlled missing-extra path.
- [ ] Install the wheel with the `xsd` extra outside the checkout and verify the
  XSD imports and validator behavior.
- [ ] Execute the README quickstart from a clean checkout and validate the
  generated XML locally with the pinned official bundle.
- [ ] Run the repository's secret scan over every commit to be released.
- [ ] Enable and verify GitHub Private Vulnerability Reporting. Do not release
  while the private reporting channel described in `SECURITY.md` is absent.
- [ ] Confirm the `0.1.0` tag does not already exist locally or remotely.
- [ ] Confirm the `nfse-br` project name is available on PyPI and that the
  releasing account or organization controls it before any upload. A public
  404 alone does not establish ownership.
- [ ] Decide explicitly whether to use TestPyPI; it is optional and must not be
  treated as production publication.
- [ ] Obtain explicit authorization before creating the tag, GitHub Release,
  TestPyPI upload, PyPI project, trusted-publishing configuration, or PyPI
  upload.

The official restricted bundle integration remains a local gate:
`OFFICIAL_BUNDLE_E2E_IN_CI = NOT_RUN_BY_DESIGN`. Passing package and schema
checks is not fiscal authorization and does not enable transmission.
