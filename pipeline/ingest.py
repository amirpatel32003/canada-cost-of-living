"""Bronze layer: land each Statistics Canada table as Parquet, only when it has a new release.

Each table carries a `releaseTime` in its metadata. The manifest remembers the release we last loaded, so a
daily run downloads nothing on days when Statistics Canada published nothing for these tables.

Bronze keeps every row and every column as text, exactly as published. Typing and filtering happen in dbt.
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .config import BRONZE_DIR, MANIFEST_PATH, TABLES, Table
from .statcan import Source, default_source


@dataclass
class IngestResult:
    table: str
    pid: int
    action: str  # "loaded" or "skipped"
    release_time: str
    rows: int


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tables": {}}


def save_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")


def members_from_metadata(meta: dict) -> list[dict]:
    """Flatten the metadata's dimensions into one row per (dimension, member)."""
    rows = []
    for dim in meta.get("dimension", []):
        for m in dim.get("member", []):
            rows.append(
                {
                    "dimension_position": int(dim["dimensionPositionId"]),
                    "dimension_name": dim["dimensionNameEn"],
                    "member_id": int(m["memberId"]),
                    "member_name": m["memberNameEn"],
                    "parent_member_id": m.get("parentMemberId"),
                    "terminated": int(m.get("terminated") or 0),
                }
            )
    return rows


def _extract_csv(blob: bytes, pid: int, dest: Path) -> None:
    """Stream the one data CSV out of the zip to disk. The wages table is several GB unzipped."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv") and "MetaData" not in n]
        if len(names) != 1:
            raise ValueError(f"expected one data CSV in the zip for {pid}, found {names}")
        with zf.open(names[0]) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out, length=1 << 20)


def ingest_table(
    table: Table,
    source: Source,
    bronze_dir: Path = BRONZE_DIR,
    manifest_path: Path = MANIFEST_PATH,
    force: bool = False,
) -> IngestResult:
    manifest = load_manifest(manifest_path)
    meta = source.metadata(table.pid)
    release = str(meta.get("releaseTime", ""))
    out = bronze_dir / f"{table.name}.parquet"
    members_out = bronze_dir / f"{table.name}_members.parquet"
    seen = manifest["tables"].get(table.name, {})

    if not force and seen.get("release_time") == release and out.exists() and members_out.exists():
        return IngestResult(table.name, table.pid, "skipped", release, int(seen.get("rows", 0)))

    bronze_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / f"{table.pid}.csv"
        _extract_csv(source.table_zip(table.pid), table.pid, csv_path)
        tmp_out = out.with_suffix(".parquet.tmp")
        con.execute(
            f"""
            copy (
                select *, '{release}' as _release_time, {table.pid} as _product_id
                from read_csv('{csv_path.as_posix()}', header = true, all_varchar = true)
            ) to '{tmp_out.as_posix()}' (format parquet, compression zstd)
            """
        )
        tmp_out.replace(out)
    rows = con.execute(f"select count(*) from read_parquet('{out.as_posix()}')").fetchone()[0]

    members = members_from_metadata(meta)
    con.execute(
        "create table m (dimension_position int, dimension_name varchar, member_id int, member_name varchar,"
        " parent_member_id int, terminated int)"
    )
    con.executemany(
        "insert into m values (?, ?, ?, ?, ?, ?)",
        [
            (r["dimension_position"], r["dimension_name"], r["member_id"], r["member_name"], r["parent_member_id"], r["terminated"])
            for r in members
        ],
    )
    con.execute(f"copy m to '{members_out.as_posix()}' (format parquet)")
    con.close()

    manifest = load_manifest(manifest_path)
    manifest["tables"][table.name] = {
        "pid": table.pid,
        "title": meta.get("cubeTitleEn", table.title),
        "release_time": release,
        "cube_end_date": str(meta.get("cubeEndDate", ""))[:10],
        "rows": rows,
        "loaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_manifest(manifest, manifest_path)
    return IngestResult(table.name, table.pid, "loaded", release, rows)


def ingest_all(source: Source | None = None, force: bool = False, bronze_dir: Path = BRONZE_DIR, **kwargs) -> list[IngestResult]:
    """Ingest every table. If Statistics Canada is unreachable for one table but we already hold its last
    load, keep that load and say so, instead of failing the whole daily run. With nothing on disk to fall back
    on, the error is raised."""
    source = source or default_source()
    results = []
    for t in TABLES:
        try:
            results.append(ingest_table(t, source, force=force, bronze_dir=bronze_dir, **kwargs))
        except Exception as exc:
            have = (bronze_dir / f"{t.name}.parquet").exists() and (bronze_dir / f"{t.name}_members.parquet").exists()
            if not have:
                raise
            manifest_path = kwargs.get("manifest_path", MANIFEST_PATH)
            seen = load_manifest(manifest_path)["tables"].get(t.name, {})
            print(f"WARNING: could not refresh {t.name} ({exc}). Keeping the copy from {seen.get('loaded_at', 'an earlier run')}.", flush=True)
            results.append(IngestResult(t.name, t.pid, "kept", str(seen.get("release_time", "")), int(seen.get("rows", 0))))
    return results


def results_as_dicts(results: list[IngestResult]) -> list[dict]:
    return [asdict(r) for r in results]
