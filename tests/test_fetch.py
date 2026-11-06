import io
import ssl
import urllib.error

import pytest

from y4cdata.fetch import USER_AGENT, FetchError, Source


class FakeOpener:
    """Stands in for urllib.request.urlopen: records each Request and answers (status, body) pairs in order.

    A status of 400 or more raises urllib.error.HTTPError, as urlopen does.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "fake", {}, io.BytesIO(b""))
        return _Response(status, body)


class _Response(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(body)
        self.status = status


def no_sleep(_seconds):
    pass


def test_get_sends_range_and_user_agent():
    op = FakeOpener([(206, b"0123456789")])
    assert Source(["https://a"], opener=op, sleep=no_sleep).get("x", (10, 19)) == b"0123456789"
    req = op.requests[0]
    assert req.full_url == "https://a/x"
    assert req.get_header("Range") == "bytes=10-19" and req.get_header("User-agent") == USER_AGENT


def test_server_errors_retry_then_fall_back_to_the_mirror():
    op = FakeOpener([(503, b"")] * 3 + [(200, b"ok")])
    assert Source(["https://a", "https://b"], opener=op, sleep=no_sleep).get("x") == b"ok"
    assert [r.full_url for r in op.requests] == ["https://a/x"] * 3 + ["https://b/x"]


def test_retries_wait_2_then_8_seconds():
    waits = []
    op = FakeOpener([(429, b""), (500, b""), (200, b"ok")])
    Source(["https://a"], opener=op, sleep=waits.append).get("x")
    assert waits == [2, 8]


def test_not_found_does_not_retry_and_exists_says_false():
    op = FakeOpener([(404, b"")])
    assert Source(["https://a"], opener=op, sleep=no_sleep).exists("x") is False
    assert len(op.requests) == 1 and op.requests[0].get_method() == "HEAD"


def test_a_range_answered_with_the_whole_file_is_not_accepted():
    # A server that ignores Range sends the full file with 200; using it would decode the wrong bytes.
    op = FakeOpener([(200, b"whole file")] * 3)
    with pytest.raises(FetchError):
        Source(["https://a"], opener=op, sleep=no_sleep).get("x", (0, 3))


def test_a_certificate_failure_goes_straight_to_the_next_root():
    # Seen on this laptop: the portal's chain ends at HARICA TLS RSA Root CA 2021, which the Windows store lacks.
    # Retrying cannot fix that, so the mirror is asked at once rather than after 10 s of waits.
    bad_cert = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
    waits = []
    op = FakeOpener([bad_cert, (200, b"ok")])
    assert Source(["https://a", "https://b"], opener=op, sleep=waits.append).get("x") == b"ok"
    assert [r.full_url for r in op.requests] == ["https://a/x", "https://b/x"] and waits == []


def test_every_root_failing_names_the_last_status():
    op = FakeOpener([(404, b""), (503, b""), (503, b""), (503, b"")])
    with pytest.raises(FetchError, match="503"):
        Source(["https://a", "https://b"], opener=op, sleep=no_sleep).get("x")
