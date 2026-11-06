from pathlib import Path

import eccodes
import numpy as np
import pytest

from y4cdata.grib import GridError, decode

DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "2t-step24.grib2"  # real 2t of the 2026-11-06 00 UTC run, step 24 (valid 7 Nov 00 UTC)


def with_key(path: Path, key: str, value: int) -> bytes:
    """The fixture message with one header key changed, as another grid layout would arrive."""
    h = eccodes.codes_new_from_message(path.read_bytes())
    try:
        eccodes.codes_set(h, key, value)
        return eccodes.codes_get_message(h)
    finally:
        eccodes.codes_release(h)


def test_temperature_lands_where_the_planet_is():
    """Real values in the fixture: 90° S row 233.5 K, equator row 299.9 K, 65° N 120° E 240.2 K, 65° N 0° 281.0 K.

    Every threshold is at least 11 K from the value it checks.
    """
    k = decode(FIXTURE.read_bytes())
    assert k.shape == (721, 1440) and k.dtype == np.float32
    assert k[-1].mean() < 253  # row 720 is 90° S: the South Pole in November is far below −20 °C
    assert k[360].mean() > 288  # row 360 is the equator: mostly tropical sea, well above 15 °C
    # Longitude: at 65° N (row 100), Yakutia at 120° E (column 1200) is far colder in November than the
    # Norwegian Sea at 0° (column 720). A grid shifted half a world would sample 60° W and 180° instead.
    assert k[100, 1200] < k[100, 720] - 15


def test_a_flipped_grid_is_refused():
    with pytest.raises(GridError, match="jScansPositively"):
        decode(with_key(FIXTURE, "jScansPositively", 1))
