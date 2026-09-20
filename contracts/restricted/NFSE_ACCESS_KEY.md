# NFS-e access-key lexical contract

`NfseAccessKey` represents the exact lexical value defined by the
`TSChaveNFSe` simple type in the official frozen Produção Restrita XSD bundle.
The evidence is pinned to:

```text
bundle size:   34933 bytes
bundle sha256: 6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc
source member: tiposSimples_v1.01.xsd
member size:   69488 bytes
member sha256: 3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4
```

The frozen facets are:

| Property | Value |
| --- | --- |
| Type | `TSChaveNFSe` |
| Base | `xs:string` |
| `whiteSpace` | `preserve` |
| `maxLength` | `50` |
| `pattern` | `[0-9]{6}([0-9A-Z]{14})[0-9]{30}` |

The pattern itself requires exactly 50 ASCII positions. The runtime therefore
preserves the input exactly and performs no stripping, Unicode normalization,
case conversion, coercion, decomposition, checksum, or reconstruction.

Lexical validity does not establish that a key exists, was fiscally
authorized, is authentic, corresponds to any received envelope, or may be
used for transmission. No positional semantics beyond the official XSD facets
are asserted here.

```text
NFSE_ACCESS_KEY_CONTRACT_CONFIRMED = YES
NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = NO
POST_RESPONSE_PARSER_IMPLEMENTED = NO
RECOVERY_IMPLEMENTED = NO
SIGNATURE_PROFILE_CONFIRMED = NO
SIGNING_IMPLEMENTED = NO
TRANSMISSION_READY = NO
```
