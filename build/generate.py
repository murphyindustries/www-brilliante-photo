#!/usr/bin/env python3
"""
Static-site localization generator for brilliante.photo.

Reads:
  build/<template>.html    — one HTML template per page, with {{placeholders}}
  build/locales.json       — locale registry (order, paths, lang/dir, native names)
  i18n/<code>.json         — homepage translations, one flat file per locale;
                             also the SHARED base strings for every other page
                             (chrome: nav/cta/footer/consent/langPicker)
  i18n/<page>/<code>.json  — page-specific translations, overlaid on the base

Writes (at the repo root):
  index.html                       — English homepage (locale with path "")
  <locale>/index.html              — localized homepages (es/, fr/, de/, …)
  classic-7/index.html             — English Classic 7 product page
  <locale>/classic-7/index.html    — localized Classic 7 pages
  sitemap.xml                      — all pages × locales with hreflang alternates,
                                     plus /privacy/

Placeholder syntax in the templates:
  {{key}}        HTML/attribute-escaped value (safe in text and attributes)
  {{{key}}}      raw value — injected verbatim (used for strings that contain markup)
  {{json:key}}   JSON-encoded value, including surrounding quotes (for the JSON-LD block)

Run:  python build/generate.py
"""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
I18N = ROOT / "i18n"

# ---------------------------------------------------------------------------
# Page registry. `subpath` is appended to the locale path ("" = the homepage);
# `i18n` names the per-page translation subdirectory overlaid on the base
# homepage strings (None = the base strings ARE the page's strings).
# `priority` = (default-locale, other-locales) sitemap priorities.
# ---------------------------------------------------------------------------
PAGES = [
    {"name": "home",      "template": "template.html",  "subpath": "",          "i18n": None,        "priority": ("1.0", "0.9")},
    {"name": "classic-7", "template": "classic-7.html", "subpath": "classic-7", "i18n": "classic-7", "priority": ("0.8", "0.7")},
]

PLACEHOLDER_RAW = re.compile(r"\{\{\{(.+?)\}\}\}")
PLACEHOLDER_JSON = re.compile(r"\{\{json:(.+?)\}\}")
PLACEHOLDER_ESC = re.compile(r"\{\{(.+?)\}\}")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def render(template: str, values: dict) -> str:
    """Resolve placeholders. Raw first, then json:, then escaped — so the more
    specific brace forms are consumed before the generic {{key}} pass."""

    def lookup(key: str) -> str:
        key = key.strip()
        if key not in values:
            raise KeyError(f"missing translation/placeholder: {key!r}")
        return values[key]

    out = PLACEHOLDER_RAW.sub(lambda m: str(lookup(m.group(1))), template)
    out = PLACEHOLDER_JSON.sub(
        lambda m: json.dumps(lookup(m.group(1)), ensure_ascii=False), out
    )
    out = PLACEHOLDER_ESC.sub(lambda m: html.escape(str(lookup(m.group(1))), quote=True), out)
    return out


def page_path(locale_path: str, subpath: str) -> str:
    """URL path of a page for a locale, without leading/trailing slashes.
    ('' , 'classic-7') -> 'classic-7';  ('es', '') -> 'es';  ('es','classic-7') -> 'es/classic-7'."""
    return "/".join(p for p in (locale_path, subpath) if p)


def url_for(base: str, path: str) -> str:
    """Absolute URL — for canonical, og:url, hreflang, sitemap (SEO needs absolute)."""
    return f"{base}/" if path == "" else f"{base}/{path}/"


def rel_for(path: str) -> str:
    """Root-relative URL — for in-page navigation (works on localhost and in prod)."""
    return "/" if path == "" else f"/{path}/"


def build_hreflangs(base: str, locales: list, subpath: str) -> str:
    """Alternates for ONE page across all locales, plus x-default → the English page."""
    lines = []
    for loc in locales:
        href = url_for(base, page_path(loc["path"], subpath))
        lines.append(f'<link rel="alternate" hreflang="{loc["lang"]}" href="{href}">')
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{url_for(base, page_path("", subpath))}">')
    return "\n".join(lines)


GLOBE_SVG = (
    '<svg class="globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9.2"/>'
    '<path d="M3 12h18"/><path d="M12 2.8c2.6 2.5 4 5.8 4 9.2s-1.4 6.7-4 9.2c-2.6-2.5-4-5.8-4-9.2s1.4-6.7 4-9.2z"/></svg>'
)
CHEV_SVG = (
    '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.4" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>'
)


def build_switcher(locales: list, current: dict, subpath: str, label: str) -> str:
    """A no-JS <details> language menu linking to THIS page in every locale. Every
    locale's links are present in the DOM (crawlable), current marked aria-current."""
    items = []
    for loc in locales:
        href = rel_for(page_path(loc["path"], subpath))
        is_current = loc["code"] == current["code"]
        native = html.escape(loc["native"])
        sub = ""
        if loc["native"] != loc["enName"]:
            sub = f'<span class="en">{html.escape(loc["enName"])}</span>'
        attrs = f'href="{href}" hreflang="{loc["lang"]}" lang="{loc["lang"]}"'
        if is_current:
            attrs += ' aria-current="page"'
        items.append(f"    <a {attrs}>{native}{sub}</a>")
    menu = "\n".join(items)
    aria = html.escape(f'{label}: {current["native"]}', quote=True)
    cur_native = html.escape(current["native"])
    return (
        '<details class="langpicker">\n'
        f'  <summary aria-label="{aria}">{GLOBE_SVG}<span class="cur">{cur_native}</span>{CHEV_SVG}</summary>\n'
        '  <div class="langmenu">\n'
        f"{menu}\n"
        "  </div>\n"
        "</details>"
    )


def build_sitemap(base: str, locales: list, lastmod: str) -> str:
    urls = []
    for page in PAGES:
        alt_lines = []
        for loc in locales:
            alt_lines.append(
                f'    <xhtml:link rel="alternate" hreflang="{loc["lang"]}" href="{url_for(base, page_path(loc["path"], page["subpath"]))}"/>'
            )
        alt_lines.append(
            f'    <xhtml:link rel="alternate" hreflang="x-default" href="{url_for(base, page_path("", page["subpath"]))}"/>'
        )
        alternates = "\n".join(alt_lines)

        for loc in locales:
            priority = page["priority"][0] if loc["path"] == "" else page["priority"][1]
            urls.append(
                "  <url>\n"
                f"    <loc>{url_for(base, page_path(loc['path'], page['subpath']))}</loc>\n"
                f"{alternates}\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                "    <changefreq>monthly</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                "  </url>"
            )
    # Privacy policy is English-only for now.
    urls.append(
        "  <url>\n"
        f"    <loc>{base}/privacy/</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        "    <changefreq>yearly</changefreq>\n"
        "    <priority>0.3</priority>\n"
        "  </url>"
    )
    body = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def main() -> int:
    cfg = load_json(BUILD / "locales.json")
    base = cfg["base"].rstrip("/")
    lastmod = cfg["lastmod"]
    locales = cfg["locales"]

    written = []
    for page in PAGES:
        template = (BUILD / page["template"]).read_text(encoding="utf-8")
        hreflangs = build_hreflangs(base, locales, page["subpath"])

        # Key-set parity within the page: every locale must define exactly the
        # keys the English file does (a missing key is a missing translation).
        en_keys = None

        for loc in locales:
            strings_path = I18N / f"{loc['code']}.json"
            if not strings_path.exists():
                print(f"  ! skipping {loc['code']}: missing {strings_path.relative_to(ROOT)}", file=sys.stderr)
                return 1
            values = load_json(strings_path)  # base/shared strings (homepage chrome)
            page_keys = set(values)
            if page["i18n"]:
                overlay_path = I18N / page["i18n"] / f"{loc['code']}.json"
                if not overlay_path.exists():
                    print(f"  ! {page['name']}: missing {overlay_path.relative_to(ROOT)}", file=sys.stderr)
                    return 1
                overlay = load_json(overlay_path)
                page_keys = set(overlay)
                values.update(overlay)
            if en_keys is None:
                en_keys = page_keys
            elif page_keys != en_keys:
                diff = sorted(page_keys ^ en_keys)
                print(f"  ! {page['name']}/{loc['code']}: key set differs from en: {diff}", file=sys.stderr)
                return 1

            path = page_path(loc["path"], page["subpath"])
            values["lang"] = loc["lang"]
            values["dir"] = loc["dir"]
            values["ogLocale"] = loc["ogLocale"]
            values["canonical"] = url_for(base, path)
            values["ogUrl"] = url_for(base, path)
            values["hreflangs"] = hreflangs
            values["langSwitcher"] = build_switcher(
                locales, loc, page["subpath"], values.get("langPicker.label", "Language")
            )
            # Cross-page navigation (localized, root-relative).
            values["homeHref"] = rel_for(page_path(loc["path"], ""))
            values["classic7Href"] = rel_for(page_path(loc["path"], "classic-7"))

            rendered = render(template, values)

            out_path = ROOT / path / "index.html" if path else ROOT / "index.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8", newline="\n")
            written.append(out_path.relative_to(ROOT).as_posix())

    sitemap = build_sitemap(base, locales, lastmod)
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8", newline="\n")
    written.append("sitemap.xml")

    print(f"Generated {len(written)} files:")
    for w in written:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
