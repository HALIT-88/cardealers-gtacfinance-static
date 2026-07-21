# cardealers.gtacfinance.com — static mirror

A faithful, self-contained static clone of **https://cardealers.gtacfinance.com/**
(a WordPress + Elementor site), built for hosting on GitHub Pages.

## What it is
- All 20 pages (home + 19 sub-pages) mirrored with their exact Elementor markup,
  styles, scripts, images and fonts localized under `docs/assets/`.
- External embeds kept **verbatim** (real embed code, same destination servers):
  - JotForm — Book a Call (`252295031984158`) and Dealer Registration (`252534206128148`)
  - Replit calculators — Declined-Leads & Leads-ROI
  - Google Maps — Contact page
- Every internal link rewritten to a relative path; every external link/href
  (book pages, socials, gtacfinance.com, gtacfoundation.org) preserved exactly.
- Images de-lazied into the markup (native `loading="lazy"`), deduped by md5.

## Build
```bash
python3 build_site.py all      # crawl + download assets + rewrite -> docs/
python3 build_site.py crawl     # just fetch raw HTML  -> raw/
python3 build_site.py build     # just (re)build       -> docs/
```
Requires Python 3 + `beautifulsoup4`. `manifest.json` records asset counts and
any real duplicate-content groups.

## Hosting
GitHub Pages is served from the `main` branch `/docs` folder. `docs/.nojekyll`
disables Jekyll so the `wp-content` asset tree is served as-is.
