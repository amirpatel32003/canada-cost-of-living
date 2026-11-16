"""Gold to JSON: write the one file the public tool reads.

Everything the page shows comes from the dbt marts. Nothing is computed here beyond reshaping rows into
arrays aligned on a shared list of quarters, which keeps the file small enough to load on a phone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .config import MANIFEST_PATH, SITE_DIR, WAREHOUSE_PATH
from .ingest import load_manifest


def _q(d) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def build_payload(con: duckdb.DuckDBPyConnection, manifest: dict) -> dict:
    quarters = [r[0] for r in con.execute(
        "select distinct quarter_start from fct_rent_quarterly order by 1").fetchall()]
    q_index = {q: i for i, q in enumerate(quarters)}
    n = len(quarters)

    unit_types = [
        {"id": r[0], "label": r[1], "kind": r[2]}
        for r in con.execute("select unit_type_id, short_label, kind from unit_types order by sort_order").fetchall()
    ]

    cities: dict[int, dict] = {}
    cols = [c[0] for c in con.execute("describe mart_city_affordability").fetchall()]
    for row in con.execute("select * from mart_city_affordability order by city").fetchall():
        rec = dict(zip(cols, row))
        d = con.execute("select lat, lon from dim_city where city_id = ?", [rec["city_id"]]).fetchone()
        cities[rec["city_id"]] = {
            "id": rec["city_id"], "city": rec["city"], "prov": rec["province_code"], "lat": d[0], "lon": d[1],
            "rent_quarter": _q(rec["rent_quarter"]),
            "median_annual_wage": rec["median_annual_wage"],
            "median_hourly_wage": rec["median_hourly_wage"],
            "rent_share": rec["rent_share_of_median_wage"],
            "income_needed_1bed": rec["income_needed_1bed"],
            "rent_change_1y": rec["rent_change_1y"],
            "rent_change_since_2019": rec["rent_change_since_2019"],
            "wage_change_since_2019": rec["wage_change_since_2019"],
            "rent": {}, "paid": {}, "caution": [],
        }
    for city_id, unit, qs, ask, paid, caution in con.execute(
        "select city_id, unit_type_id, quarter_start, asking_rent, paid_rent, asking_use_with_caution"
        " from fct_rent_quarterly order by 1, 2, 3").fetchall():
        c = cities.get(city_id)
        if c is None:
            continue
        series = c["rent"].setdefault(str(unit), [None] * n)
        series[q_index[qs]] = ask
        if paid is not None:
            c["paid"][str(unit)] = paid          # rows arrive in date order, so the last one kept is the latest
        if caution and q_index[qs] == n - 1 and unit not in c["caution"]:
            c["caution"].append(unit)

    provinces: dict[str, dict] = {}
    for code, name, food_geo, wage_geo in con.execute(
        "select province_code, province, food_geo_id, wage_geo_id from provinces order by 1").fetchall():
        prices_now = {
            str(pid): [price, year_ago]
            for pid, price, year_ago in con.execute(
                """
                with latest as (select max(month_start) m from fct_food_price_monthly where food_geo_id = ?)
                select f.product_id, f.price, y.price
                from fct_food_price_monthly f
                left join fct_food_price_monthly y
                  on y.food_geo_id = f.food_geo_id and y.product_id = f.product_id
                 and y.month_start = f.month_start - interval 12 month
                where f.food_geo_id = ? and f.month_start = (select m from latest)
                """, [food_geo, food_geo]).fetchall()
        }
        price_q: dict[str, list] = {}
        for pid, qs, price in con.execute(
            """
            select product_id, date_trunc('quarter', month_start)::date as q, round(avg(price), 2)
            from fct_food_price_monthly where food_geo_id = ? group by 1, 2 order by 1, 2
            """, [food_geo]).fetchall():
            if qs in q_index:
                price_q.setdefault(str(pid), [None] * n)[q_index[qs]] = price
        wage_q = [None] * n
        for qs, weekly in con.execute(
            """
            select date_trunc('quarter', month_start)::date as q, round(avg(median_weekly_wage_12m), 2)
            from fct_wage_monthly
            where wage_geo_id = ? and industry_id = 1 and work_type_id = 2 and median_weekly_wage_12m is not null
            group by 1 order by 1
            """, [wage_geo]).fetchall():
            if qs in q_index:
                wage_q[q_index[qs]] = weekly
        industries = {
            str(ind): {"hourly": hourly, "annual": annual}
            for ind, hourly, annual in con.execute(
                """
                select industry_id, round(median_hourly_wage_12m, 2), round(median_weekly_wage_12m * 52)
                from fct_wage_monthly
                where wage_geo_id = ? and work_type_id = 2 and median_weekly_wage_12m is not null
                qualify row_number() over (partition by industry_id order by month_start desc) = 1
                """, [wage_geo]).fetchall()
        }
        basket = con.execute(
            "select month_start, basket_per_adult, items_carried_forward from mart_basket_monthly"
            " where food_geo_id = ? order by month_start desc limit 1", [food_geo]).fetchone()
        provinces[code] = {
            "name": name,
            "basket_per_adult": basket[1] if basket else None,
            "basket_month": basket[0].strftime("%Y-%m") if basket else None,
            "prices": prices_now, "price_q": price_q, "wage_q": wage_q, "industries": industries,
        }

    products = [
        {"id": r[0], "name": r[1], "label": r[2], "category": r[3], "qty": r[4]}
        for r in con.execute(
            "select product_id, product, basket_label, basket_category, qty_per_adult_month from dim_product order by product").fetchall()
    ]
    industries = [
        {"id": r[0], "name": r[1]}
        for r in con.execute("select industry_id, industry from dim_industry order by industry_id").fetchall()
    ]
    latest = con.execute(
        "select (select max(month_start) from fct_food_price_monthly), (select max(month_start) from fct_wage_monthly)").fetchone()

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rent_quarter": _q(quarters[-1]),
            "food_month": latest[0].strftime("%Y-%m"),
            "wage_month": latest[1].strftime("%Y-%m"),
            "threshold": 0.30,
            "child_factor": 0.7,
            "sources": [
                {"name": k, "pid": v["pid"], "title": v["title"], "released": v["release_time"],
                 "data_through": v["cube_end_date"], "rows": v["rows"]}
                for k, v in sorted(manifest.get("tables", {}).items())
            ],
        },
        "quarters": [_q(q) for q in quarters],
        "unit_types": unit_types,
        "cities": sorted(cities.values(), key=lambda c: c["city"]),
        "provinces": provinces,
        "products": products,
        "industries": industries,
    }


def export(out_path: Path | None = None, warehouse: Path = WAREHOUSE_PATH, manifest_path: Path = MANIFEST_PATH) -> Path:
    out_path = out_path or SITE_DIR / "data" / "app.json"
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        payload = build_payload(con, load_manifest(manifest_path))
    finally:
        con.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    export_csvs(out_path.parent, warehouse)
    return out_path


def export_csvs(out_dir: Path, warehouse: Path = WAREHOUSE_PATH) -> list[Path]:
    """Plain CSV copies of the two marts people are most likely to reuse."""
    queries = {
        "cities.csv": "select * from mart_city_affordability order by city",
        "rent_quarterly.csv": """
            select c.city, c.province_code, u.short_label as home_type, r.quarter_start,
                   r.asking_rent, r.paid_rent, r.asking_use_with_caution
            from fct_rent_quarterly r
            join dim_city c using (city_id)
            join unit_types u using (unit_type_id)
            order by c.city, u.sort_order, r.quarter_start
        """,
    }
    con = duckdb.connect(str(warehouse), read_only=True)
    written = []
    try:
        for name, sql in queries.items():
            path = out_dir / name
            con.execute(f"copy ({sql}) to '{path.as_posix()}' (header, delimiter ',')")
            written.append(path)
    finally:
        con.close()
    return written
