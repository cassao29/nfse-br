# nfse-br

`nfse-br` is an open-source Python toolkit for Brazil's National NFS-e
ecosystem.

The current 0.1 development line contains package infrastructure, local domain
primitives, and a deliberately small unsigned restricted DPS builder. It does
not implement a complete fiscal model, XML signatures, issuance, or
transmission. Local DPS XSD validation is available through an optional
dependency.

## Current scope

The library currently provides immutable primitives for NFS-e environments,
lexical CPF/CNPJ identifiers, IBGE municipality codes, competence dates, and a
working local DPS identity value.

CPF and CNPJ checksum validation is not implemented yet. Issuance,
transmission, complete DPS XML generation, and XMLDSig are also outside the
current scope.

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

The DPS identity contract implemented here is suitable for local deterministic
work and testing only. Transmission remains gated on freezing and auditing the
exact official environment-specific XSD/layout bundle.

## Contract evidence

The working identity can be audited against exact official restricted-
environment bytes with `scripts/f0_freeze_restricted.py`. The resulting
SHA-256 provenance and audited facets are recorded in
`contracts/restricted/manifest.json`; downloaded artifacts remain under the
ignored `.f0/` directory and are not redistributed.

This evidence covers only DPS identity and series facets. Transmission remains
unavailable and `transmission_ready` remains `false`.

The derived restricted DPS structural subset is recorded separately in
`contracts/restricted/dps-schema-contract.json`. It is bound to the identity
manifest and official XSD ZIP by SHA-256, but remains repository evidence—not
a runtime XSD validator or XML builder.

## Local XSD validation

Install the optional `xsd` extra to validate XML bytes locally against the
exact frozen Produção Restrita bundle:

```console
uv sync --frozen --extra xsd
```

```python
from nfse_br.xsd import RestrictedDpsXsdValidator

validator = RestrictedDpsXsdValidator(bundle_bytes)
validator.validate(xml_bytes)
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

## Unsigned restricted DPS builder

`nfse_br.dps.builder` constructs deterministic unsigned XML for one explicit
restricted-profile subset: CNPJ provider, national service location, service
code and description, service amount, and caller-supplied minimal tax codes.
It derives `infDPS@Id` from the same municipality, CNPJ, series, and number
written to the XML.

```python
from nfse_br.dps.builder import RestrictedDpsDraft, build_unsigned_dps

xml_bytes = build_unsigned_dps(draft)
```

Building uses only the standard library and does not implicitly validate,
sign, transmit, read files, or access the network. The optional validator is a
separate explicit call. Monetary values use exact `Decimal` input with no
silent rounding, and the timestamp must already contain an allowed whole-hour
UTC offset. See
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

Install the optional XSD support and check one local unsigned DPS against the
pinned restricted schema and structural preflight:

```console
pip install 'nfse-br[xsd]'
nfse-br check-unsigned documento.xml --bundle esquemas.zip
python -m nfse_br check-unsigned documento.xml --bundle esquemas.zip
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
uv run --frozen --extra xsd mypy src tests scripts
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
`src/nfse_br/cli.py`. Gate decisions use exact counters from Coverage.py JSON
rather than rounded display percentages.

CI also installs the built base wheel into a fresh virtual environment without
dependencies or the `xsd` extra. The official restricted ZIP is not distributed
or fetched in CI; its end-to-end compilation remains the explicit local command
documented with the frozen profile.

## License

MIT
