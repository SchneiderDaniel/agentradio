#!/usr/bin/env python3
"""
Tool: AI SEO Revenue Impact Estimator
Purpose: Connect AI visibility metrics to estimated business revenue impact.

Uses the research-backed conversion differential:
- AI referral traffic converts at 14.2%
- Google organic converts at 2.8%
- This 5x difference means even small AI visibility improvements have outsized revenue impact.

Usage:
    # Generate revenue impact estimate
    python3 .claude/skills/ai-seo/scripts/measure_report.py --brand "Example Co" --domain example.com

    # With user-provided traffic data
    python3 .claude/skills/ai-seo/scripts/measure_report.py --input traffic_data.json

Input JSON format (optional, for more accurate estimates):
    {
        "brand": "Example Co",
        "domain": "example.com",
        "monthly_google_organic_traffic": 5000,
        "monthly_ai_referral_traffic": 200,
        "average_deal_value": 5000,
        "current_conversion_rate": 0.03
    }

Dependencies:
    - psycopg2
    - lib.db
"""

import sys
import json
import argparse
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from lib.db import execute, execute_one

# Research-backed constants
AI_REFERRAL_CONVERSION_RATE = 0.142  # 14.2% (ALM Corp)
GOOGLE_ORGANIC_CONVERSION_RATE = 0.028  # 2.8% (ALM Corp)
CONVERSION_MULTIPLIER = AI_REFERRAL_CONVERSION_RATE / GOOGLE_ORGANIC_CONVERSION_RATE  # ~5.07x


def estimate_with_traffic_data(data):
    """Generate revenue estimate when user provides actual traffic numbers."""
    brand = data.get("brand", "Unknown")
    domain = data.get("domain", "")
    google_traffic = data.get("monthly_google_organic_traffic", 0)
    ai_traffic = data.get("monthly_ai_referral_traffic", 0)
    deal_value = data.get("average_deal_value", 1000)
    current_cr = data.get("current_conversion_rate", GOOGLE_ORGANIC_CONVERSION_RATE)

    # Current state
    current_google_conversions = google_traffic * current_cr
    current_ai_conversions = ai_traffic * AI_REFERRAL_CONVERSION_RATE
    current_total_conversions = current_google_conversions + current_ai_conversions
    current_revenue = current_total_conversions * deal_value

    # Projected: double AI traffic through optimization
    projected_ai_traffic = ai_traffic * 2
    projected_ai_conversions = projected_ai_traffic * AI_REFERRAL_CONVERSION_RATE
    projected_total_conversions = current_google_conversions + projected_ai_conversions
    projected_revenue = projected_total_conversions * deal_value
    revenue_uplift = projected_revenue - current_revenue

    # Projected: 5x AI traffic (aggressive optimization + multi-platform)
    aggressive_ai_traffic = ai_traffic * 5 if ai_traffic > 0 else google_traffic * 0.1
    aggressive_ai_conversions = aggressive_ai_traffic * AI_REFERRAL_CONVERSION_RATE
    aggressive_total = current_google_conversions + aggressive_ai_conversions
    aggressive_revenue = aggressive_total * deal_value
    aggressive_uplift = aggressive_revenue - current_revenue

    narrative = f"""### Current State

- **Google organic traffic**: {google_traffic:,} visits/month
- **AI referral traffic**: {ai_traffic:,} visits/month
- **Estimated conversions**: {current_total_conversions:.1f}/month ({current_google_conversions:.1f} from Google + {current_ai_conversions:.1f} from AI)
- **Estimated monthly revenue from search**: ${current_revenue:,.0f}

### Scenario 1: Double AI Referral Traffic (Conservative)

By improving AI-readiness (schema, answer-first content, FAQ sections):

- **Projected AI traffic**: {projected_ai_traffic:,} visits/month
- **Projected AI conversions**: {projected_ai_conversions:.1f}/month
- **Monthly revenue uplift**: **+${revenue_uplift:,.0f}**
- **Annual revenue uplift**: **+${revenue_uplift * 12:,.0f}**

### Scenario 2: 5x AI Referral Traffic (Full Optimization)

Full AI SEO: schema, content optimization, multi-platform presence, monitoring:

- **Projected AI traffic**: {aggressive_ai_traffic:,.0f} visits/month
- **Projected AI conversions**: {aggressive_ai_conversions:.1f}/month
- **Monthly revenue uplift**: **+${aggressive_uplift:,.0f}**
- **Annual revenue uplift**: **+${aggressive_uplift * 12:,.0f}**

### Why AI Traffic Is Worth More

AI referral traffic converts at **14.2%** vs Google organic's **2.8%** — a **{CONVERSION_MULTIPLIER:.1f}x difference**. This means 100 AI referral visitors are worth the same as {int(100 * CONVERSION_MULTIPLIER)} Google organic visitors in conversion value. Optimizing for AI visibility delivers outsized returns per visitor."""

    return {
        "brand": brand,
        "domain": domain,
        "date": str(date.today()),
        "current_som": {},
        "traffic_estimate": {
            "google_organic": f"{google_traffic:,}",
            "ai_referral": f"{ai_traffic:,}",
            "google_conversions": f"{current_google_conversions:.1f}",
            "ai_conversions": f"{current_ai_conversions:.1f}"
        },
        "revenue_estimate": {
            "narrative": narrative,
            "current_monthly_revenue": round(current_revenue),
            "conservative_uplift_monthly": round(revenue_uplift),
            "conservative_uplift_annual": round(revenue_uplift * 12),
            "aggressive_uplift_monthly": round(aggressive_uplift),
            "aggressive_uplift_annual": round(aggressive_uplift * 12)
        }
    }


def estimate_without_traffic_data(brand, domain):
    """Generate revenue estimate using benchmarks when no traffic data is available."""

    # Try to get SoM data from database
    som_data = {}
    try:
        row = execute_one(
            "SELECT id FROM ops.aiseo_sites WHERE domain = %s",
            (domain.lower(),)
        )
        if row:
            agg = execute_one("""
                SELECT mention_rate, avg_position_score, primary_count
                FROM ops.aiseo_som_aggregates
                WHERE site_id = %s
                ORDER BY check_date DESC
                LIMIT 1
            """, (row['id'],))
            if agg:
                som_data = dict(agg)
    except Exception:
        pass

    narrative = f"""### No Traffic Data Available

To generate accurate revenue projections, provide your Google Analytics data:

1. **Monthly Google organic traffic** — GA4 > Reports > Acquisition > Traffic acquisition
2. **Monthly AI referral traffic** — Look for: chat.openai.com, perplexity.ai, gemini.google.com, claude.ai, copilot.microsoft.com
3. **Average deal/order value** — Your CRM or payment processor
4. **Current conversion rate** — GA4 > Reports > Monetization > Conversions

### Industry Benchmarks

Without your specific data, here's what the research shows:

- **AI referral traffic converts at 14.2%** vs Google organic's 2.8% (ALM Corp, 2M sessions)
- **AI referral traffic grew 527% YoY** through H1 2025 (Position Digital)
- **Brands cited as primary recommendation** in AI responses see 6.5x more traffic than generic mentions
- Even a **modest 200 AI referral visits/month** at 14.2% = **28 conversions** — equivalent to 1,000 Google organic visits

### Quick Estimate

If your average deal is $1,000:
- 200 AI visits/month x 14.2% = 28 conversions = **$28,000/month**
- vs 200 Google visits/month x 2.8% = 5.6 conversions = **$5,600/month**
- **Same traffic, 5x the revenue** — that's the AI referral advantage."""

    return {
        "brand": brand,
        "domain": domain,
        "date": str(date.today()),
        "current_som": som_data,
        "traffic_estimate": {
            "google_organic": "N/A — provide GA4 data",
            "ai_referral": "N/A — provide GA4 data",
            "google_conversions": "N/A",
            "ai_conversions": "N/A"
        },
        "revenue_estimate": {
            "narrative": narrative,
            "note": "Provide traffic data for accurate projections"
        }
    }


def main():
    parser = argparse.ArgumentParser(description="AI SEO Revenue Impact Estimator")
    parser.add_argument("--brand", help="Brand name")
    parser.add_argument("--domain", help="Domain")
    parser.add_argument("--input", help="Traffic data JSON file")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            data = json.load(f)
        result = estimate_with_traffic_data(data)
    elif args.brand and args.domain:
        result = estimate_without_traffic_data(args.brand, args.domain)
    else:
        print(json.dumps({"success": False, "message": "--brand and --domain required, or --input"}))
        sys.exit(1)

    output = json.dumps(result, indent=2, default=str)
    print(output)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(output)


if __name__ == "__main__":
    main()
