"""Builds the site: every map frame of the chosen runs as PNG, the full run's days 11–15 tiles, manifest.json and
Cloudflare's _headers."""

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
from y4cdata.extended import (
    BASE_STEP,
    EXTENDED_FIELDS,
    EXTENDED_STEPS,
    encode_step,
    tile_path,
    tile_png,
    tile_shape,
)
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
/extended/*
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
    indexes: dict[str, list[dict]] = {}  # steps 216..240 serve the map and days 11-15: one fetch each
    with ThreadPoolExecutor(max_workers=CONNECTIONS) as pool:
        for run in (full, short):
            if run is not None:
                _write_run(source, run, out, decode, pool, indexes)
        write_extended(source, full, out, decode, pool, indexes)
    for fr in manifest["frames"]:
        for layer, path in fr.items():
            if layer != "time" and not (out / path).is_file():
                raise RuntimeError(f"the manifest names {path}, which was not written")
    (out / "manifest.json").write_text(json.dumps(manifest, allow_nan=False, separators=(",", ":")),
                                      encoding="utf-8")
    (out / "_headers").write_text(HEADERS, encoding="utf-8")
    return "built"


def _fields(source: Source, run: Run, step: int, params: tuple[str, ...], decode: Callable[[bytes], np.ndarray],
            pool: ThreadPoolExecutor, indexes: dict[str, list[dict]]) -> dict[str, np.ndarray]:
    """The step's fields, each fetched by byte range; the step's index is read once per build."""
    index_path = run.path(step, "index")
    if index_path not in indexes:
        indexes[index_path] = parse_index(source.get(index_path).decode("utf-8"))
    records = indexes[index_path]
    grib_path = run.path(step, "grib2")
    messages = pool.map(lambda p: source.get(grib_path, byte_range(records, p)), params)
    return {param: decode(m) for param, m in zip(params, messages)}


def _write_run(source: Source, run: Run, out: Path, decode: Callable[[bytes], np.ndarray],
               pool: ThreadPoolExecutor, indexes: dict[str, list[dict]]) -> None:
    """Every map step of ``run`` as PNGs. Only the previous step's precipitation is kept, for the rain rate."""
    prev: tuple[int, np.ndarray] | None = None
    for step in run.map_steps():
        f = _fields(source, run, step, FIELDS, decode, pool, indexes)
        _save(out, file_name(run, "wind", step), png_wind(f["10u"], f["10v"]))
        _save(out, file_name(run, "temperature", step), png_gray(celsius(f["2t"]), SCALES["temperature"]))
        _save(out, file_name(run, "clouds", step), png_gray(cloud_percent(f["tcc"]), SCALES["clouds"]))
        if prev is not None:
            prev_step, prev_tp = prev
            rain = rain_rate(f["tp"], prev_tp, step - prev_step)
            _save(out, file_name(run, "rain", step), png_gray(rain, SCALES["rain"]))
        prev = (step, f["tp"])


def write_extended(source: Source, run: Run, out: Path, decode: Callable[[bytes], np.ndarray],
                   pool: ThreadPoolExecutor, indexes: dict[str, list[dict]]) -> None:
    """The full run's days 11–15 tiles. Steps are encoded to bytes as they arrive, so memory stays at about
    100 MB for the whole cube."""
    tp_before = _fields(source, run, BASE_STEP, ("tp",), decode, pool, indexes)["tp"]
    cube: np.ndarray | None = None
    for i, step in enumerate(EXTENDED_STEPS):
        f = _fields(source, run, step, EXTENDED_FIELDS, decode, pool, indexes)
        block = encode_step(f, tp_before)
        tp_before = f["tp"]
        if cube is None:
            cube = np.empty((len(EXTENDED_STEPS), *block.shape), np.uint8)
        cube[i] = block
    rows, cols = tile_shape(cube.shape[2:])
    for r in range(rows):
        for c in range(cols):
            _save(out, tile_path(run, r, c), tile_png(cube, r, c))


def _save(out: Path, relative: str, png: bytes) -> None:
    path = out / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
