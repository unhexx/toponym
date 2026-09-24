from __future__ import annotations

from pathlib import Path

import pytest

from scripts.join_foiv import (
    ALLOWED_P31,
    apply_join,
    join_foiv,
    load_main_query,
    main,
    match_records,
    norm_label,
    p31_from_query,
)
from scripts.lib.csvio import PLACES_HEADER, read_csv, write_csv
from scripts.lib.harvest import SeedError, merge_bindings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "foiv_sparql.json"
SPARQL = ROOT / "data" / "raw" / "wikidata" / "foiv-ru.sparql"


def _place(**kwargs: str) -> dict[str, str]:
    row = {key: "" for key in PLACES_HEADER}
    row.update(kwargs)
    return row


def _mvd(**kwargs: str) -> dict[str, str]:
    row = _place(
        id="foiv:mvd",
        id_scheme="foiv",
        type_id="agency",
        name_ru="Министерство внутренних дел Российской Федерации",
        abbr="МВД",
        status="active",
        source_id="ukase-326",
        updated_at="2026-09-09",
        notes="keep notes",
    )
    row.update(kwargs)
    return row


def test_sparql_foiv_file_is_pointer() -> None:
    text = SPARQL.read_text(encoding="utf-8")
    assert "Q4481741" in text
    assert "Q4481675" in text
    assert "Q14944295" in text
    assert "Q4481793" in text
    assert "Q4481792" in text
    assert "Q159" in text
    assert "SELECT" in text
    assert "VALUES ?type" in text
    assert "FILTER(?type NOT IN" in text
    assert "не вендор" in text.casefold() or "do not vendor" in text.casefold()
    assert SPARQL.stat().st_size < 10_000
    query = load_main_query(SPARQL)
    assert p31_from_query(query) == ["Q4481741", "Q4481675", "Q14944295"]
    assert "Q4481793" not in p31_from_query(query)
    assert ALLOWED_P31 == frozenset(p31_from_query(query))


def test_norm_label_yo_and_quotes() -> None:
    assert norm_label(' «Зелёное» ') == "зеленое"


def test_match_records_name_abbr_skips_blocked_and_other_p31() -> None:
    rows = [
        {
            "item": "http://www.wikidata.org/entity/Q2114337",
            "type": "http://www.wikidata.org/entity/Q4481741",
            "ru": "Министерство внутренних дел Российской Федерации",
        },
        {
            "item": "http://www.wikidata.org/entity/Q863254",
            "type": "http://www.wikidata.org/entity/Q4481675",
            "ru": "Служба внешней разведки Российской Федерации",
            "short": "СВР",
        },
        {
            "item": "http://www.wikidata.org/entity/Q9",
            "type": "http://www.wikidata.org/entity/Q4481793",
            "ru": "Министерство обороны Российской Федерации",
        },
        {
            "item": "http://www.wikidata.org/entity/Q8",
            "type": "http://www.wikidata.org/entity/Q23397",
            "ru": "Министерство внутренних дел Российской Федерации",
        },
    ]
    records = merge_bindings(rows, extra_scalars=("short",), extra_qid_sets=("p31",))
    existing = [
        _mvd(),
        _place(
            id="foiv:svr",
            id_scheme="foiv",
            name_ru="Служба внешней разведки Российской Федерации",
            abbr="СВР",
        ),
        _place(
            id="foiv:mod",
            id_scheme="foiv",
            name_ru="Министерство обороны Российской Федерации",
            abbr="Минобороны",
        ),
    ]
    matched = match_records(records, existing)
    assert matched["foiv:mvd"] == "Q2114337"
    assert matched["foiv:svr"] == "Q863254"
    assert "foiv:mod" not in matched


def test_apply_join_fills_wd_keeps_id_and_notes() -> None:
    records = merge_bindings(
        [
            {
                "item": "http://www.wikidata.org/entity/Q2114337",
                "type": "http://www.wikidata.org/entity/Q4481741",
                "ru": "Министерство внутренних дел Российской Федерации",
                "en": "Ministry of Internal Affairs",
            }
        ],
        extra_qid_sets=("p31",),
    )
    existing = [_mvd(), _place(id="foiv:mid", name_ru="Министерство иностранных дел")]
    places, counts, matched = apply_join(
        records, existing=existing, today="2026-09-24"
    )
    assert matched == 1
    assert counts.inserted == 0
    assert counts.updated == 1
    by_id = {row["id"]: row for row in places}
    assert by_id["foiv:mvd"]["wd"] == "Q2114337"
    assert by_id["foiv:mvd"]["id_scheme"] == "foiv"
    assert by_id["foiv:mvd"]["notes"] == "keep notes"
    assert by_id["foiv:mvd"]["source_id"] == "ukase-326"
    assert by_id["foiv:mvd"]["name_en"] == "Ministry of Internal Affairs"
    assert by_id["foiv:mid"]["wd"] == ""
    assert len(places) == 2


def test_apply_join_zero_matches_does_not_merge() -> None:
    records = merge_bindings(
        [
            {
                "item": "http://www.wikidata.org/entity/Q1",
                "type": "http://www.wikidata.org/entity/Q4481741",
                "ru": "Чужое министерство",
            }
        ],
        extra_qid_sets=("p31",),
    )
    with pytest.raises(SeedError, match="0/69"):
        apply_join(records, existing=[_mvd()], today="2026-09-24")


def test_cli_from_json_writes_tmp(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    raw = tmp_path / "data" / "raw" / "wikidata"
    curated.mkdir(parents=True)
    raw.mkdir(parents=True)
    write_csv(
        curated / "agencies-foiv.csv",
        PLACES_HEADER,
        [
            _mvd(),
            _place(
                id="foiv:svr",
                id_scheme="foiv",
                type_id="agency",
                name_ru="Служба внешней разведки Российской Федерации",
                abbr="СВР",
                status="active",
                source_id="ukase-326",
            ),
            _place(
                id="foiv:mod",
                id_scheme="foiv",
                type_id="agency",
                name_ru="Министерство обороны Российской Федерации",
                abbr="Минобороны",
                status="active",
                source_id="ukase-326",
            ),
        ],
    )
    (raw / "foiv-ru.sparql").write_text(SPARQL.read_text(encoding="utf-8"), encoding="utf-8")
    code = main(
        [
            "--root",
            str(tmp_path),
            "--from-json",
            str(FIXTURE),
            "--today",
            "2026-09-24",
        ]
    )
    assert code == 0
    out = capsys.readouterr()
    assert "ok\t" in out.out
    assert "matched=2/69" in out.out
    assert "inserted=0" in out.out
    _header, rows = read_csv(curated / "agencies-foiv.csv")
    by_id = {row["id"]: row for row in rows}
    assert by_id["foiv:mvd"]["wd"] == "Q2114337"
    assert by_id["foiv:svr"]["wd"] == "Q863254"
    assert by_id["foiv:mod"]["wd"] == ""
    assert by_id["foiv:mvd"]["notes"] == "keep notes"
    assert len(rows) == 3
    assert len(read_csv(ROOT / "data/curated/agencies-foiv.csv")[1]) == 69


def test_join_from_json_no_network() -> None:
    places, counts, matched, _header = join_foiv(
        root=ROOT,
        today="2026-09-24",
        from_json=FIXTURE,
        from_csv=None,
        session=None,
    )
    assert counts.inserted == 0
    assert matched >= 1
    by_id = {row["id"]: row for row in places}
    assert by_id["foiv:mvd"]["id"] == "foiv:mvd"
    assert by_id["foiv:mvd"]["id_scheme"] == "foiv"
    assert by_id["foiv:mvd"]["wd"].startswith("Q")
    assert len(places) == 69


def test_cli_zero_match_returns_2(tmp_path: Path, capsys) -> None:
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    write_csv(curated / "agencies-foiv.csv", PLACES_HEADER, [_mvd(name_ru="Другое")])
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    code = main(
        ["--root", str(tmp_path), "--from-json", str(empty), "--today", "2026-09-24"]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "0/69" in err
    _header, rows = read_csv(curated / "agencies-foiv.csv")
    assert rows[0]["wd"] == ""


def test_canon_foiv_join_fills_wd_without_insert() -> None:
    _header, rows = read_csv(ROOT / "data/curated/agencies-foiv.csv")
    assert len(rows) == 69
    assert all(row["id"].startswith("foiv:") for row in rows)
    assert all(row["id_scheme"] == "foiv" for row in rows)
    assert all(row["source_id"] == "ukase-326" for row in rows)
    filled = [row for row in rows if row["wd"].startswith("Q")]
    assert 1 <= len(filled) < 69
    mvd = next(row for row in rows if row["id"] == "foiv:mvd")
    assert mvd["wd"].startswith("Q")
    assert mvd["abbr"] == "МВД"
