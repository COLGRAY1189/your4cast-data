import json
from datetime import UTC, datetime, timedelta

from y4cdata.manifest import build_manifest, file_name, frame_plan
from y4cdata.runs import Run

FULL, SHORT = Run(datetime(2026, 11, 6, 0, tzinfo=UTC)), Run(datetime(2026, 11, 6, 6, tzinfo=UTC))


def test_frames_cover_ten_days_three_hourly_then_six_hourly():
    f = frame_plan(FULL, None)
    assert f[0].time == FULL.time and f[-1].time == FULL.time + timedelta(hours=240) and len(f) == 65
    gaps = {(b.time - a.time) for a, b in zip(f, f[1:])}
    assert gaps == {timedelta(hours=3), timedelta(hours=6)}


def test_the_short_run_supersedes_where_it_reaches():
    by_time = {fr.time: fr for fr in frame_plan(FULL, SHORT)}
    t = SHORT.time + timedelta(hours=9)
    assert by_time[t].sources["wind"] == (SHORT, 9)
    assert by_time[SHORT.time + timedelta(hours=93)].sources["wind"] == (FULL, 99)


def test_rain_needs_an_interval_so_step_0_falls_back():
    by_time = {fr.time: fr for fr in frame_plan(FULL, SHORT)}
    assert by_time[SHORT.time].sources["rain"] == (FULL, 6)
    assert "rain" not in by_time[FULL.time].sources  # nothing before the full run's step 0


def test_file_names_sit_under_frames():
    assert file_name(SHORT, "wind", 3) == "frames/2026110606/wind-003.png"


def test_manifest_is_the_documented_contract():
    m = build_manifest(frame_plan(FULL, SHORT), FULL, SHORT, datetime(2026, 11, 6, 9, 17, tzinfo=UTC))
    assert m["version"] == 1 and m["runs"] == ["2026-11-06T00:00:00Z", "2026-11-06T06:00:00Z"]
    assert m["generated"] == "2026-11-06T09:17:00Z"
    assert m["layers"]["rain"] == {"encoding": "sqrt", "min": 0, "max": 100, "unit": "mm/h"}
    assert m["layers"]["wind"]["channels"] == ["u", "v"]
    assert m["grid"] == {"width": 1440, "height": 721, "lon0": -180.0, "lat0": 90.0, "dlon": 0.25, "dlat": -0.25}
    assert m["frames"][3] == {
        "time": "2026-11-06T09:00:00Z",
        "wind": "frames/2026110606/wind-003.png",
        "temperature": "frames/2026110606/temperature-003.png",
        "rain": "frames/2026110606/rain-003.png",
        "clouds": "frames/2026110606/clouds-003.png",
    }
    assert "ECMWF" in m["source"] and "CC BY 4.0" in m["source"]
    assert json.loads(json.dumps(m, allow_nan=False)) == m


def test_without_a_short_run_the_manifest_lists_one_run():
    m = build_manifest(frame_plan(FULL, None), FULL, None, datetime(2026, 11, 6, 8, 17, tzinfo=UTC))
    assert m["runs"] == ["2026-11-06T00:00:00Z"]
