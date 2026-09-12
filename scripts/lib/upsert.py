from __future__ import annotations

from dataclasses import asdict, dataclass

from scripts.lib.detectors import row_is_ru

DELETE_FLAGS = {"1", "true", "yes", "delete", "deprecated"}


@dataclass
class UpsertCounts:
    inserted: int = 0
    updated: int = 0
    deprecated: int = 0
    skipped_gold: int = 0
    skipped_unmapped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    def add(self, other: UpsertCounts) -> None:
        self.inserted += other.inserted
        self.updated += other.updated
        self.deprecated += other.deprecated
        self.skipped_gold += other.skipped_gold
        self.skipped_unmapped += other.skipped_unmapped

    def journal_fields(self) -> dict[str, int]:
        return {
            "records_upserted": self.inserted + self.updated,
            "records_deprecated": self.deprecated,
        }


def _is_delete(row: dict[str, str]) -> bool:
    if (row.get("status") or "").strip() == "deprecated":
        return True
    flag = (row.get("_delete") or "").strip().lower()
    return flag in DELETE_FLAGS


def upsert_rows(
    existing: list[dict[str, str]],
    incoming: list[dict[str, str]],
    *,
    header: list[str],
    gold_field: str | None = None,
    gold_value: str = "gold",
) -> tuple[list[dict[str, str]], UpsertCounts]:
    out = [dict(row) for row in existing]
    index = {row.get("id", ""): i for i, row in enumerate(out) if row.get("id")}
    counts = UpsertCounts()
    for inc in incoming:
        rid = (inc.get("id") or "").strip()
        if not rid:
            continue
        delete = _is_delete(inc)
        if rid in index:
            current = out[index[rid]]
            if gold_field and current.get(gold_field) == gold_value:
                counts.skipped_gold += 1
                continue
            if delete:
                current["status"] = "deprecated"
                if inc.get("replaced_by"):
                    current["replaced_by"] = inc["replaced_by"]
                elif "replaced_by" not in current:
                    current["replaced_by"] = ""
                counts.deprecated += 1
                continue
            for key in header:
                if key == "id":
                    continue
                if key in inc:
                    current[key] = inc.get(key) or ""
            counts.updated += 1
            continue
        if delete:
            continue
        new_row = {key: inc.get(key) or "" for key in header}
        new_row["id"] = rid
        out.append(new_row)
        index[rid] = len(out) - 1
        counts.inserted += 1
    return out, counts


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _parse_geonames_mod(line: str) -> dict[str, str] | None:
    parts = line.split("\t")
    if len(parts) < 9:
        return None
    if parts[8].strip().upper() != "RU":
        return None
    geoname_id = _digits(parts[0])
    if not geoname_id:
        return None
    return {
        "geonames": geoname_id,
        "lat": parts[4].strip(),
        "lon": parts[5].strip(),
        "source_rev": parts[18].strip() if len(parts) > 18 else "",
        "name": parts[1].strip(),
    }


def _parse_geonames_delete(line: str) -> str | None:
    parts = line.split("\t")
    if not parts:
        return None
    geoname_id = _digits(parts[0])
    return geoname_id or None


def apply_geonames(
    existing: list[dict[str, str]],
    mods_body: str,
    deletes_body: str = "",
    *,
    today: str,
) -> tuple[list[dict[str, str]], UpsertCounts]:
    out = [dict(row) for row in existing]
    by_gn: dict[str, list[int]] = {}
    for i, row in enumerate(out):
        key = _digits(row.get("geonames") or "")
        if key:
            by_gn.setdefault(key, []).append(i)
    counts = UpsertCounts()

    for raw in mods_body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not row_is_ru(line):
            continue
        parsed = _parse_geonames_mod(line)
        if parsed is None:
            continue
        indexes = by_gn.get(parsed["geonames"]) or []
        if not indexes:
            # DEC-GN-001: never insert id=gn:{geonameId}
            counts.skipped_unmapped += 1
            continue
        for idx in indexes:
            row = out[idx]
            old_lat = (row.get("lat") or "").strip()
            old_lon = (row.get("lon") or "").strip()
            new_lat = parsed["lat"]
            new_lon = parsed["lon"]
            if old_lat != new_lat or old_lon != new_lon:
                row["lat"] = new_lat
                row["lon"] = new_lon
                row["notes"] = "coords from geonames-ru"
            if parsed["source_rev"]:
                row["source_rev"] = parsed["source_rev"]
            row["updated_at"] = today
            counts.updated += 1

    for raw in deletes_body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        geoname_id = _parse_geonames_delete(line)
        if not geoname_id:
            continue
        indexes = by_gn.get(geoname_id) or []
        if not indexes:
            continue
        for idx in indexes:
            row = out[idx]
            if row.get("status") != "deprecated":
                row["status"] = "deprecated"
                counts.deprecated += 1

    return out, counts


DEFAULT_MAX_VENDOR_BYTES = 10485760


def too_large(content_length: str | int | None, max_bytes: int = DEFAULT_MAX_VENDOR_BYTES) -> bool:
    if content_length is None or content_length == "":
        return False
    try:
        size = int(content_length)
    except (TypeError, ValueError):
        return False
    return size > max_bytes
