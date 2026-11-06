from pathlib import Path

import pytest

from y4cdata.index import FIELDS, byte_range, parse_index

DATA = Path(__file__).parent / "data"


def test_byte_range_is_inclusive_and_surface_only():
    recs = parse_index((DATA / "sample.index").read_text())
    start, end = byte_range(recs, "2t")
    rec = next(r for r in recs if r["param"] == "2t" and r["levtype"] == "sfc")
    assert (start, end) == (rec["_offset"], rec["_offset"] + rec["_length"] - 1)


def test_every_field_the_job_needs_is_in_a_real_index():
    recs = parse_index((DATA / "sample.index").read_text())
    for param in FIELDS:
        start, end = byte_range(recs, param)
        assert end > start


def test_missing_field_names_itself():
    with pytest.raises(KeyError, match="tcc"):
        byte_range([{"param": "2t", "levtype": "sfc", "_offset": 0, "_length": 1}], "tcc")
