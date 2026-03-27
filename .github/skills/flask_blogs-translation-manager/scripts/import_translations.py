"""
import_translations.py
----------------------
Part of the flask_blogs-translation-manager skill.

Imports a completed translation JSON file (produced by extract_untranslated.py
and filled in by an LLM) back into translations.db.

Usage (from flask_blogs/flask_planhead/):
    python ../../.github/skills/flask_blogs-translation-manager/scripts/import_translations.py \
        --file /tmp/fr_messages_translated.json [--dry-run]

Expected JSON format (same as extract_untranslated.py output, with msgstr filled):
    {
      "locale": "fr",
      "domain": "messages",
      "rows": [
        {"id": 123, "msgid": "Hello", "msgstr": "Bonjour", "msgstr_plural": null},
        ...
      ]
    }

After import, run export_sqlite_to_mo.py to regenerate .mo files.
"""

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "flask_blogs" / "flask_planhead" / "app" / "translations.db"


def import_translations(file_path: str, dry_run: bool = False):
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = data["rows"]
    locale = data.get("locale", "?")
    domain = data.get("domain", "?")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    updated = 0
    skipped = 0

    for row in rows:
        msgstr = row.get("msgstr", "")
        msgstr_plural = row.get("msgstr_plural")
        row_id = row["id"]

        if not msgstr:
            skipped += 1
            continue

        if not dry_run:
            cur.execute(
                "UPDATE translations SET msgstr=?, msgstr_plural=?, updated_at=datetime('now') WHERE id=?",
                (msgstr, msgstr_plural, row_id),
            )
        updated += 1

    if not dry_run:
        conn.commit()
    conn.close()

    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}locale={locale} domain={domain}: {updated} updated, {skipped} skipped (empty msgstr)")
    if dry_run:
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to translated JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    import_translations(args.file, args.dry_run)
