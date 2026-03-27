"""
extract_untranslated.py
-----------------------
Part of the flask_blogs-translation-manager skill.

Extracts all untranslated (or wrongly-translated) strings for a given locale
and domain, writing them to a JSON file for LLM batch translation.

Usage (from flask_blogs/flask_planhead/):
    python ../../.github/skills/flask_blogs-translation-manager/scripts/extract_untranslated.py \
        --locale fr --domain messages --out /tmp/fr_messages.json

    # To extract ALL domains at once:
    python ../../.github/skills/flask_blogs-translation-manager/scripts/extract_untranslated.py \
        --locale fr --out /tmp/fr_all.json

Output JSON format:
    {
      "locale": "fr",
      "domain": "messages",
      "rows": [
        {"id": 123, "msgid": "Hello", "msgid_plural": null, "msgstr": ""},
        ...
      ]
    }
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "flask_blogs" / "flask_planhead" / "app" / "translations.db"


def extract(locale: str, domain: str | None, out_path: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if domain:
        rows = cur.execute(
            "SELECT id, domain, msgid, msgid_plural, msgstr, msgstr_plural "
            "FROM translations WHERE locale=? AND domain=? ORDER BY id",
            (locale, domain),
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT id, domain, msgid, msgid_plural, msgstr, msgstr_plural "
            "FROM translations WHERE locale=? ORDER BY domain, id",
            (locale,),
        ).fetchall()

    conn.close()

    data = {
        "locale": locale,
        "domain": domain or "ALL",
        "rows": [
            {
                "id": r["id"],
                "domain": r["domain"],
                "msgid": r["msgid"],
                "msgid_plural": r["msgid_plural"],
                "msgstr": r["msgstr"],
                "msgstr_plural": r["msgstr_plural"],
            }
            for r in rows
        ],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(data['rows'])} rows → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", required=True, help="e.g. fr, es, de")
    parser.add_argument("--domain", default=None, help="e.g. messages (omit for all)")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    args = parser.parse_args()
    extract(args.locale, args.domain, args.out)
