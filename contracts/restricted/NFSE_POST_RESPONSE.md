# POST /nfse response contract — retrieval status

## Decision

The current official OpenAPI bytes could not be retrieved through the permitted
public, credential-free documentation access on 20 September 2026. The response
envelope therefore remains unconfirmed and no parser, recovery function, or
recovered-NFS-e validator is implemented from an assumed wire shape.

```text
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
V0.22.1_IMPLEMENTATION_READY = NO
RECOVERED_NFSE_VALIDATOR_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```

## Official endpoints examined

Only HTTP GET requests were made. No certificate, credential, DPS, fiscal-data
endpoint, or operational API method was used.

| Environment | Resource | HTTP status | Media type | Bytes | SHA-256 of returned bytes |
| --- | --- | ---: | --- | ---: | --- |
| Produção Restrita | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/docs/index` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção | `https://sefin.nfse.gov.br/SefinNacional/docs/index` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção Restrita | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/swagger/docs/v1` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção | `https://sefin.nfse.gov.br/SefinNacional/swagger/docs/v1` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |

All four responses were the same Microsoft IIS HTML error page, titled
`403 - Forbidden: Access is denied.` They are not OpenAPI documents and are not
contract evidence.

The two `/swagger/docs/v1` paths were navigation-only candidates found during
endpoint discovery. Their third-party discovery source was not used as
normative evidence, and no third-party response schema was imported into this
repository.

## Unconfirmed requirements

Without the current official OpenAPI document, the following cannot be frozen
safely:

- documented HTTP statuses for `POST /nfse`;
- exact success and error schema names;
- exact field spelling and casing, including `idDps` versus `idDPS`;
- required and optional properties;
- property types, nullability, and `tipoAmbiente` values;
- the exact `MensagemProcessamento` structure.

The official contributors' manual describes synchronous processing at a high
level, but that does not replace the current machine-readable wire contract for
the strict parser proposed in V0.22.1.

## Unblock condition

Implementation requires the currently applicable official OpenAPI bytes to be
made available through an authorized documentation channel. Their exact URL,
size, SHA-256, operation schemas, statuses, fields, and requiredness must then be
recorded before runtime code is added.

No client certificate or operational request will be used merely to bypass the
documentation access restriction.
