"""Experimental Python 3.14 wheel probe; does not declare supported Python versions."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from email.parser import Parser
from pathlib import Path
from zipfile import BadZipFile, ZipFile

_IMPORT_PROBE = """\
import json
import sys
import lxml
import nfse_br
import nfse_br.xsd
print(json.dumps({
    name: module.__file__
    for name, module in sys.modules.items()
    if name == "nfse_br" or name.startswith("nfse_br.")
}))
"""


def _run(
    stage: str, command: Sequence[str], cwd: Path, environment: dict[str, str]
) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("experimental subgate failed")
    except (OSError, subprocess.SubprocessError, RuntimeError):
        print(f"{stage} = FAIL", flush=True)
        raise
    print(f"{stage} = PASS", flush=True)
    return result.stdout


def _requirements(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("expected a nonempty flat dependency group")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("unsupported dependency group entry")
    return [str(item) for item in value]


def probe_python314(wheel: Path) -> None:
    if sys.version_info[:2] != (3, 14):
        raise ValueError("probe requires Python 3.14")
    print("Python 3.14 experimental compatibility probe", flush=True)
    wheel = wheel.resolve(strict=True)
    repo = Path(__file__).resolve().parents[1]
    with (repo / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    if project["project"]["requires-python"] != ">=3.12,<3.14":
        raise ValueError("supported project metadata changed")
    dev = _requirements(project["dependency-groups"]["dev"])
    xsd = _requirements(project["project"]["optional-dependencies"]["xsd"])
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1 or names.count("nfse_br/py.typed") != 1:
            raise ValueError("invalid wheel metadata or typing marker")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
        requirements = metadata.get_all("Requires-Python", [])
        # Hatch serializes the same two constraints in sorted order. Accept only
        # these exact clauses, not an expanded support range or a repacked wheel.
        if len(requirements) != 1 or sorted(requirements[0].split(",")) != [
            "<3.14",
            ">=3.12",
        ]:
            raise ValueError("supported wheel metadata changed")
    print("SUPPORTED_METADATA_UNCHANGED = YES", flush=True)
    print("REQUIRES_PYTHON_BYPASS = EXPLICIT", flush=True)
    print("PYTHON_314_SUPPORT_DECLARED = NO", flush=True)
    clean = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "MYPYPATH"):
        clean.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="nfse-br-python314-") as directory:
        root = Path(directory).resolve()
        if root.is_relative_to(repo):
            raise ValueError("probe environment must be outside checkout")
        environment = root / "probe-venv"
        _run(
            "PROBE_VENV_314",
            [
                sys.executable,
                "-I",
                "-c",
                "import sys, venv; "
                "venv.EnvBuilder(with_pip=True, clear=True).create(sys.argv[1])",
                str(environment),
            ],
            root,
            clean,
        )
        python = str(
            environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        pip = [
            python,
            "-I",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
        ]
        _run("DEV_DEPS_314_INSTALL", [*pip, *dev], root, clean)
        _run("LXML_314_INSTALL", [*pip, *xsd], root, clean)
        _run(
            "WHEEL_INSTALL_314",
            [*pip, "--no-deps", "--no-index", "--ignore-requires-python", str(wheel)],
            root,
            clean,
        )
        locations = json.loads(
            _run("IMPORT_PROBE_314", [python, "-I", "-c", _IMPORT_PROBE], repo, clean)
        )
        if not isinstance(locations, dict) or "nfse_br" not in locations:
            raise ValueError("missing installed package location")
        for value in locations.values():
            if not isinstance(value, str):
                raise ValueError("invalid installed package location")
            path = Path(value).resolve(strict=True)
            if (
                not path.is_relative_to(environment)
                or path.is_relative_to(repo)
                or "site-packages" not in path.parts
            ):
                raise ValueError("checkout import leak")
        for gate in ("WHEEL_IMPORT_314", "LXML_IMPORT_314", "XSD_IMPORT_314"):
            print(f"{gate} = PASS", flush=True)
        print("CHECKOUT_LEAK_314 = NO", flush=True)
        output = _run("PYTEST_314", [python, "-I", "-m", "pytest", "-q"], repo, clean)
        # Report counts, not assertion tracebacks or captured document payloads.
        summary = re.findall(r"\d+ passed(?:, \d+ skipped)?", output)
        if summary:
            print(f"PYTEST_314_COUNTS = {summary[-1]}", flush=True)
        _run(
            "MYPY_314",
            [
                python,
                "-I",
                "-m",
                "mypy",
                "--python-version",
                "3.14",
                "src",
                "tests",
                "scripts",
                "examples",
            ],
            repo,
            clean,
        )
        _run("RUFF_314", [python, "-I", "-m", "ruff", "check", "."], repo, clean)
        _run(
            "FORMAT_314",
            [python, "-I", "-m", "ruff", "format", "--check", "."],
            repo,
            clean,
        )
        for filename, gate in (
            ("smoke_base_wheel.py", "BASE_WHEEL_SMOKE_314"),
            ("smoke_typed_wheel.py", "TYPED_WHEEL_SMOKE_314"),
        ):
            smoke_output = _run(
                gate,
                [
                    python,
                    "-I",
                    str(repo / "scripts" / filename),
                    "--ignore-requires-python",
                    str(wheel),
                ],
                root,
                clean,
            )
            if filename == "smoke_typed_wheel.py":
                for line in smoke_output.splitlines():
                    if line in {
                        "PY_TYPED_IN_WHEEL = YES",
                        "CONSUMER_IMPORT_FROM_INSTALLED_WHEEL = PASS",
                        "CHECKOUT_LEAK = NO",
                        "CONSUMER_TYPING_POSITIVE = PASS",
                        "CONSUMER_TYPING_NEGATIVE = FAILS_AS_EXPECTED",
                        "NEGATIVE_ERROR_CODES = assignment, arg-type",
                    }:
                        print(line, flush=True)
    print("OFFICIAL_BUNDLE_E2E_IN_314 = NOT_RUN_BY_DESIGN")
    print("Python 3.14 experimental compatibility probe: PASS")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        probe_python314(args.wheel)
    except (
        OSError,
        ValueError,
        RuntimeError,
        BadZipFile,
        subprocess.SubprocessError,
    ) as exc:
        print(
            "Python 3.14 experimental compatibility probe failed: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        if sys.version_info[:2] != (3, 14):
            print(
                "Python 3.14 is required for this experimental probe.", file=sys.stderr
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
