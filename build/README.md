# Site localization

The homepage is generated from one template + per-locale translation files, so a
design change is made once (in the template) and propagates to every language.

## Layout

```
build/template.html     HTML template with {{placeholders}}  (edit design/markup here)
build/locales.json      locale registry: order, URL paths, lang/dir, native names
build/generate.py       the generator
i18n/<code>.json        one flat translation file per locale  (edit copy here)
```

Generated at the repo root (do **not** hand-edit these — they are overwritten):

```
index.html              English homepage   (the locale whose path is "")
<path>/index.html        one localized homepage per other locale (es/, fr/, de/, …)
sitemap.xml              homepage URLs with hreflang alternates + /privacy/
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

Every `i18n/*.json` must define the **same key set** as `i18n/en.json`, or generation
fails loudly (a missing key is a missing translation). Quick parity check:

```sh
python -c "import json,glob; en=set(json.load(open('i18n/en.json',encoding='utf-8'))); [print(p, sorted(set(json.load(open(p,encoding='utf-8')))^en)) for p in glob.glob('i18n/*.json')]"
```

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

## Adding a locale

All 30 of the app/store locales are now live. To add another:

1. Append an entry to `build/locales.json` (`code`, `path`, `lang`, `dir`,
   `ogLocale`, `native`, `enName`). Use `dir: "rtl"` for right-to-left scripts.
2. Create `i18n/<code>.json` — copy `i18n/en.json` and translate the values, anchoring
   brand/feature terms to the store CSV row for that locale (see above).
3. `python build/generate.py` and commit.

RTL (`dir: "rtl"`, e.g. ar/he) works out of the box: `<html dir>` flips the page, the
header/footer use flexbox, and the language menu uses logical properties
(`inset-inline-end`), so no per-locale CSS is needed. The before/after demo widget stays
visually LTR by design (it's a direction-neutral image comparison).

## Local preview

```sh
python -m http.server 8765    # then open http://localhost:8765/
```

(`.claude/launch.json` defines this as the `static` server for the preview panel.)
