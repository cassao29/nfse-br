# nfse-br

`nfse-br` is an open-source Python toolkit for Brazil's National NFS-e
ecosystem.

Version 0.1 contains package infrastructure only: a typed `src` layout,
development tooling, tests, coverage enforcement, and continuous integration.
It does not yet implement fiscal models, DPS documents, schema validation,
XML signatures, issuance, or transmission.

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
