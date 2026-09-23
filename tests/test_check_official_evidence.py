"""Offline gates for the official-source observer and its GET-only transport."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.request import Request

import pytest
from scripts import check_official_evidence as watch

CATALOGUE_URL = (
    "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual"
)
ARTIFACT_URL = "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/nfse-esquemas_xsd.zip"
SEFIN_BASE = "https://sefin.nfse.gov.br/SefinNacional"
SEFIN_URL = f"{SEFIN_BASE}/swagger/docs/v1"
GOOD_BYTES = b"frozen official zip"
DENIED_BYTES = b"known official 403"


class FakeTransport:
    def __init__(self, responses: dict[str, watch.Response | watch.WatchError]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, url: str) -> watch.Response:
        self.calls.append(url)
        response = self.responses[url]
        if isinstance(response, watch.WatchError):
            raise response
        return response


def html_page(
    *,
    label: str = "NFSe-ESQUEMAS_XSD-v1.01",
    href: str = ARTIFACT_URL,
    updated: str = "15/08/2026 09h58",
    extra: str = "",
) -> bytes:
    return (
        '<span class="documentModified"><span>Atualizado em</span>'
        f'<span class="value">{updated}</span></span>'
        '<div id="content-core">'
        f'<a href="{href}">{label}</a>{extra}'
        '</div><div id="viewlet-below-content-body">'
    ).encode()


def response(
    url: str, body: bytes, *, status: int = 200, content_type: str = "text/html"
) -> watch.Response:
    return watch.Response(status, content_type, body, url)


def baseline() -> tuple[watch.Watchlist, FakeTransport]:
    config = watch.Watchlist(
        catalogues=(
            watch.Catalogue("production_docs", CATALOGUE_URL, "15/08/2026 09h58"),
        ),
        artifacts=(
            watch.Artifact(
                "production_xsd",
                "production_docs",
                "^NFSe-ESQUEMAS_XSD",
                ARTIFACT_URL,
                len(GOOD_BYTES),
                hashlib.sha256(GOOD_BYTES).hexdigest(),
            ),
        ),
        sefin_bases=(SEFIN_BASE,),
        sefin_paths=("swagger/docs/v1",),
        sefin_status=403,
        sefin_content_type="text/html",
        sefin_size=len(DENIED_BYTES),
        sefin_sha256=hashlib.sha256(DENIED_BYTES).hexdigest(),
    )
    transport = FakeTransport(
        {
            CATALOGUE_URL: response(CATALOGUE_URL, html_page()),
            ARTIFACT_URL: response(
                ARTIFACT_URL, GOOD_BYTES, content_type="application/zip"
            ),
            SEFIN_URL: response(SEFIN_URL, DENIED_BYTES, status=403),
        }
    )
    return config, transport


def test_frozen_watchlist_loads_all_official_sources_and_pins() -> None:
    config = watch.load_watchlist()
    assert len(config.catalogues) == 8
    assert len(config.artifacts) == 6
    assert len(config.sefin_bases) * len(config.sefin_paths) == 12
    assert {item.id for item in config.artifacts} == {
        "production_xsd",
        "production_annex_i",
        "restricted_xsd",
        "restricted_annex_i",
        "faq_pdf",
        "contributor_api_manual",
    }
    assert next(item for item in config.artifacts if item.id == "faq_pdf").sha256 == (
        "aa45e008842f1c94e7e175f96df3f6354a23b45b6136db8ed87706d318b462f7"
    )


def test_known_403_and_identical_artifact_are_unchanged() -> None:
    config, transport = baseline()
    report = watch.evaluate(config, transport)
    assert report == {
        "status": "unchanged",
        "checked_sources": 1,
        "signals": [],
        "omitted_signals": 0,
        "post_openapi_candidate": False,
        "xmldsig_review_candidate": False,
        "material_change": False,
    }
    assert transport.calls == [CATALOGUE_URL, ARTIFACT_URL, SEFIN_URL]


def test_technical_root_card_layout_is_supported() -> None:
    config, transport = baseline()
    root = watch.Catalogue("technical_root", CATALOGUE_URL, None)
    config = replace(config, catalogues=(root,), artifacts=())
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        b'<div id="content-core"><a href="/nfse/docs">Documentation</a>'
        b'</div><div id="viewlet-below-content">',
    )
    assert watch.evaluate(config, transport)["status"] == "unchanged"


def test_relocated_artifact_with_identical_bytes_is_not_material() -> None:
    config, transport = baseline()
    relocated = ARTIFACT_URL.replace(".zip", "-moved.zip")
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, html_page(href=relocated)
    )
    transport.responses[relocated] = response(
        relocated, GOOD_BYTES, content_type="application/zip"
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "source_relocated"
    assert report["material_change"] is False
    assert watch.EXIT_CODES[str(report["status"])] == 10


def test_redirected_artifact_with_identical_bytes_is_relocation() -> None:
    config, transport = baseline()
    transport.responses[ARTIFACT_URL] = watch.Response(
        200,
        "application/zip",
        GOOD_BYTES,
        ARTIFACT_URL.replace(".zip", "-redirected.zip"),
        (ARTIFACT_URL,),
    )
    assert watch.evaluate(config, transport)["status"] == "source_relocated"


@pytest.mark.parametrize("changed", [b"new official zip", GOOD_BYTES + b"!"])
def test_changed_artifact_bytes_require_manual_review(changed: bytes) -> None:
    config, transport = baseline()
    transport.responses[ARTIFACT_URL] = response(
        ARTIFACT_URL, changed, content_type="application/zip"
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "material_change"
    assert report["material_change"] is True
    assert watch.EXIT_CODES[str(report["status"])] == 20


def test_changed_faq_version_is_material_even_if_bytes_match() -> None:
    config, transport = baseline()
    faq = replace(
        config.artifacts[0],
        id="faq_pdf",
        label_pattern=r"^Perguntas e Respostas da NFS-e - Versão",
        version="1.00",
        date="08/09/2026",
    )
    config = replace(config, artifacts=(faq,))
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        html_page(label="Perguntas e Respostas da NFS-e - Versão 1.01 - 09/09/2026"),
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "material_change"
    assert report["signals"][0]["reason"] == "faq_version_or_date"  # type: ignore[index]


def test_missing_faq_version_is_reviewable_material_change() -> None:
    config, transport = baseline()
    faq = replace(
        config.artifacts[0], id="faq_pdf", label_pattern="^FAQ", version="1.00"
    )
    config = replace(config, artifacts=(faq,))
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, html_page(label="FAQ without version")
    )
    assert watch.evaluate(config, transport)["status"] == "material_change"


@pytest.mark.parametrize(
    "label,extra",
    [
        ("unrelated document", ""),
        (
            "NFSe-ESQUEMAS_XSD-v1.01",
            f'<a href="{ARTIFACT_URL}">NFSe-ESQUEMAS_XSD duplicate</a>',
        ),
    ],
)
def test_missing_or_ambiguous_artifact_link(label: str, extra: str) -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, html_page(label=label, extra=extra)
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "review_required"
    assert ARTIFACT_URL not in transport.calls


def test_catalogue_timestamp_change_requires_review_not_material_change() -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, html_page(updated="22/09/2026 12h00")
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "review_required"
    assert report["material_change"] is False


def test_unpinned_catalogue_timestamp_is_not_assumed() -> None:
    config, transport = baseline()
    config = replace(config, catalogues=(replace(config.catalogues[0], updated=None),))
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, html_page(updated="22/09/2026 12h00")
    )
    assert watch.evaluate(config, transport)["status"] == "unchanged"


def test_new_xmlsig_keyword_link_is_candidate_not_confirmation() -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        html_page(
            extra='<a href="/nfse/signaturemethod.pdf">New SignatureMethod note</a>'
        ),
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "xmldsig_review_candidate"
    assert report["xmldsig_review_candidate"] is True
    assert "signature_profile_confirmed" not in report


def test_remote_labels_and_signal_count_are_bounded() -> None:
    config, transport = baseline()
    long_label = "SignatureMethod" + "x" * (watch.MAX_SIGNAL_TEXT * 2)
    extra = f'<a href="/nfse/signature">{long_label}</a>' * (
        watch.MAX_REPORTED_SIGNALS + 1
    )
    transport.responses[CATALOGUE_URL] = response(CATALOGUE_URL, html_page(extra=extra))
    report = watch.evaluate(config, transport)
    assert report["status"] == "xmldsig_review_candidate"
    signals = cast("list[dict[str, object]]", report["signals"])
    assert len(signals) == watch.MAX_REPORTED_SIGNALS
    assert report["omitted_signals"] == 1
    assert all(len(str(signal["label"])) <= watch.MAX_SIGNAL_TEXT for signal in signals)


def test_too_many_catalogue_links_fails_closed() -> None:
    config, transport = baseline()
    extra = '<a href="/nfse/other">Other</a>' * (watch.MAX_LINKS + 1)
    transport.responses[CATALOGUE_URL] = response(CATALOGUE_URL, html_page(extra=extra))
    assert watch.evaluate(config, transport)["status"] == "review_required"


def test_new_api_link_requests_review_not_post_confirmation() -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        html_page(extra='<a href="/nfse/openapi.json">OpenAPI documentation</a>'),
    )
    assert watch.evaluate(config, transport)["status"] == "review_required"


def test_new_official_technical_note_is_review_required() -> None:
    config, transport = baseline()
    config = replace(
        config, catalogues=(replace(config.catalogues[0], id="rtc_notes"),)
    )
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        html_page(
            extra='<a href="/nfse/nt-010.pdf">Nota Técnica SE/CGNFS-e nº 010</a>'
        ),
    )
    assert watch.evaluate(config, transport)["status"] == "review_required"


def test_baseline_403_to_official_post_openapi_is_candidate() -> None:
    config, transport = baseline()
    document = {"openapi": "3.0.0", "paths": {"/nfse": {"post": {}}}}
    transport.responses[SEFIN_URL] = response(
        SEFIN_URL, json.dumps(document).encode(), content_type="application/json"
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "post_openapi_candidate"
    assert report["post_openapi_candidate"] is True
    assert "contract_confirmed" not in report
    assert watch.EXIT_CODES[str(report["status"])] == 21


def test_multiple_signal_precedence_is_deterministic() -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL,
        html_page(extra='<a href="/nfse/signature">SignatureMethod note</a>'),
    )
    transport.responses[ARTIFACT_URL] = response(ARTIFACT_URL, b"changed artifact")
    transport.responses[SEFIN_URL] = response(
        SEFIN_URL,
        b'{"openapi":"3.0.0","paths":{"/nfse":{"post":{}}}}',
        content_type="application/json",
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "post_openapi_candidate"
    assert report["post_openapi_candidate"] is True
    assert report["xmldsig_review_candidate"] is True
    assert report["material_change"] is True
    assert watch.EXIT_CODES[str(report["status"])] == 21
    transport.responses[ARTIFACT_URL] = watch.WatchError("timeout")
    report = watch.evaluate(config, transport)
    assert report["status"] == "network_error"
    assert report["post_openapi_candidate"] is True
    assert watch.EXIT_CODES[str(report["status"])] == 30


@pytest.mark.parametrize(
    "body",
    [
        b"<html>Swagger UI</html>",
        b"not valid JSON",
        b'{"swagger":"2.0","paths":{"/nfse":{"get":{}}}}',
        b'{"swagger":"2.0","paths":{"/nfse":{"post":null}}}',
        b'{"openapi":"anything","paths":{"/nfse":{"post":{}}}}',
        b'{"swagger":"3.0","paths":{"/nfse":{"post":{}}}}',
        b"[]",
    ],
)
def test_non_openapi_or_malformed_sefin_response_is_review_required(
    body: bytes,
) -> None:
    config, transport = baseline()
    transport.responses[SEFIN_URL] = response(SEFIN_URL, body)
    assert watch.evaluate(config, transport)["status"] == "review_required"


def test_403_body_drift_is_review_required() -> None:
    config, transport = baseline()
    transport.responses[SEFIN_URL] = response(SEFIN_URL, b"different 403", status=403)
    assert watch.evaluate(config, transport)["status"] == "review_required"


@pytest.mark.parametrize(
    "final_url,redirect_chain",
    [
        ("https://sefin.nfse.gov.br/SefinNacional/moved", (SEFIN_URL,)),
        ("https://sefin.nfse.gov.br/SefinNacional/moved", ()),
        (SEFIN_URL, (SEFIN_URL,)),
    ],
)
def test_known_403_location_change_requires_review(
    final_url: str, redirect_chain: tuple[str, ...]
) -> None:
    config, transport = baseline()
    transport.responses[SEFIN_URL] = watch.Response(
        403, "text/html", DENIED_BYTES, final_url, redirect_chain
    )
    report = watch.evaluate(config, transport)
    assert report["status"] == "review_required"
    assert report["post_openapi_candidate"] is False
    assert report["material_change"] is False
    signal = report["signals"][0]  # type: ignore[index]
    assert signal["final_url"] == final_url
    assert signal["redirect_chain"] == redirect_chain


@pytest.mark.parametrize("failed", [CATALOGUE_URL, ARTIFACT_URL, SEFIN_URL])
def test_network_failure_prevents_complete_check(failed: str) -> None:
    config, transport = baseline()
    transport.responses[failed] = watch.WatchError("timeout")
    report = watch.evaluate(config, transport)
    assert report["status"] == "network_error"
    assert watch.EXIT_CODES[str(report["status"])] == 30


def test_unavailable_catalogue_and_changed_structure_are_distinct() -> None:
    config, transport = baseline()
    transport.responses[CATALOGUE_URL] = response(
        CATALOGUE_URL, b"forbidden", status=403
    )
    assert watch.evaluate(config, transport)["status"] == "network_error"
    transport.responses[CATALOGUE_URL] = response(CATALOGUE_URL, b"<html/>")
    assert watch.evaluate(config, transport)["status"] == "review_required"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.gov.br/nfse",
        "file:///etc/passwd",
        "ftp://www.gov.br/nfse",
        "data:text/plain,hello",
        "https://evilgov.br/nfse",
        "https://gov.br.example.com/nfse",
        "https://evil.example/nfse",
        "https://nfse.gov.br.evil.example/nfse",
        "https://attacker-nfse.gov.br.evil.tld/nfse",
        "https://user:pass@www.gov.br/nfse",
        "https://www.gov.br:444/nfse",
    ],
)
def test_non_official_url_is_rejected(url: str) -> None:
    with pytest.raises(watch.WatchError, match="non-official"):
        watch.HttpTransport().fetch(url)


def test_redirect_to_unexpected_host_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = watch.HttpTransport()
    called: list[str] = []

    def once(url: str) -> watch.Response:
        called.append(url)
        return watch.Response(
            302, "text/html", b"", url, location="https://evil.example/data"
        )

    monkeypatch.setattr(
        transport,
        "_request_once",
        once,
    )
    with pytest.raises(watch.WatchError, match="non-official"):
        transport.fetch(CATALOGUE_URL)
    assert called == [CATALOGUE_URL]


def test_overlong_redirect_url_is_rejected_before_follow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = watch.HttpTransport()
    called: list[str] = []

    def once(url: str) -> watch.Response:
        called.append(url)
        return watch.Response(
            302,
            "text/html",
            b"",
            url,
            location="https://www.gov.br/" + "x" * watch.MAX_URL_LENGTH,
        )

    monkeypatch.setattr(transport, "_request_once", once)
    with pytest.raises(watch.WatchError, match="length limit"):
        transport.fetch(CATALOGUE_URL)
    assert called == [CATALOGUE_URL]


def test_official_redirect_chain_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = watch.HttpTransport()
    second = "https://www.gov.br/nfse/moved"

    def once(url: str) -> watch.Response:
        if url == CATALOGUE_URL:
            return watch.Response(302, "text/html", b"", url, location=second)
        return response(url, b"ok")

    monkeypatch.setattr(transport, "_request_once", once)
    fetched = transport.fetch(CATALOGUE_URL)
    assert fetched.final_url == second
    assert fetched.redirect_chain == (CATALOGUE_URL,)


def test_too_many_redirects_and_missing_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = watch.HttpTransport()
    monkeypatch.setattr(
        transport,
        "_request_once",
        lambda url: watch.Response(302, "text/html", b"", url, location="/again"),
    )
    with pytest.raises(watch.WatchError, match="too many"):
        transport.fetch(CATALOGUE_URL)
    monkeypatch.setattr(
        transport,
        "_request_once",
        lambda url: watch.Response(302, "text/html", b"", url),
    )
    with pytest.raises(watch.WatchError, match="missing Location"):
        transport.fetch(CATALOGUE_URL)


class FakeOpenResponse:
    def __init__(
        self, body: bytes, *, length: str | None = None, status: int = 200
    ) -> None:
        self.body = body
        self.code = status
        self.headers = {"Content-Type": "text/html", "Content-Length": length}

    def __enter__(self) -> FakeOpenResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.body[:size]


class FakeOpener:
    def __init__(self, result: FakeOpenResponse | Exception) -> None:
        self.result = result
        self.request: Request | None = None
        self.timeout: int | None = None

    def open(self, request: Request, timeout: int) -> FakeOpenResponse:
        self.request = request
        self.timeout = timeout
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_transport_get_has_no_credentials_or_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = FakeOpener(FakeOpenResponse(b"ok"))
    monkeypatch.setattr(watch, "build_opener", lambda *_args: opener)
    fetched = watch.HttpTransport().fetch(CATALOGUE_URL)
    assert fetched.body == b"ok"
    assert opener.timeout == watch.TIMEOUT_SECONDS
    assert opener.request is not None
    assert opener.request.get_method() == "GET"
    assert opener.request.data is None
    assert not any(
        key.lower() in {"cookie", "authorization"} for key in opener.request.headers
    )


@pytest.mark.parametrize(
    "result",
    [
        FakeOpenResponse(b"x", length=str(watch.MAX_BYTES + 1)),
        FakeOpenResponse(b"x" * (watch.MAX_BYTES + 1)),
    ],
)
def test_transport_rejects_oversize(
    monkeypatch: pytest.MonkeyPatch, result: FakeOpenResponse
) -> None:
    monkeypatch.setattr(watch, "build_opener", lambda *_args: FakeOpener(result))
    with pytest.raises(watch.WatchError, match="byte limit"):
        watch.HttpTransport().fetch(CATALOGUE_URL)


def test_transport_timeout_is_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        watch, "build_opener", lambda *_args: FakeOpener(URLError("timed out"))
    )
    with pytest.raises(watch.WatchError, match="network request failed"):
        watch.HttpTransport().fetch(CATALOGUE_URL)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": 2, "catalogues": [], "artifacts": [], "sefin": {}},
        {"schema_version": "one"},
        {"schema_version": 1, "catalogues": "invalid"},
    ],
)
def test_invalid_watchlist_is_rejected(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(watch.WatchError):
        watch.load_watchlist(path)


def test_main_emits_one_json_and_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, transport = baseline()
    monkeypatch.setattr(watch, "load_watchlist", lambda: config)
    monkeypatch.setattr(watch, "HttpTransport", lambda: transport)
    assert watch.main() == 0
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    assert json.loads(output)["status"] == "unchanged"


def test_main_reports_setup_failure_as_one_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> watch.Watchlist:
        raise watch.WatchError("sensitive setup details")

    monkeypatch.setattr(watch, "load_watchlist", fail)
    assert watch.main() == 30
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    assert "sensitive setup details" not in output
    assert json.loads(output)["status"] == "network_error"
