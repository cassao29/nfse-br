"""Freeze the official restricted DPS structural subset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfse_br._f0.dps_schema_contract import freeze_restricted_dps_schema_contract
from nfse_br._f0.restricted_contract import ContractFreezeError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the official restricted DPS structural subset."
    )
    parser.add_argument(
        "--identity-manifest",
        type=Path,
        default=Path("contracts/restricted/manifest.json"),
        help="Path to the frozen V0.4 identity evidence manifest.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".f0/restricted-dps-schema"),
        help="Local directory for ignored official artifact bytes.",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("contracts/restricted/dps-schema-contract.json"),
        help="Path for the deterministic structural contract.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        contract = freeze_restricted_dps_schema_contract(
            identity_manifest_path=args.identity_manifest,
            work_dir=args.work_dir,
            contract_path=args.contract,
        )
    except ContractFreezeError as exc:
        print(f"F0 DPS schema freeze failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(contract, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
