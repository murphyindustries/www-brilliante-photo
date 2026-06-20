#!/usr/bin/env python3
"""
Static-site localization generator for brilliante.photo.

Reads:
  build/template.html      — the homepage HTML, with {{placeholders}}
  build/locales.json       — locale registry (order, paths, lang/dir, native names)
  i18n/<code>.json         — one flat translation file per locale

Writes (at the repo root):
  index.html               — English homepage (locale with path "")
  <path>/index.html        — one localized homepage per other locale
  sitemap.xml              — homepage URLs (with hreflang alternates) + /privacy/

Placeholder syntax in the template:
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


def url_for(base: str, path: str) -> str:
    """Absolute URL — for canonical, og:url, hreflang, sitemap (SEO needs absolute)."""
    return f"{base}/" if path == "" else f"{base}/{path}/"


def rel_for(path: str) -> str:
    """Root-relative URL — for in-page navigation (works on localhost and in prod)."""
    return "/" if path == "" else f"/{path}/"


def build_hreflangs(base: str, locales: list) -> str:
    """The same alternates block is embedded on every localized page: one entry per
    locale plus x-default pointing at the English root."""
    lines = []
    for loc in locales:
        href = url_for(base, loc["path"])
        lines.append(f'<link rel="alternate" hreflang="{loc["lang"]}" href="{href}">')
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{url_for(base, "")}">')
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


def build_switcher(base: str, locales: list, current: dict, label: str) -> str:
    """A no-JS <details> language menu. Every locale's links are present in the DOM
    (crawlable), with the current locale marked aria-current."""
    items = []
    for loc in locales:
        href = rel_for(loc["path"])
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
    alt_lines = []
    for loc in locales:
        alt_lines.append(
            f'    <xhtml:link rel="alternate" hreflang="{loc["lang"]}" href="{url_for(base, loc["path"])}"/>'
        )
    alt_lines.append(
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{url_for(base, "")}"/>'
    )
    alternates = "\n".join(alt_lines)

    urls = []
    for loc in locales:
        priority = "1.0" if loc["path"] == "" else "0.9"
        urls.append(
            "  <url>\n"
            f"    <loc>{url_for(base, loc['path'])}</loc>\n"
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
    template = (BUILD / "template.html").read_text(encoding="utf-8")

    hreflangs = build_hreflangs(base, locales)

    written = []
    for loc in locales:
        strings_path = I18N / f"{loc['code']}.json"
        if not strings_path.exists():
            print(f"  ! skipping {loc['code']}: missing {strings_path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        strings = load_json(strings_path)

        values = dict(strings)
        values["lang"] = loc["lang"]
        values["dir"] = loc["dir"]
        values["ogLocale"] = loc["ogLocale"]
        values["canonical"] = url_for(base, loc["path"])
        values["ogUrl"] = url_for(base, loc["path"])
        values["hreflangs"] = hreflangs
        values["langSwitcher"] = build_switcher(
            base, locales, loc, strings.get("langPicker.label", "Language")
        )

        rendered = render(template, values)

        out_path = ROOT / "index.html" if loc["path"] == "" else ROOT / loc["path"] / "index.html"
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
