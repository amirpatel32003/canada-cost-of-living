"""Bronze ingest: format handling, incremental skip, and reload on a new release."""
import json

import duckdb
import pytest

from pipeline.config import table_by_name
from pipeline.ingest import ingest_table, load_manifest, members_from_metadata
from pipeline.statcan import DirSource

from conftest import FIXTURES


@pytest.fixture()
def dirs(tmp_path):
    return tmp_path / "bronze", tmp_path / "manifest.json"


def test_first_run_loads_every_row_as_text(dirs):
    bronze, manifest = dirs
    res = ingest_table(table_by_name("rent"), DirSource(FIXTURES), bronze, manifest)
    assert res.action == "loaded" and res.rows > 5000
    con = duckdb.connect()
    types = {r[0]: r[1] for r in con.execute(f"describe select * from read_parquet('{bronze / 'rent.parquet'}')").fetchall()}
    assert types["VALUE"] == "VARCHAR" and types["REF_DATE"] == "VARCHAR"
    assert {"COORDINATE", "STATUS", "_release_time"} <= set(types)


def test_second_run_skips_when_release_is_unchanged(dirs):
    bronze, manifest = dirs
    src = DirSource(FIXTURES)
    first = ingest_table(table_by_name("food_prices"), src, bronze, manifest)
    stamp = (bronze / "food_prices.parquet").stat().st_mtime_ns
    second = ingest_table(table_by_name("food_prices"), src, bronze, manifest)
    assert (first.action, second.action) == ("loaded", "skipped")
    assert second.rows == first.rows
    assert (bronze / "food_prices.parquet").stat().st_mtime_ns == stamp


def test_new_release_triggers_a_reload(dirs, tmp_path):
    bronze, manifest = dirs
    ingest_table(table_by_name("rent"), DirSource(FIXTURES), bronze, manifest)
    newer = tmp_path / "newer"
    newer.mkdir()
    for f in FIXTURES.glob("46100092*"):
        (newer / f.name).write_bytes(f.read_bytes())
    meta = json.loads((newer / "46100092-meta.json").read_text(encoding="utf-8"))
    meta["releaseTime"] = "2026-12-09T08:30"
    (newer / "46100092-meta.json").write_text(json.dumps(meta), encoding="utf-8")
    res = ingest_table(table_by_name("rent"), DirSource(newer), bronze, manifest)
    assert res.action == "loaded"
    assert load_manifest(manifest)["tables"]["rent"]["release_time"] == "2026-12-09T08:30"


def test_force_reloads_even_when_unchanged(dirs):
    bronze, manifest = dirs
    src = DirSource(FIXTURES)
    ingest_table(table_by_name("rent"), src, bronze, manifest)
    assert ingest_table(table_by_name("rent"), src, bronze, manifest, force=True).action == "loaded"


def test_members_are_flattened_from_metadata():
    meta = json.loads((FIXTURES / "46100092-meta.json").read_text(encoding="utf-8"))
    rows = members_from_metadata(meta)
    toronto = [r for r in rows if r["dimension_position"] == 1 and r["member_id"] == 27][0]
    assert toronto["member_name"].startswith("Toronto")
    assert {r["dimension_position"] for r in rows} == {1, 2, 3}


def test_zip_with_two_data_files_is_rejected(dirs, tmp_path):
    import zipfile

    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "46100092-meta.json").write_bytes((FIXTURES / "46100092-meta.json").read_bytes())
    with zipfile.ZipFile(bad / "46100092-eng.zip", "w") as zf:
        zf.writestr("a.csv", "x\n1\n")
        zf.writestr("b.csv", "x\n1\n")
    with pytest.raises(ValueError):
        ingest_table(table_by_name("rent"), DirSource(bad), *dirs)
