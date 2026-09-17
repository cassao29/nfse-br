"""Smoke tests for the public package contract."""

import nfse_br


def test_package_exposes_its_version() -> None:
    """The installed package exposes the version declared for v0.1."""
    assert nfse_br.__version__ == "0.1.0"
    assert nfse_br.__all__ == ["__version__"]
