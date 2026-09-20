# XMLDSig DPS v1.01 technical inquiry

## Delivery record

- Status: `SENT`
- Sent at: `2026-09-20T09:11:54.753-03:00`
- Channel: official municipal NFS-e technical contact
- Recipient: `nfse.tecnologia@sefaz.salvador.ba.gov.br`
- Subject: `Confirmação do perfil XMLDSig da DPS v1.01 — NFS-e Padrão Nacional`
- Delivery reference: retained privately by the maintainer
- Protocol: not provided
- Automatic response: none observed as of `2026-09-20T12:15:08Z`
- Stated response time: not provided
- Response status: `PENDING`
- Sent body SHA-256: `597a6b2764856df112b9a442ee6067bb2496118c369478a549ce7ec855880b70`
- Attachments: none
- `signature_profile_confirmed`: `false`
- `transmission_ready`: `false`

An automatic response does not constitute a technical answer. The signature
profile remains unconfirmed until an applicable, authoritative response is
received and reviewed.

## Exact inquiry sent

```text
Prezados,

estamos desenvolvendo uma biblioteca Python open source para geração e
validação local de documentos da NFS-e Padrão Nacional.

O Portal Nacional da NFS-e orienta que dúvidas de contribuintes e empresas
sejam encaminhadas inicialmente ao Município e, quando necessário, o próprio
Município consulte a gestão nacional.

A dúvida abaixo é exclusivamente técnica e diz respeito ao perfil XMLDSig
aplicável à DPS v1.01 dos esquemas nacionais atuais.

Caso este não seja o canal competente, solicitamos, por gentileza, o
encaminhamento ao responsável técnico municipal pela NFS-e Padrão Nacional,
SEFIN/ADN, ou ao interlocutor do Município junto à SE/CGNFS-e.

Para implementar de forma interoperável a assinatura da DPS v1.01, pedimos
a confirmação do perfil XMLDSig aplicável ao bundle de Produção Restrita
NFSe-ESQUEMAS_XSD-PRODREST-v1.01-20260727 e ao Anexo I
ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-PRODREST-v1.01-20260209.

Favor confirmar expressamente:

1. a URI de SignatureMethod;
2. a URI de DigestMethod;
3. a URI de CanonicalizationMethod, inclusive uso de comentários e forma
   exclusiva ou inclusiva;
4. a lista ordenada de Transform/@Algorithm;
5. o elemento assinado e a forma exata de Reference/@URI, inclusive se deve
   ser "#" seguido do Id não qualificado de infDPS;
6. a composição obrigatória de KeyInfo/X509Data: somente o certificado final
   em X509Certificate ou também a cadeia;
7. os requisitos de Basic Constraints e Key Usage, diante da diferença entre
   o Anexo I e as seções 17.1–17.2 do Perguntas e Respostas v1.00 de
   08/09/2026; e
8. a posição correta de Signature, pois o XSD v1.01 e a regra E0714 a colocam
   como filha direta de DPS após infDPS, enquanto a linha de leiaute a imprime
   abaixo de infDPS.

Esta consulta trata apenas do perfil nacional da DPS v1.01; não pressupõe
regras de NF-e, ABRASF municipal ou NFS-e Via e não contém dados fiscais,
certificado ou chave privada.

Referências:
Repositório: https://github.com/cassao29/nfse-br
Release: https://github.com/cassao29/nfse-br/releases/tag/v0.1.0

Atenciosamente,
Projeto nfse-br
```
