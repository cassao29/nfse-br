"""Verify PEP 561 typing from a local wheel in an isolated external consumer."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from zipfile import BadZipFile, ZipFile

_CONSUMER_OK = """\
from dataclasses import replace
from nfse_br.domain import FederalTaxId, MunicipalityCode
from nfse_br.dps import DpsIdentity, DpsNumber, DpsSeries, parse_unsigned_dps
from nfse_br.dps.builder import (
    RestrictedDpsDraft, RestrictedDpsNationalAddress, RestrictedDpsTaker,
    build_unsigned_dps,
)


def rebuild(xml: bytes) -> bytes:
    draft: RestrictedDpsDraft = parse_unsigned_dps(xml)
    optional_taker: RestrictedDpsTaker | None = draft.taker
    if optional_taker is not None:
        recovered_address: RestrictedDpsNationalAddress = optional_taker.address
        postal: str = recovered_address.postal_code
        draft = replace(draft, taker=replace(optional_taker, name=postal))
    return build_unsigned_dps(draft)


number: DpsNumber = DpsNumber(42)
series: DpsSeries = DpsSeries("123")
tax_id: FederalTaxId = FederalTaxId.cnpj("12ABC6780001Z0")
municipality: MunicipalityCode = MunicipalityCode("2927408")
identity: DpsIdentity = DpsIdentity.build(
    municipality=municipality,
    federal_tax_id=tax_id,
    series=series,
    number=number,
)
address: RestrictedDpsNationalAddress = RestrictedDpsNationalAddress(
    municipality=municipality, postal_code="01234567", street="Rua A",
    number="1", neighborhood="Centro", complement=None,
)
taker: RestrictedDpsTaker = RestrictedDpsTaker(
    tax_id=tax_id, name="Synthetic", address=address,
)
"""

_CONSUMER_BAD = """\
from nfse_br.dps import DpsNumber, parse_unsigned_dps
from nfse_br.dps.builder import RestrictedDpsNationalAddress, RestrictedDpsTaker

wrong_value: str = DpsNumber(42).value
parse_unsigned_dps("not-bytes")

def wrong_types(
    address: RestrictedDpsNationalAddress, taker: RestrictedDpsTaker,
) -> None:
    wrong_postal: int = address.postal_code
    wrong_address: str = taker.address
    wrong_taker: str = parse_unsigned_dps(b"synthetic").taker
    RestrictedDpsTaker(tax_id=taker.tax_id, name="Synthetic", address="not-address")
"""

_LOCATION_PROBE = """\
import importlib.util
import json
import runpy
import sys

if importlib.util.find_spec("lxml") is not None:
    raise RuntimeError("unexpected optional dependency")
runpy.run_path("consumer_ok.py")
print(json.dumps({
    name: module.__file__
    for name, module in sys.modules.items()
    if name == "nfse_br" or name.startswith("nfse_br.")
}))
"""


def _run(
    command: Sequence[str], root: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _require_success(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0 or result.stderr:
        raise RuntimeError("consumer subprocess failed")


def smoke_typed_wheel(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    with ZipFile(wheel) as archive:
        markers = [
            name
            for name in archive.namelist()
            if name.startswith("nfse_br/") and name.endswith("/py.typed")
        ]
        if markers != ["nfse_br/py.typed"]:
            raise ValueError("wheel must contain exactly the package typing marker")
    print("PY_TYPED_IN_WHEEL = YES")

    repo = Path(__file__).resolve().parents[1]
    clean_environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "MYPYPATH"):
        clean_environment.pop(name, None)

    with tempfile.TemporaryDirectory(prefix="nfse-br-typed-wheel-") as directory:
        root = Path(directory).resolve()
        if root.is_relative_to(repo):
            raise ValueError("consumer must be outside the checkout")
        consumer_venv = root / "consumer-venv"
        # Create with a clean subprocess environment too: ensurepip must not
        # inherit Python import overrides from the invoking shell.
        _require_success(
            _run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys, venv; "
                    "venv.EnvBuilder(with_pip=True, clear=True).create(sys.argv[1])",
                    str(consumer_venv),
                ],
                root,
                clean_environment,
            )
        )
        python = consumer_venv / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        _require_success(
            _run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-cache-dir",
                    "--no-deps",
                    "--no-index",
                    str(wheel),
                ],
                root,
                clean_environment,
            )
        )
        (root / "consumer_ok.py").write_text(_CONSUMER_OK, encoding="utf-8")
        (root / "consumer_bad.py").write_text(_CONSUMER_BAD, encoding="utf-8")
        # Do not inherit checkout or user-level mypy configuration.
        config = root / "mypy.ini"
        config.write_text("[mypy]\n", encoding="utf-8")
        probe = _run(
            [str(python), "-I", "-c", _LOCATION_PROBE], root, clean_environment
        )
        _require_success(probe)
        locations = json.loads(probe.stdout)
        if not isinstance(locations, dict) or "nfse_br" not in locations:
            raise ValueError("missing installed package location")
        for value in locations.values():
            if not isinstance(value, str):
                raise ValueError("invalid installed module location")
            path = Path(value).resolve(strict=True)
            if (
                not path.is_relative_to(consumer_venv)
                or path.is_relative_to(repo)
                or "site-packages" not in path.parts
            ):
                raise ValueError("consumer import escaped installed wheel")
        print("CONSUMER_IMPORT_FROM_INSTALLED_WHEEL = PASS")
        print("CHECKOUT_LEAK = NO")

        command = [
            sys.executable,
            "-I",
            "-m",
            "mypy",
            "--strict",
            "--show-error-codes",
            "--no-pretty",
            "--no-color-output",
            "--no-incremental",
            "--config-file",
            str(config),
            "--python-executable",
            str(python),
            "--cache-dir",
            str(root / "mypy-cache"),
        ]
        _require_success(_run([*command, "consumer_ok.py"], root, clean_environment))
        print("CONSUMER_TYPING_POSITIVE = PASS")
        negative = _run([*command, "consumer_bad.py"], root, clean_environment)
        codes = re.findall(
            r"^consumer_bad\.py:\d+: error: .*\[([a-z-]+)\]$",
            negative.stdout,
            re.MULTILINE,
        )
        if (
            negative.returncode != 1
            or negative.stderr
            or sorted(codes)
            != [
                "arg-type",
                "arg-type",
                "assignment",
                "assignment",
                "assignment",
                "assignment",
            ]
        ):
            raise RuntimeError("negative consumer did not produce expected type errors")
        print("CONSUMER_TYPING_NEGATIVE = FAILS_AS_EXPECTED")
        print("NEGATIVE_ERROR_CODES = assignment x4, arg-type x2")
    print("Typed wheel consumer smoke test: PASS")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        smoke_typed_wheel(args.wheel)
    except (
        OSError,
        ValueError,
        RuntimeError,
        BadZipFile,
        subprocess.SubprocessError,
    ) as exc:
        print(
            f"Typed wheel consumer smoke test failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
