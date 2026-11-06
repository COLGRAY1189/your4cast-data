# Cloudflare Pages: reference for this job

Checked 2026-11-06 against Cloudflare's docs and terms. Used by `.github/workflows/build.yml`; the site layout comes
from `y4cdata/build.py`.

## Sources
- Direct Upload with CI: https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/
- Wrangler `pages` commands: https://developers.cloudflare.com/workers/wrangler/commands/pages/
- Limits: https://developers.cloudflare.com/pages/platform/limits/
- Pricing (static requests): https://developers.cloudflare.com/pages/functions/pricing/
- `_headers`: https://developers.cloudflare.com/pages/configuration/headers/
- Terms: https://www.cloudflare.com/service-specific-terms-developer-platform/ and
  https://www.cloudflare.com/service-specific-terms-application-services/

## How the job deploys
Wrangler 4.158.0 (pinned in the workflow), with two GitHub Actions secrets: `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`.

```
npx wrangler pages project list --json               # does the project exist?
npx wrangler pages project create your4cast-data --production-branch main
npx wrangler pages deploy site --project-name your4cast-data --branch main
```

The token is a custom token with the permission **Account → Cloudflare Pages → Edit** (Cloudflare's Direct Upload
guide). The live address is `https://<project>.pages.dev`; the workflow reads `manifest.json` there through the
repository variable `MANIFEST_URL`.

## Limits that matter (Free plan)
| Limit | Value | This job |
|---|---|---|
| Files per site | 20,000 | about 260 per run pair (4 layers × up to 96 steps), plus `manifest.json` and `_headers` |
| Size per file | 25 MiB | largest PNG about 0.73 MB (wind) |
| Builds per month | 500 | at most 4 deploys a day (one per new ECMWF run), about 120 a month |
| Static asset requests | "free and unlimited" on free and paid plans | everything served is static |
| `_headers` rules | 100 | 2 |

## `_headers`
```
/manifest.json
  Cache-Control: public, max-age=300
/frames/*
  Cache-Control: public, max-age=31536000, immutable
```
A splat (`*`) "will greedily match all characters" (Cloudflare's `_headers` docs), so `/frames/*` covers every
frame. Frame names contain their run and step, so their bytes never change.

## Terms (quoted 2026-11-06)
- Application Services, CDN: "Unless you are an Enterprise customer, Cloudflare offers specific Paid Services (e.g.,
  the Developer Platform, Images, and Stream) that you must use in order to serve video and other large files via
  the CDN." Pages belongs to the Developer Platform, which the clause names as the way to serve large files.
- Developer Platform: "Cloudflare may temporarily limit your storage and/or the number of requests you can make or
  receive using the Developer Platform if processing such requests would put an undue burden on the Cloudflare
  network". If that happens, R2 is the fallback named in the spec (10 GB free storage, no egress fees, 10 million
  reads a month; https://developers.cloudflare.com/r2/pricing/).
