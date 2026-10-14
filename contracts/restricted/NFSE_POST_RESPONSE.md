# POST /nfse response contract — retrieval status

## Decision

On 14 October 2026 the official SEFIN Nacional OpenAPI for Produção Restrita
was retrieved with mutual TLS and compared with real responses from the same
service. The maintainer authorized certificate-authenticated access on that
date; see [`PRODREST_EMPIRICAL_PROBE.md`](PRODREST_EMPIRICAL_PROBE.md). The
response envelope is now confirmed for the restricted environment, including
the differences between the OpenAPI and the service listed below.

```text
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = YES
POST_RESPONSE_PARSER_IMPLEMENTATION_READY = YES
POST_RESPONSE_PARSER_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```

A future parser must follow the observed service where it differs from the
OpenAPI, and must fail closed on any other shape.

## Official OpenAPI (14 October 2026)

| Environment | Resource | Access | HTTP status | Media type | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- |
| Produção Restrita | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/swagger/docs/v1` | mutual TLS | 200 | `application/json` | 14303 | `5ab00aeb7a253933e4d3cafa8f2b74992f5e91b6a81c069f7f5a55a5c08d95af` |

The document is Swagger 2.0, title `API NFS-e - Sefin Nacional`. Its
description requires mutual TLS with an ICP-Brasil A1 or A3 certificate with
client authentication, JSON messages, UTF-8 XML 1.0 documents, XMLDSig and
gzip with Base64. The bytes are kept in the ignored `.f0/` directory and are
not redistributed. Production was not contacted.

Documented operations and response schemas:

| Operation | Documented responses |
| --- | --- |
| `POST /nfse` | 201 `NFSePostResponseSucesso`; 400, 403, 500 `NFSePostResponseErro` |
| `GET /nfse/{chaveAcesso}` | 200 `NFSeGetResponseSucesso`; 400, 401, 403, 404 `ResponseErro` |
| `GET /dps/{id}` | 200 `DpsGetResponse`; 400, 404 `ResponseErro` |
| `HEAD /dps/{id}` | 200, 400, 404 without body |
| `POST /nfse/{chaveAcesso}/eventos` | 201 `EventosPostResponseSucesso`; 400, 401 `ResponseErro` |
| `GET /nfse/{chaveAcesso}/eventos/{tipoEvento}/{numSeqEvento}` | 200 `EventosPostResponseSucesso`; 401, 404, 422 `ResponseErro` |

`NFSePostResponseSucesso` requires `tipoAmbiente`, `versaoAplicativo`,
`dataHoraProcessamento`, `idDps`, `chaveAcesso` and `nfseXmlGZipB64`, with
optional `alertas`. `NFSePostResponseErro` requires `tipoAmbiente`,
`versaoAplicativo`, `dataHoraProcessamento` and `erros`, with optional `idDPS`.
`MensagemProcessamento` has optional `codigo`, `descricao` and `complemento`.

## Observed responses

All observed bodies were `application/json; charset=utf-8`, except where noted.

| Request | HTTP | Observed shape |
| --- | ---: | --- |
| `POST /nfse`, issued | 201 | `tipoAmbiente`, `versaoAplicativo`, `dataHoraProcessamento`, `idDps`, `chaveAcesso`, `nfseXmlGZipB64`, `alertas: null` |
| `POST /nfse`, rejected | 400 | `tipoAmbiente`, `versaoAplicativo`, `dataHoraProcessamento`, `idDPS`, `erros: [{Codigo, Descricao, Complemento?}]` |
| `GET /nfse/{chaveAcesso}`, found | 200 | `nfseXmlGZipB64` with the same bytes returned by the issuance |
| `GET /nfse/{chaveAcesso}`, unknown | 404 | `erro: {codigo, descricao}` (`E2401`) |
| `GET /dps/{id}`, issued | 200 | `tipoAmbiente`, `versaoAplicativo`, `dataHoraProcessamento`, `chaveAcesso` |
| `GET /dps/{id}`, rejected DPS | 404 | `tipoAmbiente: 0`, `dataHoraProcessamento`, `erro: {codigo, descricao}` (`E2404`) |
| `HEAD /dps/{id}` | 200 / 404 | no body |
| `POST /nfse/{chaveAcesso}/eventos`, rejected | 400 | `erro: [{codigo, descricao}]` |
| `GET /nfse/{chaveAcesso}/eventos` | 405 | `{"message": ...}`; the collection route is not exposed |
| `POST /nfse` with an already issued DPS | 400 | `erros` with `E0014` |

## Differences between the OpenAPI and the service

1. `POST /nfse` 400: `erros` items use `Codigo`, `Descricao` and
   `Complemento`, not the documented lower-case `MensagemProcessamento` names.
2. `POST /nfse` 201: `idDps` carries the NFS-e `Id` (`NFS` prefix), not the DPS
   identifier described by the OpenAPI.
3. `POST /nfse/{chaveAcesso}/eventos` 400: `erro` is an array, while
   `ResponseErro` documents a single object.
4. `GET /dps/{id}` 200: `idDps`, documented as required, is absent.
5. `GET /dps/{id}` 404: `tipoAmbiente` is `0`, outside the documented
   `1 | 2` enumeration, and `versaoAplicativo`, documented as required, is
   absent.
6. `alertas` is `null` on success, not an empty array.

## Still unconfirmed

- 403 and 500 bodies of `POST /nfse`;
- a non-null `alertas` item;
- a successful event response and the event retrieval route;
- production behavior.

## History: 20 September 2026

The OpenAPI could not be retrieved through public, credential-free access. All
four official documentation URLs returned the same Microsoft IIS HTML page,
`403 - Forbidden: Access is denied.`:

| Environment | Resource | HTTP status | Media type | Bytes | SHA-256 of returned bytes |
| --- | --- | ---: | --- | ---: | --- |
| Produção Restrita | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/docs/index` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção | `https://sefin.nfse.gov.br/SefinNacional/docs/index` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção Restrita | `https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional/swagger/docs/v1` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |
| Produção | `https://sefin.nfse.gov.br/SefinNacional/swagger/docs/v1` | 403 | `text/html` | 1233 | `c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736` |

At that date the record stated that no client certificate or operational
request would be used to bypass the restriction. The maintainer revised that
limit on 14 October 2026. A third-party copy of the OpenAPI was used only to
locate the official route and the request field name before the official
bytes were retrieved; no third-party schema is recorded here.
