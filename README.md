# nfse-br

`nfse-br` is an open-source Python toolkit for Brazil's National NFS-e
ecosystem.

The current 0.1 development line contains package infrastructure, local domain
primitives, and a deliberately small unsigned restricted DPS builder. It does
not implement a complete fiscal model, XML signatures, issuance, or
transmission. Local DPS XSD validation is available through an optional
dependency.

## Release 0.1.0 contract

The supported public surface for 0.1.0 is deliberately small:

- domain primitives from `nfse_br.domain`;
- opt-in CPF and CNPJ check-digit validation from their documented domain
  submodules;
- `DpsSeries`, `DpsNumber`, and `DpsIdentity` from `nfse_br.dps`;
- `RestrictedDpsDraft` and `build_unsigned_dps` from
  `nfse_br.dps.builder`;
- `RestrictedDpsXsdValidator`, `RecoveredNfseValidator`, and
  `XsdValidationError` from `nfse_br.xsd`, when the `xsd` extra is installed;
  and
- the `nfse-br check-unsigned` command.

Modules below `nfse_br._f0` and `nfse_br._xmlsig`, together with freeze and
schema-contract tooling, are private or experimental implementation details.
They may change without being treated as public API.

Version 0.1.0 does not support issuance or transmission, HTTP/SEFIN calls,
XMLDSig signing or cryptographic verification, certificate or private-key
handling, production-environment operation, a complete fiscal model, or
number allocation and persistence. See the [changelog](CHANGELOG.md) for the
release summary and known limitations.

## Quickstart from a checkout

This path uses the repository checkout directly; it does not assume a PyPI
release. It requires Python 3.12 or 3.13 and `uv` (CI currently uses
`uv 0.12.13`).

```console
git clone https://github.com/cassao29/nfse-br.git
cd nfse-br
uv sync --frozen
uv run --frozen python -c "from pathlib import Path; Path('build/quickstart').mkdir(parents=True, exist_ok=True)"
uv run --frozen python examples/build_unsigned_dps.py --output build/quickstart/dps.xml
```

The last command prints `Unsigned synthetic DPS written.` and creates
`build/quickstart/dps.xml`. It refuses to overwrite an existing file. The
example uses fixed synthetic data and writes the exact bytes returned by
`build_unsigned_dps()`; generation needs neither `lxml`, a schema bundle, nor
network access after the checkout has been installed.

Schema validation is a separate operation. First, explicitly obtain and audit
the pinned official restricted artifacts:

```console
uv run --frozen python scripts/f0_freeze_restricted.py --work-dir .f0/restricted --manifest contracts/restricted/manifest.json
```

That preparation step accesses `gov.br`, validates the discovered artifacts
against the frozen evidence, and writes the ignored bundle as
`.f0/restricted/restricted-xsd.zip`. It is never called by the example or the
validator. With the bundle present, install the optional XSD support and check
the generated document:

```console
uv sync --frozen --extra xsd
uv run --frozen --extra xsd nfse-br check-unsigned build/quickstart/dps.xml --bundle .f0/restricted/restricted-xsd.zip
```

Success emits exactly:

```json
{"status":"ok","stage":"complete","code":null,"transmission_ready":false}
```

Exit code `0` means XSD validation and the unsigned-DPS structural preflight
passed. Exit code `1` means the document was rejected; `2` means usage,
dependency, file, or bundle preparation failed. Passing these checks is not
fiscal authorization, signature validation, or permission to transmit.

## Current scope

The library currently provides immutable primitives for NFS-e environments,
lexical CPF/CNPJ identifiers, IBGE municipality codes, competence dates, and a
working local DPS identity value.

Explicit CPF and CNPJ check-digit validation is available separately from
lexical construction. Issuance, transmission, complete DPS XML generation,
and XMLDSig remain outside the current scope.

## Explicit CPF and CNPJ check digits

`FederalTaxId.cpf()` deliberately remains lexical. Call the separate validator
when mathematical CPF check digits are required:

```python
from nfse_br.domain import FederalTaxId
from nfse_br.domain.cpf import validate_cpf_check_digits

identifier = FederalTaxId.cpf("11144477735")
validate_cpf_check_digits(identifier)
```

The CPF calculation follows the two-stage modulo-11 algorithm described by
the [UFSC technical teaching material](https://canzian.prof.ufsc.br/fisicacomjavascript/exemplos/cpf/index.html).
That reference is technical rather than an official Receita Federal standard.
The validator additionally rejects all ten repeated-digit sequences as local
policy; it deliberately accepts `12345678909` under the mathematical rule.

`FederalTaxId.cnpj()` deliberately remains lexical and normalizes ASCII letters
to uppercase. Call the separate validator when mathematical CNPJ check digits
are required:

```python
from nfse_br.domain import FederalTaxId
from nfse_br.domain.cnpj import validate_cnpj_check_digits

identifier = FederalTaxId.cnpj("12ABC34501DE35")
validate_cnpj_check_digits(identifier)
```

The implementation follows the Receita Federal
[CNPJ check-digit manual](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf),
pages 3–4: ASCII value minus 48, the documented modulo-11 weights, and two
numeric check digits. It also explicitly rejects the all-zero identifier.
A correct CPF or CNPJ checksum does not establish registration, cadastral
status, ownership, fiscal authorization, or permission to transmit.
`check-unsigned` does not call either validator.

## DPS identity

The local working contract composes a 45-position identity from the `DPS`
prefix, a seven-digit municipality code, the derived CPF/CNPJ inscription type,
a fourteen-position federal document, a five-position padded series, and a
fifteen-position padded DPS number. CPF values are left-padded for composition,
and alphanumeric CNPJ values remain strings.

Series validation reflects only the current working lexical evidence; it does
not define a software/API series allocation convention.
Lexically distinct series values that produce the same padded component map to
the same logical `DpsIdentity` value and therefore compare as equal identities.

The DPS identity contract is backed by frozen official restricted-environment
XSD and layout bytes and is suitable for local deterministic work and testing.
Transmission remains unavailable: the supported DPS subset is deliberately
limited and the current XMLDSig algorithm profile is not confirmed.

## Contract evidence

The working identity can be audited against exact official restricted-
environment bytes with `scripts/f0_freeze_restricted.py`. The resulting
SHA-256 provenance and audited facets are recorded in
`contracts/restricted/manifest.json`; downloaded artifacts remain under the
ignored `.f0/` directory and are not redistributed.

The identity manifest covers the DPS identity and series facets. The separate
structural contract covers the reviewed builder/validator subset. Neither
artifact confirms the current XMLDSig algorithms, fiscal authorization, or
transmission; `transmission_ready` remains `false`.

The derived restricted DPS structural subset is recorded separately in
`contracts/restricted/dps-schema-contract.json`. It is bound to the identity
manifest and official XSD ZIP by SHA-256 and remains repository evidence; the
runtime does not load that JSON as configuration.

## Local XSD validation

Install the optional `xsd` extra to validate XML bytes locally against the
exact frozen Produção Restrita bundle:

```console
uv sync --frozen --extra xsd
```

The constructor accepts only the pinned official ZIP bytes and never downloads
schemas. `validate()` accepts at most 1 MiB of UTF-8 XML bytes, requires the
exact `{http://www.sped.fazenda.gov.br/nfse}DPS` root, returns `None` on success,
and otherwise raises a privacy-safe `XsdValidationError`. Each instance is
intended for sequential use.

This proves only safe parsing and conformance to the compiled restricted XSD.
It does not verify signatures, certificates, fiscal semantics, authorization,
or SEFIN acceptance. See
[`contracts/restricted/DPS_XSD_VALIDATOR.md`](contracts/restricted/DPS_XSD_VALIDATOR.md)
for the compilation profile and explicit local integration command.

Already-recovered NFS-e XML bytes can be checked separately against the NFS-e
entrypoint from the same pinned bundle:

```python
from nfse_br.xsd import RecoveredNfseValidator

validator = RecoveredNfseValidator(bundle_bytes)
validator.validate(nfse_xml_bytes)
```

This validates XML structure against the pinned restricted XSD bundle. It does
not verify XML signatures, fiscal authorization, or transport origin. The
library still has no POST-response parser, Base64/GZip recovery, HTTP client,
or transmission support. See
[`contracts/restricted/NFSE_RECOVERED_VALIDATOR.md`](contracts/restricted/NFSE_RECOVERED_VALIDATOR.md)
for the exact NFS-e closure and local integration command.

## Unsigned restricted DPS builder

`nfse_br.dps.builder` constructs deterministic unsigned XML for one explicit
restricted-profile subset: CNPJ provider, national service location, service
code and description, service amount, and caller-supplied minimal tax codes.
It derives `infDPS@Id` from the same municipality, CNPJ, series, and number
written to the XML.

Building uses only the standard library and does not implicitly validate,
sign, transmit, read files, or access the network. The optional validator is a
separate explicit call. Monetary values use exact `Decimal` input with no
silent rounding, and the timestamp must already contain an allowed whole-hour
UTC offset. The executable example in the quickstart supplies every field. See
[`contracts/restricted/DPS_UNSIGNED_BUILDER.md`](contracts/restricted/DPS_UNSIGNED_BUILDER.md)
for the supported mapping and limits.

## XML signature preflight

The private `nfse_br._xmlsig` package performs a fail-closed structural check
of unsigned builder output before any future signature operation. It requires
the unique direct `infDPS`, rejects pre-existing signatures and alternative
identifiers, and recomputes the target Id from `cLocEmi`, provider CNPJ,
series, and DPS number. It does not sign, verify cryptography, or replace XSD
validation.

The frozen XMLDSig schema defines grammar but leaves algorithm attributes as
open URIs. The detailed RSA-SHA1/SHA-1/C14N profile found in official material
belongs to the historical v1.00.02 manual and is not treated as confirmation
for the current restricted v1.01 bundle. See
[`contracts/restricted/DPS_XMLDSIG_PROFILE.md`](contracts/restricted/DPS_XMLDSIG_PROFILE.md).

## Unsigned DPS check CLI

After following the checkout quickstart, check one local unsigned DPS against
the pinned restricted schema and structural preflight:

```console
uv run --frozen --extra xsd nfse-br check-unsigned build/quickstart/dps.xml --bundle .f0/restricted/restricted-xsd.zip
```

The command reads only explicitly named regular files, classifying the opened
descriptor rather than relying on a prior path check. Symbolic links are
rejected where the platform provides `O_NOFOLLOW`; otherwise the opened target
must itself be a regular file. XML input is limited to 1 MiB and the bundle
read to the pinned profile size. The command writes one JSON object to stdout:
exit code `0` means both checks passed, `1` means the document was rejected,
and `2` means usage, dependency, file, or bundle preparation failed. For
example:

```json
{"status":"ok","stage":"complete","code":null,"transmission_ready":false}
```

`--help`, `--version`, package import, and the unsigned builder remain usable
without `lxml`. A successful result is not fiscal authorization, signature
validation, or permission to transmit.

## Development

The project requires Python 3.12 or 3.13 and uses
[`uv`](https://docs.astral.sh/uv/) for project management.

```console
uv sync --frozen --extra xsd
uv run --frozen --extra xsd ruff check .
uv run --frozen --extra xsd ruff format --check .
uv run --frozen --extra xsd mypy src tests scripts examples
mkdir -p build/coverage
uv run --frozen --extra xsd pytest \
  --cov=src/nfse_br --cov-branch --cov-report=term-missing \
  --cov-report=json:build/coverage/coverage.json --cov-fail-under=80
uv run --frozen --extra xsd python scripts/check_coverage.py \
  build/coverage/coverage.json
uv build
python scripts/smoke_base_wheel.py dist/nfse_br-0.1.0-py3-none-any.whl
```

The executable coverage gates require at least 80% combined coverage for the
library, 90% aggregate branch coverage for `src/nfse_br/_f0/`, 90% branch
coverage for `src/nfse_br/_f0/dps_schema_contract.py`, 90% aggregate branch
coverage for `src/nfse_br/xsd/`, and 90% branch coverage for
`src/nfse_br/dps/builder.py`, and 90% branch coverage for
`src/nfse_br/_xmlsig/preflight.py`, and 90% branch coverage for
`src/nfse_br/cli.py`, and 90% branch coverage for
`src/nfse_br/domain/cnpj.py`, and 90% branch coverage for
`src/nfse_br/domain/cpf.py`. Gate decisions use exact counters from Coverage.py
JSON rather than rounded display percentages.

CI also installs the built base wheel into a fresh virtual environment without
dependencies or the `xsd` extra. The official restricted ZIP is not distributed
or fetched in CI; its end-to-end compilation remains the explicit local command
documented with the frozen profile.

## License

MIT

See [CONTRIBUTING.md](CONTRIBUTING.md) for development instructions and
[SECURITY.md](SECURITY.md) for the vulnerability-reporting policy. The
maintainer release procedure is in [docs/RELEASE.md](docs/RELEASE.md).
