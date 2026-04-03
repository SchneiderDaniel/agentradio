#!/usr/bin/env python3
"""
Tool: AI SEO Database
Purpose: Supabase Postgres storage for AI SEO audit results, Share of Model tracking,
         and optimization history.

Usage:
    python3 .claude/skills/ai-seo/scripts/seo_db.py --init-db
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-site '{"domain":"example.com","brand_name":"Example"}'
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-audit input.json
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-pages input.json
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-queries input.json
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-som-snapshot input.json
    python3 .claude/skills/ai-seo/scripts/seo_db.py --save-som-aggregate input.json
    python3 .claude/skills/ai-seo/scripts/seo_db.py --get-site --domain example.com
    python3 .claude/skills/ai-seo/scripts/seo_db.py --audit-history --domain example.com
    python3 .claude/skills/ai-seo/scripts/seo_db.py --som-history --brand "Example"
    python3 .claude/skills/ai-seo/scripts/seo_db.py --stats

Dependencies:
    - psycopg2
    - lib.db (shared Supabase connection)

Output: JSON with success status and data
"""

import sys
import json
import argparse
from datetime import date
from pathlib import Path

# Add project root to path for lib imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from lib.db import execute, execute_one, get_connection, put_connection


def init_db():
    """Verify all 6 aiseo tables exist in ops schema."""
    row = execute_one(
        "SELECT COUNT(*) as count FROM information_schema.tables "
        "WHERE table_schema = 'ops' AND table_name LIKE 'aiseo_%'"
    )
    count = row['count'] if row else 0
    expected = 6
    if count >= expected:
        return {"success": True, "message": f"All {count} AI SEO tables found in ops schema"}
    return {
        "success": False,
        "message": f"Only {count}/{expected} tables found. Run the Supabase migration.",
        "tables_found": count
    }


# --- Site management ---

def save_site(data):
    """Create or update a tracked site."""
    domain = data.get("domain", "").strip().lower()
    brand_name = data.get("brand_name", "")
    industry = data.get("industry", "")
    niche = data.get("niche", "")
    owner_notes = data.get("owner_notes", "")

    if not domain or not brand_name:
        return {"success": False, "message": "domain and brand_name are required"}

    row = execute_one("""
        INSERT INTO ops.aiseo_sites (domain, brand_name, industry, niche, owner_notes)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(domain) DO UPDATE SET
            brand_name = EXCLUDED.brand_name,
            industry = EXCLUDED.industry,
            niche = EXCLUDED.niche,
            owner_notes = EXCLUDED.owner_notes,
            updated_at = NOW()
        RETURNING id, domain, brand_name
    """, (domain, brand_name, industry, niche, owner_notes))

    return {"success": True, "site": dict(row) if row else None}


def get_site(domain):
    """Get a site by domain."""
    row = execute_one(
        "SELECT * FROM ops.aiseo_sites WHERE domain = %s",
        (domain.strip().lower(),)
    )
    if not row:
        return {"success": False, "message": f"Site not found: {domain}"}
    return {"success": True, "site": dict(row)}


def get_site_id(domain):
    """Get site ID by domain, or None."""
    row = execute_one(
        "SELECT id FROM ops.aiseo_sites WHERE domain = %s",
        (domain.strip().lower(),)
    )
    return row['id'] if row else None


# --- Audit results ---

def save_audit(data):
    """Save an audit result."""
    site_id = data.get("site_id")
    if not site_id and data.get("domain"):
        site_id = get_site_id(data["domain"])
    if not site_id:
        return {"success": False, "message": "site_id or domain required"}

    row = execute_one("""
        INSERT INTO ops.aiseo_audits (
            site_id, audit_date, overall_score, tier,
            crawler_access_score, schema_markup_score, content_structure_score,
            entity_clarity_score, multiplatform_score, current_visibility_score,
            technical_score, findings, priority_fixes, report_path
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT(site_id, audit_date) DO UPDATE SET
            overall_score = EXCLUDED.overall_score,
            tier = EXCLUDED.tier,
            crawler_access_score = EXCLUDED.crawler_access_score,
            schema_markup_score = EXCLUDED.schema_markup_score,
            content_structure_score = EXCLUDED.content_structure_score,
            entity_clarity_score = EXCLUDED.entity_clarity_score,
            multiplatform_score = EXCLUDED.multiplatform_score,
            current_visibility_score = EXCLUDED.current_visibility_score,
            technical_score = EXCLUDED.technical_score,
            findings = EXCLUDED.findings,
            priority_fixes = EXCLUDED.priority_fixes,
            report_path = EXCLUDED.report_path
        RETURNING id
    """, (
        site_id,
        data.get("audit_date", date.today().isoformat()),
        data.get("overall_score", 0),
        data.get("tier", "not_ready"),
        data.get("crawler_access_score", 0),
        data.get("schema_markup_score", 0),
        data.get("content_structure_score", 0),
        data.get("entity_clarity_score", 0),
        data.get("multiplatform_score", 0),
        data.get("current_visibility_score", 0),
        data.get("technical_score", 0),
        json.dumps(data.get("findings", {})),
        json.dumps(data.get("priority_fixes", [])),
        data.get("report_path", "")
    ))

    return {"success": True, "audit_id": row['id'] if row else None}


def save_pages(data):
    """Save page analysis results (batch)."""
    audit_id = data.get("audit_id")
    pages = data.get("pages", [])
    if not audit_id:
        return {"success": False, "message": "audit_id required"}

    saved = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        for page in pages:
            cur.execute("""
                INSERT INTO ops.aiseo_page_analyses (
                    audit_id, url, page_type, has_schema, schema_types,
                    answer_first, stat_count, citation_count, quote_count,
                    has_faq, word_count, last_modified, page_score, findings
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                audit_id,
                page.get("url", ""),
                page.get("page_type", "unknown"),
                page.get("has_schema", False),
                page.get("schema_types", []),
                page.get("answer_first", False),
                page.get("stat_count", 0),
                page.get("citation_count", 0),
                page.get("quote_count", 0),
                page.get("has_faq", False),
                page.get("word_count", 0),
                page.get("last_modified"),
                page.get("page_score", 0),
                json.dumps(page.get("findings", {}))
            ))
            saved += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)

    return {"success": True, "pages_saved": saved}


def audit_history(domain):
    """Get audit history for a site."""
    site_id = get_site_id(domain)
    if not site_id:
        return {"success": False, "message": f"Site not found: {domain}"}

    rows = execute("""
        SELECT audit_date, overall_score, tier,
               crawler_access_score, schema_markup_score, content_structure_score,
               entity_clarity_score, multiplatform_score, current_visibility_score,
               technical_score, report_path
        FROM ops.aiseo_audits
        WHERE site_id = %s
        ORDER BY audit_date DESC
        LIMIT 20
    """, (site_id,))

    return {"success": True, "domain": domain, "audits": [dict(r) for r in rows]}


# --- Share of Model tracking ---

def save_queries(data):
    """Save tracked queries for a site."""
    site_id = data.get("site_id")
    if not site_id and data.get("domain"):
        site_id = get_site_id(data["domain"])
    if not site_id:
        return {"success": False, "message": "site_id or domain required"}

    queries = data.get("queries", [])
    saved = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        for q in queries:
            cur.execute("""
                INSERT INTO ops.aiseo_tracked_queries (site_id, query, category)
                VALUES (%s, %s, %s)
                ON CONFLICT(site_id, query) DO UPDATE SET
                    category = EXCLUDED.category,
                    is_active = TRUE
            """, (site_id, q.get("query", ""), q.get("category", "informational")))
            saved += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)

    return {"success": True, "queries_saved": saved}


def get_queries(domain):
    """Get active tracked queries for a site."""
    site_id = get_site_id(domain)
    if not site_id:
        return {"success": False, "message": f"Site not found: {domain}"}

    rows = execute("""
        SELECT id, query, category
        FROM ops.aiseo_tracked_queries
        WHERE site_id = %s AND is_active = TRUE
        ORDER BY category, query
    """, (site_id,))

    return {"success": True, "queries": [dict(r) for r in rows]}


def save_som_snapshot(data):
    """Save a single Share of Model check result."""
    site_id = data.get("site_id")
    if not site_id and data.get("domain"):
        site_id = get_site_id(data["domain"])

    execute("""
        INSERT INTO ops.aiseo_som_snapshots (
            site_id, query_id, check_date, source,
            brand_mentioned, mention_position, position_score,
            sentiment, source_url, snippet, competitor_data, raw_response
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        site_id,
        data.get("query_id"),
        data.get("check_date", date.today().isoformat()),
        data.get("source", "perplexity"),
        data.get("brand_mentioned", False),
        data.get("mention_position", "absent"),
        data.get("position_score", 0),
        data.get("sentiment", "neutral"),
        data.get("source_url", ""),
        data.get("snippet", ""),
        json.dumps(data.get("competitor_data", {})),
        data.get("raw_response", "")
    ), fetch=False)

    return {"success": True}


def save_som_aggregate(data):
    """Save aggregated Share of Model metrics."""
    site_id = data.get("site_id")
    if not site_id and data.get("domain"):
        site_id = get_site_id(data["domain"])

    execute_one("""
        INSERT INTO ops.aiseo_som_aggregates (
            site_id, check_date, total_queries, mention_count,
            mention_rate, avg_position_score, primary_count,
            competitor_comparison, report_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(site_id, check_date) DO UPDATE SET
            total_queries = EXCLUDED.total_queries,
            mention_count = EXCLUDED.mention_count,
            mention_rate = EXCLUDED.mention_rate,
            avg_position_score = EXCLUDED.avg_position_score,
            primary_count = EXCLUDED.primary_count,
            competitor_comparison = EXCLUDED.competitor_comparison,
            report_path = EXCLUDED.report_path
        RETURNING id
    """, (
        site_id,
        data.get("check_date", date.today().isoformat()),
        data.get("total_queries", 0),
        data.get("mention_count", 0),
        data.get("mention_rate", 0),
        data.get("avg_position_score", 0),
        data.get("primary_count", 0),
        json.dumps(data.get("competitor_comparison", {})),
        data.get("report_path", "")
    ))

    return {"success": True}


def som_history(brand):
    """Get Share of Model history for a brand."""
    # Find site by brand name
    row = execute_one(
        "SELECT id, domain FROM ops.aiseo_sites WHERE LOWER(brand_name) = LOWER(%s)",
        (brand,)
    )
    if not row:
        return {"success": False, "message": f"Brand not found: {brand}"}

    site_id = row['id']
    aggregates = execute("""
        SELECT check_date, total_queries, mention_count, mention_rate,
               avg_position_score, primary_count, competitor_comparison
        FROM ops.aiseo_som_aggregates
        WHERE site_id = %s
        ORDER BY check_date DESC
        LIMIT 20
    """, (site_id,))

    return {
        "success": True,
        "brand": brand,
        "domain": row['domain'],
        "history": [dict(r) for r in aggregates]
    }


def get_stats():
    """Get database statistics."""
    sites = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_sites")
    audits = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_audits")
    pages = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_page_analyses")
    queries = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_tracked_queries")
    snapshots = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_som_snapshots")
    aggregates = execute_one("SELECT COUNT(*) as count FROM ops.aiseo_som_aggregates")

    return {
        "success": True,
        "sites": sites['count'],
        "audits": audits['count'],
        "page_analyses": pages['count'],
        "tracked_queries": queries['count'],
        "som_snapshots": snapshots['count'],
        "som_aggregates": aggregates['count']
    }


def main():
    parser = argparse.ArgumentParser(description="AI SEO Database")
    parser.add_argument("--init-db", action="store_true", help="Verify database tables exist")
    parser.add_argument("--save-site", metavar="JSON", help="Create/update a site (JSON string or file)")
    parser.add_argument("--get-site", action="store_true", help="Get site by domain")
    parser.add_argument("--save-audit", metavar="FILE", help="Save audit results from JSON file")
    parser.add_argument("--save-pages", metavar="FILE", help="Save page analyses from JSON file")
    parser.add_argument("--save-queries", metavar="FILE", help="Save tracked queries from JSON file")
    parser.add_argument("--save-som-snapshot", metavar="FILE", help="Save SoM snapshot from JSON file")
    parser.add_argument("--save-som-aggregate", metavar="FILE", help="Save SoM aggregate from JSON file")
    parser.add_argument("--audit-history", action="store_true", help="Get audit history for domain")
    parser.add_argument("--som-history", action="store_true", help="Get SoM history for brand")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--domain", metavar="DOMAIN", help="Domain for lookups")
    parser.add_argument("--brand", metavar="BRAND", help="Brand name for lookups")

    args = parser.parse_args()
    result = None

    if args.init_db:
        result = init_db()

    elif args.save_site:
        data = json.loads(args.save_site) if args.save_site.startswith('{') else json.load(open(args.save_site))
        result = save_site(data)

    elif args.get_site:
        if not args.domain:
            print(json.dumps({"success": False, "message": "--domain required"}))
            sys.exit(1)
        result = get_site(args.domain)

    elif args.save_audit:
        with open(args.save_audit) as f:
            result = save_audit(json.load(f))

    elif args.save_pages:
        with open(args.save_pages) as f:
            result = save_pages(json.load(f))

    elif args.save_queries:
        with open(args.save_queries) as f:
            result = save_queries(json.load(f))

    elif args.save_som_snapshot:
        with open(args.save_som_snapshot) as f:
            result = save_som_snapshot(json.load(f))

    elif args.save_som_aggregate:
        with open(args.save_som_aggregate) as f:
            result = save_som_aggregate(json.load(f))

    elif args.audit_history:
        if not args.domain:
            print(json.dumps({"success": False, "message": "--domain required"}))
            sys.exit(1)
        result = audit_history(args.domain)

    elif args.som_history:
        if not args.brand:
            print(json.dumps({"success": False, "message": "--brand required"}))
            sys.exit(1)
        result = som_history(args.brand)

    elif args.stats:
        result = get_stats()

    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))

    if result and not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
