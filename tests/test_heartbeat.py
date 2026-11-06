from datetime import UTC, datetime, timedelta

from y4cdata.heartbeat import heartbeat_due


def test_heartbeat_comes_well_before_githubs_60_days():  # Review Focus 5
    t = datetime(2026, 11, 6, tzinfo=UTC)
    assert heartbeat_due(t - timedelta(days=30), t) and not heartbeat_due(t - timedelta(days=29), t)
