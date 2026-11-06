# ECMWF open data: reference for this job

Checked 2026-11-06 against ECMWF's own pages and real files. Code: `y4cdata/runs.py`, `y4cdata/index.py`,
`y4cdata/fetch.py`, `y4cdata/grib.py`.

## Sources
- Overview, streams, steps: https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS
- File naming: https://confluence.ecmwf.int/spaces/DAC/pages/738041084/ECMWF+open+data+file+naming+and+formats
- Getting the data (index files, byte ranges): https://confluence.ecmwf.int/spaces/DAC/pages/738041083/ECMWF+open+data+getting+the+data
- Licence: https://www.ecmwf.int/en/forecasts/datasets/open-data (CC BY 4.0, commercial use and redistribution allowed)
- AWS mirror: https://registry.opendata.aws/ecmwf-forecasts/ (same CC BY 4.0 licence)

## Hosts (`fetch.ROOTS`, tried in this order)
| Root | Notes |
|---|---|
| `https://data.ecmwf.int/forecasts` | ECMWF's portal. Limited to 500–2000 simultaneous connections across all users. Its TLS chain ends at *HARICA TLS RSA Root CA 2021*; Python on the owner's laptop cannot verify that (the root is not in its Windows store), so there every request falls straight through to the mirror. |
| `https://d2zvc0wgha4k2l.cloudfront.net` | The AWS mirror's CloudFront distribution, listed on the registry page. Serves byte ranges (206). |
| `https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com` | The S3 bucket itself. On 2026-11-06 most requests got `503 SlowDown`, so it is last. |

On 2026-11-06 around 09:30 UTC both mirror hosts answered `503 SlowDown` to every request for minutes on end
(CloudFront: "Error from cloudfront" with the S3 SlowDown body). Meanwhile the portal served all 390 requests of a
full build (65 steps: one index and five fields each) in 469 s. The mirror is a fallback, not a second main
source.

**Running the job on the owner's laptop:** Python there cannot verify the portal (see above), so point it at
Mozilla's root list for that one process. Node ships the same list as Linux and certifi:
`node -e "process.stdout.write(require('tls').rootCertificates.join('\n')+'\n')" > roots.pem`, then set
`SSL_CERT_FILE=roots.pem`. No system setting changes. CI needs none of this.

## Paths
`{root}/{yyyymmdd}/{HH}z/ifs/0p25/oper/{yyyymmdd}{HH}0000-{step}h-oper-fc.{grib2|index}`

Example: `20261106/00z/ifs/0p25/oper/20261106000000-24h-oper-fc.index`.

## Runs and steps (stream `oper`, type `fc`)
| Run (UTC) | Steps |
|---|---|
| 00, 12 | 0–144 h by 3, 150–360 h by 6 (85 files) |
| 06, 18 | 0–90 h by 3 (31 files) |

The 00 UTC run of 2026-11-06 had every file's `Last-Modified` at 07:34 UTC. A run counts as complete only when its
last step's `.index` exists (`runs.choose_runs`).

## Index files
Swap `.grib2` for `.index`. One JSON object per line, one per GRIB message:

```json
{"domain": "g", "date": "20261106", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "24", "levtype": "sfc", "param": "2t", "_offset": 23512533, "_length": 319069}
```

Fetch one field with `Range: bytes=_offset-(_offset+_length-1)`. Offsets change every run. A whole 0.25° step file
is about 100 MB with 191–194 messages; the five fields this job needs are about 2.7 MB per step.

## Fields used (`levtype=sfc`)
| Param | Meaning | Units | Bits per value (2026-11-06) |
|---|---|---|---|
| `10u`, `10v` | 10 m wind components | m/s | 11 |
| `2t` | 2 m temperature | K | 9 |
| `tp` | total precipitation, accumulated from step 0 | m | 12 |
| `tcc` | total cloud cover | 0–1 | 7 |
| `mx2t6`, `mn2t6` | highest / lowest 2 m temperature in the 6 hours before the step; present only on the 6-hourly steps (150 h on; seen at 150 h in the 2026-11-06 00 UTC index) | K | — |

The days 11–15 tiles use `mx2t6`, `mn2t6`, `tp` and `tcc` at steps 216–360 (and `tp` at 210); see
`docs/manifest.md`.

Also present and unused for now: `msl` (pressure), `2d` (dewpoint, for humidity), `tprate`, `ptype`, `100u/100v`.

## Encoding
GRIB edition 2, data representation template 5.42 (CCSDS), which needs ecCodes (≥ 2.42.0 recommended by ECMWF;
this repo pins 2.50.0). Grid template 3.0: 1440 × 721, first point lat 90 / lon 180, last lon 179.75, scanning west
to east and north to south. Row 0 is 90° N and column 0 is 180° W.

## Errors and how the job handles them (`fetch.Source.get`)
| Answer | Handling |
|---|---|
| 200 / 206 | Used. With a Range, the body must be exactly the asked length or it counts as a failure. |
| 404 | Next root at once (that host does not have the file yet). |
| 429, 5xx (incl. S3 `SlowDown`) | Retried on the same root after 2 s, then 8 s; then the next root. |
| TLS certificate not verifiable | Next root at once (a retry cannot fix it). |
| Connection error, timeout | Retried like a 5xx. |
| Every root failed | `FetchError` naming the last answer; the run fails and the workflow opens an issue. |

## Attribution
"Contains modified ECMWF open data (CC BY 4.0), changed by Your4cast."
