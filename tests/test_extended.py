import io
from datetime import UTC, datetime

import numpy as np
from PIL import Image

from y4cdata.encode import SCALES, from_bytes
from y4cdata.extended import (
    BASE_STEP,
    EXTENDED_FIELDS,
    EXTENDED_SCALES,
    EXTENDED_STEPS,
    TILE_POINTS,
    encode_steps,
    extended_block,
    tile_png,
    tile_shape,
)
from y4cdata.runs import Run


def fields_for(shape, tp_mm_per_step=2.0, max_k=300.15, min_k=280.15, cloud=0.5):
    """Raw fields for the base step and every extended step: tp grows by tp_mm_per_step each 6 h."""
    out = {}
    for i, step in enumerate([BASE_STEP] + EXTENDED_STEPS):
        out[step] = {
            "mx2t6": np.full(shape, max_k, np.float32),
            "mn2t6": np.full(shape, min_k, np.float32),
            "tp": np.full(shape, i * tp_mm_per_step / 1000, np.float32),
            "tcc": np.full(shape, cloud, np.float32),
        }
    return out


def test_steps_cover_day_eleven_wherever_it_starts():
    assert EXTENDED_STEPS[0] == 216 and EXTENDED_STEPS[-1] == 360 and len(EXTENDED_STEPS) == 25
    assert BASE_STEP == 210 and EXTENDED_FIELDS == ("mx2t6", "mn2t6", "tp", "tcc")


def test_blocks_hold_max_min_rain_and_cloud_in_display_units():
    cube = encode_steps(fields_for((40, 40)))
    assert cube.shape == (25, 4, 40, 40) and cube.dtype == np.uint8
    first = cube[0]
    assert abs(from_bytes(first[0], EXTENDED_SCALES["max"]).mean() - 27.0) < 0.3
    assert abs(from_bytes(first[1], EXTENDED_SCALES["min"]).mean() - 7.0) < 0.3
    assert abs(from_bytes(first[2], EXTENDED_SCALES["rain"]).mean() - 2.0) < 0.15  # mm in the 6 h
    assert abs(from_bytes(first[3], EXTENDED_SCALES["cloud"]).mean() - 50) < 0.3
    assert EXTENDED_SCALES["max"] == SCALES["temperature"] and EXTENDED_SCALES["cloud"] == SCALES["clouds"]
    assert (EXTENDED_SCALES["rain"].encoding, EXTENDED_SCALES["rain"].max) == ("sqrt", 200)


def test_rain_never_goes_negative():
    f = fields_for((40, 40))
    f[EXTENDED_STEPS[3]]["tp"][:] = 0.0  # packing noise: the total drops
    cube = encode_steps(f)
    assert cube[3, 2].max() == 0


def test_a_tile_covers_its_ten_degrees():
    # Row 3 is 60–50° N (grid rows 120–159); column 20 is 20–30° E (grid columns 800–839).
    cube = np.zeros((1, 4, 720, 1440), np.uint8)
    cube[0, 0, 120, 800] = 201
    cube[0, 0, 159, 839] = 202
    cube[0, 3, 120, 800] = 203
    img = np.asarray(Image.open(io.BytesIO(tile_png(cube, 3, 20))))
    assert img.shape == (4 * TILE_POINTS, TILE_POINTS)  # one step: 4 blocks of 40 rows
    assert img[0, 0] == 201 and img[39, 39] == 202 and img[3 * 40, 0] == 203


def test_the_grid_makes_648_tiles_and_leaves_the_pole_row_out():
    assert tile_shape((721, 1440)) == (18, 36)


def test_manifest_block_names_the_full_run_and_the_layout():
    b = extended_block(Run(datetime(2026, 11, 6, 0, tzinfo=UTC)))
    assert b["run"] == "2026-11-06T00:00:00Z" and b["tileDeg"] == 10 and b["points"] == 40
    assert b["steps"] == list(range(216, 361, 6)) and b["fields"] == ["max", "min", "rain", "cloud"]
    assert b["tile"] == "extended/2026110600/{row}-{col}.png"
    assert b["scales"]["rain"] == {"encoding": "sqrt", "min": 0, "max": 200, "unit": "mm"}
