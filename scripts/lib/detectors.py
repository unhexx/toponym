from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

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


def last_modified_changed(cursor: str | None, last_modified: str | None) -> bool:
    if not last_modified:
        return False
    token = (cursor or "").strip()
    if not token:
        return True
    if token == last_modified.strip():
        return False
    try:
        parsed = parsedate_to_datetime(last_modified)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        lm_date = parsed.astimezone(UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return True
    return token != lm_date


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
                return _err_result(
                    reason=f"http_head HTTP {response.status_code}",
                    cursor_old=cursor_old,
                )
        except requests.RequestException as exc:
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

    ru_total = 0
    mods_ru = 0
    bodies_empty = True
    try:
        for url in urls:
            _status, body = _fetch_dated_body(session, url)
            if body.strip():
                bodies_empty = False
            n_ru = count_ru_rows(body)
            ru_total += n_ru
            if "modifications-" in url:
                mods_ru += n_ru
    except requests.RequestException as exc:
        return _err_result(reason=f"http_dated: {exc}", cursor_old=cursor_old)

    dump_changed = False
    dump_lm = ""
    if detector.get("also") == "last_modified_header" and source.get("url"):
        try:
            head = _request(session, "HEAD", source["url"])
            if head.status_code in {405, 501}:
                head = _request(session, "GET", source["url"], stream=True)
                if getattr(head, "raw", None) is not None:
                    head.close()
            if head.status_code < 400:
                dump_lm = _header(head.headers, "Last-Modified")
                dump_changed = last_modified_changed(cursor_old, dump_lm)
        except requests.RequestException:
            dump_lm = ""
            dump_changed = False

    cursor_new = dump_lm or cursor_old
    if ru_total > 0:
        target = "mods" if mods_ru or ru_total == mods_ru else "mods/deletes"
        word = "row" if ru_total == 1 else "rows"
        return _ok_result(
            changed=True,
            reason=f"{ru_total} RU {word} in {target}",
            cursor_old=cursor_old,
            cursor_new=cursor_new,
        )
    if dump_changed:
        return _ok_result(
            changed=True,
            reason="dump Last-Modified changed",
            cursor_old=cursor_old,
            cursor_new=cursor_new,
        )
    reason = "0 RU rows in mods"
    if bodies_empty:
        reason = "0 RU rows in mods"
    return _ok_result(
        changed=False, reason=reason, cursor_old=cursor_old, cursor_new=cursor_old
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
    cursor_old = source.get("cursor") or ""
    urls = list(source.get("detector", {}).get("urls") or [])
    if not urls and source.get("url"):
        urls = [source["url"]]
    if not urls:
        return _err_result(reason="page_fingerprint: нет url", cursor_old=cursor_old)
    try:
        response = _request(session, "GET", urls[0])
        if response.status_code >= 400:
            return _err_result(
                reason=f"page_fingerprint HTTP {response.status_code}",
                cursor_old=cursor_old,
            )
        digest = fingerprint_text(normalize_html(response.text or ""))
    except requests.RequestException as exc:
        return _err_result(reason=f"page_fingerprint: {exc}", cursor_old=cursor_old)
    if digest == cursor_old:
        return _ok_result(
            changed=False, reason="отпечаток совпадает", cursor_old=cursor_old, cursor_new=digest
        )
    return _ok_result(
        changed=True,
        reason="отпечаток страницы изменился",
        cursor_old=cursor_old,
        cursor_new=digest,
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
        return {
            "id": source_id,
            "changed": row["changed"],
            "reason": row["reason"],
            "cursor_old": row["cursor_old"],
            "cursor_new": row["cursor_new"],
            "error": row["error"],
        }

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
    if report.get("error_count"):
        return 2
    if report.get("changed_count"):
        return 10
    return 0
