# Restricted DPS structural contract

`dps-schema-contract.json` freezes the provider-independent DPS structure
needed to design a future builder. It is derived from the official Produção
Restrita XSD bundle whose SHA-256 is:

```text
6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
```

The artifact is also bound to the V0.4 identity manifest with SHA-256:

```text
2d8049958e7dcfa5e4e002a45cca8d526df83ab9c42b57eff2320017f85b3b8c
```

Starting at `TCDPS`, the freeze follows every complex-type reference found in
the official schema. The resulting closed subset contains 52 complex types and
91 simple types: every type used directly plus the custom simple-type bases
reached through `restriction/@base`. It preserves sequence and choice order,
occurrence cardinalities, attributes, restriction bases, and supported facets.
The source members are recorded with their exact size and SHA-256.

The closure assertion performs a graph traversal rooted exclusively at
`TCDPS`; disconnected types cannot satisfy it. QName checks resolve the
effective namespace binding at each `type`, `base`, and `ref` use, including
inherited and locally redefined prefixes. XML Schema builtins are restricted
to those observed in the frozen profile, while `ds:Signature` is accepted only
in the XMLDSig namespace.

Here, `dps_structural_subset` means a subset of the complete NFS-e bundle, not
a partial traversal of `TCDPS`: the full local dependency closure of `TCDPS` is
included. The complex schema includes `tiposSimples_v1.01.xsd` and imports the
XMLDSig schema. The sole external particle, `ds:Signature`, remains an external
reference and is not resolved or interpreted by this tooling.

The structural contract itself has SHA-256:

```text
794c5904c4d81381d73050df63df541de587a08e195b7fb25f553937a43b67b0
```

Reproduce it from the repository root with:

```console
uv run python scripts/f0_freeze_dps_schema_contract.py
```

The command downloads and checks the already pinned official ZIP. It fails
closed if the bytes, selected schema members, reviewed structure, or existing
contract differ. Official XSD bytes remain under the ignored `.f0/` directory
and are not redistributed.

This artifact is repository evidence, not runtime configuration. The optional
local validator is independently pinned to the exact bundle and compilation
profile described in [`DPS_XSD_VALIDATOR.md`](DPS_XSD_VALIDATOR.md). Neither
artifact authorizes XML generation, signing, issuance, or transmission;
`transmission_ready` remains `false`.

One boundary recorded for future builder work is that the official
`TSNumDPS` pattern is `[1-9]{1}[0-9]{0,14}`. `DpsNumber` follows this more
specific field constraint and therefore accepts values from 1 through
999999999999999. The broader `TSIdDPS` identity pattern still describes the
15-position wire component; it does not independently express every `nDPS`
field constraint.
