"""Observe official NFS-e documentation; never promote evidence or mutate state."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

WATCHLIST = (
    Path(__file__).resolve().parents[1] / "contracts/restricted/evidence-watchlist.json"
)
MAX_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_URL_LENGTH = 2048
MAX_LINKS = 512
MAX_SIGNAL_TEXT = 256
MAX_REPORTED_SIGNALS = 64
TIMEOUT_SECONDS = 10
USER_AGENT = (
    "nfse-br-official-evidence-watch/1.0 (+https://github.com/cassao29/nfse-br)"
)
EXIT_CODES = {
    "unchanged": 0,
    "source_relocated": 10,
    "material_change": 20,
    "review_required": 20,
    "post_openapi_candidate": 21,
    "xmldsig_review_candidate": 22,
    "network_error": 30,
}
_UPDATED = re.compile(
    r'<span class="documentModified">\s*<span>Atualizado em</span>'
    r'\s*<span class="value">([^<]+)</span>',
    re.DOTALL,
)
_XMLDSIG_TERMS = re.compile(
    r"xmldsig|assinatura|signaturemethod|digestmethod|"
    r"canonicalizationmethod|keyinfo|x509data|reference\s+uri|transform",
    re.IGNORECASE,
)
_POST_TERMS = re.compile(r"post\s*/nfse|openapi|swagger", re.IGNORECASE)
_NOTE_NUMBER = re.compile(r"Nota Técnica SE/CGNFS-e nº\s*(\d+)")
_FAQ_VERSION = re.compile(r"Versão\s+([\d.]+)\s+-\s+(\d\d/\d\d/\d{4})")


class WatchError(ValueError):
    """Controlled configuration, transport, or parsing failure."""


@dataclass(frozen=True, slots=True)
class Response:
    """Bounded response bytes and their retrieval provenance."""

    status: int
    content_type: str
    body: bytes
    final_url: str
    redirect_chain: tuple[str, ...] = ()
    location: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


class Transport(Protocol):
    def fetch(self, url: str) -> Response: ...


def _official_url(url: str) -> None:
    if len(url) > MAX_URL_LENGTH:
        raise WatchError("official URL exceeds length limit")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
        or host not in {"gov.br", "www.gov.br", "nfse.gov.br"}
        and not host.endswith(".nfse.gov.br")
    ):
        raise WatchError("non-official HTTPS URL")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


class HttpTransport:
    """GET-only transport with explicit host, redirect, time, and size bounds."""

    def fetch(self, url: str) -> Response:
        chain: list[str] = []
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            _official_url(current)
            response = self._request_once(current)
            if response.status not in (301, 302, 303, 307, 308):
                return Response(
                    response.status,
                    response.content_type,
                    response.body,
                    current,
                    tuple(chain),
                )
            if response.location is None:
                raise WatchError("redirect missing Location")
            next_url = urljoin(current, response.location)
            _official_url(next_url)
            chain.append(current)
            current = next_url
        raise WatchError("too many redirects")

    def _request_once(self, url: str) -> Response:
        request = Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            method="GET",
        )
        # No cookies, credentials, client certificates, or environment proxies.
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        try:
            response = opener.open(request, timeout=TIMEOUT_SECONDS)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError) as error:
            raise WatchError("network request failed") from error
        with response:
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdecimal():
                if int(content_length) > MAX_BYTES:
                    raise WatchError("response exceeds byte limit")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise WatchError("response exceeds byte limit")
            return Response(
                status=response.code,
                content_type=response.headers.get("Content-Type", "")
                .split(";", 1)[0]
                .lower(),
                body=body,
                final_url=url,
                location=response.headers.get("Location"),
            )


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.too_many_links = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            label = " ".join("".join(self._text).split())
            if len(self.links) >= MAX_LINKS:
                self.too_many_links = True
            else:
                self.links.append((label, self._href))
            self._href = None


@dataclass(frozen=True, slots=True)
class Catalogue:
    id: str
    url: str
    updated: str | None


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    catalogue: str
    label_pattern: str
    url: str
    size: int
    sha256: str
    version: str | None = None
    date: str | None = None


@dataclass(frozen=True, slots=True)
class Watchlist:
    catalogues: tuple[Catalogue, ...]
    artifacts: tuple[Artifact, ...]
    sefin_bases: tuple[str, ...]
    sefin_paths: tuple[str, ...]
    sefin_status: int
    sefin_content_type: str
    sefin_size: int
    sefin_sha256: str


def _map(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise WatchError("invalid watchlist object")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise WatchError("invalid watchlist string")
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WatchError("invalid watchlist integer")
    return value


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise WatchError("invalid watchlist sequence")
    return value


def load_watchlist(path: Path = WATCHLIST) -> Watchlist:
    """Load frozen monitoring pins without modifying their source file."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    data = _map(raw)
    if _int(data.get("schema_version")) != 1:
        raise WatchError("unsupported watchlist schema")
    catalogues: list[Catalogue] = []
    for item in _sequence(data.get("catalogues")):
        entry = _map(item)
        updated = entry.get("updated")
        catalogues.append(
            Catalogue(
                _str(entry.get("id")),
                _str(entry.get("url")),
                None if updated is None else _str(updated),
            )
        )
    artifacts: list[Artifact] = []
    for item in _sequence(data.get("artifacts")):
        entry = _map(item)
        version = entry.get("version")
        date = entry.get("date")
        artifacts.append(
            Artifact(
                _str(entry.get("id")),
                _str(entry.get("catalogue")),
                _str(entry.get("label_pattern")),
                _str(entry.get("url")),
                _int(entry.get("size")),
                _str(entry.get("sha256")),
                None if version is None else _str(version),
                None if date is None else _str(date),
            )
        )
    sefin = _map(data.get("sefin"))
    baseline = _map(sefin.get("baseline"))
    return Watchlist(
        tuple(catalogues),
        tuple(artifacts),
        tuple(_str(item) for item in _sequence(sefin.get("bases"))),
        tuple(_str(item) for item in _sequence(sefin.get("paths"))),
        _int(baseline.get("status")),
        _str(baseline.get("content_type")),
        _int(baseline.get("size")),
        _str(baseline.get("sha256")),
    )


def _catalogue_content(body: bytes) -> tuple[str | None, list[tuple[str, str]], str]:
    html = body.decode("utf-8", errors="replace")
    updated = _UPDATED.search(html)
    start = html.find('<div id="content-core">')
    end = html.find('<div id="viewlet-below-content-body">', start)
    if end < 0:
        end = html.find('<div id="viewlet-below-content">', start)
    if start < 0 or end < 0:
        raise WatchError("official catalogue content not found")
    core = html[start:end]
    parser = _AnchorParser()
    parser.feed(core)
    if parser.too_many_links:
        raise WatchError("official catalogue exceeds link limit")
    return (updated.group(1) if updated else None), parser.links, core


def _signal(kind: str, source: str, **details: object) -> dict[str, object]:
    bounded = {
        key: value[:MAX_SIGNAL_TEXT] if isinstance(value, str) else value
        for key, value in details.items()
    }
    return {"kind": kind, "source": source[:MAX_SIGNAL_TEXT], **bounded}


def _openapi_candidate(body: bytes) -> bool:
    try:
        document: object = json.loads(body)
    except (UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(document, dict):
        return False
    swagger = document.get("swagger")
    openapi = document.get("openapi")
    paths = document.get("paths")
    valid_marker = swagger == "2.0" or (
        isinstance(openapi, str)
        and re.fullmatch(r"3\.\d+(?:\.\d+)?", openapi) is not None
    )
    if not valid_marker or not isinstance(paths, dict):
        return False
    operation = paths.get("/nfse")
    return isinstance(operation, dict) and isinstance(operation.get("post"), dict)


def _inspect_artifact(
    artifact: Artifact,
    links: list[tuple[str, str]],
    catalogue_url: str,
    transport: Transport,
) -> list[dict[str, object]]:
    matches = [
        (label, urljoin(catalogue_url, href))
        for label, href in links
        if re.search(artifact.label_pattern, label, re.IGNORECASE)
    ]
    if len(matches) != 1:
        return [
            _signal("review_required", artifact.id, reason="missing_or_ambiguous_link")
        ]
    label, url = matches[0]
    try:
        response = transport.fetch(url)
    except WatchError:
        return [_signal("network_error", artifact.id, reason="artifact_fetch_failed")]
    if response.status != 200:
        return [
            _signal(
                "network_error",
                artifact.id,
                reason="artifact_not_available",
                http=response.status,
            )
        ]
    size = len(response.body)
    digest = response.sha256
    details: dict[str, object] = {
        "url": url,
        "final_url": response.final_url,
        "redirect_chain": response.redirect_chain,
        "content_type": response.content_type,
        "size": size,
        "sha256": digest,
    }
    if artifact.id == "faq_pdf":
        version = _FAQ_VERSION.search(label)
        if version is None or (version.group(1), version.group(2)) != (
            artifact.version,
            artifact.date,
        ):
            return [
                _signal(
                    "material_change",
                    artifact.id,
                    reason="faq_version_or_date",
                    **details,
                )
            ]
    if size != artifact.size or digest != artifact.sha256:
        return [
            _signal("material_change", artifact.id, reason="artifact_bytes", **details)
        ]
    if url != artifact.url or response.final_url != artifact.url:
        return [_signal("source_relocated", artifact.id, **details)]
    return []


def _inspect_new_links(
    catalogue: Catalogue, links: list[tuple[str, str]]
) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    for label, href in links:
        if catalogue.id == "rtc_notes":
            note = _NOTE_NUMBER.search(label)
            if note and int(note.group(1)) > 9:
                signals.append(
                    _signal(
                        "review_required", catalogue.id, reason="new_note", label=label
                    )
                )
        if _XMLDSIG_TERMS.search(label) or _XMLDSIG_TERMS.search(href):
            signals.append(
                _signal(
                    "xmldsig_review_candidate",
                    catalogue.id,
                    label=label,
                    url=urljoin(catalogue.url, href),
                )
            )
        elif _POST_TERMS.search(label) or _POST_TERMS.search(href):
            signals.append(
                _signal(
                    "review_required",
                    catalogue.id,
                    reason="new_api_link",
                    label=label,
                    url=urljoin(catalogue.url, href),
                )
            )
    return signals


def _inspect_sefin(config: Watchlist, transport: Transport) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    for base in config.sefin_bases:
        for path in config.sefin_paths:
            url = f"{base}/{path}"
            try:
                response = transport.fetch(url)
            except WatchError:
                signals.append(
                    _signal("network_error", url, reason="sefin_probe_failed")
                )
                continue
            if (
                response.status == config.sefin_status
                and response.content_type == config.sefin_content_type
                and len(response.body) == config.sefin_size
                and response.sha256 == config.sefin_sha256
                and response.final_url == url
                and response.redirect_chain == ()
            ):
                continue
            details: dict[str, object] = {
                "http": response.status,
                "content_type": response.content_type,
                "size": len(response.body),
                "sha256": response.sha256,
                "final_url": response.final_url,
                "redirect_chain": response.redirect_chain,
            }
            if response.status == 200 and _openapi_candidate(response.body):
                signals.append(_signal("post_openapi_candidate", url, **details))
            else:
                signals.append(
                    _signal(
                        "review_required",
                        url,
                        reason="sefin_baseline_changed",
                        **details,
                    )
                )
    return signals


def evaluate(config: Watchlist, transport: Transport) -> dict[str, object]:
    """Compare observed bytes with frozen pins; report candidates only."""
    signals: list[dict[str, object]] = []
    checked = 0
    for catalogue in config.catalogues:
        try:
            response = transport.fetch(catalogue.url)
        except WatchError:
            signals.append(
                _signal("network_error", catalogue.id, reason="catalogue_fetch_failed")
            )
            continue
        if response.status != 200 or response.content_type != "text/html":
            signals.append(
                _signal(
                    "network_error",
                    catalogue.id,
                    reason="catalogue_not_available",
                    http=response.status,
                )
            )
            continue
        try:
            updated, links, _ = _catalogue_content(response.body)
        except WatchError:
            signals.append(
                _signal(
                    "review_required",
                    catalogue.id,
                    reason="catalogue_structure_changed",
                )
            )
            continue
        checked += 1
        if catalogue.updated is not None and updated != catalogue.updated:
            signals.append(
                _signal(
                    "review_required",
                    catalogue.id,
                    reason="catalogue_updated",
                    previous=catalogue.updated,
                    observed=updated,
                )
            )
        signals.extend(_inspect_new_links(catalogue, links))
        for artifact in config.artifacts:
            if artifact.catalogue == catalogue.id:
                signals.extend(
                    _inspect_artifact(artifact, links, catalogue.url, transport)
                )
    signals.extend(_inspect_sefin(config, transport))
    kinds = {signal["kind"] for signal in signals}
    if "network_error" in kinds:
        status = "network_error"
    elif "post_openapi_candidate" in kinds:
        status = "post_openapi_candidate"
    elif "xmldsig_review_candidate" in kinds:
        status = "xmldsig_review_candidate"
    elif "material_change" in kinds:
        status = "material_change"
    elif "review_required" in kinds:
        status = "review_required"
    elif "source_relocated" in kinds:
        status = "source_relocated"
    else:
        status = "unchanged"
    return {
        "status": status,
        "checked_sources": checked,
        "signals": signals[:MAX_REPORTED_SIGNALS],
        "omitted_signals": max(0, len(signals) - MAX_REPORTED_SIGNALS),
        "post_openapi_candidate": "post_openapi_candidate" in kinds,
        "xmldsig_review_candidate": "xmldsig_review_candidate" in kinds,
        "material_change": "material_change" in kinds,
    }


def main() -> int:
    """Print one compact JSON report; never write to the repository."""
    try:
        report = evaluate(load_watchlist(), HttpTransport())
    except Exception:
        report = {
            "status": "network_error",
            "checked_sources": 0,
            "signals": [
                {"kind": "network_error", "source": "watcher", "reason": "setup_failed"}
            ],
            "omitted_signals": 0,
            "post_openapi_candidate": False,
            "xmldsig_review_candidate": False,
            "material_change": False,
        }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return EXIT_CODES[str(report["status"])]


if __name__ == "__main__":
    sys.exit(main())
