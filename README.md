# your4cast-data

Map-layer data for the Your4cast weather app (Android). Every hour a GitHub Actions job checks for a new ECMWF
forecast run. When there is one, it turns the run into map textures and a `manifest.json` and publishes them on
Cloudflare Pages:

- **Layers:** wind (u and v), temperature, rain rate, cloud cover.
- **Range:** 10 days, 3-hourly to 144 h and 6-hourly to 240 h.
- **Grid:** global 0.25° (1440 × 721).

The format the app reads is in [docs/manifest.md](docs/manifest.md). How the job reads ECMWF's files is in
[docs/ecmwf-open-data.md](docs/ecmwf-open-data.md), and how it publishes is in
[docs/cloudflare-pages.md](docs/cloudflare-pages.md).

## Attribution

Contains modified ECMWF open data (CC BY 4.0), changed by Your4cast.
Source: https://www.ecmwf.int/en/forecasts/datasets/open-data. The fields are converted to °C, mm/h and %, rain is
taken as the rate between forecast steps, and every layer is re-encoded as 8-bit PNG. The test fixture
`tests/data/2t-step24.grib2` is one unmodified ECMWF field (same licence).

## Running it

```
python -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m y4cdata --out site --status-file status.txt
```

A full build downloads about 260 MB of selected fields from ECMWF (byte ranges, at most 4 at a time) and writes
about 110 MB of PNGs.

## Schedule
- `build.yml`: every hour at :17 UTC, and by hand. It deploys only when a newer complete run exists. A failed run
  opens (or comments on) an issue labelled `build-failing`. When the last commit is 30 or more days old it commits
  `HEARTBEAT.md`, because GitHub switches off schedules in public repos after 60 quiet days.
- `test.yml`: the tests, on every push.

The code in this repository is not licensed for reuse.
