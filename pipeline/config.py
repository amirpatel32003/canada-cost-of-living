"""Paths and the list of Statistics Canada tables the pipeline loads."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("COL_PROJECT_DIR", Path(__file__).resolve().parents[1]))
DATA_DIR = Path(os.environ.get("COL_DATA_DIR", ROOT / "data"))
BRONZE_DIR = DATA_DIR / "bronze"
MANIFEST_PATH = DATA_DIR / "manifest.json"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"
DBT_DIR = ROOT / "dbt"
SITE_DIR = ROOT / "site"

WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"
CSV_BASE = "https://www150.statcan.gc.ca/n1/tbl/csv"


@dataclass(frozen=True)
class Table:
    """One Statistics Canada table (a "cube") and the short name it gets in bronze."""

    pid: int
    name: str
    title: str


TABLES: tuple[Table, ...] = (
    Table(46100092, "rent", "Asking rent and paid rent prices, by rental unit type and number of bedrooms"),
    Table(18100245, "food_prices", "Monthly average retail prices for selected products"),
    Table(14100063, "wages", "Employee wages by industry, monthly, unadjusted for seasonality"),
)


def table_by_name(name: str) -> Table:
    for t in TABLES:
        if t.name == name:
            return t
    raise KeyError(f"unknown table {name!r}; expected one of {[t.name for t in TABLES]}")
