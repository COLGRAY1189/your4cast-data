"""ECMWF IFS open-data runs: which steps each has, where its files are, and which runs to publish.

Steps per run (ECMWF open data, stream ``oper``, type ``fc``): 00 and 12 UTC run 0-144 h by 3 and 150-360 h by 6;
06 and 18 UTC run 0-90 h by 3.
https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

MAP_HORIZON_H = 240
"""The map shows 10 days from the full run's start."""

RUN_HOURS = (0, 6, 12, 18)
LOOKBACK = timedelta(hours=48)


class NoCompleteRun(Exception):
    """No full run in the last 48 hours has all its files published."""


@dataclass(frozen=True)
class Run:
    """One forecast run, identified by its start time (UTC, on a run hour)."""

    time: datetime

    def __post_init__(self) -> None:
        t = self.time
        if t.tzinfo is None or t.utcoffset() != timedelta(0):
            raise ValueError(f"run time must be UTC: {t!r}")
        if t.hour not in RUN_HOURS or (t.minute, t.second, t.microsecond) != (0, 0, 0):
            raise ValueError(f"not a run time: {t.isoformat()}")

    @property
    def is_full(self) -> bool:
        """00 and 12 UTC runs reach 360 h; 06 and 18 UTC runs stop at 90 h."""
        return self.time.hour in (0, 12)

    @property
    def last_step(self) -> int:
        return 360 if self.is_full else 90

    @property
    def key(self) -> str:
        return f"{self.time:%Y%m%d%H}"

    def map_steps(self, horizon: int = MAP_HORIZON_H) -> list[int]:
        """The run's steps up to ``horizon`` hours: every 3 h to 144 h, every 6 h after."""
        last = min(horizon, self.last_step)
        return [s for s in range(0, min(last, 144) + 1, 3)] + list(range(150, last + 1, 6))

    def path(self, step: int, ext: str) -> str:
        """The file's path below a data root, e.g. ``20261106/00z/ifs/0p25/oper/20261106000000-24h-oper-fc.index``."""
        t = self.time
        return f"{t:%Y%m%d}/{t:%H}z/ifs/0p25/oper/{t:%Y%m%d%H}0000-{step}h-oper-fc.{ext}"


def choose_runs(now: datetime, exists: Callable[[str], bool]) -> tuple[Run, Run | None]:
    """The newest complete full run, and the newest complete short run newer than it, if any.

    A run counts as complete only when its last step's index exists: ECMWF publishes a run's files over time.
    """
    newest = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    newest -= timedelta(hours=newest.hour % 6)
    short: Run | None = None
    t = newest
    while now - t < LOOKBACK:
        run = Run(t)
        complete = exists(run.path(run.last_step, "index"))
        if run.is_full and complete:
            return run, short
        if not run.is_full and complete and short is None:
            short = run
        t -= timedelta(hours=6)
    raise NoCompleteRun(f"no complete 00/12 UTC run since {(now - LOOKBACK).isoformat()}")
