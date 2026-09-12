from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote, urlparse

import requests

USER_AGENT = "toponym-check/2026.09.09 (+https://github.com/unhexx/toponym)"
TIMEOUT_SEC = 15
GITHUB_ACCEPT = "application/vnd.github+json"

_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def utcnow() -> datetime:
    return datetime.now(UTC)


def yesterday_utc(now: datetime | None = None) -> str:
    current = now or utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)
    return (current.date() - timedelta(days=1)).isoformat()


def expand_url(url: str, *, now: datetime | None = None) -> str:
    return url.replace("{yesterday}", yesterday_utc(now))


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    stream: bool = False,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> requests.Response:
    kwargs: dict[str, Any] = {
        "timeout": TIMEOUT_SEC,
        "stream": stream,
        "allow_redirects": True,
    }
    if headers:
        kwargs["headers"] = headers
    if params:
        kwargs["params"] = params
    try:
        return session.request(method, url, **kwargs)
    except (requests.Timeout, requests.ConnectionError):
        return session.request(method, url, **kwargs)


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    value = getter(name) or getter(name.lower()) or getter(name.title())
    return str(value).strip() if value else ""


def header_cursor(headers: Any) -> str:
    etag = _header(headers, "ETag")
    last_modified = _header(headers, "Last-Modified")
    length = _header(headers, "Content-Length")
    return "|".join((etag, last_modified, length))


def row_is_ru(line: str) -> bool:
    parts = line.split("\t")
    if len(parts) >= 9:
        return parts[8].strip().upper() == "RU"
    return any(part.strip().upper() == "RU" for part in parts)


def count_ru_rows(body: str) -> int:
    total = 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if row_is_ru(line):
            total += 1
    return total


def normalize_html(html: str) -> str:
    text = _SCRIPT_RE.sub(" ", html)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mediawiki_api_endpoint(page_url: str) -> tuple[str, str] | None:
    parsed = urlparse(page_url)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "wikipedia.org" and not host.endswith(".wikipedia.org"):
        return None
    path = unquote(parsed.path or "")
    if not path.startswith("/wiki/"):
        return None
    title = path[len("/wiki/") :]
    if not title:
        return None
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc}/w/api.php", title


def _mediawiki_lastrevid(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    query = payload.get("query") or {}
    pages = query.get("pages")
    page: Any = None
    if isinstance(pages, list) and pages:
        page = pages[0]
    elif isinstance(pages, dict) and pages:
        page = next(iter(pages.values()), None)
    if not isinstance(page, dict) or page.get("missing") or page.get("invalid"):
        return ""
    revid = page.get("lastrevid")
    if revid is None:
        revisions = page.get("revisions") or []
        if revisions and isinstance(revisions[0], dict):
            revid = revisions[0].get("revid")
    if revid is None or revid == "":
        return ""
    return str(revid)


def _fetch_mediawiki_revid(session: requests.Session, page_url: str) -> str:
    parsed = _mediawiki_api_endpoint(page_url)
    if parsed is None:
        return ""
    api, title = parsed
    try:
        response = _request(
            session,
            "GET",
            api,
            params={
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "info",
                "redirects": "1",
                "titles": title,
            },
        )
        if response.status_code >= 400:
            return ""
        return _mediawiki_lastrevid(response.json())
    except (requests.RequestException, ValueError, TypeError):
        return ""


def _ok_result(
    *,
    changed: bool,
    reason: str,
    cursor_old: str,
    cursor_new: str | None = None,
) -> dict[str, Any]:
    return {
        "changed": changed,
        "reason": reason,
        "cursor_old": cursor_old,
        "cursor_new": cursor_old if cursor_new is None else cursor_new,
        "error": False,
    }


def _err_result(*, reason: str, cursor_old: str) -> dict[str, Any]:
    return {
        "changed": False,
        "reason": reason,
        "cursor_old": cursor_old,
        "cursor_new": cursor_old,
        "error": True,
    }


def detect_none(source: dict[str, Any], **_: Any) -> dict[str, Any]:
    cursor = source.get("cursor") or ""
    return _ok_result(changed=False, reason="kind=none", cursor_old=cursor, cursor_new=cursor)


def source_error_blocks(source: dict[str, Any]) -> bool:
    """Ошибка источника валит daily, если catalog не задал blocking: false."""
    if "blocking" not in source:
        return True
    return bool(source.get("blocking"))


def detect_http_head(
    source: dict[str, Any],
    *,
    session: requests.Session,
    **_: Any,
) -> dict[str, Any]:
    cursor_old = source.get("cursor") or ""
    urls = list(source.get("detector", {}).get("urls") or [])
    if not urls and source.get("url"):
        urls = [source["url"]]
    if not urls:
        return _err_result(reason="http_head: нет url", cursor_old=cursor_old)

    last_cursor = cursor_old
    changed = False
    reasons: list[str] = []
    for url in urls:
        try:
            response = _request(session, "HEAD", url)
            if response.status_code in {405, 501} or (
                response.status_code >= 400 and response.status_code not in {404}
            ):
                response = _request(session, "GET", url, stream=True)
                if getattr(response, "raw", None) is not None:
                    response.close()
            if response.status_code >= 400:
                reason = f"http_head HTTP {response.status_code}"
                if not source_error_blocks(source):
                    reason += "; pointer only"
                return _err_result(reason=reason, cursor_old=cursor_old)
        except requests.RequestException as exc:
            if not source_error_blocks(source):
                return _err_result(
                    reason="http_head timeout/no reliable headers; pointer only",
                    cursor_old=cursor_old,
                )
            return _err_result(reason=f"http_head: {exc}", cursor_old=cursor_old)
        token = header_cursor(response.headers)
        last_cursor = token or last_cursor
        if token and token != cursor_old:
            changed = True
            reasons.append(f"cursor {urlparse(url).path or url}")
        elif not token:
            reasons.append("нет ETag/Last-Modified/Content-Length")

    if changed:
        reason = "; ".join(reasons) or "заголовки изменились"
        return _ok_result(
            changed=True, reason=reason, cursor_old=cursor_old, cursor_new=last_cursor
        )
    return _ok_result(
        changed=False,
        reason="заголовки совпадают" if cursor_old else "нет кэширующих заголовков",
        cursor_old=cursor_old,
        cursor_new=last_cursor or cursor_old,
    )


def _fetch_dated_body(session: requests.Session, url: str) -> tuple[int, str]:
    response = _request(session, "GET", url)
    status = response.status_code
    if status == 404:
        return 404, ""
    if status >= 400:
        raise requests.HTTPError(f"HTTP {status} for {url}", response=response)
    return status, response.text or ""


def detect_http_dated(
    source: dict[str, Any],
    *,
    session: requests.Session,
    now: datetime | None = None,
    **_: Any,
) -> dict[str, Any]:
    cursor_old = source.get("cursor") or ""
    detector = source.get("detector") or {}
    urls = [expand_url(url, now=now) for url in detector.get("urls") or []]
    if not urls:
        return _err_result(reason="http_dated: нет urls", cursor_old=cursor_old)

    # `also: last_modified_header` is informational. Dump Last-Modified
    # must not flip `changed` and must not replace the mods-date cursor.
    ru_total = 0
    mods_ru = 0
    try:
        for url in urls:
            _status, body = _fetch_dated_body(session, url)
            n_ru = count_ru_rows(body)
            ru_total += n_ru
            if "modifications-" in url:
                mods_ru += n_ru
    except requests.RequestException as exc:
        return _err_result(reason=f"http_dated: {exc}", cursor_old=cursor_old)

    yesterday = yesterday_utc(now)
    if ru_total > 0:
        target = "mods" if mods_ru or ru_total == mods_ru else "mods/deletes"
        word = "row" if ru_total == 1 else "rows"
        if cursor_old == yesterday:
            return _ok_result(
                changed=False,
                reason=f"cursor already {yesterday}",
                cursor_old=cursor_old,
                cursor_new=cursor_old,
            )
        return _ok_result(
            changed=True,
            reason=f"{ru_total} RU {word} in {target}",
            cursor_old=cursor_old,
            cursor_new=yesterday,
        )
    return _ok_result(
        changed=False,
        reason="0 RU rows in mods",
        cursor_old=cursor_old,
        cursor_new=cursor_old,
    )


def detect_github_commits(
    source: dict[str, Any],
    *,
    session: requests.Session,
    **_: Any,
) -> dict[str, Any]:
    cursor_old = source.get("cursor") or ""
    detector = source.get("detector") or {}
    repo = detector.get("repo")
    if not repo:
        return _err_result(reason="github_commits: нет repo", cursor_old=cursor_old)

    since = source.get("checked_at") or ""
    if detector.get("since") and detector["since"] != "checked_at":
        since = detector["since"]
    url = f"https://api.github.com/repos/{repo}/commits"
    headers = {"Accept": GITHUB_ACCEPT, "User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {"per_page": "1"}
    if since:
        params["since"] = since
    try:
        response = _request(session, "GET", url, headers=headers, params=params)
        if response.status_code >= 400:
            return _err_result(
                reason=f"github_commits HTTP {response.status_code}",
                cursor_old=cursor_old,
            )
        payload = response.json()
    except requests.RequestException as exc:
        return _err_result(reason=f"github_commits: {exc}", cursor_old=cursor_old)
    except ValueError as exc:
        return _err_result(reason=f"github_commits JSON: {exc}", cursor_old=cursor_old)

    if not isinstance(payload, list):
        return _err_result(reason="github_commits: ответ не список", cursor_old=cursor_old)
    if not payload:
        return _ok_result(
            changed=False,
            reason=f"нет коммитов since {since or '—'}",
            cursor_old=cursor_old,
            cursor_new=cursor_old,
        )
    sha = payload[0].get("sha") or ""
    if not sha:
        return _err_result(reason="github_commits: пустой sha", cursor_old=cursor_old)
    if sha == cursor_old:
        return _ok_result(
            changed=False, reason="тот же SHA", cursor_old=cursor_old, cursor_new=sha
        )
    return _ok_result(
        changed=True,
        reason=f"новый коммит {sha[:7]}",
        cursor_old=cursor_old,
        cursor_new=sha,
    )


def detect_page_fingerprint(
    source: dict[str, Any],
    *,
    session: requests.Session,
    **_: Any,
) -> dict[str, Any]:
    raw_cursor = source.get("cursor")
    cursor_old = "" if raw_cursor is None else str(raw_cursor)
    urls = list(source.get("detector", {}).get("urls") or [])
    if not urls and source.get("url"):
        urls = [source["url"]]
    if not urls:
        return _err_result(reason="page_fingerprint: нет url", cursor_old=cursor_old)
    url = urls[0]
    revid = _fetch_mediawiki_revid(session, url)
    if revid:
        if revid == cursor_old:
            return _ok_result(
                changed=False,
                reason="тот же MediaWiki rev",
                cursor_old=cursor_old,
                cursor_new=revid,
            )
        return _ok_result(
            changed=True,
            reason=f"MediaWiki rev {revid}",
            cursor_old=cursor_old,
            cursor_new=revid,
        )
    try:
        response = _request(session, "GET", url)
        if response.status_code >= 400:
            return _err_result(
                reason=f"page_fingerprint HTTP {response.status_code}",
                cursor_old=cursor_old,
            )
        etag = _header(response.headers, "ETag")
    except requests.RequestException as exc:
        return _err_result(reason=f"page_fingerprint: {exc}", cursor_old=cursor_old)
    if etag:
        if etag == cursor_old:
            return _ok_result(
                changed=False, reason="ETag совпадает", cursor_old=cursor_old, cursor_new=etag
            )
        return _ok_result(
            changed=True, reason="ETag изменился", cursor_old=cursor_old, cursor_new=etag
        )
    return _err_result(
        reason="page_fingerprint: нет MediaWiki rev/ETag",
        cursor_old=cursor_old,
    )


_KIND_HANDLERS = {
    "http_head": detect_http_head,
    "http_dated": detect_http_dated,
    "github_commits": detect_github_commits,
    "page_fingerprint": detect_page_fingerprint,
    "none": detect_none,
}


def detect_source(
    source: dict[str, Any],
    *,
    session: requests.Session | None,
    now: datetime | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    source_id = source.get("id") or ""
    kind = (source.get("detector") or {}).get("kind")
    cursor_old = source.get("cursor") or ""

    def with_id(row: dict[str, Any]) -> dict[str, Any]:
        out = {
            "id": source_id,
            "changed": row["changed"],
            "reason": row["reason"],
            "cursor_old": row["cursor_old"],
            "cursor_new": row["cursor_new"],
            "error": row["error"],
        }
        if row["error"]:
            out["blocking"] = source_error_blocks(source)
        return out

    if not kind:
        return with_id(_err_result(reason="нет detector.kind", cursor_old=cursor_old))
    if offline and kind != "none":
        return with_id(_err_result(reason="offline: сеть недоступна", cursor_old=cursor_old))
    handler = _KIND_HANDLERS.get(kind)
    if handler is None:
        return with_id(_err_result(reason=f"неизвестный kind={kind}", cursor_old=cursor_old))
    if kind != "none" and session is None:
        return with_id(_err_result(reason="нет HTTP-сессии", cursor_old=cursor_old))
    return with_id(handler(source, session=session, now=now))


def check_catalog(
    catalog: dict[str, Any],
    *,
    source_id: str | None = None,
    session: requests.Session | None = None,
    now: datetime | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    current = now or utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    as_of = current.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources_out: list[dict[str, Any]] = []
    if source_id is not None:
        match = [row for row in catalog.get("sources", []) if row.get("id") == source_id]
        if not match:
            sources_out.append(
                {
                    "id": source_id,
                    "changed": False,
                    "reason": "неизвестный источник",
                    "cursor_old": "",
                    "cursor_new": "",
                    "error": True,
                    "blocking": True,
                }
            )
        else:
            sources_out.append(
                detect_source(match[0], session=session, now=current, offline=offline)
            )
    else:
        for row in catalog.get("sources", []):
            sources_out.append(
                detect_source(row, session=session, now=current, offline=offline)
            )

    changed_count = sum(1 for row in sources_out if row.get("changed") and not row.get("error"))
    error_count = sum(1 for row in sources_out if row.get("error"))
    return {
        "as_of": as_of,
        "sources": sources_out,
        "changed_count": changed_count,
        "error_count": error_count,
    }


def exit_code(report: dict[str, Any]) -> int:
    sources = report.get("sources") or []
    if any(row.get("error") and row.get("blocking", True) for row in sources):
        return 2
    if report.get("changed_count"):
        return 10
    return 0
