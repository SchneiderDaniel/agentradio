#!/usr/bin/env python3
"""
Passage-level citability analyzer for GEO optimization.

Takes crawl JSON, breaks each page into sections (by H2/H3),
scores each section 0-10 for AI citability.

Usage:
    python3 .claude/skills/ai-seo/scripts/analyze_citability.py --input .tmp/audit_crawl_domain.json

Output: JSON with per-section citability scores saved to .tmp/citability_<domain>.json
"""

import sys
import json
import re
import argparse
from pathlib import Path


def split_into_sections(content):
    """Split markdown content into sections by H2/H3 headings."""
    sections = []
    current_heading = "Introduction"
    current_content = []

    for line in content.split('\n'):
        if line.startswith('## ') or line.startswith('### '):
            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": '\n'.join(current_content).strip(),
                    "heading_level": 2 if current_heading.startswith('## ') else 3
                })
            current_heading = line.lstrip('#').strip()
            current_content = []
        else:
            current_content.append(line)

    # Don't forget the last section
    if current_content:
        sections.append({
            "heading": current_heading,
            "content": '\n'.join(current_content).strip(),
            "heading_level": 2
        })

    return sections


def score_section_citability(section):
    """Score a single section 0-10 for AI citability."""
    content = section["content"]
    heading = section["heading"]
    words = content.split()
    word_count = len(words)
    score = 0
    signals = []
    issues = []

    # 1. Length check (optimal: 134-167 words per citable passage)
    if 100 <= word_count <= 200:
        score += 2
        signals.append(f"Optimal passage length ({word_count} words)")
    elif 60 <= word_count <= 300:
        score += 1
        signals.append(f"Acceptable length ({word_count} words)")
    else:
        if word_count < 60:
            issues.append(f"Too short for citation ({word_count} words, need 100-200)")
        else:
            issues.append(f"Too long for single citation ({word_count} words) — consider splitting")

    # 2. Self-contained check — does it make sense without context?
    # Heuristic: starts with a definition or declarative statement
    first_sentence = content.split('.')[0] if '.' in content else content[:100]
    definitional = any(p in first_sentence.lower() for p in [
        ' is ', ' are ', ' refers to', ' means ', ' involves ', ' describes ',
        ' provides ', ' enables ', ' helps ', ' allows '
    ])
    if definitional:
        score += 1.5
        signals.append("Self-contained opening (definitional/declarative)")

    # 3. Statistics / data points
    stat_patterns = [
        r'\d+%', r'\d+x', r'\$[\d,]+', r'\d+\.\d+',
        r'(?:increased|decreased|grew|reduced|improved)\s+(?:by\s+)?\d+',
        r'\d+\s+(?:million|billion|thousand|percent)'
    ]
    stat_count = sum(len(re.findall(p, content, re.IGNORECASE)) for p in stat_patterns)
    if stat_count >= 3:
        score += 2
        signals.append(f"Data-rich ({stat_count} statistics/numbers)")
    elif stat_count >= 1:
        score += 1
        signals.append(f"Some data ({stat_count} statistics/numbers)")
    else:
        issues.append("No statistics or data points — AI models prefer fact-dense passages")

    # 4. Attribution / source citations
    citation_patterns = [
        r'according to', r'research (?:shows|suggests|found|indicates)',
        r'(?:a|the) (?:\d{4} )?study', r'source:', r'\(.*?\d{4}\)',
        r'per (?:a |the )?report', r'data from'
    ]
    citation_count = sum(len(re.findall(p, content, re.IGNORECASE)) for p in citation_patterns)
    if citation_count >= 2:
        score += 1.5
        signals.append(f"Well-attributed ({citation_count} source references)")
    elif citation_count >= 1:
        score += 0.5
        signals.append(f"Some attribution ({citation_count} source reference)")
    else:
        issues.append("No source attributions — reduces AI trust in passage")

    # 5. Question heading (matches query patterns)
    if heading.endswith('?') or heading.lower().startswith(('what ', 'how ', 'why ', 'when ', 'where ', 'who ', 'which ', 'can ', 'does ', 'is ', 'are ')):
        score += 1
        signals.append("Question-format heading (matches AI query patterns)")

    # 6. Lists / structured content
    list_items = len(re.findall(r'^\s*[-*•]\s', content, re.MULTILINE))
    if list_items >= 3:
        score += 1
        signals.append(f"Structured list ({list_items} items)")

    # 7. Expert quote present
    quote_patterns = [r'"[^"]{20,}"', r'\u201c[^\u201d]{20,}\u201d', r'>\s+.{20,}']
    has_quote = any(re.search(p, content) for p in quote_patterns)
    if has_quote:
        score += 1
        signals.append("Contains expert quote")

    # Cap at 10
    final_score = min(round(score, 1), 10)

    # Determine tier
    if final_score >= 7:
        tier = "highly_citable"
    elif final_score >= 4:
        tier = "moderately_citable"
    else:
        tier = "low_citability"

    return {
        "heading": heading,
        "word_count": word_count,
        "citability_score": final_score,
        "tier": tier,
        "signals": signals,
        "issues": issues
    }


def analyze_page(page_data):
    """Analyze all sections of a single page."""
    content = page_data.get("content", "") or page_data.get("markdown", "")
    url = page_data.get("url", "")

    if not content:
        return {
            "url": url,
            "sections": [],
            "page_citability_score": 0,
            "total_sections": 0,
            "highly_citable": 0,
            "needs_work": 0
        }

    sections = split_into_sections(content)
    scored_sections = [score_section_citability(s) for s in sections]

    # Filter out very short sections (nav items, etc.)
    scored_sections = [s for s in scored_sections if s["word_count"] >= 20]

    if not scored_sections:
        return {
            "url": url,
            "sections": [],
            "page_citability_score": 0,
            "total_sections": 0,
            "highly_citable": 0,
            "needs_work": 0
        }

    avg_score = sum(s["citability_score"] for s in scored_sections) / len(scored_sections)
    highly_citable = sum(1 for s in scored_sections if s["tier"] == "highly_citable")
    needs_work = sum(1 for s in scored_sections if s["tier"] == "low_citability")

    return {
        "url": url,
        "sections": scored_sections,
        "page_citability_score": round(avg_score, 1),
        "total_sections": len(scored_sections),
        "highly_citable": highly_citable,
        "needs_work": needs_work
    }


def main():
    parser = argparse.ArgumentParser(description="Passage-level citability analyzer")
    parser.add_argument("--input", required=True, help="Path to crawl results JSON")
    parser.add_argument("--output", help="Output path")

    args = parser.parse_args()

    with open(args.input) as f:
        crawl_data = json.load(f)

    pages = crawl_data.get("pages", crawl_data.get("page_analyses", []))
    page_results = [analyze_page(p) for p in pages]

    # Site-level aggregates
    all_sections = [s for p in page_results for s in p["sections"]]
    total_sections = len(all_sections)
    highly_citable = sum(1 for s in all_sections if s["tier"] == "highly_citable")
    low_citability = sum(1 for s in all_sections if s["tier"] == "low_citability")
    avg_citability = (
        sum(s["citability_score"] for s in all_sections) / total_sections
        if total_sections else 0
    )

    result = {
        "domain": crawl_data.get("domain", ""),
        "analysis_date": str(__import__('datetime').date.today()),
        "site_citability": {
            "average_score": round(avg_citability, 1),
            "total_sections_analyzed": total_sections,
            "highly_citable_sections": highly_citable,
            "highly_citable_pct": round(highly_citable / total_sections * 100, 1) if total_sections else 0,
            "low_citability_sections": low_citability,
            "low_citability_pct": round(low_citability / total_sections * 100, 1) if total_sections else 0,
        },
        "pages": page_results,
        "top_citable_sections": sorted(
            all_sections, key=lambda s: s["citability_score"], reverse=True
        )[:5],
        "worst_sections": sorted(
            [s for s in all_sections if s["word_count"] >= 50],
            key=lambda s: s["citability_score"]
        )[:5]
    }

    domain_slug = crawl_data.get("domain", "unknown").replace(".", "_")
    output_path = args.output or f".tmp/citability_{domain_slug}.json"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(json.dumps({
        "success": True,
        "output": output_path,
        "avg_citability": result["site_citability"]["average_score"],
        "total_sections": total_sections,
        "highly_citable_pct": result["site_citability"]["highly_citable_pct"]
    }, indent=2))


if __name__ == "__main__":
    main()
