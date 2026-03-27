"""
batch_translate.py
------------------
Part of the flask_blogs-translation-manager skill.

Orchestrates efficient LLM-assisted batch translation of all untranslated strings
for a locale. Processes one domain at a time, writing translated JSON files and
importing them into translations.db.

This script is intended to be called by the developer agent. It:
  1. Reads all rows for a domain from translations.db
  2. Formats them as a Python dict ready for the agent to fill translations inline
  3. Writes the completed dict back to the DB via import_translations.py

Usage: The developer agent should call this module's helpers directly, or use
extract_untranslated.py + import_translations.py as the two-step CLI workflow.

--- AGENT WORKFLOW (for developer agent) ---

Step 1: Find all domains needing translation for a locale
    python batch_translate.py --locale fr --status

Step 2: For each domain, generate a translated Python dict and call:
    python batch_translate.py --locale fr --domain <domain> --translations '{...}'
    where --translations is a JSON string: {"<msgid>": "<translated_msgstr>", ...}

Step 3: After all domains done:
    cd flask_blogs/flask_planhead && python -m scripts.export_sqlite_to_mo
"""

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[4] / "flask_blogs" / "flask_planhead" / "app" / "translations.db"


def status(locale: str):
    """Print remaining untranslated count per domain."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT domain, COUNT(*) as total, "
        "SUM(CASE WHEN msgstr='' OR msgstr IS NULL THEN 1 ELSE 0 END) as empty "
        "FROM translations WHERE locale=? GROUP BY domain ORDER BY empty DESC",
        (locale,),
    ).fetchall()
    conn.close()
    total_empty = sum(r[2] for r in rows)
    print(f"Locale: {locale} — {total_empty} untranslated strings remaining\n")
    print(f"{'Domain':<40} {'Total':>6} {'Empty':>6}")
    print("-" * 55)
    for domain, total, empty in rows:
        marker = " OK" if empty == 0 else ""
        print(f"{domain:<40} {total:>6} {empty:>6}{marker}")


def get_domain_strings(locale: str, domain: str) -> list[dict]:
    """Return all rows for locale+domain as list of dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, msgid, msgid_plural, msgstr, msgstr_plural "
        "FROM translations WHERE locale=? AND domain=? ORDER BY id",
        (locale, domain),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def apply_translations(locale: str, domain: str, translations_json: str):
    """
    Apply a JSON dict of {msgid: msgstr} translations to the DB.
    translations_json: '{"Hello": "Bonjour", "Cancel": "Annuler", ...}'
    """
    translations = json.loads(translations_json)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    updated = 0
    not_found = 0
    for msgid, msgstr in translations.items():
        if not msgstr:
            continue
        result = cur.execute(
            "UPDATE translations SET msgstr=?, updated_at=datetime('now') "
            "WHERE locale=? AND domain=? AND msgid=?",
            (msgstr, locale, domain, msgid),
        )
        if result.rowcount > 0:
            updated += 1
        else:
            not_found += 1
    conn.commit()
    conn.close()
    print(f"locale={locale} domain={domain}: {updated} updated, {not_found} msgids not matched")


def print_for_translation(locale: str, domain: str):
    """Print strings formatted for LLM to fill in translations."""
    rows = get_domain_strings(locale, domain)
    print(f"# Translate to {locale.upper()} — domain: {domain} ({len(rows)} strings)")
    print("# Fill in the translated values. Preserve %(var)s, %s, \\n etc exactly.")
    print("# Return as JSON: {\"<msgid>\": \"<translated_msgstr>\", ...}\n")
    data = {r["msgid"]: "" for r in rows}
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", required=True, help="e.g. fr, es")
    parser.add_argument("--status", action="store_true", help="Show untranslated counts per domain")
    parser.add_argument("--domain", help="Domain to work on")
    parser.add_argument("--print", dest="print_strings", action="store_true",
                        help="Print strings formatted for LLM translation")
    parser.add_argument("--translations", help="JSON string of {msgid: msgstr} to import")
    args = parser.parse_args()

    if args.status:
        status(args.locale)
    elif args.print_strings and args.domain:
        print_for_translation(args.locale, args.domain)
    elif args.translations and args.domain:
        apply_translations(args.locale, args.domain, args.translations)
    else:
        parser.print_help()
