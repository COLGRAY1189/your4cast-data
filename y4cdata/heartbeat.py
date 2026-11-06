"""Keeps the hourly schedule alive. GitHub switches off scheduled workflows in a public repo after 60 days with
no repository activity, and the build itself commits nothing, so the workflow commits HEARTBEAT.md when the last
commit is 30 or more days old.

https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule

``python -m y4cdata.heartbeat`` prints ``due`` or ``not due`` for this repo's last commit.
"""

import subprocess
from datetime import UTC, datetime, timedelta

EVERY = timedelta(days=30)


def heartbeat_due(last_commit: datetime, now: datetime) -> bool:
    return now - last_commit >= EVERY


def last_commit_time() -> datetime:
    out = subprocess.run(["git", "log", "-1", "--format=%ct"], capture_output=True, text=True, check=True)
    return datetime.fromtimestamp(int(out.stdout.strip()), UTC)


if __name__ == "__main__":
    print("due" if heartbeat_due(last_commit_time(), datetime.now(UTC)) else "not due")
