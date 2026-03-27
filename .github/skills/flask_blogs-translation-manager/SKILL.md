---
name: flask_blogs-translation-manager
description: Manage PlAnhead translations. Edit translations.db (SQLite) first, then export to .po/.mo via export_sqlite_to_mo.py. Never edit .po files directly. DB is dev-time only; runtime uses Flask-Babel .mo files.
---

# Skill: flask_blogs-translation-manager

## Purpose
Manage all translations for the **PlAnhead** Flask app. The single source of truth for translations is `translations.db` (SQLite). `.po` and `.mo` files are **generated artefacts** — never edited directly.

---

## ⚠️ CRITICAL: Pipeline Order

```
[Dev/build time]  translations.db  →  export_sqlite_to_mo.py  →  .po / .mo files
[Runtime]         Flask-Babel reads .mo files directly — ZERO DB access
```

**Always edit the DB first, then export. Never the reverse.**
**The DB is NEVER queried at request time. Flask-Babel uses `.mo` files only.**

### Runtime architecture guardrail
- Do **not** implement runtime translation lookups against `translations.db`.
- Do **not** warm/custom-cache translations from SQLite in request lifecycle hooks.
- Runtime i18n must flow through Flask-Babel gettext/lazy_gettext/ngettext and compiled `.mo` binaries.

---

## Workflows

### 1. Translate missing strings (fill empty msgstr)
```sql
-- Find all untranslated rows for a locale
SELECT id, domain, msgid, msgstr
FROM translations
WHERE locale = 'fr' AND (msgstr = '' OR msgstr IS NULL)
ORDER BY domain;
```
Then `UPDATE translations SET msgstr = '...', updated_at = datetime('now') WHERE id = ...`

After all updates:
```bash
cd flask_blogs/flask_planhead
python scripts/export_sqlite_to_mo.py
```

### 2. Add new UI strings (new feature)
```bash
cd flask_blogs/flask_planhead
# 1. Extract new strings from source
pybabel extract -F babel.cfg -o app/translations/messages.pot .

# 2. Update .po stubs for all locales
pybabel update -i app/translations/messages.pot -d app/translations

# 3. Import new stubs into DB (does not overwrite existing translations)
python scripts/migrate_po_to_sqlite.py

# 4. Translate new strings in DB (SQL UPDATE)
# 5. Export
python scripts/export_sqlite_to_mo.py
```

### 3. Verify coverage
```bash
cd flask_blogs/flask_planhead
python -m pytest tests/test_translation_completeness_db.py -v
```

Check counts directly:
```sql
SELECT locale, COUNT(*) as total,
       SUM(CASE WHEN msgstr = '' OR msgstr IS NULL THEN 1 ELSE 0 END) as empty
FROM translations
GROUP BY locale;
```

---

## Database Schema
**File**: `flask_blogs/flask_planhead/app/translations.db`  
**Table**: `translations`

| Column | Description |
|--------|-------------|
| id | Primary key |
| locale | `en`, `de`, `fr`, `es` |
| domain | Feature domain (e.g. `bank_account`, `main`, `messages`) |
| msgctxt | Optional context |
| msgid | English source string (never change this) |
| msgid_plural | Plural source string (if applicable) |
| msgstr | Translated string ← **edit this** |
| msgstr_plural | Translated plural (JSON array for plural forms) |
| updated_at | Timestamp |

---

## Key Scripts (run from `flask_blogs/flask_planhead/`)

| Script | Purpose |
|--------|---------|
| `scripts/export_sqlite_to_mo.py` | DB → `.po` + `.mo` (use after any DB edit) |
| `scripts/migrate_po_to_sqlite.py` | `.po` → DB (use only when importing new stubs) |

---

## Batch Translation Workflow (for large-scale LLM translation)

When translating many strings (e.g. a full locale), use the skill scripts for efficiency.
Located in `.github/skills/flask_blogs-translation-manager/scripts/`.
**Run all commands from `flask_blogs/flask_planhead/`.**

### Step 1 — Check status
```bash
python ../../.github/skills/flask_blogs-translation-manager/scripts/batch_translate.py \
    --locale fr --status
```

### Step 2 — Translate one domain at a time (per locale)
For each domain, print all strings, translate them as a JSON dict, then apply:

```bash
# Print strings formatted for LLM to fill in
python ../../.github/skills/flask_blogs-translation-manager/scripts/batch_translate.py \
    --locale fr --domain messages --print
```

The agent fills in the translations as a JSON dict `{"msgid": "translated_msgstr", ...}`, then applies:

```bash
python ../../.github/skills/flask_blogs-translation-manager/scripts/batch_translate.py \
    --locale fr --domain messages \
    --translations '{"Hello": "Bonjour", "Cancel": "Annuler", ...}'
```

### Step 3 — Export after all domains complete
```bash
cd flask_blogs/flask_planhead && python -m scripts.export_sqlite_to_mo
```

### Agent instruction (CRITICAL)
- Translate **one full domain per LLM call** — never string by string
- Translate from the **English `msgid`** — never from the existing `msgstr` (which may be wrong)
- Apply all translations for a domain in **one `--translations` call**
- Process FR completely before starting ES (or vice versa)

---

## Translation Guidelines
- **Register**: Formal (DE uses "Sie" → FR "vous" → ES "usted")
- **Format specifiers**: Preserve exactly — `%(var)s`, `%(var)d`, `%s`, `%d`
- **HTML/newlines**: Preserve exactly
- **Plural forms**: FR and ES both use `msgstr[0]` = singular, `msgstr[1]` = plural
- **Fallback**: Missing translations fall back to `en`
- **Reference**: Use `de` translations as style/register reference when translating `fr`/`es`

### 🚫 NEVER translate these — copy msgid verbatim as msgstr:
| Term | Reason |
|------|--------|
| **PlAnhead** | Brand name — must be identical in all locales |
| KfW 124, KfW 297, KfW 300 | German government programme codes |
| Bauspar, Bausparen, Bausparvertrag | German financial product names |
| SiGeKo | Technical abbreviation (safety coordinator) |
| QNG | Certification label name |
| ETF, CPI, ROI, TCO, IANA, UTC, DST | Technical acronyms |
| PDF, URL, API, HTML, CSS, LED, OLED | Universal technical terms |
| Espresso, Diesel, Gas | Same in target languages |
| City/country names | Proper nouns |
| `%(var)s`, `{var}`, `%s`, `%%` | Format specifiers |

---

## Supported Locales
`en` · `de` · `fr` · `es`
