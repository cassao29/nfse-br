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

The DPS identity contract implemented here is suitable for local deterministic
work and testing only. Transmission remains gated on freezing and auditing the
exact official environment-specific XSD/layout bundle.

## Development

The project requires Python 3.12 or 3.13 and uses
[`uv`](https://docs.astral.sh/uv/) for project management.

```console
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest --cov=src/nfse_br --cov-branch --cov-report=term-missing --cov-fail-under=80
uv build
```

## License

MIT
