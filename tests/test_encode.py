import io

import numpy as np
import pytest
from PIL import Image

from y4cdata.encode import SCALES, from_bytes, png_gray, png_wind, to_bytes


def test_out_of_range_values_clamp_instead_of_wrapping():  # Review Focus 3
    w = SCALES["wind"]
    assert list(to_bytes(np.array([-75.0, 75.0]), w)) == [0, 255]
    assert list(to_bytes(np.array([-75.0]), SCALES["temperature"])) == [0]
    assert list(to_bytes(np.array([250.0]), SCALES["rain"])) == [255]


def test_light_rain_survives_the_encoding():
    r = SCALES["rain"]
    assert to_bytes(np.array([0.1]), r)[0] >= 7
    assert abs(from_bytes(to_bytes(np.array([0.1]), r), r)[0] - 0.1) < 0.02


def test_round_trip_error_is_within_half_a_step():
    t = SCALES["temperature"]
    x = np.linspace(-70, 60, 1000)
    assert np.abs(from_bytes(to_bytes(x, t), t) - x).max() <= (t.max - t.min) / 255 / 2 + 1e-6


def test_wind_png_has_no_alpha_and_scalars_are_grey():  # Review Focus 4
    u = np.full((2, 3), 10.0)
    v = np.full((2, 3), -10.0)
    img = Image.open(io.BytesIO(png_wind(u, v)))
    assert img.mode == "RGB" and img.size == (3, 2) and img.getpixel((0, 0))[2] == 0
    w = SCALES["wind"]
    r, g, _ = img.getpixel((0, 0))
    assert abs(from_bytes(np.array([r]), w)[0] - 10) < 0.3 and abs(from_bytes(np.array([g]), w)[0] + 10) < 0.3
    assert Image.open(io.BytesIO(png_gray(u, SCALES["temperature"]))).mode == "L"


def test_a_missing_value_fails_loudly():
    # ECMWF fields have no gaps; a NaN means something upstream broke, and casting it would draw garbage.
    with pytest.raises(ValueError, match="NaN"):
        to_bytes(np.array([1.0, np.nan]), SCALES["temperature"])
