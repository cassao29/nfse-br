# Recovered NFS-e document information contract

This evidence freeze records only the direct XML paths needed for local,
standard-library structural extraction. It comes from the already-frozen
Produção Restrita XSD bundle; no operational endpoint or third-party source is
part of this contract.

## Source binding

```text
Bundle size:   34933 bytes
Bundle sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
Root QName:    {http://www.sped.fazenda.gov.br/nfse}NFSe
```

| Member | Size | SHA-256 |
| --- | ---: | --- |
| `NFSe_v1.01.xsd` | 738 | `1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0` |
| `tiposComplexos_v1.01.xsd` | 114148 | `6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac` |
| `tiposSimples_v1.01.xsd` | 69488 | `3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4` |

## Exact paths

All element cardinalities below are `1..1`. Where `minOccurs` or `maxOccurs`
is absent in the XSD, this is the XML Schema default rather than a project
inference.

| Path | Declaration |
| --- | --- |
| `NFSe` | global element of type `TCNFSe` |
| `NFSe/infNFSe` | `TCNFSe` direct child of type `TCInfNFSe` |
| `NFSe/infNFSe/@Id` | required `TSIdNFSe` attribute named exactly `Id` |
| `NFSe/infNFSe/nNFSe` | `TCInfNFSe` direct child of type `TSNNFSe` |
| `NFSe/infNFSe/DPS` | `TCInfNFSe` direct child of type `TCDPS` |
| `NFSe/infNFSe/DPS/infDPS` | `TCDPS` direct child of type `TCInfDPS` |
| `NFSe/infNFSe/DPS/infDPS/@Id` | required `TSIdDPS` attribute named exactly `Id` |

The relevant simple types are:

| Type | Base | `whiteSpace` | `maxLength` | `pattern` |
| --- | --- | --- | ---: | --- |
| `TSIdNFSe` | `xs:string` | `preserve` | 53 | `NFS[0-9]{9}[0-9A-Z]{14}[0-9]{27}` |
| `TSNNFSe` | `xs:string` | `preserve` | 13 | `[1-9]{1}[0-9]{0,12}` |
| `TSIdDPS` | `xs:string` | `preserve` | 45 | `DPS[0-9]{7}(1[0-9]{14}\|2[0-9A-Z]{14})[0-9]{20}` |

## Extractor scope

`extract_nfse_document_info` confirms only that local bytes pass the project's
safe XML parsing policy, have the exact NFS-e root, contain unique direct paths
listed above, and carry lexical `NfseId` and embedded DPS identifier values.
The NFS-e number is returned exactly as observed; full `TSNNFSe` assurance
remains the responsibility of XSD validation.

For schema assurance, validate the same bytes first with
`RecoveredNfseValidator`. Structural extraction alone does not establish XSD
validity, authenticity, XML signature validity, ICP-Brasil status, transport
origin, fiscal authorization, or acceptance by SEFIN.

No access key is derived. The frozen evidence continues to prohibit automatic
conversion between `NfseId` and `NfseAccessKey` because their XSD lexical
languages conflict.

```text
NFSE_DOCUMENT_INFO_CONTRACT_CONFIRMED = YES
ID_ACCESS_KEY_CONVERSION_ALLOWED = NO
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```
