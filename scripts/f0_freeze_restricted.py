"""Freeze official restricted-environment DPS identity evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfse_br._f0.restricted_contract import (
    ContractFreezeError,
    freeze_restricted_contract,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze official restricted DPS identity evidence."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".f0/restricted"),
        help="Local directory for ignored official artifact bytes.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("contracts/restricted/manifest.json"),
        help="Path for the deterministic evidence manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        manifest = freeze_restricted_contract(
            work_dir=args.work_dir,
            manifest_path=args.manifest,
        )
    except ContractFreezeError as exc:
        print(f"F0 restricted freeze failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
