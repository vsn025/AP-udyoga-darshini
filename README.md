# AP Udyoga Darshini — self-hosted AP government jobs aggregator

A fully independent system. No AI, no third-party services at runtime:
a Python crawler visits official government websites on a schedule,
saves results to a JSON file, and a static site displays them.

```
scraper/sources.py    all 34 sources: 26 district collectorates (S3WaaS),
                      APPSC / SLPRB / DSC / HMFW, UPSC / SSC / RRB / IBPS
scraper/scrape.py     crawler: parse -> dedup -> merge history -> health report
docs/index.html       the website (works offline against the JSON)
docs/data/jobs.json   the database (regenerated every crawl)
.github/workflows/crawl.yml   runs the crawler every 6 hours, free
```

## Deploy in ~10 minutes (free, no server)

1. Create a new **public** GitHub repository and upload this folder's contents
   (keep the folder structure, including the hidden `.github` folder).
2. Repo → **Settings → Pages** → Source: *Deploy from a branch* →
   Branch `main`, folder `/docs` → Save.
3. Repo → **Actions** tab → enable workflows → open *"Crawl AP government job
   notifications"* → **Run workflow** (first crawl takes ~3–5 min).
4. Your site is live at `https://<username>.github.io/<repo>/` and refreshes
   itself every 6 hours from then on. Nothing else to maintain.

## Run locally

```bash
pip install -r requirements.txt
python scraper/scrape.py          # crawls all sources -> docs/data/jobs.json
python -m http.server -d docs     # open http://localhost:8000
```

## Honest accuracy notes

* **Coverage is visible, never assumed.** Every crawl records per-source
  health (ok / empty / unreachable / portal) and the site shows it under
  "Source coverage". If a district site is down, you see a red dot — the
  gap is never silent.
* **SSC and RRB are JavaScript portals** that cannot be scraped with plain
  HTTP; they are surfaced as direct portal links. To scrape them too, add a
  Playwright-based parser (`pip install playwright`) — the source registry
  already supports adding new `kind`s.
* **Deadlines are extracted, never guessed.** A last date is shown only when
  the notice text states one; otherwise the field is blank and the reader is
  sent to the official PDF.
* No aggregator can be literally 100% complete — some notices exist only as
  scanned PDFs or physical notice boards. This design gets you the maximum
  that automated collection honestly can, and tells you exactly what it
  covered each run.

## Extending

Add any new source in `scraper/sources.py` (one dict). S3WaaS sites need no
code; other server-rendered sites are handled by the generic parser; mark
JS-heavy ones as `"kind": "portal"` until you add a Playwright parser.
