"""HTTP fetching from ECMWF's open-data portal, with its AWS mirror as the fallback.

The portal caps all users at 500-2000 simultaneous connections, so callers keep to a few at once and a busy answer
(429 or 5xx) is retried, then handed to the next root.
"""

import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable

USER_AGENT = "your4cast-data/1.0 (+https://github.com/COLGRAY1189/your4cast-data)"
ROOTS = [
    "https://data.ecmwf.int/forecasts",
    # The AWS Open Data mirror's CloudFront distribution (registry.opendata.aws/ecmwf-forecasts). Its S3 bucket
    # answered "503 SlowDown" to most requests on 2026-11-06 while CloudFront served them, so S3 comes last.
    "https://d2zvc0wgha4k2l.cloudfront.net",
    "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com",
]
RETRY_WAITS = (2, 8)
"""Seconds between the three attempts on one root."""
TIMEOUT_S = 120


class FetchError(Exception):
    """Every root failed."""


class Source:
    """Reads files below one of several roots, the first root first."""

    def __init__(self, roots: list[str] = ROOTS, opener: Callable = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.roots = [r.rstrip("/") for r in roots]
        self.opener = opener
        self.sleep = sleep

    def get(self, path: str, byte_range: tuple[int, int] | None = None) -> bytes:
        """The file's bytes, or only the inclusive ``byte_range`` of them."""
        last = "no roots"
        for root in self.roots:
            url = f"{root}/{path}"
            for attempt in range(len(RETRY_WAITS) + 1):
                if attempt:
                    self.sleep(RETRY_WAITS[attempt - 1])
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                if byte_range:
                    req.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
                try:
                    with self.opener(req, timeout=TIMEOUT_S) as resp:
                        data = resp.read()
                except urllib.error.HTTPError as e:
                    last = f"HTTP {e.code} for {url}"
                    if e.code == 429 or e.code >= 500:
                        continue
                    break  # 404 and other client errors: this root will not have it
                except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                    last = f"{type(e).__name__} for {url}: {e}"
                    if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
                        break  # a certificate this machine cannot verify will not verify on a retry
                    continue
                if byte_range and len(data) != byte_range[1] - byte_range[0] + 1:
                    # A server that ignored Range sent something else; decoding it would read the wrong field.
                    last = f"asked for {byte_range[1] - byte_range[0] + 1} bytes, got {len(data)} from {url}"
                    continue
                return data
        raise FetchError(last)

    def exists(self, path: str) -> bool:
        """True when any root answers 200 to a HEAD request for the file."""
        for root in self.roots:
            req = urllib.request.Request(f"{root}/{path}", method="HEAD", headers={"User-Agent": USER_AGENT})
            try:
                with self.opener(req, timeout=TIMEOUT_S) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                continue
        return False
