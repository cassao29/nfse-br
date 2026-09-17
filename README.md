# nfse-br

`nfse-br` is an open-source Python toolkit for Brazil's National NFS-e
ecosystem.

The current 0.1 development line contains package infrastructure and local
domain primitives. It does not yet implement fiscal models, DPS documents,
schema validation, XML signatures, issuance, or transmission.

## Current scope

The library currently provides immutable primitives for NFS-e environments,
lexical CPF/CNPJ identifiers, IBGE municipality codes, competence dates, and a
working local DPS identity value.

CPF and CNPJ checksum validation is not implemented yet. Issuance,
transmission, DPS XML, XSD validation, and XMLDSig are also outside the current
scope.

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

## Development

The project requires Python 3.12 or 3.13 and uses
[`uv`](https://docs.astral.sh/uv/) for project management.

```console
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests scripts/check_coverage.py
mkdir -p build/coverage
uv run pytest --cov=src/nfse_br --cov-branch --cov-report=term-missing \
  --cov-report=json:build/coverage/coverage.json --cov-fail-under=80
uv run python scripts/check_coverage.py build/coverage/coverage.json
uv build
```

The executable coverage gates require at least 80% combined coverage for the
library, 90% aggregate branch coverage for `src/nfse_br/_f0/`, and 90% branch
coverage for `src/nfse_br/_f0/dps_schema_contract.py`. Gate decisions use the
exact counters from Coverage.py JSON rather than rounded display percentages.

## License

MIT
