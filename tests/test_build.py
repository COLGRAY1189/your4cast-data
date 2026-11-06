import io
import json
import urllib.error
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from y4cdata import __main__ as cli
from y4cdata.build import build, read_published
from y4cdata.encode import SCALES, from_bytes
from y4cdata.index import FIELDS
from y4cdata.runs import Run

FULL, SHORT = Run(datetime(2026, 11, 6, 0, tzinfo=UTC)), Run(datetime(2026, 11, 6, 6, tzinfo=UTC))
NOW = datetime(2026, 11, 6, 20, tzinfo=UTC)


class FakeSource:
    """Both runs complete. Every index lists the five fields 100 bytes apart; a field's 'bytes' name its param
    and step, which fake_decode turns into an array."""

    def __init__(self):
        self.live = {FULL.path(360, "index"), SHORT.path(90, "index")}
        self.gets = []

    def exists(self, path):
        return path in self.live

    def get(self, path, byte_range=None):
        self.gets.append(path)
        if path.endswith(".index"):
            recs = [{"param": p, "levtype": "sfc", "_offset": i * 100, "_length": 100} for i, p in enumerate(FIELDS)]
            return "\n".join(json.dumps(r) for r in recs).encode()
        step = int(path.split("-")[1].rstrip("h"))  # ".../20261106000000-24h-oper-fc.grib2"
        return json.dumps({"param": FIELDS[byte_range[0] // 100], "step": step}).encode()


def fake_decode(message):
    d = json.loads(message)
    value = {"10u": 5.0, "10v": -5.0, "2t": 293.15, "tp": 0.001 * d["step"], "tcc": 0.5}[d["param"]]
    return np.full((4, 8), value, dtype=np.float32)


def test_build_writes_every_frame_and_the_manifest(tmp_path):
    assert build(FakeSource(), NOW, tmp_path, None, decode=fake_decode) == "built"
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["runs"] == ["2026-11-06T00:00:00Z", "2026-11-06T06:00:00Z"]
    for fr in m["frames"]:
        for layer, path in fr.items():
            if layer != "time":
                assert (tmp_path / path).is_file(), path


def test_layers_hold_the_derived_values(tmp_path):
    build(FakeSource(), NOW, tmp_path, None, decode=fake_decode)
    temp = np.asarray(Image.open(tmp_path / "frames/2026110600/temperature-024.png"))
    rain = np.asarray(Image.open(tmp_path / "frames/2026110600/rain-024.png"))
    assert abs(from_bytes(temp, SCALES["temperature"]).mean() - 20.0) < 0.3  # 293.15 K
    assert abs(from_bytes(rain, SCALES["rain"]).mean() - 1.0) < 0.1  # tp grows 1 mm an hour


def test_superseded_full_run_frames_stay_in_the_deploy(tmp_path):  # Review Focus 2
    build(FakeSource(), NOW, tmp_path, None, decode=fake_decode)
    for step in range(0, 91, 3):
        assert (tmp_path / f"frames/2026110600/wind-{step:03d}.png").is_file()


def test_headers_cache_the_manifest_briefly_and_frames_for_a_year(tmp_path):
    build(FakeSource(), NOW, tmp_path, None, decode=fake_decode)
    h = (tmp_path / "_headers").read_text()
    assert "/manifest.json\n  Cache-Control: public, max-age=300" in h
    assert "/frames/*\n  Cache-Control: public, max-age=31536000, immutable" in h


def test_same_runs_already_live_means_unchanged(tmp_path):
    live = {"runs": ["2026-11-06T00:00:00Z", "2026-11-06T06:00:00Z"]}
    source = FakeSource()
    assert build(source, NOW, tmp_path, live, decode=fake_decode) == "unchanged"
    assert not any(tmp_path.iterdir()) and source.gets == []


def test_each_step_fetches_its_index_once(tmp_path):
    source = FakeSource()
    build(source, NOW, tmp_path, None, decode=fake_decode)
    indexes = [p for p in source.gets if p.endswith(".index")]
    assert len(indexes) == len(set(indexes)) == len(FULL.map_steps()) + len(SHORT.map_steps())


class Answer(io.BytesIO):
    status = 200


def test_published_manifest_404_means_none_is_live():
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b""))
    assert read_published("https://x/manifest.json", opener=opener) is None


def test_published_manifest_other_errors_stop_the_run():
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "err", {}, io.BytesIO(b""))
    with pytest.raises(urllib.error.HTTPError):
        read_published("https://x/manifest.json", opener=opener)


def test_published_manifest_is_read():
    assert read_published("https://x/m.json", opener=lambda req, timeout=None: Answer(b'{"runs": []}')) == {"runs": []}


def test_cli_writes_the_status_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build", lambda *a, **k: "unchanged")
    monkeypatch.setattr(cli, "read_published", lambda url: {"runs": []})
    status = tmp_path / "status.txt"
    assert cli.main(["--out", str(tmp_path / "site"), "--published-url", "https://x", "--status-file", str(status)]) == 0
    assert status.read_text() == "unchanged"
