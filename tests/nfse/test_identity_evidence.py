"""Tests for the frozen NFS-e identity evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_frozen_identity_evidence_keeps_lexical_conflict_fail_closed() -> None:
    contract_path = (
        _REPOSITORY_ROOT / "contracts" / "restricted" / "nfse-identity-contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract["authority"] == "official_frozen_and_current"
    assert contract["environment"] == "restricted"
    assert contract["bundle"] == {
        "sha256": "6c7e0510d3ecff4454f291f4e10b742d27a4818f23aab181494f96d0ea79f3dc",
        "size": 34_933,
    }
    assert contract["annex_i"]["sha256"] == (
        "2ae2ac9f91efa9b64f0c9ed97acaf18bb7513b090fae39ba5bda59187e64d9e9"
    )
    assert contract["source_members"] == {
        "NFSe_v1.01.xsd": {
            "sha256": (
                "1dd8f543060a4ba6f355693f1fa5d79a269acae7c3dfe42d621f62911cfebac0"
            ),
            "size": 738,
        },
        "tiposComplexos_v1.01.xsd": {
            "sha256": (
                "6f792f408a33c11e799042a8d61cac7d1c9f5992c53e07e60ce75a15f157d1ac"
            ),
            "size": 114_148,
        },
        "tiposSimples_v1.01.xsd": {
            "sha256": (
                "3d8171c9b7c9a82ecb48eed9a96485f2077006e7d21db6cd182839dd34dbb5e4"
            ),
            "size": 69_488,
        },
    }

    identity = contract["identity_chain"]["id_attribute"]
    assert identity["name"] == "Id"
    assert identity["type"] == "TSIdNFSe"
    assert identity["use"] == "required"
    assert identity["base"] == "xs:string"
    assert identity["effective_length"] == 53
    assert identity["facets"] == {
        "maxLength": 53,
        "pattern": "NFS[0-9]{9}[0-9A-Z]{14}[0-9]{27}",
        "whiteSpace": "preserve",
    }

    access_key = contract["ts_chave_nfse"]
    assert access_key["effective_length"] == 50
    assert access_key["facets"] == {
        "maxLength": 50,
        "pattern": "[0-9]{6}([0-9A-Z]{14})[0-9]{30}",
        "whiteSpace": "preserve",
    }

    assert contract["relationships"]["lexical"] == {
        "access_key_pattern": "[0-9]{6}([0-9A-Z]{14})[0-9]{30}",
        "classification": "CONFLICTING",
        "confirmed": False,
        "id_without_prefix_pattern": "[0-9]{9}[0-9A-Z]{14}[0-9]{27}",
        "neither_language_contains_the_other": True,
    }
    assert contract["relationships"]["semantic"]["classification"] == (
        "CURRENT_CONFIRMED"
    )
    assert contract["relationships"]["semantic"]["confirmed"] is True
    assert contract["relationships"]["conversion"]["allowed"] is False
    assert contract["semantic_source"] == {
        "date": "2026-05-05",
        "document": "Nota Técnica SE/CGNFS-e nº 008",
        "field": "CHAVE DE ACESSO DA NFS-E",
        "instruction": 'Informar o id da NFS-e sem o prefixo "NFS".',
        "page": 16,
        "pdf_page_index": 15,
        "published_xml_path": "NFSe/infNFSe/id",
        "retrieved_at": "2026-09-20",
        "section": "2.4.5",
        "sha256": ("3d1dd84ec118f8c732af2f8ec874a9df0399a5cf08a8a97fd83ef19a9e823bf5"),
        "size": 1_194_919,
        "title": "Especificações Técnicas do DANFSe",
        "url": (
            "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/"
            "nt-008-se-cgnfse-danfse-20260505.pdf/@@download/file"
        ),
        "version": "1.0",
    }
    assert contract["project_synthetic_fixture_is_normative_evidence"] is False
    assert contract["transmission_ready"] is False


def test_frozen_identity_and_access_key_languages_are_not_equivalent() -> None:
    id_without_prefix = re.compile(r"[0-9]{9}[0-9A-Z]{14}[0-9]{27}")
    access_key = re.compile(r"[0-9]{6}([0-9A-Z]{14})[0-9]{30}")

    id_only = "0" * 9 + "0" * 11 + "A" + "0" * 2 + "0" * 27
    access_key_only = "0" * 6 + "A" + "0" * 13 + "0" * 30

    assert id_without_prefix.fullmatch(id_only) is not None
    assert access_key.fullmatch(id_only) is None
    assert access_key.fullmatch(access_key_only) is not None
    assert id_without_prefix.fullmatch(access_key_only) is None
