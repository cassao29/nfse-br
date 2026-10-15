"""Bindings for the confirmed restricted POST /nfse response contract evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = _ROOT / "contracts/restricted/nfse-post-response-contract.json"
_DOC_PATH = _ROOT / "contracts/restricted/NFSE_POST_RESPONSE.md"
_PROBE_PATH = _ROOT / "contracts/restricted/prodrest-empirical-probe.json"

_OPENAPI_SHA256 = "5ab00aeb7a253933e4d3cafa8f2b74992f5e91b6a81c069f7f5a55a5c08d95af"
_FORBIDDEN_HTML_SHA256 = (
    "c55f527e536de44c7980fecece7428ae5a765647495e47008a8a54fa1e434736"
)


def _contract() -> dict[str, object]:
    return cast(
        dict[str, object], json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    )


def test_contract_is_confirmed_from_the_official_openapi_only() -> None:
    contract = _contract()
    openapi = cast(dict[str, object], contract["openapi"])

    assert contract["contract_confirmed"] is True
    assert contract["implementation_ready"] is True
    assert contract["parser_implemented"] is False
    assert contract["transmission_ready"] is False
    assert contract["third_party_contract_data_used"] is False
    assert openapi["sha256"] == _OPENAPI_SHA256
    assert openapi["bytes"] == 14303
    assert openapi["access"] == "mutual_tls"
    assert openapi["raw_artifact_versioned"] is False
    assert cast(str, openapi["url"]).startswith(
        "https://sefin.producaorestrita.nfse.gov.br/"
    )


def test_observed_service_differences_are_recorded() -> None:
    contract = _contract()
    observed = cast(dict[str, list[str]], contract["observed"])
    differences = cast(list[str], contract["openapi_service_differences"])

    assert observed["post_nfse_400_error_item"] == [
        "Codigo",
        "Descricao",
        "Complemento?",
    ]
    assert "idDPS" in observed["post_nfse_400"]
    assert "idDps" in observed["post_nfse_201"]
    assert "idDps" not in observed["get_dps_200"]
    assert observed["get_nfse_200"] == observed["get_nfse_200_after_cancellation"]
    assert observed["get_eventos_collection_405"] == ["message"]
    assert observed["post_nfse_400_duplicate_codes"] == ["E0014"]
    expected_tokens = [
        "Codigo/Descricao/Complemento",
        "NFS-e Id",
        "erro is an array",
        "omits idDps",
        "tipoAmbiente 0",
        "alertas is null",
        "eventos array",
        "Base64 applied twice",
    ]
    assert len(differences) == len(expected_tokens)
    for difference, token in zip(differences, expected_tokens, strict=True):
        assert token in difference


def test_observations_are_bound_to_the_probe_record() -> None:
    contract = _contract()
    probe = json.loads(_PROBE_PATH.read_text(encoding="utf-8"))
    observations = {row["id"]: row for row in probe["api_observations"]}

    assert cast(str, contract["observations_record"]).startswith(_PROBE_PATH.name)
    assert observations["A2"]["request"] == "GET /dps/{id}"
    assert observations["A6"]["codes"] == ["E2401"]
    assert observations["A1"]["codes"] == ["E0014"]


def test_history_keeps_the_unavailable_capture() -> None:
    history = cast(list[dict[str, object]], _contract()["history"])

    assert len(history) == 1
    assert history[0]["capture_date"] == "2026-09-20"
    assert history[0]["contract_confirmed"] is False
    resources = cast(list[dict[str, object]], history[0]["resources"])
    assert {resource["sha256"] for resource in resources} == {_FORBIDDEN_HTML_SHA256}


def test_documentation_states_match_the_contract() -> None:
    document = _DOC_PATH.read_text(encoding="utf-8")
    first_state_block = document.split("```text\n", 1)[1].split("```", 1)[0]

    assert first_state_block == (
        "NFSE_POST_RESPONSE_CONTRACT_CONFIRMED = YES\n"
        "POST_RESPONSE_PARSER_IMPLEMENTATION_READY = YES\n"
        "POST_RESPONSE_PARSER_IMPLEMENTED = NO\n"
        "TRANSMISSION_READY = NO\n"
    )
    assert _OPENAPI_SHA256 in document
    assert _FORBIDDEN_HTML_SHA256 in document
