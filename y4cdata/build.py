"""Builds the site: every map frame of the chosen runs as PNG, plus manifest.json and Cloudflare's _headers."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np

from y4cdata import grib
from y4cdata.encode import SCALES, png_gray, png_wind
from y4cdata.fetch import USER_AGENT, Source
from y4cdata.fields import celsius, cloud_percent, rain_rate
from y4cdata.index import FIELDS, byte_range, parse_index
from y4cdata.manifest import build_manifest, file_name, frame_plan
from y4cdata.runs import Run, choose_runs

CONNECTIONS = 4
"""Simultaneous downloads: ECMWF's portal caps all users together at 500-2000."""

HEADERS = """\
/manifest.json
  Cache-Control: public, max-age=300
/frames/*
  Cache-Control: public, max-age=31536000, immutable
"""


def read_published(url: str, opener: Callable = urllib.request.urlopen) -> dict | None:
    """The live manifest, or None when there is none yet (404). Any other failure stops the run."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def build(source: Source, now: datetime, out: Path, published: dict | None,
          decode: Callable[[bytes], np.ndarray] = grib.decode) -> Literal["built", "unchanged"]:
    """Writes the site for the newest complete runs into ``out``, unless those runs are already live."""
    full, short = choose_runs(now, source.exists)
    frames = frame_plan(full, short)
    manifest = build_manifest(frames, full, short, now)
    if published is not None and published.get("runs") == manifest["runs"]:
        return "unchanged"
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=CONNECTIONS) as pool:
        for run in (full, short):
            if run is not None:
                _write_run(source, run, out, decode, pool)
    for fr in manifest["frames"]:
        for layer, path in fr.items():
            if layer != "time" and not (out / path).is_file():
                raise RuntimeError(f"the manifest names {path}, which was not written")
    (out / "manifest.json").write_text(json.dumps(manifest, allow_nan=False, separators=(",", ":")),
                                      encoding="utf-8")
    (out / "_headers").write_text(HEADERS, encoding="utf-8")
    return "built"


def _write_run(source: Source, run: Run, out: Path, decode: Callable[[bytes], np.ndarray],
               pool: ThreadPoolExecutor) -> None:
    """Every map step of ``run`` as PNGs. Only the previous step's precipitation is kept, for the rain rate."""
    prev: tuple[int, np.ndarray] | None = None
    for step in run.map_steps():
        records = parse_index(source.get(run.path(step, "index")).decode("utf-8"))
        grib_path = run.path(step, "grib2")
        messages = pool.map(lambda p: source.get(grib_path, byte_range(records, p)), FIELDS)
        f = {param: decode(m) for param, m in zip(FIELDS, messages)}
        _save(out, run, "wind", step, png_wind(f["10u"], f["10v"]))
        _save(out, run, "temperature", step, png_gray(celsius(f["2t"]), SCALES["temperature"]))
        _save(out, run, "clouds", step, png_gray(cloud_percent(f["tcc"]), SCALES["clouds"]))
        if prev is not None:
            prev_step, prev_tp = prev
            _save(out, run, "rain", step, png_gray(rain_rate(f["tp"], prev_tp, step - prev_step), SCALES["rain"]))
        prev = (step, f["tp"])


def _save(out: Path, run: Run, layer: str, step: int, png: bytes) -> None:
    path = out / file_name(run, layer, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
