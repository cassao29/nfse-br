# Official evidence watchlist (WATCH-1)

This is a read-only observer for evidence that might eventually unlock
the restricted NFS-e `POST /nfse` response contract or the DPS v1.01 XMLDSig
profile. A dedicated GitHub Actions workflow runs it weekly; manual execution
remains available after a relevant portal notice. It is **not** a runtime
milestone or a contract approval. Do not feed its output directly into code
generation or blocker states.

Run from the repository root with Python 3.12 or 3.13:

```console
python scripts/check_official_evidence.py
```

It prints exactly one compact JSON object. `checked_sources` counts official
catalogues successfully parsed, not SEFIN probes or artifact downloads. A
nonzero exit is a request for human review, not permission to implement. The
frozen observer configuration is
[`contracts/restricted/evidence-watchlist.json`](../contracts/restricted/evidence-watchlist.json).
No downloaded artifact is persisted by the script.

## Weekly workflow

[`WATCH-1 official evidence`](../.github/workflows/watch-official-evidence.yml)
runs every Monday at 12:17 UTC (09:17 America/Bahia), using cron
`17 12 * * 1`, and supports manual `workflow_dispatch` from GitHub Actions.
It uses Python 3.12 and only `contents: read`; checkout does not persist
credentials. No secrets, new dependencies, or artifact uploads are required.

The run is green only when the watcher exits with code `0` **and** reports
`status: unchanged`. Every other status or exit, invalid output, and timeout
fails the job with an error annotation. The complete parsed JSON is written
as escaped text to `GITHUB_STEP_SUMMARY`; errors that prevent a usable report
produce a controlled `network_error` summary. Downloaded evidence is never
saved or uploaded, and the workflow creates no issue, PR, commit, release,
or email. A red run calls for human review and changes no contract state.

The regular `CI` workflow continues to run only offline/mocked tests, including
the weekly workflow's success and failure gates. It never runs the live watcher.
The weekly workflow has only schedule/manual triggers, so PRs and pushes run
the regular CI without contacting official sources. The schedule becomes
active after the workflow is merged into the default branch; a first manual
dispatch should then verify its behavior on the GitHub runner. Scheduling
follows the [GitHub Actions schedule semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).

## Sources and frozen reference points

The eight catalogues are the official NFS-e [technical documentation root](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica),
[API catalogue](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao),
[production documentation](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual),
[restricted/test documentation](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/producao-restrita),
[FAQ](https://www.gov.br/nfse/pt-br/biblioteca/perguntas-e-respostas/perguntas-e-respostas-da-nfs-e),
[updates and deployments](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/atualizacoes-e-implantacoes),
[contact channels](https://www.gov.br/nfse/pt-br/canais-de-atendimento), and
[RTC technical notes](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc).
The RTC page is included because it is the official current technical-note
index. Page layout changes alone are not material evidence; the observer checks
the published update marker, relevant links, and pinned download bytes.

The pinned downloadable artifacts are:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Production XSD bundle | 65,640 | `e7935cbd9470527c6cc32984c1b2263e614183bf0139ce2733eaaed2de9a8072` |
| Production Anexo I | 215,196 | `de5bc492959eadc8bfa7540e16939995924f2188f743648eaf84d3b31e9eeb7c` |
| Restricted XSD bundle | 34,933 | `6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc` |
| Restricted Anexo I | 215,056 | `2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9` |
| FAQ v1.00, 08/09/2026 | 1,140,924 | `aa45e008842f1c94e7e175f96df3f6354a23b45b6136db8ed87706d318b462f7` |
| Contributor API manual | 188,158 | `ac2f36e34ff565cc36d67c5d67415c33cc09f27b2dea006e8da9bcd2ddce5581` |

The restricted and production SEFIN documentation paths listed in the JSON
are probed with GET only. Their frozen 403 response (HTML, 1,233 bytes,
SHA-256 `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736`)
is **an access baseline, not evidence of a response contract**. A changed 403
body or an HTML page is reviewable but does not confirm OpenAPI. A candidate
requires HTTP 200, parseable JSON, an OpenAPI/Swagger marker, and a `post`
operation at `/nfse`.

## Signals and exit codes

| Status | Exit | Meaning / next action |
| --- | ---: | --- |
| `unchanged` | 0 | No action. |
| `source_relocated` | 10 | Same pinned bytes at a new official location; verify identity, then make a docs-only repair. |
| `material_change` | 20 | Version, date, size, or hash changed; preserve official bytes and review on an evidence branch, without runtime changes. |
| `review_required` | 20 | New relevant link, catalogue marker, non-OpenAPI SEFIN response, or parse ambiguity; inspect manually. |
| `post_openapi_candidate` | 21 | Preserve official bytes, URL, retrieval time, size, hash, and redirects; review the exact POST contract before considering a parser/recovery milestone. |
| `xmldsig_review_candidate` | 22 | Preserve official material; review the full DPS v1.01 XMLDSig matrix before considering signer work. |
| `network_error` | 30 | Meaningful check was incomplete; retry later and do not infer `unchanged`. |

The JSON also carries independent candidate/material booleans and bounded
metadata signals. At most 64 signals are printed; `omitted_signals` counts any
additional signals, which also require manual review. If several signals
coexist, the status is a single priority summary (`network_error`, POST
candidate, XMLDSig candidate, material change, review required, relocation,
unchanged); review **all** reported signals. The observer does not emit an `unblocked`
status and never edits pins, contracts, source files, Git state, issues, PRs,
or mail. Official evidence must be reviewed and classified manually as
`CURRENT_CONFIRMED`, `CURRENT_PARTIAL`, `CONFLICTING`, `HISTORICAL_ONLY`, or
`UNCONFIRMED` in a separate evidence change.

## Technical inquiry and decision boundary

Mail is outside the watcher. If the inquiry recorded in
[`XMLDSIG_INQUIRY.md`](../contracts/restricted/XMLDSIG_INQUIRY.md) receives an
official reply, record `TECHNICAL_QUERY_RESPONSE_RECEIVED` **only after**
preserving the original message and original attachments, with sizes and
SHA-256 hashes. Verify authority and DPS v1.01 applicability before summarizing
or classifying. Profile confirmation still requires a signed target, exact
Reference URI, CanonicalizationMethod, SignatureMethod, DigestMethod, ordered
transforms, KeyInfo/X509Data representation, certificate-chain embedding, and
resolution of the Basic Constraints, Key Usage, and Signature-position
conflicts. Partial answers do not unlock signing.

Until a separate reviewed evidence change establishes otherwise, the states
remain:

```text
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTATION_READY = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
TECHNICAL_QUERY_RESPONSE = PENDING
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
TRANSMISSION_READY = NO
```

No runtime V0.30 work starts from a watcher signal alone. The transport uses
stdlib GET over official HTTPS hosts only, with no cookies, Authorization,
client certificate, request body, proxy, or endpoint-operation calls. Redirects,
response bytes, and time are bounded; off-allowlist redirects fail closed.
Regular CI runs only offline mocked tests. Live official requests are confined
to explicit local runs and the dedicated weekly/manual WATCH-1 workflow.
