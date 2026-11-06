"""ECMWF open-data index files: one JSON record per GRIB field, with its byte offset and length in the .grib2 file.

https://confluence.ecmwf.int/spaces/DAC/pages/738041083/ECMWF+open+data+getting+the+data
"""

import json

FIELDS = ("10u", "10v", "2t", "tp", "tcc")
"""The surface fields the map needs: 10 m wind (m/s), 2 m temperature (K), total precipitation (m, accumulated
from step 0) and total cloud cover (0-1)."""


def parse_index(text: str) -> list[dict]:
    """Every record in an index file, in file order."""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def byte_range(records: list[dict], param: str) -> tuple[int, int]:
    """The inclusive first and last byte of the surface field ``param``, for an HTTP Range request."""
    for r in records:
        if r.get("param") == param and r.get("levtype") == "sfc":
            start = int(r["_offset"])
            return start, start + int(r["_length"]) - 1
    raise KeyError(f"no surface field {param!r} in the index")
