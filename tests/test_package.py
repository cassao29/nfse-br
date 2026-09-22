"""Smoke tests for the public package contract."""

from importlib.metadata import version

import nfse_br


def test_package_exposes_its_version() -> None:
    """The installed package exposes the version declared for v0.3."""
    assert nfse_br.__version__ == "0.3.0"
    assert version("nfse-br") == nfse_br.__version__
    assert nfse_br.__all__ == ["__version__"]
