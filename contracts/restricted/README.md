# Restricted contract evidence

The authority for this evidence is the official NFS-e restricted-environment
documentation page:

<https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita>

The freeze resolves and downloads two artifacts from that page:

- `NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727`
- `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209`

`manifest.json` records SHA-256 hashes of the exact official bytes. Only the
`TSIdDPS` and `TSSerieDPS` facets needed by the DPS identity implementation are
audited. This is not an audit of the full DPS schema, XML signature contract,
API, or transmission behavior.

Official ZIP, XLSX, and XSD bytes are stored under the ignored
`.f0/restricted/` directory and are not redistributed by this repository.

Reproduce the freeze from the repository root with:

```console
uv run python scripts/f0_freeze_restricted.py
```

The command fails closed if the official labels, URLs, archive structure, or
audited facets drift. A successful identity freeze still records
`transmission_ready` as `false`.
