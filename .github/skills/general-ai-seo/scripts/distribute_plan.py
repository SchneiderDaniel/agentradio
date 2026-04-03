#!/usr/bin/env python3
"""
Tool: Multi-Platform Distribution Planner
Purpose: Generate a platform-specific distribution strategy to maximize AI citation surface area.

This script generates query templates and processes research results.
Claude orchestrates the actual Perplexity/Firecrawl research.

Usage:
    # Generate research queries for platform presence check
    python3 .claude/skills/ai-seo/scripts/distribute_plan.py --assess \
        --brand "Example Co" --industry "AI consulting" --output assessment_queries.json

    # Process research results into a distribution plan
    python3 .claude/skills/ai-seo/scripts/distribute_plan.py --plan \
        --input research_results.json --output distribution_plan.json

Dependencies:
    - pyyaml
"""

import sys
import json
import argparse
from datetime import date, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PLAYBOOK_PATH = SKILL_DIR / "references" / "platform_playbook.yaml"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def generate_assessment_queries(brand, industry, niche=None):
    """Generate queries to assess current platform presence."""
    queries = {
        "reddit": [
            f"site:reddit.com {brand}",
            f"site:reddit.com {industry} {brand}",
            f"reddit {brand} reviews",
        ],
        "youtube": [
            f"site:youtube.com {brand}",
            f"{brand} youtube channel",
            f"{brand} {industry} video",
        ],
        "linkedin": [
            f"site:linkedin.com {brand}",
            f"linkedin {brand} {industry}",
        ],
        "third_party": [
            f"{brand} review",
            f"best {industry} companies",
            f"top {industry} providers 2026",
            f"{brand} case study",
            f"{brand} mentioned in",
        ],
        "general": [
            f'"{brand}" -{brand.lower().replace(" ", "")}.com',  # Mentions excluding own domain
            f"{brand} podcast guest",
            f"{brand} interview",
        ]
    }

    if niche:
        queries["third_party"].extend([
            f"best {niche} tools",
            f"top {niche} companies",
        ])

    return {
        "brand": brand,
        "industry": industry,
        "niche": niche,
        "assessment_queries": queries,
        "instructions": (
            "Run each query through Firecrawl search and Perplexity. "
            "For each platform, note: (1) whether the brand is present, "
            "(2) how active they are, (3) the quality/recency of mentions. "
            "Return results as JSON with platform scores."
        )
    }


def generate_distribution_plan(research_data):
    """Generate a 90-day distribution plan based on research results.

    Input format:
    {
        "brand": "Example Co",
        "industry": "AI consulting",
        "current_presence": {
            "reddit": {"present": false, "activity_level": "none", "notes": "..."},
            "youtube": {"present": true, "activity_level": "low", "notes": "..."},
            "linkedin": {"present": true, "activity_level": "medium", "notes": "..."},
            "third_party": {"mentions_found": 3, "quality": "low", "notes": "..."}
        },
        "platform_count": 2,
        "gaps": ["reddit", "third_party"]
    }
    """
    brand = research_data.get("brand", "Unknown")
    industry = research_data.get("industry", "")
    presence = research_data.get("current_presence", {})
    platform_count = research_data.get("platform_count", 0)
    gaps = research_data.get("gaps", [])

    # Load playbook for platform-specific tactics
    try:
        import yaml
        with open(PLAYBOOK_PATH) as f:
            playbook = yaml.safe_load(f)
    except Exception:
        playbook = {"platforms": {}, "distribution_calendar_template": {}}

    # Score current state
    platform_scores = {}
    for platform, data in presence.items():
        if isinstance(data, dict):
            activity = data.get("activity_level", "none")
            score_map = {"high": 4, "medium": 2, "low": 1, "none": 0}
            platform_scores[platform] = score_map.get(activity, 0)

    total_platform_score = sum(platform_scores.values())
    max_possible = len(platform_scores) * 4

    # Determine priorities
    priorities = []

    # Third-party seeding is ALWAYS highest priority (85% of citations)
    if "third_party" in gaps or platform_scores.get("third_party", 0) < 2:
        priorities.append({
            "platform": "Third-Party Mentions",
            "priority": 1,
            "reason": "85% of brand citations in AI come from third-party pages",
            "current_state": presence.get("third_party", {}).get("notes", "Unknown"),
        })

    # Reddit (24% of AI responses — OtterlyAI 2026)
    if "reddit" in gaps or platform_scores.get("reddit", 0) < 2:
        priorities.append({
            "platform": "Reddit",
            "priority": 2,
            "reason": "Reddit appears in 24% of AI-generated responses (OtterlyAI 2026)",
            "current_state": presence.get("reddit", {}).get("notes", "Unknown"),
        })

    # YouTube (29.5% of AI Overviews)
    if "youtube" in gaps or platform_scores.get("youtube", 0) < 2:
        priorities.append({
            "platform": "YouTube",
            "priority": 3,
            "reason": "YouTube appears in 29.5% of Google AI Overviews",
            "current_state": presence.get("youtube", {}).get("notes", "Unknown"),
        })

    # LinkedIn
    if "linkedin" in gaps or platform_scores.get("linkedin", 0) < 2:
        priorities.append({
            "platform": "LinkedIn",
            "priority": 4,
            "reason": "Professional authority signal for B2B queries",
            "current_state": presence.get("linkedin", {}).get("notes", "Unknown"),
        })

    # Build 90-day calendar
    today = date.today()
    calendar = []

    # Weeks 1-4: Third-party seeding
    for week in range(1, 5):
        week_start = today + timedelta(weeks=week-1)
        actions = []
        if week == 1:
            actions = [
                f"Identify 10 target publications in {industry}",
                "Audit competitor third-party mentions (where do they appear that you don't?)",
                "Draft 3 guest post pitches with unique data/frameworks",
            ]
        elif week == 2:
            actions = [
                "Send guest post pitches to top 5 publications",
                "Submit to 5 relevant industry directories",
                "Respond to 3 journalist/HARO queries",
            ]
        elif week == 3:
            actions = [
                "Follow up on guest post pitches",
                "Identify 5 'best of' lists to get included in",
                "Reach out to list curators with differentiators",
            ]
        elif week == 4:
            actions = [
                "Pitch 2 podcast appearances",
                "Submit expert quotes to 3 industry publications",
                "Review and update any existing third-party mentions",
            ]

        calendar.append({
            "week": week,
            "start_date": str(week_start),
            "focus": "Third-Party Seeding",
            "actions": actions
        })

    # Weeks 5-8: Reddit + YouTube
    for week in range(5, 9):
        week_start = today + timedelta(weeks=week-1)
        actions = []
        if week == 5:
            actions = [
                f"Join 5 relevant subreddits in {industry}",
                "Post 3 genuinely helpful comments/answers (NO self-promotion)",
                "If YouTube: optimize top 5 video descriptions for AI (answer-first format)",
            ]
        elif week == 6:
            actions = [
                "Post 5 more helpful Reddit comments with data/insights",
                "Create 1 detailed Reddit post sharing original research or framework",
                "If YouTube: create 1 answer-optimized video for top AI query gap",
            ]
        elif week == 7:
            actions = [
                "Continue Reddit engagement (3-5 comments/week)",
                "If YouTube: add timestamps and full transcripts to top 10 videos",
                "Cross-post valuable Reddit content to YouTube community tab",
            ]
        elif week == 8:
            actions = [
                "Review Reddit engagement metrics",
                "If YouTube: create 1 comparison video (high citation format)",
                "Start building Reddit authority in 2-3 key subreddits",
            ]

        calendar.append({
            "week": week,
            "start_date": str(week_start),
            "focus": "Reddit + YouTube",
            "actions": actions
        })

    # Weeks 9-12: LinkedIn + maintenance
    for week in range(9, 13):
        week_start = today + timedelta(weeks=week-1)
        actions = []
        if week == 9:
            actions = [
                "Establish 3x/week LinkedIn posting cadence",
                "Post 1 original data/framework piece",
                "Follow up on all guest post and podcast pitches",
            ]
        elif week == 10:
            actions = [
                "LinkedIn: share 1 contrarian take with evidence",
                "Update 3 cornerstone content pages with fresh data",
                "Check which Reddit comments gained traction — double down",
            ]
        elif week == 11:
            actions = [
                "LinkedIn: post 1 case study breakdown",
                "Run Share of Model check to measure improvement",
                "Compare SoM before vs after 90-day campaign",
            ]
        elif week == 12:
            actions = [
                "Generate full measurement report",
                "Identify what worked best — double down for next quarter",
                "Plan next 90-day cycle based on results",
                "Update content freshness on all key pages",
            ]

        calendar.append({
            "week": week,
            "start_date": str(week_start),
            "focus": "LinkedIn + Maintenance",
            "actions": actions
        })

    plan = {
        "brand": brand,
        "industry": industry,
        "generated_date": str(today),
        "current_platform_count": platform_count,
        "target_platform_count": max(platform_count + 2, 4),
        "platform_scores": platform_scores,
        "total_score": f"{total_platform_score}/{max_possible}",
        "citation_boost_potential": "2.8x" if platform_count < 4 else "maintaining",
        "priorities": priorities,
        "gaps": gaps,
        "calendar": calendar,
        "key_metrics_to_track": [
            "Share of Model (monthly)",
            "Third-party mentions count",
            "Reddit karma/engagement in target subreddits",
            "YouTube AI-optimized video count",
            "LinkedIn post engagement rate",
            "AI referral traffic in GA4"
        ]
    }

    return plan


def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Distribution Planner")
    parser.add_argument("--assess", action="store_true", help="Generate assessment queries")
    parser.add_argument("--plan", action="store_true", help="Generate distribution plan from research")
    parser.add_argument("--brand", help="Brand name")
    parser.add_argument("--industry", help="Industry")
    parser.add_argument("--niche", help="Specific niche")
    parser.add_argument("--input", help="Input JSON file")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()
    result = None

    if args.assess:
        if not args.brand or not args.industry:
            print(json.dumps({"success": False, "message": "--brand and --industry required"}))
            sys.exit(1)
        result = generate_assessment_queries(args.brand, args.industry, args.niche)

    elif args.plan:
        if not args.input:
            print(json.dumps({"success": False, "message": "--input required"}))
            sys.exit(1)
        with open(args.input) as f:
            data = json.load(f)
        result = generate_distribution_plan(data)

    else:
        parser.print_help()
        sys.exit(1)

    output = json.dumps(result, indent=2, default=str)
    print(output)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(output)


if __name__ == "__main__":
    main()
