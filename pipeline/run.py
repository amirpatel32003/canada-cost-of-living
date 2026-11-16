"""Command line entry point.

    python -m pipeline.run ingest      download tables that have a new release
    python -m pipeline.run build       dbt seed + run + test
    python -m pipeline.run export      write site/data/app.json
    python -m pipeline.run all         the three steps in order
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import config
from .export import export
from .ingest import ingest_all, results_as_dicts


def dbt_build(extra: list[str] | None = None) -> None:
    env = dict(os.environ)
    env.setdefault("COL_BRONZE_DIR", str(config.BRONZE_DIR))
    env.setdefault("COL_WAREHOUSE_PATH", str(config.WAREHOUSE_PATH))
    env.setdefault("DBT_PROFILES_DIR", str(config.DBT_DIR))
    config.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "dbt.cli.main", "build", "--project-dir", str(config.DBT_DIR)] + (extra or [])
    subprocess.run(cmd, check=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["ingest", "build", "export", "all"])
    parser.add_argument("--table", help="ingest only this table (rent, food_prices or wages)")
    parser.add_argument("--force", action="store_true", help="re-download every table even if the release is unchanged")
    args = parser.parse_args(argv)

    if args.step in ("ingest", "all"):
        if args.table:
            from .ingest import ingest_table
            from .statcan import default_source

            results = [ingest_table(config.table_by_name(args.table), default_source(), force=args.force)]
        else:
            results = ingest_all(force=args.force)
        print(json.dumps(results_as_dicts(results), indent=1))
    if args.step in ("build", "all"):
        dbt_build()
    if args.step in ("export", "all"):
        print(f"wrote {export()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
