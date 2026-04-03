#!/usr/bin/env python3
"""
Tool: AI SEO Report Formatter
Purpose: Generate markdown reports from audit scores, monitoring data, or measurement data.

Usage:
    python3 .claude/skills/ai-seo/scripts/format_report.py --input scored_audit.json --type audit
    python3 .claude/skills/ai-seo/scripts/format_report.py --input som_data.json --type monitor
    python3 .claude/skills/ai-seo/scripts/format_report.py --input measure_data.json --type measure

Output: Markdown report saved to data/ai_seo/<type>/<domain|brand>_YYYY-MM-DD.md
"""

import sys
import json
import argparse
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SKILL_DIR = Path(__file__).resolve().parent.parent
HTML_TEMPLATE_PATH = SKILL_DIR / "references" / "report_template.html"


def format_audit_report(data):
    """Format an audit scoring result into a readable markdown report."""
    domain = data.get("domain", "unknown")
    brand = data.get("brand_name", domain)
    score = data.get("overall_score", 0)
    tier_label = data.get("tier_label", "Unknown")
    tier_desc = data.get("tier_description", "")
    dim_scores = data.get("dimension_scores", {})
    dim_max = data.get("dimension_max", {})
    findings = data.get("detailed_findings", {})
    fixes = data.get("priority_fixes", [])
    pages_count = data.get("total_pages_analyzed", 0)
    audit_date = data.get("audit_date", str(date.today()))

    # Normalize score: raw may be out of 120, display as 0-100
    raw_score = data.get("raw_score", score)
    max_raw = data.get("max_raw_score", 120)
    if max_raw and max_raw != 100 and raw_score == score:
        score = round(raw_score / max_raw * 100)

    # Score bar visualization
    filled = int(score / 5)  # 20 chars for 100 points
    bar = f"[{'█' * filled}{'░' * (20 - filled)}] {score}/100"

    lines = [
        f"# AI SEO Audit Report: {brand}",
        f"",
        f"> **Domain**: {domain}",
        f"> **Date**: {audit_date}",
        f"> **Pages Analyzed**: {pages_count}",
        f"",
        f"---",
        f"",
        f"## Overall Score: {score}/100 — {tier_label}",
        f"",
        f"```",
        f"{bar}",
        f"```",
        f"",
        f"*{tier_desc}*",
        f"",
        f"---",
        f"",
        f"## Dimension Scores",
        f"",
        f"| Dimension | Score | Max | Status |",
        f"|---|---|---|---|",
    ]

    dim_labels = {
        "content_structure": "Content Structure",
        "schema_markup": "Schema Markup",
        "crawler_access": "Crawler Access",
        "multiplatform_presence": "Multi-Platform Presence",
        "entity_clarity": "Entity Clarity",
        "current_ai_visibility": "AI Visibility",
        "technical_foundations": "Technical Foundations",
        "eeat_signals": "E-E-A-T Signals",
        "geo_citability": "GEO Citability",
    }

    for key, label in dim_labels.items():
        s = dim_scores.get(key, 0)
        m = dim_max.get(key, 0)
        pct = (s / m * 100) if m else 0
        status = "Strong" if pct >= 70 else ("Needs Work" if pct >= 40 else "Critical")
        lines.append(f"| {label} | {s} | {m} | {status} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## Detailed Findings",
        f"",
    ])

    for dim_key, dim_label in dim_labels.items():
        dim_data = findings.get(dim_key, {})
        dim_findings = dim_data.get("findings", {})
        if dim_findings:
            lines.append(f"### {dim_label}")
            lines.append(f"")
            for check, finding in dim_findings.items():
                check_label = check.replace("_", " ").title()
                confidence = ""
                if isinstance(finding, dict):
                    confidence = f" [{finding.get('confidence', 'Hypothesis')}]"
                    finding = finding.get("text", str(finding))
                lines.append(f"- **{check_label}**{confidence}: {finding}")
            lines.append(f"")

    lines.extend([
        f"---",
        f"",
        f"## Priority Fixes (Ordered by Impact)",
        f"",
    ])

    for i, fix in enumerate(fixes, 1):
        confidence = fix.get('confidence', '')
        confidence_str = f" [{confidence}]" if confidence else ""
        lines.extend([
            f"### {i}. {fix['action']}{confidence_str}",
            f"",
            f"- **Dimension**: {fix['dimension']}",
            f"- **Impact**: {fix['impact']}",
            f"- **Effort**: {fix['effort']}",
        ])
        if fix.get('evidence'):
            lines.append(f"- *Evidence: {fix['evidence']}*")
        if fix.get('what_not_to_do'):
            lines.append(f"- **WARNING — Do NOT**: {fix['what_not_to_do']}")
        lines.append(f"")

    lines.extend([
        f"---",
        f"",
        f"## Key Statistics (Why This Matters)",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Schema markup citation boost | 2.5x higher AI citation rate |",
        f"| Answer-first citation boost | 2.3x more citations |",
        f"| In-text citations boost | +115% visibility |",
        f"| Expert quotes boost | +37% visibility |",
        f"| Statistics boost | +22% visibility |",
        f"| Multi-platform presence | 2.8x more likely in ChatGPT (4+ platforms) |",
        f"| AI referral conversion rate | 14.2% vs 2.8% Google organic |",
        f"",
        f"---",
        f"",
        f"*Generated by AI SEO Command Center | {audit_date}*",
    ])

    return "\n".join(lines)


def format_audit_fixes(data):
    """Generate a machine-readable JSON fix list for another AI model to consume and execute.

    Output is a lean structure: site context, then an ordered list of issues with
    what's broken, what to do, and ready-to-paste code/content where possible.
    """
    domain = data.get("domain", "unknown")
    brand = data.get("brand_name", domain)
    score = data.get("overall_score", 0)
    tier = data.get("tier_label", "Unknown")
    pages = data.get("page_analyses", [])
    fixes = data.get("priority_fixes", [])
    findings = data.get("detailed_findings", {})
    aggregates = data.get("site_aggregates", {})

    # Build per-page issue list
    page_issues = []
    for page in pages:
        url = page.get("url", "")
        issues = []

        if not page.get("has_schema"):
            issues.append({
                "issue": "missing_schema",
                "detail": "No JSON-LD structured data on this page"
            })

        if not page.get("has_faq"):
            issues.append({
                "issue": "missing_faq",
                "detail": "No FAQ section on this page"
            })

        if page.get("citation_count", 0) == 0:
            issues.append({
                "issue": "no_citations",
                "detail": "No source attributions or statistics with citations"
            })

        if page.get("quote_count", 0) == 0:
            issues.append({
                "issue": "no_expert_quotes",
                "detail": "No named expert quotes with credentials"
            })

        if page.get("question_heading_count", 0) == 0:
            issues.append({
                "issue": "no_question_headings",
                "detail": "No H2/H3 headings phrased as questions"
            })

        if page.get("stat_count", 0) < 3:
            issues.append({
                "issue": "low_stat_density",
                "detail": f"Only {page.get('stat_count', 0)} statistics found — aim for 5+ per page"
            })

        # Social meta / OG image issues
        social_meta = page.get("social_meta", {})
        if social_meta and not social_meta.get("has_og_image"):
            issues.append({
                "issue": "missing_og_image",
                "detail": "No og:image tag — shared links will have no preview image on social media"
            })
        if social_meta and not social_meta.get("complete"):
            missing = []
            if not social_meta.get("has_og_title"):
                missing.append("og:title")
            if not social_meta.get("has_og_description"):
                missing.append("og:description")
            if not social_meta.get("has_twitter_card"):
                missing.append("twitter:card")
            if missing:
                issues.append({
                    "issue": "incomplete_social_meta",
                    "detail": f"Missing social meta tags: {', '.join(missing)}"
                })

        # Content freshness
        if not page.get("last_modified"):
            issues.append({
                "issue": "no_freshness_date",
                "detail": "No visible update date — AI models deprioritize content without recency signals"
            })

        page_findings = page.get("findings", {})
        for key, finding in page_findings.items():
            if isinstance(finding, dict) and finding.get("status") == "fail":
                issues.append({
                    "issue": key,
                    "detail": finding.get("finding", "")
                })

        if issues:
            page_issues.append({
                "url": url,
                "page_type": page.get("page_type", "unknown"),
                "word_count": page.get("word_count", 0),
                "issues": issues
            })

    # Build site-level issues from findings and scores
    # Findings can be strings OR dicts with status — handle both
    site_issues = []

    def _extract_issues_from_dimension(dim_name, category):
        """Extract site-level issues from a dimension's scores and findings."""
        dim = findings.get(dim_name, {})
        if not isinstance(dim, dict):
            return
        dim_scores = dim.get("scores", {})
        dim_findings = dim.get("findings", {})

        for key, score in dim_scores.items():
            if isinstance(score, (int, float)) and score == 0:
                finding_text = dim_findings.get(key, "")
                if isinstance(finding_text, dict):
                    finding_text = finding_text.get("finding", str(finding_text))
                if finding_text:
                    site_issues.append({
                        "category": category,
                        "issue": key,
                        "detail": str(finding_text)
                    })

    # Crawler access — check for specific failures
    _extract_issues_from_dimension("crawler_access", "crawler_access")

    # Schema
    if aggregates.get("schema_coverage_pct", 0) == 0:
        site_issues.append({
            "category": "schema_markup",
            "issue": "no_schema_anywhere",
            "detail": "0% of pages have JSON-LD structured data"
        })

    # Sitemap missing
    if not data.get("site_aggregates", {}).get("sitemap_exists", True):
        # Check from page_analyses if not in aggregates
        pass  # Handled by priority_fixes now

    # E-E-A-T
    _extract_issues_from_dimension("eeat_signals", "eeat")

    # Entity clarity
    _extract_issues_from_dimension("entity_clarity", "entity_clarity")

    # Content structure — low scores
    _extract_issues_from_dimension("content_structure", "content_structure")

    # Multi-platform presence
    _extract_issues_from_dimension("multiplatform_presence", "multiplatform")

    # GEO citability
    _extract_issues_from_dimension("geo_citability", "geo_citability")

    # Build the output
    output = {
        "meta": {
            "domain": domain,
            "brand_name": brand,
            "audit_date": data.get("audit_date", str(date.today())),
            "overall_score": score,
            "tier": tier,
            "purpose": "Machine-readable fix list. Each item describes what is broken and what to do. Priority-ordered — fix from top to bottom."
        },
        "fixes": [],
        "site_issues": site_issues,
        "page_issues": page_issues
    }

    # Priority fixes — keep lean, add actionable context
    for fix in fixes:
        fix_entry = {
            "priority": fix.get("priority"),
            "dimension": fix.get("dimension"),
            "action": fix.get("action"),
            "effort": fix.get("effort"),
            "evidence": fix.get("evidence") if isinstance(fix.get("evidence"), str) else str(fix.get("evidence", "")),
        }
        if fix.get("what_not_to_do"):
            fix_entry["do_not"] = fix["what_not_to_do"]
        output["fixes"].append(fix_entry)

    return json.dumps(output, indent=2, ensure_ascii=False)


def format_monitor_report(data):
    """Format Share of Model monitoring data into a markdown report."""
    brand = data.get("brand", "Unknown")
    check_date = data.get("check_date", str(date.today()))
    total_queries = data.get("total_queries", 0)
    mention_count = data.get("mention_count", 0)
    mention_rate = data.get("mention_rate", 0)
    avg_position = data.get("avg_position_score", 0)
    primary_count = data.get("primary_count", 0)
    query_results = data.get("query_results", [])
    competitors = data.get("competitor_comparison", {})

    lines = [
        f"# Share of Model Report: {brand}",
        f"",
        f"> **Date**: {check_date}",
        f"> **Queries Tracked**: {total_queries}",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Mention Rate | {mention_rate:.1f}% ({mention_count}/{total_queries} queries) |",
        f"| Avg Position Score | {avg_position:.2f} / 3.0 |",
        f"| Primary Recommendations | {primary_count} |",
        f"",
    ]

    if competitors:
        lines.extend([
            f"## Competitor Comparison",
            f"",
            f"| Brand | Mention Rate | Avg Position |",
            f"|---|---|---|",
            f"| **{brand}** | **{mention_rate:.1f}%** | **{avg_position:.2f}** |",
        ])
        for comp_name, comp_data in competitors.items():
            lines.append(
                f"| {comp_name} | {comp_data.get('mention_rate', 0):.1f}% | "
                f"{comp_data.get('avg_position', 0):.2f} |"
            )
        lines.append(f"")

    if query_results:
        lines.extend([
            f"## Per-Query Results",
            f"",
            f"| Query | Mentioned | Position | Sentiment |",
            f"|---|---|---|---|",
        ])
        for qr in query_results:
            mentioned = "Yes" if qr.get("brand_mentioned") else "No"
            position = qr.get("mention_position", "absent")
            sentiment = qr.get("sentiment", "n/a")
            lines.append(f"| {qr.get('query', '')} | {mentioned} | {position} | {sentiment} |")
        lines.append(f"")

    lines.extend([
        f"---",
        f"",
        f"*Generated by AI SEO Command Center | {check_date}*",
    ])

    return "\n".join(lines)


def format_measure_report(data):
    """Format measurement/revenue impact data into a markdown report."""
    brand = data.get("brand", "Unknown")
    measure_date = data.get("date", str(date.today()))
    current_som = data.get("current_som", {})
    traffic_estimate = data.get("traffic_estimate", {})
    revenue_estimate = data.get("revenue_estimate", {})

    lines = [
        f"# Revenue Impact Report: {brand}",
        f"",
        f"> **Date**: {measure_date}",
        f"",
        f"---",
        f"",
        f"## Current AI Visibility",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Share of Model | {current_som.get('mention_rate', 0):.1f}% |",
        f"| Avg Position Score | {current_som.get('avg_position', 0):.2f} / 3.0 |",
        f"",
        f"## Estimated Traffic Impact",
        f"",
        f"| Source | Est. Monthly Visits | Conversion Rate | Est. Conversions |",
        f"|---|---|---|---|",
        f"| Google Organic | {traffic_estimate.get('google_organic', 'N/A')} | 2.8% | {traffic_estimate.get('google_conversions', 'N/A')} |",
        f"| AI Referral | {traffic_estimate.get('ai_referral', 'N/A')} | 14.2% | {traffic_estimate.get('ai_conversions', 'N/A')} |",
        f"",
        f"## Revenue Opportunity",
        f"",
        f"{revenue_estimate.get('narrative', 'Revenue estimate requires traffic data from Google Analytics.')}",
        f"",
        f"### How to get your traffic data",
        f"",
        f"1. Open Google Analytics 4",
        f"2. Go to **Reports > Acquisition > Traffic acquisition**",
        f"3. Look for these referral sources:",
        f"   - `chat.openai.com` (ChatGPT)",
        f"   - `perplexity.ai` (Perplexity)",
        f"   - `gemini.google.com` (Gemini)",
        f"   - `claude.ai` (Claude)",
        f"   - `copilot.microsoft.com` (Copilot)",
        f"4. These are your AI referral traffic numbers",
        f"",
        f"---",
        f"",
        f"*Generated by AI SEO Command Center | {measure_date}*",
    ]

    return "\n".join(lines)


def _score_color(score):
    """Return CSS color based on score."""
    if score >= 80:
        return "#00d68f"
    elif score >= 60:
        return "#ffc048"
    elif score >= 40:
        return "#ff9f43"
    return "#ff6b6b"


def _bar_color(pct):
    """Return bar fill color based on percentage."""
    if pct >= 70:
        return "#00d68f"
    elif pct >= 40:
        return "#ffc048"
    return "#ff6b6b"


def _finding_dot_color(finding_text):
    """Determine dot color from finding text heuristics."""
    lower = finding_text.lower()
    if any(w in lower for w in ["not found", "not checked", "missing", "0%", "0 schema", "none", "no "]):
        return "#ff6b6b"
    if any(w in lower for w in ["requires", "partial", "manual"]):
        return "#ffc048"
    return "#00d68f"


def _escape_html(text):
    """Escape HTML special characters."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _dim_tooltips():
    """Return tooltip explanations for each dimension."""
    return {
        "content_structure": (
            "AI models extract answers from pages that lead with a clear, direct answer. "
            "Pages with <span class='tooltip-stat'>answer-first format get cited 2.3x more</span> by ChatGPT and Perplexity. "
            "Statistics, citations, and expert quotes make your content more quotable."
            "<span class='tooltip-source'>Source: Digital Bloom IQ, 2025</span>"
        ),
        "schema_markup": (
            "JSON-LD schema tells AI crawlers exactly what your content means. "
            "Sites with structured data are <span class='tooltip-stat'>2.5x more likely to appear in AI-generated answers</span>. "
            "FAQPage schema directly feeds the Q&A pipelines that power ChatGPT and Perplexity."
            "<span class='tooltip-source'>Source: Stackmatix, 2025</span>"
        ),
        "crawler_access": (
            "AI models can only cite what they can see. If GPTBot, ClaudeBot, or PerplexityBot are blocked in robots.txt, "
            "your site is invisible to those platforms. "
            "llms.txt is an emerging standard that tells AI crawlers what your site is about in their language."
            "<span class='tooltip-source'>Source: llmstxt.org</span>"
        ),
        "multiplatform_presence": (
            "85% of brand citations in AI responses come from third-party sources, not your own site. "
            "Brands present on <span class='tooltip-stat'>4+ platforms are 2.8x more likely</span> to appear in ChatGPT. "
            "Reddit appears in 24% of AI responses. LinkedIn is the #2 most-cited domain in AI search."
            "<span class='tooltip-source'>Source: OtterlyAI 2026 + ALM Corp 2026</span>"
        ),
        "entity_clarity": (
            "AI models need to confidently identify WHO you are before citing you. "
            "Consistent brand naming, an About page, author credentials, and linked social profiles "
            "help models build an entity graph for your brand. Without this, AI can't distinguish you from noise."
            "<span class='tooltip-source'>Source: Google E-E-A-T guidelines</span>"
        ),
        "current_ai_visibility": (
            "This measures whether AI models are ALREADY citing you. "
            "We query Perplexity and check Google AI Overviews with your industry's questions. "
            "A zero score means you're invisible to AI search right now — but it also means there's massive upside."
            "<span class='tooltip-source'>Baseline measurement</span>"
        ),
        "technical_foundations": (
            "HTTPS, mobile-friendliness, page speed, and clean URLs are table stakes. "
            "They don't directly boost AI citations, but their absence can prevent crawling entirely. "
            "Think of this as the foundation everything else builds on."
            "<span class='tooltip-source'>Source: Google Core Web Vitals</span>"
        ),
        "eeat_signals": (
            "Experience, Expertise, Authoritativeness, and Trustworthiness — Google's quality framework that AI models also use. "
            "Author bios with credentials, first-person case studies, testimonials, and transparent business details "
            "all signal to AI that your content comes from a <span class='tooltip-stat'>credible, real-world source</span>. "
            "Without E-E-A-T signals, AI models treat your content as generic."
            "<span class='tooltip-source'>Source: Google Search Quality Rater Guidelines, 2024</span>"
        ),
        "geo_citability": (
            "Generative Engine Optimization — how likely AI models are to quote or cite your content verbatim. "
            "This measures quotable formatting: concise definitions, numbered lists, stat-backed claims, "
            "and <span class='tooltip-stat'>self-contained answer blocks</span> that AI can extract without modification. "
            "High GEO scores correlate with appearing as a cited source in AI responses."
            "<span class='tooltip-source'>Source: GEO Framework, Princeton/Georgia Tech, 2024</span>"
        ),
    }


def _fix_tooltips():
    """Return tooltip explanations keyed by fix action keywords."""
    return {
        "JSON-LD structured data": (
            "JSON-LD is code you add to your pages that tells AI models the structure of your content — "
            "what's a question, what's an answer, who wrote it, when it was updated. "
            "Without it, AI models have to guess. With it, they can extract and cite you precisely. "
            "<span class='tooltip-stat'>2.5x citation boost</span> is the highest-leverage single fix."
            "<span class='tooltip-source'>Source: Stackmatix, 2025</span>"
        ),
        "answer the core question": (
            "AI models scan for a direct answer in the first 40-60 words of a page. "
            "If your page opens with a tagline or marketing fluff, the AI skips to a competitor who answers directly. "
            "<span class='tooltip-stat'>2.3x more citations</span> for pages that lead with the answer."
            "<span class='tooltip-source'>Source: Digital Bloom IQ, 2025</span>"
        ),
        "statistics with source attributions": (
            "When AI models find a stat like '14.2% conversion rate (Source: ALM Corp)', they treat it as citable fact. "
            "Pages with in-text citations see a <span class='tooltip-stat'>+115% visibility boost</span> — "
            "the single biggest content-level signal."
            "<span class='tooltip-source'>Source: Digital Bloom IQ, 2025</span>"
        ),
        "robots.txt": (
            "Your robots.txt file tells crawlers what they can and can't access. "
            "Many sites accidentally block GPTBot or PerplexityBot. "
            "If AI crawlers can't read your pages, nothing else you do matters."
            "<span class='tooltip-source'>Quick fix: check /robots.txt on your site</span>"
        ),
        "FAQ sections": (
            "FAQ sections with FAQPage schema are directly extracted by AI Q&A pipelines. "
            "When someone asks ChatGPT a question that matches your FAQ, "
            "the model can pull your answer verbatim. Low effort, high payoff."
            "<span class='tooltip-source'>Source: Google Search Central</span>"
        ),
        "Reddit, YouTube, and LinkedIn": (
            "AI models heavily weight third-party validation. "
            "Reddit appears in <span class='tooltip-stat'>24% of AI responses</span>, "
            "YouTube in <span class='tooltip-stat'>29.5% of AI Overviews</span>. "
            "Your own site is only one signal — what others say about you matters more."
            "<span class='tooltip-source'>Source: OtterlyAI 2026 + Digiday</span>"
        ),
        "expert quotes": (
            "Named expert quotes with credentials ('John Smith, CTO at Acme') "
            "give AI models a quotable, authoritative source. "
            "<span class='tooltip-stat'>+37% visibility boost</span> from expert quotations."
            "<span class='tooltip-source'>Source: Digital Bloom IQ, 2025</span>"
        ),
        "llms.txt": (
            "llms.txt is a new standard (like robots.txt but for AI). It tells AI crawlers: "
            "here's what our site is about, here are our key pages, here's how to describe us. "
            "Early-mover advantage — most sites don't have one yet."
            "<span class='tooltip-source'>Source: llmstxt.org</span>"
        ),
    }


def _generate_optimization_section(opt_data):
    """Generate HTML for Section 2: How to Fix It."""
    if not opt_data:
        return ""

    parts = []

    # Projected Score
    projected = opt_data.get("projected_score")
    if projected:
        current = projected.get("current", 0)
        proj = projected.get("projected", 0)
        breakdown = _escape_html(projected.get("breakdown", ""))
        current_color = _score_color(current)
        proj_color = _score_color(proj)
        parts.append(
            f'<div class="projected-score">'
            f'<div class="score-compare">'
            f'<div class="score-box"><div class="score-val" style="color:{current_color}">{current}</div>'
            f'<div class="score-lbl">Current Score</div></div>'
            f'<div class="score-arrow">&#8594;</div>'
            f'<div class="score-box"><div class="score-val" style="color:{proj_color}">{proj}</div>'
            f'<div class="score-lbl">Projected Score</div></div>'
            f'</div>'
            f'<div class="score-breakdown">{breakdown}</div>'
            f'</div>'
        )

    # Answer-First Rewrite
    answer_first = opt_data.get("answer_first")
    if answer_first:
        recommended = _escape_html(answer_first.get("recommended", ""))
        current = _escape_html(answer_first.get("current", ""))
        word_count = answer_first.get("word_count", 0)
        why = _escape_html(answer_first.get("why", ""))

        parts.append(
            f'<h3 style="font-size:1.15rem;margin-bottom:16px;">Answer-First Rewrite</h3>'
        )
        parts.append(
            f'<div class="before-after">'
            f'<div class="before-col">'
            f'<div class="col-label">&#10005; Current Opening</div>'
            f'<div class="col-text">{current}</div>'
            f'</div>'
            f'<div class="after-col">'
            f'<div class="col-label">&#10003; Recommended Opening</div>'
            f'<div class="col-text">{recommended}</div>'
            f'</div>'
            f'</div>'
        )
        parts.append(
            f'<div class="answer-preview">'
            f'<div class="preview-label">Preview — Optimized Opening</div>'
            f'<div class="preview-text">{recommended}</div>'
            f'<div class="preview-meta"><span>{word_count} words</span></div>'
            f'<div class="preview-why">{why}</div>'
            f'</div>'
        )

    # Priority Fix Cards
    fixes = opt_data.get("fixes", [])
    if fixes:
        parts.append('<h3 style="font-size:1.15rem;margin-bottom:16px;">Priority Fixes</h3>')
        for i, fix in enumerate(fixes, 1):
            effort = fix.get("effort", "medium")
            effort_class = "low" if "low" in effort else ("high" if "high" in effort else "medium")
            time_est = _escape_html(fix.get("time_estimate", ""))
            impact = _escape_html(fix.get("impact", ""))
            title = _escape_html(fix.get("title", ""))
            before = _escape_html(fix.get("before", ""))
            after = _escape_html(fix.get("after", ""))

            parts.append(
                f'<div class="opt-fix-card">'
                f'<div class="opt-fix-header">'
                f'<div class="opt-fix-number">{i}</div>'
                f'<div class="opt-fix-title">{title}</div>'
                f'<div class="opt-fix-tags">'
                f'<span class="fix-tag fix-tag-effort-{effort_class}">Effort: {_escape_html(effort)}</span>'
                f'<span class="effort-time">{time_est}</span>'
                f'<span class="fix-tag fix-tag-impact">{impact}</span>'
                f'</div>'
                f'</div>'
                f'<div class="before-after">'
                f'<div class="before-col">'
                f'<div class="col-label">&#10005; Current</div>'
                f'<div class="col-text">{before}</div>'
                f'</div>'
                f'<div class="after-col">'
                f'<div class="col-label">&#10003; Recommended</div>'
                f'<div class="col-text">{after}</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

    # FAQ Section Preview
    faq_pairs = opt_data.get("faq_pairs", [])
    if faq_pairs:
        parts.append('<h3 style="font-size:1.15rem;margin:24px 0 16px;">FAQ Section Preview</h3>')
        for pair in faq_pairs:
            q = _escape_html(pair.get("question", ""))
            a = _escape_html(pair.get("answer", ""))
            parts.append(
                f'<details class="accordion-item">'
                f'<summary>{q}</summary>'
                f'<div class="accordion-body">{a}</div>'
                f'</details>'
            )

    # Expert Quote
    expert_quote = opt_data.get("expert_quote")
    if expert_quote:
        quote_text = _escape_html(expert_quote.get("quote", ""))
        attribution = _escape_html(expert_quote.get("attribution", ""))
        credentials = _escape_html(expert_quote.get("credentials", ""))
        needs_custom = expert_quote.get("needs_customization", False)

        parts.append(
            '<h3 style="font-size:1.15rem;margin:24px 0 16px;">Expert Quote</h3>'
        )
        note_html = ""
        if needs_custom:
            note_html = '<div class="quote-note">This quote needs customization — verify the attribution and adjust wording to match your voice.</div>'

        parts.append(
            f'<div class="quote-card">'
            f'<blockquote>&ldquo;{quote_text}&rdquo;</blockquote>'
            f'<div class="quote-attribution">{attribution}</div>'
            f'<div class="quote-credentials">{credentials}</div>'
            f'{note_html}'
            f'</div>'
        )

    return "\n  ".join(parts)


def _generate_technical_section(opt_data):
    """Generate HTML for Section 3: Copy & Paste (Technical Implementation)."""
    if not opt_data:
        return ""

    schema_blocks = opt_data.get("schema_blocks", [])
    llms_txt = opt_data.get("llms_txt", "")

    if not schema_blocks and not llms_txt:
        return ""

    parts = []

    # Schema Markup blocks
    if schema_blocks:
        parts.append('<h3 style="font-size:1.15rem;margin-bottom:16px;">Schema Markup (JSON-LD)</h3>')
        for block in schema_blocks:
            label = _escape_html(block.get("label", "Schema"))
            json_content = _escape_html(block.get("json", ""))
            parts.append(
                f'<div class="code-label">{label} <span class="copy-hint">Copy</span></div>'
                f'<div class="code-block">&lt;script type="application/ld+json"&gt;\n{json_content}\n&lt;/script&gt;</div>'
            )

    # llms.txt
    if llms_txt:
        parts.append(
            '<h3 style="font-size:1.15rem;margin:24px 0 16px;">llms.txt</h3>'
            '<div class="code-label">llms.txt <span class="copy-hint">Copy</span></div>'
            '<p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:12px;">'
            'Save as <code style="background:var(--surface-2);padding:2px 6px;border-radius:4px;">/llms.txt</code> at your domain root</p>'
            f'<div class="code-block">{_escape_html(llms_txt)}</div>'
        )

    return "\n  ".join(parts)


def _extract_site_context(audit_data):
    """Extract real content from crawl data for generating concrete recommendations."""
    pages = audit_data.get("page_analyses", [])
    brand = audit_data.get("brand_name", "Company")
    domain = audit_data.get("domain", "example.com")

    # Pull meta description (best short summary of the business)
    meta_desc = ""
    for p in pages:
        findings = p.get("findings", {})
        content = p.get("content", "") or ""
        if not meta_desc and content:
            # First substantive paragraph as fallback
            for para in content.split('\n\n'):
                para = para.strip()
                if para and not para.startswith('#') and len(para.split()) >= 10:
                    meta_desc = para[:200]
                    break

    # Pull from eeat_data for experience claims
    eeat = audit_data.get("eeat_data", {})
    experience_finding = eeat.get("experience", {}).get("finding", "")

    # Pull services/sections from page content
    services = []
    headings = []
    for p in pages:
        content = p.get("content", "") or ""
        import re
        for match in re.finditer(r'^###?\s+(.+)$', content, re.MULTILINE):
            h = match.group(1).strip()
            headings.append(h)
            # Service-like headings
            if any(w in h.lower() for w in ["audit", "transform", "optimize", "maintain",
                                             "consult", "develop", "design", "implement",
                                             "migrate", "support", "train", "custom"]):
                services.append(h)

    # Pull testimonial quotes
    quotes = []
    for p in pages:
        content = p.get("content", "") or ""
        import re
        for match in re.finditer(r'["\u201c]([^"\u201d]{20,200})["\u201d]', content):
            quotes.append(match.group(1))

    return {
        "brand": brand,
        "domain": domain,
        "meta_desc": meta_desc,
        "experience_finding": experience_finding,
        "services": services[:5],
        "headings": headings[:10],
        "quotes": quotes[:3],
    }


def _build_optimization_from_fixes(fixes, audit_data):
    """Build CONCRETE optimization data from audit findings — not generic templates.

    Pulls real data from the crawl to generate:
    - Pre-filled schema JSON-LD (not placeholders)
    - A draft answer-first paragraph
    - Implementation notes for the team
    """
    import json as _json

    ctx = _extract_site_context(audit_data)
    brand = ctx["brand"]
    domain = ctx["domain"]
    biz_type = audit_data.get("business_type", "unknown")

    opt = {"fixes": [], "schema_blocks": [], "llms_txt": ""}

    # === PRIORITY FIXES with implementation guidance ===
    for fix in fixes:
        action = fix.get("action", "")
        impl_note = ""

        # Add team implementation guidance based on fix type
        dimension = fix.get("dimension", "")
        if "schema" in dimension.lower():
            impl_note = "WHO: Your developer or CMS admin. WHERE: Add to <head> section of every page. HOW: Paste the JSON-LD from the Copy & Paste tab. CUSTOMIZE: Replace any remaining {{brackets}} with your actual content."
        elif "content" in dimension.lower() and "answer" in action.lower():
            impl_note = "WHO: Your content writer or marketing lead. WHERE: Below the hero section, above the fold. HOW: Use the draft paragraph below as a starting point — rewrite in your brand voice. Keep it 40-60 words, factual, no fluff."
        elif "content" in dimension.lower():
            impl_note = "WHO: Content team. HOW: Add real statistics from your internal data (client results, project counts, time savings). Always attribute: 'According to [source]...' format. AI models cross-reference claims."
        elif "crawler" in dimension.lower():
            impl_note = "WHO: Your developer or DevOps. WHERE: robots.txt at domain root. HOW: Add explicit User-agent rules for GPTBot, ClaudeBot, PerplexityBot. Takes 5 minutes."
        elif "platform" in dimension.lower():
            impl_note = "WHO: Marketing team. HOW: This is ongoing, not a one-time fix. Start with LinkedIn (post 2x/week about your work). Reddit (answer questions in your industry subreddits). YouTube (even short case study videos count)."
        elif "e-e-a-t" in dimension.lower():
            impl_note = "WHO: Leadership + content team. HOW: Add a team page with photos and credentials. Turn your best client results into detailed case studies with specific numbers. Add author bylines to all content."

        opt_fix = {
            "title": action[:100],
            "before": fix.get("evidence", ""),
            "after": action,
            "impact": fix.get("impact", ""),
            "effort": fix.get("effort", "medium"),
            "time_estimate": "",
        }

        if fix.get("what_not_to_do"):
            opt_fix["after"] += f"\n\n\u26a0\ufe0f {fix['what_not_to_do']}"

        if impl_note:
            opt_fix["after"] += f"\n\n\ud83d\udccb IMPLEMENTATION: {impl_note}"

        opt["fixes"].append(opt_fix)

    # === ANSWER-FIRST PARAGRAPH (pre-written draft) ===
    if ctx["meta_desc"]:
        # Generate a concrete answer-first paragraph from actual site data
        services_text = ", ".join(ctx["services"][:3]) if ctx["services"] else "consulting and implementation"
        answer_first = (
            f"{brand} is a {biz_type.replace('_', ' ')} that {ctx['meta_desc'].rstrip('.')}. "
        )
        # Add a proof point if we have one
        if ctx["quotes"]:
            answer_first += f'Clients report results like "{ctx["quotes"][0][:80]}."'
        elif ctx["experience_finding"]:
            # Extract a number from the experience finding
            import re
            numbers = re.findall(r'[\$\d][\d,.]+[KMB+]*', ctx["experience_finding"])
            if numbers:
                answer_first += f"With proven results including {numbers[0]} in documented client outcomes."

        word_count = len(answer_first.split())

        opt["answer_first"] = {
            "recommended": answer_first,
            "current": "No answer-first paragraph found — site opens with a tagline/slogan.",
            "word_count": word_count,
            "why": (
                "AI models skip taglines and slogans. They look for the first declarative paragraph "
                "that answers 'What does this company do?' This paragraph should appear BELOW your "
                "hero section, not replace it. Rewrite this draft in your brand voice — keep it "
                "40-60 words, factual, and specific."
            )
        }

    # === SCHEMA BLOCKS (pre-filled from real data) ===
    meta_desc_clean = ctx["meta_desc"][:160] if ctx["meta_desc"] else f"{brand} provides professional services"

    # Organization schema — always needed, pre-filled
    org_schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "url": f"https://{domain}",
        "description": meta_desc_clean,
        "sameAs": []
    }

    # Try to extract social links from entity_data
    entity = audit_data.get("entity_data", {})
    profiles_finding = entity.get("profiles_finding", "")
    if "twitter" in profiles_finding.lower() or "linkedin" in profiles_finding.lower():
        org_schema["sameAs"].append(f"https://linkedin.com/company/{brand.lower().replace(' ', '-')} [VERIFY THIS URL]")
        org_schema["sameAs"].append(f"https://twitter.com/{brand.lower().replace(' ', '')} [VERIFY THIS URL]")
    else:
        org_schema["sameAs"] = [
            "[ADD YOUR LINKEDIN COMPANY URL]",
            "[ADD YOUR TWITTER/X URL]",
            "[ADD YOUR YOUTUBE CHANNEL URL]"
        ]

    opt["schema_blocks"].append({
        "label": f"Organization Schema — paste into <head> of every page",
        "json": _json.dumps(org_schema, indent=2)
    })

    # Business-type-specific schemas
    if biz_type == "agency":
        for svc in (ctx["services"][:2] or ["Consulting"]):
            svc_schema = {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": svc,
                "provider": {"@type": "Organization", "name": brand},
                "description": f"{brand}'s {svc.lower()} service [YOUR TEAM: write 1-2 sentences describing this service and its outcomes]",
                "areaServed": "[YOUR COUNTRY/REGION, e.g., 'United States' or 'Global']"
            }
            opt["schema_blocks"].append({
                "label": f"Service Schema: {svc} — paste into the relevant service page",
                "json": _json.dumps(svc_schema, indent=2)
            })

        # Review schema from testimonials
        if ctx["quotes"]:
            review_schema = {
                "@context": "https://schema.org",
                "@type": "Review",
                "reviewBody": ctx["quotes"][0][:200],
                "author": {"@type": "Person", "name": "[CLIENT NAME — get permission first]"},
                "itemReviewed": {"@type": "Organization", "name": brand},
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": "5",
                    "bestRating": "5"
                }
            }
            opt["schema_blocks"].append({
                "label": "Review Schema — paste near your testimonials section",
                "json": _json.dumps(review_schema, indent=2)
            })

    elif biz_type == "saas":
        app_schema = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": brand,
            "applicationCategory": "BusinessApplication [CHANGE TO YOUR CATEGORY]",
            "operatingSystem": "Web",
            "description": meta_desc_clean,
            "offers": {
                "@type": "Offer",
                "price": "[YOUR STARTING PRICE]",
                "priceCurrency": "USD"
            }
        }
        opt["schema_blocks"].append({
            "label": f"SoftwareApplication Schema — paste into your pricing/product page",
            "json": _json.dumps(app_schema, indent=2)
        })

    elif biz_type == "ecommerce":
        product_schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "[PRODUCT NAME]",
            "brand": {"@type": "Brand", "name": brand},
            "description": "[PRODUCT DESCRIPTION]",
            "offers": {
                "@type": "Offer",
                "price": "[PRICE]",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock"
            }
        }
        opt["schema_blocks"].append({
            "label": "Product Schema — paste into each product page (customize per product)",
            "json": _json.dumps(product_schema, indent=2)
        })

    elif biz_type == "local_service":
        local_schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": brand,
            "url": f"https://{domain}",
            "description": meta_desc_clean,
            "telephone": "[YOUR PHONE NUMBER]",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "[YOUR ADDRESS]",
                "addressLocality": "[CITY]",
                "addressRegion": "[STATE]",
                "postalCode": "[ZIP]"
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": "[YOUR LATITUDE]",
                "longitude": "[YOUR LONGITUDE]"
            },
            "areaServed": "[YOUR SERVICE AREA]",
            "openingHours": "[e.g., Mo-Fr 08:00-18:00]"
        }
        opt["schema_blocks"].append({
            "label": "LocalBusiness Schema — paste into your homepage <head>",
            "json": _json.dumps(local_schema, indent=2)
        })

    # === FAQ PAIRS (from headings that look like questions) ===
    faq_pairs = []
    for h in ctx["headings"]:
        if h.endswith("?"):
            faq_pairs.append({
                "question": h,
                "answer": f"[YOUR TEAM: Write a 40-80 word answer. Lead with the direct answer, include one specific number or data point. Keep it self-contained — AI models extract FAQ answers verbatim.]"
            })
    # If no question headings found, suggest common ones for the business type
    if not faq_pairs:
        type_faqs = {
            "agency": [
                f"What does {brand} do?",
                f"How much does it cost to work with {brand}?",
                f"What industries does {brand} serve?",
                f"How long does a typical project take?",
                f"What makes {brand} different from other consultancies?",
            ],
            "saas": [
                f"What is {brand}?",
                f"How much does {brand} cost?",
                f"Does {brand} offer a free trial?",
                f"What integrations does {brand} support?",
                f"Is {brand} suitable for enterprise teams?",
            ],
            "ecommerce": [
                f"What is {brand}'s return policy?",
                f"Does {brand} offer free shipping?",
                f"What materials does {brand} use?",
                f"Where is {brand} based?",
                f"How do I track my {brand} order?",
            ],
            "local_service": [
                f"What areas does {brand} serve?",
                f"Does {brand} offer emergency services?",
                f"How much does {brand} charge?",
                f"Is {brand} licensed and insured?",
                f"How do I schedule an appointment with {brand}?",
            ],
        }
        for q in type_faqs.get(biz_type, type_faqs["agency"]):
            faq_pairs.append({
                "question": q,
                "answer": "[YOUR TEAM: Write a 40-80 word answer. Be specific — use real numbers, name your services, mention your process. AI models cite FAQ answers that contain concrete details, not vague marketing copy.]"
            })

    if faq_pairs:
        opt["faq_pairs"] = faq_pairs[:6]

    # === LLMS.TXT (pre-filled) ===
    llms_findings = audit_data.get("detailed_findings", {}).get("crawler_access", {}).get("findings", {})
    if "not found" in llms_findings.get("llms_txt", ""):
        services_list = "\n".join(f"- [{s}](https://{domain}/services): {s}" for s in ctx["services"][:4]) if ctx["services"] else f"- [{brand} Services](https://{domain}/services): Our service offerings"

        opt["llms_txt"] = (
            f"# {brand}\n"
            f"> {meta_desc_clean}\n\n"
            f"## About\n"
            f"- [{brand} Homepage](https://{domain}): Main website\n"
            f"- [{brand} About](https://{domain}/about): Company background and team\n\n"
            f"## Services\n"
            f"{services_list}\n\n"
            f"## Resources\n"
            f"- [{brand} Blog](https://{domain}/blog): Industry insights and thought leadership\n"
            f"- [{brand} Case Studies](https://{domain}/case-studies): Client results and outcomes\n"
        )

    # === PROJECTED SCORE ===
    # Calculate what the score would be if top fixes are implemented
    current_score = audit_data.get("overall_score", 0)
    dim_scores = audit_data.get("dimension_scores", {})
    dim_max = audit_data.get("dimension_max", {})

    # Estimate points gained per fix
    projected_gains = {}
    for fix in fixes:
        dim = fix.get("dimension", "").lower()
        if "schema" in dim and dim_scores.get("schema_markup", 0) < 12:
            projected_gains["schema_markup"] = min(16, dim_max.get("schema_markup", 20)) - dim_scores.get("schema_markup", 0)
        elif "content" in dim and "answer" in fix.get("action", "").lower():
            projected_gains["content_structure"] = min(5, dim_max.get("content_structure", 25) - dim_scores.get("content_structure", 0))
        elif "crawler" in dim:
            projected_gains["crawler_access"] = min(4, dim_max.get("crawler_access", 15) - dim_scores.get("crawler_access", 0))
        elif "e-e-a-t" in dim:
            projected_gains["eeat_signals"] = min(4, dim_max.get("eeat_signals", 10) - dim_scores.get("eeat_signals", 0))
        elif "citability" in dim or "geo" in dim:
            projected_gains["geo_citability"] = min(4, dim_max.get("geo_citability", 10) - dim_scores.get("geo_citability", 0))

    total_gain_raw = sum(projected_gains.values())
    max_total = audit_data.get("max_score", 120)
    projected_score = min(100, current_score + round(total_gain_raw / max_total * 100))

    breakdown_parts = []
    for dim, gain in sorted(projected_gains.items(), key=lambda x: -x[1]):
        dim_label = dim.replace("_", " ").title()
        breakdown_parts.append(f"+{round(gain / max_total * 100)} from {dim_label}")

    opt["projected_score"] = {
        "current": current_score,
        "projected": projected_score,
        "breakdown": " | ".join(breakdown_parts) if breakdown_parts else "No significant gains estimated"
    }

    return opt


def format_audit_html(data, optimization_data=None):
    """Generate a styled HTML audit report from scored data."""
    template = HTML_TEMPLATE_PATH.read_text()

    domain = data.get("domain", "unknown")
    brand = data.get("brand_name", domain)
    score = data.get("overall_score", 0)
    tier_key = data.get("tier", "not_ready")
    tier_label = data.get("tier_label", "Unknown")
    tier_desc = data.get("tier_description", "")
    dim_scores = data.get("dimension_scores", {})
    dim_max = data.get("dimension_max", {})
    findings = data.get("detailed_findings", {})
    fixes = data.get("priority_fixes", [])
    pages_count = data.get("total_pages_analyzed", 0)
    audit_date = data.get("audit_date", str(date.today()))
    business_type = data.get("business_type", "")

    # Normalize score: raw may be out of 120, display as 0-100
    raw_score = data.get("raw_score", score)
    max_raw = data.get("max_raw_score", 120)
    if max_raw and max_raw != 100 and raw_score == score:
        score = round(raw_score / max_raw * 100)

    # Score ring math
    circumference = 2 * 3.14159 * 52  # r=52
    dash_offset = circumference * (1 - score / 100)
    score_color = _score_color(score)

    # Tooltip data
    dim_tips = _dim_tooltips()
    fix_tips = _fix_tooltips()

    # Dimension bars
    dim_labels = {
        "content_structure": "Content Structure",
        "schema_markup": "Schema Markup",
        "crawler_access": "Crawler Access",
        "multiplatform_presence": "Multi-Platform Presence",
        "entity_clarity": "Entity Clarity",
        "current_ai_visibility": "AI Visibility",
        "technical_foundations": "Technical Foundations",
        "eeat_signals": "E-E-A-T Signals",
        "geo_citability": "GEO Citability",
    }
    # Custom gradient colors for specific dimensions
    dim_gradient_colors = {
        "eeat_signals": "linear-gradient(90deg, #7c3aed, #a78bfa)",     # purple gradient
        "geo_citability": "linear-gradient(90deg, #2563eb, #60a5fa)",    # blue gradient
    }
    bars_html = []
    for key, label in dim_labels.items():
        s = dim_scores.get(key, 0)
        m = dim_max.get(key, 0)
        pct = (s / m * 100) if m else 0
        if key in dim_gradient_colors:
            bar_bg = dim_gradient_colors[key]
        else:
            bar_bg = _bar_color(pct)
        tip = dim_tips.get(key, "")
        tooltip_html = (
            f'<span class="tooltip-wrap">'
            f'<span class="tooltip-icon">?</span>'
            f'<span class="tooltip-bubble">{tip}</span>'
            f'</span>'
        ) if tip else ""
        bars_html.append(
            f'<div class="dim-row">'
            f'<div class="dim-label">{label}{tooltip_html}</div>'
            f'<div class="dim-bar-track"><div class="dim-bar-fill" style="width:{pct:.0f}%;background:{bar_bg}"></div></div>'
            f'<div class="dim-score">{s}/{m}</div>'
            f'</div>'
        )

    # Finding cards (2-column grid)
    cards_html = []
    for dim_key, dim_label in dim_labels.items():
        dim_data = findings.get(dim_key, {})
        dim_findings = dim_data.get("findings", {})
        if not dim_findings:
            continue
        items = []
        for check, finding in dim_findings.items():
            check_label = check.replace("_", " ").title()
            # Support finding as dict with text + confidence
            confidence = ""
            finding_text = finding
            if isinstance(finding, dict):
                finding_text = finding.get("text", str(finding))
                confidence = finding.get("confidence", "")
            dot_color = _finding_dot_color(str(finding_text))
            confidence_badge = ""
            if confidence:
                conf_colors = {
                    "Confirmed": ("#00d68f", "#0a2e1f"),
                    "Likely": ("#ffc048", "#2e2510"),
                    "Hypothesis": ("#8b95a5", "#1e2228"),
                }
                bg, text_bg = conf_colors.get(confidence, ("#8b95a5", "#1e2228"))
                confidence_badge = (
                    f'<span style="display:inline-block;font-size:0.65rem;padding:1px 6px;'
                    f'border-radius:4px;background:{text_bg};color:{bg};'
                    f'border:1px solid {bg};margin-left:6px;vertical-align:middle;">'
                    f'{_escape_html(confidence)}</span>'
                )
            items.append(
                f'<div class="finding-item">'
                f'<div class="finding-dot" style="background:{dot_color}"></div>'
                f'<div><div class="finding-label">{_escape_html(check_label)}{confidence_badge}</div>'
                f'<div class="finding-text">{_escape_html(finding_text)}</div></div>'
                f'</div>'
            )
        cards_html.append(
            f'<div class="card"><h3>{dim_label}</h3>{"".join(items)}</div>'
        )

    # Fix cards with tooltips
    fix_cards_html = []
    for i, fix in enumerate(fixes, 1):
        effort = fix.get("effort", "medium")
        effort_class = "low" if "low" in effort else ("high" if "high" in effort else "medium")
        action_text = fix.get("action", "")
        confidence = fix.get("confidence", "")
        evidence = fix.get("evidence", "")
        what_not_to_do = fix.get("what_not_to_do", "")

        # Find matching tooltip by checking if any key phrase appears in the action
        tip_html = ""
        for keyword, tip_text in fix_tips.items():
            if keyword.lower() in action_text.lower():
                tip_html = (
                    f'<span class="tooltip-wrap">'
                    f'<span class="tooltip-icon">?</span>'
                    f'<span class="tooltip-bubble">{tip_text}</span>'
                    f'</span>'
                )
                break

        # Confidence badge next to fix number
        conf_badge_html = ""
        if confidence:
            conf_colors = {
                "Confirmed": ("#00d68f", "#0a2e1f"),
                "Likely": ("#ffc048", "#2e2510"),
                "Hypothesis": ("#8b95a5", "#1e2228"),
            }
            bg, text_bg = conf_colors.get(confidence, ("#8b95a5", "#1e2228"))
            conf_badge_html = (
                f'<span style="display:inline-block;font-size:0.65rem;padding:1px 6px;'
                f'border-radius:4px;background:{text_bg};color:{bg};'
                f'border:1px solid {bg};margin-left:8px;vertical-align:middle;">'
                f'{_escape_html(confidence)}</span>'
            )

        # Evidence line
        evidence_html = ""
        if evidence:
            evidence_html = (
                f'<div style="font-size:0.8rem;font-style:italic;color:var(--text-muted);'
                f'margin-top:6px;padding-left:4px;">{_escape_html(evidence)}</div>'
            )

        # What NOT to do warning box
        warning_html = ""
        if what_not_to_do:
            warning_html = (
                f'<div style="margin-top:10px;padding:10px 14px;border:1px solid #ff6b6b;'
                f'border-left:3px solid #ff6b6b;border-radius:6px;background:rgba(255,107,107,0.06);'
                f'font-size:0.82rem;color:#ff6b6b;">'
                f'<strong>Do NOT:</strong> {_escape_html(what_not_to_do)}</div>'
            )

        fix_cards_html.append(
            f'<div class="fix-card">'
            f'<div class="fix-number" style="background:var(--accent-glow);color:var(--accent)">{i}{conf_badge_html}</div>'
            f'<div class="fix-body">'
            f'<div class="fix-action">{_escape_html(action_text)}{tip_html}</div>'
            f'{evidence_html}'
            f'<div class="fix-meta">'
            f'<span class="fix-tag fix-tag-impact">{_escape_html(fix.get("impact", ""))}</span>'
            f'<span class="fix-tag fix-tag-effort-{effort_class}">Effort: {_escape_html(effort)}</span>'
            f'</div>'
            f'{warning_html}'
            f'</div></div>'
        )

    # Generate optimization sections
    # If no separate optimization data, build "How to Fix" from priority_fixes
    if not optimization_data and fixes:
        optimization_data = _build_optimization_from_fixes(fixes, data)
    optimization_html = _generate_optimization_section(optimization_data)
    technical_html = _generate_technical_section(optimization_data)

    # Business type badge HTML
    business_type_html = ""
    if business_type:
        business_type_html = (
            f'<span style="display:inline-block;font-size:0.75rem;padding:3px 10px;'
            f'border-radius:12px;background:rgba(99,102,241,0.12);color:#818cf8;'
            f'border:1px solid rgba(99,102,241,0.25);margin-left:12px;vertical-align:middle;'
            f'font-weight:500;">{_escape_html(business_type)}</span>'
        )

    # Fill template
    html = template
    replacements = {
        "{{DOMAIN}}": _escape_html(domain),
        "{{BRAND_NAME}}": _escape_html(brand),
        "{{AUDIT_DATE}}": _escape_html(audit_date),
        "{{PAGES_ANALYZED}}": str(pages_count),
        "{{OVERALL_SCORE}}": str(score),
        "{{SCORE_COLOR}}": score_color,
        "{{CIRCUMFERENCE}}": f"{circumference:.2f}",
        "{{DASH_OFFSET}}": f"{dash_offset:.2f}",
        "{{TIER_KEY}}": tier_key,
        "{{TIER_LABEL}}": _escape_html(tier_label),
        "{{TIER_DESCRIPTION}}": _escape_html(tier_desc),
        "{{BUSINESS_TYPE_BADGE}}": business_type_html,
        "{{DIMENSION_BARS}}": "\n    ".join(bars_html),
        "{{FINDING_CARDS}}": "\n    ".join(cards_html),
        "{{FIX_CARDS}}": "\n    ".join(fix_cards_html),
        "{{OPTIMIZATION_SECTION}}": optimization_html,
        "{{TECHNICAL_SECTION}}": technical_html,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


def main():
    parser = argparse.ArgumentParser(description="AI SEO Report Formatter")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--type", required=True, choices=["audit", "monitor", "measure"],
                        help="Report type")
    parser.add_argument("--format", choices=["markdown", "html", "fixes"], default="markdown",
                        help="Output format: markdown, html, or fixes (machine-readable JSON fix list)")
    parser.add_argument("--output", help="Custom output path")
    parser.add_argument("--optimization", help="Path to optimization data JSON (audit HTML only)")

    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    # Load optimization data if provided
    optimization_data = None
    if args.optimization:
        with open(args.optimization) as f:
            optimization_data = json.load(f)

    output_format = getattr(args, 'format', 'markdown')
    ext = ".html" if output_format == "html" else (".json" if output_format == "fixes" else ".md")

    if args.type == "audit":
        if output_format == "html":
            report = format_audit_html(data, optimization_data=optimization_data)
        elif output_format == "fixes":
            report = format_audit_fixes(data)
        else:
            report = format_audit_report(data)
        slug = data.get("domain", "unknown").replace(".", "_")
        subdir = "audits"
        if output_format == "fixes":
            slug = slug + "_fixes"
    elif args.type == "monitor":
        report = format_monitor_report(data)
        slug = data.get("brand", "unknown").replace(" ", "_").lower()
        subdir = "monitoring"
    elif args.type == "measure":
        report = format_measure_report(data)
        slug = data.get("brand", "unknown").replace(" ", "_").lower()
        subdir = "measurement"
    else:
        print(json.dumps({"success": False, "message": f"Unknown type: {args.type}"}))
        sys.exit(1)

    output_dir = PROJECT_ROOT / "data" / "ai_seo" / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output or str(output_dir / f"{slug}_{date.today().isoformat()}{ext}")

    # Sanitize surrogates from crawled content before writing
    report = report.encode('utf-8', errors='replace').decode('utf-8')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(json.dumps({
        "success": True,
        "output": output_path,
        "type": args.type,
        "lines": len(report.split('\n'))
    }, indent=2))


if __name__ == "__main__":
    main()
