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

## Reviewed catalogue changes

### RTC technical notes, marker of 02/10/2026 17h57 (reviewed 15/10/2026)

The weekly run reported `review_required` (`catalogue_updated`) from 5 October
2026. Compared with the Wayback capture of 22/08/2026 (marker 15/07/2026
09h00), the page changed in two entries:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| NT SE/CGNFS-e nº 009 v1.01, dated 11/09/2026, listed 01/10/2026 | 703,145 | `cc86c9402e317e84eb3a9f48bbd5e0b8e3dcd84f2645700190c84d45bf1ea58e` |
| AnexoVI-LeiautesRN_RTC_IBSCBS v1.04.01 (NT 009 v1.01) | 296,297 | `103a150dd6f56ec8edcaa3a453b59a1b0e096d7cd5025d7bd06a387f141ddf39` |
| AnexoVII-IndOp_IBSCBS v1.03.00 (NT 009 v1.01) | 27,475 | `95f30a44ee94adeea57fb92f3a0337b1e62fdc106f393e73894087889be9e5aa` |
| NT SE/CGNFS-e nº 010 v1.00 (NFS-e Via), dated 11/09/2026 | 425,218 | `18cd169f76f7f94975f031d7d14d39baa67c42714d2f031c2b62d791589af104` |

Classification:

- **NT 009 v1.01: `CURRENT_PARTIAL`.** It replaces v1.0.1 (04/06/2026) and adds
  sections 2.9 to 2.16 to the future RTC layout (Anexo VI). Examples: `dest`
  and `indDest` move to `infDPS`, `CST` and `cClassTrib` move, `verCalcIBSCBS`
  is added, and the condominium and `comExt` groups change. It publishes no
  XSD and no implementation date; the schedule "será publicado no portal".
  The note cites Anexo VII v1.02.01, while the page publishes v1.03.00
  (`CONFLICTING` version label, no runtime effect).
- **NT 010 v1.00: out of scope.** It covers the NFS-e Via (road-use NFS-e)
  layout and its acquirer manifestation event, not DPS or the regular NFS-e.

Effect on this library: none now. The builder and parsers do not serialize or
read IBS/CBS groups; they appear only in the frozen schema contract. The pinned
production and restricted XSD bundles did not change. When the RTC layout of
NT 009 reaches an official XSD, the bundle pins report `material_change`, and
the schema contract is reviewed then.

The same review fixed the note detector: the portal labels NT 010 as "Nota
Técnica 010 SE/CGNFS-e nº 010", a format the earlier pattern missed. Notes up
to nº 010 are now reviewed; a higher number reports `review_required` in both
label formats.

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

On 14 October 2026 a reviewed evidence change confirmed the signature profile
and the `POST /nfse` response envelope through the official validator in
Produção Restrita, without waiting for the inquiry; see
[`PRODREST_EMPIRICAL_PROBE.md`](../contracts/restricted/PRODREST_EMPIRICAL_PROBE.md).
The watcher itself stays credential-free and does not perform such requests.
The states are now:

```text
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = YES
POST_RESPONSE_PARSER_IMPLEMENTATION_READY = YES
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
TECHNICAL_QUERY_RESPONSE = PENDING
SIGNATURE_PROFILE_CONFIRMED = YES
SIGNING_IMPLEMENTED = NO
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
TRANSMISSION_READY = NO
```

The requirement above for a complete reply, including Basic Constraints and Key
Usage, applies to the inquiry route. Those two items remain `CONFLICTING` in the
documents and do not block the confirmed profile: they describe the
certificate, and a standard ICP-Brasil e-CNPJ A1, as issued, was accepted by
the validator. The `Signature` position conflict was resolved by the probe.

No runtime V0.30 work starts from a watcher signal alone. The transport uses
stdlib GET over official HTTPS hosts only, with no cookies, Authorization,
client certificate, request body, proxy, or endpoint-operation calls. Redirects,
response bytes, and time are bounded; off-allowlist redirects fail closed.
Regular CI runs only offline mocked tests. Live official requests are confined
to explicit local runs and the dedicated weekly/manual WATCH-1 workflow.
