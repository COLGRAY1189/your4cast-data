"""Decodes one ECMWF GRIB2 field into a north-up array starting at 180° W.

The 0.25° fields are CCSDS-packed (data template 5.42), which only ecCodes reads. The grid is checked key by key
so that a change of layout at ECMWF fails the run instead of drawing the map flipped or shifted.
"""

import eccodes
import numpy as np

WIDTH, HEIGHT = 1440, 721

EXPECTED_GRID = {
    "Ni": WIDTH,
    "Nj": HEIGHT,
    "latitudeOfFirstGridPointInDegrees": 90.0,
    "longitudeOfFirstGridPointInDegrees": 180.0,
    "iScansNegatively": 0,
    "jScansPositively": 0,
}


class GridError(Exception):
    """The field is not on the grid the textures assume."""


def decode(message: bytes) -> np.ndarray:
    """The field's values, shape (721, 1440): row 0 is 90° N, column 0 is 180° W, columns step east by 0.25°."""
    h = eccodes.codes_new_from_message(message)
    try:
        for key, want in EXPECTED_GRID.items():
            got = eccodes.codes_get(h, key, ktype=float if isinstance(want, float) else int)
            if got != want:
                raise GridError(f"{key} is {got}, expected {want}")
        values = eccodes.codes_get_values(h)
    finally:
        eccodes.codes_release(h)
    return np.asarray(values, dtype=np.float32).reshape(HEIGHT, WIDTH)
