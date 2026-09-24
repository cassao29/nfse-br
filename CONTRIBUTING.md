# Contributing

This project supports Python 3.12, 3.13, and 3.14 and uses
[`uv`](https://docs.astral.sh/uv/) for dependency and environment management.

Use GitHub Flow: branch from an up-to-date `main`, keep pull requests small,
and use Conventional Commit messages. Do not commit downloaded official
ZIP/XSD/XLSX/PDF artifacts, generated XML, coverage reports, `.f0/` contents,
certificates, keys, or fiscal data.

Install the frozen development environment and run the same core checks used
by CI:

```console
uv sync --frozen --extra xsd
uv run --frozen --extra xsd ruff check .
uv run --frozen --extra xsd ruff format --check .
uv run --frozen --extra xsd mypy src tests scripts examples
uv run --frozen --extra xsd coverage erase
uv run --frozen --extra xsd python -c "from pathlib import Path; Path('build/coverage').mkdir(parents=True, exist_ok=True)"
uv run --frozen --extra xsd pytest \
  --cov=src/nfse_br --cov-branch --cov-report=term-missing \
  --cov-report=json:build/coverage/coverage.json --cov-fail-under=80
uv run --frozen --extra xsd python scripts/check_coverage.py \
  build/coverage/coverage.json
uv build
uv run --frozen --extra xsd python scripts/smoke_base_wheel.py \
  dist/nfse_br-0.4.1-py3-none-any.whl
```

Run the suite under all supported Python versions. Pull requests are checked
on Linux and Windows Server 2022; platform-specific skips must be narrow and
justified. Tests are offline unless a documented local integration procedure
explicitly says otherwise.

Never weaken evidence pins, parser policy, coverage thresholds, or branch
protection merely to make a change pass.
