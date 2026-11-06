"""Days 11–15 for the app's rewarded unlock: 6-hourly values per 10° tile, which the app sums into local days.

MET Norway's point forecast stops at about 10 days; ECMWF's 00 and 12 UTC runs reach 360 h (spec section 7). A tile
is one 8-bit grey PNG, 40 columns (west to east) by 40 × steps × 4 rows: for step index i and field f (max, min,
rain, cloud) the block i·4 + f holds rows 40·(i·4 + f) … +39, north to south. The contract is in docs/manifest.md.
"""

import io

import numpy as np
from PIL import Image

from y4cdata.encode import SCALES, Scale, to_bytes
from y4cdata.fields import celsius, cloud_percent, rain_rate
from y4cdata.runs import Run

BASE_STEP = 210
"""Fetched for `tp` only: the start of the first 6-hour interval."""

EXTENDED_STEPS = list(range(216, 361, 6))
"""Each step's values cover the 6 hours before it, so together they cover run+210 h … run+360 h. That reaches back
far enough for a local day 11 that starts before run+240 h (Cape Town on the 00 UTC run: run+238 h; Sydney on the
12 UTC run: run+218 h)."""

EXTENDED_FIELDS = ("mx2t6", "mn2t6", "tp", "tcc")
FIELD_NAMES = ("max", "min", "rain", "cloud")
TILE_DEG = 10
TILE_POINTS = 40
"""Grid points per tile side at 0.25°."""

EXTENDED_SCALES: dict[str, Scale] = {
    "max": SCALES["temperature"],
    "min": SCALES["temperature"],
    "rain": Scale("sqrt", 0, 200, "mm"),
    "cloud": SCALES["clouds"],
}


def encode_step(fields: dict[str, np.ndarray], tp_before: np.ndarray) -> np.ndarray:
    """One step's four blocks as bytes, shape (4, h, w): max and min °C over the 6 h, rain mm in them, cloud %."""
    rain_mm = rain_rate(fields["tp"], tp_before, 1)  # a rate over 1 h of an interval total is that total
    return np.stack([
        to_bytes(celsius(fields["mx2t6"]), EXTENDED_SCALES["max"]),
        to_bytes(celsius(fields["mn2t6"]), EXTENDED_SCALES["min"]),
        to_bytes(rain_mm, EXTENDED_SCALES["rain"]),
        to_bytes(cloud_percent(fields["tcc"]), EXTENDED_SCALES["cloud"]),
    ])


def encode_steps(fields: dict[int, dict[str, np.ndarray]]) -> np.ndarray:
    """Every extended step's blocks, shape (25, 4, h, w); ``fields`` also holds BASE_STEP's ``tp``."""
    tp_before = fields[BASE_STEP]["tp"]
    out = []
    for step in EXTENDED_STEPS:
        out.append(encode_step(fields[step], tp_before))
        tp_before = fields[step]["tp"]
    return np.stack(out)


def tile_shape(grid: tuple[int, int]) -> tuple[int, int]:
    """Tile rows and columns for a grid; the 721st row (90° S) is left out so every tile is 40 × 40 points."""
    return grid[0] // TILE_POINTS, grid[1] // TILE_POINTS


def tile_png(cube: np.ndarray, row: int, col: int) -> bytes:
    """Tile (row, col) of an encoded cube as a grey PNG."""
    r0, c0 = row * TILE_POINTS, col * TILE_POINTS
    part = cube[:, :, r0:r0 + TILE_POINTS, c0:c0 + TILE_POINTS]
    out = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(part.reshape(-1, TILE_POINTS))).save(out, format="PNG", compress_level=9)
    return out.getvalue()


def tile_path(run: Run, row: int, col: int) -> str:
    return f"extended/{run.key}/{row}-{col}.png"


def extended_block(full: Run) -> dict:
    """The manifest's `extended` key: where the tiles are and how to read them."""
    return {
        "run": _iso(full),
        "tileDeg": TILE_DEG,
        "points": TILE_POINTS,
        "steps": EXTENDED_STEPS,
        "fields": list(FIELD_NAMES),
        "tile": f"extended/{full.key}/{{row}}-{{col}}.png",
        "scales": {
            name: {"encoding": s.encoding, "min": s.min, "max": s.max, "unit": s.unit}
            for name, s in EXTENDED_SCALES.items()
        },
    }


def _iso(run: Run) -> str:
    return run.time.strftime("%Y-%m-%dT%H:%M:%SZ")
