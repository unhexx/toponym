from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

PLACES_HEADER = [
    "id",
    "id_scheme",
    "type_id",
    "name_ru",
    "name_yo",
    "name_en",
    "abbr",
    "parent_id",
    "admin1",
    "lat",
    "lon",
    "wd",
    "geonames",
    "fias",
    "oktmo",
    "iso",
    "status",
    "replaced_by",
    "source_id",
    "source_rev",
    "updated_at",
    "notes",
]


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def read_csv(path: Path | str) -> tuple[list[str], list[dict[str, str]]]:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=",")
        header = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = []
        for raw in reader:
            rows.append({key: _cell(raw.get(key)) for key in header})
    return header, rows


def dump_csv_bytes(header: list[str], rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=header,
        delimiter=",",
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _cell(row.get(key)) for key in header})
    return buf.getvalue().encode("utf-8")


def write_csv(path: Path | str, header: list[str], rows: list[dict[str, str]]) -> bool:
    path = Path(path)
    payload = dump_csv_bytes(header, rows)
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return True
