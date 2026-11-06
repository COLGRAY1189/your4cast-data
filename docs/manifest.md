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

## Caching and updates
- `manifest.json` is served with `Cache-Control: public, max-age=300`; frames with
  `public, max-age=31536000, immutable`. A frame's bytes never change under its name.
- **On any 404 for a frame, fetch `manifest.json` again**: a new run was published and the old frames were
  replaced. Every frame of the current full run stays in each deploy, so a manifest a few hours old usually still
  works.
