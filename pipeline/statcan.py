"""A small client for the Statistics Canada Web Data Service (WDS).

Two sources are supported behind the same interface so the whole pipeline can run offline in tests and CI:

* HttpSource reads the live service.
* DirSource reads `<pid>-eng.zip` and `<pid>-meta.json` files from a folder (see tests/fixtures).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Protocol

from .config import CSV_BASE, WDS_BASE


class Source(Protocol):
    def metadata(self, pid: int) -> dict: ...

    def table_zip(self, pid: int) -> bytes: ...


class StatCanError(RuntimeError):
    pass


class HttpSource:
    """Live Statistics Canada. Retries with backoff because the service rate limits and has short outages."""

    def __init__(self, retries: int = 4, timeout: int = 120):
        import requests

        self._session = requests.Session()
        self._session.headers["User-Agent"] = "canada-cost-of-living (github.com/amirpatel32003)"
        self._retries = retries
        self._timeout = timeout

    def _request(self, method: str, url: str, **kwargs):
        last: Exception | None = None
        for attempt in range(self._retries):
            try:
                resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
                if resp.status_code in (409, 429) or resp.status_code >= 500:
                    raise StatCanError(f"{resp.status_code} from {url}")
                resp.raise_for_status()
                return resp
            except Exception as exc:  # network errors and retryable statuses
                last = exc
                time.sleep(2 ** attempt)
        raise StatCanError(f"gave up on {url}: {last}")

    def metadata(self, pid: int) -> dict:
        resp = self._request("POST", f"{WDS_BASE}/getCubeMetadata", json=[{"productId": pid}])
        body = resp.json()[0]
        if body.get("status") != "SUCCESS":
            raise StatCanError(f"getCubeMetadata failed for {pid}: {body}")
        return body["object"]

    def table_zip(self, pid: int) -> bytes:
        return self._request("GET", f"{CSV_BASE}/{pid}-eng.zip").content


class DirSource:
    """Offline source: a folder holding `<pid>-eng.zip` and `<pid>-meta.json`."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def metadata(self, pid: int) -> dict:
        return json.loads((self.folder / f"{pid}-meta.json").read_text(encoding="utf-8"))

    def table_zip(self, pid: int) -> bytes:
        return (self.folder / f"{pid}-eng.zip").read_bytes()


def default_source() -> Source:
    """COL_SOURCE_DIR switches the pipeline to offline files; otherwise it calls Statistics Canada."""
    folder = os.environ.get("COL_SOURCE_DIR")
    return DirSource(folder) if folder else HttpSource()
