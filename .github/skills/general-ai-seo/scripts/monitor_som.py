#!/usr/bin/env python3
"""
Tool: Share of Model Monitor
Purpose: Track how often a brand appears in AI-generated responses across platforms.

This script handles query generation and result processing. The actual AI queries
are executed by Claude using Perplexity MCP — this script manages the data pipeline.

Usage:
    # Generate tracked queries for a brand
    python3 .claude/skills/ai-seo/scripts/monitor_som.py --generate-queries \
        --brand "Example Co" --industry "AI consulting" --output queries.json

    # Process query results (after Claude runs them through Perplexity)
    python3 .claude/skills/ai-seo/scripts/monitor_som.py --process-results \
        --input results.json --brand "Example Co"

    # Aggregate results for a check date
    python3 .claude/skills/ai-seo/scripts/monitor_som.py --aggregate \
        --brand "Example Co"

    # Get historical SoM data
    python3 .claude/skills/ai-seo/scripts/monitor_som.py --history \
        --brand "Example Co"

Dependencies:
    - psycopg2
    - lib.db (shared Supabase connection)
"""

import sys
import json
import argparse
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from lib.db import execute, execute_one


def generate_queries(brand, industry, niche=None):
    """Generate a set of tracked queries for monitoring.

    These are query TEMPLATES — Claude should customize them based on the
    brand's specific offerings and ICP.
    """
    templates = {
        "informational": [
            f"What is the best {industry} company?",
            f"How to choose a {industry} provider?",
            f"What should I look for in a {industry} service?",
            f"Top {industry} companies in 2026",
            f"Best {industry} for small businesses",
            f"{industry} trends 2026",
            f"How does {industry} work?",
        ],
        "comparative": [
            f"Best {industry} companies compared",
            f"{industry} alternatives and options",
            f"Which {industry} provider is best for startups?",
            f"Affordable {industry} solutions",
        ],
        "transactional": [
            f"Hire a {industry} expert",
            f"Find a {industry} consultant",
            f"{industry} services near me",
            f"Get started with {industry}",
        ],
        "brand": [
            f"What is {brand}?",
            f"{brand} reviews",
            f"Is {brand} good?",
            f"{brand} vs competitors",
        ]
    }

    if niche:
        templates["informational"].extend([
            f"Best {niche} tools 2026",
            f"How to implement {niche}",
            f"{niche} best practices",
        ])

    queries = []
    for category, query_list in templates.items():
        for q in query_list:
            queries.append({
                "query": q,
                "category": category
            })

    return {
        "brand": brand,
        "industry": industry,
        "niche": niche,
        "queries": queries,
        "total": len(queries)
    }


def process_results(results_data, brand):
    """Process Perplexity query results and calculate SoM metrics.

    Input format (from Claude's Perplexity queries):
    {
        "brand": "Example Co",
        "domain": "example.com",
        "check_date": "2026-03-16",
        "results": [
            {
                "query": "best AI consulting companies",
                "query_id": 123,  // optional, from DB
                "category": "informational",
                "response": "full AI response text...",
                "brand_mentioned": true,
                "mention_position": "primary",  // primary, top3, mentioned, absent
                "sentiment": "positive",  // positive, neutral, negative
                "source_url": "https://...",  // if cited
                "competitors_mentioned": ["Comp A", "Comp B"]
            }
        ]
    }
    """
    results = results_data.get("results", [])
    check_date = results_data.get("check_date", date.today().isoformat())

    total_queries = len(results)
    mention_count = sum(1 for r in results if r.get("brand_mentioned"))
    mention_rate = (mention_count / total_queries * 100) if total_queries else 0

    position_scores = []
    primary_count = 0
    for r in results:
        pos = r.get("mention_position", "absent")
        if pos == "primary":
            position_scores.append(3)
            primary_count += 1
        elif pos == "top3":
            position_scores.append(2)
        elif pos == "mentioned":
            position_scores.append(1)
        else:
            position_scores.append(0)

    avg_position = sum(position_scores) / len(position_scores) if position_scores else 0

    # Competitor analysis
    competitor_mentions = {}
    for r in results:
        for comp in r.get("competitors_mentioned", []):
            if comp not in competitor_mentions:
                competitor_mentions[comp] = {"mention_count": 0, "total_queries": 0}
            competitor_mentions[comp]["total_queries"] += 1
            competitor_mentions[comp]["mention_count"] += 1

    competitor_comparison = {}
    for comp, data in competitor_mentions.items():
        competitor_comparison[comp] = {
            "mention_rate": round(data["mention_count"] / total_queries * 100, 1),
            "mention_count": data["mention_count"]
        }

    summary = {
        "brand": brand,
        "check_date": check_date,
        "total_queries": total_queries,
        "mention_count": mention_count,
        "mention_rate": round(mention_rate, 1),
        "avg_position_score": round(avg_position, 2),
        "primary_count": primary_count,
        "competitor_comparison": competitor_comparison,
        "query_results": results
    }

    return summary


def save_results_to_db(summary, domain):
    """Save processed results to database."""
    # Get site ID
    site_row = execute_one(
        "SELECT id FROM ops.aiseo_sites WHERE domain = %s",
        (domain.lower(),)
    )
    if not site_row:
        return {"success": False, "message": f"Site not found: {domain}. Run --save-site first."}

    site_id = site_row['id']
    check_date = summary.get("check_date", date.today().isoformat())

    # Save aggregate
    execute("""
        INSERT INTO ops.aiseo_som_aggregates (
            site_id, check_date, total_queries, mention_count,
            mention_rate, avg_position_score, primary_count, competitor_comparison
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(site_id, check_date) DO UPDATE SET
            total_queries = EXCLUDED.total_queries,
            mention_count = EXCLUDED.mention_count,
            mention_rate = EXCLUDED.mention_rate,
            avg_position_score = EXCLUDED.avg_position_score,
            primary_count = EXCLUDED.primary_count,
            competitor_comparison = EXCLUDED.competitor_comparison
    """, (
        site_id, check_date,
        summary["total_queries"], summary["mention_count"],
        summary["mention_rate"], summary["avg_position_score"],
        summary["primary_count"],
        json.dumps(summary.get("competitor_comparison", {}))
    ), fetch=False)

    return {"success": True, "message": f"SoM aggregate saved for {check_date}"}


def get_history(brand, limit=20):
    """Get historical SoM data for trending."""
    row = execute_one(
        "SELECT id, domain FROM ops.aiseo_sites WHERE LOWER(brand_name) = LOWER(%s)",
        (brand,)
    )
    if not row:
        return {"success": False, "message": f"Brand not found: {brand}"}

    aggregates = execute("""
        SELECT check_date, total_queries, mention_count, mention_rate,
               avg_position_score, primary_count, competitor_comparison
        FROM ops.aiseo_som_aggregates
        WHERE site_id = %s
        ORDER BY check_date DESC
        LIMIT %s
    """, (row['id'], limit))

    # Calculate trend
    history = [dict(r) for r in aggregates]
    trend = "no data"
    if len(history) >= 2:
        latest = history[0].get("mention_rate", 0)
        previous = history[1].get("mention_rate", 0)
        if latest > previous:
            trend = "improving"
        elif latest < previous:
            trend = "declining"
        else:
            trend = "stable"

    return {
        "success": True,
        "brand": brand,
        "domain": row['domain'],
        "trend": trend,
        "history": history
    }


def main():
    parser = argparse.ArgumentParser(description="Share of Model Monitor")
    parser.add_argument("--generate-queries", action="store_true",
                        help="Generate tracked queries for a brand")
    parser.add_argument("--process-results", action="store_true",
                        help="Process Perplexity query results")
    parser.add_argument("--save-to-db", action="store_true",
                        help="Save processed results to database")
    parser.add_argument("--history", action="store_true",
                        help="Get historical SoM data")
    parser.add_argument("--brand", help="Brand name")
    parser.add_argument("--industry", help="Industry/niche")
    parser.add_argument("--niche", help="Specific niche within industry")
    parser.add_argument("--domain", help="Domain for DB operations")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()
    result = None

    if args.generate_queries:
        if not args.brand or not args.industry:
            print(json.dumps({"success": False, "message": "--brand and --industry required"}))
            sys.exit(1)
        result = generate_queries(args.brand, args.industry, args.niche)

    elif args.process_results:
        if not args.input or not args.brand:
            print(json.dumps({"success": False, "message": "--input and --brand required"}))
            sys.exit(1)
        with open(args.input) as f:
            data = json.load(f)
        result = process_results(data, args.brand)

    elif args.save_to_db:
        if not args.input or not args.domain:
            print(json.dumps({"success": False, "message": "--input and --domain required"}))
            sys.exit(1)
        with open(args.input) as f:
            data = json.load(f)
        result = save_results_to_db(data, args.domain)

    elif args.history:
        if not args.brand:
            print(json.dumps({"success": False, "message": "--brand required"}))
            sys.exit(1)
        result = get_history(args.brand)

    else:
        parser.print_help()
        sys.exit(1)

    output = json.dumps(result, indent=2, default=str)
    print(output)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(output)

    if result and not result.get("success", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
