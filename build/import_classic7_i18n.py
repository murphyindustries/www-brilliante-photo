#!/usr/bin/env python3
"""
Import the Classic 7 Photo Viewer page strings from the Microsoft Store listing CSV.

The /classic-7/ product page is localized from the SAME copy as the Store listing
(brilliante-marketing/store/classic-photo-viewer/store-listing.csv) — the CSV is the
source of truth; this importer regenerates i18n/classic-7/<code>.json from it. Run it
again whenever the store copy changes, then `python build/generate.py`.

What it does per site locale:
  - maps the site locale code to the CSV column (site `pt` = CSV `pt-pt`)
  - parses the Description field into its five blocks (lede, story paragraph,
    "Simple and free" section, "Opens what Windows already knows" section, and the
    Microsoft non-affiliation note) — the structure is identical in every locale,
    and the parse FAILS LOUDLY if a locale deviates
  - pulls the Brilliante cross-promo strings (bv.*) from the locale's existing
    homepage i18n file, so the promo panel reuses already-reviewed translations
  - writes i18n/classic-7/<code>.json
  - inserts a `footer.classic7` key (the localized product title) into the HOMEPAGE
    i18n file if missing — the homepage's footer-only Classic 7 mention

Usage:
  python build/import_classic7_i18n.py [--csv <path-to-store-listing.csv>]
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "i18n"
OUT = I18N / "classic-7"

DEFAULT_CSV = (
    ROOT.parent / "brilliante-marketing" / "store" / "classic-photo-viewer" / "store-listing.csv"
)

# site locale code -> store CSV column (identity lowercase unless listed)
CSV_COLUMN = {"en": "en-us", "pt": "pt-pt"}


def csv_col(site_code: str) -> str:
    return CSV_COLUMN.get(site_code, site_code.lower())


def load_listing(path: Path) -> dict:
    """{field name: {csv column: value}} from the listing CSV."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = {}
    for r in rows:
        fields[r["Field"]] = r
    return fields


BULLET = re.compile(r"^\s*•\s*(.+?)\s*$")


def parse_description(text: str, locale: str) -> dict:
    """Split the Store Description into the page's content blocks.

    Expected shape (all 31 locales follow it):
      [0] lede paragraph          [1] story paragraph
      [2] section: header + 4 bullets      [3] section: header + 4 bullets
      [4] the not-affiliated-with-Microsoft note
    """
    text = text.replace("\r\n", "\n").strip()
    blocks = re.split(r"\n\s*\n", text)
    if len(blocks) != 5:
        raise ValueError(f"{locale}: expected 5 description blocks, got {len(blocks)}")

    def section(block: str, which: str):
        lines = block.split("\n")
        header, bullets = lines[0].strip(), [m.group(1) for m in map(BULLET.match, lines[1:]) if m]
        if BULLET.match(lines[0]) or len(bullets) != len(lines) - 1 or len(bullets) != 4:
            raise ValueError(f"{locale}: malformed {which} section: {block[:80]!r}")
        return header, bullets

    for i, b in enumerate(blocks[:2] + blocks[4:]):
        if "•" in b:
            raise ValueError(f"{locale}: unexpected bullets in prose block {i}: {b[:80]!r}")
    h1, b1 = section(blocks[2], "simple-and-free")
    h2, b2 = section(blocks[3], "formats")
    return {
        "lede": blocks[0].strip(),
        "story": blocks[1].strip(),
        "sec1": (h1, b1),
        "sec2": (h2, b2),
        "note": blocks[4].strip(),
    }


def build_strings(fields: dict, col: str, home: dict) -> dict:
    def field(name: str) -> str:
        v = fields[name].get(col, "").strip()
        if not v:
            raise ValueError(f"missing {name} for CSV column {col}")
        return v

    title = field("Title")
    short = field("ShortDescription")
    d = parse_description(field("Description"), col)

    out = {
        "meta.title": f"{title} — {field('Feature1')}",
        "meta.description": short,
        "meta.ogDescription": short,
        "meta.jsonldDescription": short,
        "app.name": title,
        "hero.kicker": field("Feature1"),
        "hero.lede": d["lede"],
        "cta.meta": field("Feature5"),
        "story.para": d["story"],
        "shot.alt": field("Feature4"),
        "sec1.head": d["sec1"][0],
        "sec2.head": d["sec2"][0],
        "note.text": d["note"],
        # Brilliante cross-promo panel — reuse the homepage's reviewed translations.
        "bv.name": home["app.name"],
        "bv.kicker": home["hero.kicker"],
        "bv.head_html": home["features.head_html"],
        "bv.body": home["meta.ogDescription"],
    }
    for i, b in enumerate(d["sec1"][1], 1):
        out[f"sec1.b{i}"] = b
    for i, b in enumerate(d["sec2"][1], 1):
        out[f"sec2.b{i}"] = b
    return out


FOOTER_KEY = "footer.classic7"


def inject_footer_key(home_path: Path, title: str) -> bool:
    """Textually insert footer.classic7 after footer.support, preserving the file's
    hand formatting (json.dump would destroy the blank-line grouping)."""
    src = home_path.read_text(encoding="utf-8")
    if f'"{FOOTER_KEY}"' in src:
        return False
    m = re.search(r'^([ \t]*)"footer\.support":.*$', src, re.M)
    if not m:
        raise ValueError(f"{home_path.name}: no footer.support line to anchor on")
    line = f'{m.group(1)}"{FOOTER_KEY}": {json.dumps(title, ensure_ascii=False)},'
    src = src[: m.end()] + "\n" + line + src[m.end() :]
    home_path.write_text(src, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = ap.parse_args()

    fields = load_listing(args.csv)
    locales = json.loads((ROOT / "build" / "locales.json").read_text(encoding="utf-8"))["locales"]
    OUT.mkdir(parents=True, exist_ok=True)

    for loc in locales:
        code = loc["code"]
        home_path = I18N / f"{code}.json"
        home = json.loads(home_path.read_text(encoding="utf-8"))
        strings = build_strings(fields, csv_col(code), home)

        out_path = OUT / f"{code}.json"
        out_path.write_text(
            json.dumps(strings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        added = inject_footer_key(home_path, strings["app.name"])
        print(f"  {code:8s} -> {out_path.relative_to(ROOT).as_posix()}"
              + ("  (+ footer.classic7)" if added else ""))
    print(f"Imported {len(locales)} locales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
