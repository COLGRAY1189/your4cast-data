from datetime import UTC, datetime

import pytest

from y4cdata.runs import NoCompleteRun, Run, choose_runs


def test_full_run_steps_follow_ecmwf():
    r = Run(datetime(2026, 11, 6, 0, tzinfo=UTC))
    assert r.is_full and r.last_step == 360
    s = r.map_steps()
    assert s[:3] == [0, 3, 6] and 144 in s and 147 not in s and s[-2:] == [234, 240] and len(s) == 65


def test_short_run_stops_at_90():
    r = Run(datetime(2026, 11, 6, 6, tzinfo=UTC))
    assert not r.is_full and r.last_step == 90 and r.map_steps() == list(range(0, 91, 3))


def test_path_matches_ecmwf_naming():
    assert Run(datetime(2026, 11, 6, 0, tzinfo=UTC)).path(24, "index") == \
        "20261106/00z/ifs/0p25/oper/20261106000000-24h-oper-fc.index"


def test_a_run_still_being_published_is_skipped():  # Review Focus 1
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    live = {Run(datetime(2026, 11, 6, 0, tzinfo=UTC)).path(360, "index"),
            Run(datetime(2026, 11, 6, 6, tzinfo=UTC)).path(90, "index")}  # 12 UTC has not finished
    full, short = choose_runs(now, lambda p: p in live)
    assert full.time.hour == 0 and short.time.hour == 6


def test_short_run_older_than_full_run_is_not_used():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    live = {Run(datetime(2026, 11, 6, 12, tzinfo=UTC)).path(360, "index"),
            Run(datetime(2026, 11, 6, 6, tzinfo=UTC)).path(90, "index")}
    assert choose_runs(now, lambda p: p in live) == (Run(datetime(2026, 11, 6, 12, tzinfo=UTC)), None)


def test_nothing_complete_in_48_hours_raises():
    with pytest.raises(NoCompleteRun):
        choose_runs(datetime(2026, 11, 6, 20, tzinfo=UTC), lambda p: False)
