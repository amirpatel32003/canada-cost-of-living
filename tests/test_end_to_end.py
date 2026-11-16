"""Run ingest, dbt build (models plus every data test) and export on the fixtures, then check the numbers."""
import json
import os
import subprocess
import sys

import duckdb
import pytest

from conftest import FIXTURES, ROOT


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    env = dict(os.environ, COL_SOURCE_DIR=str(FIXTURES), COL_DATA_DIR=str(data), PYTHONPATH=str(ROOT))
    out = data / "app.json"
    code = (
        "from pipeline.ingest import ingest_all; from pipeline.run import dbt_build; from pipeline.export import export;"
        f"from pathlib import Path; ingest_all(); dbt_build(['--target-path', r'{data / 'target'}']); export(Path(r'{out}'))"
    )
    subprocess.run([sys.executable, "-c", code], check=True, env=env, cwd=ROOT)
    return data, json.loads(out.read_text(encoding="utf-8"))


def test_every_city_is_exported(built):
    _, app = built
    assert len(app["cities"]) == 42
    assert len({c["id"] for c in app["cities"]}) == 42


def test_unpublished_values_become_nulls_not_zeros(built):
    data, app = built
    con = duckdb.connect(str(data / "warehouse.duckdb"), read_only=True)
    assert con.execute("select count(*) from stg_rent where status in ('..', 'F') and rent is not null").fetchone()[0] == 0
    assert con.execute("select count(*) from stg_rent where rent = 0").fetchone()[0] == 0
    saguenay = [c for c in app["cities"] if c["city"] == "Saguenay"][0]
    assert "5" not in saguenay["rent"]            # room rent is suppressed there, so no series is published


def test_wages_ignore_gender_and_age_splits(built):
    data, _ = built
    con = duckdb.connect(str(data / "warehouse.duckdb"), read_only=True)
    n = con.execute(
        "select count(*) from fct_wage_monthly where wage_geo_id = 7 and industry_id = 1 and work_type_id = 2"
        " and month_start = date '2026-10-01'").fetchone()[0]
    assert n == 1


def test_basket_matches_a_hand_calculation(built):
    data, app = built
    con = duckdb.connect(str(data / "warehouse.duckdb"), read_only=True)
    qty = dict(con.execute("select product_id, qty_per_adult_month from basket_items").fetchall())
    prices = app["provinces"]["ON"]["prices"]
    by_hand = round(sum(q * prices[str(pid)][0] for pid, q in qty.items()), 2)
    assert app["provinces"]["ON"]["basket_per_adult"] == pytest.approx(by_hand, abs=0.01)


def test_missing_price_is_carried_forward_and_flagged(built):
    data, _ = built
    con = duckdb.connect(str(data / "warehouse.duckdb"), read_only=True)
    row = con.execute(
        "select price, is_carried_forward from fct_food_price_monthly"
        " where food_geo_id = 2 and product_id = 78 and month_start = date '2026-09-01'").fetchone()
    assert row is not None and row[0] is not None and row[1] is True


def test_rent_share_uses_the_documented_formula(built):
    _, app = built
    t = [c for c in app["cities"] if c["city"] == "Toronto"][0]
    rent = t["rent"]["2"][-1]
    assert t["rent_share"] == pytest.approx(rent / (t["median_annual_wage"] / 12), abs=0.001)
    assert t["income_needed_1bed"] == pytest.approx(rent * 12 / 0.30, abs=1)


def test_series_are_aligned_to_the_quarter_list(built):
    _, app = built
    n = len(app["quarters"])
    assert all(len(s) == n for c in app["cities"] for s in c["rent"].values())
    assert all(len(p["wage_q"]) == n for p in app["provinces"].values())
