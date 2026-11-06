"""``python -m y4cdata --out site [--published-url URL] [--status-file status.txt]``

Builds the site for the newest complete ECMWF runs. Writes ``built`` or ``unchanged`` to the status file (the
workflow deploys only after ``built``) and exits non-zero on any error.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from y4cdata.build import build, read_published
from y4cdata.fetch import Source


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="y4cdata", description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, required=True, help="directory to write the site into")
    p.add_argument("--published-url", help="the live manifest.json; when its runs match, nothing is built")
    p.add_argument("--status-file", type=Path, help="where to write 'built' or 'unchanged'")
    args = p.parse_args(argv)
    published = read_published(args.published_url) if args.published_url else None
    status = build(Source(), datetime.now(UTC), args.out, published)
    if args.status_file:
        args.status_file.write_text(status, encoding="utf-8")
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
