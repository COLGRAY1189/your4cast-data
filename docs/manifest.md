# `manifest.json`: the contract the app reads

Published at the site root next to `frames/`. Built by `y4cdata/manifest.py`; plan 4's live map consumes it.

## Example (shortened)

```json
{
  "version": 1,
  "generated": "2026-11-06T09:17:00Z",
  "runs": ["2026-11-06T00:00:00Z", "2026-11-06T06:00:00Z"],
  "source": "Contains modified ECMWF open data (CC BY 4.0), changed by Your4cast. IFS 0.25°, stream oper.",
  "grid": {"width": 1440, "height": 721, "lon0": -180.0, "lat0": 90.0, "dlon": 0.25, "dlat": -0.25},
  "layers": {
    "wind": {"encoding": "linear", "min": -60, "max": 60, "unit": "m/s", "channels": ["u", "v"]},
    "temperature": {"encoding": "linear", "min": -70, "max": 60, "unit": "°C"},
    "rain": {"encoding": "sqrt", "min": 0, "max": 100, "unit": "mm/h"},
    "clouds": {"encoding": "linear", "min": 0, "max": 100, "unit": "%"}
  },
  "frames": [
    {"time": "2026-11-06T00:00:00Z", "wind": "frames/2026110600/wind-000.png",
     "temperature": "frames/2026110600/temperature-000.png", "clouds": "frames/2026110600/clouds-000.png"},
    {"time": "2026-11-06T09:00:00Z", "wind": "frames/2026110606/wind-003.png",
     "temperature": "frames/2026110606/temperature-003.png", "rain": "frames/2026110606/rain-003.png",
     "clouds": "frames/2026110606/clouds-003.png"}
  ]
}
```

## Keys
| Key | Meaning |
|---|---|
| `version` | `1`. A change that would break this document's reader raises it. |
| `generated` | When the job wrote this manifest (UTC). Data older than about 18 h means the job has stopped. |
| `runs` | The ECMWF runs the frames come from: the newest complete 00/12 UTC run, then a newer complete 06/18 UTC run if there is one. |
| `source` | The attribution to show on the map. |
| `grid` | Every texture is `width` × `height` pixels. Pixel (x, y) is longitude `lon0 + x·dlon`, latitude `lat0 + y·dlat`: x = 0 is 180° W, y = 0 is 90° N, y = 720 is 90° S. Columns repeat at the dateline (x = 1440 would be 180° E = x 0). |
| `layers` | How each layer's bytes become values (below). |
| `frames` | One per moment, oldest first: 3-hourly to the full run's +144 h, then 6-hourly to +240 h. Each names a PNG per layer. **`rain` is missing from the very first frame** (rain is a rate over the hours before the moment, and nothing precedes the run's start). |

## Decoding a pixel
Byte `b` (0–255) from the PNG:

- `linear`: `value = min + (max − min) · b / 255`
- `sqrt`: `value = max · (b / 255)²`

Values beyond `min`/`max` were clamped when encoded. Wind PNGs are RGB: **u (towards east) in red, v (towards
north) in green**, blue 0, no alpha. Every other layer is an 8-bit grey PNG. Rain is the mean rate over the 3 or
6 hours that end at the frame's time.

## `extended`: days 11–15 (for the rewarded unlock)

```json
"extended": {
  "run": "2026-11-06T00:00:00Z", "tileDeg": 10, "points": 40,
  "steps": [216, 222, 228, …, 360], "fields": ["max", "min", "rain", "cloud"],
  "tile": "extended/2026110600/{row}-{col}.png",
  "scales": {"max": {"encoding": "linear", "min": -70, "max": 60, "unit": "°C"},
             "min": {…same…}, "rain": {"encoding": "sqrt", "min": 0, "max": 200, "unit": "mm"},
             "cloud": {"encoding": "linear", "min": 0, "max": 100, "unit": "%"}}
}
```

- Always from the **full** run, never the short one: only 00 and 12 UTC runs reach 360 h.
- **Which point, then which tile:** the nearest grid point, `Y = round((90 − lat) / 0.25)` (at most 719) and
  `X = round((lon + 180) / 0.25) mod 1440`. Its tile is `row = Y div 40`, `col = X div 40` (rows 0–17, columns 0–35,
  648 tiles), and inside it `y = Y − 40·row`, `x = X − 40·col`. The pole row (90° S) is not served.
  - **Round, never floor.** On ECMWF's land-sea mask (2026-11-06), flooring put Cape Town on a sea point (land
    0.00), whose 6-hourly highs barely move. The nearest point is land (0.98), and so were the nearest points for
    Durban, London, Sydney, New York and Johannesburg.
- **Inside a tile:** one 8-bit grey PNG, 40 wide by 40 × 25 × 4 = 4000 tall. For step index `i` (0 for 216 …
  24 for 360) and field `f` (0 max, 1 min, 2 rain, 3 cloud), the value is at pixel `(x, 40·(i·4 + f) + y)`.
- **What a step means:** step `s` covers the 6 hours before run + `s` h, so the 25 steps cover run + 210 h to
  run + 360 h. `max` and `min` are the highest and lowest 2 m temperature in those 6 hours (ECMWF `mx2t6`,
  `mn2t6`), `rain` is the precipitation total in them in mm, and `cloud` is cloud cover at run + `s` h.
- **A local day** is the 6-hour intervals inside it: max of `max`, min of `min`, sum of `rain`, mean of `cloud`.
  Show a day only when the intervals cover all of it. Far west of UTC, day 15 can end after run + 360 h, and then
  only days 11–14 are shown.

## Caching and updates
- `manifest.json` is served with `Cache-Control: public, max-age=300`; frames with
  `public, max-age=31536000, immutable`. A frame's bytes never change under its name.
- **On any 404 for a frame, fetch `manifest.json` again**: a new run was published and the old frames were
  replaced. Every frame of the current full run stays in each deploy, so a manifest a few hours old usually still
  works.
