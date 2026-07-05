# Site localization

Each page is generated from one template + per-locale translation files, so a
design change is made once (in the template) and propagates to every language.
The generator has a **page registry** (`PAGES` in `generate.py`): the homepage
and the Classic 7 product page, each localized into every registered locale.

## Layout

```
build/template.html     homepage template with {{placeholders}}  (edit design/markup here)
build/classic-7.html    /classic-7/ product-page template (Classic 7's own Aero-glass identity)
build/locales.json      locale registry: order, URL paths, lang/dir, native names
build/generate.py       the generator (page registry lives at the top)
i18n/<code>.json        homepage translations — ALSO the shared base for other pages
                        (chrome strings: nav/cta/footer/consent/langPicker)
i18n/classic-7/<code>.json  Classic 7 page translations, overlaid on the base
build/import_classic7_i18n.py  regenerates i18n/classic-7/ from the Store listing CSV
```

Generated at the repo root (do **not** hand-edit these — they are overwritten):

```
index.html               English homepage   (the locale whose path is "")
<path>/index.html        one localized homepage per other locale (es/, fr/, de/, …)
classic-7/index.html     English Classic 7 page
<path>/classic-7/index.html  localized Classic 7 pages
sitemap.xml              all pages × locales with hreflang alternates + /privacy/
```

The privacy policy (`privacy/index.html`) is **English-only for now** and is not
generated; it's maintained by hand.

## Regenerate

```sh
python build/generate.py
```

No dependencies — standard-library Python 3 only. Run it after editing the template,
any `i18n/*.json`, or `locales.json`, and commit the regenerated output.

## Placeholders

| Syntax            | Behavior                                              |
|-------------------|-------------------------------------------------------|
| `{{key}}`         | HTML/attribute-escaped value (safe in text and attrs) |
| `{{{key}}}`       | raw value — for strings that contain markup           |
| `{{json:key}}`    | JSON-encoded (with quotes) — used in the JSON-LD block |

Keys ending in `_html` hold markup (highlight `<span class="hl">`, `<em>`, `<b>`,
`&nbsp;`) and are referenced with the raw `{{{ }}}` form. Everything else is plain
text. The generator also injects computed values: `lang`, `dir`, `ogLocale`,
`canonical`, `ogUrl`, `hreflangs`, `langSwitcher`.

Within each page, every locale file must define the **same key set** as that page's
`en.json` — the generator now enforces this itself and fails loudly on any diff
(a missing key is a missing translation). Page templates may also reference the
shared base keys (e.g. `{{cta.getItFrom}}`) and the generator-injected cross-page
paths `homeHref` / `classic7Href`.

## The Classic 7 page (`/classic-7/`)

Its copy is the **Microsoft Store listing**, verbatim — the CSV at
`brilliante-marketing/store/classic-photo-viewer/store-listing.csv` is the source of
truth for all 30 locales. Don't edit `i18n/classic-7/*.json` by hand; update the store
CSV and re-run:

```sh
python build/import_classic7_i18n.py   # parses the CSV (incl. the Description blocks)
python build/generate.py
```

The importer also maintains the homepage's footer-only Classic 7 link text
(`footer.classic7` in `i18n/<code>.json` = the localized product title). The page
deliberately uses Classic 7's **Aero-glass identity** (sky gradient, photo-frame icon
`/classic7-icon.svg` + `/classic7-icon-256.png`, Segoe UI) rather than the Brilliante
navy+gem — the only suite-branded element is the Brilliante cross-promo panel
(the funnel: Classic 7 → Brilliante, never the reverse). Store links carry the
registered campaign IDs `web-classic7-hero`, `web-classic7-closing`, and
`web-viewer-classic7` (see `brilliante-marketing/store/CAMPAIGNS.md`).

## Translation terminology

Brand and feature terms are kept consistent with the **Microsoft Store listing** and
the **in-app resources**, not translated ad hoc:

- Source of truth for store copy: `uhdr-viewer/store/store-listing.csv`
  (per-locale `Title`, `ShortTitle`, `Feature1…`). `ShortTitle` → `app.name`;
  `Title` minus the brand → the `hero.kicker` ("HDR Photo Viewer").
- Source of truth for in-app strings: `uhdr-viewer/projects/brilliante-viewer/Strings/<locale>/Resources.resw`.
- Vendor feature names follow each vendor's official localized guides — e.g.
  **Motion Photo** and **Top Shot** stay English in some locales and are localized in
  others (ja モーションフォト, zh-Hans 动态相片, ko 모션 포토 / 베스트 포토). See the
  "Conventions & history" notes in `uhdr-viewer/store/README.md`.
- Format/tech tokens are left in English everywhere: HDR, Ultra HDR, HEIC, AVIF,
  JPEG XR, SDR, PNG, EXIF, GPS, Windows, Android, Microsoft Store, Brilliante.

## Analytics & cookie consent

Google Analytics 4 with **Consent Mode v2**, all in one static file: **`/analytics.js`**.

- **Set the Measurement ID in one place** — the `GA_ID` constant at the top of
  `analytics.js` (looks like `G-XXXXXXXXXX`). No rebuild needed; it's a static file
  referenced by every page (`<script src="/analytics.js">`), including the privacy page.
- While the ID is the placeholder (`G-XXXXXXXXXX`), GA is **not** loaded and the cookie
  banner stays hidden — safe to deploy without tracking anything.
- Consent defaults to **denied**. The banner flips `analytics_storage` to `granted`
  only on Accept; the choice is stored in `localStorage` (`brilliante-analytics-consent`)
  so returning visitors aren't asked again. Decline stores `denied`.
- The banner **markup** lives in the homepage template (localized via the `consent.*`
  keys in `i18n/`) and inline in `privacy/index.html` (English). The banner **behavior**
  (show/hide, wiring the buttons) is all in `analytics.js`.

## Adding a locale

All 30 of the app/store locales are now live. To add another:

1. Append an entry to `build/locales.json` (`code`, `path`, `lang`, `dir`,
   `ogLocale`, `native`, `enName`). Use `dir: "rtl"` for right-to-left scripts.
2. Create `i18n/<code>.json` — copy `i18n/en.json` and translate the values, anchoring
   brand/feature terms to the store CSV row for that locale (see above).
3. Run `python build/import_classic7_i18n.py` to produce `i18n/classic-7/<code>.json`
   (the locale must exist in the Classic 7 store CSV).
4. `python build/generate.py` and commit.

RTL (`dir: "rtl"`, e.g. ar/he) works out of the box: `<html dir>` flips the page, the
header/footer use flexbox, and the language menu uses logical properties
(`inset-inline-end`), so no per-locale CSS is needed. The before/after demo widget stays
visually LTR by design (it's a direction-neutral image comparison).

## Local preview

```sh
python -m http.server 8765    # then open http://localhost:8765/
```

(`.claude/launch.json` defines this as the `static` server for the preview panel.)
